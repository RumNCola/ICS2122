'''Anton Little's Testing python file.'''

import logging

import numpy as np


from src.processor import *
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
    
def show_points(instancia: InstanceData):
    # Mañana agregar un slider para cual de los 100 tiempos mostrar
    fig, ax = plt.subplots()

    point_lists = instancia.points

    xs = []
    ys = []
    for point in point_lists[0]:
        xs.append(point[0])
        ys.append(point[1])

    l0, = ax.plot(xs, ys, "bo")

    plt.title("Representación Realística de Manhattan")

    plt.show()

def run():
    '''
    Ciclo principal del código.
    '''

    logger = logger_stuff()
    
    instancias = None
    try:
        instancias = [load_data(DATA_SRC[i]) for i in range(len(DATA_SRC))] #Instancias es un list de len 4 con cada instancia cargada
        for instancia in instancias:
            print(instancia)
            exit()
        return instancias
        
    
    except Exception as e:
        logger.critical('Error en la carga de datos. terminando Ejecución')
        raise e

    #Visualizador de datos con histograma, opcional
    #view_raw_data(data, 'arrivals')

    show_points(instancias[0])

    logger.info('Ejecución finalizada con éxito')
    return

def check_instancias(instancias):
    count = 0
    
    epsilon = 0.1
    for instancia in instancias:
        for point_list in instancia.points:
            for point in point_list:
                if abs(point[0] - 10000) + abs(point[1] - 10000) < epsilon:
                    count += 1

    print("Count: ", count)



from plagio_PII import *
if __name__ == '__main__':
    print("Running ALL_MAIN")

    try:
        instancias = run()
        check_instancias(instancias)
        launch_cool_app(instancias)
        print('SUCCESS: Ejecución terminada con éxito')
    except ImportError as e:
        print(f'Terminando Ejecución por {e}')
    except Exception as e:
        print(f'Terminando Ejecución por {e}')