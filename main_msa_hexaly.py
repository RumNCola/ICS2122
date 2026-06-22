from __future__ import annotations

from pathlib import Path
import inspect
import itertools
import json
import multiprocessing as mp
import time
import traceback
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.dynamic.config_dynamic import DynamicMSAConfig
from src.dynamic.data_normalizer import normalize_requests_df
from src.dynamic.dispatcher import MSADynamicDispatcher


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------


# Todas las rutas relativas del script se anclan al directorio donde está este
# archivo. Esto evita que un cambio de working directory dentro del dispatcher,
# Hexaly o multiprocessing rompa los guardados posteriores.
SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_path(path: Path | str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = SCRIPT_DIR / candidate
    return candidate.resolve()


def _save_csv(df: pd.DataFrame, path: Path | str) -> Path:
    """Guarda un CSV creando siempre su carpeta padre."""
    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False)
    return target


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_safe(value: Any) -> Any:
    """Convierte valores complejos a texto para guardarlos sin problemas."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _flatten_run_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_safe(value) for key, value in row.items()}


def _as_dataframe(value: Any) -> pd.DataFrame:
    """Normaliza una salida opcional del dispatcher como DataFrame."""
    if isinstance(value, pd.DataFrame):
        return value
    if value is None:
        return pd.DataFrame()
    try:
        return pd.DataFrame(value)
    except Exception:
        return pd.DataFrame({"value": [str(value)]})


def _load_real_replica(
    *,
    rica: bool,
    instancia: int,
    replica_id: int,
    input_dir: Path | str = Path("data"),
) -> pd.DataFrame:
    """Carga y normaliza la réplica que se ejecutará online."""
    if not rica:
        input_path = Path(input_dir) / f"instancia_tipo_{instancia}.csv"
        if not input_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {input_path}")
        df = pd.read_csv(input_path)
    else:
        from src.ricas_replica_creator import replica

        df, _ = replica(instancia, replicas=max(1, replica_id + 1))

    return normalize_requests_df(df, replica_id=replica_id)


def _build_dynamic_config(
    candidates: dict[str, Any],
) -> tuple[DynamicMSAConfig, list[str], list[str]]:
    """
    Construye DynamicMSAConfig usando únicamente argumentos admitidos.

    Esto permite que el batch funcione con distintas versiones de la clase de
    configuración. Los argumentos no soportados quedan registrados en cada
    corrida mediante ``config_ignored_fields``.
    """
    try:
        signature = inspect.signature(DynamicMSAConfig)
        parameters = signature.parameters
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )

        if accepts_kwargs:
            supported = dict(candidates)
        else:
            supported = {
                key: value for key, value in candidates.items() if key in parameters
            }
    except (TypeError, ValueError):
        # Campos confirmados por el main_msa_hexaly original.
        baseline_fields = {
            "instancia",
            "n_scenarios",
            "lookahead_sec",
            "scenario_time_limit_sec",
            "consensus_mode",
            "seed",
        }
        supported = {
            key: value for key, value in candidates.items() if key in baseline_fields
        }

    applied_fields = sorted(supported)
    ignored_fields = sorted(set(candidates) - set(supported))
    return DynamicMSAConfig(**supported), applied_fields, ignored_fields


# -----------------------------------------------------------------------------
# Una corrida
# -----------------------------------------------------------------------------


def _execute_one(
    *,
    rica: bool = False,
    instancia: int = 1,
    replica_id: int = 0,
    n_scenarios: int = 20,
    lookahead_min: int = 140,
    scenario_time_limit_sec: float = 10.0,
    parallel_backend: str | None = None,
    parallel_max_workers: int | None = None,
    parallel_cpu_reserve: int | None = None,
    parallel_log_progress: bool | None = None,
    dynamic_insertion_n_scenarios: int | None = None,
    enable_dynamic_pickup_insertion: bool | None = None,
    run_msa_on_request_arrival_if_vehicle_waiting: bool | None = None,
    no_improvement_time_sec: int | None = None,
    seed: int | None = 42,
    input_dir: Path | str = Path("data"),
    save_individual_outputs: bool = True,
    output_dir: Path | str = Path("outputs/msa_hexaly/batch_runs"),
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, Any]:
    """Ejecuta una réplica y devuelve resumen, trips, log dinámico y resultado."""
    # Usar rutas absolutas es importante: el dispatcher o una dependencia puede
    # cambiar temporalmente el current working directory durante la corrida.
    output_dir = _resolve_path(output_dir)
    input_dir = _resolve_path(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = _load_real_replica(
        rica=rica,
        instancia=instancia,
        replica_id=replica_id,
        input_dir=input_dir,
    )

    config_candidates: dict[str, Any] = {
        "instancia": instancia,
        "n_scenarios": n_scenarios,
        "lookahead_sec": lookahead_min * 60,
        "scenario_time_limit_sec": scenario_time_limit_sec,
        "consensus_mode": "van_hentenryck",
        "seed": seed,
    }

    # Se agregan sólo cuando fueron configurados explícitamente. Así se
    # conservan los defaults propios del MSA Hexaly actual.
    optional_config = {
        "parallel_backend": parallel_backend,
        "parallel_max_workers": parallel_max_workers,
        "parallel_cpu_reserve": parallel_cpu_reserve,
        "parallel_log_progress": parallel_log_progress,
        "dynamic_insertion_n_scenarios": dynamic_insertion_n_scenarios,
        "enable_dynamic_pickup_insertion": enable_dynamic_pickup_insertion,
        "run_msa_on_request_arrival_if_vehicle_waiting": (
            run_msa_on_request_arrival_if_vehicle_waiting
        ),
        "no_improvement_time_sec": no_improvement_time_sec,
    }
    config_candidates.update(
        {key: value for key, value in optional_config.items() if value is not None}
    )

    cfg, applied_fields, ignored_fields = _build_dynamic_config(config_candidates)

    if ignored_fields:
        print(
            "ADVERTENCIA: DynamicMSAConfig no admite estos parámetros; "
            f"se ignorarán: {ignored_fields}"
        )

    start_dt = datetime.now()
    t0 = time.perf_counter()

    dispatcher = MSADynamicDispatcher(cfg)
    result = dispatcher.run_replica(df)

    elapsed_sec = time.perf_counter() - t0
    end_dt = datetime.now()

    params = {
        "solver": "hexaly",
        "rica": rica,
        "input_dir": str(input_dir),
        "instancia": instancia,
        "replica_id": replica_id,
        "n_scenarios": n_scenarios,
        "lookahead_min": lookahead_min,
        "scenario_time_limit_sec": scenario_time_limit_sec,
        "parallel_backend": parallel_backend,
        "parallel_max_workers": parallel_max_workers,
        "parallel_cpu_reserve": parallel_cpu_reserve,
        "parallel_log_progress": parallel_log_progress,
        "dynamic_insertion_n_scenarios": dynamic_insertion_n_scenarios,
        "enable_dynamic_pickup_insertion": enable_dynamic_pickup_insertion,
        "run_msa_on_request_arrival_if_vehicle_waiting": (
            run_msa_on_request_arrival_if_vehicle_waiting
        ),
        "no_improvement_time_sec": no_improvement_time_sec,
        "seed": seed,
        "config_applied_fields": applied_fields,
        "config_ignored_fields": ignored_fields,
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

    committed_trips = _as_dataframe(getattr(result, "committed_trips", None))
    dynamic_insertion_log = _as_dataframe(
        getattr(result, "dynamic_insertion_log", None)
    )

    if save_individual_outputs:
        # Reforzamos la creación justo antes de escribir por si una dependencia
        # modificó o limpió carpetas durante la ejecución.
        output_dir.mkdir(parents=True, exist_ok=True)
        time_limit_tag = str(scenario_time_limit_sec).replace(".", "p")
        no_improvement_tag = (
            "off"
            if no_improvement_time_sec is None
            else str(no_improvement_time_sec).replace(".", "p")
        )
        run_tag = (
            f"I{instancia}_R{replica_id}_S{n_scenarios}_"
            f"L{lookahead_min}_TL{time_limit_tag}_NI{no_improvement_tag}_SEED{seed}"
        )
        _save_csv(
            committed_trips,
            output_dir / f"trips_{run_tag}.csv",
        )
        _save_csv(
            dynamic_insertion_log,
            output_dir / f"dynamic_insertions_{run_tag}.csv",
        )
        _save_csv(
            pd.DataFrame([row]),
            output_dir / f"summary_{run_tag}.csv",
        )

    return row, committed_trips, dynamic_insertion_log, result


def run_one(
    *,
    rica: bool = False,
    instancia: int = 1,
    replica_id: int = 0,
    n_scenarios: int = 20,
    lookahead_min: int = 140,
    scenario_time_limit_sec: float = 10.0,
    parallel_backend: str | None = None,
    parallel_max_workers: int | None = None,
    parallel_cpu_reserve: int | None = None,
    parallel_log_progress: bool | None = None,
    dynamic_insertion_n_scenarios: int | None = None,
    enable_dynamic_pickup_insertion: bool | None = None,
    run_msa_on_request_arrival_if_vehicle_waiting: bool | None = None,
    no_improvement_time_sec: int | None = None,
    seed: int | None = 42,
    input_dir: Path | str = Path("data"),
    save_individual_outputs: bool = True,
    output_dir: Path | str = Path("outputs/msa_hexaly/batch_runs"),
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Interfaz equivalente a ``run_one`` de main_msa_alns_batch."""
    row, trips, dynamic_log, _ = _execute_one(
        rica=rica,
        instancia=instancia,
        replica_id=replica_id,
        n_scenarios=n_scenarios,
        lookahead_min=lookahead_min,
        scenario_time_limit_sec=scenario_time_limit_sec,
        parallel_backend=parallel_backend,
        parallel_max_workers=parallel_max_workers,
        parallel_cpu_reserve=parallel_cpu_reserve,
        parallel_log_progress=parallel_log_progress,
        dynamic_insertion_n_scenarios=dynamic_insertion_n_scenarios,
        enable_dynamic_pickup_insertion=enable_dynamic_pickup_insertion,
        run_msa_on_request_arrival_if_vehicle_waiting=(
            run_msa_on_request_arrival_if_vehicle_waiting
        ),
        no_improvement_time_sec=no_improvement_time_sec,
        seed=seed,
        input_dir=input_dir,
        save_individual_outputs=save_individual_outputs,
        output_dir=output_dir,
    )
    return row, trips, dynamic_log


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
    rica: bool = False,
    input_dir: Path | str = Path("data"),
    parallel_backend: str | None = None,
    parallel_max_workers_values: list[int | None] | None = None,
    parallel_cpu_reserve: int | None = None,
    parallel_log_progress: bool | None = None,
    dynamic_insertion_n_scenarios_values: list[int | None] | None = None,
    enable_dynamic_pickup_insertion: bool | None = None,
    run_msa_on_request_arrival_if_vehicle_waiting: bool | None = None,
    no_improvement_time_sec: int | None = None,
    seed_values: list[int | None] | None = None,
) -> list[dict[str, Any]]:
    """Construye el producto cartesiano de parámetros del batch."""
    parallel_max_workers_values = parallel_max_workers_values or [None]
    dynamic_insertion_n_scenarios_values = (
        dynamic_insertion_n_scenarios_values or [None]
    )
    seed_values = seed_values or [42]

    experiments: list[dict[str, Any]] = []
    for (
        instancia,
        replica_id,
        n_scenarios,
        lookahead_min,
        scenario_time_limit_sec,
        no_improvement_time_sec,
        parallel_max_workers,
        dynamic_insertion_n_scenarios,
        seed,
    ) in itertools.product(
        instancias,
        list(replicas),
        n_scenarios_values,
        lookahead_min_values,
        scenario_time_limit_values,
        [no_improvement_time_sec] if no_improvement_time_sec is not None else [5],
        parallel_max_workers_values,
        dynamic_insertion_n_scenarios_values,
        seed_values,
    ):
        experiments.append(
            {
                "rica": rica,
                "input_dir": str(input_dir),
                "instancia": instancia,
                "replica_id": replica_id,
                "n_scenarios": n_scenarios,
                "lookahead_min": lookahead_min,
                "scenario_time_limit_sec": scenario_time_limit_sec,
                "no_improvement_time_sec": no_improvement_time_sec,
                "parallel_backend": parallel_backend,
                "parallel_max_workers": parallel_max_workers,
                "parallel_cpu_reserve": parallel_cpu_reserve,
                "parallel_log_progress": parallel_log_progress,
                "dynamic_insertion_n_scenarios": (
                    dynamic_insertion_n_scenarios
                ),
                "enable_dynamic_pickup_insertion": (
                    enable_dynamic_pickup_insertion
                ),
                "run_msa_on_request_arrival_if_vehicle_waiting": (
                    run_msa_on_request_arrival_if_vehicle_waiting
                ),
                "seed": seed,
            }
        )

    return experiments


