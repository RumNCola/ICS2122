#!/usr/bin/env python3
"""Agrupa corridas CSV y grafica el profit devengado acumulado promedio.

Criterio por defecto para los archivos trips_*.csv:
- El profit de un viaje se reconoce en `return_to_depot_time`.
- No se reconoce al salir del depósito.

Si se dispone de un archivo a nivel de pedido, puede usarse el mismo script
indicando las columnas exactas, por ejemplo:
    --time-column service_completion_time --profit-column customer_profit
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, stdev
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


@dataclass
class RunSeries:
    path: Path
    group: str
    event_times: list[float]
    cumulative_profit: list[float]
    first_start_time: float
    last_event_time: float
    row_count: int

    @property
    def final_profit(self) -> float:
        return self.cumulative_profit[-1] if self.cumulative_profit else 0.0

    def value_at(self, time_seconds: float) -> float:
        """Profit acumulado reconocido hasta time_seconds, inclusive."""
        idx = bisect_right(self.event_times, time_seconds) - 1
        return self.cumulative_profit[idx] if idx >= 0 else 0.0


def parse_number(value: str | None, *, field: str, file: Path, line: int) -> float:
    if value is None or not value.strip():
        raise ValueError(f"{file.name}, línea {line}: valor vacío en '{field}'.")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"{file.name}, línea {line}: '{value}' no es numérico en '{field}'."
        ) from exc


def infer_group(path: Path, mode: str) -> str:
    """Agrupa por configuración, eliminando tokens de réplica y semilla."""
    if mode == "all":
        return "todas_las_corridas"

    tokens = path.stem.split("_")
    kept: list[str] = []
    for token in tokens:
        if token.lower() == "trips":
            continue
        if re.fullmatch(r"R\d+", token, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"SEED[-+]?\d+", token, flags=re.IGNORECASE):
            continue
        kept.append(token)
    return "_".join(kept) or "sin_configuracion"


def read_run(
    path: Path,
    *,
    group_mode: str,
    time_column: str,
    profit_column: str,
    start_column: str,
) -> RunSeries:
    event_profit: dict[float, float] = defaultdict(float)
    start_times: list[float] = []
    row_count = 0

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path.name}: el CSV no tiene encabezado.")

        required = {time_column, profit_column}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise ValueError(
                f"{path.name}: faltan columnas requeridas: {sorted(missing)}. "
                f"Columnas disponibles: {reader.fieldnames}"
            )

        for line_number, row in enumerate(reader, start=2):
            # Ignora líneas completamente vacías.
            if not any((value or "").strip() for value in row.values()):
                continue

            recognition_time = parse_number(
                row.get(time_column), field=time_column, file=path, line=line_number
            )
            profit = parse_number(
                row.get(profit_column), field=profit_column, file=path, line=line_number
            )
            if not math.isfinite(recognition_time) or not math.isfinite(profit):
                raise ValueError(
                    f"{path.name}, línea {line_number}: tiempo/profit no finito."
                )

            event_profit[recognition_time] += profit
            row_count += 1

            raw_start = row.get(start_column)
            if raw_start is not None and raw_start.strip():
                start_times.append(
                    parse_number(
                        raw_start, field=start_column, file=path, line=line_number
                    )
                )

    times = sorted(event_profit)
    cumulative: list[float] = []
    running = 0.0
    for event_time in times:
        running += event_profit[event_time]
        cumulative.append(running)

    if times:
        first_start = min(start_times) if start_times else times[0]
        last_event = times[-1]
    else:
        first_start = min(start_times) if start_times else 0.0
        last_event = first_start

    return RunSeries(
        path=path,
        group=infer_group(path, group_mode),
        event_times=times,
        cumulative_profit=cumulative,
        first_start_time=first_start,
        last_event_time=last_event,
        row_count=row_count,
    )


def make_time_grid(runs: list[RunSeries], grid_seconds: float) -> list[float]:
    start = min(run.first_start_time for run in runs)
    end = max(run.last_event_time for run in runs)

    if grid_seconds > 0:
        start = math.floor(start / grid_seconds) * grid_seconds
        end = math.ceil(end / grid_seconds) * grid_seconds
        count = int(round((end - start) / grid_seconds))
        return [start + i * grid_seconds for i in range(count + 1)]

    # Grid exacta: la media solo puede cambiar cuando alguna corrida reconoce profit.
    points = {start, end}
    for run in runs:
        points.update(run.event_times)
    return sorted(points)


def format_hhmmss(seconds: float) -> str:
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    whole = int(round(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{secs:02d}"


def aggregate_group(
    group: str, runs: list[RunSeries], grid_seconds: float
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    time_grid = make_time_grid(runs, grid_seconds)
    n = len(runs)

    for t in time_grid:
        values = [run.value_at(t) for run in runs]
        mean = fmean(values)
        sd = stdev(values) if n > 1 else 0.0
        margin = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
        rows.append(
            {
                "group": group,
                "time_seconds": t,
                "time_hhmmss": format_hhmmss(t),
                "n_runs": n,
                "mean_cumulative_accrued_profit": mean,
                "std_cumulative_accrued_profit": sd,
                "ci95_lower": mean - margin,
                "ci95_upper": mean + margin,
                "min_cumulative_accrued_profit": min(values),
                "max_cumulative_accrued_profit": max(values),
            }
        )
    return rows


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_groups(
    aggregated: dict[str, list[dict[str, float | int | str]]], output_path: Path
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for group, rows in sorted(aggregated.items()):
        times = [float(row["time_seconds"]) for row in rows]
        means = [float(row["mean_cumulative_accrued_profit"]) for row in rows]
        lower = [float(row["ci95_lower"]) for row in rows]
        upper = [float(row["ci95_upper"]) for row in rows]
        n_runs = int(rows[0]["n_runs"]) if rows else 0

        label = f"{group} (n={n_runs})"
        line = ax.step(times, means, where="post", linewidth=2, label=label)
        if n_runs > 1:
            ax.fill_between(
                times,
                lower,
                upper,
                step="post",
                alpha=0.18,
                color=line[0].get_color(),
            )

    ax.set_title("Profit devengado acumulado promedio en el tiempo")
    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Profit devengado acumulado promedio")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: format_hhmmss(x)[:5]))
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Agrupa CSV de corridas, calcula el profit devengado acumulado "
            "promedio y genera CSV + gráfico."
        )
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=".",
        help="Carpeta que contiene los CSV (default: carpeta actual).",
    )
    parser.add_argument(
        "--pattern",
        default="trips_*.csv",
        help="Patrón de archivos (default: trips_*.csv).",
    )
    parser.add_argument(
        "--output-dir",
        default="profit_devengado_output",
        help="Carpeta de salida.",
    )
    parser.add_argument(
        "--time-column",
        default="return_to_depot_time",
        help=(
            "Columna que marca cuándo se reconoce el profit. Por defecto se usa "
            "return_to_depot_time porque el archivo actual no tiene timestamps por pedido."
        ),
    )
    parser.add_argument(
        "--profit-column",
        default="total_profit",
        help="Columna de profit a reconocer (default: total_profit).",
    )
    parser.add_argument(
        "--start-column",
        default="departure_time_from_depot",
        help="Columna usada para iniciar el eje temporal antes del primer devengo.",
    )
    parser.add_argument(
        "--group-mode",
        choices=("config", "all"),
        default="config",
        help=(
            "config: separa configuraciones y elimina R#/SEED# del nombre; "
            "all: promedia todos los archivos juntos."
        ),
    )
    parser.add_argument(
        "--grid-seconds",
        type=float,
        default=0.0,
        help=(
            "Resolución temporal fija en segundos. 0 usa la unión exacta de los "
            "instantes de devengo (default: 0)."
        ),
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = input_dir / output_dir

    files = sorted(input_dir.glob(args.pattern))
    if not files:
        raise SystemExit(
            f"No se encontraron archivos en {input_dir} con patrón '{args.pattern}'."
        )

    runs: list[RunSeries] = []
    errors: list[str] = []
    for file in files:
        try:
            runs.append(
                read_run(
                    file,
                    group_mode=args.group_mode,
                    time_column=args.time_column,
                    profit_column=args.profit_column,
                    start_column=args.start_column,
                )
            )
        except Exception as exc:  # Se informan todos los archivos problemáticos juntos.
            errors.append(str(exc))

    if errors:
        joined = "\n- ".join(errors)
        raise SystemExit(f"No se pudo procesar uno o más archivos:\n- {joined}")

    grouped: dict[str, list[RunSeries]] = defaultdict(list)
    for run in runs:
        grouped[run.group].append(run)

    aggregated: dict[str, list[dict[str, float | int | str]]] = {}
    all_aggregate_rows: list[dict[str, float | int | str]] = []
    for group, group_runs in sorted(grouped.items()):
        rows = aggregate_group(group, group_runs, args.grid_seconds)
        aggregated[group] = rows
        all_aggregate_rows.extend(rows)

    aggregate_fields = [
        "group",
        "time_seconds",
        "time_hhmmss",
        "n_runs",
        "mean_cumulative_accrued_profit",
        "std_cumulative_accrued_profit",
        "ci95_lower",
        "ci95_upper",
        "min_cumulative_accrued_profit",
        "max_cumulative_accrued_profit",
    ]
    write_csv(
        output_dir / "profit_promedio_devengado.csv",
        all_aggregate_rows,
        aggregate_fields,
    )

    run_summary_rows = [
        {
            "group": run.group,
            "file": run.path.name,
            "n_rows_or_trips": run.row_count,
            "first_start_time_seconds": run.first_start_time,
            "first_start_time_hhmmss": format_hhmmss(run.first_start_time),
            "last_recognition_time_seconds": run.last_event_time,
            "last_recognition_time_hhmmss": format_hhmmss(run.last_event_time),
            "final_accrued_profit": run.final_profit,
        }
        for run in sorted(runs, key=lambda item: (item.group, item.path.name))
    ]
    write_csv(
        output_dir / "resumen_corridas.csv",
        run_summary_rows,
        [
            "group",
            "file",
            "n_rows_or_trips",
            "first_start_time_seconds",
            "first_start_time_hhmmss",
            "last_recognition_time_seconds",
            "last_recognition_time_hhmmss",
            "final_accrued_profit",
        ],
    )

    plot_groups(aggregated, output_dir / "profit_promedio_devengado.png")

    print(f"Archivos procesados: {len(runs)}")
    for group, group_runs in sorted(grouped.items()):
        final_values = [run.final_profit for run in group_runs]
        print(
            f"- {group}: n={len(group_runs)}, "
            f"profit final promedio={fmean(final_values):.6g}"
        )
    print(f"Resultados guardados en: {output_dir}")


if __name__ == "__main__":
    main()
