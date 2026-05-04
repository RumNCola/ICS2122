import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from src.core import Cliente, tiempo_viaje, DEPOT, T_FINAL, V_CAMIONES

"""
Adaptative Large Neighbourhood Search (ALNS) para el VRPTW

Tenemos:
  - N camiones, cada uno con una posición y tiempo de inicio fijos (N=3)
  - Un pool de clientes a asignar
  - Ventanas de tiempo (ready, deadline) por cliente
  - Tiempo de servicio y profit por cliente

Retorna el mejor ruteo encontrado: asignación de clientes a camiones (algunos
pueden quedar  sin asignar/rechazados) que maximiza la ganancia total.

Implementacion:
  Destrucción: eliminacion_aleatoria, eliminacion_peor
  Reparación:  insercion_greedy, insercion_regret2

Los pesos adaptativos se actualizan tras cada iteración con un sistema de puntajes simple.
"""

#----------- Solución ---------------------------

#estado mínimo de un camion
@dataclass
class InicioRuta:
    truck_id: int
    pos: Tuple[float, float]
    time: float   #tiempo mínimo disponible en pos


#estructura central de ALNS
class SolucionALNS:
    """
    routes[k] = lista ordenada de c_ids de clientes para el camión k.
    sin_asignar = conjunto de c_ids que no han sido asignados (no están en ninguna ruta).
    """
    def __init__(self, routes: List[List[int]], sin_asignar: Set[int],
                 customers: Dict[int, Cliente], starts: List[InicioRuta],
                 depot: Tuple[float, float] = DEPOT, t_final: float = T_FINAL,
                 velocidad: float = V_CAMIONES):
        self.routes = routes    #lista de listas (una por camión)
        self.sin_asignar = sin_asignar  #conjunto de cids sin asignar
        self.customers = customers  #Dict {cid --> Cliente}
        self.starts = starts  #uno por camión
        self.depot = depot
        self.t_final = t_final
        self.velocidad = velocidad

    def clonar(self) -> "SolucionALNS":
        return SolucionALNS(
            routes = [list(r) for r in self.routes],
            sin_asignar = set(self.sin_asignar),
            customers = self.customers,  #referencia compartida de solo lectura
            starts = self.starts,
            depot = self.depot,
            t_final = self.t_final,
            velocidad = self.velocidad,
        )

    #----------- Helpers de horario ---------------------------

    #reconstruccion de tiempos
    def _horario_ruta(self, k: int) -> List[Tuple[float, float]]:
        """
        Recorre la ruta del camion k, cliente por cliente (pos y tiempo)
        Retorna lista de tuplas (llegada, salida) para la ruta actual del camión k.
        La posición/tiempo de inicio viene de self.starts[k].
        """

        #inicio
        pos = self.starts[k].pos
        t = self.starts[k].time
        horario = []
        for cid in self.routes[k]:
            c = self.customers[cid]
            t_viaje = tiempo_viaje(pos, c.pos, self.velocidad)
            llegada = max(t + t_viaje, c.ready)   #igual que en core.py
            salida  = llegada + c.servicio
            horario.append((llegada, salida))
            pos = c.pos
            t = salida
        return horario
    
    #factibilidad check (feasability)
    def _ruta_factible(self, k: int, ruta: Optional[List[int]] = None) -> bool:
        """
        Verifica factibilidad de ventanas de tiempo
        También verifica retorno al depósito para el camión k.
        """

        #caso base
        if ruta is None:
            ruta = self.routes[k]

        pos = self.starts[k].pos
        t = self.starts[k].time
        for cid in ruta:
            c = self.customers[cid]
            t_viaje = tiempo_viaje(pos, c.pos, self.velocidad)
            llegada = max(t + t_viaje, c.ready)
            if llegada > c.deadline:
                return False   #viola time window
            t = llegada + c.servicio
            pos = c.pos
        t_viaje_retorno = tiempo_viaje(pos, self.depot, self.velocidad)
        return t + t_viaje_retorno <= self.t_final
    
    #proxy de costo (funcion ultra simple)
    def _tiempo_retorno_ruta(self, k: int, 
                             ruta: Optional[List[int]] = None) -> float:
        """
        Tiempo en que el camión k retorna al depósito
        Proxy de costo porque una ruta que termina antes es preferible
        Por que es preferible? Pregunta para ver si realmente están leyendo esto
        """
        if ruta is None:
            ruta = self.routes[k]
        pos = self.starts[k].pos
        t = self.starts[k].time
        for cid in ruta:
            c = self.customers[cid]
            t_viaje = tiempo_viaje(pos, c.pos, self.velocidad)
            t = max(t + t_viaje, c.ready) + c.servicio
            pos = c.pos
        return t + tiempo_viaje(pos, self.depot, self.velocidad)

    #--------- Costo de inserción ----------------------------

    #delta de tiempo de retorno
    def costo_insercion(self, k: int, 
                        pos_idx: int, cid: int) -> float:
        """
        Tiempo de retorno adicional al insertar cid en la posición pos_idx (cualquier pos, no solo al final) del camión k.
        Calcula cuanto tiempo adicional cuesta la inserción
        Retorna inf si la inserción es infactible (para no considerarla).
        """

        ruta = self.routes[k]
        nueva_ruta = ruta[:pos_idx] + [cid] + ruta[pos_idx:]
        if not self._ruta_factible(k, nueva_ruta):
            return math.inf   #infactible
        t_retorno_anterior = self._tiempo_retorno_ruta(k, ruta)
        t_retorno_nuevo = self._tiempo_retorno_ruta(k, nueva_ruta)
        return t_retorno_nuevo - t_retorno_anterior
    
    #busqueda exhaustiva
    def mejor_insercion(self, cid: int) -> Tuple[int, int, float]:
        """
        Prueba todas las posiciones posibles, en todas las rutas de todos los camiones
        Retorna (camion, posicion, costo) óptimo
        O(K*L), K=nº camiones, L=largo promedio ruta
        (-1, -1, inf) si no existe ninguna inserción factible.
        Disclaimer posterior: Creo que esto esta cagando la rutina
        """
        mejor_k = -1
        mejor_pos = -1
        mejor_costo = math.inf

        for k in range(len(self.routes)):
            for p in range(len(self.routes[k]) + 1):
                c = self.costo_insercion(k, p, cid)
                if c < mejor_costo:
                    mejor_costo = c
                    mejor_k = k
                    mejor_pos = p

        return mejor_k, mejor_pos, mejor_costo

    #---------- Objetivo ----------------------------
    
    #profit total con iter ultra simple
    def ganancia_total(self) -> float:
        return sum(self.customers[cid].profit 
                   for ruta in self.routes
                   for cid in ruta
                   )
    
    #factibilidad global
    def es_totalmente_factible(self) -> bool:
        return all(self._ruta_factible(k) for k in range(len(self.routes)))

    #----------- Delta de eliminación --------------------

    #beneficio de quitar un cliente
    def delta_eliminacion(self, k: int, p: int) -> float:
        """
        Cuanto tiempo se ahorra en la ruta si se elimina el cliente en posicion p.
        Valor alto = fuerte candidato a eliminar, ya que es muy costoso tenerlo en la ruta
        """
        ruta = self.routes[k]
        nueva_ruta = ruta[:p] + ruta[p + 1:]
        tr_anterior = self._tiempo_retorno_ruta(k, ruta)
        tr_nueva = self._tiempo_retorno_ruta(k, nueva_ruta)
        return tr_anterior - tr_nueva


