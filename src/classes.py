#Archivo que creará las clases necesarias (modelo, heuristicas, processor, etc).
import typing

from typing import Dict
from dataclasses import dataclass, field

@dataclass
class Data:
    arrivals        : list = field(default_factory=list)
    deadlines       : list = field(default_factory=list)
    indicador       : list = field(default_factory=list)
    points          : list = field(default_factory=list)
    profits         : list = field(default_factory=list)
    ready_times     : list = field(default_factory=list)
    service_times   : list = field(default_factory=list)
