import math
import time
from typing import Dict, List, Optional, Tuple

from src.core import (
    Cliente, EstadoCamion, extraer_clientes,
    asignar_cercano_disponible as asignar_greedy, confirmar_asignacion, _insercion_factible,
    V_CAMIONES, DEPOT, T_INICIO, T_FINAL, NUM_CAMIONES, distancia, tiempo_viaje
)
from src.alns_solver import InicioRuta
from src.scenario_gen import generar_escenarios

"""
MDP + MSA (Multiple-Scenario Approach) con Política de Consenso y Distancia.

Arquitectura:
    Estado: posiciones/tiempos de camiones + clientes pendientes/asignados + tiempo transcurrido
    Acción: asignar nuevo cliente al camión k (o rechazar)
    Etapa: cada nueva llegada de cliente
    Recompensa: ganancia acumulada

Lógica de decisión por etapa:
    1. Muestrear N escenarios futuros con scenario_gen.py.
    
    2. Para cada escenario s y cada acción candidata a en {0,1,2,−1}:
        Q(a, s) = recompensa_inmediata(a) + rollout_greedy(futuro_s | estados_camion(a))
        donde estados_camion(a) = estados actuales actualizados por la acción a.
     
    3. Valor esperado: E[Q(a)] = promedio_s Q(a, s).
    
    4. Seleccionar acción entre las que tienen consenso >= umbral.
    Si ninguna supera el umbral, se usa argmax E[Q(a)]
    Empates decididos por varianza (diversidad): se prefiere la acción cuyo Q
    tenga mayor varianza entre escenarios (señal más robusta).

  5. consenso: fracción de escenarios en que cada acción fue la mejor (Sugerencia de Klapp).
"""


#---------------------- Parámetros ajustables (editar para afinar ejecución (ANTON)) -----------------------

#escenarios muestreados por etapa de decisión
N_ESCENARIOS = 50   #50 escenarios x 4 acciones candidatas = 200 rollouts

UMBRAL_CONSENSO = 0.30  #fracción mínima de votos para seleccionar una acción
MAX_CLIENTES_FUTUROS = 40    #max clientes futuros por escenario


#--------------------------- Helpers de estado MDP -----------------------------------------------

#reduccion de estado
def _camiones_a_inicios(camiones: List[EstadoCamion]) -> List[InicioRuta]:
    """
    Para alivianar carga computacional
    Intuición es que rollouts no necesitan historial de visitas, solo necesita:
        Donde esta cada camion
        Cuando queda libre
    """

    return [InicioRuta(c.truck_id, c.pos, c.avail_time) for c in camiones]

#proyeccion de una accion
def _avanzar_inicio(starts: List[InicioRuta], k: int, cliente: Cliente,
                   velocidad: float = V_CAMIONES, 
                   fin_horizonte: float = T_FINAL) -> Optional[List[InicioRuta]]:
    """
    Como quedaría el estado de los camiones si el camión k acepta a este cliente ahora?

    Retorna la lista de starts actualizada con el camión k comprometido con Cliente especifico.
    Retorna None si el compromiso es infactible.
    """
    sk = starts[k]
    t_viaje = tiempo_viaje(sk.pos, cliente.pos, velocidad)
    llegada = max(sk.time + t_viaje, cliente.ready)
    if llegada > cliente.deadline:
        return None    #identico a core.py
    salida = llegada + cliente.servicio
    if salida + tiempo_viaje(cliente.pos, DEPOT, velocidad) > fin_horizonte:
        return None   #identico a core.py
    nuevos_starts = list(starts)   #copia superficial de la lista para abaratar
    nuevos_starts[k] = InicioRuta(k, cliente.pos, salida)
    return nuevos_starts


#-------------------- Evaluacion de rollout greedy --------------------------------

#evaluador greedy de un escenario
def _simulacion_greedy(clientes_futuros: Dict[int, Cliente], starts: List[InicioRuta],
                    fin_horizonte: float = T_FINAL,
                    velocidad: float = V_CAMIONES) -> float:
    """
    Estima la ganancia futura usando una política greedy sobre los clientes futuros
    partiendo desde "starts". Retorna la ganancia total obtenida.

    Se usa greedy (no ALNS) para que el rollout sea consistente con la política
    online real, evitando sobreestimación del valor futuro.
    """
    camiones = [EstadoCamion(truck_id=s.truck_id, pos=s.pos, avail_time=s.time)
                for s in starts]
    clientes_ord = sorted(clientes_futuros.values(), key=lambda c: c.arrival)
    ganancia = 0.0
    for cliente in clientes_ord:
        k = asignar_greedy(cliente, camiones, fin_horizonte, velocidad)
        if k >= 0:
            confirmar_asignacion(cliente, camiones[k], velocidad)
            ganancia += cliente.profit
    return ganancia


