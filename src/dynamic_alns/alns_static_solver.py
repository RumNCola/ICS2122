from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

import pandas as pd

from .config_dynamic import DynamicMSAConfig
from .data_normalizer import is_delivery_value, normalize_requests_df
from .entities import PlannedStop


@dataclass(slots=True, frozen=True)
class Customer:
    id: str
    x: float
    y: float
    indicador: object
    ready_time: float
    deadline: float
    service_time: float
    profit: float
    is_delivery: bool


@dataclass(slots=True)
class TripInfo:
    vehicle_id: int
    trip: int
    customer_ids: list[str]
    departure_time_from_depot: float
    return_to_depot_time: float
    total_profit: float
    total_distance_km: float
    feasible: bool = True
    stops: list[PlannedStop] = field(default_factory=list)


@dataclass(slots=True)
class EvalResult:
    feasible: bool
    score: float
    total_profit: float
    total_distance_km: float
    nb_trips: int
    trips: list[TripInfo] = field(default_factory=list)


@dataclass(slots=True)
class InsertionMove:
    customer_id: str
    vehicle_id: int
    route_index: int
    position: int
    eval_result: EvalResult
    gain: float
    raw_gain: float
    added_distance_km: float


SolutionRoutes = dict[int, list[list[str]]]


class Timeout:
    def __init__(self, seconds: float):
        self.start = time.perf_counter()
        self.seconds = max(0.001, float(seconds))

    def expired(self) -> bool:
        return time.perf_counter() - self.start >= self.seconds

    def remaining(self) -> float:
        return max(0.0, self.seconds - (time.perf_counter() - self.start))


