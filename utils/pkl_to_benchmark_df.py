from __future__ import annotations

import argparse
import pickle
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd


FIELDS = [
    "arrivals",
    "deadlines",
    "indicador",
    "points",
    "profits",
    "ready_times",
    "service_times",
]

ROMAN_BY_INSTANCE = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
}

INSTANCE_BY_ROMAN = {v: k for k, v in ROMAN_BY_INSTANCE.items()}


# -----------------------------------------------------------------------------
# API principal
# -----------------------------------------------------------------------------


def load_all_instance_dataframes(
    base_dir: Union[str, Path] = "data",
    *,
    instances: Iterable[Union[int, str]] = (1, 2, 3, 4),
    drop_depot: bool = True,
    recompute_profits: bool = True,
    delivery_profit: float = 2.0,
    pickup_profit: float = 1.0,
    indicador_as_string: bool = True,
    sort_by_replica_and_arrival: bool = False,
) -> Dict[int, pd.DataFrame]:
    """
    Carga las 4 instancias desde carpetas y retorna un dict:

        {
            1: df_instancia_1,
            2: df_instancia_2,
            3: df_instancia_3,
            4: df_instancia_4,
        }

    Cada DataFrame contiene todas las replicas de esa instancia.
    """
    base_dir = Path(base_dir)
    dataframes: Dict[int, pd.DataFrame] = {}

    for instance in instances:
        instance_num = parse_instance_id(instance)
        folder = base_dir / f"Instancia Tipo {ROMAN_BY_INSTANCE[instance_num]}"
        df = pkl_folder_to_dataframe(
            folder,
            drop_depot=drop_depot,
            recompute_profits=recompute_profits,
            delivery_profit=delivery_profit,
            pickup_profit=pickup_profit,
            indicador_as_string=indicador_as_string,
            sort_by_replica_and_arrival=sort_by_replica_and_arrival,
        )
        dataframes[instance_num] = df

    return dataframes


def pkl_folder_to_dataframe(
    folder: Union[str, Path],
    *,
    drop_depot: bool = True,
    recompute_profits: bool = True,
    delivery_profit: float = 2.0,
    pickup_profit: float = 1.0,
    indicador_as_string: bool = True,
    sort_by_replica_and_arrival: bool = False,
) -> pd.DataFrame:
    """
    Convierte una carpeta de .pkl separados por campo a un único DataFrame.

    Parámetros clave:
    - folder: carpeta que contiene los scen_*.pkl de UNA instancia.
    - drop_depot: elimina el primer nodo de cada replica si parece ser el depot.
    - recompute_profits: ignora scen_profits_sample.pkl y calcula profits desde indicador.
    - indicador_as_string: deja indicador como "True"/"False", igual al CSV sampleado.
    """
    folder = Path(folder)
    if not folder.exists():
        raise FileNotFoundError(f"No existe la carpeta: {folder}")

    raw = load_raw_pkl_fields(folder)
    validate_raw_fields(raw, folder=folder)

    n_replicas = len(raw["arrivals"])
    rows: List[pd.DataFrame] = []

    for replica_id in range(n_replicas):
        arr = _as_1d_array(raw["arrivals"][replica_id], field="arrivals", replica_id=replica_id)
        dead = _as_1d_array(raw["deadlines"][replica_id], field="deadlines", replica_id=replica_id)
        ind = _as_1d_array(raw["indicador"][replica_id], field="indicador", replica_id=replica_id)
        pts = _as_points_array(raw["points"][replica_id], replica_id=replica_id)
        pft = _as_1d_array(raw["profits"][replica_id], field="profits", replica_id=replica_id)
        ready = _as_1d_array(raw["ready_times"][replica_id], field="ready_times", replica_id=replica_id)
        service = _as_1d_array(raw["service_times"][replica_id], field="service_times", replica_id=replica_id)

        lengths = {
            "arrivals": len(arr),
            "deadlines": len(dead),
            "indicador": len(ind),
            "points": len(pts),
            "profits": len(pft),
            "ready_times": len(ready),
            "service_times": len(service),
        }
        if len(set(lengths.values())) != 1:
            raise ValueError(
                f"Largos inconsistentes en {folder}, replica {replica_id}: {lengths}"
            )

        keep_mask = np.ones(len(arr), dtype=bool)
        if drop_depot and len(arr) > 0 and _looks_like_depot_row(
            arrival=arr[0],
            deadline=dead[0],
            indicador=ind[0],
            point=pts[0],
            profit=pft[0],
            ready=ready[0],
            service=service[0],
        ):
            keep_mask[0] = False

        arr = arr[keep_mask]
        dead = dead[keep_mask]
        ind = ind[keep_mask]
        pts = pts[keep_mask]
        pft = pft[keep_mask]
        ready = ready[keep_mask]
        service = service[keep_mask]

        if recompute_profits:
            pft = np.array(
                [delivery_profit if is_delivery_flag(v) else pickup_profit for v in ind],
                dtype=float,
            )

        if indicador_as_string:
            ind_out = np.array(["False" if is_delivery_flag(v) else "True" for v in ind])
        else:
            # Mantiene el tipo original lo más posible.
            ind_out = ind

        replica_df = pd.DataFrame(
            {
                "replica": replica_id,
                "arrivals": arr.astype(float),
                "deadlines": dead.astype(float),
                "indicador": ind_out,
                "x": pts[:, 0].astype(float),
                "y": pts[:, 1].astype(float),
                "profits": pft.astype(float),
                "ready_times": ready.astype(float),
                "service_times": service.astype(float),
            }
        )
        rows.append(replica_df)

    if not rows:
        return pd.DataFrame(
            columns=[
                "replica",
                "arrivals",
                "deadlines",
                "indicador",
                "x",
                "y",
                "profits",
                "ready_times",
                "service_times",
            ]
        )

    df = pd.concat(rows, ignore_index=True)

    if sort_by_replica_and_arrival:
        df = df.sort_values(["replica", "arrivals"]).reset_index(drop=True)

    return df


