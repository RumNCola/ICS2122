from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config_dynamic import DynamicMSAConfig
from .data_normalizer import future_window, normalize_requests_df


class FutureScenarioSampler:
    """Samplea escenarios futuros para MSA usando ricas_replica_creator.replica().

    Genera replicas completas y luego filtra la ventana (now, now + lookahead). Es
    compatible con tu generador actual. Si keep_sampler_excels=False, borra el Excel
    que ese generador escribe para no llenar el repo durante corridas MSA.
    """

    def __init__(self, config: DynamicMSAConfig):
        self.config = config

    def sample(self, now_sec: float) -> list[pd.DataFrame]:
        from src.ricas_replica_creator import replica

        cfg = self.config
        raw_df, xlsx_path = replica(cfg.instancia, cfg.n_scenarios)
        if not cfg.keep_sampler_excels:
            try:
                Path(xlsx_path).unlink(missing_ok=True)
            except Exception:
                pass

        raw_df = normalize_requests_df(raw_df)
        scenarios: list[pd.DataFrame] = []

        max_future = max(cfg.delivery_cutoff_sec, cfg.pickup_cutoff_sec)
        for sid in sorted(raw_df["replica"].dropna().unique().astype(int)):
            scen = raw_df.loc[raw_df["replica"].astype(int) == sid].copy()
            if now_sec > 15 * 3600:  # Si ya estamos muy cerca del final del día, no tiene sentido mirar tan lejos.
                cfg.lookahead_sec = max(15 * 3600 - now_sec + 1, 1)
            elif now_sec <= 15 * 3600 and now_sec > 13.5 * 3600:
                cfg.lookahead_sec = 90 * 60
            elif now_sec <= 13.5 * 3600 and now_sec > 12 * 3600:
                cfg.lookahead_sec = 120 * 60
            elif now_sec <= 12 * 3600 and now_sec > 10.5 * 3600:
                cfg.lookahead_sec = 150 * 60
            else:
                cfg.lookahead_sec = 180 * 60

            scen = future_window(scen, now_sec, cfg.lookahead_sec, max_future)
            if scen.empty:
                scenarios.append(scen)
                continue

            scen["scenario_id"] = sid
            scen["id"] = scen["id"].astype(str).map(lambda x: f"S{sid}_{x}")
            scenarios.append(scen.reset_index(drop=True))

        return scenarios
