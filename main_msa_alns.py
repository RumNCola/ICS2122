from __future__ import annotations

from pathlib import Path
import multiprocessing as mp

import pandas as pd

from src.dynamic_alns.config_dynamic import DynamicMSAConfig
from src.dynamic_alns.data_normalizer import normalize_requests_df
from src.dynamic_alns.dispatcher import MSADynamicDispatcherALNS


def main(
    instancia: int = 1,
    replica_id: int = 0,
    n_scenarios: int = 25,
    lookahead_min: int = 120,
    scenario_time_limit_sec: float = 15.0,
    parallel_backend: str = "process",
    parallel_max_workers: int | None = None,
    parallel_log_progress: bool = True,
    parallel_cpu_reserve: int = 1,
):
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

    # Escenario real observado: instancia_tipo_i.csv filtrado por replica_id.
    df = normalize_requests_df(df, replica_id=replica_id)

    cfg = DynamicMSAConfig(
        instancia=instancia,
        n_scenarios=n_scenarios,
        lookahead_sec=lookahead_min * 60,
        scenario_time_limit_sec=scenario_time_limit_sec,
        parallel_backend=parallel_backend,
        parallel_max_workers=parallel_max_workers,
        parallel_cpu_reserve=parallel_cpu_reserve,
        parallel_start_method="spawn",
        parallel_log_progress=True,
        consensus_mode="van_hentenryck",
        seed=42,
        enable_dynamic_pickup_insertion=True,
        # True mantiene el comportamiento flexible: si hay camion esperando en depot
        # y llega un pedido nuevo, se puede replanificar. Cambia a False si quieres
        # ejecutar MSA solo en 09:00 y retornos de camion.
        run_msa_on_request_arrival_if_vehicle_waiting=True,
    )

    dispatcher = MSADynamicDispatcherALNS(cfg)
    result = dispatcher.run_replica(df)

    out_dir = Path("outputs/msa_alns")
    out_dir.mkdir(parents=True, exist_ok=True)

    trips_path = out_dir / f"committed_trips_instancia_{instancia}_replica_{replica_id}.csv"
    dynamic_path = out_dir / f"dynamic_insertions_instancia_{instancia}_replica_{replica_id}.csv"
    summary_path = out_dir / f"summary_instancia_{instancia}_replica_{replica_id}.csv"

    result.committed_trips.to_csv(trips_path, index=False)
    result.dynamic_insertion_log.to_csv(dynamic_path, index=False)
    pd.DataFrame([result.summary]).to_csv(summary_path, index=False)

    print(result.summary)
    print(f"Trips guardados en: {trips_path}")
    print(f"Inserciones dinamicas guardadas en: {dynamic_path}")
    print(f"Summary guardado en: {summary_path}")
    return result


if __name__ == "__main__":
    # Obligatorio/recomendado en Windows cuando se usa multiprocessing.
    t_0 = pd.Timestamp.now()
    print(f'Hora actual {t_0}')
    mp.freeze_support()
    main(
        instancia=1,
        replica_id=0,
        n_scenarios=20,
        lookahead_min=160,
        scenario_time_limit_sec=300,
        parallel_backend="process",
        # None = autodetectar CPUs y reservar parallel_cpu_reserve.
        parallel_max_workers=None,
        parallel_cpu_reserve=1,
    )
    print(f'Tiempo de ejecución: {pd.Timestamp.now() - t_0}')
