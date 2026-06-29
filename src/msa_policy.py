"""
MSA (Multiple Scenario Approach) — loop event-driven fiel al paper
Bent & Van Hentenryck (2004). Reemplaza la política VFA/rollout anterior.

Las funciones VFA (decidir_msa, rollout_realista, etc.) se conservan COMENTADAS
al final del archivo como baseline para comparación en Fase 5.
"""
import math
import time
from typing import Dict, List, Optional, Tuple

from src.core import (
    Cliente, EstadoCamion, extraer_clientes,
    confirmar_asignacion,
    V_CAMIONES, DEPOT, T_INICIO, T_FINAL, NUM_CAMIONES, distancia, tiempo_viaje,
)
from src.alns_solver import InicioRuta, SolucionALNS, resolver_alns, ldc, DEPOT_CID
from src.scenario_gen import generar_escenarios
from src.pool_msa import PoolMSA


# ══════════════════════════════════════════════════════════════════════════════
# Parámetros nombrados MSA (sin números mágicos en el loop)
# ══════════════════════════════════════════════════════════════════════════════

N_ESCENARIOS_INIT       = 15    # planes generados en t=T_INICIO
N_ESCENARIOS_VENTANA    = 1     # planes generados por evento (≤60s/réplica)
ALNS_ITER_PRESUPUESTO   = 30    # iteraciones ALNS por escenario (presupuesto real)
ALNS_TIEMPO_PRESUPUESTO = 999.0 # sin límite de tiempo — parada por iteraciones fijas
BASE_SEMILLA_MSA        = 42    # semilla raíz para reproducibilidad
PENALIDAD_CARGA_MSA     = 0.0        # MSA puro, fiel al paper (Fase 5 mide el sesgo)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers internos del loop
# ══════════════════════════════════════════════════════════════════════════════

def _t_next_departure(pool: PoolMSA, camiones: List[EstadoCamion],
                      pendientes: Dict[int, Cliente], t_actual: float) -> float:
    """Próximo LDT entre trucks con movimiento pendiente en σ*.
    Usa t_ultimo_departure (backward de _ruta_factible) para evitar ldt no-propagado.
    """
    if pool.distinguido is None:
        return float('inf')
    t_min = float('inf')
    for k, camion in enumerate(camiones):
        dest_cid = pool.distinguido.siguiente_destino(k, ldc(camion))
        if dest_cid is None or dest_cid == DEPOT_CID:
            continue
        if dest_cid not in pendientes:
            continue
        t_dep_k = pool.distinguido.t_ultimo_departure(k, t_actual)
        t_min = min(t_min, t_dep_k)
    return t_min


def _prefijo_comprometido(
        pool: PoolMSA, camiones: List[EstadoCamion],
        pendientes: Dict[int, Cliente], debug: bool
) -> Tuple[List[List[int]], List[InicioRuta], Dict[int, Cliente]]:
    """Extrae el prefijo comprometido de σ* para cada truck, calcula effective_starts
    y devuelve los clientes libres (pendientes NO en el prefijo).

    rutas_bloqueadas[k] = σ*.routes[k][idx_ldc+1:]  (lo que truck k aún no sirvió)
    effective_starts[k] = estado del truck k DESPUÉS de servir rutas_bloqueadas[k]
    free_pendientes      = pendientes sin los cids comprometidos

    Garantía I2 por construcción: el plan generado tendrá el mismo next-move
    que σ* para cada truck, porque el prefijo bloqueado es idéntico.
    """
    sigma = pool.distinguido
    rutas_bloqueadas: List[List[int]] = []
    effective_starts: List[InicioRuta] = []

    for k, camion in enumerate(camiones):
        ldc_k  = ldc(camion)
        ruta_k = sigma.routes[k] if sigma is not None else []

        if ldc_k == DEPOT_CID:
            prefijo = list(ruta_k)
        else:
            if ldc_k not in ruta_k:
                if debug:
                    raise AssertionError(
                        f"ldc({k})={ldc_k} no está en σ*.routes[{k}]={ruta_k}. "
                        "No debería ocurrir si I2 se mantiene; si salta, I2 tiene "
                        "un hueco — investigar (note: _succ es global, ldc podría "
                        "estar en la ruta de otro truck j≠k y aun así pasar compatible)."
                    )
                prefijo = []   # fallback mudo en no-debug
            else:
                idx    = ruta_k.index(ldc_k)
                prefijo = list(ruta_k[idx + 1:])

        rutas_bloqueadas.append(prefijo)

        # Effective start: estado del truck DESPUÉS de servir el prefijo
        pos, t = camion.pos, camion.avail_time
        for cid in prefijo:
            c = pendientes.get(cid)
            if c is None:
                break   # cliente del prefijo no en pendientes (ya servido o bug)
            viaje    = tiempo_viaje(pos, c.pos, V_CAMIONES)
            llegada  = max(t + viaje, c.ready)
            t        = llegada + c.servicio
            pos      = c.pos
        effective_starts.append(InicioRuta(k, pos, t))

    committed_cids  = {cid for rb in rutas_bloqueadas for cid in rb}
    free_pendientes = {cid: c for cid, c in pendientes.items()
                       if cid not in committed_cids}
    return rutas_bloqueadas, effective_starts, free_pendientes


