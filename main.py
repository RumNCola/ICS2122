# Módulo con el flujo principal, ejecutado por main.bat
import logging


from instance_loader import *
from config.settings import *
from utils.utilities import *


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
        data = [load_instance_data(DATA_SRC[i]) for i in range(len(DATA_SRC))] #Data es un list de len 4 con cada instancia cargada
    
    except Exception as e:
        logger.critical('Error en la carga de datos. terminando Ejecución')
        raise e

    #Visualizador de datos con histograma, opcional
    view_raw_data(data, 'arrivals')

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