'''Anton Little's main python file.'''

import logging

import numpy as np

from src.constants import *
from src.instance_loader import *
from config.settings import *
from utils.utilities import *

def logger_stuff():
    try:
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename='main.log', level=logging.INFO)
        logger.info('Iniciando ejecución de flujo principal')
        return logger
    
    except Exception as e:
        print('CRITICAL: Error al crear el Logger')
        raise ImportError

# This should be the main of instance_loader, but I couldn't get it to work :(
def main_instance_loader():
    print("Running function main_instance_loader()")
    instances = load_default_instances()

    for instance in instances:
        print(instance)    

def run():
    '''
    Ciclo principal del código.
    '''

    logger = logger_stuff()
    
    try:
        instances = load_default_instances()
        i0 = instances[0]
        clients = [int(c) for c in i0.indicador[0][:10]]
        profits = [int(p) for p in i0.profits[0][:10]]
        print(clients, PICKUP)
        print(profits)
    except Exception as e:
        logger.critical('Error en la carga de datos. terminando Ejecución')
        raise e

    logger.info('Ejecución finalizada con éxito')
    return

from ALL_visualizador import *
if __name__ == '__main__':
    print("Running ALL_MAIN")

    try:
        run()

        print('SUCCESS: Ejecución terminada con éxito')
    except ImportError as e:
        print(f'Terminando Ejecución por {e}')
    except Exception as e:
        print(f'Terminando Ejecución por {e}')