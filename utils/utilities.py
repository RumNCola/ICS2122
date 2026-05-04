# Archivo con funciones generales que permiten el desarrollo del código. Nada muy específico.
import numpy as np
import polars as pl
import matplotlib.pyplot as plt

def k_opt(route: list, k: int) -> list:
    '''
    Funcion que recibe una ruta desordenada y la ordena para minimizar su costo usando el metodo
    k-opt, con k integer.
    '''

def travel_time(route: list) -> int:
    '''
    Funcion que recibe una ruta y calcula el tiempo total de viaje
    '''
    

def feasibility_check_rtb(route:list, actual_time: int) -> bool:
    '''
    Funcion que recibe una ruta en formato simulated_data y retorna un booleano si es factible el RTB
    '''
    

def feasibility_check_tw(route: list, actual_time: int) -> bool:
    '''
    Función que recibe una ruta (lista), tiempo actual y retorna un booleano si es factible considerando los timewindows
    '''
    pass


def feasibility_check(route: list, actual_time: int) -> bool:
    '''
    Funcion que recibe una lista de clientes a visitar en formato simulated_data y retorna un booleano si es factible
    '''
    pass

def distance(point_a: pl.DataFrame, point_b: pl.DataFrame) -> float:
    '''
    Funcion que calcula la distancia euclideana entre dos puntos. Se entregan en formato dataframe
    '''
    point_a = [point_a['x'][0], point_a['y'][0]]
    point_b = [point_b['x'][0], point_b['y'][0]]
    return np.sqrt( np.square(point_a[0] - point_b[0]) + np.square(point_a[1] - point_b[1]) )

def nearest_neighbor(center: pl.DataFrame, data: pl.DataFrame, current_route: list, actual_time: int) -> pl.DataFrame:
    '''
    Metodo que recibe un cliente en formato dataframe y los clientes to_be_assigned y retorna un
    dataframe con el cliente más cercano y su índice en data
    '''

    nearest = None
    min_d = 10e8
    for i in range(len(data)):
        if data[i] == center or data[i] in current_route: # se salta el nodo si es el centro o ya esta en la ruta
            continue
        else:
            dist = distance(center, data[i])
            if dist < min_d:
                if feasibility_check(current_route.append(data[i]), actual_time):
                    nearest = data[i]
                    min_d = dist
    return nearest


def view_raw_data(data, target: str) -> None:

    '''
    Método que imprime en histogramas los datos de todas las isntancias asociadas a scen_{target}_sample.pkl
    Con este metodo saqué los plots de data_analyisis.md
    '''
    for k in range(len(data)):

        if target == 'arrivals':
            puntos      = data[k].arrivals
        elif target == 'deadlines':
            puntos      = data[k].deadlines
        elif target == 'points':
            puntos      = data[k].deadlines #esta no se si funcione, no lo he probado
        elif target == 'ready_times':
            puntos      = data[k].ready_times
        elif target == 'service_times':
            puntos      = data[k].ready_times

        counter     = 0
        total       = 0
        points      = []
        timeborder  = 60 * 60 * 9 # 9 horas
        for i in range(len(puntos)):
            for j in range(len(puntos[i])):
                if int(puntos[i][j]) <= timeborder:
                    counter += 1
                points.append(puntos[i][j])
                total += 1


        print(f'Instancia: {k + 1}, counter: {counter}. Proportion: {100 * counter / total}%')
        plt.title(f'Distribuición de ingreso de solicitudes para la instancia {k + 1}')
        plt.ylabel('Número de solicitudes')
        plt.xlabel('Tiempo (s)')
        plt.axvline(x=timeborder, color='blue', linestyle='--')
        plt.hist(points, 26, rwidth=0.9, color='black')
        plt.show()