import numpy as np
from typing import Dict, List

from src.core import Cliente

"""
Generador de escenarios para MSA (Multiple Scenario Approach).

Genera realizaciones de clientes futuros. Replican las distribuciones definidas
en el generador de replicas del Rica. Se usa numpy.random.Generator para control de seed
por escenario.
"""

_TIEMPO_SERVICIO = 180.0

#Rango de clientes totales por instancia (indexado en 1, igual que replica())
_RANGO_CANTIDAD = {1: (161, 232), 2: (171, 235), 3: (165, 247), 4: (165, 247)}

#Probabilidad de delivery por instancia (tambien igual que replica())
_P_DELIVERY = {1: 0.6209366, 2: 0.6701915, 3: 0.6608995, 4: 0.6608995}

#parametros de zonas horarias de llegada para instancias 2-4
#clave: instancia -> {'d': (p1, p2, hi3_delivery), 'p': (p1, p2, hi3_pickup)}
_ZONAS_LLEGADA = {
    2: {'d': (0.1943, 0.4948, 55_800), 'p': (0.2090, 0.4727, 56_700)},
    3: {'d': (0.2231, 0.4774, 55_800), 'p': (0.2253, 0.4479, 56_700)},
    4: {'d': (0.2086, 0.5017, 55_800), 'p': (0.2032, 0.4774, 56_700)},
}

#función auxiliar
def _recortar(v: float) -> float:
    return float(np.clip(v, 0.0, 20_000.0))


def _muestrear_clientes(instancia: int, n: int, rng) -> List:
    
    """
    Genera n clientes para la instancia dada usando rng con seed definida.
    Sortea 4 cosas indep: tipo, tiempo de llegada, ventana de tiempo + profit y pos espacial

    Retorna lista de (arrival, ready, deadline, x, y, profit, is_pickup).
    Los arrivals cubren todo el día operacional; el caller filtra por current_time.
    """

    prob_delivery = _P_DELIVERY[instancia]
    resultado = []

    for i in range(n): #Se generan n clientes
        #tipo de cliente (bernoulli)
        es_delivery = rng.random() < prob_delivery

        #tiempo de llegada

        #instancia 1 uniforme pura
        if instancia == 1:
            arrival = rng.uniform(31_500, 55_800 if es_delivery else 56_700)
        
        #instancias 2-4 mezclas de uniformes
        else:
            p1, p2, hi3 = _ZONAS_LLEGADA[instancia]['d' if es_delivery else 'p']
            u = rng.random()
            if u < p1:
                arrival = rng.uniform(31_500, 39_600) #zona 1
            elif u < p1 + p2:
                arrival = rng.uniform(39_600, 46_800) #zona 2
            else:
                arrival = rng.uniform(46_800, hi3) #zona 3

        #time windows y profit
        if es_delivery:
            ready = arrival + 900   #15 min dsp de llegar
            deadline = ready + 10_800   #ventana de 3 horas
            profit = 2.0
        else:
            ready = arrival  #disponible altiro
            deadline = 61_200.0  #hasta final del horizonte operacional
            profit = 1.0

        #posicion espacial

        #1 y 2 uniformes
        if instancia in (1, 2):
            x = float(rng.uniform(0, 20_000))
            y = float(rng.uniform(0, 20_000))

        #instancia 3 es mezcla de clusters entiendo
        elif instancia == 3:
            if es_delivery:
                if rng.random() < 0.5068:  #cluster norte_ 50.68%
                    x = _recortar(rng.normal(10_022.78, 2_862.292))
                    y = _recortar(rng.normal(14_712.9,  2_004.336))
                else:  #cluster sur: 49.32%
                    if rng.random() < 0.012:  #casos borde
                        x = float(rng.uniform(0, 200) if rng.random() < 0.5
                                  else rng.uniform(19_800, 20_000))
                    else:
                        x = _recortar(20_000 * rng.beta(1.775272, 1.79102))
                    y = _recortar(rng.normal(4_943.167, 2_123.399))
            #pickup
            else:
                if rng.random() < 0.5015:
                    x = _recortar(rng.normal(10_037.04, 2_922.686))
                    y = _recortar(rng.normal(14_750.37, 1_975.571))
                else:
                    if rng.random() < 0.013:
                        x = float(rng.uniform(0, 200) if rng.random() < 0.5
                                  else rng.uniform(19_800, 20_000))
                    else:
                        x = _recortar(20_000 * rng.beta(1.836308, 1.846874))
                    y = _recortar(rng.normal(4_943.167, 2_123.399))

        #instancia 4

        #mezcla de 3 clusters
        else:
            if es_delivery:
                p_der, p_izq = 0.5061, 0.2455
                u = rng.random()
                if u < p_der:  #cluster derecho
                    x = _recortar(rng.normal(14_972.16, 2_032.986))
                    y = _recortar(20_000 * rng.beta(3.208858, 3.186452))
                elif u < p_der + p_izq:  #cluster izq
                    x = _recortar(rng.normal(4_961.03,  2_055.79))
                    y = _recortar(rng.normal(14_970.59, 2_060.453))
                else:          #clustter inf izq
                    x = _recortar(rng.normal(4_956.316, 2_041.85))
                    y = _recortar(rng.normal(5_008.544, 2_041.99))

            #pickup
            else:
                p_der, p_izq = 0.5000, 0.2515
                u = rng.random()
                if u < p_der:
                    x = _recortar(rng.normal(15_009.78, 1_995.241))
                    y = _recortar(20_000 * rng.beta(3.050116, 3.046799))
                elif u < p_der + p_izq:
                    x = _recortar(rng.normal(4_949.299, 2_046.547))
                    y = _recortar(rng.normal(15_000.59, 2_014.086))
                else:
                    x = _recortar(rng.normal(5_021.175, 2_067.657))
                    y = _recortar(rng.normal(4_996.648, 2_002.915))

        resultado.append((float(arrival), float(ready), float(deadline),
                          x, y, float(profit), not es_delivery))
    return resultado

