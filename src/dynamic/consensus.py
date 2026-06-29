from __future__ import annotations

from collections import Counter
from typing import Iterable

from .config_dynamic import DynamicMSAConfig
from .entities import ScenarioPlan


class ConsensusSelector:

    WAIT_TOKEN = "WAIT"

    def __init__(self, config: DynamicMSAConfig):
        self.config = config

    def _vehicle_ids_from_plans(self, plans: Iterable[ScenarioPlan]) -> list[int]:
        ids: set[int] = set()
        for plan in plans:
            for trip in plan.trips:
                ids.add(int(trip.vehicle_id))
        return sorted(ids)

    def next_customer_by_vehicle(
        self,
        plan: ScenarioPlan,
        vehicle_ids: list[int] | None = None,
    ) -> dict[int, str]:
        if vehicle_ids is None:
            vehicle_ids = self._vehicle_ids_from_plans([plan])

        nexts: dict[int, str] = {int(v): self.WAIT_TOKEN for v in vehicle_ids}
        assigned: set[int] = set()

        for trip in sorted(plan.trips, key=lambda t: (int(t.vehicle_id), int(t.trip))):
            vehicle_id = int(trip.vehicle_id)
            if vehicle_id not in nexts or vehicle_id in assigned:
                continue
            if trip.customer_ids:
                nexts[vehicle_id] = str(trip.customer_ids[0])
            assigned.add(vehicle_id)

        return nexts

    def build_vote_matrix(
        self,
        plans: list[ScenarioPlan],
        vehicle_ids: list[int],
    ) -> dict[int, Counter[str]]:
        matrix: dict[int, Counter[str]] = {int(v): Counter() for v in vehicle_ids}

        for plan in plans:
            nexts = self.next_customer_by_vehicle(plan, vehicle_ids)
            for vehicle_id in vehicle_ids:
                matrix[int(vehicle_id)][nexts[int(vehicle_id)]] += 1

        return matrix

    def van_hentenryck_score(
        self,
        plan: ScenarioPlan,
        vote_matrix: dict[int, Counter[str]],
        vehicle_ids: list[int],
    ) -> int:
        """Implementa f_t(pi) = sum_v M_t[v, a_v(pi)]."""
        nexts = self.next_customer_by_vehicle(plan, vehicle_ids)
        return int(sum(vote_matrix[int(v)][nexts[int(v)]] for v in vehicle_ids))

    def _signature_exact_next_stop(
        self,
        plan: ScenarioPlan,
        vehicle_ids: list[int] | None = None,
    ) -> tuple[tuple[int, str], ...]:
        nexts = self.next_customer_by_vehicle(plan, vehicle_ids)
        return tuple(sorted(nexts.items()))

    def _signature_served_set(self, plan: ScenarioPlan) -> tuple[str, ...]:
        return tuple(sorted(str(x) for x in plan.served_ids))

    def _select_legacy_exact(
        self,
        plans: list[ScenarioPlan],
        vehicle_ids: list[int],
    ) -> ScenarioPlan:
        signatures = [self._signature_exact_next_stop(p, vehicle_ids) for p in plans]
        freq = Counter(signatures)
        n = max(1, len(plans))

        def score(plan: ScenarioPlan) -> tuple[float, float, float]:
            consensus = freq[self._signature_exact_next_stop(plan, vehicle_ids)] / n
            # En legacy se puede usar threshold si se configuro. En Van Hentenryck no.
            threshold = self.config.consensus_threshold
            passes = 1.0 if threshold is None or consensus >= threshold else 0.0
            return (passes, consensus, plan.total_profit, -plan.total_distance_km)

        best = max(plans, key=score)
        if self.config.consensus_threshold is not None:
            best_consensus = freq[self._signature_exact_next_stop(best, vehicle_ids)] / n
            if best_consensus < self.config.consensus_threshold:
                best = max(plans, key=lambda p: (p.total_profit, -p.total_distance_km))
        return best

    def _select_legacy_served_set(self, plans: list[ScenarioPlan]) -> ScenarioPlan:
        signatures = [self._signature_served_set(p) for p in plans]
        freq = Counter(signatures)
        n = max(1, len(plans))

        def score(plan: ScenarioPlan) -> tuple[float, float, float]:
            consensus = freq[self._signature_served_set(plan)] / n
            threshold = self.config.consensus_threshold
            passes = 1.0 if threshold is None or consensus >= threshold else 0.0
            return (passes, consensus, plan.total_profit, -plan.total_distance_km)

        best = max(plans, key=score)
        if self.config.consensus_threshold is not None:
            best_consensus = freq[self._signature_served_set(best)] / n
            if best_consensus < self.config.consensus_threshold:
                best = max(plans, key=lambda p: (p.total_profit, -p.total_distance_km))
        return best

    def select(
        self,
        plans: list[ScenarioPlan],
        vehicle_ids: list[int] | None = None,
    ) -> ScenarioPlan | None:
        feasible = [p for p in plans if p.trips]
        if not feasible:
            return None

        if vehicle_ids is None:
            vehicle_ids = self._vehicle_ids_from_plans(feasible)
        vehicle_ids = sorted({int(v) for v in vehicle_ids})
        if not vehicle_ids:
            return max(feasible, key=lambda p: (p.total_profit, -p.total_distance_km))

        if self.config.consensus_mode == "exact_next_stop":
            return self._select_legacy_exact(feasible, vehicle_ids)
        if self.config.consensus_mode == "served_set":
            return self._select_legacy_served_set(feasible)

        vote_matrix = self.build_vote_matrix(feasible, vehicle_ids)

        def score(plan: ScenarioPlan) -> tuple[int, float, float]:
            return (
                self.van_hentenryck_score(plan, vote_matrix, vehicle_ids),
                plan.total_profit,
                -plan.total_distance_km,
            )

        return max(feasible, key=score)
