from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DistanceMetric = Literal["manhattan", "euclidean"]
ConsensusMode = Literal["van_hentenryck", "exact_next_stop", "served_set"]


@dataclass(slots=True)
class DynamicMSAConfig:
    """Configuracion para SDVRPTW + MSA + Hexaly.

    Los tiempos estan en segundos absolutos del dia.
    Esta configuracion sigue el caso RICAS del informe:
    - solicitudes aparecen desde 08:45,
    - camiones operan desde 09:00 hasta 17:00,
    - deliveries aparecen hasta 15:30,
    - pickups aparecen hasta 15:45.

    Si tu version final usa 08:30 como inicio operacional, cambia
    shift_start_sec y arrivals_start_sec desde el main.
    """

    instancia: int = 1
    nb_vehicles: int = 3
    depot_xy: tuple[float, float] = (10_000.0, 10_000.0)
    vehicle_speed_m_per_s: float = 25_000 / 3600
    distance_metric: DistanceMetric = "manhattan"

    arrivals_start_sec: int = 8 * 3600 + 45 * 60
    shift_start_sec: int = 9 * 3600
    delivery_cutoff_sec: int = 15 * 3600 + 30 * 60
    pickup_cutoff_sec: int = 15 * 3600 + 45 * 60
    shift_end_sec: int = 17 * 3600

    service_time_sec: int = 180
    delivery_preparation_sec: int = 900
    delivery_window_sec: int = 3 * 3600
    outsourcing_notice_sec: int = 5 * 60

    # MSA
    n_scenarios: int = 25
    lookahead_sec: int = 2 * 3600
    scenario_time_limit_sec: int = 15
    # Consenso MSA. Por defecto se usa la funcion original de Bent & Van Hentenryck.
    # consensus_threshold NO se usa en modo van_hentenryck; queda solo para comparar
    # contra modos legacy basados en coincidencia exacta.
    consensus_mode: ConsensusMode = "van_hentenryck"
    consensus_threshold: float | None = None

    # Se ejecuta MSA cuando un camion llega o va de regreso al depot.
    # En codigo preliminar se usa como gracia para planificar al regreso.
    replan_grace_sec: int = 5 * 60

    # Hexaly deterministic adapter
    max_trips_per_vehicle: int = 300
    minimize_trips_after_profit: bool = True
    minimize_distance_after_profit: bool = True
    distance_cost_per_km_in_profit: float = 0.0

    # ICD para pickups dinamicos
    icd_dispatch_threshold: float = 0.50
    icd_postpone_threshold: float = 0.20

    # Simulacion
    seed: int | None = 42
    commit_only_first_trip: bool = True
    allow_dynamic_pickup_insertion: bool = False

    def validate(self) -> None:
        if self.instancia not in {1, 2, 3, 4}:
            raise ValueError("instancia debe ser 1, 2, 3 o 4")
        if self.nb_vehicles <= 0:
            raise ValueError("nb_vehicles debe ser positivo")
        if self.shift_start_sec >= self.shift_end_sec:
            raise ValueError("shift_start_sec debe ser menor que shift_end_sec")
        if self.lookahead_sec <= 0:
            raise ValueError("lookahead_sec debe ser positivo")
        if self.n_scenarios <= 0:
            raise ValueError("n_scenarios debe ser positivo")
        if self.scenario_time_limit_sec <= 0:
            raise ValueError("scenario_time_limit_sec debe ser positivo")
        if self.consensus_threshold is not None and not (0 <= self.consensus_threshold <= 1):
            raise ValueError("consensus_threshold debe estar entre 0 y 1 o ser None")
        if not (0 <= self.icd_postpone_threshold <= self.icd_dispatch_threshold <= 1):
            raise ValueError("debe cumplirse 0 <= postpone <= dispatch <= 1")
