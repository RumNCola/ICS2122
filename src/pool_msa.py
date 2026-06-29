"""
Pool S_t de planes MSA, cálculo de función de consenso y handlers de eventos.
(MSA_SPEC Secciones 1 y 2)

Estructura M_t: dict[int, Counter[int]]
  M[v][r] = #{σ ∈ S_t | _succ(σ, ldc(v), v) == r}

¿Por qué Counter y no ndarray?
  - Los cid son enteros arbitrarios (no densos); ndarray requeriría un mapeo cid→índice
    con bookkeeping extra.
  - Counter es esparso: accesos a claves ausentes retornan 0, sin inicialización explícita
    del espacio de cids.
  - Pool pequeño (O(10–100) planes, 3 vehículos): sin ganancia de rendimiento con numpy.
  - M[v][r] mapea directamente a dict[v][Counter[r]], sin traducción conceptual.

Desempate en seleccionar_distinguido (jerarquía completa, documentada):
  1. f descendente       — argmax del score de consenso
  2. costo total ascendente — menor suma de _tiempo_retorno_ruta; determinista y
                            semánticamente coherente (no depende del orden de inserción)
  3. tupla de rutas ascendente — tuple(tuple(r) for r in sigma.routes); función pura
                            del contenido del plan; garantía de reproducibilidad en Fase 5
"""

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

from src.alns_solver import (
    CID_NO_EN_PLAN, DEPOT_CID, InicioRuta, SolucionALNS, _succ, ldc,
)
from src.core import Cliente, EstadoCamion


