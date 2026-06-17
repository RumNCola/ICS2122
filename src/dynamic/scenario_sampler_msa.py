from __future__ import annotations

import pandas as pd

from .config_dynamic import DynamicMSAConfig
from .data_normalizer import normalize_requests_df, future_window


class FutureScenarioSampler:
    """Samplea escenarios futuros para MSA usando ricas_replica_creator.replica().

    Esta version preliminar genera replicas completas y luego filtra la ventana
    (now, now + lookahead). Es simple y compatible con tu codigo actual.
    Luego se puede optimizar para simular directamente desde now.
    """

    def __init__(self, config: DynamicMSAConfig):
        self.config = config

    def sample(self, now_sec: float) -> list[pd.DataFrame]:
        from src.ricas_replica_creator import replica

        cfg = self.config
        raw_df, _ = replica(cfg.instancia, cfg.n_scenarios)
        raw_df = normalize_requests_df(raw_df)
        scenarios: list[pd.DataFrame] = []

        max_future = max(cfg.delivery_cutoff_sec, cfg.pickup_cutoff_sec)
        for sid in sorted(raw_df["replica"].dropna().unique().astype(int)):
            scen = raw_df.loc[raw_df["replica"].astype(int) == sid].copy()
            scen = future_window(scen, now_sec, cfg.lookahead_sec, max_future)
            if scen.empty:
                scenarios.append(scen)
                continue

            scen["scenario_id"] = sid
            scen["id"] = scen["id"].astype(str).map(lambda x: f"S{sid}_{x}")
            scenarios.append(scen.reset_index(drop=True))

        return scenarios
