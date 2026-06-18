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
class PlannedStop:
    """Stop con informacion suficiente para simular progreso e insercion dinamica."""

    request_id: str
    x: float
    y: float
    indicador: object
    ready_time: float
    deadline: float
    service_time: float
    profit: float
    is_delivery: bool
    arrival_time: float
    service_start: float
    service_end: float


@dataclass(slots=True)
class PlannedTrip:
    vehicle_id: int
    trip: int
    customer_ids: list[str]
    departure_time_from_depot: float
    return_to_depot_time: float
    total_profit: float
    total_distance_km: float
    stops: list[PlannedStop] = field(default_factory=list)
    source: str = "msa"


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
                projected_stops = [s for s in tr.stops if str(s.request_id) in known_ids]
                projected_trips.append(
                    PlannedTrip(
                        vehicle_id=tr.vehicle_id,
                        trip=tr.trip,
                        customer_ids=ids,
                        departure_time_from_depot=tr.departure_time_from_depot,
                        return_to_depot_time=tr.return_to_depot_time,
                        total_profit=trip_profit,
                        total_distance_km=tr.total_distance_km,
                        stops=projected_stops,
                        source=tr.source,
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
    scheduled_ids: set[str] = field(default_factory=set)
    active_trips: dict[int, PlannedTrip] = field(default_factory=dict)
    committed_trips: list[PlannedTrip] = field(default_factory=list)
    dynamic_inserted_pickup_ids: set[str] = field(default_factory=set)
    dynamic_rejected_pickup_ids: set[str] = field(default_factory=set)
    dynamic_undecided_pickup_ids: set[str] = field(default_factory=set)
    processed_arrival_ids: set[str] = field(default_factory=set)

    def available_vehicle_ids(self) -> list[int]:
        return [
            vid
            for vid, v in self.vehicles.items()
            if v.available_time <= self.now_sec and v.status == "at_depot" and vid not in self.active_trips
        ]

    def next_vehicle_available_time(self) -> float | None:
        times = [v.available_time for v in self.vehicles.values() if v.status in {"returning", "en_route"}]
        return min(times) if times else None

    def next_active_stop_time(self) -> float | None:
        times: list[float] = []
        for trip in self.active_trips.values():
            for stop in trip.stops:
                if stop.service_end > self.now_sec:
                    times.append(float(stop.service_end))
                    break
        return min(times) if times else None

# Helper agregado para actualizar viajes comprometidos cuando ICD inserta un pickup
def _online_state_upsert_committed_trip(self: OnlineState, trip: PlannedTrip) -> None:
    key = (int(trip.vehicle_id), int(trip.trip), float(trip.departure_time_from_depot))
    for i, existing in enumerate(self.committed_trips):
        existing_key = (int(existing.vehicle_id), int(existing.trip), float(existing.departure_time_from_depot))
        if existing_key == key:
            self.committed_trips[i] = trip
            return
    self.committed_trips.append(trip)

OnlineState.upsert_committed_trip = _online_state_upsert_committed_trip  # type: ignore[attr-defined]
