from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import pandas as pd

from .config_dynamic import DynamicMSAConfig
from .consensus import ConsensusSelector
from .data_normalizer import normalize_requests_df
from .entities import OnlineState, PlannedTrip, ScenarioPlan, VehicleState
from .hexaly_adapter import HexalyScenarioSolver
from .icd import ICDPickupClassifier
from .scenario_sampler_msa import FutureScenarioSampler


@dataclass
class DispatchResult:
    final_state: OnlineState
    committed_trips: pd.DataFrame
    summary: dict


class MSADynamicDispatcher:
    """Runner preliminar SDVRPTW con MSA + Hexaly.

    Logica operacional de esta version:
    1. Mantiene eventos reales de la replica por arrival time.
    2. Cuando uno o mas camiones estan en depot, resuelve MSA con Hexaly.
    3. Cada escenario = pedidos conocidos no servidos + pedidos futuros sampleados.
    4. Hexaly resuelve rapido cada escenario; se proyecta a conocidos y se elige por consenso.
    5. Se compromete solo el primer viaje de cada camion disponible.

    usa deterministic_bound.py. La insercion en ruta de pickups dinamicos
    queda aislada para una siguiente iteracion, porque requiere extender el solver o usar
    heuristica de insercion sobre rutas parcialmente bloqueadas.
    """

    def __init__(self, config: DynamicMSAConfig):
        config.validate()
        self.config = config
        self.sampler = FutureScenarioSampler(config)
        self.solver = HexalyScenarioSolver(config)
        self.consensus = ConsensusSelector(config)
        self.icd = ICDPickupClassifier(config)

    def initial_state(self) -> OnlineState:
        vehicles = {
            vid: VehicleState(vehicle_id=vid, available_time=float(self.config.shift_start_sec))
            for vid in range(self.config.nb_vehicles)
        }
        return OnlineState(now_sec=float(self.config.shift_start_sec), vehicles=vehicles)

    def _outsourcing_deadline(self, row: pd.Series) -> float:
        # Regla: tercerizar 5 min + tau_0d antes del deadline.
        # Para simplificar tau_0d se aproxima como Manhattan depot-cliente / velocidad.
        dx = abs(float(row["x"]) - self.config.depot_xy[0])
        dy = abs(float(row["y"]) - self.config.depot_xy[1])
        tau = (dx + dy) / self.config.vehicle_speed_m_per_s
        return float(row["deadlines"]) - self.config.outsourcing_notice_sec - tau

    def _mark_expired_requests(self, state: OnlineState, requests_df: pd.DataFrame) -> None:
        unresolved = requests_df.loc[
            ~requests_df["id"].astype(str).isin(state.served_ids | state.outsourced_ids)
        ].copy()
        for _, row in unresolved.iterrows():
            rid = str(row["id"])
            if state.now_sec >= self._outsourcing_deadline(row):
                state.outsourced_ids.add(rid)

    def _build_known_unresolved(self, state: OnlineState, all_requests: pd.DataFrame) -> pd.DataFrame:
        known = all_requests.loc[all_requests["arrivals"] <= state.now_sec].copy()
        blocked = state.served_ids | state.outsourced_ids
        known = known.loc[~known["id"].astype(str).isin(blocked)].copy()
        return known.reset_index(drop=True)

    def _solve_msa_at_state(self, state: OnlineState, known_unresolved: pd.DataFrame) -> tuple[ScenarioPlan | None, list[ScenarioPlan]]:
        available = state.available_vehicle_ids()
        if not available or known_unresolved.empty:
            return None, []

        future_scenarios = self.sampler.sample(state.now_sec)
        known_ids = {str(x) for x in known_unresolved["id"].tolist()}
        profit_by_id = {
            str(row["id"]): float(row["profits"])
            for _, row in known_unresolved.iterrows()
        }
        projected_plans: list[ScenarioPlan] = []

        for sid, future in enumerate(future_scenarios):
            scen_df = pd.concat([known_unresolved, future], ignore_index=True)
            if scen_df.empty:
                continue
            plan = self.solver.solve(
                scen_df,
                now_sec=state.now_sec,
                physical_vehicle_ids=available,
                scenario_id=sid,
            )
            projected_plans.append(plan.projected(known_ids, profit_by_id=profit_by_id))

        selected = self.consensus.select(projected_plans, vehicle_ids=available)
        return selected, projected_plans

    def _commit_plan(self, state: OnlineState, plan: ScenarioPlan) -> None:
        if plan is None:
            return

        for trip in sorted(plan.trips, key=lambda t: (t.vehicle_id, t.trip)):
            if self.config.commit_only_first_trip:
                already_committed_for_vehicle = any(
                    tr.vehicle_id == trip.vehicle_id and tr.departure_time_from_depot >= state.now_sec
                    for tr in state.committed_trips
                )
                if already_committed_for_vehicle:
                    continue

            if not trip.customer_ids:
                continue

            state.committed_trips.append(trip)
            state.served_ids.update(trip.customer_ids)
            vehicle = state.vehicles[trip.vehicle_id]
            vehicle.available_time = min(float(trip.return_to_depot_time), float(self.config.shift_end_sec))
            vehicle.status = "at_depot" if vehicle.available_time < self.config.shift_end_sec else "done"

    def run_replica(self, requests_df: pd.DataFrame) -> DispatchResult:
        all_requests = normalize_requests_df(requests_df)
        state = self.initial_state()

        while state.now_sec < self.config.shift_end_sec:
            self._mark_expired_requests(state, all_requests)
            known_unresolved = self._build_known_unresolved(state, all_requests)

            selected, scenario_plans = self._solve_msa_at_state(state, known_unresolved)
            if selected is not None:
                accepted, postponed, undecided = self.icd.classify(known_unresolved, scenario_plans)
                state.accepted_pickup_ids.update(accepted)
                state.postponed_ids.update(postponed)
                self._commit_plan(state, selected)

            # Avanzar al proximo evento: llegada de request o retorno de camion.
            future_arrivals = all_requests.loc[all_requests["arrivals"] > state.now_sec, "arrivals"].tolist()
            next_arrival = min(future_arrivals) if future_arrivals else math.inf
            next_vehicle_time = state.next_vehicle_available_time()
            next_vehicle_time = next_vehicle_time if next_vehicle_time is not None and next_vehicle_time > state.now_sec else math.inf

            next_time = min(next_arrival, next_vehicle_time, self.config.shift_end_sec)
            if not math.isfinite(next_time) or next_time <= state.now_sec:
                break
            state.now_sec = float(next_time)

            # Marcar disponibles los camiones que ya volvieron.
            for v in state.vehicles.values():
                if v.available_time <= state.now_sec and v.status != "done":
                    v.status = "at_depot"

            # Cierre: si no quedan pedidos futuros ni conocidos y todos estan en depot, avanzar al proximo arrival o terminar.
            if state.now_sec >= self.config.shift_end_sec:
                break

        # Todo lo no servido al final se terceriza.
        all_ids = {str(x) for x in all_requests["id"].tolist()}
        unresolved_final = all_ids - state.served_ids - state.outsourced_ids
        state.outsourced_ids.update(unresolved_final)

        trips_df = pd.DataFrame([asdict(tr) for tr in state.committed_trips])
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
        }
        return DispatchResult(final_state=state, committed_trips=trips_df, summary=summary)