def _ejecutar_departure(dest: Optional[int], k: int,
                        camiones: List[EstadoCamion],
                        pendientes: Dict[int, Cliente],
                        depot: Tuple[float, float],
                        velocidad: float,
                        t_final: float) -> None:
    """Aplica el movimiento físico del truck k según el valor retornado por
    on_vehicle_departure. Cuatro casos (A/B/C/D del plan):
      A: dest es cid real (>0)  → confirmar_asignacion, quitar de pendientes
      B: dest == DEPOT_CID      → actualizar posición/tiempo del truck a depot
      C: dest is None, pool vivo → truck idle, sin acción
      D: dest is None, pool vacío→ manejado por el caller (_regenerar_pool)
    """
    cam = camiones[k]
    if dest is None:
        return   # C o D — caller decide en D
    if dest == DEPOT_CID:
        # B: truck retorna al depósito
        viaje       = tiempo_viaje(cam.pos, depot, velocidad)
        t_retorno   = cam.avail_time + viaje
        cam.pos     = depot
        cam.avail_time = t_retorno
        return
    # A: movimiento a cliente real
    cliente = pendientes.get(dest)
    if cliente is None:
        return   # cliente ya servido o inconsistencia; ignorar
    confirmar_asignacion(cliente, cam, velocidad)
    del pendientes[dest]


def _regenerar_pool(pool: PoolMSA, camiones: List[EstadoCamion],
                    pendientes: Dict[int, Cliente],
                    idx_instancia: int, n_procesados: int, t: float,
                    fin_horizonte: float, velocidad: float,
                    depot: Tuple[float, float], next_sem) -> None:
    """Reconstruye el pool desde cero cuando quedó vacío.
    Genera N_ESCENARIOS_INIT planes nuevos e inicializa σ*.
    """
    pool.planes = []
    pool.distinguido = None
    starts_now = [InicioRuta(k, camiones[k].pos, camiones[k].avail_time)
                  for k in range(len(camiones))]
    for _ in range(N_ESCENARIOS_INIT):
        futuros = generar_escenarios(
            idx_instancia, t, 1, n_procesados,
            base_semilla=next_sem())[0]
        sigma = resolver_alns(
            {**pendientes, **futuros}, starts_now,
            n_iteraciones=ALNS_ITER_PRESUPUESTO,
            limite_tiempo_s=ALNS_TIEMPO_PRESUPUESTO,
            seed=next_sem(), depot=depot, t_final=fin_horizonte,
            velocidad=velocidad,
            penalidad_carga=PENALIDAD_CARGA_MSA
        ).proyectar()
        pool.agregar(sigma)
    pool._seleccionar(camiones)


def _verificar_invariantes(pool: PoolMSA, camiones: List[EstadoCamion],
                           check_I2: bool = True) -> None:
    """Chequeos de I1, I2, I3 en modo debug. O(|S_t| × K × L) — no usar en producción.

    check_I2=False: solo verifica I1. Úsase justo después de on_timeout y
    on_customer_request, donde I2 puede transitoriamente no mantenerse:
    - Después de on_timeout: ldc cambió por departures del tick anterior; I2 se
      re-establece en on_vehicle_departure y en la purga final del tick.
    - Después de on_customer_request: el cliente nuevo puede insertarse en trucks
      distintos en planes distintos; la diversidad es el propósito de MSA. I2 se
      re-establece en el siguiente on_vehicle_departure.
    check_I2=True (default): verifica I1 + I2 + I3. Úsase solo después de la
    purga final del tick (punto donde I2 se re-establece explícitamente).
    """
    for s in pool.planes:
        assert all(PoolMSA._es_factible_cola(s, k, camiones[k])
                   for k in range(len(camiones))), \
            "I1 violado: cola pendiente infactible en pool"
    if check_I2 and pool.distinguido is not None:
        assert all(s.compatible(pool.distinguido, camiones) for s in pool.planes), \
            "I2 violado: plan incompatible con σ* en pool (check post-purge)"
        M      = pool.matriz_consenso(camiones)
        f_star = pool.f_consenso(pool.distinguido, M, camiones)
        for s in pool.planes:
            assert f_star >= pool.f_consenso(s, M, camiones), \
                "I3 violado: σ* no maximiza f_t"