# -----------------------------------------------------------------------------
# Resumen Excel: mismas métricas y hojas que main_msa_alns_batch
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

    metrics = [metric for metric in DEFAULT_NUMERIC_METRICS if metric in runs_df]
    for metric in metrics:
        runs_df[metric] = pd.to_numeric(runs_df[metric], errors="coerce")

    valid_group_cols = [column for column in group_cols if column in runs_df]

    if not metrics:
        if not valid_group_cols:
            return pd.DataFrame({"_all": ["all"], "run_count": [len(runs_df)]})
        return (
            runs_df.groupby(valid_group_cols, dropna=False)
            .size()
            .reset_index(name="run_count")
        )

    if not valid_group_cols:
        grouped = runs_df.assign(_all="all").groupby("_all", dropna=False)
    else:
        grouped = runs_df.groupby(valid_group_cols, dropna=False)

    agg = grouped[metrics].agg(["count", "mean", "std", "min", "max"]).reset_index()
    agg.columns = [
        "_".join(str(part) for part in column if str(part))
        for column in agg.columns.to_flat_index()
    ]

    # Error estándar: SE = std / sqrt(n).
    for metric in metrics:
        count_col = f"{metric}_count"
        std_col = f"{metric}_std"
        if count_col in agg and std_col in agg:
            agg[f"{metric}_se"] = agg[std_col] / np.sqrt(
                agg[count_col].replace(0, np.nan)
            )

    return agg


