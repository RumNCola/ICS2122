"""

Modelo Hexaly para el problema RICAS tipo Prize-Collecting VRPTW multi-trip.

Ajustes principales respecto de la version inicial:
- Distancia Manhattan por defecto.
- 3 camiones por defecto.
- Depot en (0, 0) por defecto.
- Jornada de camiones 09:00-17:00, en segundos absolutos del dia.
- Servicio constante de 3 minutos por cliente, salvo que el escenario indique otro valor.
- indicador=False / "False" => delivery, recompensa 2.
- indicador=True / "True"   => pickup, recompensa 1.
- Deliveries deben cargarse en depot: cada camion puede hacer varios viajes depot->clientes->depot.
  Para TODO delivery dentro de un viaje, el ultimo paso por depot antes de atenderlo es la salida
  de ese viaje. Por lo tanto, el viaje no puede salir del depot antes del ready_time de ningun
  delivery contenido en el viaje. Si hay varios deliveries en el mismo viaje, el viaje sale despues
  del maximo ready_time de esos deliveries. Pickups no fuerzan una recarga en depot.
- Pickups no tienen deadline propia: por defecto se pueden atender hasta fin de jornada. Por defecto
  se respeta su ready_time/arrival como release time; esto se puede cambiar con pickup_ready_policy.

Uso tipico:

    from deterministic_bound import VRPTWConfig, solve_vrptw_hexaly

    cfg = VRPTWConfig(
        nb_vehicles=3,
        max_trips_per_vehicle=100,
        depot_xy=(10000, 10000),
        shift_start_sec=9*3600,
        shift_end_sec=17*3600,
        vehicle_speed_m_per_s=25000/3600,
        time_limit_sec=60,
    )

    sol = solve_vrptw_hexaly(escenario, cfg)
    print(sol.summary_as_dict())
    print(sol.routes_as_dataframe())

Nota: requiere Hexaly instalado y PYTHONPATH apuntando al Python API de Hexaly.
"""

from __future__ import annotations

import argparse
import math
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

Number = Union[int, float, np.integer, np.floating]
Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Dataclasses de entrada/salida
# ---------------------------------------------------------------------------


@dataclass
class VRPTWConfig:
    """Parametros del modelo RICAS.

    nb_vehicles:
        Numero de camiones fisicos.

    max_trips_per_vehicle:
        Numero maximo de viajes depot->clientes->depot que puede hacer cada camion.
        Es una cota de modelamiento. Si queda muy baja, puedes cortar soluciones buenas.

    delivery_must_be_loaded_at_depot:
        Si True, todo delivery en un viaje exige que la salida de ese viaje desde depot sea
        posterior al ready_time del delivery. Es decir, para un delivery j servido en el viaje
        r, se impone departure_time_r >= ready_time_j. Como cada viaje parte desde depot,
        esto garantiza que el camion paso por depot despues de que el paquete estuviera listo
        y lo pudo cargar antes de visitar al cliente. Pickups no imponen esta restriccion.

    pickup_ready_policy:
        "arrival": un pickup no se puede servir antes de su ready_time/arrival.
        "shift_start": los pickups quedan disponibles desde las 09:00.
        Para una simulacion online, normalmente conviene "arrival" si el escenario incluye pedidos
        futuros; si el escenario contiene solo pedidos revelados, puede usarse "shift_start".

    deadline_is_latest_start:
        True interpreta deadline como ultimo inicio de servicio. Entonces la restriccion interna
        usa service_end <= deadline + service_time. Esto calza con la frase "puede ser atendida
        hasta deadline_time" si atender = iniciar servicio.
    """

    nb_vehicles: int = 3
    max_trips_per_vehicle: int = 10
    depot_xy: Point = (0.0, 0.0)
    shift_start_sec: float = 9 * 3600
    shift_end_sec: float = 17 * 3600
    vehicle_speed_m_per_s: float = 8.33
    service_time_default: float = 180.0
    distance_metric: str = "manhattan"  # "manhattan" o "euclidean"
    require_all_customers: bool = False
    hard_time_windows: bool = True
    deadline_is_latest_start: bool = True
    delivery_must_be_loaded_at_depot: bool = True
    pickup_ready_policy: str = "arrival"  # "arrival" o "shift_start"
    force_service_time_default: bool = True
    time_limit_sec: int = 60
    round_travel_time_to_int: bool = True
    seed: Optional[int] = None

    # Objetivos lexicograficos secundarios despues de maximizar utilidad.
    minimize_vehicles_after_profit: bool = True
    minimize_trips_after_profit: bool = True
    minimize_distance_after_profit: bool = True
    distance_cost_per_km_in_profit: float = 0.0

    def validate(self) -> None:
        if self.nb_vehicles <= 0:
            raise ValueError("nb_vehicles debe ser positivo.")
        if self.max_trips_per_vehicle <= 0:
            raise ValueError("max_trips_per_vehicle debe ser positivo.")
        if self.shift_end_sec <= self.shift_start_sec:
            raise ValueError("shift_end_sec debe ser mayor que shift_start_sec.")
        if self.vehicle_speed_m_per_s <= 0:
            raise ValueError("vehicle_speed_m_per_s debe ser positivo.")
        if self.time_limit_sec <= 0:
            raise ValueError("time_limit_sec debe ser positivo.")
        if self.distance_metric not in {"manhattan", "euclidean"}:
            raise ValueError("distance_metric debe ser 'manhattan' o 'euclidean'.")
        if self.pickup_ready_policy not in {"arrival", "shift_start"}:
            raise ValueError("pickup_ready_policy debe ser 'arrival' o 'shift_start'.")


@dataclass
class VRPTWScenario:
    """Escenario normalizado que recibe el optimizador.

    Internamente los clientes usan indices 0..n-1. ids conserva el id original.
    """

    x: List[float]
    y: List[float]
    ready_times: List[float]
    deadlines: List[float]
    service_times: List[float]
    profits: List[float]
    indicador: List[Any] = field(default_factory=list)
    arrivals: List[float] = field(default_factory=list)
    ids: List[Any] = field(default_factory=list)
    name: str = "scenario"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = len(self.x)
        fields = {
            "y": self.y,
            "ready_times": self.ready_times,
            "deadlines": self.deadlines,
            "service_times": self.service_times,
            "profits": self.profits,
        }
        for field_name, values in fields.items():
            if len(values) != n:
                raise ValueError(
                    f"Largo inconsistente: x tiene {n}, pero {field_name} tiene {len(values)}."
                )
        if not self.indicador:
            self.indicador = [None] * n
        if not self.arrivals:
            self.arrivals = list(self.ready_times)
        if not self.ids:
            self.ids = list(range(n))
        if len(self.indicador) != n or len(self.arrivals) != n or len(self.ids) != n:
            raise ValueError("indicador, arrivals e ids deben tener el mismo largo que x.")
        self._cast_numeric_lists()

    @property
    def n_customers(self) -> int:
        return len(self.x)

    def _cast_numeric_lists(self) -> None:
        for attr in ["x", "y", "ready_times", "deadlines", "service_times", "profits", "arrivals"]:
            setattr(self, attr, [float(v) for v in getattr(self, attr)])


