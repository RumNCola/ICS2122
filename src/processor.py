# Archivo encargado de procesar datos
import os
import pickle
import logging
from config.settings import *
from src.classes import Data

# Nota: No pasé los datos a DataFrames porque los arrays son de columna variable.
# Anton, si quieres hacer el análisis y no te funciona la lista de arrays, pasalo a polars,
# no pandas. Polars es más rápido y es intuitivo.

# Pd: no usé gpt para programar 

def process_arrivals(data_source: str) -> list:
    '''
    Recibe la ruta del data source (carpeta instancia).
    Función encargada de procesar el archivo de arrivals 'scen_arrivals_sample.pkl'.
    '''
    path = os.path.join(data_source, DATA_FILES['arrivals'])
    with open(path, 'rb') as f:
        arrivals = (pickle.load(f))
    return arrivals

def process_deadlines(data_source: str) -> list:
    '''
    Recibe la ruta del data source (carpeta instancia).
    Procesa y carga el deadlines 'scen_deadlines_sample.pkl'.
    '''
    path = os.path.join(data_source, DATA_FILES['deadlines'])
    with open(path, 'rb') as f:
        deadlines = pickle.load(f)
    return deadlines

def process_indicador(data_source: str) -> list:
    '''
    Recibe la ruta del data source (carpeta instancia).
    Procesa y carga el deadlines 'scen_indicador_sample.pkl'.
    '''
    path = os.path.join(data_source, DATA_FILES['indicador'])
    with open(path, 'rb') as f:
        indicador = pickle.load(f)
    return indicador

def process_points(data_source: str) -> list:
    '''
    Recibe la ruta del data source (carpeta instancia).
    Procesa y carga el deadlines 'scen_deadlines_sample.pkl'.
    '''
    path = os.path.join(data_source, DATA_FILES['points'])
    with open(path, 'rb') as f:
        file = pickle.load(f)
    return file

def process_profits(data_source: str) -> list:
    '''
    Recibe la ruta del data source (carpeta instancia).
    Procesa y carga el deadlines 'scen_deadlines_sample.pkl'.
    '''
    path = os.path.join(data_source, DATA_FILES['profits'])
    with open(path, 'rb') as f:
        file = pickle.load(f)
    return file

def process_ready_times(data_source: str) -> list:
    '''
    Recibe la ruta del data source (carpeta instancia).
    Procesa y carga el deadlines 'scen_deadlines_sample.pkl'.
    '''
    path = os.path.join(data_source, DATA_FILES['ready_times'])
    with open(path, 'rb') as f:
        file = pickle.load(f)
    return file

def process_service_times(data_source: str) -> list:
    '''
    Recibe la ruta del data source (carpeta instancia).
    Procesa y carga el deadlines 'scen_deadlines_sample.pkl'.
    '''
    path = os.path.join(data_source, DATA_FILES['service_times'])
    with open(path, 'rb') as f:
        file = pickle.load(f)
    return file

def load_data(data_source: str) -> Data:
    '''
    Recibe la ruta de fuente de datos data_source y crea una clase Data con los datos asociados
    cargados.
    '''
    data                    = Data()
    try:
        logger              = logging.getLogger(__name__)
    except Exception as e:
        print(f'CRITICAL: No se pudo cargar el Logger, terminando ejecución')
        raise e
    
    logger.info(f'Iniciando carga de archivos de la instancia {data_source}...')
    try:
        data.arrivals       = process_arrivals(data_source)
        logger.info(f'Carga de arrivals completada')
        data.deadlines      = process_deadlines(data_source)
        logger.info(f'Carga de deadlines completada')
        data.indicador      = process_indicador(data_source)
        logger.info(f'Carga de indicador completada')
        data.points         = process_points(data_source)
        logger.info(f'Carga de points completada')
        data.ready_times    = process_ready_times(data_source)
        logger.info(f'Carga de ready_times completada')
        data.service_times  = process_service_times(data_source)
        logger.info(f'Carga de service_times completada')
    except Exception as e:
        logger.critical('Carga de archivos incompleta, deteniendo ejecución...')
        raise Exception
    logger.info(f'Carga de data {data_source} completada con éxito')
    return data