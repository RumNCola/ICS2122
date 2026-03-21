# Archivo que creará el modelo.

from docplex.mp.model import Model


def create_deterministic_model() -> :
    '''
    Función que crea un modelo de carácter deterministico, segun lo visto en el paper de Chen et al.
    '''