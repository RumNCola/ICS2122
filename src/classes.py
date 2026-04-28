#Archivo que creará las clases necesarias (modelo, heuristicas, processor, etc).
import typing

from typing import Dict
from dataclasses import dataclass, field
from config.settings import *

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
        
        # Horrible hard code ayuda
        if key == "arrivals" :
            return self.arrivals
        if key == "deadlines":
            return self.deadlines
        if key == "indicador":
            return self.indicador
        if key == "points":
            return self.points
        if key == "profits":
            return self.profits
        if key == "ready_times":
            return self.ready_times
        if key == "service_times":
            return self.service_times
        


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
class Model:   
    pass