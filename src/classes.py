#Archivo que creará las clases necesarias (modelo, heuristicas, processor, etc).
import typing
import logging
import numpy as np
import polars as pl


from typing import Dict
from dataclasses import dataclass, field
from config.settings import *
from src.ricas_replica_creator import replica
from utils.utilities import *

# Dataclass asociado a los datos de las instancias.
@dataclass
class InstanceData:
    '''Cada una de los data_types es realmente una lista de NUM_REPLICAS replicas...
    Donde cada replica tiene el data interesante:
    e.g. instance.arrivals[3] son los arrivals de la cuarta réplica '''
    file_path       : str = "/"
    name            : str = "Unnamed Instance Data"
    arrivals        : list = field(default_factory=list)
    deadlines       : list = field(default_factory=list)
    indicador       : list = field(default_factory=list)
    points          : list = field(default_factory=list)
    profits         : list = field(default_factory=list)
    ready_times     : list = field(default_factory=list)
    service_times   : list = field(default_factory=list)

    def __getitem__(self, key): # Permite usar el operador [], por ejemplo instance["arrivals"]
        data_types = DATA_TYPES

        if key not in data_types:
            raise KeyError(f"{key} no es una data_type de Instancia, keys = {data_types}")
        
        # Horrible hard code ayuda ---- esto está bien asi - Fer
        if key == "arrivals" :
            return self.arrivals
        elif key == "deadlines":
            return self.deadlines
        elif key == "indicador":
            return self.indicador
        elif key == "points":
            return self.points
        elif key == "profits":
            return self.profits
        elif key == "ready_times":
            return self.ready_times
        elif key == "service_times":
            return self.service_times
        else:
            raise KeyError
        


    def __str__(self):
        s = f"'{self.file_path}', of type {type(self)}"
        s += f"\n# arrivals: {len(self.arrivals)}"
        s += f"\n# deadlines: {len(self.deadlines)}"
        s += f"\n# indicador: {len(self.indicador)}"
        s += f"\n# points: {len(self.points)}"
        s += f"\n# profits: {len(self.profits)}"
        s += f"\n# ready_times: {len(self.ready_times)}"
        s += f"\n# service_times: {len(self.service_times)}"

        return s


# Dataclass que guarda el modelo 
@dataclass
class Event:
    pass 

@dataclass
class Customer:
    pos             : list          # Posicion del customer, lista de dos variables
    state           : int           # 0 si no ha solicitado servicio. 1 si solicitó servicio y no ha sido atendido. 2 si solicitó y ya fué atendido
    delivery        : bool          # True si es delivery, false si es pickup
    arrival         : int           # Tiempo de llegada de solicitud
    timelimit       : int           # Tiempo máximo en el que puede ser atendido

@dataclass
class Truck:
    id              : int
    pos             : list
    routes          : list[list]    # Lista de lista de customers
    current_route   : list          # Lista de customers
    arrival_times   : list          # Lista de próximos tiempos de llegada a destinos
    departure_times : list          # Lista de próximos tiempos de salida a destinos
    is_waiting      : bool          # True si el camión está esperando
    is_rtb          : bool          # True si el camión va devuelta al depot

