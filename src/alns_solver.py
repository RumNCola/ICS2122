import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from src.core import Cliente, EstadoCamion, tiempo_viaje, DEPOT, T_FINAL, V_CAMIONES

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

#----------- Constantes MSA ---------------------------

DEPOT_CID: int = 0
# cid >= 0: cliente conocido (instancia real)
# cid <  0: cliente futuro muestreado por scenario_gen (se purga en proyectar())

CID_NO_EN_PLAN: int = -(2**31)
# Sentinel: cid no aparece en ninguna ruta del plan.
# _succ/_pred lo retornan cuando buscan un cid y no lo encuentran.
# compatible() trata cualquier aparición del sentinel como incompatibilidad.


def ldc(camion: EstadoCamion) -> int:
    """Último cliente del que partió el vehículo (ldc, MSA_SPEC Sección 4).
    Retorna DEPOT_CID si el camión no ha servido ningún cliente todavía.
    """
    if camion.visited:
        return camion.visited[-1].cid
    return DEPOT_CID


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
        clone = SolucionALNS(
            routes = [list(r) for r in self.routes],
            sin_asignar = set(self.sin_asignar),
            customers = self.customers,  #referencia compartida de solo lectura
            starts = self.starts,
            depot = self.depot,
            t_final = self.t_final,
            velocidad = self.velocidad,
        )
        # Propagar longitud del prefijo bloqueado para que repair lo respete
        clone._prefijo_len = getattr(self, '_prefijo_len', None)
        return clone

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
    def mejor_insercion(self, cid: int,
                        penalidad_carga: float = 0.0) -> Tuple[int, int, float]:
        """
        Prueba todas las posiciones posibles en todos los camiones.
        penalidad_carga > 0 sesga hacia rutas cortas (balance de carga):
          costo_ajustado = costo_real + penalidad_carga * len(ruta[k])
        Retorna (camion, posicion, costo_REAL) — el costo ajustado solo se usa
        para elegir; el retorno es siempre el delta de tiempo real.
        (-1, -1, inf) si ninguna posición es factible.
        """
        mejor_k   = -1
        mejor_pos = -1
        mejor_adj = math.inf   # costo ajustado (para elegir)

        prefijo_len = getattr(self, '_prefijo_len', None)

        for k in range(len(self.routes)):
            penalty  = penalidad_carga * len(self.routes[k])
            min_pos  = prefijo_len[k] if prefijo_len else 0
            for p in range(min_pos, len(self.routes[k]) + 1):
                c = self.costo_insercion(k, p, cid)
                if c < math.inf:
                    c_adj = c + penalty
                    if c_adj < mejor_adj:
                        mejor_adj = c_adj
                        mejor_k   = k
                        mejor_pos = p

        real = (self.costo_insercion(mejor_k, mejor_pos, cid)
                if mejor_k >= 0 else math.inf)
        return mejor_k, mejor_pos, real

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

    #----------- Métodos MSA (MSA_SPEC Secciones 3-4) ---------------------------

    def siguiente_destino(self, k: int, ldc_cid: int) -> Optional[int]:
        """Próximo cid al que debe moverse el vehículo k partiendo desde ldc_cid.

        Retorna None solo si ldc_cid == DEPOT_CID y routes[k] está vacío
        (vehículo sin asignaciones; distinto de 'retornando al depósito' que sería DEPOT_CID).
        En todos los demás casos delega a _succ.
        """
        if ldc_cid == DEPOT_CID and not self.routes[k]:
            return None
        return _succ(self, ldc_cid, v=k)

    def proyectar(self) -> "SolucionALNS":
        """Retorna σ⁻: plan con todos los cid < 0 eliminados de las rutas (MSA_SPEC §2).

        Los cid >= 0 conservan su orden relativo. Rutas que quedan completamente
        vacías tras remover negativos permanecen como [] (no se eliminan).
        customers se comparte por referencia de solo lectura (misma política que clonar()).
        """
        nuevas_rutas = [[cid for cid in ruta if cid >= 0] for ruta in self.routes]
        nueva_sin_asignar = {cid for cid in self.sin_asignar if cid >= 0}
        return SolucionALNS(
            routes=nuevas_rutas,
            sin_asignar=nueva_sin_asignar,
            customers=self.customers,   # referencia compartida; cid<0 quedan huérfanos, inofensivo
            starts=self.starts,
            depot=self.depot,
            t_final=self.t_final,
            velocidad=self.velocidad,
        )

    def t_ultimo_departure(self, k: int, t_actual: float) -> float:
        """Último instante en que el truck k puede partir hacia routes[k] sin
        inducir infactibilidad en la cola completa.

        Opción (b) del plan: binary search sobre factible_desde(t), que replica
        exactamente _ruta_factible(k) con starts[k].time = t sin mutar self.starts
        (cero aliasing sobre la lista compartida por clonar/proyectar).

        Monotonicidad: aumentar t solo puede retrasar llegadas (max(t+travel, ready)
        es no-decreciente en t) → feasibility es monótona decreciente → binary search
        válido.

        Retorna:
          +inf    si routes[k] está vacía (truck sin compromisos, no dispara VD).
          t_actual si ya vencido (factible_desde(lo) = False → despachar ahora).
          hi      si destino sin presión temporal (holgado); no se hace binary search.
          lo ∈ [t_actual, T_FINAL]  en el caso normal.
        """
        if not self.routes[k]:
            return float('inf')

        pos0 = self.starts[k].pos
        lo   = max(self.starts[k].time, t_actual)
        hi   = self.t_final

        def factible_desde(t: float) -> bool:
            """_ruta_factible(k) con starts[k].time = t. Sin mutación de self.starts."""
            pos, curr = pos0, t
            for cid in self.routes[k]:
                c       = self.customers[cid]
                t_viaje = tiempo_viaje(pos, c.pos, self.velocidad)
                llegada = max(curr + t_viaje, c.ready)
                if llegada > c.deadline:
                    return False
                curr = llegada + c.servicio
                pos  = c.pos
            return curr + tiempo_viaje(pos, self.depot, self.velocidad) <= self.t_final

        if not factible_desde(lo):
            return t_actual   # ya vencido — despachar ahora

        # Blindaje: destino sin presión temporal (caso holgado); no se hace binary search
        if factible_desde(hi):
            return hi

        PRECISION = 1.0   # 1 segundo
        while hi - lo > PRECISION:
            mid = (lo + hi) / 2.0
            if factible_desde(mid):
                lo = mid
            else:
                hi = mid
        return lo

    def compatible(self, sigma_star: "SolucionALNS",
                   camiones: List[EstadoCamion]) -> bool:
        """True si self concuerda con sigma_star en el siguiente destino de cada vehículo.

        Implementa COMPATIBLE del MSA_SPEC Sección 4: para cada vehículo k compara
        _succ(self, ldc(k)) contra _succ(sigma_star, ldc(k)).
        Si _succ retorna CID_NO_EN_PLAN en cualquiera de los dos planes → False.
        """
        for k, camion in enumerate(camiones):
            r = ldc(camion)
            a = _succ(self, r, k)
            b = _succ(sigma_star, r, k)
            if CID_NO_EN_PLAN in (a, b):
                return False
            if a != b:
                return False
        return True


