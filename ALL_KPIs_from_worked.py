'''In goes a 'worked' folder, out comes the KPI's'''

from src.constants import *
from src.classes import *
from src.instance_loader import *
from ALL_myopic_solution import *

import pandas as pd

VERBOSE_KPIS = False

def calc_total_U(df_ca):
    U = 0
    for _id in df_ca["indicador"][1:]: # First is el máldito DEPOT
        
        if _id == PICKUP:
            U += 1
        else:
            U += 2

    return U

def get_distancia_recorrida_camion(tiempos_ci: list, replica: Replica):
    t_and_index = [(tiempos_ci[j], j) for j in range(replica.num_points)]
    
    t_and_index.sort()

    primer_destino = t_and_index[0][1]
    dist_acumulada = dist(DEPOT_POS, replica.points[primer_destino])

    new_pos = DEPOT_POS

    for i in range(1, len(t_and_index)):
        t, new_index = t_and_index[i]

        if t >= INF: # Finish recorrido
            break
        
        last_index = t_and_index[i-1][1]
        last_pos = replica.points[last_index]
        new_pos = replica.points[new_index]

        dist_acumulada += dist(last_pos, new_pos)

    dist_acumulada += dist(new_pos, DEPOT_POS)

    return dist_acumulada
    


def get_distancia_recorrida_camiones(df_ca, replica: Replica):
    '''returns (d1, d2, d3) use sum() for KPI'''

    dists_camiones = []

    for id_camion in IDS_CAMIONES:
        key = f"tiempos_c{id_camion}"
        tiempos_ci = df_ca[key]

        d = get_distancia_recorrida_camion(tiempos_ci, replica)

        dists_camiones.append(d)

    return dists_camiones

def U_relativa_kpi(df_ca):
    U_todos_atendidos = calc_total_U(df_ca)

    u_p_d = calculate_utility_from_df_atendidos(df_ca)
    U_conseguido = u_p_d[0]

    U_relativo = U_conseguido / U_todos_atendidos

    if VERBOSE_KPIS:
        print(f"U_relativo: {U_conseguido}/{U_todos_atendidos} = {U_relativo*100}%")

    return U_relativo

def d_camiones_kpi(df_ca, replica: Replica):
    dist_camiones = get_distancia_recorrida_camiones(df_ca, replica)

    if VERBOSE_KPIS:
        print(f"{sum(dist_camiones)} = sum({dist_camiones})")

    return sum(dist_camiones)

def kpis_dict_from_df_clientes_atendidos(df_ca: pd.DataFrame, replica: Replica):

    kpi_u = U_relativa_kpi(df_ca)
    kpi_d = d_camiones_kpi(df_ca, replica)

    return {"U_relativa": kpi_u, "D_camiones": kpi_d}

def analysis_instancia_path(analysis_path: str, instance_index: int):
    instancia_folder_name = f"Instancia_{LABELS_INSTANCIAS[instance_index]}"

    return os.path.join(analysis_path, instancia_folder_name) 

# TODO: Move this to ALL_FILEPATHS
def analysis_replica_path(analysis_path: str, instance_index: int, replica_index: int):
    path = analysis_instancia_path(analysis_path, instance_index)
    name = f"{LABELS_INSTANCIAS[instance_index]}_replica_{replica_index}"

    return os.path.join(path, name)


def solve_and_save_replicas(analysis_path, instance_index, indices_replicas):
    print("AAAA")
    
    instance = load_instance_data(DATA_SRC[instance_index])

    for r_id in indices_replicas:
        # 1) solve the replica
        out_path = analysis_replica_path(analysis_path, instance_index, r_id)
        replica = get_replica_from_instancia(instance, r_id)

        solve_replica_myopic_and_save(out_path, replica)

    print("BBBBB")

def create_resumen_kpis(analysis_path, indices_instancias, indices_replicas):
    print("CCCC")
    
    
    df = pd.DataFrame()

    i_indices = []
    r_indices = []
    u_rels = []
    dists = []
    
    for instance_index in indices_instancias:
        instance = load_instance_data(DATA_SRC[instance_index])
        for r_id in indices_replicas:
            # 2) Evaluate
            out_path = analysis_replica_path(analysis_path, instance_index, r_id)
            ca_path = os.path.join(out_path, "clientes_atendidos.csv")

            df_ca = pd.read_csv(ca_path)
            replica = get_replica_from_instancia(instance, r_id)
            kpis = kpis_dict_from_df_clientes_atendidos(df_ca, replica)

            i_indices.append(instance_index)
            r_indices.append(r_id)
            u_rels.append(kpis["U_relativa"])
            dists.append( kpis["D_camiones"])


    df["Instancia"] = i_indices
    df["replica"] = r_indices
    df["U_relativa"] = u_rels
    df["D_camiones"] = dists

    dest_unk = os.path.join(analysis_path, "CamionSummary.csv")
    df.to_csv(dest_unk, index=False)
    print("DDDD")

def create_analysis_directories(analysis_folder_path: str, instance_indexes: list, replicas_indexes: list):
    
    num_written_folders = 0
    for instance_index in instance_indexes:
        num_written_folders += 1

        for replica_index in replicas_indexes:
            replica_path = analysis_replica_path(analysis_folder_path, instance_index, replica_index)
            os.makedirs(replica_path, exist_ok=True)
            num_written_folders += 1

    num_written_folders = num_written_folders

    print(f"Wrote {num_written_folders} folders to {analysis_folder_path}")

def create_myopic_analysis_folder(analysis_path, instancias_indices = [0,1,2,3], num_replicas = 20):
    replicas_indices = list(range(num_replicas))

    create_analysis_directories(analysis_path, instancias_indices, replicas_indices)
    
    for instance_index in instancias_indices:
        solve_and_save_replicas(analysis_path, instance_index, replicas_indices)
    
    create_resumen_kpis(analysis_path, instancias_indices, replicas_indices)

if __name__ == "__main__":
    analysis_path = os.path.join("outputs", "myopic_outputs", "analysisdelete")
    
    num_replicas = 10
    instancias_indices = [0, 1, 2, 3]

    create_myopic_analysis_folder(analysis_path, instancias_indices, num_replicas)
    

    

    
    
