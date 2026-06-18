from __future__ import annotations

import pandas as pd

from src.deterministic_bound import VRPTWConfig, solve_vrptw_hexaly

from .config_dynamic import DynamicMSAConfig
from .data_normalizer import normalize_requests_df
from .entities import PlannedTrip, ScenarioPlan


class HexalyScenarioSolver:
    """Adaptador entre MSA dinamico y tu solver deterministico Hexaly.

    Importante: deterministic_bound.py modela viajes depot -> clientes -> depot.
    Por eso esta version usa Hexaly en decisiones tipo dispatch wave desde depot.
    Si un camion esta en ruta, no se reoptimiza su cliente actual aqui.
    """

    def __init__(self, config: DynamicMSAConfig):
        self.config = config

    def _build_cfg(self, now_sec: float, nb_available_vehicles: int) -> VRPTWConfig:
        cfg = self.config
        if cfg.scenario_time_limit_sec >= 10:
            factor = 1
        else:
            if now_sec <= 3600 * 11:
                factor = 13/8

            elif now_sec >= 3600 * 11 and now_sec <= 3600 * 15:
                # Durante el peak de demanda, se aumenta el tiempo de ejecución al doble.
                factor = 12/8
            else:
                factor = 1

        # Achico el factor para la última media hora
        if now_sec > 3600 * 15 and now_sec <= 3600 * 16:
            factor = 6 / 8
        elif now_sec > 3600 * 16 and now_sec <= 3600 * 16.75:
            factor = 3/8
        elif now_sec > 3600 * 16.75:
            factor = 2/8
            
        print(f'Hora actual en la simulación: {now_sec/3600:.2f}h, {now_sec}s')

        return VRPTWConfig(
            nb_vehicles=max(1, nb_available_vehicles),
            max_trips_per_vehicle=cfg.max_trips_per_vehicle,
            depot_xy=cfg.depot_xy,
            shift_start_sec=float(now_sec),
            shift_end_sec=float(cfg.shift_end_sec),
            vehicle_speed_m_per_s=cfg.vehicle_speed_m_per_s,
            service_time_default=float(cfg.service_time_sec),
            force_service_time_default=True,
            distance_metric=cfg.distance_metric,
            require_all_customers=False,
            hard_time_windows=True,
            deadline_is_latest_start=True,
            delivery_must_be_loaded_at_depot=True,
            pickup_ready_policy="arrival",
            time_limit_sec=int(cfg.scenario_time_limit_sec * factor),
            minimize_trips_after_profit=cfg.minimize_trips_after_profit,
            minimize_distance_after_profit=cfg.minimize_distance_after_profit,
            distance_cost_per_km_in_profit=cfg.distance_cost_per_km_in_profit,
            seed=cfg.seed,
        )

    def solve(self, requests_df: pd.DataFrame, now_sec: float, physical_vehicle_ids: list[int], scenario_id: int) -> ScenarioPlan:
        requests = normalize_requests_df(requests_df)
        if requests.empty or not physical_vehicle_ids:
            return ScenarioPlan(scenario_id=scenario_id, trips=[], total_profit=0.0, total_distance_km=0.0, served_ids=set())

        # El solver filtra por replica si existe. Forzamos una replica unica para el escenario MSA.
        requests = requests.copy().reset_index(drop=True)
        requests["replica"] = 0

        hx_cfg = self._build_cfg(now_sec, nb_available_vehicles=len(physical_vehicle_ids))
        sol = solve_vrptw_hexaly(requests, hx_cfg, replica_id=0)

        trips: list[PlannedTrip] = []
        trips_df = sol.trips_as_dataframe()
        if not trips_df.empty:
            for _, row in trips_df.iterrows():
                local_vehicle = int(row["vehicle"])
                if local_vehicle >= len(physical_vehicle_ids):
                    continue
                physical_vehicle = physical_vehicle_ids[local_vehicle]
                ids = list(row["customer_ids"])
                trips.append(
                    PlannedTrip(
                        vehicle_id=physical_vehicle,
                        trip=int(row["trip"]),
                        customer_ids=[str(x) for x in ids],
                        departure_time_from_depot=float(row["departure_time_from_depot"]),
                        return_to_depot_time=float(row["return_to_depot_time"]),
                        total_profit=float(row["total_profit"]),
                        total_distance_km=float(row["total_distance_km"]),
                    )
                )

        return ScenarioPlan(
            scenario_id=scenario_id,
            trips=trips,
            total_profit=float(sol.total_profit),
            total_distance_km=float(sol.total_distance_km),
            served_ids={str(x) for x in sol.served_ids},
            raw_solution=sol,
        )
