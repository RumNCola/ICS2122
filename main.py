# Módulo con el flujo principal, ejecutado por main.bat
import logging

from src.instance_loader import *
from config.settings import *
from utils.utilities import *
from src.classes import *
from src.ricas_replica_creator import replica

def run():
    '''
    Ciclo principal del código.
    '''
    try:
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename='main.log', level=logging.INFO)
        logger.info('Iniciando ejecución de flujo principal')
    
    except Exception as e:
        print('CRITICAL: Error al crear el Logger')
        raise ImportError
    
    try:
        # Obtener datos simulados
        if SIMULATE_DATA:
            logger.info('Creando replica con metodo Rica')
            data_path = replica(INSTANCE, NB_SCENARIOS)
        else:
            logger.info(f'Obteniendo replica del archivo {DATA_FILE}')
            data_path = DATA_FILE
            
    except Exception as e:
        logger.critical('Error en la carga de replica. Terminando ejecución')
        raise e

    try:
        # Crear MDP
        logger.info('Iniciando creación de MDP')
        orchestrator = MDP(data_path, REPLICA_ID)

    except Exception as e:
        logger.critical('Error en la creación de MDP. Terminando ejecución')
        raise e

    logger.info('Ejecución finalizada con éxito')
    return

if __name__ == '__main__':
    try:
        run()
        print('SUCCESS: Ejecución terminada con éxito')
    except ImportError as e:
        print(f'Terminando Ejecución por {e}')
    except Exception as e:
        print(f'Terminando Ejecución por {e}')