#----------- Funciones libres MSA: sucesor y predecesor en plan ---------------------------

def _succ(sigma: SolucionALNS, r: int, v: Optional[int] = None) -> int:
    """Sucesor de cid r en el plan sigma (MSA_SPEC Secciones 3-4).

    r != DEPOT_CID: busca r en TODAS las rutas de sigma; retorna el siguiente cid,
                    DEPOT_CID si r es el último de su ruta, CID_NO_EN_PLAN si r no
                    aparece en ninguna ruta. El parámetro v se ignora en este caso.
    r == DEPOT_CID: v es requerido (vehículo cuya ruta consultar); retorna
                    sigma.routes[v][0] si la ruta no está vacía, DEPOT_CID si lo está.
    """
    if r == DEPOT_CID:
        if v is None:
            raise ValueError("_succ con r=DEPOT_CID requiere v explícito (índice de vehículo)")
        ruta = sigma.routes[v]
        return ruta[0] if ruta else DEPOT_CID

    for ruta in sigma.routes:
        for i, cid in enumerate(ruta):
            if cid == r:
                return ruta[i + 1] if i + 1 < len(ruta) else DEPOT_CID
    return CID_NO_EN_PLAN


def _pred(sigma: SolucionALNS, r: int, v: Optional[int] = None) -> int:
    """Predecesor de cid r en el plan sigma (MSA_SPEC Secciones 3-4).

    r == DEPOT_CID: lanza ValueError — el depósito es inicio y fin de ruta,
                    no tiene predecesor único. MSA nunca necesita esto; fallar fuerte
                    para no enmascarar un bug de lógica en el caller.
    r != DEPOT_CID: busca r en TODAS las rutas de sigma; retorna el cid anterior,
                    DEPOT_CID si r es el primero de su ruta, CID_NO_EN_PLAN si r no
                    aparece en ninguna ruta. El parámetro v se ignora.
    """
    if r == DEPOT_CID:
        raise ValueError(
            "pred(DEPOT_CID) es indefinido: el depósito es inicio y fin de ruta, "
            "no tiene predecesor único en el plan. "
            "Si llegaste aquí hay un bug de lógica en el caller."
        )

    for ruta in sigma.routes:
        for i, cid in enumerate(ruta):
            if cid == r:
                return ruta[i - 1] if i > 0 else DEPOT_CID
    return CID_NO_EN_PLAN


