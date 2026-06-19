from __future__ import annotations

from pathlib import Path
import itertools
import json
import multiprocessing as mp
import time
import traceback
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.dynamic_alns.config_dynamic import DynamicMSAConfig
from src.dynamic_alns.data_normalizer import normalize_requests_df
from src.dynamic_alns.dispatcher import MSADynamicDispatcherALNS


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_safe(value: Any) -> Any:
    """Convierte listas/dicts/tuplas a texto para que Excel no falle."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _load_real_replica(instancia: int, replica_id: int) -> pd.DataFrame:
    """Carga la replica real que se va a ejecutar online."""
    input_path = Path(f"instancias_de_geyter/instancia_tipo_{instancia}.csv")

    if input_path.exists():
        df = pd.read_csv(input_path)
    else:
        from src.ricas_replica_creator import replica

        df, xlsx_path = replica(instancia, replicas=max(1, replica_id + 1))
        try:
            Path(xlsx_path).unlink(missing_ok=True)
        except Exception:
            pass

    return normalize_requests_df(df, replica_id=replica_id)


def _flatten_run_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _json_safe(v) for k, v in row.items()}


# -----------------------------------------------------------------------------
# Una corrida
# -----------------------------------------------------------------------------


def run_one(
    *,
    instancia: int = 1,
    replica_id: int = 0,
    n_scenarios: int = 25,
    lookahead_min: int = 120,
    scenario_time_limit_sec: float = 15.0,
    parallel_backend: str = "process",
    parallel_max_workers: int | None = None,
    parallel_cpu_reserve: int = 1,
    parallel_log_progress: bool = False,
    alns_max_iterations: int = 20_000,
    dynamic_insertion_n_scenarios: int | None = None,
    run_msa_on_request_arrival_if_vehicle_waiting: bool = True,
    seed: int | None = 42,
    save_individual_outputs: bool = True,
    output_dir: Path | str = Path("outputs/msa_alns/batch_runs"),
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Ejecuta una replica y devuelve fila resumen + trips + log dinamico."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = _load_real_replica(instancia, replica_id)

    cfg = DynamicMSAConfig(
        instancia=instancia,
        n_scenarios=n_scenarios,
        lookahead_sec=lookahead_min * 60,
        scenario_time_limit_sec=scenario_time_limit_sec,
        parallel_backend=parallel_backend,
        parallel_max_workers=parallel_max_workers,
        parallel_cpu_reserve=parallel_cpu_reserve,
        parallel_start_method="spawn",
        parallel_log_progress=parallel_log_progress,
        consensus_mode="van_hentenryck",
        seed=seed,
        alns_max_iterations=alns_max_iterations,
        enable_dynamic_pickup_insertion=True,
        dynamic_insertion_n_scenarios=dynamic_insertion_n_scenarios,
        run_msa_on_request_arrival_if_vehicle_waiting=run_msa_on_request_arrival_if_vehicle_waiting,
    )

    start_dt = datetime.now()
    t0 = time.perf_counter()

    dispatcher = MSADynamicDispatcherALNS(cfg)
    result = dispatcher.run_replica(df)

    elapsed_sec = time.perf_counter() - t0
    end_dt = datetime.now()

    params = {
        "instancia": instancia,
        "replica_id": replica_id,
        "n_scenarios": n_scenarios,
        "lookahead_min": lookahead_min,
        "scenario_time_limit_sec": scenario_time_limit_sec,
        "parallel_backend": parallel_backend,
        "parallel_max_workers": parallel_max_workers,
        "parallel_cpu_reserve": parallel_cpu_reserve,
        "parallel_log_progress": parallel_log_progress,
        "alns_max_iterations": alns_max_iterations,
        "dynamic_insertion_n_scenarios": dynamic_insertion_n_scenarios,
        "run_msa_on_request_arrival_if_vehicle_waiting": run_msa_on_request_arrival_if_vehicle_waiting,
        "seed": seed,
    }

    summary = dict(result.summary)
    summary["service_rate"] = (
        summary.get("served_customers", 0) / summary.get("total_customers", 1)
        if summary.get("total_customers", 0)
        else 0.0
    )

    row = {
        "status": "ok",
        "start_timestamp": start_dt.isoformat(timespec="seconds"),
        "end_timestamp": end_dt.isoformat(timespec="seconds"),
        "elapsed_total_sec": elapsed_sec,
        "elapsed_total_min": elapsed_sec / 60.0,
        **params,
        **summary,
    }
    row = _flatten_run_row(row)

    if save_individual_outputs:
        run_tag = f"I{instancia}_R{replica_id}_S{n_scenarios}_L{lookahead_min}_TL{scenario_time_limit_sec}"
        result.committed_trips.to_csv(output_dir / f"trips_{run_tag}.csv", index=False)
        result.dynamic_insertion_log.to_csv(output_dir / f"dynamic_insertions_{run_tag}.csv", index=False)
        pd.DataFrame([row]).to_csv(output_dir / f"summary_{run_tag}.csv", index=False)

    return row, result.committed_trips, result.dynamic_insertion_log


# -----------------------------------------------------------------------------
# Grilla de experimentos
# -----------------------------------------------------------------------------


def build_experiment_grid(
    *,
    instancias: list[int],
    replicas: list[int] | range,
    n_scenarios_values: list[int],
    lookahead_min_values: list[int],
    scenario_time_limit_values: list[float],
    parallel_backend: str = "process",
    parallel_max_workers_values: list[int | None] | None = None,
    alns_max_iterations_values: list[int] | None = None,
    dynamic_insertion_n_scenarios_values: list[int | None] | None = None,
    seed_values: list[int | None] | None = None,
) -> list[dict[str, Any]]:
    parallel_max_workers_values = parallel_max_workers_values or [None]
    alns_max_iterations_values = alns_max_iterations_values or [20_000]
    dynamic_insertion_n_scenarios_values = dynamic_insertion_n_scenarios_values or [None]
    seed_values = seed_values or [42]

    experiments: list[dict[str, Any]] = []
    for (
        instancia,
        replica_id,
        n_scenarios,
        lookahead_min,
        scenario_time_limit_sec,
        parallel_max_workers,
        alns_max_iterations,
        dynamic_insertion_n_scenarios,
        seed,
    ) in itertools.product(
        instancias,
        list(replicas),
        n_scenarios_values,
        lookahead_min_values,
        scenario_time_limit_values,
        parallel_max_workers_values,
        alns_max_iterations_values,
        dynamic_insertion_n_scenarios_values,
        seed_values,
    ):
        experiments.append(
            {
                "instancia": instancia,
                "replica_id": replica_id,
                "n_scenarios": n_scenarios,
                "lookahead_min": lookahead_min,
                "scenario_time_limit_sec": scenario_time_limit_sec,
                "parallel_backend": parallel_backend,
                "parallel_max_workers": parallel_max_workers,
                "alns_max_iterations": alns_max_iterations,
                "dynamic_insertion_n_scenarios": dynamic_insertion_n_scenarios,
                "seed": seed,
            }
        )
    return experiments


# -----------------------------------------------------------------------------
# Resumen Excel
# -----------------------------------------------------------------------------


DEFAULT_NUMERIC_METRICS = [
    "served_customers",
    "outsourced_customers",
    "total_customers",
    "service_rate",
    "total_profit",
    "total_possible_profit",
    "profit_rate",
    "total_distance_km",
    "nb_trips",
    "dynamic_pickups_inserted",
    "dynamic_pickups_postponed",
    "dynamic_pickups_undecided",
    "msa_calls",
    "msa_scenarios_completed",
    "msa_total_wall_time_sec",
    "msa_avg_wall_time_sec",
    "msa_max_wall_time_sec",
    "parallel_worker_errors",
    "parallel_fallback_tasks",
    "elapsed_total_sec",
    "elapsed_total_min",
]


def aggregate_metrics(runs_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if runs_df.empty:
        return pd.DataFrame()

    metrics = [m for m in DEFAULT_NUMERIC_METRICS if m in runs_df.columns]
    for m in metrics:
        runs_df[m] = pd.to_numeric(runs_df[m], errors="coerce")

    valid_group_cols = [c for c in group_cols if c in runs_df.columns]
    if not valid_group_cols:
        grouped = runs_df.assign(_all="all").groupby("_all", dropna=False)
    else:
        grouped = runs_df.groupby(valid_group_cols, dropna=False)

    agg = grouped[metrics].agg(["count", "mean", "std", "min", "max"]).reset_index()
    agg.columns = ["_".join([str(x) for x in col if str(x)]) for col in agg.columns.to_flat_index()]

    # Agregar SE = std/sqrt(n) para cada metrica.
    for m in metrics:
        count_col = f"{m}_count"
        std_col = f"{m}_std"
        if count_col in agg.columns and std_col in agg.columns:
            agg[f"{m}_se"] = agg[std_col] / np.sqrt(agg[count_col].replace(0, np.nan))

    return agg


def save_excel_summary(
    *,
    runs_df: pd.DataFrame,
    errors_df: pd.DataFrame,
    experiments_df: pd.DataFrame,
    excel_path: Path,
) -> None:
    excel_path.parent.mkdir(parents=True, exist_ok=True)

    group_config = [
        "instancia",
        "n_scenarios",
        "lookahead_min",
        "scenario_time_limit_sec",
        "parallel_backend",
        "parallel_max_workers",
        "alns_max_iterations",
        "dynamic_insertion_n_scenarios",
    ]

    by_config = aggregate_metrics(runs_df.copy(), group_config)
    by_instance = aggregate_metrics(runs_df.copy(), ["instancia"])
    overall = aggregate_metrics(runs_df.copy(), [])

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        runs_df.to_excel(writer, sheet_name="runs_detail", index=False)
        by_config.to_excel(writer, sheet_name="summary_by_config", index=False)
        by_instance.to_excel(writer, sheet_name="summary_by_instance", index=False)
        overall.to_excel(writer, sheet_name="summary_overall", index=False)
        experiments_df.to_excel(writer, sheet_name="planned_experiments", index=False)
        errors_df.to_excel(writer, sheet_name="errors", index=False)


# -----------------------------------------------------------------------------
# Batch principal
# -----------------------------------------------------------------------------


def run_batch(
    experiments: list[dict[str, Any]],
    *,
    batch_name: str | None = None,
    output_root: Path | str = Path("outputs/msa_alns/batch"),
    save_individual_outputs: bool = True,
    stop_on_error: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    batch_name = batch_name or f"batch_{_now_stamp()}"
    output_root = Path(output_root)
    batch_dir = output_root / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    print(f"Batch: {batch_name}")
    print(f"Total corridas programadas: {len(experiments)}")
    print(f"Salida: {batch_dir}")

    for idx, params in enumerate(experiments, start=1):
        print("-" * 90)
        print(f"Corrida {idx}/{len(experiments)} | params={params}")

        try:
            row, _, _ = run_one(
                **params,
                save_individual_outputs=save_individual_outputs,
                output_dir=batch_dir / "individual_runs",
            )
            row["run_id"] = idx
            rows.append(row)
            print(
                f"OK corrida {idx}: "
                f"profit_rate={row.get('profit_rate')}, "
                f"profit={row.get('total_profit')}, "
                f"elapsed_min={row.get('elapsed_total_min'):.2f}"
            )
        except Exception as exc:
            err = {
                "run_id": idx,
                "status": "error",
                **params,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            }
            errors.append(_flatten_run_row(err))
            print(f"ERROR corrida {idx}: {type(exc).__name__}: {exc}")
            if stop_on_error:
                break

        # Guardado incremental por seguridad.
        runs_df_partial = pd.DataFrame(rows)
        errors_df_partial = pd.DataFrame(errors)
        runs_df_partial.to_csv(batch_dir / "runs_detail_partial.csv", index=False)
        errors_df_partial.to_csv(batch_dir / "errors_partial.csv", index=False)

    runs_df = pd.DataFrame(rows)
    errors_df = pd.DataFrame(errors)
    experiments_df = pd.DataFrame(experiments)

    excel_path = batch_dir / f"summary_{batch_name}.xlsx"
    save_excel_summary(
        runs_df=runs_df,
        errors_df=errors_df,
        experiments_df=experiments_df,
        excel_path=excel_path,
    )

    runs_df.to_csv(batch_dir / "runs_detail.csv", index=False)
    errors_df.to_csv(batch_dir / "errors.csv", index=False)
    experiments_df.to_csv(batch_dir / "planned_experiments.csv", index=False)

    print("=" * 90)
    print(f"Batch terminado. Corridas OK: {len(runs_df)} | errores: {len(errors_df)}")
    print(f"Excel resumen guardado en: {excel_path}")

    return runs_df, errors_df, excel_path


if __name__ == "__main__":
    # Obligatorio/recomendado en Windows cuando se usa multiprocessing.
    mp.freeze_support()

    # Ajusta esta grilla segun el tiempo disponible.
    # Ejemplo chico para validar que todo corre:
    #Evolución del lookahead todo lo demas constante
    EXPERIMENTS = build_experiment_grid(
        instancias=[1],
        replicas=range(0,100,20),
        n_scenarios_values=[30],
        lookahead_min_values=[120, 130, 140, 150, 160],
        scenario_time_limit_values=[1.0],
        parallel_backend="process",
        parallel_max_workers_values=[16],
        alns_max_iterations_values=[10_000],
        dynamic_insertion_n_scenarios_values=[5],
        seed_values=[42],
    )
    run_batch(
        EXPERIMENTS,
        batch_name=None,
        save_individual_outputs=True,
        stop_on_error=False,
    )

    #Evolución del n_scenarios todo lo demas constante
    EXPERIMENTS = build_experiment_grid(
        instancias=[1],
        replicas=range(0, 100, 10),
        n_scenarios_values=[15, 20, 30, 40, 50, 60],
        lookahead_min_values=[140],
        scenario_time_limit_values=[15.0],
        parallel_backend="process",
        parallel_max_workers_values=[16],
        alns_max_iterations_values=[10_000],
        dynamic_insertion_n_scenarios_values=[5],
        seed_values=[42],
    )

    run_batch(
        EXPERIMENTS,
        batch_name=None,
        save_individual_outputs=True,
        stop_on_error=False,
    )
    #Evolución del time_limit todo lo demas constante
    EXPERIMENTS = build_experiment_grid(
        instancias=[1],
        replicas=range(0, 100, 20),
        n_scenarios_values=[20],
        lookahead_min_values=[140],
        scenario_time_limit_values=[15, 25, 35, 60, 120, 200],
        parallel_backend="process",
        parallel_max_workers_values=[16],
        alns_max_iterations_values=[20_000],
        dynamic_insertion_n_scenarios_values=[5],
        seed_values=[42],
    )

    run_batch(
        EXPERIMENTS,
        batch_name=None,
        save_individual_outputs=True,
        stop_on_error=False,
    )
    #Toda la carne a la parrilla
    EXPERIMENTS = build_experiment_grid(
        instancias=[1, 2, 3, 4],
        replicas=range(0, 100, 20),
        n_scenarios_values=[50],
        lookahead_min_values=[140],
        scenario_time_limit_values=[200],
        parallel_backend="process",
        parallel_max_workers_values=[16],
        alns_max_iterations_values=[20_000],
        dynamic_insertion_n_scenarios_values=[5],
        seed_values=[42],
    )

    run_batch(
        EXPERIMENTS,
        batch_name=None,
        save_individual_outputs=True,
        stop_on_error=False,
    )