def load_raw_pkl_fields(folder: Union[str, Path]) -> Dict[str, Any]:
    """
    Carga los 7 archivos .pkl de una carpeta.

    Acepta nombres como:
    - scen_arrivals_sample.pkl
    - scen_arrivals_sample(1).pkl
    - scen_arrivals.pkl
    - cualquier archivo que contenga 'arrivals' y termine en .pkl
    """
    folder = Path(folder)
    raw: Dict[str, Any] = {}

    for field in FIELDS:
        path = find_field_pickle(folder, field)
        with path.open("rb") as f:
            raw[field] = pickle.load(f)

    return raw


def find_field_pickle(folder: Union[str, Path], field: str) -> Path:
    folder = Path(folder)

    patterns = [
        f"scen_{field}_sample.pkl",
        f"scen_{field}_sample*.pkl",
        f"scen_{field}.pkl",
        f"*{field}*.pkl",
    ]

    candidates: List[Path] = []
    for pattern in patterns:
        candidates.extend(sorted(folder.glob(pattern)))
        if candidates:
            break

    # Elimina duplicados conservando orden.
    unique_candidates: List[Path] = []
    seen = set()
    for p in candidates:
        if p not in seen:
            seen.add(p)
            unique_candidates.append(p)

    if not unique_candidates:
        raise FileNotFoundError(
            f"No encontré archivo .pkl para campo '{field}' en carpeta {folder}"
        )

    if len(unique_candidates) > 1:
        names = [p.name for p in unique_candidates]
        raise ValueError(
            f"Encontré más de un .pkl para campo '{field}' en {folder}: {names}. "
            "Deja solo uno o usa nombres no ambiguos."
        )

    return unique_candidates[0]


def validate_raw_fields(raw: Dict[str, Any], *, folder: Union[str, Path]) -> None:
    missing = [field for field in FIELDS if field not in raw]
    if missing:
        raise KeyError(f"Faltan campos en {folder}: {missing}")

    replica_counts = {}
    for field in FIELDS:
        try:
            replica_counts[field] = len(raw[field])
        except TypeError as exc:
            raise TypeError(
                f"El campo {field} en {folder} no parece ser una lista de replicas."
            ) from exc

    if len(set(replica_counts.values())) != 1:
        raise ValueError(
            f"Los campos no tienen la misma cantidad de replicas en {folder}: {replica_counts}"
        )


def parse_instance_id(value: Union[int, str]) -> int:
    if isinstance(value, int):
        if value not in ROMAN_BY_INSTANCE:
            raise ValueError("La instancia debe estar entre 1 y 4.")
        return value

    text = str(value).strip().upper()
    if text.isdigit():
        return parse_instance_id(int(text))

    if text in INSTANCE_BY_ROMAN:
        return INSTANCE_BY_ROMAN[text]

    raise ValueError("La instancia debe ser 1, 2, 3, 4 o I, II, III, IV.")


def is_delivery_flag(value: Any) -> bool:
    """
    En estos datos:
        False / "False" -> delivery
        True  / "True"  -> pickup
    """
    if isinstance(value, (bool, np.bool_)):
        return bool(value) is False

    text = str(value).strip().lower()
    if text == "false":
        return True
    if text == "true":
        return False

    # Si viene 0/1 numérico, se interpreta igual que booleano:
    # 0 -> False -> delivery, 1 -> True -> pickup.
    if isinstance(value, (int, float, np.integer, np.floating)):
        return int(value) == 0

    raise ValueError(f"No pude interpretar indicador={value!r} como pickup/delivery.")


