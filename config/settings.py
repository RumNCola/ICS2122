# Archivo con información NO SENSIBLE asociada a prametros de la ejecución. Ejemplo: Mipgaps.
# Notar que la informacion sensible va en environment/.env
import os
import math

#RUTAS DE CARPETAS IMPORTANTES
DATA_FOLDER = 'data'

# Nombre de las carpetas de instancias
DATA_SRC = [
    os.path.join(DATA_FOLDER, 'Instancia Tipo I'),
    os.path.join(DATA_FOLDER, 'Instancia Tipo II'),
    os.path.join(DATA_FOLDER, 'Instancia Tipo III'),
    os.path.join(DATA_FOLDER, 'Instancia Tipo IV')
    ]

DATA_FILENAMES = {
    'arrivals': 'scen_arrivals_sample.pkl',
    'deadlines': 'scen_deadlines_sample.pkl',
    'indicador': 'scen_indicador_sample.pkl',
    'points': 'scen_points_sample.pkl',
    'profits': 'scen_profits_sample.pkl',
    'ready_times': 'scen_ready_times_sample.pkl',
    'service_times': 'scen_service_times_sample.pkl'
}

DATA_TYPES = DATA_FILENAMES.keys()

SIMULATE_DATA = True # True simula los datos, en caso contrario, escoge los datos del parquet DATA_FILE
NB_REPLICA = 100 # número de replicas a simular
INSTANCE = 1 # Instancia base sobre la que se simulan los datos
DATA_FILE = 'simulated_data/Instancia_4_100_replicas_2026-05-02_23-15-35.parquet'
REPLICA_ID = 1 # Número de la replica a cargar

# Parametros del modelo
REWARDS = [
    2, # Recompenza clientes estáticos
    1  # Recompenza clientes dinámicos
]

FUTURE = False #SI el MDP ve el futuro

NB_TRUCKS   = 3 #Número de camiones

MAX_HORIZON     = 17 * 60 * 60 # Horizonte de tiempo máximo en segundos (17:00)
MIN_HORIZON     = 9 * 60 * 60  # Inicio de operaciones
MAX_DELIVERY    = math.ceil(15,5 * 60 * 60)
MAX_PICKUP      = math.ceil(15,75 * 60 * 60)