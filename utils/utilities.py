# Archivo con funciones generales que permiten el desarrollo del código. Nada muy específico.
import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from config.settings import *

def k_opt(route: list, k: int) -> list:
    '''
    Funcion que recibe una ruta desordenada y la ordena para minimizar su costo usando el metodo
    k-opt, con k integer.
    '''

def distance(point_a: pl.DataFrame, point_b: pl.DataFrame) -> float:
    '''
    Funcion que calcula la distancia euclideana entre dos puntos. Se entregan en formato dataframe.
    Tambien recive [0,0] en caso del depot
    '''
    if point_a != [0, 0]:
        point_a = [point_a['x'][0], point_a['y'][0]]    
    if point_b != [0, 0]:
        point_b = [point_b['x'][0], point_b['y'][0]]
    return np.sqrt( np.square(point_a[0] - point_b[0]) + np.square(point_a[1] - point_b[1]) )

def travel_time(route: list[pl.DataFrame]) -> int:
    '''
    Funcion que recibe una ruta y calcula el tiempo total de viaje
    '''
    travel_time     = 0
    travel_time    += distance([0, 0], route[0]) / SPEED + 3 * 60 # (segundos)
    for i in range(len(route) - 1):
        travel_time += distance(route[i], route[i + 1]) / SPEED + 3 * 60 # (segundos)
    travel_time    += distance(route[-1], [0, 0])

    return travel_time

def find_arrivals(route: list[pl.DataFrame], actual_time: int) -> list:
    '''
    Funcion que entrega una lista con los tiempos arrival de una ruta
    '''
    arrival = [actual_time + distance([0,0], route[0]) / SPEED + 3 * 60]
    for i in range(len(route) - 1):
        new = arrival[-1] + distance(route[i], route[i + 1]) / SPEED + 3 * 60
        arrival.append(new)
    new = arrival[-1] + distance(route[i], [0,0])
    arrival.append(new)
    
    return arrival

def find_departures(route: list[pl.DataFrame], actual_time: int) -> list:
    '''
    FUncion que entrega un lista con los tiempos de departure de los nodos
    '''
    arrivals = find_arrivals(route, actual_time)
    departures = [actual_time] + arrivals[1:-1]
    return departures 
    

def find_utility(route: list[pl.DataFrame]) -> int:
    '''
    Funcion que calcula la utilidad de una solucion
    '''
    u = 0
    for i in range(len(route)):
        if route[i]['indicador'] == True:
            u += REWARDS[1]
        else:
            u += REWARDS[0]
    return u

def route_distance(route: list[pl.DataFrame]) -> int:
    '''
    Funcion que calcula la distancia de una ruta
    '''
    dist = distance([0,0], route[0]) + distance([0,0], route[-1])
    for i in range(len(route) - 1):
        dist += distance(route[i], route[i + 1])
    return dist

def feasibility_check_rtb(route:list, actual_time: int) -> bool:
    '''
    Funcion que recibe una ruta en formato simulated_data y retorna un booleano si es factible el RTB
    '''
    arrival_time = actual_time + travel_time(route)
    if 17 * 60 * 60 - arrival_time < 0:
        return False
    else:
        return True
    
def feasibility_check_tw(route: list, actual_time: int) -> bool:
    '''
    Función que recibe una ruta (lista), tiempo actual y retorna un booleano si es factible considerando los timewindows
    '''
    # SUPUESTO: se consideran los tres minutos de descargo en la ventana de tiempo

    travel_time = distance([0, 0], route[0]) / SPEED + 3 * 60
    
    for i in range(len(route)):
        # Caso para el último nodo
        timelimit = route[i]['deadlines'][0]
        timelimit_low = route[i]['ready_times'][0]
        
        if i == len(route) - 1:
            if timelimit_low <= actual_time + travel_time <= timelimit:
                return True
            else:
                return False
        else:    
            if timelimit_low <= actual_time + travel_time <= timelimit:
                travel_time += distance(route[i], route[i + 1]) / SPEED + 3 * 60
                continue
            else:
                return False


def feasibility_check(route: list, actual_time: int) -> bool:
    '''
    Funcion que recibe una lista de clientes a visitar en formato simulated_data y retorna un booleano si es factible
    '''
    if feasibility_check_rtb(route, actual_time) and feasibility_check_tw(route, actual_time):
        return True
    else:
        return False

def nearest_neighbor(center: pl.DataFrame, to_be_assigned: pl.DataFrame, current_route: list, actual_time: int) -> pl.DataFrame:
    '''
    Metodo que recibe un cliente en formato dataframe y los clientes to_be_assigned y retorna un
    dataframe con el cliente más cercano y su índice en data
    '''
    nearest = None
    min_d = 10e8
    for i in range(len(to_be_assigned)):
        if to_be_assigned[i] == center or to_be_assigned[i] in current_route: # se salta el nodo si es el centro o ya esta en la ruta
            continue
        else:
            dist = distance(center, to_be_assigned[i])
            if dist < min_d:
                new_route = current_route + to_be_assigned[i]
                if feasibility_check(new_route, actual_time):
                    nearest = to_be_assigned[i]
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