#generador de escenarios
def generar_escenarios(idx_instancia: int, t_actual: float, n_escenarios: int, 
                       n_procesados: int, base_cid: int = -100_000, base_semilla: int = 0, 
                       max_futuro: int = 40) -> List[Dict[int, Cliente]]:
    
    """
    muestrea n_escenarios realizaciones de clientes futuros para la instancia dada.

    Los parámetros son:
    idx_instancia: 0-3 (Instancia I-IV; convertido internamente a idx en 1)
    t_actual: tiempo actual de simulación (en segundos)
    n_escenarios: número de escenarios a generar
    n_procesados: clientes ya revelados (para estimar cuántos quedan)
    base_cid: cid inicial para clientes muestreados (negativo, evita colisiones)
    base_semilla: base de seed para reproducibilidad
    max_futuro: máximo de clientes por escenario

    Retorna lista de n diccionarios {cid -> Cliente}.
    """

    #conversión de índice (convencion inicial)
    instancia   = idx_instancia + 1
    lo, hi     = _RANGO_CANTIDAD[instancia]
    escenarios  = []
    contador_cid = base_cid

    #loop principal (un escenario por iter.)
    for k in range(n_escenarios):
        rng = np.random.default_rng(base_semilla + k * 31357) #nº primo grande para asegurar que secuencias no se solapen 

        #estimacion de clientes futuros
        if instancia == 1:
            n_total  = int(np.random.normal(199.65, 13.424))
        elif instancia == 2:
            n_total = int(np.random.normal(200.48, 12.415))
        elif instancia == 3:
            n_total = int(np.random.normal(200.56, 14.02474))
        elif instancia == 4:
            n_total = int(np.random.normal(200.56, 14.02474))
        else:
            print("No se dio instancia válida")
        
        n_futuro = max(0, n_total - n_procesados)

        #sobremuestreamos para compensar el filtro arrival > current_time (naturalmente)
        n_candidatos = max(n_futuro * 4, max_futuro * 5)
        raw = _muestrear_clientes(instancia, n_candidatos, rng)

        #Conservar solo los que aun no han llegado hasta max_futuro
        filtrado = [r for r in raw if r[0] > t_actual][:max_futuro]

        clientes: Dict[int, Cliente] = {}
        for (arrival, ready, deadline, x, y, profit, is_pickup) in filtrado:
            cliente = Cliente(cid=contador_cid, x=x, y=y, arrival=arrival,
                               ready=ready, deadline=deadline, servicio=_TIEMPO_SERVICIO,
                               profit=profit, is_pickup=is_pickup,)
            
            clientes[contador_cid] = cliente
            contador_cid -= 1

        escenarios.append(clientes) #clientes es Dict{c_id --> objeto Cliente}

    return escenarios #lista de N Dicts con el formato anterior