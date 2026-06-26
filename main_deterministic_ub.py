from pathlib import Path

from src.deterministic_bound import VRPTWConfig, solve_vrptw_hexaly
from src.ricas_replica_creator import replica
import numpy as np
import pandas as pd


def _metric_summary_table(df: pd.DataFrame, metrics: list[str], confidence: float = 0.95) -> pd.DataFrame:
    """
    Construye una tabla con media, desviacion estandar muestral, error estandar
    e intervalo de confianza normal aproximado para cada metrica.

    Para 100 replicas, el IC normal 95% usa z = 1.96. Si alguna metrica tiene
    menos observaciones por valores faltantes, n se ajusta automaticamente.
    """
    z_by_confidence = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}
    z = z_by_confidence.get(confidence, 1.960)

    rows = []
    for metric in metrics:
        if metric not in df.columns:
            continue

        values = pd.to_numeric(df[metric], errors="coerce").dropna()
        n = int(values.shape[0])
        mean = float(values.mean()) if n > 0 else np.nan
        std = float(values.std(ddof=1)) if n >= 2 else 0.0
        se = float(std / np.sqrt(n)) if n >= 1 else np.nan
        margin = float(z * se) if n >= 1 else np.nan

        rows.append(
            {
                "metric": metric,
                "n": n,
                "mean": mean,
                "std": std,
                "standard_error": se,
                "confidence_level": confidence,
                "z_value": z,
                "ci_lower": mean - margin if n >= 1 else np.nan,
                "ci_upper": mean + margin if n >= 1 else np.nan,
                "ci_margin": margin,
            }
        )

    return pd.DataFrame(rows)


def _print_metric_with_se(stats_df: pd.DataFrame, metric: str, label: str) -> None:
    row = stats_df.loc[stats_df["metric"] == metric]
    if row.empty:
        print(f"{label}: métrica no disponible")
        return
    row = row.iloc[0]
    print(
        f"{label}: {row['mean']:.4f} "
        f"(SE={row['standard_error']:.4f}, IC95%=[{row['ci_lower']:.4f}, {row['ci_upper']:.4f}], n={int(row['n'])})"
    )