#------------------- Construcción ---------------------------------------

#solucion inicial
def _construir_greedy(customers: Dict[int, Cliente], starts: List[InicioRuta],
                      depot: Tuple[float, float], fin_horizonte: float,
                      velocidad: float, rng: random.Random,
                      rutas_bloqueadas: Optional[List[List[int]]] = None,
                      penalidad_carga: float = 0.0) -> SolucionALNS:
    """
    Construye una solución inicial insertando clientes de a uno,
    ordenados por deadline (más ajustado primero) con desempate aleatorio.

    rutas_bloqueadas[k] = prefijo comprometido del truck k; estos cids ya están
    en routes[k] y no entran en sin_asignar. Solo los cids libres son insertados.
    penalidad_carga > 0 sesga mejor_insercion hacia balance de carga entre trucks.
    """
    n_camiones = len(starts)
    if rutas_bloqueadas is None:
        rutas_bloqueadas = [[] for _ in range(n_camiones)]

    locked_cids = {cid for rb in rutas_bloqueadas for cid in rb}

    sol = SolucionALNS(routes      = [list(rb) for rb in rutas_bloqueadas],
                       sin_asignar = set(customers.keys()) - locked_cids,
                       customers   = customers,
                       starts      = starts,
                       depot       = depot,
                       t_final     = fin_horizonte,
                       velocidad   = velocidad,
                       )
    # Almacenar longitud del prefijo bloqueado para que mejor_insercion y
    # los operadores de destrucción no toquen posiciones dentro del prefijo.
    sol._prefijo_len = [len(rb) for rb in rutas_bloqueadas]

    #clientes reales (cid >= 0) antes que futuros muestreados (cid < 0)
    free_cids = [cid for cid in customers if cid not in locked_cids]
    orden = sorted(free_cids,
                   key=lambda cid: (
                       0 if cid >= 0 else 1,
                       customers[cid].deadline,
                       rng.random()
                   ))

    for cid in orden:
        k, p, costo = sol.mejor_insercion(cid, penalidad_carga=penalidad_carga)
        if k >= 0:
            sol.routes[k].insert(p, cid)
            sol.sin_asignar.discard(cid)

    return sol


#----------------------- Destrucción -----------------------------------

#eliminación random
def eliminacion_aleatoria(sol: SolucionALNS, q: int, rng: random.Random,
                          prefijo_len: Optional[List[int]] = None) -> List[int]:
    """
    Elimina q clientes al azar de posiciones no bloqueadas (>= prefijo_len[k]).
    Retorna lista de cids eliminados.
    """
    asignados = [
        (k, p, cid)
        for k, ruta in enumerate(sol.routes)
        for p, cid in enumerate(ruta)
        if prefijo_len is None or p >= prefijo_len[k]
    ]
    if not asignados:
        return []
    muestra = rng.sample(asignados, min(q, len(asignados)))
    eliminados = []
    for k, p, cid in sorted(muestra, key=lambda x: (x[0], -x[1])):
        sol.routes[k].pop(p)
        sol.sin_asignar.add(cid)
        eliminados.append(cid)
    return eliminados


