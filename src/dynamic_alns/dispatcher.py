from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass

import pandas as pd

from .alns_adapter import ALNSScenarioSolver
from .config_dynamic import DynamicMSAConfig
from .consensus import ConsensusSelector
from .data_normalizer import is_pickup_value, normalize_requests_df
from .dynamic_pickup_inserter import DynamicPickupInserter
from .entities import OnlineState, PlannedTrip, ScenarioPlan, VehicleState
from .icd import ICDPickupClassifier
from .scenario_sampler_msa import FutureScenarioSampler
from .parallel_scenarios import ScenarioBatchExecutor, build_scenario_tasks


@dataclass
class DispatchResult:
    final_state: OnlineState
    committed_trips: pd.DataFrame
    dynamic_insertion_log: pd.DataFrame
    summary: dict

    @property
    def dynamic_insertions(self) -> pd.DataFrame:
        return self.dynamic_insertion_log


class MSADynamicDispatcherALNS:
    """Runner SDVRPTW con MSA + ALNS + insercion dinamica de pickups por ICD.

    En 09:00 y retornos al depot se corre MSA+ALNS. Mientras un camion esta
    ejecutando un viaje, un pickup nuevo puede insertarse en el sufijo modificable
    de la ruta mediante ICD. Si el camion ya va hacia un cliente, ese cliente queda
    bloqueado y no se cambia.
    """

    def __init__(self, config: DynamicMSAConfig):
        config.validate()
        self.config = config
        self.sampler = FutureScenarioSampler(config)
        self.solver = ALNSScenarioSolver(config)
        self.scenario_executor = ScenarioBatchExecutor(config)
        self.consensus = ConsensusSelector(config)
        self.icd = ICDPickupClassifier(config)
        self.dynamic_inserter = DynamicPickupInserter(config, self.sampler)
        self.dynamic_log: list[dict] = []
        self.msa_wall_times_sec: list[float] = []
        self.msa_scenarios_completed: int = 0

    def initial_state(self) -> OnlineState:
        vehicles = {
            vid: VehicleState(vehicle_id=vid, available_time=float(self.config.shift_start_sec), status="at_depot")
            for vid in range(self.config.nb_vehicles)
        }
        return OnlineState(now_sec=float(self.config.shift_start_sec), vehicles=vehicles)

    def _outsourcing_deadline(self, row: pd.Series) -> float:
        dx = abs(float(row["x"]) - self.config.depot_xy[0])
        dy = abs(float(row["y"]) - self.config.depot_xy[1])
        tau = (dx + dy) / self.config.vehicle_speed_m_per_s
        return float(row["deadlines"]) - self.config.outsourcing_notice_sec - tau

    def _mark_expired_requests(self, state: OnlineState, requests_df: pd.DataFrame) -> None:
        blocked = state.served_ids | state.outsourced_ids | state.scheduled_ids
        unresolved_known = requests_df.loc[
            (requests_df["arrivals"] <= state.now_sec)
            & ~requests_df["id"].astype(str).isin(blocked)
        ].copy()
        for _, row in unresolved_known.iterrows():
            rid = str(row["id"])
            if state.now_sec >= self._outsourcing_deadline(row):
                state.outsourced_ids.add(rid)

    def _build_known_unresolved(self, state: OnlineState, all_requests: pd.DataFrame) -> pd.DataFrame:
        known = all_requests.loc[all_requests["arrivals"] <= state.now_sec].copy()
        blocked = state.served_ids | state.outsourced_ids | state.scheduled_ids
        known = known.loc[~known["id"].astype(str).isin(blocked)].copy()
        return known.reset_index(drop=True)

    def _solve_msa_at_state(
        self,
        state: OnlineState,
        known_unresolved: pd.DataFrame,
    ) -> tuple[ScenarioPlan | None, list[ScenarioPlan]]:
        available = state.available_vehicle_ids()
        if not available or known_unresolved.empty:
            return None, []

        started = time.perf_counter()
        future_scenarios = self.sampler.sample(state.now_sec)
        if not future_scenarios:
            return None, []

        per_scenario_limit = self.scenario_executor.per_scenario_time_limit(
            len(future_scenarios)
        )
        tasks = build_scenario_tasks(
            config=self.config,
            known_df=known_unresolved,
            future_scenarios=future_scenarios,
            now_sec=state.now_sec,
            physical_vehicle_ids=available,
            per_scenario_time_limit_sec=per_scenario_limit,
        )
        results = self.scenario_executor.solve(tasks)
        projected_plans = [
            result.plan
            for result in results
            if result.plan is not None and result.error is None
        ]

        self.msa_scenarios_completed += len(projected_plans)
        self.msa_wall_times_sec.append(time.perf_counter() - started)

        selected = self.consensus.select(projected_plans, vehicle_ids=available)
        return selected, projected_plans

    def _commit_plan(self, state: OnlineState, plan: ScenarioPlan) -> None:
        if plan is None:
            return
        committed_vehicle_ids: set[int] = set()
        for trip in sorted(plan.trips, key=lambda t: (int(t.vehicle_id), int(t.trip))):
            vehicle_id = int(trip.vehicle_id)
            if self.config.commit_only_first_trip and vehicle_id in committed_vehicle_ids:
                continue
            if not trip.customer_ids:
                continue
            if vehicle_id not in state.vehicles:
                continue
            if state.vehicles[vehicle_id].status != "at_depot":
                continue

            state.committed_trips.append(trip)
            state.active_trips[vehicle_id] = trip
            state.scheduled_ids.update(str(cid) for cid in trip.customer_ids)
            vehicle = state.vehicles[vehicle_id]
            vehicle.available_time = min(float(trip.return_to_depot_time), float(self.config.shift_end_sec))
            vehicle.status = "done" if vehicle.available_time >= self.config.shift_end_sec else "en_route"
            vehicle.current_target_id = self._current_target(trip, state.now_sec)
            committed_vehicle_ids.add(vehicle_id)

    def _current_target(self, trip: PlannedTrip, now_sec: float) -> str | None:
        for stop in trip.stops:
            if stop.service_end > now_sec + 1e-9:
                return str(stop.request_id)
        return "DEPOT" if trip.return_to_depot_time > now_sec else None

    def _update_vehicle_progress(self, state: OnlineState) -> bool:
        any_returned = False
        to_remove: list[int] = []
        for vehicle_id, trip in list(state.active_trips.items()):
            for stop in trip.stops:
                rid = str(stop.request_id)
                if stop.service_end <= state.now_sec + 1e-9:
                    state.served_ids.add(rid)
                    state.scheduled_ids.discard(rid)

            vehicle = state.vehicles[vehicle_id]
            if trip.return_to_depot_time <= state.now_sec + 1e-9:
                for rid in trip.customer_ids:
                    state.served_ids.add(str(rid))
                    state.scheduled_ids.discard(str(rid))
                vehicle.status = "at_depot" if state.now_sec < self.config.shift_end_sec else "done"
                vehicle.available_time = float(state.now_sec)
                vehicle.current_target_id = None
                to_remove.append(vehicle_id)
                any_returned = True
            else:
                target = self._current_target(trip, state.now_sec)
                vehicle.current_target_id = target
                vehicle.status = "returning" if target == "DEPOT" else "en_route"
                vehicle.available_time = float(trip.return_to_depot_time)
        for vehicle_id in to_remove:
            state.active_trips.pop(vehicle_id, None)
        return any_returned

    def _process_new_arrivals_for_dynamic_insertion(self, state: OnlineState, all_requests: pd.DataFrame) -> None:
        arrivals = all_requests.loc[
            (all_requests["arrivals"] <= state.now_sec)
            & ~all_requests["id"].astype(str).isin(state.processed_arrival_ids)
        ].copy()
        if arrivals.empty:
            return
        for _, row in arrivals.iterrows():
            rid = str(row["id"])
            state.processed_arrival_ids.add(rid)
            if not self.config.enable_dynamic_pickup_insertion:
                continue
            if not is_pickup_value(row["indicador"]):
                continue
            if rid in state.served_ids or rid in state.outsourced_ids or rid in state.scheduled_ids:
                continue
            decision = self.dynamic_inserter.handle_pickup_arrival(state, row)
            self.dynamic_log.append({
                "time": state.now_sec,
                "request_id": rid,
                "decision": decision.decision,
                "phi": decision.phi,
                "vehicle_id": decision.vehicle_id,
                "position": decision.position,
            })

    def _next_event_time(self, state: OnlineState, all_requests: pd.DataFrame) -> float:
        future_arrivals = all_requests.loc[all_requests["arrivals"] > state.now_sec, "arrivals"].tolist()
        next_arrival = min(future_arrivals) if future_arrivals else math.inf
        next_vehicle_time = state.next_vehicle_available_time()
        next_vehicle_time = next_vehicle_time if next_vehicle_time is not None and next_vehicle_time > state.now_sec else math.inf
        next_stop_time = state.next_active_stop_time()
        next_stop_time = next_stop_time if next_stop_time is not None and next_stop_time > state.now_sec else math.inf
        return min(next_arrival, next_vehicle_time, next_stop_time, self.config.shift_end_sec)

    def _run_replica_impl(self, requests_df: pd.DataFrame) -> DispatchResult:
        all_requests = normalize_requests_df(requests_df)
        state = self.initial_state()
        self.dynamic_log = []
        state.processed_arrival_ids.update(
            str(x) for x in all_requests.loc[all_requests["arrivals"] <= state.now_sec, "id"].tolist()
        )
        initial_dispatch_done = False

        while state.now_sec < self.config.shift_end_sec:
            returned_now = self._update_vehicle_progress(state)
            self._mark_expired_requests(state, all_requests)
            known_unresolved = self._build_known_unresolved(state, all_requests)

            available = state.available_vehicle_ids()
            should_run_msa = bool(available) and not known_unresolved.empty and (
                not initial_dispatch_done
                or returned_now
                or self.config.run_msa_on_request_arrival_if_vehicle_waiting
            )
            if should_run_msa:
                selected, scenario_plans = self._solve_msa_at_state(state, known_unresolved)
                initial_dispatch_done = True
                if selected is not None:
                    accepted, postponed, undecided = self.icd.classify(known_unresolved, scenario_plans)
                    state.accepted_pickup_ids.update(accepted)
                    state.postponed_ids.update(postponed)
                    self._commit_plan(state, selected)

            next_time = self._next_event_time(state, all_requests)
            if not math.isfinite(next_time) or next_time <= state.now_sec + 1e-9:
                break
            state.now_sec = float(next_time)
            self._update_vehicle_progress(state)
            self._process_new_arrivals_for_dynamic_insertion(state, all_requests)

        state.now_sec = float(self.config.shift_end_sec)
        self._update_vehicle_progress(state)
        all_ids = {str(x) for x in all_requests["id"].tolist()}
        unresolved_final = all_ids - state.served_ids - state.outsourced_ids
        state.outsourced_ids.update(unresolved_final)

        trips_df = pd.DataFrame([asdict(tr) for tr in state.committed_trips])
        dynamic_df = pd.DataFrame(self.dynamic_log)
        total_possible_profit = float(all_requests["profits"].sum())
        served_profit = float(all_requests.loc[all_requests["id"].astype(str).isin(state.served_ids), "profits"].sum())
        summary = {
            "served_customers": len(state.served_ids),
            "outsourced_customers": len(state.outsourced_ids),
            "total_customers": len(all_requests),
            "total_profit": served_profit,
            "total_possible_profit": total_possible_profit,
            "profit_rate": served_profit / total_possible_profit if total_possible_profit else 0.0,
            "total_distance_km": float(trips_df["total_distance_km"].sum()) if not trips_df.empty else 0.0,
            "nb_trips": len(state.committed_trips),
            "dynamic_pickups_inserted": len(state.dynamic_inserted_pickup_ids),
            "dynamic_pickups_postponed": len(state.dynamic_rejected_pickup_ids),
            "dynamic_pickups_undecided": len(state.dynamic_undecided_pickup_ids),
            "solver": "MSA+ALNS+ICD-dynamic-pickups",
            "consensus_mode": self.config.consensus_mode,
            "parallel_backend": self.config.parallel_backend,
            "parallel_workers": self.scenario_executor.resolved_workers,
            "msa_calls": len(self.msa_wall_times_sec),
            "msa_scenarios_completed": self.msa_scenarios_completed,
            "msa_total_wall_time_sec": float(sum(self.msa_wall_times_sec)),
            "msa_avg_wall_time_sec": (
                float(sum(self.msa_wall_times_sec) / len(self.msa_wall_times_sec))
                if self.msa_wall_times_sec
                else 0.0
            ),
            "msa_max_wall_time_sec": (
                float(max(self.msa_wall_times_sec)) if self.msa_wall_times_sec else 0.0
            ),
            "parallel_worker_errors": len(self.scenario_executor.worker_errors),
            "parallel_fallback_tasks": self.scenario_executor.tasks_fallback,
        }
        return DispatchResult(state, trips_df, dynamic_df, summary)

    def run_replica(self, requests_df: pd.DataFrame) -> DispatchResult:
        """Ejecuta una replica y mantiene un pool persistente durante todo el dia.

        Crear procesos en cada retorno al depot es caro, especialmente en Windows.
        Por eso el pool se crea de forma perezosa en el primer MSA, se reutiliza
        durante todos los eventos y se cierra al terminar la replica.
        """

        self.dynamic_log = []
        self.msa_wall_times_sec = []
        self.msa_scenarios_completed = 0
        self.scenario_executor.worker_errors = []
        self.scenario_executor.tasks_completed = 0
        self.scenario_executor.tasks_fallback = 0
        try:
            return self._run_replica_impl(requests_df)
        finally:
            self.scenario_executor.close()