#------------------------ Desempate por varianza -------------------------------
def _varianza(valores: List[float]) -> float:
    if len(valores) < 2:
        return 0.0
    mu = sum(valores) / len(valores)
    return sum((v - mu) ** 2 for v in valores) / len(valores)


#----------------------- Decisión MSA (valor esperado + consenso) -------------------------

def decidir_msa(cliente: Cliente, camiones: List[EstadoCamion],
        idx_instancia: int, n_procesados: int, base_semilla: int,
        num_camiones: int = NUM_CAMIONES, velocidad: float = V_CAMIONES,
        fin_horizonte: float = T_FINAL, depot: Tuple[float, float] = DEPOT,
        n_escenarios: int = N_ESCENARIOS, 
        umbral_consenso: float = UMBRAL_CONSENSO) -> Tuple[int, Dict[int, float], float]:
    """
    Ejecuta una etapa de decisión MSA usando rollouts greedy para evaluar escenarios

    Retorna:
        acción: truck_id (base 0) o -1 (rechazar)
        consenso: {accion: frac. de escenarios donde fue mejor}
        tiempo_s: tiempo de pared para esta llamada
    """

    t0 = time.perf_counter()
    starts = _camiones_a_inicios(camiones)

    #precalcular starts factibles por acción
    starts_por_accion: Dict[int, Optional[List[InicioRuta]]] = {-1: starts}  #rechazar: estado sin cambios
    for k in range(num_camiones):
        starts_por_accion[k] = _avanzar_inicio(starts, k, cliente, velocidad, fin_horizonte)

    acciones_factibles = [a for a, s in starts_por_accion.items() if s is not None]
    if not acciones_factibles or acciones_factibles == [-1]:
        elapsed = time.perf_counter() - t0
        return -1, {-1: 1.0}, elapsed  #si ningun camion puede atender al cliente, rechazo inmediatamente

    #muestrear escenarios futuros
    escenarios_futuros = generar_escenarios(idx_instancia=idx_instancia, t_actual=cliente.arrival,
        n_escenarios=n_escenarios, n_procesados=n_procesados,
        base_semilla=base_semilla, max_futuro=MAX_CLIENTES_FUTUROS)

    #Q(a,s) = recompensa_inmediata(a) + rollout_greedy(futuro_s | starts_por_accion[a])

    q_listas: Dict[int, List[float]] = {a: [] for a in acciones_factibles}   #Q(a,s) por escenario
    victorias: Dict[int, int] = {a: 0  for a in acciones_factibles}   #votos de consenso

    for s_idx, clientes_futuros in enumerate(escenarios_futuros):
        q_s: Dict[int, float] = {}

        for accion in acciones_factibles:
            ganancia_futura = _simulacion_greedy(clientes_futuros,
                                              starts_por_accion[accion],  #estado proyectado
                                              fin_horizonte,
                                              velocidad)
            
            inmediata = cliente.profit if accion >= 0 else 0.0   #profit inmediato
            q_s[accion] = inmediata + ganancia_futura
            q_listas[accion].append(q_s[accion])

        mejor_en_s = max(q_s, key=q_s.get)
        victorias[mejor_en_s] += 1

    #seleccion de accion
    n = len(escenarios_futuros)
    valor_esperado: Dict[int, float] = {a: sum(qs) / len(qs)
                                        for a, qs in q_listas.items() if qs
                                        }   #valor esperado
    
    consenso = {a: cnt / n for a, cnt in victorias.items() if cnt > 0}   #votos de consenso

    #selección: preferir acciones sobre el umbral de consenso
    #fallback a todas las factibles si ninguna lo supera.
    #desempate por varianza (mayor varianza = señal más discriminante).
    candidatos = {a: v for a, v in consenso.items() if v >= umbral_consenso}
    if not candidatos:
        candidatos = valor_esperado   #fallback

    mejor_accion = max(candidatos,
                       key=lambda a: (valor_esperado[a], _varianza(q_listas.get(a, [])))
                       )   #se maximiza V.E. y varianza solo para desempatar

    elapsed = time.perf_counter() - t0
    return mejor_accion, consenso, elapsed


