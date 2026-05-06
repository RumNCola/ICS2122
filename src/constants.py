'''CONSTANTES específicas al problema'''

INF = 10**12

TIEMPO_DELIVERY_LOADING = 900

TIEMPO_DE_SERVICIO_PICKUP = 180
TIEMPO_DE_SERVICIO_DELIVERY = 180

PICKUP = True
DELIVERY = False

WIDTH_MAPA = 20000 # metros
HEIGHT_MAPA = 20000 # metros

DEPOT_POS = [10000, 10000]

NUM_REPLICAS = 100

NUM_CAMIONES = 3

VEL_RAPPI_MS = 25000 / 3600
VEL_CAMION_MS = 25000 / 3600 # (25 km / hra) = 6.9444 m/s

LABELS_INSTANCIAS = ["I", "II", "III", "IV"]

def seconds_to_hh_mm_ss(seconds_since_0000):
    '''7261 -> 02:01:01'''
    seconds_since_0000 = int(seconds_since_0000)

    hh = seconds_since_0000//3600

    seconds_since_the_hour = seconds_since_0000 - hh*3600
    mm = seconds_since_the_hour // 60

    ss = seconds_since_the_hour - 60*mm

    return f"{hh:02}:{mm:02}:{ss:02}"

def hh_mm_ss_to_seconds(hh_mm_ss):
    '''8:30:00 -> 43543'''
    hh, mm, ss = [int(d) for d in hh_mm_ss.split(":")]

    seconds_since_00 = hh*3600 + mm*60 + ss

    return seconds_since_00

if __name__ == "__main__":
    print(hh_mm_ss_to_seconds("12:05:43"))
    print(seconds_to_hh_mm_ss("7200"), seconds_to_hh_mm_ss("7261"))

    print(hh_mm_ss_to_seconds(seconds_to_hh_mm_ss(120324)))
    print(seconds_to_hh_mm_ss(hh_mm_ss_to_seconds("21:59:20")))

    print(START_TIME, END_TIME)

def dist(pA: tuple, pB: tuple):
    '''Manhattan distance: |x2 - x1| + |y2 - y1| Igual que la vida real'''
    dx = pB[0] - pA[0]
    dy = pB[1] - pA[1]
    return abs(dx) + abs(dy)

def travel_time(pA: tuple, pB: tuple, v = 25000/3600):
    '''returns t = dist(pA, pB) / v'''

    t = (dist(pA, pB) / v)

    return t

import math
def duracion_rappi(pos_cliente, indicador_cliente): # ESTO nooooo va aquí
    '''Salen del depot: travel_time + service_time'''
    tiempo_de_servicio = TIEMPO_DE_SERVICIO_DELIVERY
    if indicador_cliente == PICKUP:
        tiempo_de_servicio = TIEMPO_DE_SERVICIO_PICKUP

    duracion_rappi = travel_time(DEPOT_POS, pos_cliente, VEL_RAPPI_MS) + tiempo_de_servicio

    duracion_rappi = int(math.ceil(duracion_rappi))
    
    return duracion_rappi

START_TIME = hh_mm_ss_to_seconds("8:30:00")
END_TIME = hh_mm_ss_to_seconds("17:00:00")

CAMIONES_START_ss = hh_mm_ss_to_seconds("9:00:00")

T_SS_CAMION = list(range(CAMIONES_START_ss, END_TIME+1))

import os
MANHATTAN_FILEPATH = os.path.join("images", "ImageSources", "GoogleEarthManhattan.png")