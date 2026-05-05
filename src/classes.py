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
    rtb_time        : int           # Tiempo (s) en el que el camión volverá al depot. -1 es que ya volvió


# ENTREgA 3: EL CAMIÓN NUNCA CONSIDERA ESPERAR EN EL DEPOT.
class MSA:
    def __init__(self, truck: Truck, actual_time: int, current_data: pl.DataFrame, data_assigned: pl.DataFrame, sampling_data: pl.DataFrame):
        '''
        Clase que ejecuta MSA para el camión entregado, desde el momento actual. Usa método greedy para crear las rutas
        '''
        self.truck          = truck
        # El ´tiempo actual' es el el máximo entre el tiempo actual y la llegada del truck al depot
        if self.truck.rtb_time == -1:
            self.actual_time = actual_time
        else:
            self.actual_time    = max(actual_time, self.truck.rtb_time)
        self.log            = logging.getLogger(__name__)
        # SUPUESTO ENTREGA 2: LOS QUE NO ESTÁN LISTOS NO SE CONSIDERAN
        # Data REVELADA disponible actualmente
        self.current_data   = current_data.filter(pl.col('arrivals') <= self.actual_time & pl.col('ready_times') <= self.actual_time) # Filtro para robustez. Lo hago igual en la MDP cuando se lo entrega
        # Clientes REVELADOS pendientes de asignacion
        self.to_be_assigned = self.current_data.join(data_assigned, how='anti')
        # Clientes SAMPLEADOS. solo nos interesa PICKUPS que podría pasar despues hasta un tiempo determinado Horizonte de dos horas
        self.sampling_data  = sampling_data.filter(pl.col('arrivals') >= self.actual_time & pl.col('indicador') == True & pl.col('arrivals') <= self.actual_time + 2 * 60 * 60)
    
    def create_routes(self) -> list:
        '''
        Metodo que aplica el greedy sobre un DataFrame y retorna la lista de rutas a seguir
        Actualiza el camion con su ruta a seguir, set de rutas y tiempos de departure, arribo
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
        arrivals    = [] # Los arrivals se quedan igual
        departures  = [] # Los departures cambian al realizar la proyeccion
        final_routes = [] # Las rutas finales las creo a medida que verifico que sean nodos reales.

        # Proyectar rutas <=> eliminar los nodos simulados
        # i es la ruta, j es el nodo
        for i in range(len(routes)):
            route            = [routes[i][0]]
            base_arrival     = find_arrivals(routes[i])
            arrival          = []
            departure        = []
                       
            for j in range(len(routes[i])):
                # Si el nodo es simulado
                if routes[i][j] not in self.to_be_assigned:
                    continue

                # Si el nodo es real
                else:
                    # Se agrega el nodo a la ruta
                    route.append(routes[i][j])
                    # El tiempo de llegada no cambia
                    arrival.append(base_arrival[j])
                    
            # Los departures se calculan como a_{k+1} - d(N[p],N[q]) /SPEED - 3 * 60
            for k in len(arrival):
                if k == 0:
                    departure.append(arrival[0] - distance(route[0], [0, 0]) / SPEED - 3 * 60)
                elif k < len(arrival) - 1:
                    departure.append(arrival[k] - (distance(route[k], route[k+1]) / SPEED + 3 * 60))
                else:
                    departure.append(arrival[-1] - distance(route[-1], [0, 0]) / SPEED)
            
            departures.append(departure)
            arrivals.append(arrival)
            final_routes.append(route)        
                    
#AQUI VOY ANTON
            final_routes.append(route)

        self.truck.arrival_times = arrivals
        self.truck.rtb_trime = arrivals[-1]
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
                razon = find_utility(routes[i]) / route_distance(routes[i])
                if razon > best_razon:
                    best_razon = razon
                    best_route = routes[i]
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

class ICD:
    def __init__(self, trucks):
        self.trucks = trucks

    def best_insertion
    def rejection_policy(self, pickup: pl.DataFrame) -> bool:
        '''
        Funcion que recibe un pickup nuevo y retorna un booleano si este es atendible
        o no. Además actualiza los camiones
        '''
        # Revisamos cada camion. Buscaremos la insercion que genere el menor retraso.
        costs = []
        for i in range(len(self.trucks)):
            cost = travel_time(self.trucks[i].current_route)





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
        self.trucks         = []                    # Lista de camiones
        self.t_actual       = 9 * 60 * 60           # Tiempo actual. inicia siendo las 9:00
        self.data           = data_df.filter(pl.col('replica') == replica_id) # Datos de instancia 'replica_id'
        self.data_assigned  = pl.DataFrame()        # Clientes asignados
        self.data_served    = pl.DataFrame()        # Clientes efectivamente atendidos
        self.available_data = self.data.filter(pl.col('arrivals') <= self.t_actual)              # Inicialmente solo está disponible la data de las 9:00
        self.msa_sampling   = replica(INSTANCE, NB_REPLICA)
        self.log            = logging.getLogger(__name__)

        # Se agregan la entrada de pickups al pool de epochs
        self.initialize_epochs()
        # Crear los camiones
        self.create_trucks()
        # Crear rutas MSA
        self.create_routes()
        self.epochs.pop(0)
        self.log.info('Inicialización de MDP realizada con exito')

    def create_trucks(self):
        '''
        Método que crea los camiones según self.nb_trucks
        '''
        self.log.info('Iniciando creacion de camiones')
        try:
            for i in range(self.nb_trucks):
                self.trucks.append(Truck(i, [0,0], [], [], [], [], True, True, -1))
        except Exception as e:
            self.log.critical(f'Error {e} en la creación de camiones. Deteniendo Ejecución')
            raise e
        return
    
    def create_routes(self) -> None:
        '''
        Método que crea las rutas a los camiones en espera dentro del depot - SUPUESTO: La creación de rutas inicia a las 9:00 y no entre 8:30 y 9:00
        '''
        if self.t_actual == 9 * 60 * 60:
            self.log.info('Creando rutas iniciales')
        else:
            self.log.info('Creando nuevas rutas')
        try:
            for i in range(self.nb_trucks):
                # Crear la ruta es cuando rtb es true. Despachar cuando rtb true y pos = [0,0]
                # Revisamos los camiones que están esperando en el depot
                if self.trucks[i].is_rtb == True:
                    msa = MSA(self.trucks[i], self.t_actual, self.data, self.data_assigned)
                    self.trucks[i] = msa.execute()
                    # actualizar data_assigned
                    self.data_assigned.vstack(self.trucks[i].current_route)
                    # actualizar la lista de eventos y ordenarla
                    self.epochs.extend(self.trucks[i].arrival_times).sort()
                else:
                    continue
        except Exception as e:
            self.log.error(f'Error {e} en la creacion de rutas.')
            raise e
        return

    def initialize_epochs(self) -> None:
        '''
        Método que inicializa los eventos. Es decir, agrega las solicitudes de pickups reveladas en el tiempo
        a las epochs de decision.
        '''
        # Solo los eventos de pickup (indicador true). Se obtiene su tiempo de arribal exclusivamente. por eso i[0]
        # Tambien solo dejé los que ocurren dsps del inicio de operaciones
        epochs = [i[0] for i in self.data.filter(pl.col('indicador') == True & pl.col('arrivals') > 9 * 60 * 60)['arrival']]
        self.epochs += epochs
        return
        
    def identify_event(self, event_time: int) -> None:
        '''
        Método que identifica si un epoch registrado está asociado a un pickup ingresado al sistema o
        al arrivo de una nueva solicitud.
        Hice robusta la resolucion. QUe revise los arrivals y los pickups entrantes, no solo 1
        '''
        for i in range(len(self.trucks)):
            for j in range(len(self.trucks[i].arrival_times)):
                if event_time == self.trucks[i].arrival_times[j]:
                    return None

        domain = self.data.filter(pl.col('indicador') == True & pl.col('arrivals') == event_time)
        # Si es un pickup
        if len(domain) != 0:
            return domain[0] # Al retornar un no nulo debería llamar al icd
        # Si es un arrival
        else:
            return None
        
    def launch_ICD(self, event_time: int) -> None:
        '''
        Método que inicia ICD ante la llegada de un cliente pickup nuevo.
        Lo asigna a un camión y le actualiza en el MDP.
        '''
        
        

        return








