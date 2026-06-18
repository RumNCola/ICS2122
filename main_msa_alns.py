from __future__ import annotations

from pathlib import Path

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
):
    input_path = Path(f"data/instancia_tipo_{instancia}.csv")
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
    main(instancia=1, replica_id=0, n_scenarios=20, lookahead_min=140, scenario_time_limit_sec=15)

# {'served_customers': 92, 'outsourced_customers': 96, 'total_customers': 188, 'total_profit': 125.0, 'total_possible_profit': 305.0, 'profit_rate': 0.4098360655737705, 'total_distance_km': 464.3789140624999, 'nb_trips': 6, 'dynamic_pickups_inserted': 57, 'dynamic_pickups_postponed': 9, 'dynamic_pickups_undecided': 3, 'solver': 'MSA+ALNS+ICD-dynamic-pickups', 'consensus_mode': 'van_hentenryck'}
# 624999, 'nb_trips': 6, 'dynamic_pickups_inserted': 57, 'dynamic_pickups_postponed': 9, 'dynamic_pickups_undecided': 3, 'solver': 'MSA+ALNS+ICD-dynamic-pickups', 'consensus_mode': 'van_hentenryck'}