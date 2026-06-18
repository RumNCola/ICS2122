from __future__ import annotations

from dataclasses import dataclass
import math
import random
import pandas as pd

from .config_dynamic import DynamicMSAConfig
from .data_normalizer import is_pickup_value, normalize_requests_df
from .entities import OnlineState, PlannedStop, PlannedTrip
from .scenario_sampler_msa import FutureScenarioSampler


@dataclass(slots=True)
class PickupNode:
    request_id: str
    x: float
    y: float
    indicador: object
    ready_time: float
    deadline: float
    service_time: float
    profit: float


@dataclass(slots=True)
class InsertionDecision:
    request_id: str
    decision: str
    phi: float
    vehicle_id: int | None = None
    position: int | None = None
    new_trip: PlannedTrip | None = None


class DynamicPickupInserter:
    """ICD para insertar pickups dinamicos en rutas activas.

    Se calcula phi como la frecuencia de escenarios en que el pickup es insertable y
    seleccionado. Si phi supera el umbral de despacho, se inserta en la mejor posicion
    factible. La insercion solo ocurre despues del proximo cliente bloqueado del camion.
    """

    def __init__(self, config: DynamicMSAConfig, sampler: FutureScenarioSampler):
        self.config = config
        self.sampler = sampler
        self.rng = random.Random(config.seed)

    def handle_pickup_arrival(self, state: OnlineState, pickup_row: pd.Series) -> InsertionDecision:
        node = self._row_to_node(pickup_row, real=True, sid=0)
        active = {v: t for v, t in state.active_trips.items() if t.return_to_depot_time > state.now_sec}
        if not active:
            return InsertionDecision(node.request_id, "infeasible", 0.0)

        n_scen = int(self.config.dynamic_insertion_n_scenarios or self.config.n_scenarios)
        scenarios = self.sampler.sample(state.now_sec)[:n_scen] or [pd.DataFrame()]
        votes = 0
        for sid, future in enumerate(scenarios):
            future_nodes = self._future_nodes(future, sid)
            if self._scenario_vote(active, node, future_nodes, state.now_sec):
                votes += 1
        phi = votes / max(1, len(scenarios))

        threshold = self.config.dynamic_insertion_min_phi_to_insert
        if threshold is None:
            threshold = self.config.icd_dispatch_threshold

        if phi >= threshold:
            best = self._best_insertion(active, node, state.now_sec)
            if best is None:
                return InsertionDecision(node.request_id, "infeasible", phi)
            vehicle_id, position, new_trip, _score = best
            old_trip = state.active_trips[vehicle_id]
            state.active_trips[vehicle_id] = new_trip
            self._replace_committed(state, old_trip, new_trip)
            state.scheduled_ids.add(node.request_id)
            state.accepted_pickup_ids.add(node.request_id)
            state.dynamic_inserted_pickup_ids.add(node.request_id)
            vehicle = state.vehicles[vehicle_id]
            vehicle.available_time = new_trip.return_to_depot_time
            vehicle.status = "returning" if self._current_target(new_trip, state.now_sec) == "DEPOT" else "en_route"
            vehicle.current_target_id = self._current_target(new_trip, state.now_sec)
            return InsertionDecision(node.request_id, "inserted", phi, vehicle_id, position, new_trip)

        if phi < self.config.icd_postpone_threshold:
            state.postponed_ids.add(node.request_id)
            state.dynamic_rejected_pickup_ids.add(node.request_id)
            return InsertionDecision(node.request_id, "postponed", phi)

        state.dynamic_undecided_pickup_ids.add(node.request_id)
        return InsertionDecision(node.request_id, "undecided", phi)

    def _scenario_vote(self, active: dict[int, PlannedTrip], node: PickupNode, future_nodes: list[PickupNode], now: float) -> bool:
        trips = {v: self._copy_trip(t) for v, t in active.items()}
        pool = [node] + future_nodes[: int(self.config.dynamic_insertion_max_future_pickups_per_scenario)]
        inserted: set[str] = set()
        while pool:
            best = None
            best_node = None
            for n in pool:
                move = self._best_insertion(trips, n, now)
                if move is not None and (best is None or move[3] > best[3]):
                    best = move
                    best_node = n
            if best is None or best[3] <= 0:
                break
            vid, _pos, new_trip, _score = best
            trips[vid] = new_trip
            inserted.add(best_node.request_id)  # type: ignore[union-attr]
            pool = [n for n in pool if n.request_id != best_node.request_id]  # type: ignore[union-attr]
        return node.request_id in inserted

    def _best_insertion(self, active: dict[int, PlannedTrip], node: PickupNode, now: float) -> tuple[int, int, PlannedTrip, float] | None:
        best = None
        for vid, trip in active.items():
            if node.request_id in trip.customer_ids:
                continue
            prefix, flex = self._prefix_flex(trip, now)
            if flex is None:
                continue
            for pos in range(len(flex) + 1):
                templates = list(flex)
                templates.insert(pos, self._node_template(node))
                new_trip = self._rebuild(trip, prefix, templates, now)
                if new_trip is None:
                    continue
                add_km = new_trip.total_distance_km - trip.total_distance_km
                delay_min = (new_trip.return_to_depot_time - trip.return_to_depot_time) / 60.0
                score = node.profit - self.config.alns_distance_weight * add_km - 1e-3 * delay_min
                if best is None or score > best[3]:
                    best = (vid, pos, new_trip, score)
        return best

    def _prefix_flex(self, trip: PlannedTrip, now: float) -> tuple[list[PlannedStop], list[PlannedStop] | None]:
        if not trip.stops:
            return [], None
        if now < trip.departure_time_from_depot:
            return [], list(trip.stops)
        completed = [s for s in trip.stops if s.service_end <= now + 1e-9]
        pending = [s for s in trip.stops if s.service_end > now + 1e-9]
        if not pending:
            return completed, None
        # Bloquea el siguiente cliente objetivo.
        return completed + [pending[0]], pending[1:]

    def _rebuild(self, trip: PlannedTrip, prefix: list[PlannedStop], suffix: list[PlannedStop], now: float) -> PlannedTrip | None:
        depot = self.config.depot_xy
        if prefix:
            new_stops = list(prefix)
            prev = (prefix[-1].x, prefix[-1].y)
            t = prefix[-1].service_end
            departure = trip.departure_time_from_depot
        else:
            new_stops = []
            prev = depot
            t = max(trip.departure_time_from_depot, now)
            departure = t
        for tmpl in suffix:
            xy = (tmpl.x, tmpl.y)
            arrival = t + self._travel(prev, xy)
            ready = max(tmpl.ready_time, now if not tmpl.is_delivery else tmpl.ready_time)
            start = max(arrival, ready)
            if start > tmpl.deadline + 1e-9:
                return None
            end = start + tmpl.service_time
            if end > self.config.shift_end_sec + 1e-9:
                return None
            new_stops.append(PlannedStop(str(tmpl.request_id), tmpl.x, tmpl.y, tmpl.indicador, tmpl.ready_time, tmpl.deadline, tmpl.service_time, tmpl.profit, tmpl.is_delivery, arrival, start, end))
            t = end
            prev = xy
        ret = t + self._travel(prev, depot)
        if ret > self.config.shift_end_sec + self.config.dynamic_insertion_margin_sec + 1e-9:
            return None
        return PlannedTrip(trip.vehicle_id, trip.trip, [s.request_id for s in new_stops], departure, ret, sum(s.profit for s in new_stops), self._trip_km(new_stops), new_stops, "dynamic_icd")

    def _row_to_node(self, row: pd.Series, *, real: bool, sid: int) -> PickupNode:
        rid = str(row["id"])
        if not real:
            rid = f"SC{sid}_{rid}"
        return PickupNode(rid, float(row["x"]), float(row["y"]), row["indicador"], max(float(row["ready_times"]), float(row["arrivals"])), float(self.config.shift_end_sec), float(row.get("service_times", self.config.service_time_sec)), float(row.get("profits", 1.0)))

    def _future_nodes(self, future: pd.DataFrame, sid: int) -> list[PickupNode]:
        if future is None or future.empty:
            return []
        df = normalize_requests_df(future)
        df = df.loc[df["indicador"].map(is_pickup_value)].copy()
        if df.empty:
            return []
        df = df.sort_values(["arrivals", "id"]).head(int(self.config.dynamic_insertion_max_future_pickups_per_scenario))
        return [self._row_to_node(row, real=False, sid=sid) for _, row in df.iterrows()]

    def _node_template(self, node: PickupNode) -> PlannedStop:
        return PlannedStop(node.request_id, node.x, node.y, node.indicador, node.ready_time, node.deadline, node.service_time, node.profit, False, 0.0, 0.0, 0.0)

    def _replace_committed(self, state: OnlineState, old_trip: PlannedTrip, new_trip: PlannedTrip) -> None:
        for i, tr in enumerate(state.committed_trips):
            if tr is old_trip or (tr.vehicle_id == old_trip.vehicle_id and tr.customer_ids == old_trip.customer_ids and abs(tr.departure_time_from_depot - old_trip.departure_time_from_depot) < 1e-6):
                state.committed_trips[i] = new_trip
                return
        state.committed_trips.append(new_trip)

    def _copy_trip(self, trip: PlannedTrip) -> PlannedTrip:
        return PlannedTrip(trip.vehicle_id, trip.trip, list(trip.customer_ids), trip.departure_time_from_depot, trip.return_to_depot_time, trip.total_profit, trip.total_distance_km, list(trip.stops), trip.source)

    def _current_target(self, trip: PlannedTrip, now: float) -> str | None:
        for s in trip.stops:
            if s.service_end > now:
                return s.request_id
        return "DEPOT" if trip.return_to_depot_time > now else None

    def _travel(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.ceil(self._dist_m(a, b) / self.config.vehicle_speed_m_per_s)

    def _dist_m(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        if self.config.distance_metric == "euclidean":
            return math.hypot(a[0] - b[0], a[1] - b[1])
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _km(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return self._dist_m(a, b) / 1000.0

    def _trip_km(self, stops: list[PlannedStop]) -> float:
        prev = self.config.depot_xy
        d = 0.0
        for s in stops:
            xy = (s.x, s.y)
            d += self._km(prev, xy)
            prev = xy
        d += self._km(prev, self.config.depot_xy)
        return d
