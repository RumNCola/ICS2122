from __future__ import annotations

from collections import Counter

import pandas as pd

from .config_dynamic import DynamicMSAConfig
from .data_normalizer import is_pickup_value
from .entities import ScenarioPlan


class ICDPickupClassifier:

    def __init__(self, config: DynamicMSAConfig):
        self.config = config

    def classify(self, known_df: pd.DataFrame, plans: list[ScenarioPlan]) -> tuple[set[str], set[str], set[str]]:
        pickups = known_df.loc[known_df["indicador"].map(is_pickup_value)].copy()
        candidate_ids = {str(x) for x in pickups["id"].tolist()}
        if not candidate_ids or not plans:
            return set(), set(), set()

        counts = Counter()
        for plan in plans:
            for rid in plan.served_ids:
                if rid in candidate_ids:
                    counts[rid] += 1

        accepted: set[str] = set()
        postponed: set[str] = set()
        undecided: set[str] = set()
        denom = max(1, len(plans))

        for rid in candidate_ids:
            phi = counts[rid] / denom
            if phi >= self.config.icd_dispatch_threshold:
                accepted.add(rid)
            elif phi < self.config.icd_postpone_threshold:
                postponed.add(rid)
            else:
                undecided.add(rid)

        return accepted, postponed, undecided