@dataclass
class RouteStop:
    vehicle: int
    trip: int
    position: int
    customer_index: int
    customer_id: Any
    order_type: str
    indicador: Any
    x: float
    y: float
    arrival_time: float
    service_start: float
    service_end: float
    ready_time_effective: float
    ready_time_original: float
    deadline_original: float
    latest_end_effective: float
    profit: float
    travel_time_from_previous: float
    distance_km_from_previous: float
    loaded_at_depot_time: Optional[float] = None
    delivery_load_ready_slack_sec: Optional[float] = None


@dataclass
class RouteResult:
    vehicle: int
    trip: int
    stops: List[RouteStop]
    total_profit: float
    total_distance_km: float
    total_travel_time_sec: float
    available_time_at_depot: float
    departure_time_from_depot: float
    route_end_time_at_last_customer: float
    return_to_depot_time: float
    feasible_time_windows: bool
    max_delivery_ready_loaded: float
    delivery_load_feasible: bool = True
    n_delivery_load_violations: int = 0

    @property
    def customer_ids(self) -> List[Any]:
        return [stop.customer_id for stop in self.stops]

    @property
    def customer_indices(self) -> List[int]:
        return [stop.customer_index for stop in self.stops]


@dataclass
class VRPTWSolution:
    routes: List[RouteResult]
    served_indices: List[int]
    unserved_indices: List[int]
    served_ids: List[Any]
    unserved_ids: List[Any]
    total_profit: float
    total_possible_profit: float
    total_distance_km: float
    total_travel_time_sec: float
    nb_vehicles_used: int
    nb_trips_used: int
    objective_summary: Dict[str, Any]
    solver_status: Optional[str] = None

    @property
    def service_rate(self) -> float:
        total = len(self.served_indices) + len(self.unserved_indices)
        return 0.0 if total == 0 else len(self.served_indices) / total

    @property
    def profit_rate(self) -> float:
        return 0.0 if self.total_possible_profit == 0 else self.total_profit / self.total_possible_profit

    def routes_as_dataframe(self) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for route in self.routes:
            for stop in route.stops:
                rows.append(
                    {
                        "vehicle": stop.vehicle,
                        "trip": stop.trip,
                        "position": stop.position,
                        "customer_index": stop.customer_index,
                        "customer_id": stop.customer_id,
                        "order_type": stop.order_type,
                        "indicador": stop.indicador,
                        "x": stop.x,
                        "y": stop.y,
                        "arrival_time": stop.arrival_time,
                        "service_start": stop.service_start,
                        "service_end": stop.service_end,
                        "ready_time_effective": stop.ready_time_effective,
                        "ready_time_original": stop.ready_time_original,
                        "deadline_original": stop.deadline_original,
                        "latest_end_effective": stop.latest_end_effective,
                        "profit": stop.profit,
                        "travel_time_from_previous": stop.travel_time_from_previous,
                        "distance_km_from_previous": stop.distance_km_from_previous,
                        "loaded_at_depot_time": stop.loaded_at_depot_time,
                        "delivery_load_ready_slack_sec": stop.delivery_load_ready_slack_sec,
                    }
                )
        return pd.DataFrame(rows)

    def trips_as_dataframe(self) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for route in self.routes:
            rows.append(
                {
                    "vehicle": route.vehicle,
                    "trip": route.trip,
                    "n_stops": len(route.stops),
                    "customer_ids": route.customer_ids,
                    "total_profit": route.total_profit,
                    "total_distance_km": route.total_distance_km,
                    "total_travel_time_sec": route.total_travel_time_sec,
                    "available_time_at_depot": route.available_time_at_depot,
                    "departure_time_from_depot": route.departure_time_from_depot,
                    "route_end_time_at_last_customer": route.route_end_time_at_last_customer,
                    "return_to_depot_time": route.return_to_depot_time,
                    "tour_duration_sec": route.return_to_depot_time - route.departure_time_from_depot,
                    "tour_duration_min": (route.return_to_depot_time - route.departure_time_from_depot) / 60.0,
                    "tour_duration_hours": (route.return_to_depot_time - route.departure_time_from_depot) / 3600.0,
                    "feasible_time_windows": route.feasible_time_windows,
                    "max_delivery_ready_loaded": route.max_delivery_ready_loaded,
                    "delivery_load_feasible": route.delivery_load_feasible,
                    "n_delivery_load_violations": route.n_delivery_load_violations,
                }
            )
        return pd.DataFrame(rows)

    def summary_as_dict(self) -> Dict[str, Any]:
        # Métricas agregadas por tour/viaje.
        # Un tour corresponde a un RouteResult no vacío: depot -> clientes -> depot.
        # route_duration_sec incluye esperas, servicio y traslado desde salida del depot
        # hasta retorno al depot. total_travel_time_sec considera solo tiempo de viaje.
        nb_tours = len(self.routes)
        customers_per_tour = [len(route.stops) for route in self.routes]
        tour_durations_sec = [
            route.return_to_depot_time - route.departure_time_from_depot
            for route in self.routes
        ]

        avg_customers_per_tour = (
            float(np.mean(customers_per_tour)) if customers_per_tour else 0.0
        )
        avg_tour_duration_sec = (
            float(np.mean(tour_durations_sec)) if tour_durations_sec else 0.0
        )

        # Desviacion estandar muestral y error estandar.
        # Estos campos permiten construir intervalos de confianza por replica
        # sobre la distribucion de tours de esa replica.
        std_customers_per_tour = (
            float(np.std(customers_per_tour, ddof=1)) if len(customers_per_tour) >= 2 else 0.0
        )
        se_customers_per_tour = (
            std_customers_per_tour / math.sqrt(len(customers_per_tour))
            if customers_per_tour else 0.0
        )
        std_tour_duration_sec = (
            float(np.std(tour_durations_sec, ddof=1)) if len(tour_durations_sec) >= 2 else 0.0
        )
        se_tour_duration_sec = (
            std_tour_duration_sec / math.sqrt(len(tour_durations_sec))
            if tour_durations_sec else 0.0
        )

        return {
            "nb_vehicles_used": self.nb_vehicles_used,
            "nb_trips_used": self.nb_trips_used,
            "served_customers": len(self.served_indices),
            "unserved_customers": len(self.unserved_indices),
            "service_rate": self.service_rate,
            "total_profit": self.total_profit,
            "total_possible_profit": self.total_possible_profit,
            "profit_rate": self.profit_rate,
            "total_distance_km": self.total_distance_km,
            "total_travel_time_sec": self.total_travel_time_sec,
            "nb_tours": nb_tours,
            "avg_customers_per_tour": avg_customers_per_tour,
            "std_customers_per_tour": std_customers_per_tour,
            "se_customers_per_tour": se_customers_per_tour,
            "avg_tour_duration_sec": avg_tour_duration_sec,
            "std_tour_duration_sec": std_tour_duration_sec,
            "se_tour_duration_sec": se_tour_duration_sec,
            "avg_tour_duration_min": avg_tour_duration_sec / 60.0,
            "std_tour_duration_min": std_tour_duration_sec / 60.0,
            "se_tour_duration_min": se_tour_duration_sec / 60.0,
            "avg_tour_duration_hours": avg_tour_duration_sec / 3600.0,
            "std_tour_duration_hours": std_tour_duration_sec / 3600.0,
            "se_tour_duration_hours": se_tour_duration_sec / 3600.0,
            "solver_status": self.solver_status,
            **self.objective_summary,
        }
    
    def camion_positions_as_dataframe(self, include_depot: bool = False) -> pd.DataFrame:
        rows = []

        depot_xy = self.objective_summary.get("depot_xy", None)

        for route in self.routes:
            camion_id = route.vehicle

            if include_depot and depot_xy is not None:
                rows.append({
                    "camion": camion_id,
                    "timestamps": route.departure_time_from_depot,
                    "camion_pos": str(tuple(depot_xy)),
                })

            for stop in route.stops:
                rows.append({
                    "camion": camion_id,
                    "timestamps": stop.service_start,
                    "camion_pos": str((stop.x, stop.y)),
                })

            if include_depot and depot_xy is not None:
                rows.append({
                    "camion": camion_id,
                    "timestamps": route.return_to_depot_time,
                    "camion_pos": str(tuple(depot_xy)),
                })

        df = pd.DataFrame(rows)

        if not df.empty:
            df = df.sort_values(["camion", "timestamps"]).reset_index(drop=True)

        return df

    def save_camion_positions_csv(
        self,
        filepath: str,
        include_depot: bool = False,
    ) -> None:
        df = self.camion_positions_as_dataframe(include_depot=include_depot)
        df.to_csv(filepath, index=False)