#------------------- Construcción ---------------------------------------

#solucion inicial
def _construir_greedy(customers: Dict[int, Cliente], starts: List[InicioRuta],
                      depot: Tuple[float, float], fin_horizonte: float,
                      velocidad: float, rng: random.Random) -> SolucionALNS:
    """
    Construye una solución inicial insertando clientes de a uno,
    ordenados por deadline (más ajustado primero) con desempate aleatorio.
    """
    n_camiones = len(starts)
    sol = SolucionALNS(routes = [[] for _ in range(n_camiones)],
                       sin_asignar = set(customers.keys()),
                       customers = customers,
                       starts = starts,
                       depot = depot,
                       t_final = fin_horizonte,
                       velocidad = velocidad,
                       )

    #clientes reales (cid >= 0) antes que futuros muestreados (cid < 0) para
    #garantizar prioridad de ruta al cliente actual que acaba de llegar.
    orden = sorted(customers.keys(),
                   key=lambda cid: (  
                       0 if cid >= 0 else 1,   #reales antes que muestreados
                       customers[cid].deadline,   #deadline mas ajustado primero
                       rng.random()   #desempate random
                       ))

    for cid in orden:
        k, p, costo = sol.mejor_insercion(cid)
        if k >= 0:
            sol.routes[k].insert(p, cid)
            sol.sin_asignar.discard(cid)

    return sol