def save_excel_summary(
    *,
    runs_df: pd.DataFrame,
    errors_df: pd.DataFrame,
    experiments_df: pd.DataFrame,
    excel_path: Path,
) -> None:
    """Guarda las mismas seis hojas producidas por main_msa_alns_batch."""
    excel_path.parent.mkdir(parents=True, exist_ok=True)

    group_config = [
        "instancia",
        "rica",
        "n_scenarios",
        "lookahead_min",
        "scenario_time_limit_sec",
        "parallel_backend",
        "parallel_max_workers",
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
        experiments_df.to_excel(
            writer, sheet_name="planned_experiments", index=False
        )
        errors_df.to_excel(writer, sheet_name="errors", index=False)


# -----------------------------------------------------------------------------
# Batch principal
# -----------------------------------------------------------------------------


def run_batch(
    experiments: list[dict[str, Any]],
    *,
    batch_name: str | None = None,
    output_root: Path | str = Path("outputs/msa_hexaly/batch"),
    save_individual_outputs: bool = True,
    stop_on_error: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    """Ejecuta secuencialmente la grilla y guarda CSV incrementales y Excel."""
    batch_name = batch_name or f"batch_{_now_stamp()}"
    # Se resuelve una sola vez, antes de ejecutar el dispatcher. Desde aquí en
    # adelante todas las rutas del batch son absolutas.
    output_root = _resolve_path(output_root)
    batch_dir = output_root / batch_name
    individual_runs_dir = batch_dir / "individual_runs"
    batch_dir.mkdir(parents=True, exist_ok=True)
    individual_runs_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    print(f"Batch: {batch_name}")
    print(f"Total corridas programadas: {len(experiments)}")
    print(f"Salida: {batch_dir}")

    for idx, params in enumerate(experiments, start=1):
        # Garantiza que las carpetas sigan existiendo incluso si una dependencia
        # cambió el working directory o realizó limpieza temporal.
        batch_dir.mkdir(parents=True, exist_ok=True)
        individual_runs_dir.mkdir(parents=True, exist_ok=True)

        print("-" * 90)
        print(f"Corrida {idx}/{len(experiments)} | params={params}")

        try:
            row, _, _ = run_one(
                **params,
                save_individual_outputs=save_individual_outputs,
                output_dir=individual_runs_dir,
            )
            row = {"run_id": idx, **row}
            rows.append(row)

            elapsed_min = pd.to_numeric(
                pd.Series([row.get("elapsed_total_min")]), errors="coerce"
            ).iloc[0]
            elapsed_text = (
                f"{elapsed_min:.2f}" if pd.notna(elapsed_min) else "n/a"
            )
            print(
                f"OK corrida {idx}: "
                f"profit_rate={row.get('profit_rate')}, "
                f"profit={row.get('total_profit')}, "
                f"elapsed_min={elapsed_text}"
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

        # Guardado incremental por seguridad, igual que en el batch ALNS.
        _save_csv(
            pd.DataFrame(rows),
            batch_dir / "runs_detail_partial.csv",
        )
        _save_csv(
            pd.DataFrame(errors),
            batch_dir / "errors_partial.csv",
        )

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

    _save_csv(runs_df, batch_dir / "runs_detail.csv")
    _save_csv(errors_df, batch_dir / "errors.csv")
    _save_csv(experiments_df, batch_dir / "planned_experiments.csv")

    print("=" * 90)
    print(f"Batch terminado. Corridas OK: {len(runs_df)} | errores: {len(errors_df)}")
    print(f"Excel resumen guardado en: {excel_path}")

    return runs_df, errors_df, excel_path


# -----------------------------------------------------------------------------
# Compatibilidad con el main anterior
# -----------------------------------------------------------------------------


def main(
    rica: bool,
    instancia: int = 1,
    replica_id: int = 0,
    n_scenarios: int = 20,
    lookahead_min: int = 140,
    scenario_time_limit_sec: float = 10.0,
    seed: int | None = 42,
):
    """Ejecuta una sola corrida y conserva el retorno ``result`` anterior."""
    row, _, _, result = _execute_one(
        rica=rica,
        instancia=instancia,
        replica_id=replica_id,
        n_scenarios=n_scenarios,
        lookahead_min=lookahead_min,
        scenario_time_limit_sec=scenario_time_limit_sec,
        seed=seed,
        save_individual_outputs=True,
        output_dir=Path("outputs/msa_hexaly"),
    )
    print(row)
    return result


if __name__ == "__main__":
    # Recomendado en Windows si la implementación interna usa multiprocessing.
    mp.freeze_support()

    # Esta grilla reproduce el antiguo loop de réplicas, pero ahora genera un
    # batch consolidado con métricas individuales y agregadas en Excel.
    # EXPERIMENTS = build_experiment_grid(
    #     instancias=[1],
    #     replicas=range(2, 100, 9),
    #     n_scenarios_values=[20],
    #     lookahead_min_values=[160],
    #     scenario_time_limit_values=[40.0],
    #     rica=False,
    #     input_dir=Path("data"),
    #     seed_values=[42],
    # )

    # run_batch(
    #     EXPERIMENTS,
    #     batch_name=None,
    #     save_individual_outputs=True,
    #     stop_on_error=False,
    # )
    # EXPERIMENTS = build_experiment_grid(
    #     instancias=[2],
    #     replicas=range(2, 100, 9),
    #     n_scenarios_values=[20],
    #     lookahead_min_values=[160],
    #     scenario_time_limit_values=[40.0],
    #     rica=False,
    #     input_dir=Path("data"),
    #     seed_values=[42],
    # )

    # run_batch(
    #     EXPERIMENTS,
    #     batch_name=None,
    #     save_individual_outputs=True,
    #     stop_on_error=False,
    # )
    # EXPERIMENTS = build_experiment_grid(
    #     instancias=[3],
    #     replicas=range(2, 100, 90),
    #     n_scenarios_values=[20],
    #     lookahead_min_values=[160],
    #     scenario_time_limit_values=[40.0],
    #     rica=False,
    #     input_dir=Path("data"),
    #     seed_values=[42],
    # )

    # run_batch(
    #     EXPERIMENTS,
    #     batch_name=None,
    #     save_individual_outputs=True,
    #     stop_on_error=False,
    # )
    EXPERIMENTS = build_experiment_grid(
        instancias=[3],
        replicas=range(0,20),
        n_scenarios_values=[20],
        lookahead_min_values=[160],
        scenario_time_limit_values=[40.0],
        no_improvement_time_sec=5,
        rica=False,
        input_dir=Path("data"),
        seed_values=[42],
    )

    run_batch(
        EXPERIMENTS,
        batch_name=None,
        save_individual_outputs=True,
        stop_on_error=False,
    )
    EXPERIMENTS = build_experiment_grid(
        instancias=[2],
        replicas=range(0,20),
        n_scenarios_values=[20],
        lookahead_min_values=[160],
        scenario_time_limit_values=[30.0],
        no_improvement_time_sec=5,
        rica=False,
        input_dir=Path("data"),
        seed_values=[42],
    )

    run_batch(
        EXPERIMENTS,
        batch_name=None,
        save_individual_outputs=True,
        stop_on_error=False,
    )

# Instancia 1
# NUMERO DE ESCENARIOS
#n_scenarios=50, lookahead_min=140 scenario_time_limit_Sec=6 entrega 45,5% de retorno
#n_scenarios=30, lookahead_min=140 scenario_time_limit_Sec=6 entrega 43% de retorno
#n_scenarios=25, lookahead_min=140 scenario_time_limit_Sec=6 entrega 42,5% de retorno
#n_scenarios=20, lookahead_min=140 scenario_time_limit_Sec=6 entrega 56% de retorno
######################
# Con tiempo adaptativo de resolucion en el peak y la ultima media hora
#n_scenarios=20, lookahead_min=140 scenario_time_limit_Sec=6 entrega 61% de retorno 
######################
#n_scenarios=18, lookahead_min=140 scenario_time_limit_Sec=6 entrega 42% de retorno
#n_scenarios=15, lookahead_min=140 scenario_time_limit_Sec=6 entrega 43% de retorno
#n_scenarios=15, lookahead_min=140 scenario_time_limit_Sec=6 entrega 43% de retorno
#n_scenarios=10, lookahead_min=140 scenario_time_limit_Sec=6 entrega 38% de retorno
 
# Conclusión: 20 escenarios es el número ideal

# LOOKAHEAD_MIN
#n_scenarios=20, lookahead_min=160 scenario_time_limit_Sec=8 entrega 54% de retorno
#n_scenarios=20, lookahead_min=150 scenario_time_limit_Sec=8 entrega 43% de retorno
#n_scenarios=20, lookahead_min=140 scenario_time_limit_Sec=8 entrega 61% de retorno
#n_scenarios=20, lookahead_min=130 scenario_time_limit_Sec=8 entrega % de retorno
#n_scenarios=30, lookahead_min=140 scenario_time_limit_Sec=10 entrega % de retorno

#Mas escenarios, Mas Lookahead, Mas tiempo!
#n_scenarios=50, lookahead_min=160 scenario_time_limit_Sec=15 entrega 65,5% de retorno
#n_scenarios=30, lookahead_min=160 scenario_time_limit_Sec=10 entrega 62% de retorno