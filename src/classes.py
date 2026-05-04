#Archivo que creará las clases necesarias (modelo, heuristicas, processor, etc).
import typing
import logging
import polars as pl

from typing import Dict
from dataclasses import dataclass, field
from config.settings import *
from src.ricas_replica_creator import replica

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
    is_waiting      : bool          # True si viene devuelta a depot

class MSA:
    def __init__(self, truck, actual_time, current_data, data_assigned):
        '''
        Clase que ejecuta MSA para el camión entregado, desde el momento actual. Usa método greedy para crear las rutas
        '''
        self.truck          = truck
        self.actual_time    = actual_time
        self.log            = logging.getLogger(__name__)
        self.current_data   = current_data.filter(pl.col('arrivals') <= actual_time) # Filtro para robustez. Lo hago igual en la MDP cuando se lo entrega
        self.to_be_assigned = self.current_data.join(data_assigned, how='anti')
    
    def greedy(dataframe: pl.DataFrame) -> list:
        '''
        Metodo que aplica el greedy sobre un DataFrame y retorna la lista de rutas a seguir
        '''
        

    def execute() -> pl.DataFrame:
        '''
        Método que ejecuta el MSA
        '''
        self.log.info(f'Iniciando ejecución de MSA en el minuto {actual_time / 60}')

        try:
            sampling = replica(INSTANCE, NB_SCENARIOS, self.actual_time).filter(pl.col('arrivals') >= actual_time) # Notar que se muestra solo lo que no ha pasado todavía
        except Exception as e:
            self.log.critical(f'Error {e} al samplear escenarios. Deteniendo ejecución.')
            raise e
        
        try:
            for i in range(NB_SCENARIOS):

        
        except Exception as e:


        # try:
        #     self.data = 
        
        # except Exception as e:
        #     self.log.critical(f'Error {e} al unir dataframes sampling y current_data. Deteniendo ejecucion')
        


        return

class ALNS:
    def __init__(self):
        pass


class MDP:
    '''
    Clase principal que almacena el MDP y todos los elementos del problema
    '''
    def __init__(self, data_path: str, replica_id: int):
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
        self.data           = pl.read_parquet(data_path).filter(pl.col('replica') == replica_id) # Datos de instancia 'replica_id'
        self.data_assigned  = pl.DataFrame()
        self.available_data = self.data.filter(pl.col('arrivals') <= self.t_actual)              # Inicialmente solo está disponible la data de las 9:00
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
        if self.t_actual = 9 * 60 * 60:
            self.log.info('Creando rutas iniciales')
        else:
            self.log.info('Creando nuevas rutas')
        try:
            for i in range(self.nb_trucks):
                # Revisamos los camiones que están esperando en el depot
                if self.trucks[i].is_waiting == True and self.trucks[i].pos == [0,0]:



                else:
                    continue

        except Exception as e:
            self.log.error(f'Error {e} en la creacion de rutas.')
            raise e
        return




