# Archivo encargado de procesar datos
import os
import pickle
import logging
from config.settings import *
from src.classes import InstanceData

# Nota: No pasé los datos a DataFrames porque los arrays son de columna variable.
# Anton, si quieres hacer el análisis y no te funciona la lista de arrays, pasalo a polars,
# no pandas. Polars es más rápido y es intuitivo.

# Pd: no usé gpt para programar 
# PPd: 25/03 Se simplificaron 7 funciones en 2

def process_datafile(instance_source, type_of_data) -> list:
    '''
    Recibe la ruta del instance source (carpeta instancia) y
    type_of_data que debe ser un 'key' de DATA_FILENAMES

    Función encargada de procesar el archivo DATA_FILENAMES[type_of_data].
    '''

    if type_of_data not in DATA_FILENAMES.keys():
        # Esto debería ser un logger en vez de un print
        print(f"{type_of_data} no es un archivo reconocido entre {DATA_FILENAMES.keys}")
        raise KeyError

    path = os.path.join(instance_source, DATA_FILENAMES[type_of_data])
    with open(path, 'rb') as f:
        requested_info = pickle.load(f)
    return requested_info

def load_instance_data(instance_source: str) -> InstanceData:
    '''
    Recibe la ruta de fuente de datos instance_source y devuelve una InstanceData con los datos asociados
    cargados.
    '''
    data                    = InstanceData()
    data.file_path = instance_source
    try:
        logger              = logging.getLogger(__name__)
    except Exception as e:
        print(f'CRITICAL: No se pudo cargar el Logger, terminando ejecución')
        raise e
    
    logger.info(f'Iniciando carga de archivos de la instancia {instance_source}...')
    try:
        data.name = data.file_path
        data.arrivals       = process_datafile(instance_source, "arrivals")
        logger.info(f'Carga de arrivals completada')

        data.deadlines      = process_datafile(instance_source, "deadlines")
        logger.info(f'Carga de deadlines completada')

        data.indicador      = process_datafile(instance_source, "indicador")
        logger.info(f'Carga de indicador completada')

        data.points         = process_datafile(instance_source, "points")
        logger.info(f'Carga de points completada')

        data.profits         = process_datafile(instance_source, "profits")
        logger.info(f'Carga de profits completada')

        data.ready_times    = process_datafile(instance_source, "ready_times")
        logger.info(f'Carga de ready_times completada')

        data.service_times  = process_datafile(instance_source, "service_times")
        logger.info(f'Carga de service_times completada')

    except Exception as e:
        logger.critical('Carga de archivos incompleta, deteniendo ejecución...')
        raise e
        
    logger.info(f'Carga de data {instance_source} completada con éxito')
    return data

def load_default_instances():
    '''Carga y retorna una lista con las 4 instancias del enunciado'''
    instances = [load_instance_data(DATA_SRC[i]) for i in range(len(DATA_SRC))]

    return instances

if __name__ == "__main__":
    print("Running instance_loader.py")

    print("I cannot run but I must scream")


    