#----------------------- Destrucción -----------------------------------

#eliminación random
def eliminacion_aleatoria(sol: SolucionALNS, q: int, rng: random.Random) -> List[int]:
    """
    Elimina q clientes al azar. 
    Elimina en orden de indice descendiente para evitar errores en .pop()
    Retorna lista de cids eliminados.
    """
    asignados = [(k, p, cid) for k, ruta in enumerate(sol.routes)
                 for p, cid in enumerate(ruta)]
    if not asignados:
        return []
    muestra = rng.sample(asignados, min(q, len(asignados)))
    eliminados = []
    for k, p, cid in sorted(muestra, key=lambda x: (x[0], -x[1])):
        sol.routes[k].pop(p)  #se elimina cid
        sol.sin_asignar.add(cid)
        eliminados.append(cid)  #lista con eliminados
    return eliminados


def eliminacion_peor(sol: SolucionALNS, q: int, rng: random.Random) -> List[int]:
    """
    Elimina los q clientes con peor relación (costo/ganancia): ocupan puestos
    de ruta caros en relación a la ganancia (intuitivo). 
    Ruido pequeño para aleatorizar.
    """
    puntuados = []
    for k, ruta in enumerate(sol.routes):
        for p, cid in enumerate(ruta):
            delta = sol.delta_eliminacion(k, p)   #tiempo que se ahorra
            ganancia = sol.customers[cid].profit   #ganancia asociada
            puntaje = -delta / (ganancia + 1e-9)   #criterio de eliminacion
            puntuados.append((puntaje + rng.uniform(0, 0.1), k, p, cid))

    puntuados.sort(reverse=True)

    #se ejecuta la eliminación
    eliminados = []
    a_eliminar = []
    for _, k, p, cid in puntuados[:q]:
        a_eliminar.append((k, p, cid))

    for k, p, cid in sorted(a_eliminar, key=lambda x: (x[0], -x[1])):
        sol.routes[k].pop(p)
        sol.sin_asignar.add(cid)
        eliminados.append(cid)

    return eliminados

#----------------- Reparación -----------------------------------

#greedy
def insercion_greedy(sol: SolucionALNS, 
                     rng: random.Random) -> None:
    """
    Inserta los clientes sin asignar ordenados por ganancia descendente
    Más valiosos primero. Cada uno a mejor posición factible.
    """
    pool = list(sol.sin_asignar)
    pool.sort(key=lambda cid: 
              (-sol.customers[cid].profit, rng.random()))

    for cid in pool:
        k, p, costo = sol.mejor_insercion(cid)
        if k >= 0:
            sol.routes[k].insert(p, cid)
            sol.sin_asignar.discard(cid)

#regret
def insercion_regret2(sol: SolucionALNS, 
                      rng: random.Random) -> None:
    """
    Inserta repetidamente al cliente con mayor arrepentimiento, no al más "valioso"
    Dif entre 2da mejor insercion y la mejor (= costo_2da_mejor − costo_mejor). 
    Arrepentimiento alto = pocas buenas opciones.
    Intuición es: Si no lo insertas ahora, después sera proporcionalmente mucho mas caro
    """
    while sol.sin_asignar:
        mejor_cid = None
        mejor_regret = -math.inf
        mejor_k = -1
        mejor_pos = -1

        for cid in list(sol.sin_asignar):
            costos = []
            for k in range(len(sol.routes)):
                for p in range(len(sol.routes[k])+1):
                    c = sol.costo_insercion(k, p, cid)
                    if c< math.inf:
                        costos.append((c, k, p))
            costos.sort()

            if not costos:
                continue   #infactible, dejar sin asignar

            c1, k1, p1 = costos[0]
            c2 = costos[1][0] if len(costos) > 1 else math.inf #insercion unica
            regret = c2 - c1

            #actualización (si es necesaria)
            if regret > mejor_regret:
                mejor_regret = regret
                mejor_cid = cid
                mejor_k = k1
                mejor_pos = p1

        if mejor_cid is None:
            break

        sol.routes[mejor_k].insert(mejor_pos, mejor_cid)
        sol.sin_asignar.discard(mejor_cid)


#---------------- Loop principal ejecución ALNS ---------------------------------------------

_OPS_DESTRUCCION = [eliminacion_aleatoria, eliminacion_peor]
_OPS_REPARACION = [insercion_greedy, insercion_regret2]