class ALNSPrizeCollectingVRPTW:
    """ALNS para PC multi-trip VRPTW usado como evaluador de escenarios MSA.

    Incluye operadores base y operadores de tu avance:
    - destroy: random, worst, related, sequence, shaw_ready, shaw_deadline,
      geographic, route_vehicle.
    - repair: greedy, regret2, regret3, ratio, deadline, ready.
    """

    def __init__(
        self,
        config: DynamicMSAConfig,
        requests_df: pd.DataFrame,
        *,
        now_sec: float,
        vehicle_ids: list[int],
        seed: int | None = None,
    ):
        self.config = config
        self.now_sec = float(now_sec)
        self.vehicle_ids = [int(v) for v in vehicle_ids]
        self.rng = random.Random(seed)
        # La evaluacion ALNS consulta las mismas distancias miles de veces.
        # Este cache local a cada worker evita recalcular Manhattan/Euclidea.
        self._distance_m_cache: dict[tuple[tuple[float, float], tuple[float, float]], float] = {}
        self.customers = self._build_customers(requests_df)
        self.customer_ids = sorted(self.customers.keys())

        self.destroy_ops: dict[str, Callable[[SolutionRoutes, int], tuple[SolutionRoutes, set[str]]]] = {
            "random": self._destroy_random,
            "worst": self._destroy_worst,
            "related": self._destroy_related,
            "sequence": self._destroy_sequence,
            "shaw_ready": self._destroy_shaw_ready,
            "shaw_deadline": self._destroy_shaw_deadline,
            "geographic": self._destroy_geographic,
            "route_vehicle": self._destroy_route_vehicle,
        }
        if not self.config.alns_enable_extended_operators:
            self.destroy_ops = {k: self.destroy_ops[k] for k in ["random", "worst", "related", "sequence"]}

        self.repair_ops: dict[str, Callable[[SolutionRoutes, set[str], Timeout], SolutionRoutes]] = {
            "greedy": self._repair_greedy,
            "regret2": lambda s, p, t: self._repair_regret(s, p, t, k=2),
            "regret3": lambda s, p, t: self._repair_regret(s, p, t, k=3),
            "ratio": self._repair_ratio,
            "deadline": self._repair_by_deadline,
            "ready": self._repair_by_ready,
        }
        if not self.config.alns_enable_extended_operators:
            self.repair_ops = {k: self.repair_ops[k] for k in ["greedy", "regret2", "regret3"]}

        self.pair_weights = {(d, r): 1.0 for d in self.destroy_ops for r in self.repair_ops}
        self.pair_scores = {key: 0.0 for key in self.pair_weights}
        self.pair_counts = {key: 0 for key in self.pair_weights}

    # ------------------------------------------------------------------
    # Datos y distancias
    # ------------------------------------------------------------------

    def _build_customers(self, requests_df: pd.DataFrame) -> dict[str, Customer]:
        df = normalize_requests_df(requests_df)
        customers: dict[str, Customer] = {}
        for _, row in df.iterrows():
            rid = str(row["id"])
            is_delivery = is_delivery_value(row["indicador"])
            ready = float(row["ready_times"])
            deadline = float(row["deadlines"]) if is_delivery else float(self.config.shift_end_sec)
            customers[rid] = Customer(
                id=rid,
                x=float(row["x"]),
                y=float(row["y"]),
                indicador=row["indicador"],
                ready_time=max(float(self.now_sec), ready),
                deadline=min(float(deadline), float(self.config.shift_end_sec)),
                service_time=float(row.get("service_times", self.config.service_time_sec)),
                profit=float(row["profits"]),
                is_delivery=bool(is_delivery),
            )
        return customers

    def _dist_m(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        # Distancias simetricas: normalizamos la llave para que (a,b) y (b,a)
        # compartan la misma entrada. El cache vive solo durante un escenario.
        key = (a, b) if a <= b else (b, a)
        cached = self._distance_m_cache.get(key)
        if cached is not None:
            return cached
        if self.config.distance_metric == "euclidean":
            value = math.hypot(a[0] - b[0], a[1] - b[1])
        else:
            value = abs(a[0] - b[0]) + abs(a[1] - b[1])
        self._distance_m_cache[key] = value
        return value

    def _travel_sec(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.ceil(self._dist_m(a, b) / self.config.vehicle_speed_m_per_s)

    def _distance_km(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return self._dist_m(a, b) / 1000.0

    # ------------------------------------------------------------------
    # Evaluacion
    # ------------------------------------------------------------------

    def empty_solution(self) -> SolutionRoutes:
        return {v: [] for v in self.vehicle_ids}

    def clone(self, routes: SolutionRoutes) -> SolutionRoutes:
        return {int(v): [list(route) for route in route_list] for v, route_list in routes.items()}

    def served_ids(self, routes: SolutionRoutes) -> set[str]:
        out: set[str] = set()
        for route_list in routes.values():
            for route in route_list:
                out.update(str(cid) for cid in route)
        return out

    def clean(self, routes: SolutionRoutes) -> SolutionRoutes:
        cleaned = {int(v): [list(r) for r in route_list if len(r) > 0] for v, route_list in routes.items()}
        for v in self.vehicle_ids:
            cleaned.setdefault(v, [])
        return cleaned

    def evaluate_trip(self, *, vehicle_id: int, trip_index: int, sequence: list[str], available_at_depot: float) -> tuple[TripInfo, bool, float]:
        depot = self.config.depot_xy
        if not sequence:
            info = TripInfo(vehicle_id, trip_index, [], available_at_depot, available_at_depot, 0.0, 0.0, True, [])
            return info, True, available_at_depot

        delivery_ready = [self.customers[cid].ready_time for cid in sequence if self.customers[cid].is_delivery]
        departure = max(float(available_at_depot), max(delivery_ready) if delivery_ready else float(available_at_depot), self.now_sec)
        current_time = departure
        prev_xy = depot
        total_distance_km = 0.0
        total_profit = 0.0
        feasible = True
        stops: list[PlannedStop] = []

        for cid in sequence:
            c = self.customers[cid]
            xy = (c.x, c.y)
            current_time += self._travel_sec(prev_xy, xy)
            total_distance_km += self._distance_km(prev_xy, xy)
            arrival_time = current_time
            service_start = max(arrival_time, c.ready_time)
            if service_start > c.deadline + 1e-9:
                feasible = False
            service_end = service_start + c.service_time
            if service_end > self.config.shift_end_sec + 1e-9:
                feasible = False
            stops.append(
                PlannedStop(
                    request_id=str(cid),
                    x=float(c.x),
                    y=float(c.y),
                    indicador=c.indicador,
                    ready_time=float(c.ready_time),
                    deadline=float(c.deadline),
                    service_time=float(c.service_time),
                    profit=float(c.profit),
                    is_delivery=bool(c.is_delivery),
                    arrival_time=float(arrival_time),
                    service_start=float(service_start),
                    service_end=float(service_end),
                )
            )
            current_time = service_end
            total_profit += c.profit
            prev_xy = xy

        current_time += self._travel_sec(prev_xy, depot)
        total_distance_km += self._distance_km(prev_xy, depot)
        if current_time > self.config.shift_end_sec + 1e-9:
            feasible = False

        info = TripInfo(
            vehicle_id=vehicle_id,
            trip=trip_index,
            customer_ids=list(sequence),
            departure_time_from_depot=float(departure),
            return_to_depot_time=float(current_time),
            total_profit=float(total_profit),
            total_distance_km=float(total_distance_km),
            feasible=feasible,
            stops=stops,
        )
        return info, feasible, current_time

    def evaluate(self, routes: SolutionRoutes) -> EvalResult:
        routes = self.clean(routes)
        feasible = True
        total_profit = 0.0
        total_distance_km = 0.0
        trips: list[TripInfo] = []

        seen: set[str] = set()
        duplicate = False
        for route_list in routes.values():
            for route in route_list:
                for cid in route:
                    if cid in seen:
                        duplicate = True
                    seen.add(cid)
        if duplicate:
            feasible = False

        for vehicle_id in self.vehicle_ids:
            available = float(self.now_sec)
            route_list = routes.get(vehicle_id, [])
            if len(route_list) > self.config.max_trips_per_vehicle:
                feasible = False
            for trip_index, seq in enumerate(route_list):
                if not seq:
                    continue
                info, ok, available = self.evaluate_trip(vehicle_id=vehicle_id, trip_index=trip_index, sequence=seq, available_at_depot=available)
                feasible = feasible and ok
                trips.append(info)
                total_profit += info.total_profit
                total_distance_km += info.total_distance_km

        if not feasible:
            return EvalResult(False, -1e18, total_profit, total_distance_km, len(trips), trips)

        score = total_profit - self.config.alns_distance_weight * total_distance_km - self.config.alns_trip_penalty * len(trips)
        return EvalResult(True, score, total_profit, total_distance_km, len(trips), trips)

    def evaluate_fixed_sequences(self, routes: SolutionRoutes) -> EvalResult:
        return self.evaluate(routes)

    # ------------------------------------------------------------------
    # Inserciones
    # ------------------------------------------------------------------

    def _insert_candidate(self, routes: SolutionRoutes, cid: str, vehicle_id: int, route_index: int, position: int) -> SolutionRoutes:
        new_routes = self.clone(routes)
        route_list = new_routes.setdefault(vehicle_id, [])
        if route_index == len(route_list):
            route_list.append([cid])
        else:
            route_list[route_index].insert(position, cid)
        return self.clean(new_routes)

    def _remove_customers(self, routes: SolutionRoutes, remove_ids: Iterable[str]) -> SolutionRoutes:
        remove = {str(x) for x in remove_ids}
        new_routes = self.clone(routes)
        for v in list(new_routes.keys()):
            updated = []
            for route in new_routes[v]:
                seq = [cid for cid in route if cid not in remove]
                if seq:
                    updated.append(seq)
            new_routes[v] = updated
        return self.clean(new_routes)

    def _all_insertion_moves_for_customer(self, routes: SolutionRoutes, cid: str, current_score: float, current_distance: float | None = None) -> list[InsertionMove]:
        moves: list[InsertionMove] = []
        if cid in self.served_ids(routes):
            return moves
        if current_distance is None:
            current_distance = self.evaluate(routes).total_distance_km

        for vehicle_id in self.vehicle_ids:
            route_list = routes.get(vehicle_id, [])
            for ridx, seq in enumerate(route_list):
                for pos in range(len(seq) + 1):
                    cand_routes = self._insert_candidate(routes, cid, vehicle_id, ridx, pos)
                    ev = self.evaluate(cand_routes)
                    if ev.feasible:
                        raw_gain = ev.score - current_score
                        gain = raw_gain
                        if self.config.alns_repair_noise:
                            gain += self.rng.uniform(-self.config.alns_repair_noise, self.config.alns_repair_noise)
                        moves.append(InsertionMove(cid, vehicle_id, ridx, pos, ev, gain, raw_gain, ev.total_distance_km - current_distance))
            if len(route_list) < self.config.max_trips_per_vehicle:
                ridx = len(route_list)
                cand_routes = self._insert_candidate(routes, cid, vehicle_id, ridx, 0)
                ev = self.evaluate(cand_routes)
                if ev.feasible:
                    raw_gain = ev.score - current_score
                    gain = raw_gain
                    if self.config.alns_repair_noise:
                        gain += self.rng.uniform(-self.config.alns_repair_noise, self.config.alns_repair_noise)
                    moves.append(InsertionMove(cid, vehicle_id, ridx, 0, ev, gain, raw_gain, ev.total_distance_km - current_distance))
        moves.sort(key=lambda m: m.gain, reverse=True)
        return moves

    def _apply_move(self, routes: SolutionRoutes, move: InsertionMove) -> SolutionRoutes:
        return self._insert_candidate(routes, move.customer_id, move.vehicle_id, move.route_index, move.position)

    def _repair_greedy(self, routes: SolutionRoutes, pool: set[str], timeout: Timeout) -> SolutionRoutes:
        routes = self.clean(routes)
        pool = set(pool)
        while pool and not timeout.expired():
            current = self.evaluate(routes)
            best: InsertionMove | None = None
            for cid in list(pool):
                if timeout.expired():
                    break
                moves = self._all_insertion_moves_for_customer(routes, cid, current.score, current.total_distance_km)
                if moves and (best is None or moves[0].gain > best.gain):
                    best = moves[0]
            if best is None or best.raw_gain <= 1e-9:
                break
            routes = self._apply_move(routes, best)
            pool.remove(best.customer_id)
        return self.clean(routes)

    def _repair_regret(self, routes: SolutionRoutes, pool: set[str], timeout: Timeout, *, k: int) -> SolutionRoutes:
        routes = self.clean(routes)
        pool = set(pool)
        while pool and not timeout.expired():
            current = self.evaluate(routes)
            chosen: tuple[float, InsertionMove] | None = None
            for cid in list(pool):
                if timeout.expired():
                    break
                moves = self._all_insertion_moves_for_customer(routes, cid, current.score, current.total_distance_km)
                if not moves:
                    continue
                best = moves[0]
                if best.raw_gain <= 1e-9:
                    continue
                if len(moves) >= k:
                    regret = best.raw_gain - moves[k - 1].raw_gain
                elif len(moves) >= 2:
                    regret = best.raw_gain - moves[-1].raw_gain + 0.1
                else:
                    regret = best.raw_gain + 0.5
                key = (regret, best.raw_gain)
                if chosen is None or key > (chosen[0], chosen[1].raw_gain):
                    chosen = (regret, best)
            if chosen is None:
                break
            move = chosen[1]
            routes = self._apply_move(routes, move)
            pool.remove(move.customer_id)
        return self.clean(routes)

    def _repair_ratio(self, routes: SolutionRoutes, pool: set[str], timeout: Timeout) -> SolutionRoutes:
        routes = self.clean(routes)
        pool = set(pool)
        while pool and not timeout.expired():
            current = self.evaluate(routes)
            best_key: tuple[float, float] | None = None
            best_move: InsertionMove | None = None
            for cid in list(pool):
                if timeout.expired():
                    break
                moves = self._all_insertion_moves_for_customer(routes, cid, current.score, current.total_distance_km)
                if not moves or moves[0].raw_gain <= 1e-9:
                    continue
                move = moves[0]
                c = self.customers[cid]
                ratio = c.profit / max(1e-6, max(0.0, move.added_distance_km))
                key = (ratio, move.raw_gain)
                if best_key is None or key > best_key:
                    best_key, best_move = key, move
            if best_move is None:
                break
            routes = self._apply_move(routes, best_move)
            pool.remove(best_move.customer_id)
        return self.clean(routes)

    def _repair_ordered(self, routes: SolutionRoutes, pool: set[str], timeout: Timeout, *, key_func) -> SolutionRoutes:
        routes = self.clean(routes)
        for cid in sorted(set(pool), key=key_func):
            if timeout.expired():
                break
            current = self.evaluate(routes)
            moves = self._all_insertion_moves_for_customer(routes, cid, current.score, current.total_distance_km)
            if moves and moves[0].raw_gain > 1e-9:
                routes = self._apply_move(routes, moves[0])
        return self.clean(routes)

    def _repair_by_deadline(self, routes: SolutionRoutes, pool: set[str], timeout: Timeout) -> SolutionRoutes:
        return self._repair_ordered(routes, pool, timeout, key_func=lambda cid: (self.customers[cid].deadline, -self.customers[cid].profit, self.rng.random()))

    def _repair_by_ready(self, routes: SolutionRoutes, pool: set[str], timeout: Timeout) -> SolutionRoutes:
        return self._repair_ordered(routes, pool, timeout, key_func=lambda cid: (self.customers[cid].ready_time, self.customers[cid].deadline, self.rng.random()))

    # ------------------------------------------------------------------
    # Construccion inicial
    # ------------------------------------------------------------------

    def initial_solution(self, timeout: Timeout) -> SolutionRoutes:
        pool = set(self.customer_ids)
        routes = self.empty_solution()
        ordered = sorted(pool, key=lambda cid: (self.customers[cid].deadline, -self.customers[cid].profit, self.customers[cid].ready_time))
        for cid in ordered:
            if timeout.expired():
                break
            current = self.evaluate(routes)
            moves = self._all_insertion_moves_for_customer(routes, cid, current.score, current.total_distance_km)
            if moves and moves[0].raw_gain > 1e-9:
                routes = self._apply_move(routes, moves[0])
                pool.discard(cid)
        if pool and not timeout.expired():
            routes = self._repair_regret(routes, pool, timeout, k=2)
        return self.clean(routes)

    # ------------------------------------------------------------------
    # Destruccion
    # ------------------------------------------------------------------

    def _choose_q(self, n_served: int) -> int:
        if n_served <= 0:
            return 0
        frac = self.rng.uniform(self.config.alns_min_remove_fraction, self.config.alns_max_remove_fraction)
        q = int(math.ceil(frac * n_served))
        q = max(self.config.alns_min_remove, q)
        q = min(self.config.alns_max_remove, q, n_served)
        return q

    def _destroy_random(self, routes: SolutionRoutes, q: int) -> tuple[SolutionRoutes, set[str]]:
        served = list(self.served_ids(routes))
        if not served or q <= 0:
            return self.clean(routes), set()
        remove = set(self.rng.sample(served, k=min(q, len(served))))
        return self._remove_customers(routes, remove), remove

    def _destroy_worst(self, routes: SolutionRoutes, q: int) -> tuple[SolutionRoutes, set[str]]:
        served = list(self.served_ids(routes))
        if not served or q <= 0:
            return self.clean(routes), set()
        current = self.evaluate(routes)
        scored: list[tuple[float, str]] = []
        for cid in served:
            cand = self._remove_customers(routes, {cid})
            ev = self.evaluate(cand)
            # Si removerlo sube el score, es mal cliente: conviene destruirlo.
            delta = ev.score - current.score
            scored.append((delta, cid))
        scored.sort(reverse=True)
        remove = {cid for _, cid in scored[: min(q, len(scored))]}
        return self._remove_customers(routes, remove), remove

    def _destroy_related(self, routes: SolutionRoutes, q: int) -> tuple[SolutionRoutes, set[str]]:
        served = list(self.served_ids(routes))
        if not served or q <= 0:
            return self.clean(routes), set()
        seed = self.rng.choice(served)
        seed_c = self.customers[seed]
        scored = []
        for cid in served:
            c = self.customers[cid]
            spatial = self._dist_m((seed_c.x, seed_c.y), (c.x, c.y)) / 1000.0
            time_rel = abs(seed_c.ready_time - c.ready_time) / 3600.0
            deadline_rel = abs(seed_c.deadline - c.deadline) / 3600.0
            type_penalty = 0.0 if seed_c.is_delivery == c.is_delivery else 1.0
            scored.append((spatial + 0.4 * time_rel + 0.4 * deadline_rel + type_penalty, cid))
        scored.sort()
        remove = {cid for _, cid in scored[: min(q, len(scored))]}
        return self._remove_customers(routes, remove), remove

    def _destroy_by_scalar_similarity(self, routes: SolutionRoutes, q: int, attr: str) -> tuple[SolutionRoutes, set[str]]:
        served = list(self.served_ids(routes))
        if not served or q <= 0:
            return self.clean(routes), set()
        seed = self.rng.choice(served)
        value = getattr(self.customers[seed], attr)
        served.sort(key=lambda cid: abs(getattr(self.customers[cid], attr) - value))
        remove = set(served[: min(q, len(served))])
        return self._remove_customers(routes, remove), remove

    def _destroy_shaw_ready(self, routes: SolutionRoutes, q: int) -> tuple[SolutionRoutes, set[str]]:
        return self._destroy_by_scalar_similarity(routes, q, "ready_time")

    def _destroy_shaw_deadline(self, routes: SolutionRoutes, q: int) -> tuple[SolutionRoutes, set[str]]:
        return self._destroy_by_scalar_similarity(routes, q, "deadline")

    def _destroy_geographic(self, routes: SolutionRoutes, q: int) -> tuple[SolutionRoutes, set[str]]:
        served = list(self.served_ids(routes))
        if not served or q <= 0:
            return self.clean(routes), set()
        seed = self.rng.choice(served)
        seed_c = self.customers[seed]
        served.sort(key=lambda cid: self._dist_m((seed_c.x, seed_c.y), (self.customers[cid].x, self.customers[cid].y)))
        remove = set(served[: min(q, len(served))])
        return self._remove_customers(routes, remove), remove

    def _destroy_sequence(self, routes: SolutionRoutes, q: int) -> tuple[SolutionRoutes, set[str]]:
        non_empty: list[tuple[int, int, list[str]]] = []
        for v, route_list in routes.items():
            for ridx, seq in enumerate(route_list):
                if seq:
                    non_empty.append((v, ridx, seq))
        if not non_empty or q <= 0:
            return self.clean(routes), set()
        _, _, seq = self.rng.choice(non_empty)
        start = self.rng.randrange(len(seq))
        length = min(q, len(seq) - start)
        remove = set(seq[start:start + length])
        if len(remove) < q:
            remaining = list(self.served_ids(routes) - remove)
            if remaining:
                remove.update(self.rng.sample(remaining, k=min(q - len(remove), len(remaining))))
        return self._remove_customers(routes, remove), remove

    def _destroy_route_vehicle(self, routes: SolutionRoutes, q: int) -> tuple[SolutionRoutes, set[str]]:
        # Inspirado en matar_camion: elimina la carga completa de un camion al azar.
        non_empty_vehicles = [v for v, route_list in routes.items() if any(route_list)]
        if not non_empty_vehicles:
            return self.clean(routes), set()
        v = self.rng.choice(non_empty_vehicles)
        remove = {cid for route in routes.get(v, []) for cid in route}
        return self._remove_customers(routes, remove), remove

    # ------------------------------------------------------------------
    # ALNS loop
    # ------------------------------------------------------------------

    def _choose_pair(self) -> tuple[str, str]:
        total = sum(max(w, 1e-9) for w in self.pair_weights.values())
        draw = self.rng.random() * total
        acc = 0.0
        for pair, weight in self.pair_weights.items():
            acc += max(weight, 1e-9)
            if acc >= draw:
                return pair
        return next(iter(self.pair_weights))

    def _update_weights(self) -> None:
        rho = self.config.alns_reaction_factor
        for pair in list(self.pair_weights.keys()):
            count = self.pair_counts[pair]
            if count > 0:
                avg_score = self.pair_scores[pair] / count
                self.pair_weights[pair] = (1 - rho) * self.pair_weights[pair] + rho * max(0.05, avg_score)
            self.pair_scores[pair] = 0.0
            self.pair_counts[pair] = 0

    def _accept(self, new_score: float, current_score: float, temperature: float) -> bool:
        if new_score >= current_score:
            return True
        prob = math.exp((new_score - current_score) / max(temperature, 1e-9))
        return self.rng.random() < prob

    def solve(self, time_limit_sec: float) -> EvalResult:
        timeout = Timeout(time_limit_sec)
        current_routes = self.initial_solution(timeout)
        current_eval = self.evaluate(current_routes)
        best_routes = self.clone(current_routes)
        best_eval = current_eval
        temperature = self.config.alns_initial_temperature

        iteration = 0
        while not timeout.expired() and iteration < self.config.alns_max_iterations:
            iteration += 1
            served_n = len(self.served_ids(current_routes))
            if served_n == 0:
                current_routes = self.initial_solution(timeout)
                current_eval = self.evaluate(current_routes)
                if current_eval.score > best_eval.score:
                    best_routes = self.clone(current_routes)
                    best_eval = current_eval
                continue

            q = self._choose_q(served_n)
            destroy_name, repair_name = self._choose_pair()
            destroyed_routes, removed = self.destroy_ops[destroy_name](current_routes, q)
            pool = set(removed) | (set(self.customer_ids) - self.served_ids(destroyed_routes))
            repaired_routes = self.repair_ops[repair_name](destroyed_routes, pool, timeout)
            new_eval = self.evaluate(repaired_routes)

            pair = (destroy_name, repair_name)
            self.pair_counts[pair] += 1

            if new_eval.feasible and new_eval.score > best_eval.score + 1e-9:
                best_routes = self.clone(repaired_routes)
                best_eval = new_eval
                current_routes = self.clone(repaired_routes)
                current_eval = new_eval
                self.pair_scores[pair] += self.config.alns_score_global_best
            elif new_eval.feasible and new_eval.score > current_eval.score + 1e-9:
                current_routes = self.clone(repaired_routes)
                current_eval = new_eval
                self.pair_scores[pair] += self.config.alns_score_improved
            elif new_eval.feasible and self._accept(new_eval.score, current_eval.score, temperature):
                current_routes = self.clone(repaired_routes)
                current_eval = new_eval
                self.pair_scores[pair] += self.config.alns_score_accepted

            if iteration % self.config.alns_segment_length == 0:
                self._update_weights()
            temperature *= self.config.alns_cooling_rate

        return self.evaluate(best_routes)