# ---------------------------------------------------------------------------
# Carga y normalizacion de datos
# ---------------------------------------------------------------------------


def load_scenario_from_pickle(
    pkl_path: Union[str, Path],
    replica_id: Optional[int] = 0,
    *,
    scenario_name: Optional[str] = None,
    config: Optional[VRPTWConfig] = None,
) -> VRPTWScenario:
    pkl_path = Path(pkl_path)
    with pkl_path.open("rb") as f:
        obj = pickle.load(f)
    return scenario_from_any(
        obj,
        replica_id=replica_id,
        scenario_name=scenario_name or pkl_path.stem,
        config=config,
    )


def scenario_from_any(
    data: Any,
    replica_id: Optional[int] = 0,
    *,
    scenario_name: str = "scenario",
    config: Optional[VRPTWConfig] = None,
) -> VRPTWScenario:
    if isinstance(data, VRPTWScenario):
        return data

    if isinstance(data, pd.DataFrame):
        return scenario_from_dataframe(data, replica_id=replica_id, scenario_name=scenario_name, config=config)

    if isinstance(data, dict):
        for key in ("df", "data", "scenario", "escenario", "replica"):
            if key in data and isinstance(data[key], pd.DataFrame):
                return scenario_from_dataframe(data[key], replica_id=replica_id, scenario_name=scenario_name, config=config)
        return scenario_from_mapping(data, replica_id=replica_id, scenario_name=scenario_name, config=config)

    required_attrs = ["arrivals", "deadlines", "profits", "ready_times", "service_times"]
    if all(hasattr(data, attr) for attr in required_attrs):
        return scenario_from_instance_data_like(
            data,
            replica_id=replica_id,
            scenario_name=getattr(data, "name", scenario_name),
            config=config,
        )

    raise TypeError(
        "No pude convertir el objeto a VRPTWScenario. Esperaba DataFrame, dict, "
        "VRPTWScenario u objeto tipo InstanceData."
    )


def scenario_from_dataframe(
    df: pd.DataFrame,
    replica_id: Optional[int] = 0,
    *,
    scenario_name: str = "scenario",
    config: Optional[VRPTWConfig] = None,
) -> VRPTWScenario:
    config = config or VRPTWConfig()
    local = df.copy()

    if "replica" in local.columns:
        if replica_id is None:
            replica_id = int(local["replica"].iloc[0])
        local = local.loc[local["replica"] == replica_id].copy()
        if local.empty:
            raise ValueError(f"No hay filas para replica_id={replica_id}.")

    if "x" in local.columns and "y" in local.columns:
        x = local["x"].tolist()
        y = local["y"].tolist()
    elif "points" in local.columns:
        x, y = _split_points(local["points"].tolist())
    else:
        raise KeyError("El DataFrame debe tener columnas x/y o points.")

    ready = _get_column_or_default(local, "ready_times", None)
    if ready is None:
        ready = _get_column_or_default(local, "arrivals", None)
    if ready is None:
        raise KeyError("Falta ready_times o arrivals en el DataFrame.")

    deadlines = _get_column_or_default(local, "deadlines", None)
    if deadlines is None:
        deadlines = [config.shift_end_sec] * len(local)

    service_times = _get_column_or_default(local, "service_times", None)
    if service_times is None or config.force_service_time_default:
        service_times = [config.service_time_default] * len(local)

    indicador = _get_column_or_default(local, "indicador", [None] * len(local))
    arrivals = _get_column_or_default(local, "arrivals", ready)
    profits = _get_column_or_default(local, "profits", None)
    if profits is None:
        profits = _profits_from_indicador(indicador)

    ids = _get_column_or_default(local, "id", None)
    if ids is None:
        ids = _get_column_or_default(local, "customer_id", None)
    if ids is None:
        ids = local.index.tolist()

    return VRPTWScenario(
        x=list(x),
        y=list(y),
        ready_times=list(ready),
        deadlines=list(deadlines),
        service_times=list(service_times),
        profits=list(profits),
        indicador=list(indicador),
        arrivals=list(arrivals),
        ids=list(ids),
        name=scenario_name,
        metadata={"replica_id": replica_id},
    )


