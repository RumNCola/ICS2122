'''CR output -> posiciones_camiones.csv & clientes_atendidos.csv\n
TODO: Checkear realidad de rutas interpoladas'''

from src.constants import *
from src.classes import *
from src.instance_loader import *
from ALL_myopic_solution import move_camion, add_columna_rappi, add_columna_indicador
from ALL_filepaths import *

import pandas as pd

EPS = 0.1

raw_filename = "FJ_output_29mayv1.csv"
out_foldername = "FJ2905EEE"

CR_FOLDER = os.path.join("outputs", "CR_outputs")
CR_RAW_FILEPATH = os.path.join(CR_FOLDER, "raw", raw_filename)

CR_OUT_FOLDER = os.path.join(CR_FOLDER, "worked", out_foldername)

df_raw = pd.read_csv(CR_RAW_FILEPATH)

g_REPLICA = Replica()

def clean_pos_string(entry:str ):
    '''returns (x, y)'''

    entry = entry.replace("(", "").replace(")", "")

    x, y = [float(d) for d in entry.split(", ")]

    return x, y

def clean_df_raw(df_raw: pd.DataFrame):
    '''Adds x, y columns, +1 to id_camion'''

    positions = [clean_pos_string(entry) for entry in df_raw["camion_pos"]]

    clean_df = df_raw.copy(deep = True)

    clean_df["camion_id"] = [_id+1 for _id in df_raw["camion_id"]]
    clean_df["x"] = [p[0] for p in positions]
    clean_df["y"] = [p[1] for p in positions]

    return clean_df


def interpolate_xs_ys_to_cx_cy(timestamps: list, xs: list, ys: list):
    '''Se inventa el camino (por segundo) de un camión en base a los 'objetivos'.\n
      Returns (cx: list, cy: list)\n
      Si quieres, es una función de interpolación.\n
      Agrega el DEPOT careraja como último objetivo a las 17:00'''
    timestamps.append(hh_mm_ss_to_seconds("17:00:00"))
    xs.append(DEPOT_POS[0])
    ys.append(DEPOT_POS[1])

    
    current_pos = DEPOT_POS
    obj_index = 0
    next_objective = (xs[0], ys[0])

    cx = []
    cy = []

    for t_ss in T_SS_CAMION:
        new_pos = move_camion(current_pos, next_objective)

        if t_ss > timestamps[obj_index]:
            # Teleport 
            current_pos = next_objective
            new_pos = next_objective

            if obj_index <= (len(xs)-2):
                obj_index += 1

            next_objective = (xs[obj_index], ys[obj_index])

        cx.append(current_pos[0])
        cy.append(current_pos[1])
        current_pos = new_pos

    return (cx, cy)

def df_only_for_camion(df_clean, id_camion):
    df_camion = df_clean.loc[df_clean["camion_id"] == id_camion]

    return df_camion



def create_t_cx_cy_columns(df_clean: pd.DataFrame, id_camion):
    '''Retorna (cx, cy): las 2 columnas de 1 camión en base a df_clean e id_camion'''
    df_camion = df_only_for_camion(df_clean, id_camion)
    
    timestamps = list(df_camion["timestamps"])
    xs_camion = list(df_camion["x"])
    ys_camion = list(df_camion["y"])

    return interpolate_xs_ys_to_cx_cy(timestamps, xs_camion, ys_camion)

def create_posiciones_camiones_df(df_raw):
    """t,c1_x,c1_y,c2_x,c2_y,c3_x,c3_y"""

    df_clean = clean_df_raw(df_raw)
    

    df = pd.DataFrame()
    df["t"] = T_SS_CAMION
    for id_camion in IDS_CAMIONES:
        cx, cy = create_t_cx_cy_columns(df_clean, id_camion)
        
        key_x = f"c{id_camion}_x"
        key_y = f"c{id_camion}_y"
        df[key_x] = cx
        df[key_y] = cy

    return df

def columna_tiempos_ci(df_clean, id_camion, points_clientes):
    df_camion = df_only_for_camion(df_clean, id_camion)
    timestamps = list(df_camion["timestamps"]) 
    xs_camion = list(df_camion["x"])
    ys_camion = list(df_camion["y"])

    num_events = len(timestamps)
    num_clientes = len(points_clientes)

    columna_tiempos_ci = [INF] * num_clientes

    for event_index in range(num_events): # ~ 100
        for cliente_index in range(num_clientes): # ~ 200
            
            camion_pos = (xs_camion[event_index], ys_camion[event_index])
            if dist(camion_pos, points_clientes[cliente_index]) < EPS:
                columna_tiempos_ci[cliente_index] = timestamps[event_index]

    return columna_tiempos_ci

def create_clientes_atendidos_df(df_raw: pd.DataFrame, replica: Replica):
    df_clean = clean_df_raw(df_raw)

    df = pd.DataFrame()

    for id_camion in IDS_CAMIONES:
        column_name = f"tiempos_c{id_camion}"

        columna = columna_tiempos_ci(df_clean, id_camion, replica.points)
        df[column_name] = columna

    add_columna_rappi(df, replica)
    add_columna_indicador(df, replica)
    
    return df

def create_worked_from_raw_csv(raw_csv_path, out_folder):
    instance_I = load_instance_data(DATA_SRC[0])
    replica = get_replica_from_instancia(instance_I, 0) 

    print("Loaded instancia & replica")
    
    df_raw = pd.read_csv(raw_csv_path)
    create_directory(out_folder)
    
    cr_out_pc = output_filepath_pc(out_folder)
    cr_out_ca = output_filepath_ca(out_folder)
    
    df_pc = create_posiciones_camiones_df(df_raw)
    df_pc.to_csv(cr_out_pc, index=False)
    print(f"Writing to... {cr_out_pc}")

    df_ca = create_clientes_atendidos_df(df_raw, replica)
    df_ca.to_csv(cr_out_ca, index=False)
    print(f"Writing to... {cr_out_ca}")

        
if __name__ == "__main__":
    print("Running ALL_traductor_...")

    instance_I = load_instance_data(DATA_SRC[0])
    replica = get_replica_from_instancia(instance_I, 0) 

    print("Loaded instancia & replica")

    create_worked_from_raw_csv(CR_RAW_FILEPATH, CR_OUT_FOLDER)