#------------------------ Simulación completa de réplica --------------------------------

#orquestador
def simular_msa(
        datos_instancia, replica_idx: int,
        idx_instancia: int, num_camiones: int = NUM_CAMIONES,
        velocidad: float = V_CAMIONES, fin_horizonte: float = T_FINAL,
        depot: Tuple[float, float] = DEPOT, n_escenarios: int = N_ESCENARIOS,
        umbral_consenso: float = UMBRAL_CONSENSO, verbose: bool = False,
        on_customer=None) -> dict:
    """
    Ejecuta la política MSA sobre una réplica (EN LINEA)

    Retorna diccionario de métricas con claves:
        consenso_promedio, n_msa_commits, n_fallbacks_greedy,
        n_rechazos_msa, tiempo_promedio_escenarios (en s.)
    """
    clientes = extraer_clientes(datos_instancia, replica_idx)
    camiones = [EstadoCamion(truck_id=k) for k in range(num_camiones)]

    entregas_servidas = 0
    pickups_servidos = 0
    rechazados = 0
    n_commits_msa = 0
    n_fallbacks_greedy = 0
    n_rechazos_msa = 0
    puntajes_consenso = []
    tiempos_escenario = []

    for idx_cliente, cliente in enumerate(clientes):

        accion, consenso, elapsed = decidir_msa(cliente=cliente,
            camiones=camiones, idx_instancia=idx_instancia,
            n_procesados=idx_cliente, base_semilla=replica_idx*100_000+idx_cliente,
            num_camiones=num_camiones, velocidad=velocidad,
            fin_horizonte=fin_horizonte, depot=depot,
            n_escenarios=n_escenarios, umbral_consenso=umbral_consenso)
        
        #definiciones y appends iniciales
        tiempos_escenario.append(elapsed)
        mejor_puntaje = max(consenso.values()) if consenso else 0.0
        puntajes_consenso.append(mejor_puntaje)
        n_commits_msa += 1

        if on_customer:
            on_customer(idx_cliente, len(clientes))

        if verbose and idx_cliente % 20 == 0:
            es_alto = mejor_puntaje >= umbral_consenso
            print(f"cliente {idx_cliente:3d}/{len(clientes)}: "
                  f"accion={accion:+d}, consenso={mejor_puntaje:.2f}"
                  f"{'*' if es_alto else ' '}, t={elapsed:.3f}s")

        if accion == -1:
            rechazados += 1
            n_rechazos_msa += 1
            continue

        #verificar que la acción MSA sigue siendo factible fisicamente
        #si la accion MSA resulta infactible cuando se ejecuta, fallback a greedy
        nuevo_disp = _insercion_factible(camiones[accion], cliente, fin_horizonte, velocidad)
        if nuevo_disp is None:
            accion = asignar_greedy(cliente, camiones, fin_horizonte, velocidad)
            n_fallbacks_greedy += 1
            if accion == -1:
                rechazados += 1
                continue

        confirmar_asignacion(cliente, camiones[accion], velocidad)
        if cliente.is_pickup:
            pickups_servidos += 1
        else:
            entregas_servidas += 1

    #calculo distancia total
    dist_total = sum(c.total_distance for c in camiones)
    dist_total += sum(distancia(c.pos, depot) for c in camiones)   #distancia de regreso
    ganancia_total = sum(c.total_profit for c in camiones)
    total_servidos = entregas_servidas + pickups_servidos

    #conseno promedio final
    consenso_promedio = (sum(puntajes_consenso) / len(puntajes_consenso)
                         if puntajes_consenso else 0.0)

    return {"profit_total": ganancia_total,
            "total_aceptados": total_servidos,
            "total_rechazados": rechazados,
            "deliveries_aceptados": entregas_servidas,
            "pickups_aceptados": pickups_servidos,
            "distancia_total": dist_total,
            "rutas_camiones": [c.visited for c in camiones],
            "estados_camiones": camiones,
            
            #métricas específicas de MSA
            "score_consenso_promedio": consenso_promedio,
            "n_msa_commits": n_commits_msa,
            "n_fallbacks_greedy": n_fallbacks_greedy,
            "n_rechazos_msa": n_rechazos_msa,
            "tiempo_promedio_escenarios": (sum(tiempos_escenario) / len(tiempos_escenario)
                                           if tiempos_escenario else 0.0),
                                           }

