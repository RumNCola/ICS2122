'''TODO: FILL UP'''
import os

def output_filepath_pc(out_folder):
    return os.path.join(out_folder, "posiciones_camiones.csv")

def output_filepath_ca(out_folder):
    return os.path.join(out_folder, "clientes_atendidos.csv")

def create_directory(directory):
    os.makedirs(directory, exist_ok=True)