def scenario_from_mapping(
    data: Dict[str, Any],
    replica_id: Optional[int] = 0,
    *,
    scenario_name: str = "scenario",
    config: Optional[VRPTWConfig] = None,
) -> VRPTWScenario:
    config = config or VRPTWConfig()

    x = _select_replica(_first_present(data, ["x", "xs", "customer_x"]), replica_id, field="x")
    y = _select_replica(_first_present(data, ["y", "ys", "customer_y"]), replica_id, field="y")
    points = _select_replica(_first_present(data, ["points", "coordinates", "coords"]), replica_id, field="points")

    if (x is None or y is None) and points is not None:
        x, y = _split_points(points)
    if x is None or y is None:
        raise KeyError("El dict debe traer x/y o points.")

    ready = _select_replica(_first_present(data, ["ready_times", "ready", "earliest"]), replica_id, field="ready_times")
    arrivals = _select_replica(_first_present(data, ["arrivals", "arrival_times"]), replica_id, field="arrivals")
    if ready is None:
        ready = arrivals
    if ready is None:
        raise KeyError("El dict debe traer ready_times o arrivals.")

    deadlines = _select_replica(
        _first_present(data, ["deadlines", "deadline", "latest", "due_dates"]),
        replica_id,
        field="deadlines",
    )
    if deadlines is None:
        deadlines = [config.shift_end_sec] * len(x)

    service_times = _select_replica(
        _first_present(data, ["service_times", "service", "service_time"]),
        replica_id,
        field="service_times",
    )
    if service_times is None or config.force_service_time_default:
        service_times = [config.service_time_default] * len(x)

    indicador = _select_replica(_first_present(data, ["indicador", "is_pickup", "pickup"]), replica_id, field="indicador")
    if indicador is None:
        indicador = [None] * len(x)

    profits = _select_replica(
        _first_present(data, ["profits", "profit", "prizes", "rewards"]),
        replica_id,
        field="profits",
    )
    if profits is None:
        profits = _profits_from_indicador(indicador)

    ids = _select_replica(_first_present(data, ["ids", "id", "customer_ids"]), replica_id, field="ids")
    if ids is None:
        ids = list(range(len(x)))

    if arrivals is None:
        arrivals = list(ready)

    return VRPTWScenario(
        x=list(x),
        y=list(y),
        ready_times=list(ready),
        deadlines=list(deadlines),
        service_times=list(service_times),
        profits=list(profits),
        indicador=list(indicador),
        arrivals=list(arrivals),
        ids=list(ids),
        name=scenario_name,
        metadata={"replica_id": replica_id},
    )


def scenario_from_instance_data_like(
    instance: Any,
    replica_id: Optional[int] = 0,
    *,
    scenario_name: str = "scenario",
    config: Optional[VRPTWConfig] = None,
) -> VRPTWScenario:
    config = config or VRPTWConfig()

    points = _select_replica(getattr(instance, "points", None), replica_id, field="points")
    if points is None or len(points) == 0:
        x = _select_replica(getattr(instance, "x", None), replica_id, field="x")
        y = _select_replica(getattr(instance, "y", None), replica_id, field="y")
        if x is None or y is None:
            raise KeyError("InstanceData no trae points ni x/y.")
    else:
        x, y = _split_points(points)

    arrivals = _select_replica(getattr(instance, "arrivals", None), replica_id, field="arrivals")
    ready = _select_replica(getattr(instance, "ready_times", None), replica_id, field="ready_times")
    if ready is None:
        ready = arrivals
    if ready is None:
        raise KeyError("InstanceData debe traer ready_times o arrivals.")

    deadlines = _select_replica(getattr(instance, "deadlines", None), replica_id, field="deadlines")
    if deadlines is None:
        deadlines = [config.shift_end_sec] * len(x)

    indicador = _select_replica(getattr(instance, "indicador", None), replica_id, field="indicador")
    if indicador is None:
        indicador = [None] * len(x)

    profits = _select_replica(getattr(instance, "profits", None), replica_id, field="profits")
    if profits is None:
        profits = _profits_from_indicador(indicador)

    service_times = _select_replica(getattr(instance, "service_times", None), replica_id, field="service_times")
    if service_times is None or config.force_service_time_default:
        service_times = [config.service_time_default] * len(x)

    if arrivals is None:
        arrivals = list(ready)

    return VRPTWScenario(
        x=list(x),
        y=list(y),
        ready_times=list(ready),
        deadlines=list(deadlines),
        service_times=list(service_times),
        profits=list(profits),
        indicador=list(indicador),
        arrivals=list(arrivals),
        ids=list(range(len(x))),
        name=scenario_name,
        metadata={"replica_id": replica_id, "source_file_path": getattr(instance, "file_path", None)},
    )


# ---------------------------------------------------------------------------
# Solver Hexaly
# ---------------------------------------------------------------------------


class RicasHexalyVRPTW:
    def __init__(self, config: Optional[VRPTWConfig] = None):
        self.config = config or VRPTWConfig()
        self.config.validate()

    def solve(self, scenario_input: Any, replica_id: Optional[int] = 0) -> VRPTWSolution:
        return solve_vrptw_hexaly(scenario_input, self.config, replica_id=replica_id)


