'''Convierte los pickles en .csv'''

from src.constants import *
from src.classes import *
from src.instance_loader import *

import pandas as pd # Fernando in Shambles

def create_metadata_df(instancia: InstanceData):
    metadata_df = pd.DataFrame(columns=["replica", "num_rows"])
    replicas_list = []
    num_rows_list = []
    for replica in range(NUM_REPLICAS):
        num_rows = len(instancia.indicador[replica])

        replicas_list.append(replica)
        num_rows_list.append(num_rows)

    metadata_df["replica"] = replicas_list
    metadata_df["num_rows"] = num_rows_list

    return metadata_df

def create_points_df(instancia: InstanceData):
    points_df = pd.DataFrame(columns=["replica", "x", "y"])

    replicas_list = []
    x_list = []
    y_list = []

    for replica in range(NUM_REPLICAS): # CHANGE ME for NUM_REPLICAS
        points = instancia.points[replica]
        
        for point in points:
            x, y = point

            replicas_list.append(replica)
            x_list.append(x)
            y_list.append(y)
    
    points_df["replica"] = replicas_list
    points_df["x"] = x_list
    points_df["y"] = y_list

    return points_df

def create_data_type_df(instancia: InstanceData, data_type):
    df = pd.DataFrame(columns=["replica", data_type])

    replicas_list = []
    data_list = []

    for replica in range(NUM_REPLICAS):
        data = instancia[data_type]
        
        replicas_list.extend([replica]*len(data[replica]))
        data_list.extend(data[replica]) # !
    
    df["replica"] = replicas_list
    df[data_type] = data_list

    return df

def export_instancia_to_csvs(instancia: InstanceData, filepath_carpeta: str):
    '''Crea una carpeta con los .csv correspondiente a cada data_type'''

    dfs = {}

    for data_type in DATA_TYPES:
        if data_type == "points": # Ahhh HardCode
            dfs[data_type] = create_points_df(instancia)
        else:
            dfs[data_type] = create_data_type_df(instancia, data_type)

    dfs["_metadata"] = create_metadata_df(instancia)

    for key in dfs.keys():
        filename = f"{key}.csv"
        destination_filepath = os.path.join(filepath_carpeta, filename)
        dfs[key].to_csv(destination_filepath, index=False)

    print(f"Se rellenó la carpeta {filepath_carpeta} con {len(dfs.keys())} archivos .csv")

def export_to_csv():
    instances = load_default_instances()

    folder_names = ["Instancia_I_csvs", "Instancia_II_csvs", "Instancia_III_csvs", "Instancia_IV_csvs"]
    
    for i in range(4):
        export_instancia_to_csvs(instances[i], os.path.join("outputs", folder_names[i]))

if __name__ == "__main__":
    print("Running ALL_to_csvs.py...")

    export_to_csv()