class MSA:
    def __init__(self, truck: Truck, actual_time: int, current_data: pl.DataFrame, data_assigned: pl.DataFrame, sampling_data: pl.DataFrame):
        '''
        Clase que ejecuta MSA para el camión entregado, desde el momento actual. Usa método greedy para crear las rutas
        '''
        self.truck          = truck
        self.actual_time    = actual_time
        self.log            = logging.getLogger(__name__)
        # SUPUESTO ENTREGA 2: LOS QUE NO ESTÁN LISTOS NO SE CONSIDERAN
        # Data REVELADA disponible actualmente
        self.current_data   = current_data.filter(pl.col('arrivals') <= actual_time & pl.col('ready_times') <= actual_time) # Filtro para robustez. Lo hago igual en la MDP cuando se lo entrega
        # Clientes REVELADOS pendientes de asignacion
        self.to_be_assigned = self.current_data.join(data_assigned, how='anti')
        # Clientes SAMPLEADOS. solo nos interesa PICKUPS que podría pasar despues hasta un tiempo determinado Horizonte de dos horas
        self.sampling_data  = sampling_data.filter(pl.col('arrivals') >= actual_time & pl.col('indicador') == True & pl.col('arrivals') <= actual_time + 2 * 60 * 60)
    
    def create_routes(self) -> list:
        '''
        Metodo que aplica el greedy sobre un DataFrame y retorna la lista de rutas a seguir
        Utilizaré distintos métodos para crear rutas
        '''
        routes = []
        for i in range(NB_SCENARIOS):
            clients         = len(self.to_be_assigned) # Número de clientes revelados
            # Crear una ruta, iniciando desde cada cliente realizado
            for j in range(clients):
                route   = [self.to_be_assigned[j]]
                # Nota, no se incluye si es infactible atender al cliente
                if not feasibility_check(route, self.actual_time):
                    continue
                domain  = self.to_be_assigned.vstack(self.sampling_data)
                flag = True
                while flag:
                    nearest = nearest_neighbor(route[-1], domain, route, self.actual_time)
                    if nearest == None:
                        flag = False
                    else:
                        if travel_time(route + [nearest]) <= ROUTE_TIMELIMIT:
                            route.append(nearest)
                if feasibility_check(route, self.actual_time):
                    routes.append(route)

        # Encontrar tiempos de arrivo y salida
        arrivals    = [] # Los arrivalss se quedan igual
        departures  = [] # Los departures cambian al realizar la proyeccion
        final_routes = [] # Las rutas finales las creo a medida que verifico que sean nodos reales.

        # Proyectar rutas <=> eliminar los nodos simulados
        for i in range(len(routes)):
            route       = [routes[i][0]]
            arrival     = [self.actual_time + distance([0,0], routes[i][0]) / SPEED + 3 * 60]
            departures  = [self.actual_time]
            wait_time = 0
            for j in range(len(routes[i])):
                if routes[i][j] not in self.to_be_assigned:
                    wait_time += self.arrival[-1] +             
                else:


        self.truck.routes = final_routes
                
        return final_routes
    
    def execute(self) -> pl.DataFrame:
        '''
        Método que ejecuta el MSA
        '''
        self.log.info(f'Iniciando ejecución de MSA en el minuto {self.actual_time / 60}')

        # Me queda actualizar el dataframe de atendidos
        try:
            routes = self.create_routes()
        
        except Exception as e:
            self.log.critical(f'Error {e} al crear las rutas MSA.create_routes')
            raise e

        # Aqui se crea la matriz de consenso y se escoge la mejor - PARA LA ENTREGA 3. Ahora sera msad
        try:
        # En esta entrega se escoge la que tiene mayor razon de utilidad / distancia
            best_route = None
            best_razon = -10e6
            for i in range(len(routes)):
                for j in range(len(routes[i])):
                    razon = find_utility(routes[i][j]) / route_distance(routes[i][j])
                    if razon > best_razon:
                        best_razon = razon
                        best_route = routes[i][j]
        except Exception as e:
            self.log.critical('Error al calcular la mejor ruta bajo criterio Anton')
        
        if best_route == None or best_razon == -10e6:
            raise Exception
        
        self.truck.current_route    = best_route
        self.truck.is_waiting       = False # Camion despachado
        self.truck.is_rtb           = False

        return self.truck

class ALNS:
    def __init__(self):
        pass


class MDP:
    '''
    Clase principal que almacena el MDP y todos los elementos del problema
    '''
    def __init__(self, data_df: pl.DataFrame, replica_id: int):
        '''
        Inicializador. Recibe la ruta de los datos a usar y el número de replica a trabajar
        '''
        self.future         = FUTURE                # Si ve el futuro   
        self.nb_trucks      = NB_TRUCKS             # Número de camiones
        self.min_horizon    = MIN_HORIZON           # Inicio de operaciones (9:00) por default
        self.max_delivery   = MAX_DELIVERY          # Hora límite entrada de deliveries (15:30)
        self.max_pickup     = MAX_PICKUP            # Hora límite entrada de pickups (15:45)
        self.max_horizon    = MAX_HORIZON           # Horizonte de tiempo (17:00) por default
        self.epochs         = [9 * 60 * 60]                   # Epocas - 'an epoch begins when the vehicle arrives at a location and observes new customer requests'.
        self.events         = []                    # Cola de Eventos
        self.trucks         = []                    # Lista de camiones
        self.t_actual       = 9 * 60 * 60           # Tiempo actual. inicia siendo las 9:00
        self.data           = data_df.filter(pl.col('replica') == replica_id) # Datos de instancia 'replica_id'
        self.data_assigned  = pl.DataFrame()
        self.available_data = self.data.filter(pl.col('arrivals') <= self.t_actual)              # Inicialmente solo está disponible la data de las 9:00
        self.msa_sampling   = replica(INSTANCE, NB_REPLICA)
        self.log            = logging.getLogger(__name__)

        self.create_trucks()
        self.create_routes()
        self.log.info('Inicialización de MDP realizada con exito')

    def create_trucks(self):
        '''
        Método que crea los camiones según self.nb_trucks
        '''
        self.log.info('Iniciando creacion de camiones')
        try:
            for i in range(self.nb_trucks):
                self.trucks.append(Truck(i, [0,0], [], [], [], True))
        except Exception as e:
            self.log.critical(f'Error {e} en la creación de camiones. Deteniendo Ejecución')
            raise e
        return
    
    def create_routes(self):
        '''
        Método que crea las rutas a los camiones en espera dentro del depot - SUPUESTO: La creación de rutas inicia a las 9:00 y no entre 8:30 y 9:00
        '''
        if self.t_actual == 9 * 60 * 60:
            self.log.info('Creando rutas iniciales')
        else:
            self.log.info('Creando nuevas rutas')
        try:
            for i in range(self.nb_trucks):
                # Revisamos los camiones que están esperando en el depot
                if self.trucks[i].is_rtb == True:
                    msa = MSA(self.trucks[i], self.t_actual, self.data, self.data_assigned)
                    msa.execute()
                    #actualizar data_assigned
                else:
                    continue

        except Exception as e:
            self.log.error(f'Error {e} en la creacion de rutas.')
            raise e
        return