def solve_vrptw_hexaly(
    scenario_input: Any,
    config: Optional[VRPTWConfig] = None,
    *,
    replica_id: Optional[int] = 0,
) -> VRPTWSolution:
    """Resuelve el escenario como PC-MultiTrip-VRPTW con Hexaly."""

    config = config or VRPTWConfig()
    config.validate()
    scenario = scenario_from_any(scenario_input, replica_id=replica_id, config=config)

    # Por si la carga se hace mal
    if scenario.n_customers == 0:
        return VRPTWSolution(
            routes=[],
            served_indices=[],
            unserved_indices=[],
            served_ids=[],
            unserved_ids=[],
            total_profit=0.0,
            total_possible_profit=0.0,
            total_distance_km=0.0,
            total_travel_time_sec=0.0,
            nb_vehicles_used=0,
            nb_trips_used=0,
            objective_summary={},
            solver_status="EMPTY_SCENARIO",
        )

    try:
        import hexaly.optimizer
    except ImportError as exc:
        raise ImportError(
            "No pude importar hexaly.optimizer. Revisa que Hexaly este instalado"
        ) from exc

    n = scenario.n_customers
    nb_vehicles = config.nb_vehicles
    max_trips = config.max_trips_per_vehicle
    nb_trip_slots = nb_vehicles * max_trips

    is_delivery = [_is_delivery_flag(v) for v in scenario.indicador]
    is_pickup = [1 - v for v in is_delivery]
    order_types = ["delivery" if d else "pickup" for d in is_delivery]
    effective_ready, latest_end = _compute_effective_time_windows(scenario, config, is_delivery)

    distance_matrix_km, distance_depot_km, travel_time_matrix, travel_time_depot = _build_matrices(
        scenario,
        config,
    )

    with hexaly.optimizer.HexalyOptimizer() as optimizer:  # type: ignore[attr-defined]
        model = optimizer.model

        trip_routes = [model.list(n) for _ in range(nb_trip_slots)]

        if config.require_all_customers:
            model.constraint(model.partition(trip_routes))
        else:
            model.constraint(model.disjoint(trip_routes))

        profits = model.array(scenario.profits)
        ready = model.array(effective_ready)
        original_ready = model.array(scenario.ready_times)
        latest = model.array(latest_end)
        service = model.array(scenario.service_times)
        delivery = model.array(is_delivery)
        pickup = model.array(is_pickup)
        dist_matrix = model.array(distance_matrix_km)
        dist_depot = model.array(distance_depot_km)
        time_matrix = model.array(travel_time_matrix)
        time_depot = model.array(travel_time_depot)

        trip_used_exprs = []
        vehicle_used_exprs = []
        distance_exprs = []
        travel_time_exprs = []
        lateness_exprs = []
        route_profit_exprs = []
        return_time_exprs_by_vehicle: List[List[Any]] = []

        profit_lambda = model.lambda_function(lambda j: profits[j])

        for k in range(nb_vehicles):
            vehicle_trip_used = []
            return_time_exprs_for_vehicle: List[Any] = []

            for t in range(max_trips):
                slot = k * max_trips + t
                seq = trip_routes[slot]
                c = model.count(seq)
                used = c > 0
                trip_used_exprs.append(used)
                vehicle_trip_used.append(used)

                available_at_depot = (
                    float(config.shift_start_sec)
                    if t == 0
                    else return_time_exprs_for_vehicle[t - 1]
                )

                # Si hay deliveries en el viaje, el camion sale del depot no antes del max ready_time
                # de esos deliveries; asi se modela que los paquetes se cargan en depot al iniciar viaje.
                if config.delivery_must_be_loaded_at_depot:
                    # Regla operacional estricta para deliveries:
                    # Si un delivery j esta en este viaje, el camion debe salir del depot
                    # en este viaje despues de ready[j]. Como el viaje empieza en depot,
                    # esta salida es el ultimo paso por depot antes de visitar a j.
                    #
                    # En forma compacta:
                    #     departure_time >= ready[j]   para todo delivery j en seq
                    #
                    # Por eso el viaje sale no antes del max ready_time de todos los
                    # deliveries incluidos. Los pickups tienen coeficiente 0 y no fuerzan
                    # recarga ni espera en depot.
                    delivery_ready_lambda = model.lambda_function(lambda j: delivery[j] * ready[j])
                    max_delivery_ready = model.max(seq, delivery_ready_lambda)
                    departure_time = model.iif(
                        used,
                        model.max(available_at_depot, max_delivery_ready),
                        available_at_depot,
                    )

                    # Restriccion explicita de carga: evita que el modelo pueda servir un
                    # delivery cuya orden no fue cargada en depot en la salida de este viaje.
                    # Es redundante con departure_time=max(...), pero deja la factibilidad
                    # totalmente expresada y permite penalizarla si las TW fueran suaves.
                    delivery_load_late_lambda = model.lambda_function(
                        lambda i: delivery[seq[i]] * model.max(0, ready[seq[i]] - departure_time)
                    )
                    route_delivery_load_lateness = model.sum(
                        model.range(0, c),
                        delivery_load_late_lambda,
                    )
                else:
                    max_delivery_ready = 0
                    departure_time = model.iif(used, available_at_depot, available_at_depot)
                    route_delivery_load_lateness = 0

                route_profit = model.sum(seq, profit_lambda)
                route_profit_exprs.append(route_profit)

                route_dist_lambda = model.lambda_function(
                    lambda i: model.at(dist_matrix, seq[i - 1], seq[i])
                )
                route_distance = model.sum(model.range(1, c), route_dist_lambda) + model.iif(
                    used,
                    dist_depot[seq[0]] + dist_depot[seq[c - 1]],
                    0,
                )
                distance_exprs.append(route_distance)

                route_travel_time_lambda = model.lambda_function(
                    lambda i: model.at(time_matrix, seq[i - 1], seq[i])
                )
                route_travel_time = model.sum(model.range(1, c), route_travel_time_lambda) + model.iif(
                    used,
                    time_depot[seq[0]] + time_depot[seq[c - 1]],
                    0,
                )
                travel_time_exprs.append(route_travel_time)

                end_time_lambda = model.lambda_function(
                    lambda i, prev: model.max(
                        ready[seq[i]],
                        model.iif(
                            i == 0,
                            departure_time + time_depot[seq[0]],
                            prev + model.at(time_matrix, seq[i - 1], seq[i]),
                        ),
                    )
                    + service[seq[i]]
                )
                end_time = model.array(model.range(0, c), end_time_lambda, 0)

                return_to_depot_time = model.iif(
                    used,
                    end_time[c - 1] + time_depot[seq[c - 1]],
                    available_at_depot,
                )
                return_time_exprs_for_vehicle.append(return_to_depot_time)

                home_lateness = model.iif(
                    used,
                    model.max(0, return_to_depot_time - float(config.shift_end_sec)),
                    0,
                )

                late_lambda = model.lambda_function(
                    lambda i: model.max(0, end_time[i] - latest[seq[i]])
                )
                route_lateness = (
                    home_lateness
                    + model.sum(model.range(0, c), late_lambda)
                    + route_delivery_load_lateness
                )
                lateness_exprs.append(route_lateness)

                # Restriccion extra de consistencia: si hay pickups y se quiere respetar arrival/ready,
                # el max(ready, arrival) ya queda en el end_time. original_ready queda disponible para debug.
                _ = original_ready
                _ = pickup

                if config.hard_time_windows:
                    model.constraint(route_lateness == 0)

            return_time_exprs_by_vehicle.append(return_time_exprs_for_vehicle)
            vehicle_used_exprs.append(model.sum(vehicle_trip_used) > 0)

        total_profit = model.sum(route_profit_exprs)
        total_lateness = model.sum(lateness_exprs)
        nb_vehicles_used = model.sum(vehicle_used_exprs)
        nb_trips_used = model.sum(trip_used_exprs)
        total_distance = model.div(model.round(1000 * model.sum(distance_exprs)), 1000)
        total_travel_time = model.sum(travel_time_exprs)

        if config.distance_cost_per_km_in_profit > 0:
            profit_objective = total_profit - config.distance_cost_per_km_in_profit * total_distance
        else:
            profit_objective = total_profit

        if config.require_all_customers:
            if not config.hard_time_windows:
                model.minimize(total_lateness)
            if config.minimize_vehicles_after_profit:
                model.minimize(nb_vehicles_used)
            if config.minimize_trips_after_profit:
                model.minimize(nb_trips_used)
            if config.minimize_distance_after_profit:
                model.minimize(total_distance)
        else:
            if not config.hard_time_windows:
                model.minimize(total_lateness)
            model.maximize(profit_objective)
            if config.minimize_vehicles_after_profit:
                model.minimize(nb_vehicles_used)
            if config.minimize_trips_after_profit:
                model.minimize(nb_trips_used)
            if config.minimize_distance_after_profit:
                model.minimize(total_distance)

        model.close()

        optimizer.param.time_limit = int(config.time_limit_sec)
        if config.seed is not None:
            for attr in ("seed", "random_seed"):
                try:
                    setattr(optimizer.param, attr, int(config.seed))
                    break
                except Exception:
                    pass

        optimizer.solve()

        selected_trip_routes: List[List[int]] = []
        for slot in range(nb_trip_slots):
            seq_value = list(trip_routes[slot].value)
            selected_trip_routes.append([int(i) for i in seq_value])

        solver_status = _safe_solver_status(optimizer)

    return _build_solution_from_trip_sequences(
        selected_trip_routes=selected_trip_routes,
        scenario=scenario,
        config=config,
        is_delivery=is_delivery,
        order_types=order_types,
        effective_ready=effective_ready,
        latest_end=latest_end,
        distance_matrix_km=distance_matrix_km,
        distance_depot_km=distance_depot_km,
        travel_time_matrix=travel_time_matrix,
        travel_time_depot=travel_time_depot,
        solver_status=solver_status,
    )


