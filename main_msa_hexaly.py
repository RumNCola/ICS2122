from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.dynamic.config_dynamic import DynamicMSAConfig
from src.dynamic.data_normalizer import normalize_requests_df
from src.dynamic.dispatcher import MSADynamicDispatcher


def main(rica: bool, instancia: int = 1, replica_id: int = 0, n_scenarios: int = 20, lookahead_min: int = 140):
    if not rica:
        input_path = Path(f"data/instancia_tipo_{instancia}.csv")
        if input_path.exists():
            df = pd.read_csv(input_path)
        else:
            raise FileNotFoundError(f"Archivo no encontrado: {input_path}")
    else:
        from src.ricas_replica_creator import replica
        df, _ = replica(instancia, replicas=max(1, replica_id + 1))

    df = normalize_requests_df(df, replica_id=replica_id)

    cfg = DynamicMSAConfig(
        instancia=instancia,
        n_scenarios=n_scenarios,
        lookahead_sec=lookahead_min * 60,
        scenario_time_limit_sec=10,
        consensus_mode="van_hentenryck",
        seed=42,
    )

    dispatcher = MSADynamicDispatcher(cfg)
    result = dispatcher.run_replica(df)

    out_dir = Path("outputs/msa_hexaly")
    out_dir.mkdir(parents=True, exist_ok=True)

    trips_path = out_dir / f"committed_trips_instancia_{instancia}_replica_{replica_id}.csv"
    summary_path = out_dir / f"summary_instancia_{instancia}_replica_{replica_id}.csv"

    result.committed_trips.to_csv(trips_path, index=False)
    pd.DataFrame([result.summary]).to_csv(summary_path, index=False)

    print(result.summary)
    print(f"Trips guardados en: {trips_path}")
    print(f"Summary guardado en: {summary_path}")
    return result


if __name__ == "__main__":
    # Ejemplo rapido.
    main(rica=False, instancia=1, replica_id=0, n_scenarios=30, lookahead_min=160)
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

#Mas escenarios, Mas Lookahead, Mas tiempo!
#n_scenarios=50, lookahead_min=160 scenario_time_limit_Sec=15 entrega 65,5% de retorno
#n_scenarios=30, lookahead_min=160 scenario_time_limit_Sec=10 entrega % de retorno