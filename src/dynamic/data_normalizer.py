from __future__ import annotations

import pandas as pd

CANONICAL_RENAMES = {
    "ready times": "ready_times",
    "service times": "service_times",
    "arrival": "arrivals",
    "deadline": "deadlines",
    "profit": "profits",
}


def normalize_requests_df(df: pd.DataFrame, *, replica_id: int | None = None) -> pd.DataFrame:
    """Normaliza los dataframes del proyecto a columnas canonicas.

    Entrada esperada desde ricas_replica_creator.py o instancias_de_geyter:
    replica, arrivals, deadlines, indicador, x, y, profits, ready times, service times.

    Salida canonica:
    replica, id, arrivals, ready_times, deadlines, indicador, x, y, profits, service_times.
    """
    out = df.copy()
    out = out.rename(columns={c: CANONICAL_RENAMES.get(c, c) for c in out.columns})

    if replica_id is not None and "replica" in out.columns:
        out = out.loc[out["replica"].astype(int) == int(replica_id)].copy()

    required = ["arrivals", "deadlines", "indicador", "x", "y", "profits"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise KeyError(f"Faltan columnas requeridas: {missing}")

    if "ready_times" not in out.columns:
        # Fallback seguro: pickups quedan listos al arrival, pero deliveries deberian tener +900.
        out["ready_times"] = out["arrivals"]

    if "service_times" not in out.columns:
        out["service_times"] = 180

    if "replica" not in out.columns:
        out["replica"] = 0

    if "id" not in out.columns:
        # ID estable dentro de cada replica. Importante para consenso y proyeccion.
        out = out.reset_index(drop=True)
        out["id"] = out.apply(lambda r: f"R{int(r['replica'])}_C{int(r.name)}", axis=1)

    numeric_cols = ["replica", "arrivals", "ready_times", "deadlines", "x", "y", "profits", "service_times"]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=["arrivals", "ready_times", "deadlines", "x", "y", "profits", "service_times"])
    out = out.sort_values(["arrivals", "id"]).reset_index(drop=True)
    return out


def is_pickup_value(value: object) -> bool:
    return str(value).strip().lower() == "true"


def is_delivery_value(value: object) -> bool:
    return str(value).strip().lower() == "false"


def known_at(df: pd.DataFrame, now_sec: float) -> pd.DataFrame:
    return df.loc[df["arrivals"] <= now_sec].copy()


def future_window(df: pd.DataFrame, now_sec: float, lookahead_sec: float, max_sec: float) -> pd.DataFrame:
    end = min(now_sec + lookahead_sec, max_sec)
    return df.loc[(df["arrivals"] > now_sec) & (df["arrivals"] <= end)].copy()