# ---------------------------------------------------------------------------
# Evaluacion post-solve en Python
# ---------------------------------------------------------------------------


def _build_solution_from_trip_sequences(
    *,
    selected_trip_routes: List[List[int]],
    scenario: VRPTWScenario,
    config: VRPTWConfig,
    is_delivery: List[int],
    order_types: List[str],
    effective_ready: List[float],
    latest_end: List[float],
    distance_matrix_km: List[List[float]],
    distance_depot_km: List[float],
    travel_time_matrix: List[List[float]],
    travel_time_depot: List[float],
    solver_status: Optional[str],
) -> VRPTWSolution:
    route_results: List[RouteResult] = []
    served: List[int] = []

    for vehicle in range(config.nb_vehicles):
        available_at_depot = float(config.shift_start_sec)
        for trip in range(config.max_trips_per_vehicle):
            slot = vehicle * config.max_trips_per_vehicle + trip
            seq = selected_trip_routes[slot]
            if not seq:
                continue
            route = _evaluate_trip_route(
                vehicle=vehicle,
                trip=trip,
                seq=seq,
                scenario=scenario,
                config=config,
                is_delivery=is_delivery,
                order_types=order_types,
                effective_ready=effective_ready,
                latest_end=latest_end,
                distance_matrix_km=distance_matrix_km,
                distance_depot_km=distance_depot_km,
                travel_time_matrix=travel_time_matrix,
                travel_time_depot=travel_time_depot,
                available_at_depot=available_at_depot,
            )
            route_results.append(route)
            served.extend(seq)
            available_at_depot = route.return_to_depot_time

    served_sorted = sorted(set(served))
    unserved = [i for i in range(scenario.n_customers) if i not in served_sorted]

    total_profit = sum(scenario.profits[i] for i in served_sorted)
    total_possible_profit = sum(scenario.profits)
    total_distance_km = sum(r.total_distance_km for r in route_results)
    total_travel_time_sec = sum(r.total_travel_time_sec for r in route_results)
    used_vehicles = sorted({r.vehicle for r in route_results})

    objective_summary = {
        "distance_metric": config.distance_metric,
        "depot_xy": config.depot_xy,
        "shift_start_sec": config.shift_start_sec,
        "shift_end_sec": config.shift_end_sec,
        "hard_time_windows": config.hard_time_windows,
        "require_all_customers": config.require_all_customers,
        "deadline_is_latest_start": config.deadline_is_latest_start,
        "delivery_must_be_loaded_at_depot": config.delivery_must_be_loaded_at_depot,
        "delivery_loading_rule": (
            "each delivery in a trip requires trip departure from depot >= its ready_time"
            if config.delivery_must_be_loaded_at_depot
            else "disabled"
        ),
        "pickup_ready_policy": config.pickup_ready_policy,
        "max_trips_per_vehicle": config.max_trips_per_vehicle,
        "distance_cost_per_km_in_profit": config.distance_cost_per_km_in_profit,
    }

    return VRPTWSolution(
        routes=route_results,
        served_indices=served_sorted,
        unserved_indices=unserved,
        served_ids=[scenario.ids[i] for i in served_sorted],
        unserved_ids=[scenario.ids[i] for i in unserved],
        total_profit=total_profit,
        total_possible_profit=total_possible_profit,
        total_distance_km=total_distance_km,
        total_travel_time_sec=total_travel_time_sec,
        nb_vehicles_used=len(used_vehicles),
        nb_trips_used=len(route_results),
        objective_summary=objective_summary,
        solver_status=solver_status,
    )


