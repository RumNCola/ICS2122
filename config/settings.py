# Archivo con información NO SENSIBLE asociada a prametros de la ejecución. Ejemplo: Mipgaps.
# Notar que la informacion sensible va en environment/.env
import os

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

# Parametros del modelo
REWARDS = [
    2, # Recompenza clientes estáticos
    1  # Recompenza clientes dinámicos
]