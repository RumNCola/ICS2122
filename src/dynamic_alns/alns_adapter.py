from __future__ import annotations

import pandas as pd

from .alns_static_solver import ALNSPrizeCollectingVRPTW, EvalResult, SolutionRoutes
from .config_dynamic import DynamicMSAConfig
from .data_normalizer import normalize_requests_df
from .entities import PlannedStop, PlannedTrip, ScenarioPlan


class ALNSScenarioSolver:
    """Adaptador entre MSA dinamico y ALNS estatico.

    Entrada: pedidos conocidos + futuros sampleados, tiempo actual y camiones disponibles.
    Salida: ScenarioPlan, compatible con el selector de consenso de Van Hentenryck.
    """

    def __init__(self, config: DynamicMSAConfig):
        self.config = config

    def _scenario_time_limit(self) -> float:
        cfg = self.config
        if cfg.respect_msa_event_budget:
            return max(0.1, min(cfg.scenario_time_limit_sec, cfg.msa_event_budget_sec / max(1, cfg.n_scenarios)))
        return float(cfg.scenario_time_limit_sec)

    def solve(
        self,
        requests_df: pd.DataFrame,
        now_sec: float,
        physical_vehicle_ids: list[int],
        scenario_id: int,
        time_limit_override_sec: float | None = None,
    ) -> ScenarioPlan:
        requests = normalize_requests_df(requests_df)
        if requests.empty or not physical_vehicle_ids:
            return ScenarioPlan(
                scenario_id=scenario_id,
                trips=[],
                total_profit=0.0,
                total_distance_km=0.0,
                served_ids=set(),
            )

        requests = requests.copy().reset_index(drop=True)
        requests["id"] = requests["id"].astype(str)
        requests["replica"] = 0

        seed = None if self.config.seed is None else int(self.config.seed + 10_000 * scenario_id)
        solver = ALNSPrizeCollectingVRPTW(
            self.config,
            requests,
            now_sec=now_sec,
            vehicle_ids=physical_vehicle_ids,
            seed=seed,
        )
        time_limit = (
            float(time_limit_override_sec)
            if time_limit_override_sec is not None
            else self._scenario_time_limit()
        )
        ev = solver.solve(time_limit)
        return self._eval_to_plan(ev, scenario_id=scenario_id)

    def project_plan_to_known(
        self,
        plan: ScenarioPlan,
        known_df: pd.DataFrame,
        now_sec: float,
        physical_vehicle_ids: list[int],
    ) -> ScenarioPlan:
        """Proyecta un plan de escenario a clientes conocidos y recalcula tiempos/distancia.

        Esto es mas fiel a MSA: se resuelven escenarios conocidos+futuros, pero antes de
        ejecutar se eliminan pedidos futuros. La ruta restante debe comprimirse y reevaluarse.
        """
        known = normalize_requests_df(known_df)
        if known.empty or not plan.trips:
            return ScenarioPlan(plan.scenario_id, [], 0.0, 0.0, set(), raw_solution=plan.raw_solution)

        known["id"] = known["id"].astype(str)
        known_ids = set(known["id"].tolist())
        routes: SolutionRoutes = {int(v): [] for v in physical_vehicle_ids}

        for trip in sorted(plan.trips, key=lambda t: (int(t.vehicle_id), int(t.trip))):
            ids = [str(cid) for cid in trip.customer_ids if str(cid) in known_ids]
            if ids:
                routes.setdefault(int(trip.vehicle_id), []).append(ids)

        if not any(routes.values()):
            return ScenarioPlan(plan.scenario_id, [], 0.0, 0.0, set(), raw_solution=plan.raw_solution)

        # Se crea un evaluador solo con clientes conocidos. No corre ALNS; solo evalua las secuencias.
        eval_solver = ALNSPrizeCollectingVRPTW(
            self.config,
            known,
            now_sec=now_sec,
            vehicle_ids=physical_vehicle_ids,
            seed=self.config.seed,
        )
        ev = eval_solver.evaluate_fixed_sequences(routes)
        if not ev.feasible:
            # En teoria remover futuros no deberia romper factibilidad. Si pasa, descartamos.
            return ScenarioPlan(plan.scenario_id, [], 0.0, 0.0, set(), raw_solution=plan.raw_solution)
        return self._eval_to_plan(ev, scenario_id=plan.scenario_id, raw_solution=plan.raw_solution)

    @staticmethod
    def _eval_to_plan(ev: EvalResult, *, scenario_id: int, raw_solution: object | None = None) -> ScenarioPlan:
        trips = [
            PlannedTrip(
                vehicle_id=int(tr.vehicle_id),
                trip=int(tr.trip),
                customer_ids=[str(x) for x in tr.customer_ids],
                departure_time_from_depot=float(tr.departure_time_from_depot),
                return_to_depot_time=float(tr.return_to_depot_time),
                total_profit=float(tr.total_profit),
                total_distance_km=float(tr.total_distance_km),
                stops=list(getattr(tr, "stops", [])),
                source="msa_alns",
            )
            for tr in ev.trips
            if tr.customer_ids
        ]
        served = {cid for tr in trips for cid in tr.customer_ids}
        return ScenarioPlan(
            scenario_id=int(scenario_id),
            trips=trips,
            total_profit=float(ev.total_profit),
            total_distance_km=float(ev.total_distance_km),
            served_ids=served,
            raw_solution=raw_solution if raw_solution is not None else ev,
        )