def _evaluate_trip_route(
    *,
    vehicle: int,
    trip: int,
    seq: List[int],
    scenario: VRPTWScenario,
    config: VRPTWConfig,
    is_delivery: List[int],
    order_types: List[str],
    effective_ready: List[float],
    latest_end: List[float],
    distance_matrix_km: List[List[float]],
    distance_depot_km: List[float],
    travel_time_matrix: List[List[float]],
    travel_time_depot: List[float],
    available_at_depot: float,
) -> RouteResult:
    stops: List[RouteStop] = []
    feasible_tw = True
    total_distance = 0.0
    total_travel_time = 0.0

    if config.delivery_must_be_loaded_at_depot:
        delivery_ready_times = [effective_ready[i] for i in seq if is_delivery[i]]
        max_delivery_ready = max(delivery_ready_times) if delivery_ready_times else 0.0
        departure_time = max(available_at_depot, max_delivery_ready)
    else:
        max_delivery_ready = 0.0
        departure_time = available_at_depot

    # Verificacion post-solve de la regla operacional:
    # todo delivery servido en este viaje debe tener ready_time <= departure_time_from_depot.
    # Para pickups no aplica.
    delivery_load_violations = [
        i for i in seq
        if is_delivery[i] and departure_time + 1e-9 < effective_ready[i]
    ]
    delivery_load_feasible = len(delivery_load_violations) == 0
    if not delivery_load_feasible:
        feasible_tw = False

    current_time = departure_time
    prev: Optional[int] = None

    for position, customer in enumerate(seq):
        if prev is None:
            travel_time = travel_time_depot[customer]
            distance_km = distance_depot_km[customer]
        else:
            travel_time = travel_time_matrix[prev][customer]
            distance_km = distance_matrix_km[prev][customer]

        arrival = current_time + travel_time
        service_start = max(arrival, effective_ready[customer])
        service_end = service_start + scenario.service_times[customer]

        if service_end > latest_end[customer] + 1e-9:
            feasible_tw = False

        stops.append(
            RouteStop(
                vehicle=vehicle,
                trip=trip,
                position=position,
                customer_index=customer,
                customer_id=scenario.ids[customer],
                order_type=order_types[customer],
                indicador=scenario.indicador[customer],
                x=scenario.x[customer],
                y=scenario.y[customer],
                arrival_time=arrival,
                service_start=service_start,
                service_end=service_end,
                ready_time_effective=effective_ready[customer],
                ready_time_original=scenario.ready_times[customer],
                deadline_original=scenario.deadlines[customer],
                latest_end_effective=latest_end[customer],
                profit=scenario.profits[customer],
                travel_time_from_previous=travel_time,
                distance_km_from_previous=distance_km,
                loaded_at_depot_time=departure_time if is_delivery[customer] else None,
                delivery_load_ready_slack_sec=(
                    departure_time - effective_ready[customer] if is_delivery[customer] else None
                ),
            )
        )

        total_distance += distance_km
        total_travel_time += travel_time
        current_time = service_end
        prev = customer

    if prev is None:
        return RouteResult(
            vehicle=vehicle,
            trip=trip,
            stops=[],
            total_profit=0.0,
            total_distance_km=0.0,
            total_travel_time_sec=0.0,
            available_time_at_depot=available_at_depot,
            departure_time_from_depot=available_at_depot,
            route_end_time_at_last_customer=available_at_depot,
            return_to_depot_time=available_at_depot,
            feasible_time_windows=True,
            max_delivery_ready_loaded=0.0,
            delivery_load_feasible=True,
            n_delivery_load_violations=0,
        )

    total_distance += distance_depot_km[prev]
    total_travel_time += travel_time_depot[prev]
    return_to_depot = current_time + travel_time_depot[prev]
    if return_to_depot > config.shift_end_sec + 1e-9:
        feasible_tw = False

    return RouteResult(
        vehicle=vehicle,
        trip=trip,
        stops=stops,
        total_profit=sum(scenario.profits[i] for i in seq),
        total_distance_km=total_distance,
        total_travel_time_sec=total_travel_time,
        available_time_at_depot=available_at_depot,
        departure_time_from_depot=departure_time,
        route_end_time_at_last_customer=current_time,
        return_to_depot_time=return_to_depot,
        feasible_time_windows=feasible_tw,
        max_delivery_ready_loaded=max_delivery_ready,
        delivery_load_feasible=delivery_load_feasible,
        n_delivery_load_violations=len(delivery_load_violations),
    )


# ---------------------------------------------------------------------------
# Helpers de tiempos, matrices y tipos de pedido
# ---------------------------------------------------------------------------


def _compute_effective_time_windows(
    scenario: VRPTWScenario,
    config: VRPTWConfig,
    is_delivery: List[int],
) -> Tuple[List[float], List[float]]:
    effective_ready: List[float] = []
    latest_end: List[float] = []

    for i in range(scenario.n_customers):
        if is_delivery[i]:
            ready_i = scenario.ready_times[i]
            latest_i = (
                scenario.deadlines[i] + scenario.service_times[i]
                if config.deadline_is_latest_start
                else scenario.deadlines[i]
            )
        else:
            if config.pickup_ready_policy == "shift_start":
                ready_i = config.shift_start_sec
            else:
                ready_i = max(config.shift_start_sec, scenario.ready_times[i])
            latest_i = config.shift_end_sec
        effective_ready.append(float(max(config.shift_start_sec, ready_i)))
        latest_end.append(float(min(config.shift_end_sec, latest_i)))

    return effective_ready, latest_end


