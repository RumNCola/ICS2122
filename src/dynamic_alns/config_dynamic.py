from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DistanceMetric = Literal["manhattan", "euclidean"]
ConsensusMode = Literal["van_hentenryck", "exact_next_stop", "served_set"]


@dataclass(slots=True)
class DynamicMSAConfig:
    """Configuracion para SDVRPTW + MSA + ALNS + insercion dinamica ICD."""

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
    scenario_time_limit_sec: float = 15.0
    respect_msa_event_budget: bool = False
    msa_event_budget_sec: float = 5 * 60

    # Consenso MSA. En modo Van Hentenryck no se usa threshold.
    consensus_mode: ConsensusMode = "van_hentenryck"
    consensus_threshold: float | None = None

    # ALNS por escenario
    max_trips_per_vehicle: int = 20
    alns_max_iterations: int = 20_000
    alns_min_remove_fraction: float = 0.08
    alns_max_remove_fraction: float = 0.25
    alns_min_remove: int = 1
    alns_max_remove: int = 35
    alns_initial_temperature: float = 1.0
    alns_cooling_rate: float = 0.995
    alns_segment_length: int = 100
    alns_reaction_factor: float = 0.25
    alns_score_global_best: float = 8.0
    alns_score_improved: float = 4.0
    alns_score_accepted: float = 1.0
    alns_distance_weight: float = 1e-4
    alns_trip_penalty: float = 1e-3
    alns_repair_noise: float = 0.0
    alns_enable_extended_operators: bool = True

    # ICD para pickups dinamicos en rutas ya iniciadas
    icd_dispatch_threshold: float = 0.50
    icd_postpone_threshold: float = 0.20
    enable_dynamic_pickup_insertion: bool = True
    dynamic_insertion_n_scenarios: int | None = None
    dynamic_insertion_max_future_pickups_per_scenario: int = 12
    dynamic_insertion_use_icd_thresholds: bool = True
    dynamic_insertion_min_phi_to_insert: float | None = None
    dynamic_insertion_margin_sec: float = 0.0

    # Simulacion
    seed: int | None = 42
    commit_only_first_trip: bool = True
    run_msa_on_request_arrival_if_vehicle_waiting: bool = True
    keep_sampler_excels: bool = False

    def validate(self) -> None:
        if self.instancia not in {1, 2, 3, 4}:
            raise ValueError("instancia debe ser 1, 2, 3 o 4")
        if self.nb_vehicles <= 0:
            raise ValueError("nb_vehicles debe ser positivo")
        if self.shift_start_sec >= self.shift_end_sec:
            raise ValueError("shift_start_sec debe ser menor que shift_end_sec")
        if self.vehicle_speed_m_per_s <= 0:
            raise ValueError("vehicle_speed_m_per_s debe ser positivo")
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
        if self.dynamic_insertion_n_scenarios is not None and self.dynamic_insertion_n_scenarios <= 0:
            raise ValueError("dynamic_insertion_n_scenarios debe ser positivo o None")
        if self.dynamic_insertion_min_phi_to_insert is not None and not (0 <= self.dynamic_insertion_min_phi_to_insert <= 1):
            raise ValueError("dynamic_insertion_min_phi_to_insert debe estar entre 0 y 1 o ser None")
        if self.max_trips_per_vehicle <= 0:
            raise ValueError("max_trips_per_vehicle debe ser positivo")
        if not (0 < self.alns_min_remove_fraction <= self.alns_max_remove_fraction <= 1):
            raise ValueError("fracciones de remocion ALNS invalidas")
        if self.alns_initial_temperature <= 0:
            raise ValueError("alns_initial_temperature debe ser positivo")
        if not (0 < self.alns_cooling_rate <= 1):
            raise ValueError("alns_cooling_rate debe estar en (0, 1]")