def eliminacion_peor(sol: SolucionALNS, q: int, rng: random.Random,
                     prefijo_len: Optional[List[int]] = None) -> List[int]:
    """
    Elimina los q clientes con peor relación costo/ganancia de posiciones no
    bloqueadas (>= prefijo_len[k]). Ruido pequeño para aleatorizar.
    """
    puntuados = []
    for k, ruta in enumerate(sol.routes):
        min_p = prefijo_len[k] if prefijo_len else 0
        for p in range(min_p, len(ruta)):
            cid      = ruta[p]
            delta    = sol.delta_eliminacion(k, p)
            ganancia = sol.customers[cid].profit
            puntaje  = -delta / (ganancia + 1e-9)
            puntuados.append((puntaje + rng.uniform(0, 0.1), k, p, cid))

    puntuados.sort(reverse=True)

    eliminados = []
    a_eliminar = [(k, p, cid) for _, k, p, cid in puntuados[:q]]
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
_PUNTAJE_ACEPTADO  = 1   #aceptado por RRT pese a ser peor que actual
_PUNTAJE_RECHAZADO = 0

_DECAIMIENTO = 0.8  #factor de decaimiento para pesos adaptativos

def resolver_alns(customers: Dict[int, Cliente], starts: List[InicioRuta],
               n_iteraciones: int = 100, fraccion_elim: float = 0.20,
               limite_tiempo_s: float = 2.0, seed: int = 0,
               depot: Tuple[float, float] = DEPOT, t_final: float = T_FINAL,
               velocidad: float = V_CAMIONES,
               umbral_rrt_inicial: float = 2.0,
               rutas_bloqueadas: Optional[List[List[int]]] = None,
               penalidad_carga: float = 0.0) -> SolucionALNS:
    """
    Ejecuta ALNS. Retorna mejor solución.

    Nuevos parámetros MSA (aditivos; None / 0.0 preservan comportamiento original):
        rutas_bloqueadas: prefijos comprometidos por truck — no se destruyen ni
                          se reasignan. routes[k][:len(rutas_bloqueadas[k])] es fijo.
        penalidad_carga:  sesgo de balance en mejor_insercion (0 = desactivado).
    """
    n = len(starts)
    if rutas_bloqueadas is None:
        rutas_bloqueadas = [[] for _ in range(n)]

    prefijo_len = [len(rb) for rb in rutas_bloqueadas]  # longitud del prefijo por truck

    if not customers and all(len(rb) == 0 for rb in rutas_bloqueadas):
        return SolucionALNS([[] for _ in range(n)], set(), customers,
                            starts, depot, t_final, velocidad)

    # Con rutas bloqueadas pero sin clientes libres: plan = solo prefijos
    if not customers:
        return SolucionALNS([list(rb) for rb in rutas_bloqueadas], set(), customers,
                            starts, depot, t_final, velocidad)

    rng = random.Random(seed)

    actual = _construir_greedy(customers, starts, depot, t_final, velocidad, rng,
                               rutas_bloqueadas=rutas_bloqueadas,
                               penalidad_carga=penalidad_carga)
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
        _OPS_DESTRUCCION[idx_d](candidato, q, rng, prefijo_len)   #destruir
        _OPS_REPARACION[idx_r](candidato, rng)                     #reparar

        puntaje = _PUNTAJE_RECHAZADO
        cand_gain = candidato.ganancia_total()
        act_gain = actual.ganancia_total()
        # umbral decays linearly from umbral_rrt_inicial to ~0 over n_iteraciones
        umbral = umbral_rrt_inicial * (1.0 - it / n_iteraciones)

        #actualizar mejor (estricto, sin umbral)
        if cand_gain > mejor.ganancia_total():
            mejor = candidato.clonar()
            puntaje = _PUNTAJE_MEJOR

        #actualizar actual (RRT: acepta si no cae más de umbral respecto al actual)
        if cand_gain >= act_gain - umbral:
            actual = candidato
            if cand_gain >= act_gain:
                puntaje = max(puntaje, _PUNTAJE_MEJOR_ACT)
            else:
                puntaje = max(puntaje, _PUNTAJE_ACEPTADO)

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
