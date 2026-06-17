from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

VehicleStatus = Literal["at_depot", "en_route", "returning", "done"]
RequestDecision = Literal["unknown", "accepted", "postponed", "outsourced", "served"]


@dataclass(slots=True)
class VehicleState:
    vehicle_id: int
    available_time: float
    status: VehicleStatus = "at_depot"
    current_target_id: str | None = None
    committed_route_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PlannedTrip:
    vehicle_id: int
    trip: int
    customer_ids: list[str]
    departure_time_from_depot: float
    return_to_depot_time: float
    total_profit: float
    total_distance_km: float


@dataclass(slots=True)
class ScenarioPlan:
    scenario_id: int
    trips: list[PlannedTrip]
    total_profit: float
    total_distance_km: float
    served_ids: set[str]
    raw_solution: object | None = None

    def projected(
        self,
        known_ids: set[str],
        profit_by_id: dict[str, float] | None = None,
    ) -> "ScenarioPlan":
        """Proyecta el plan de escenario sobre pedidos ya conocidos.

        MSA resuelve escenarios con pedidos conocidos + pedidos futuros sampleados.
        Para tomar una decision real, se eliminan los clientes futuros. Si se entrega
        profit_by_id, la utilidad proyectada se recalcula solo con clientes conocidos
        para que el tie-breaker del consenso no quede contaminado por pedidos futuros.
        """
        projected_trips: list[PlannedTrip] = []
        served: set[str] = set()
        projected_profit = 0.0
        projected_distance = 0.0

        for tr in self.trips:
            ids = [str(rid) for rid in tr.customer_ids if str(rid) in known_ids]
            if ids:
                served.update(ids)
                trip_profit = (
                    float(sum(profit_by_id.get(rid, 0.0) for rid in ids))
                    if profit_by_id is not None
                    else float(tr.total_profit)
                )
                projected_profit += trip_profit
                projected_distance += float(tr.total_distance_km)
                projected_trips.append(
                    PlannedTrip(
                        vehicle_id=tr.vehicle_id,
                        trip=tr.trip,
                        customer_ids=ids,
                        departure_time_from_depot=tr.departure_time_from_depot,
                        return_to_depot_time=tr.return_to_depot_time,
                        total_profit=trip_profit,
                        total_distance_km=tr.total_distance_km,
                    )
                )

        return ScenarioPlan(
            scenario_id=self.scenario_id,
            trips=projected_trips,
            total_profit=projected_profit if profit_by_id is not None else self.total_profit,
            total_distance_km=projected_distance if profit_by_id is not None else self.total_distance_km,
            served_ids=served,
            raw_solution=self.raw_solution,
        )


@dataclass
class OnlineState:
    now_sec: float
    vehicles: dict[int, VehicleState]
    served_ids: set[str] = field(default_factory=set)
    outsourced_ids: set[str] = field(default_factory=set)
    postponed_ids: set[str] = field(default_factory=set)
    accepted_pickup_ids: set[str] = field(default_factory=set)
    committed_trips: list[PlannedTrip] = field(default_factory=list)

    def available_vehicle_ids(self) -> list[int]:
        return [vid for vid, v in self.vehicles.items() if v.available_time <= self.now_sec and v.status != "done"]

    def next_vehicle_available_time(self) -> float | None:
        times = [v.available_time for v in self.vehicles.values() if v.status != "done"]
        return min(times) if times else None