def _build_matrices(
    scenario: VRPTWScenario,
    config: VRPTWConfig,
) -> Tuple[List[List[float]], List[float], List[List[float]], List[float]]:
    n = scenario.n_customers
    dist_km = [[0.0 for _ in range(n)] for _ in range(n)]
    travel_s = [[0.0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            d_m = _distance_m(
                scenario.x[i],
                scenario.y[i],
                scenario.x[j],
                scenario.y[j],
                config.distance_metric,
            )
            d_km = d_m / 1000.0
            t_s = d_m / config.vehicle_speed_m_per_s
            if config.round_travel_time_to_int:
                t_s = float(math.ceil(t_s))
            dist_km[i][j] = dist_km[j][i] = d_km
            travel_s[i][j] = travel_s[j][i] = t_s

    depot_x, depot_y = config.depot_xy
    dist_depot_km: List[float] = []
    travel_depot_s: List[float] = []
    for i in range(n):
        d_m = _distance_m(depot_x, depot_y, scenario.x[i], scenario.y[i], config.distance_metric)
        d_km = d_m / 1000.0
        t_s = d_m / config.vehicle_speed_m_per_s
        if config.round_travel_time_to_int:
            t_s = float(math.ceil(t_s))
        dist_depot_km.append(d_km)
        travel_depot_s.append(t_s)

    return dist_km, dist_depot_km, travel_s, travel_depot_s


def _distance_m(x1: float, y1: float, x2: float, y2: float, metric: str) -> float:
    if metric == "manhattan":
        return abs(x1 - x2) + abs(y1 - y2)
    if metric == "euclidean":
        return math.hypot(x1 - x2, y1 - y2)
    raise ValueError(f"Metrica no soportada: {metric}")


def _is_delivery_flag(value: Any) -> int:
    """indicador False/'False' -> delivery; True/'True' -> pickup."""
    if isinstance(value, bool):
        return 1 if value is False else 0
    s = str(value).strip().lower()
    if s == "false":
        return 1
    if s == "true":
        return 0
    return 0


def _profits_from_indicador(indicador: Sequence[Any]) -> List[float]:
    profits: List[float] = []
    for value in indicador:
        profits.append(2.0 if _is_delivery_flag(value) else 1.0)
    return profits


def _split_points(points: Sequence[Any]) -> Tuple[List[float], List[float]]:
    x: List[float] = []
    y: List[float] = []
    for p in points:
        if isinstance(p, dict):
            x.append(float(p["x"]))
            y.append(float(p["y"]))
        else:
            if len(p) < 2:  # type: ignore[arg-type]
                raise ValueError(f"Punto invalido: {p}")
            x.append(float(p[0]))  # type: ignore[index]
            y.append(float(p[1]))  # type: ignore[index]
    return x, y


def _get_column_or_default(df: pd.DataFrame, col: str, default: Any) -> Any:
    if col in df.columns:
        return df[col].tolist()
    return default


def _first_present(mapping: Dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _select_replica(values: Any, replica_id: Optional[int], *, field: str) -> Any:
    if values is None:
        return None

    if isinstance(values, pd.Series):
        values = values.tolist()
    elif isinstance(values, np.ndarray):
        values = values.tolist()

    if not isinstance(values, (list, tuple)) or len(values) == 0:
        return values

    if _looks_like_replicas(values, field=field):
        rid = 0 if replica_id is None else int(replica_id)
        if rid < 0 or rid >= len(values):
            raise IndexError(f"replica_id={rid} fuera de rango para campo {field} con {len(values)} replicas.")
        return values[rid]

    return values


def _looks_like_replicas(values: Sequence[Any], *, field: str) -> bool:
    first = values[0]
    if first is None or isinstance(first, (str, bytes)):
        return False
    if isinstance(first, np.ndarray):
        first = first.tolist()
    if not isinstance(first, (list, tuple)):
        return False
    if field == "points" and len(first) >= 2 and _is_number(first[0]) and _is_number(first[1]):
        return False
    return True


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating))


def _safe_solver_status(optimizer: Any) -> Optional[str]:
    for attr in ("status", "solution_status"):
        try:
            return str(getattr(optimizer, attr))
        except Exception:
            continue
    try:
        return str(optimizer)
    except Exception:
        return None


def sec_to_hhmmss(seconds: float) -> str:
    seconds_i = int(round(seconds))
    h = seconds_i // 3600
    m = (seconds_i % 3600) // 60
    s = seconds_i % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# CLI basico
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolver PC-MultiTrip-VRPTW RICAS con Hexaly.")
    parser.add_argument("--pkl", type=str, required=True, help="Ruta al archivo .pkl")
    parser.add_argument("--replica", type=int, default=0, help="Replica a resolver si el pkl trae varias")
    parser.add_argument("--vehicles", type=int, default=3, help="Numero de camiones fisicos")
    parser.add_argument("--max-trips", type=int, default=10, help="Maximo de viajes por camion")
    parser.add_argument("--time-limit", type=int, default=60, help="Tiempo limite de Hexaly en segundos")
    parser.add_argument("--speed", type=float, default=8.33, help="Velocidad en m/s")
    parser.add_argument("--depot-x", type=float, default=0.0)
    parser.add_argument("--depot-y", type=float, default=0.0)
    parser.add_argument("--shift-start", type=float, default=9 * 3600)
    parser.add_argument("--shift-end", type=float, default=17 * 3600)
    parser.add_argument("--metric", choices=["manhattan", "euclidean"], default="manhattan")
    parser.add_argument("--require-all", action="store_true", help="Forzar atender todos los clientes")
    parser.add_argument("--soft-tw", action="store_true", help="Usar ventanas suaves minimizando tardanza")
    parser.add_argument(
        "--pickup-ready-policy",
        choices=["arrival", "shift_start"],
        default="arrival",
        help="Politica de disponibilidad para pickups",
    )
    parser.add_argument("--out-csv", type=str, default=None, help="Archivo CSV para guardar paradas")
    parser.add_argument("--out-trips-csv", type=str, default=None, help="Archivo CSV para guardar resumen de viajes")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = VRPTWConfig(
        nb_vehicles=args.vehicles,
        max_trips_per_vehicle=args.max_trips,
        depot_xy=(args.depot_x, args.depot_y),
        shift_start_sec=args.shift_start,
        shift_end_sec=args.shift_end,
        vehicle_speed_m_per_s=args.speed,
        distance_metric=args.metric,
        time_limit_sec=args.time_limit,
        require_all_customers=args.require_all,
        hard_time_windows=not args.soft_tw,
        pickup_ready_policy=args.pickup_ready_policy,
    )
    scenario = load_scenario_from_pickle(args.pkl, replica_id=args.replica, config=cfg)
    sol = solve_vrptw_hexaly(scenario, cfg)
    print(sol.summary_as_dict())
    if args.out_csv:
        sol.routes_as_dataframe().to_csv(args.out_csv, index=False)
        print(f"Paradas guardadas en {args.out_csv}")
    if args.out_trips_csv:
        sol.trips_as_dataframe().to_csv(args.out_trips_csv, index=False)
        print(f"Resumen de viajes guardado en {args.out_trips_csv}")


if __name__ == "__main__":
    main()