_PUNTAJE_MEJOR = 3   #nuevo mejor global
_PUNTAJE_MEJOR_ACT = 2   #mejora sobre el actual
_PUNTAJE_ACEPTADO  = 1   #aceptado pese a ser peor (aceptación greedy)
_PUNTAJE_RECHAZADO = 0

_DECAIMIENTO = 0.8  #factor de decaimiento para pesos adaptativos

def resolver_alns(customers: Dict[int, Cliente], starts: List[InicioRuta],
               n_iteraciones: int = 100, fraccion_elim: float = 0.20,
               limite_tiempo_s: float = 2.0, seed: int = 0,
               depot: Tuple[float, float] = DEPOT, t_final: float = T_FINAL,
               velocidad: float = V_CAMIONES) -> SolucionALNS:
    """
    Ejecuta ALNS (aura). Retorna mejor solucion

    Parámetros:
        customers: {cid: Cliente}. Pool completo (se pueden atender o no)
        starts: posición/tiempo de inicio por camión
        n_iteraciones: máximo de iteraciones ALNS (ayuda)
        fraccion_elim: fracción de clientes asignados a eliminar por iteración
        limite_tiempo_s: límite de tiempo en segundos
        seed: semilla RNG
    """
    if not customers:
        n = len(starts)
        return SolucionALNS([[] for _ in range(n)], set(), customers,
                            starts, depot, t_final, velocidad)

    rng = random.Random(seed)

    actual = _construir_greedy(customers, starts, depot, t_final, velocidad, rng)
    mejor = actual.clonar()

    pesos_d = [1.0]*len(_OPS_DESTRUCCION)   #pesos destruccion 
    pesos_r = [1.0]*len(_OPS_REPARACION)   #pesos reparacion
    puntajes_d = [0.0]*len(_OPS_DESTRUCCION)
    puntajes_r = [0.0]*len(_OPS_REPARACION)
    conteos_d = [0]*len(_OPS_DESTRUCCION)
    conteos_r = [0]*len(_OPS_REPARACION)

    t_inicio = time.perf_counter()
    size_segmento = max(1, n_iteraciones // 10)

    for it in range(n_iteraciones):
        if time.perf_counter() - t_inicio > limite_tiempo_s:
            break

        #seleccion adaptativa de operadores
        idx_d = _eleccion_ponderada(pesos_d, rng)
        idx_r = _eleccion_ponderada(pesos_r, rng)

        candidato = actual.clonar()

        n_asignados = sum(len(r) for r in candidato.routes)
        q = max(1, int(fraccion_elim * n_asignados))
        _OPS_DESTRUCCION[idx_d](candidato, q, rng)   #destruir
        _OPS_REPARACION[idx_r](candidato, rng)    #reparar

        puntaje = _PUNTAJE_RECHAZADO

        #actualizar mejor
        if candidato.ganancia_total() > mejor.ganancia_total():
            mejor = candidato.clonar()
            puntaje = _PUNTAJE_MEJOR

        #actualizar actual
        if candidato.ganancia_total() >= actual.ganancia_total():
            actual = candidato
            puntaje = max(puntaje, _PUNTAJE_MEJOR_ACT)

        #actualizar puntajes
        puntajes_d[idx_d] += puntaje
        puntajes_r[idx_r] += puntaje
        conteos_d[idx_d] += 1
        conteos_r[idx_r] += 1

        #actualizar pesos
        if (it + 1) % size_segmento == 0:
            for i in range(len(_OPS_DESTRUCCION)):
                if conteos_d[i] > 0:
                    pesos_d[i] = _DECAIMIENTO * pesos_d[i] + (1 - _DECAIMIENTO) * (puntajes_d[i] / conteos_d[i])
                    puntajes_d[i] = conteos_d[i] = 0
            for i in range(len(_OPS_REPARACION)):
                if conteos_r[i] > 0:
                    pesos_r[i] = _DECAIMIENTO * pesos_r[i] + (1 - _DECAIMIENTO) * (puntajes_r[i] / conteos_r[i])
                    puntajes_r[i] = conteos_r[i] = 0

    return mejor


#ruleta ponderada clásica
def _eleccion_ponderada(pesos: List[float], rng: random.Random) -> int:
    total = sum(pesos)

    #uniforme(0, suma_pesos), recorre hasta encontrar en que sector cayó
    r = rng.uniform(0, total)
    acumulado = 0.0
    for i, w in enumerate(pesos):
        acumulado += w
        if r <= acumulado:
            return i
    return len(pesos) - 1