# ══════════════════════════════════════════════════════════════════════════════
# Loop principal
# ══════════════════════════════════════════════════════════════════════════════

def simular_msa(
        datos_instancia, replica_idx: int,
        idx_instancia: int,
        num_camiones: int = NUM_CAMIONES,
        velocidad: float = V_CAMIONES,
        fin_horizonte: float = T_FINAL,
        depot: Tuple[float, float] = DEPOT,
        modo: str = "consenso",      # "consenso" = MSAc, "distancia" = MSAd
        debug: bool = False,
        verbose: bool = False,
        collect_logs: bool = False,  # True → devuelve series temporales para figuras
        on_customer=None) -> dict:
    """
    Política MSA event-driven (Bent & Van Hentenryck 2004).

    Loop: avanza al próximo evento (min entre próxima llegada de cliente y próximo LDT
    de truck), aplica handlers en orden Timeout → Plan Generation → Customer Request →
    Vehicle Departure.

    Retorna dict base compatible con el baseline VFA + historial_pool=[(t, |S_t|)].
    """
    clientes  = extraer_clientes(datos_instancia, replica_idx)
    camiones  = [EstadoCamion(truck_id=k) for k in range(num_camiones)]
    pendientes: Dict[int, Cliente] = {}

    pool = PoolMSA(modo=modo)

    # Contador de semilla único: fluye por todo el loop incluida regeneración
    _sem = [BASE_SEMILLA_MSA]
    def _next_sem() -> int:
        s = _sem[0]; _sem[0] += 1; return s

    historial_pool: List[Tuple[float, int]] = []
    total_aceptados  = 0
    total_rechazados = 0
    n_procesados     = 0

    # Logs para figuras (solo si collect_logs=True)
    _log_utilidad:    List[Tuple[float, float]] = []   # (t, profit_acumulado)
    _log_tours:       List[Tuple[float, int, float]] = []  # (t, truck_id, dur_s)
    _log_decisiones:  List[Tuple[float, int, bool, float]] = []  # (t, cid, aceptado, profit)
    _profit_acum:     float = 0.0

    # ── Inicialización (t = T_INICIO) ─────────────────────────────────────────
    starts_init = [InicioRuta(k, depot, T_INICIO) for k in range(num_camiones)]
    for _ in range(N_ESCENARIOS_INIT):
        futuros = generar_escenarios(
            idx_instancia, T_INICIO, 1, 0,
            base_semilla=_next_sem())[0]
        sigma = resolver_alns(
            futuros, starts_init,
            n_iteraciones=ALNS_ITER_PRESUPUESTO,
            limite_tiempo_s=ALNS_TIEMPO_PRESUPUESTO,
            seed=_next_sem(), depot=depot, t_final=fin_horizonte,
            velocidad=velocidad,
            penalidad_carga=PENALIDAD_CARGA_MSA,
        ).proyectar()
        pool.agregar(sigma)
    pool._seleccionar(camiones)

    # ── Loop de eventos ───────────────────────────────────────────────────────
    idx_cli = 0
    t = T_INICIO

    while True:
        t_cli = clientes[idx_cli].arrival if idx_cli < len(clientes) else float('inf')
        t_dep = _t_next_departure(pool, camiones, pendientes, t)
        t_next = min(t_cli, t_dep)

        if t_next == float('inf'):
            break

        t = t_next
        historial_pool.append((t, len(pool.planes)))

        # ── P1: Timeout ────────────────────────────────────────────────────
        pool.on_timeout(camiones)

        if debug:
            _verificar_invariantes(pool, camiones, check_I2=False)

        # ── P2: Plan Generation ────────────────────────────────────────────
        for _ in range(N_ESCENARIOS_VENTANA):
            if pool.distinguido is not None:
                bl, _, free_p = _prefijo_comprometido(pool, camiones, pendientes, debug)
            else:
                bl    = [[] for _ in range(num_camiones)]
                free_p = dict(pendientes)

            # Starts REALES del truck (antes del prefijo comprometido).
            # _ruta_factible simula la cola completa = prefijo + clientes libres.
            starts_real = [InicioRuta(k, camiones[k].pos, camiones[k].avail_time)
                           for k in range(num_camiones)]

            # Committed customers deben estar en customers para que _ruta_factible
            # pueda hacer lookup al verificar el prefijo bloqueado.
            committed_cids     = {cid for route in bl for cid in route}
            committed_customers = {cid: pendientes[cid]
                                   for cid in committed_cids if cid in pendientes}

            futuros = generar_escenarios(
                idx_instancia, t, 1, n_procesados,
                base_semilla=_next_sem())[0]
            sigma = resolver_alns(
                {**free_p, **futuros, **committed_customers}, starts_real,
                n_iteraciones=ALNS_ITER_PRESUPUESTO,
                limite_tiempo_s=ALNS_TIEMPO_PRESUPUESTO,
                seed=_next_sem(), depot=depot, t_final=fin_horizonte,
                velocidad=velocidad,
                rutas_bloqueadas=bl,
                penalidad_carga=PENALIDAD_CARGA_MSA,
            ).proyectar()

            # Fix I2: prepend anchor ldc(k) a cada ruta para que compatible() funcione.
            # _succ(σ, ldc(k), k) necesita encontrar ldc(k) en routes[k].
            # El cliente ldc ya fue servido (no está en pendientes) → lo obtenemos
            # de camion.visited[-1]. customers se copia para no contaminar otros planes.
            sigma.customers = dict(sigma.customers)
            for k, camion in enumerate(camiones):
                ldc_cid = ldc(camion)
                if ldc_cid != DEPOT_CID:
                    sigma.customers[ldc_cid] = camion.visited[-1]
                    if not sigma.routes[k] or sigma.routes[k][0] != ldc_cid:
                        sigma.routes[k].insert(0, ldc_cid)

            pool.on_plan_generation(sigma, camiones)

        # ── P3: Customer Request ───────────────────────────────────────────
        while idx_cli < len(clientes) and clientes[idx_cli].arrival <= t:
            r = clientes[idx_cli]
            if on_customer:
                on_customer(idx_cli, len(clientes))
            aceptado = pool.on_customer_request(r, camiones)
            if aceptado:
                pendientes[r.cid] = r
                total_aceptados  += 1
                if collect_logs:
                    _profit_acum += r.profit
            else:
                total_rechazados += 1
            if collect_logs:
                _log_decisiones.append((t, r.cid, aceptado, r.profit))
                _log_utilidad.append((t, _profit_acum))
            n_procesados += 1
            idx_cli      += 1

        if debug:
            _verificar_invariantes(pool, camiones, check_I2=False)

        # ── P4: Vehicle Departure ──────────────────────────────────────────
        for k in range(num_camiones):
            # Regenerar pool si está vacío antes de intentar despachar
            if pool.distinguido is None:
                _regenerar_pool(pool, camiones, pendientes,
                                idx_instancia, n_procesados, t,
                                fin_horizonte, velocidad, depot, _next_sem)

            if pool.distinguido is None:
                continue

            dest_cid = pool.distinguido.siguiente_destino(k, ldc(camiones[k]))
            if dest_cid is None or dest_cid == DEPOT_CID:
                # Caso B (DEPOT_CID): mover truck al depósito si avail_time ≤ t
                if dest_cid == DEPOT_CID and camiones[k].avail_time <= t + 1.0:
                    _ejecutar_departure(DEPOT_CID, k, camiones, pendientes,
                                        depot, velocidad, fin_horizonte)
                continue

            t_dep_k = pool.distinguido.t_ultimo_departure(k, t)
            if t_dep_k > t + 1.0:
                continue   # el truck puede esperar; LDT no alcanzado aún

            # Truck k debe partir ahora
            dest = pool.on_vehicle_departure(k, camiones)

            if dest is None and pool.distinguido is None:
                # D: pool quedó vacío; se regenera en la próxima iteración P4 del mismo tick
                _regenerar_pool(pool, camiones, pendientes,
                                idx_instancia, n_procesados, t,
                                fin_horizonte, velocidad, depot, _next_sem)
                continue

            t_antes = camiones[k].avail_time  # tiempo antes del departure
            _ejecutar_departure(dest, k, camiones, pendientes,
                                depot, velocidad, fin_horizonte)
            if collect_logs and dest is not None and dest != DEPOT_CID:
                dur = camiones[k].avail_time - t_antes  # duración del servicio+viaje
                _log_tours.append((t, k, dur))

            if verbose:
                print(f"t={t:.0f}  truck {k} → {dest}  |S_t|={len(pool.planes)}")

        # Purga final de I2: múltiples departures en el mismo tick actualizan ldc
        # secuencialmente; el pool puede quedar con planes incompatibles con el
        # σ* final bajo los ldc actualizados. Se re-purga para restaurar I2.
        if pool.distinguido is not None:
            pool._purgar(camiones)
            if pool.planes:
                pool._seleccionar(camiones)
            else:
                pool.distinguido = None

        if debug:
            _verificar_invariantes(pool, camiones, check_I2=True)  # post-purge final

    # ── Métricas finales ───────────────────────────────────────────────────────
    dist_total   = sum(c.total_distance for c in camiones)
    dist_total  += sum(distancia(c.pos, depot) for c in camiones)
    profit_total = sum(c.total_profit for c in camiones)

    resultado = {
        "profit_total":      profit_total,
        "total_aceptados":   total_aceptados,
        "total_rechazados":  total_rechazados,
        "distancia_total":   dist_total,
        "rutas_camiones":    [c.visited for c in camiones],
        "estados_camiones":  camiones,
        "historial_pool":    historial_pool,
        "score_consenso_promedio":    None,
        "n_msa_commits":             None,
        "n_fallbacks_greedy":        None,
        "n_rechazos_msa":            None,
        "tiempo_promedio_escenarios": None,
    }
    if collect_logs:
        resultado["log_utilidad"]   = _log_utilidad    # [(t, profit_acum)]
        resultado["log_tours"]      = _log_tours        # [(t, truck_id, dur_s)]
        resultado["log_decisiones"] = _log_decisiones   # [(t, cid, aceptado, profit)]
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# BASELINE VFA (conservado como referencia para Fase 5)
# ══════════════════════════════════════════════════════════════════════════════
#
# Las funciones a continuación implementan la política VFA/rollout original.
# NO se usan en simular_msa — son baseline para comparación en Fase 5.
# Se conservan comentadas para evitar confusión con el loop MSA activo.
#
# from src.core import asignar_cercano_disponible as asignar_greedy, _insercion_factible
#
# N_ESCENARIOS      = 50
# UMBRAL_CONSENSO   = 0.70
# ALPHA_RESERVA     = 1.0
# MAX_CLIENTES_FUTUROS = 100
# ALNS_ITER         = 50
# ALNS_TLIMIT       = 0.5
# BASE_SEMILLA      = 2122
# PICKUP_PENALTY    = 0.0
#
# def _camiones_a_inicios(camiones):
#     return [InicioRuta(c.truck_id, c.pos, c.avail_time) for c in camiones]
#
# def _avanzar_inicio(starts, k, cliente, velocidad=V_CAMIONES, fin_horizonte=T_FINAL):
#     sk = starts[k]
#     t_viaje = tiempo_viaje(sk.pos, cliente.pos, velocidad)
#     llegada = max(sk.time + t_viaje, cliente.ready)
#     if llegada > cliente.deadline: return None
#     salida = llegada + cliente.servicio
#     if salida + tiempo_viaje(cliente.pos, DEPOT, velocidad) > fin_horizonte: return None
#     nuevos = list(starts); nuevos[k] = InicioRuta(k, cliente.pos, salida)
#     return nuevos
#
# def rollout_realista(starts, clientes_futuros, fin_horizonte=T_FINAL, velocidad=V_CAMIONES):
#     from src.core import asignar_cercano_disponible as ag
#     camiones = [EstadoCamion(truck_id=s.truck_id, pos=s.pos, avail_time=s.time) for s in starts]
#     for cliente in sorted(clientes_futuros.values(), key=lambda c: c.arrival):
#         k = ag(cliente, camiones, fin_horizonte, velocidad)
#         if k >= 0:
#             confirmar_asignacion(cliente, camiones[k], velocidad)
#     return sum(c.total_profit for c in camiones)
#
# def decidir_msa(cliente, camiones, idx_instancia, n_procesados, base_semilla,
#                 num_camiones=NUM_CAMIONES, velocidad=V_CAMIONES,
#                 fin_horizonte=T_FINAL, depot=DEPOT,
#                 n_escenarios=N_ESCENARIOS, umbral_consenso=UMBRAL_CONSENSO,
#                 alpha_reserva=ALPHA_RESERVA):
#     """Política VFA original (costo de oportunidad + rollout). BASELINE para Fase 5."""
#     ... (ver git history)
#
# def simular_msa_vfa(datos_instancia, replica_idx, idx_instancia, ...):
#     """Versión VFA original de simular_msa. BASELINE para Fase 5."""
#     ... (ver git history)
