import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

"""
Se definen estructuras fundamentales para el SDVRPTW.

Se definen: Cliente, EstadoCamion, constantes, helpers geométricos,
verificación de factibilidad, heurística de asignación y cargador de instancias.
"""


#-------- Constantes del problema ---------------

V_CAMIONES: float = 25000 / 3600 # 25km / hr = m/s
DEPOT: Tuple[float, float] = (10_000.0, 10_000.0) #centro en cuadrado de 20x20
T_INICIO: float = 30_600.0  #08:30:00 (secs desde las 00.00)
T_FINAL: float = 61_200.0  #17:00:00
T_SERVICIO: float = 180.0 #3 min por cliente
NUM_CAMIONES: int = 3


#---- EDD ------

#cliente
@dataclass
class Cliente:
    cid: int #id
    x: float #(m)
    y: float #(m)
    arrival: float #cuando aparece
    ready: float #desde cuando acepta
    deadline: float #hasta cuando acepta
    servicio: float #cuanto demora el servicio
    profit: float #ganancia: 2 delivery 1 pickup
    is_pickup: bool #True: pickup; False: delivery

    @property
    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)

#camion
@dataclass
class EstadoCamion:
    truck_id: int
    pos: Tuple[float, float] = field(default_factory=lambda: (DEPOT[0], DEPOT[1])) #pos actual empezando en DEPOT
    avail_time: float = T_INICIO #cuando queda libre (aclaracion: instante en que puede moverse al sig. destino, no cuando termina el clinete actual)
    total_profit: float = 0.0 #profit acumulado
    visited: List[Cliente] = field(default_factory=list) #historial de ruta
    total_distance: float = 0.0 #recorridos en (m.)


#------- Helpers geométricos ---------
def distancia(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) #distancia manhattan


def tiempo_viaje(p1: Tuple[float, float], p2: Tuple[float, float],
           speed: float = V_CAMIONES) -> float:
    return distancia(p1, p2) / speed #segundos de viaje


#----- Ruteo -------
def _insercion_factible(camion: EstadoCamion, cliente: Cliente,
                        fin_horizonte: float = T_FINAL,
                        velocidad: float = V_CAMIONES) -> Optional[float]:
    """
    Verifica factibilidad: si el camion puede atender al cliente y volver al depot a tiempo
    Retorna el nuevo tiempo de disponibilidad del camión si es factible, sino None.
    """
    t_viaje = tiempo_viaje(camion.pos, cliente.pos, velocidad)

    #1. ventana de tiempo de cliente
    llegada = max(camion.avail_time + t_viaje, cliente.ready)
    if llegada > cliente.deadline:
        return None
    
    #2. horizonte operacional
    salida = llegada + cliente.servicio
    if salida + tiempo_viaje(cliente.pos, DEPOT, velocidad) > fin_horizonte:
        return None
    return salida


def asignar_cercano_disponible(cliente: Cliente,
                              camiones: List[EstadoCamion],
                              fin_horizonte: float = T_FINAL,
                              velocidad: float = V_CAMIONES) -> int:
    """
    Retorna el truck_id del camión factible con menor tiempo de compromiso adicional,
    o -1 si ningún camión puede atender al cliente. Heurística greedy.
    """
    mejor_k = -1
    mejor_costo = math.inf
    for k, camion in enumerate(camiones):
        nuevo_disp = _insercion_factible(camion, cliente, fin_horizonte, velocidad)
        if nuevo_disp is None:
            continue
        costo = nuevo_disp - camion.avail_time
        if costo < mejor_costo:
            mejor_costo = costo
            mejor_k = k
    return mejor_k


def confirmar_asignacion(cliente: Cliente, camion: EstadoCamion,
                    velocidad: float = V_CAMIONES) -> None:
    """
    Actualiza el estado del camion al asignarle un cliente
    (solo al final de ruta)
    """
    t_viaje = tiempo_viaje(camion.pos, cliente.pos, velocidad)
    llegada = max(camion.avail_time + t_viaje, cliente.ready)
    salida = llegada + cliente.servicio
    camion.total_distance += distancia(camion.pos, cliente.pos)
    camion.pos = cliente.pos
    camion.avail_time = salida
    camion.total_profit += cliente.profit
    camion.visited.append(cliente)


#------- Extracción de datos de instancia -----------

def extraer_clientes(datos_instancia, replica_idx: int) -> List[Cliente]:
    """
    Convierte los raw arrays de InstanceData para replica_idx en una lista
    ordenada de Cliente. El índice 0 en cada arreglo es el depósito (profit == 0)
    por lo que se omite. Retorna los clientes ordenados por tiempo de llegada.
    Deja todo bonito
    """

    #arrays indexados por replica
    llegadas = datos_instancia.arrivals[replica_idx]
    puntos = datos_instancia.points[replica_idx]
    tiempos_ready = datos_instancia.ready_times[replica_idx]
    deadlines = datos_instancia.deadlines[replica_idx]
    tiempos_serv = datos_instancia.service_times[replica_idx]
    ganancias = datos_instancia.profits[replica_idx]
    indicador = datos_instancia.indicador[replica_idx]

    clientes = []
    for i in range(len(llegadas)):
        if float(ganancias[i]) == 0.0: #depot
            continue
        cliente = Cliente(
            cid = i,
            x = float(puntos[i][0]),
            y = float(puntos[i][1]),
            arrival = float(llegadas[i]),
            ready = float(tiempos_ready[i]),
            deadline = float(deadlines[i]),
            servicio = float(tiempos_serv[i]),
            profit = float(ganancias[i]),
            is_pickup= bool(indicador[i]),
        )
        clientes.append(cliente)

    clientes.sort(key=lambda c: c.arrival)
    return clientes
