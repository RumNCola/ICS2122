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