def main(instancia: int = 1, replicas: int = 100):
    """
    Resuelve deterministicamente el benchmark de informacion perfecta para una instancia
    con multiples replicas y guarda dos salidas:

    1) solution_summaries_...csv
       Resumen por replica, incluyendo metricas promedio por tour.

    2) tour_histogram_data_...csv
       Base desagregada por tour para construir histogramas de:
       - numero de clientes por tour
       - tiempo/duracion del tour

    3) metric_summary_stats_...csv
       Tabla con media, desviacion estandar, error estandar e IC95% por metrica.
    """
    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Crear/leer réplicas simuladas
    # instancia puede ser 1, 2, 3 o 4
    # replicas es la cantidad de días/escenarios que quieres resolver
    # df, csv_path = replica(instancia, replicas)
    df, csv_path = (
        pd.read_csv(f"data/instancia_tipo_{instancia}.csv"),
        f"data/instancia_tipo_{instancia}.csv",
    )

    print(f"Archivo generado/leído: {csv_path}")
    print(df.head())
    print(df["replica"].value_counts().sort_index())

    # Seguridad: si el archivo trae menos réplicas que las solicitadas, resolver solo las disponibles.
    available_replicas = sorted(df["replica"].dropna().unique().astype(int).tolist())
    replica_ids = available_replicas[:replicas]

    # 2. Configurar el problema
    cfg = VRPTWConfig(
        nb_vehicles=3,
        max_trips_per_vehicle=300,
        minimize_vehicles_after_profit=False,
        minimize_trips_after_profit=True,
        minimize_distance_after_profit=True,

        # Según el informe: depot en centro del mapa
        depot_xy=(10000.0, 10000.0),

        # Jornada operacional
        shift_start_sec=9 * 3600,
        shift_end_sec=17 * 3600,

        # 25 km/h en m/s
        vehicle_speed_m_per_s=25_000 / 3600,

        # Distancia Manhattan
        distance_metric="manhattan",

        # Servicio constante de 3 minutos
        service_time_default=180.0,
        force_service_time_default=True,

        # Pickups disponibles desde que aparecen
        pickup_ready_policy="arrival",

        # False = los no atendidos se interpretan como tercerizados
        require_all_customers=False,

        # Ventanas duras
        hard_time_windows=True,

        # Deadline interpretado como último inicio de servicio
        deadline_is_latest_start=True,

        # Delivery requiere carga en depot antes de atenderse
        delivery_must_be_loaded_at_depot=True,

        time_limit_sec=15,
    )

    # 3. Resolver cada réplica como escenario determinístico con información perfecta
    solution_summaries = []
    tour_histogram_rows = []

    for replica_id in replica_ids:
        print(f"Replica {replica_id}")

        escenario = (
            df[df["replica"] == replica_id]
            .copy()
            .reset_index(drop=True)
        )

        print(f"Clientes en escenario {replica_id}: {len(escenario)}")

        # 4. Resolver
        solution = solve_vrptw_hexaly(escenario, cfg, replica_id=replica_id)

        # 5. Revisar resultados y guardar resumen
        summary = solution.summary_as_dict()
        summary["instancia"] = instancia
        summary["replica"] = replica_id
        print(summary)
        solution_summaries.append(summary)

        # 6. Guardar posiciones de camiones para visualización
        solution.save_camion_positions_csv(
            output_dir / f"truck_positions_instance_{instancia}_replica_{replica_id + 1}.csv",
            include_depot=True,
        )

        # 7. Base desagregada por tour para histogramas
        trips_df = solution.trips_as_dataframe()
        if not trips_df.empty:
            trips_df = trips_df.copy()
            trips_df["instancia"] = instancia
            trips_df["replica"] = replica_id
            trips_df["tour_id"] = trips_df.apply(
                lambda row: f"I{instancia}_R{replica_id}_V{int(row['vehicle'])}_T{int(row['trip'])}",
                axis=1,
            )
            trips_df = trips_df.rename(columns={"n_stops": "n_customers_tour"})

            histogram_cols = [
                "instancia",
                "replica",
                "tour_id",
                "vehicle",
                "trip",
                "n_customers_tour",
                "tour_duration_sec",
                "tour_duration_min",
                "tour_duration_hours",
                "total_travel_time_sec",
                "total_distance_km",
                "total_profit",
                "departure_time_from_depot",
                "return_to_depot_time",
            ]
            tour_histogram_rows.append(trips_df[histogram_cols])

    # 8. Guardar resultados agregados por réplica
    solution_summaries_df = pd.DataFrame(solution_summaries)
    summaries_path = output_dir / f"solution_summaries_instancia_{instancia}_replicas_{len(replica_ids)}.csv"
    solution_summaries_df.to_csv(summaries_path, index=False)

    # 9. Guardar archivo para histogramas por tour/réplica
    if tour_histogram_rows:
        tour_histogram_df = pd.concat(tour_histogram_rows, ignore_index=True)
    else:
        tour_histogram_df = pd.DataFrame(
            columns=[
                "instancia",
                "replica",
                "tour_id",
                "vehicle",
                "trip",
                "n_customers_tour",
                "tour_duration_sec",
                "tour_duration_min",
                "tour_duration_hours",
                "total_travel_time_sec",
                "total_distance_km",
                "total_profit",
                "departure_time_from_depot",
                "return_to_depot_time",
            ]
        )

    histogram_path = output_dir / f"tour_histogram_data_instancia_{instancia}_replicas_{len(replica_ids)}.csv"
    tour_histogram_df.to_csv(histogram_path, index=False)

    # 10. Tabla para intervalos de confianza sobre metricas por replica.
    # Cada fila resume una metrica usando las replicas como observaciones independientes.
    replica_level_metrics = [
        "served_customers",
        "unserved_customers",
        "service_rate",
        "total_profit",
        "total_possible_profit",
        "profit_rate",
        "total_distance_km",
        "total_travel_time_sec",
        "nb_tours",
        "avg_customers_per_tour",
        "avg_tour_duration_sec",
        "avg_tour_duration_min",
        "avg_tour_duration_hours",
    ]
    metric_stats_df = _metric_summary_table(solution_summaries_df, replica_level_metrics, confidence=0.95)
    metric_stats_path = output_dir / f"metric_summary_stats_instancia_{instancia}_replicas_{len(replica_ids)}.csv"
    metric_stats_df.to_csv(metric_stats_path, index=False)

    # 11. Tabla adicional para intervalos de confianza usando cada tour como observacion.
    # Ojo: esta tabla sirve para describir dispersion de tours; para comparar politicas,
    # la tabla por replica suele ser metodologicamente mas limpia.
    tour_level_metrics = [
        "n_customers_tour",
        "tour_duration_sec",
        "tour_duration_min",
        "tour_duration_hours",
        "total_travel_time_sec",
        "total_distance_km",
        "total_profit",
    ]
    tour_metric_stats_df = _metric_summary_table(tour_histogram_df, tour_level_metrics, confidence=0.95)
    tour_metric_stats_path = output_dir / f"tour_metric_summary_stats_instancia_{instancia}_replicas_{len(replica_ids)}.csv"
    tour_metric_stats_df.to_csv(tour_metric_stats_path, index=False)

    print(f"Número de réplicas resueltas: {len(replica_ids)}")
    print(f"Resumen por réplica guardado en: {summaries_path}")
    print(f"Base para histogramas guardada en: {histogram_path}")
    print(f"Estadísticas con error estándar por réplica guardadas en: {metric_stats_path}")
    print(f"Estadísticas con error estándar por tour guardadas en: {tour_metric_stats_path}")

    print(" --- Atencion ---")
    _print_metric_with_se(metric_stats_df, "served_customers", "Promedio de clientes atendidos")
    _print_metric_with_se(metric_stats_df, "unserved_customers", "Promedio de clientes no atendidos")
    _print_metric_with_se(metric_stats_df, "service_rate", "Promedio de service_rate")

    print(" --- Ganancias ---")
    _print_metric_with_se(metric_stats_df, "total_profit", "Promedio de profit")
    _print_metric_with_se(metric_stats_df, "total_possible_profit", "Promedio de total_possible_profit")
    _print_metric_with_se(metric_stats_df, "profit_rate", "Promedio de profit_rate")

    print(" --- Tours, usando replicas como observaciones ---")
    _print_metric_with_se(metric_stats_df, "nb_tours", "Promedio de tours por réplica")
    _print_metric_with_se(metric_stats_df, "avg_customers_per_tour", "Promedio de clientes por tour")
    _print_metric_with_se(metric_stats_df, "avg_tour_duration_min", "Promedio de duración de tour [min]")
    _print_metric_with_se(metric_stats_df, "avg_tour_duration_hours", "Promedio de duración de tour [h]")

    print(" --- Tours, usando tours individuales como observaciones ---")
    _print_metric_with_se(tour_metric_stats_df, "n_customers_tour", "Clientes por tour")
    _print_metric_with_se(tour_metric_stats_df, "tour_duration_min", "Duración de tour [min]")
    _print_metric_with_se(tour_metric_stats_df, "tour_duration_hours", "Duración de tour [h]")

    print(" --- MISC ---")
    _print_metric_with_se(metric_stats_df, "total_distance_km", "Promedio de distancia recorrida")

    return solution_summaries_df, tour_histogram_df, metric_stats_df, tour_metric_stats_df


if __name__ == "__main__":
    # np.random.seed(42)
    # for i in range(4):
    #     if i < 2:
    #         continue
    #     else:
    main(instancia=1, replicas=100)
