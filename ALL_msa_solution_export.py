import math
import pandas as pd

from src.instance_loader import load_default_instances
from src.msa_policy import simular_msa
from src.core import DEPOT, T_INICIO, V_CAMIONES


############################ Anton Little #################################
INSTANCIA_IDX = 0
REPLICA_IDX = 0
OUTPUT_CSV = "output_msa.csv"

#cargar instancias
instancias = load_default_instances()

#correr msa
m = simular_msa(datos_instancia=instancias[INSTANCIA_IDX],
                replica_idx=REPLICA_IDX, idx_instancia=INSTANCIA_IDX)

#inicializar datos
timestamps = []
camion_pos = []
camion_ids = []

#guardar los datos iterativamente
for camion in m["estados_camiones"]:
    x, y = DEPOT
    t = T_INICIO
    for cliente in camion.visited:
        t_viaje = math.hypot(cliente.x- x, cliente.y - y)/V_CAMIONES
        t = max(t + t_viaje, cliente.ready)
        timestamps.append(t)
        camion_pos.append((cliente.x, cliente.y))
        camion_ids.append(camion.truck_id)
        t += cliente.servicio
        x, y = cliente.x, cliente.y

#crear df
df = pd.DataFrame()
df["camion_id"] = camion_ids
df["timestamps"] = timestamps
df["camion_pos"] = camion_pos

#exportar
df.to_csv(OUTPUT_CSV, index=False)
print(f"Exportado {len(df)} eventos a {OUTPUT_CSV}")