def _as_1d_array(values: Any, *, field: str, replica_id: int) -> np.ndarray:
    arr = np.asarray(values)
    if arr.ndim != 1:
        raise ValueError(
            f"El campo {field}, replica {replica_id}, debería ser 1D y tiene shape {arr.shape}."
        )
    return arr


def _as_points_array(values: Any, *, replica_id: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError(
            f"points, replica {replica_id}, debería tener shape (n, 2) y tiene {arr.shape}."
        )
    return arr


def _looks_like_depot_row(
    *,
    arrival: Any,
    deadline: Any,
    indicador: Any,
    point: Sequence[float],
    profit: Any,
    ready: Any,
    service: Any,
) -> bool:
    """
    Detecta la fila depot típica de estos .pkl:
        point = (10000, 10000), profit = 0, service = 0.

    No exige arrival/deadline exactos para hacerlo robusto.
    """
    try:
        x, y = float(point[0]), float(point[1])
        p = float(profit)
        s = float(service)
    except Exception:
        return False

    return (
        abs(x - 10000.0) <= 1e-6
        and abs(y - 10000.0) <= 1e-6
        and abs(p) <= 1e-9
        and abs(s) <= 1e-9
    )


def save_dataframes(
    dataframes: Dict[int, pd.DataFrame],
    output_dir: Union[str, Path] = "processed_data",
    *,
    save_csv: bool = True,
    save_pkl: bool = False,
    prefix: str = "Instancia_Tipo",
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for instance_num, df in dataframes.items():
        roman = ROMAN_BY_INSTANCE[instance_num]
        base_name = f"{prefix}_{instance_num}_{roman}"

        if save_csv:
            csv_path = output_dir / f"{base_name}.csv"
            df.to_csv(csv_path, index=False)
            print(f"CSV guardado: {csv_path} | filas={len(df):,}")

        if save_pkl:
            pkl_path = output_dir / f"{base_name}.pkl"
            df.to_pickle(pkl_path)
            print(f"PKL guardado: {pkl_path} | filas={len(df):,}")



def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convierte carpetas de .pkl RICAS a DataFrames/CSV tipo benchmark."
    )
    parser.add_argument("--base-dir", type=str, default="data")
    parser.add_argument("--out-dir", type=str, default="processed_data")
    parser.add_argument(
        "--instances",
        type=str,
        default="1,2,3,4",
        help="Instancias a cargar. Ej: 1,2,3,4 o I,II,III,IV",
    )
    parser.add_argument(
        "--keep-depot",
        action="store_true",
        help="No elimina la primera fila depot de cada replica.",
    )
    parser.add_argument(
        "--use-pkl-profits",
        action="store_true",
        help="Usa profits del archivo .pkl en vez de recalcularlos desde indicador.",
    )
    parser.add_argument("--delivery-profit", type=float, default=2.0)
    parser.add_argument("--pickup-profit", type=float, default=1.0)
    parser.add_argument(
        "--indicator-bool",
        action="store_true",
        help="Mantiene indicador como booleano. Por defecto lo exporta como strings True/False, igual al CSV sampleado.",
    )
    parser.add_argument("--sort", action="store_true", help="Ordena por replica y arrivals.")
    parser.add_argument("--save-csv", action="store_true", help="Guarda CSVs.")
    parser.add_argument("--save-pkl", action="store_true", help="Guarda DataFrames como .pkl.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    instances = [x.strip() for x in args.instances.split(",") if x.strip()]

    dfs = load_all_instance_dataframes(
        base_dir=args.base_dir,
        instances=instances,
        drop_depot=not args.keep_depot,
        recompute_profits=not args.use_pkl_profits,
        delivery_profit=args.delivery_profit,
        pickup_profit=args.pickup_profit,
        indicador_as_string=not args.indicator_bool,
        sort_by_replica_and_arrival=args.sort,
    )

    for instance_num, df in dfs.items():
        print("=" * 70)
        print(f"Instancia Tipo {ROMAN_BY_INSTANCE[instance_num]} / {instance_num}")
        print(f"Filas totales: {len(df):,}")
        print("Clientes por replica:")
        print(df["replica"].value_counts().sort_index())
        print("Primeras filas:")
        print(df.head())

    if True or args.save_pkl:
        save_dataframes(
            dfs,
            output_dir='output_dir',
            save_csv=True,
            save_pkl=False,
        )


if __name__ == "__main__":
    main()