class PoolMSA:
    def __init__(self, modo: str = "consenso") -> None:
        """
        modo="consenso" → selecciona σ* por función de consenso (MSAc).
        modo="distancia" → selecciona σ* por menor costo total de rutas (MSAd).
        El switch es transparente a todos los handlers (usan _seleccionar).
        """
        self.planes: List[SolucionALNS] = []
        self.distinguido: Optional[SolucionALNS] = None
        self.modo = modo

    def agregar(self, sigma: SolucionALNS) -> None:
        self.planes.append(sigma)

    # ── M_t ─────────────────────────────────────────────────────────────────

    def matriz_consenso(self, camiones: List[EstadoCamion]) -> Dict[int, Counter]:
        """M[v][r] = #{σ | _succ(σ, ldc(v), v) == r}.

        Si _succ retorna CID_NO_EN_PLAN el plan no contribuye al conteo de v:
        semánticamente, un plan donde ldc(v) está ausente no tiene voto válido
        para ese vehículo y no debe sesgar el consenso.
        """
        M: Dict[int, Counter] = {v: Counter() for v in range(len(camiones))}
        for sigma in self.planes:
            for v, camion in enumerate(camiones):
                r_next = _succ(sigma, ldc(camion), v)
                if r_next != CID_NO_EN_PLAN:
                    M[v][r_next] += 1
        return M

    # ── f_t ─────────────────────────────────────────────────────────────────

    def f_consenso(self, sigma: SolucionALNS,
                   M: Dict[int, Counter],
                   camiones: List[EstadoCamion]) -> int:
        """f_t(σ) = Σ_v M[v][_succ(σ, ldc(v), v)]  (MSA_SPEC §2).

        CID_NO_EN_PLAN: Counter retorna 0 — contribución nula, correcto semánticamente.
        """
        return sum(
            M[v][_succ(sigma, ldc(camion), v)]
            for v, camion in enumerate(camiones)
        )

    # ── Costo total (MSAd criterion) ─────────────────────────────────────────

    def _costo_total(self, sigma: SolucionALNS) -> float:
        """Σ_k _tiempo_retorno_ruta(k) — menor valor = rutas más cortas (MSAd)."""
        return sum(sigma._tiempo_retorno_ruta(k) for k in range(len(sigma.routes)))

    # ── Clave de desempate ────────────────────────────────────────────────────

    def _clave_consenso(self, sigma: SolucionALNS,
                        M: Dict[int, Counter],
                        camiones: List[EstadoCamion]) -> Tuple:
        """Jerarquía: f desc → costo asc → tupla de rutas asc.  min() ≡ argmax f."""
        return (
            -self.f_consenso(sigma, M, camiones),
            self._costo_total(sigma),
            tuple(tuple(r) for r in sigma.routes),
        )

    # ── seleccionar_distinguido (MSAc) ───────────────────────────────────────

    def seleccionar_distinguido(self, camiones: List[EstadoCamion]) -> SolucionALNS:
        """argmax f_consenso sobre el pool. Actualiza self.distinguido."""
        if not self.planes:
            raise ValueError("seleccionar_distinguido: pool vacío")
        M = self.matriz_consenso(camiones)
        self.distinguido = min(
            self.planes,
            key=lambda s: self._clave_consenso(s, M, camiones),
        )
        return self.distinguido

    # ── Dispatcher MSAc / MSAd ────────────────────────────────────────────────

    def _seleccionar(self, camiones: List[EstadoCamion]) -> SolucionALNS:
        """Selecciona σ* según self.modo. Todos los handlers usan este método
        para que el switch MSAc/MSAd sea transparente al loop de Fase 4."""
        if self.modo == "distancia":
            return self.seleccionar_distinguido_distancia()
        return self.seleccionar_distinguido(camiones)

    # ── seleccionar_distinguido_distancia (MSAd) ─────────────────────────────

    def seleccionar_distinguido_distancia(self) -> SolucionALNS:
        """argmin costo total de rutas. Actualiza self.distinguido.

        Desempate: tupla de rutas ascendente (coherente con criterio de tercer nivel
        de MSAc; el switch MSAc/MSAd es transparente al llamador).
        """
        if not self.planes:
            raise ValueError("seleccionar_distinguido_distancia: pool vacío")
        self.distinguido = min(
            self.planes,
            key=lambda s: (
                self._costo_total(s),
                tuple(tuple(r) for r in s.routes),
            ),
        )
        return self.distinguido

    # ══════════════════════════════════════════════════════════════════════════
    # Handlers de eventos MSA (MSA_SPEC §1)
    # Orden de prioridad cuando coinciden: Timeout → Plan Generation →
    # Customer Request → Vehicle Departure
    # ══════════════════════════════════════════════════════════════════════════

    # ── Privado: factibilidad excluyendo el anchor ldc ───────────────────────

    @staticmethod
    def _es_factible_cola(sigma: SolucionALNS, k: int,
                          camion: EstadoCamion) -> bool:
        """Verifica I1 excluyendo el anchor ldc(camion) al principio de routes[k].

        Los planes mantienen el cliente ya servido (ldc) como primer elemento de
        routes[k] para que _succ(σ, ldc, k) funcione en compatible(). Pero si
        _ruta_factible lo re-chequea desde starts[k].time (= avail_time = service_end),
        falla porque service_end > ldc.deadline — el cliente ya fue servido.

        Fix: si routes[k][0] == ldc(camion), se salta ese primer elemento y sólo
        se verifica la cola pendiente (routes[k][1:]). Cuando ldc == DEPOT_CID
        (ningún cliente servido aún) se verifica la ruta completa.
        """
        ldc_cid = ldc(camion)
        ruta    = sigma.routes[k]
        if ldc_cid != DEPOT_CID:
            # ldc puede estar en cualquier posición de la ruta (no solo pos=0)
            # cuando el plan acumula múltiples anchors de clientes ya servidos.
            # Buscamos su índice y saltamos todo hasta él (inclusive).
            idx = next((i for i, c in enumerate(ruta) if c == ldc_cid), -1)
            if idx >= 0:
                ruta = ruta[idx + 1:]   # verificar solo la cola pendiente
        return sigma._ruta_factible(k, ruta)

    # ── Privado: purga I1 ∧ I2 ───────────────────────────────────────────────

    def _purgar(self, camiones: List[EstadoCamion]) -> None:
        """PURGAR_POOL (MSA_SPEC §1): elimina planes que violan I1 (factibilidad)
        o I2 (compatibilidad con σ* actual).
        Usa _es_factible_cola para I1 (evita falsos negativos por anchor ldc).
        Si self.distinguido is None, solo purga por I1.
        Usada exclusivamente por on_plan_generation antes de agregar el nuevo plan.
        """
        if self.distinguido is None:
            self.planes = [
                s for s in self.planes
                if all(self._es_factible_cola(s, k, camiones[k])
                       for k in range(len(camiones)))
            ]
            return
        self.planes = [
            s for s in self.planes
            if (all(self._es_factible_cola(s, k, camiones[k])
                    for k in range(len(camiones)))
                and s.compatible(self.distinguido, camiones))
        ]

    # ── Privado: wrapper de inserción para on_customer_request ────────────────

    @staticmethod
    def _insertar_cliente(sigma: SolucionALNS, r: Cliente) -> Tuple[int, int, float]:
        """Precondición de mejor_insercion: añade r.cid a sigma.customers (que puede
        ser un dict compartido por referencia). Llama mejor_insercion(r.cid).
        NO modifica routes — el caller aplica la inserción si cost < inf.
        Retorna (k, pos, cost) o (-1, -1, inf).

        Verificación empírica (tests/test_mejor_insercion_caract.py, 6/6 en verde):
        mejor_insercion es correcto en lógica de inserción y detección de factibilidad.
        El bug "esto esta cagando la rutina" aplica al loop ALNS, no a este uso.
        """
        sigma.customers[r.cid] = r
        k, pos, cost = sigma.mejor_insercion(r.cid)
        return k, pos, cost

    # ── Regla 1: Timeout ─────────────────────────────────────────────────────

    def on_timeout(self, camiones: List[EstadoCamion]) -> None:
        """Timeout (MSA_SPEC §1 Regla 1):
        Actualiza starts de cada plan al estado real de los camiones (LISTA NUEVA
        en cada plan — precondición A1: nunca mutar in-place).
        Purga planes donde _ruta_factible(k) falla para algún k (criterio I1 activo).
        σ* NO cambia.
        """
        for sigma in self.planes:
            sigma.starts = [                                   # lista nueva — A1
                InicioRuta(k, camiones[k].pos, camiones[k].avail_time)
                for k in range(len(camiones))
            ]
        # I1: purgar por factibilidad de la cola pendiente (skip anchor ldc)
        self.planes = [
            s for s in self.planes
            if all(self._es_factible_cola(s, k, camiones[k])
                   for k in range(len(camiones)))
        ]
        # I2: purgar por compatibilidad con σ*. Los ldc pueden haber cambiado entre
        # ticks (departures actualizan ldc antes de on_timeout), por lo que el signo
        # de I2 cambia y es necesario re-establecerlo explícitamente aquí.
        if self.distinguido is not None:
            self.planes = [s for s in self.planes
                           if s.compatible(self.distinguido, camiones)]
        # Si σ* fue purgado por I1 o I2, reseleccionar de los supervivientes.
        # El spec dice "σ* no cambia" para el caso normal (σ* supervive). Si σ*
        # cae, reseleccionamos: todos los supervivientes acuerdan en ldc (por I2).
        if self.distinguido is not None and self.distinguido not in self.planes:
            if self.planes:
                self._seleccionar(camiones)
            else:
                self.distinguido = None

    # ── Regla 2: Plan Generation ──────────────────────────────────────────────

    def on_plan_generation(self, sigma_proyectado: SolucionALNS,
                           camiones: List[EstadoCamion]) -> None:
        """Plan Generation (MSA_SPEC §1 Regla 2):
        _purgar (I1 ∧ I2 con σ* actual), agrega σ⁻ al pool, recomputa σ*.
        A2: _seleccionar construye M una sola vez con snapshot consistente.
        """
        self._purgar(camiones)
        self.planes.append(sigma_proyectado)
        self._seleccionar(camiones)

    # ── Regla 3: Customer Request ─────────────────────────────────────────────

    def on_customer_request(self, r: Cliente,
                            camiones: List[EstadoCamion]) -> bool:
        """Customer Request (MSA_SPEC §1 Regla 3):
        F = {INSERT(σ,r) | σ ∈ S_t ∧ FEASIBLEINSERT(σ,r)}.
        F ≠ ∅ → S_t ← F, recomputa σ*, retorna True.
        F = ∅ → sin cambios, retorna False.

        GOLDEN RULE: decisión estructural (¿existe plan que acomoda r?),
        NUNCA por comparación de costos. El truck asignado emerge de σ*.

        Manejo de customers compartidos (precondición A1 de Phase 1):
        _insertar_cliente añade r.cid al dict customers (compartido por ref).
        Tras determinar F, se limpia r.cid de los dicts de planes DESCARTADOS
        cuyo id(customers) no esté compartido con ningún plan superviviente.
        """
        if not self.planes:
            return False

        insertions: Dict[int, Tuple[int, int]] = {}    # id(sigma) → (k, pos)
        for sigma in self.planes:
            k, pos, cost = self._insertar_cliente(sigma, r)
            if cost < math.inf:
                insertions[id(sigma)] = (k, pos)

        F = [s for s in self.planes if id(s) in insertions]
        sigma_ids_F = {id(s) for s in F}

        if F:
            # Aplicar inserción a planes supervivientes
            for s in F:
                k, pos = insertions[id(s)]
                s.routes[k].insert(pos, r.cid)

            # Limpiar r.cid de los dicts DESCARTADOS que no son compartidos
            # con ningún superviviente (dedup por id para no hacer pop doble).
            surviving_dict_ids = {id(s.customers) for s in F}
            seen_cleaned: set = set()
            for s in self.planes:
                if id(s) not in sigma_ids_F:
                    dict_id = id(s.customers)
                    if dict_id not in surviving_dict_ids and dict_id not in seen_cleaned:
                        s.customers.pop(r.cid, None)
                        seen_cleaned.add(dict_id)

            self.planes = F
            self._seleccionar(camiones)
            return True

        # F = ∅: limpiar r.cid de TODOS los dicts (ninguno es superviviente)
        seen_cleaned = set()
        for s in self.planes:
            dict_id = id(s.customers)
            if dict_id not in seen_cleaned:
                s.customers.pop(r.cid, None)
                seen_cleaned.add(dict_id)
        return False

    # ── Regla 4: Vehicle Departure ────────────────────────────────────────────

    def on_vehicle_departure(self, v: int,
                             camiones: List[EstadoCamion]) -> Optional[int]:
        """Vehicle Departure (MSA_SPEC §1 Regla 4):
        Captura dest = siguiente_destino del σ* PRE-filtro,
        filtra pool por COMPATIBLE(σ, σ*_t, camiones), recomputa σ*.

        Valor de retorno:
          int  (incluido DEPOT_CID=0): dest válido, pool no vacío.
          None con pool.distinguido is not None: truck sin asignaciones (ruta vacía).
          None con pool.distinguido is None: pool quedó vacío tras filtrado —
            señal inequívoca de "ningún plan respalda este movimiento";
            Fase 4 debe detectar esto vía pool.distinguido is None y regenerar el pool.
        """
        if not self.planes or self.distinguido is None:
            return None

        old_star = self.distinguido
        dest = old_star.siguiente_destino(v, ldc(camiones[v]))

        self.planes = [s for s in self.planes if s.compatible(old_star, camiones)]

        if self.planes:
            self._seleccionar(camiones)
            return dest
        else:
            self.distinguido = None
            return None    # pool vacío — Fase 4 detecta via pool.distinguido is None
