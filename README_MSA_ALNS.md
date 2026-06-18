# MSA + ALNS + ICD dynamic pickup insertion

Esta version reemplaza Hexaly por ALNS y mantiene el selector de consenso de Bent & Van Hentenryck.

## Ejecutar

```bash
python main_msa_alns.py
```

O desde Python:

```python
from main_msa_alns import main

result = main(
    instancia=1,
    replica_id=0,
    n_scenarios=25,
    lookahead_min=120,
    scenario_time_limit_sec=15,
)
```

## Fuente de datos

- La replica real se lee desde `instancias_de_geyter/instancia_tipo_{instancia}.csv`, filtrando `replica == replica_id`.
- Los escenarios futuros del MSA se generan con `src.ricas_replica_creator.replica(instancia, n_scenarios)` y luego se filtran por `now` y `lookahead_sec`.

## Consenso

El modo por defecto es:

```python
consensus_mode = "van_hentenryck"
```

No usa `consensus_threshold`. El selector calcula:

```text
M_t[v,r] = numero de planes que mandan al vehiculo v al cliente r
f_t(pi) = sum_v M_t[v, a_v(pi)]
```

Selecciona el plan con mayor `f_t(pi)`.

## Insercion dinamica de pickups

Archivo central:

```text
src/dynamic_alns/dynamic_insertion.py
```

Cuando aparece un pickup mientras hay camiones ejecutando rutas activas:

1. Se calcula una mejor insercion factible en el sufijo modificable de las rutas activas.
2. Se samplean escenarios futuros.
3. Para cada escenario se simula una insercion tipo regret de pickups futuros + pickup nuevo.
4. Se calcula `phi`, frecuencia de escenarios donde el pickup nuevo queda insertado.
5. Si `phi >= icd_dispatch_threshold`, se inserta realmente.
6. Si `phi < icd_postpone_threshold`, se posterga.
7. En caso intermedio queda como `undecided`.

Restriccion clave: el prefijo bloqueado de una ruta no se modifica. Esto incluye clientes ya atendidos y el cliente al que el camion ya se dirige.

## Operadores ALNS

Archivo central:

```text
src/dynamic_alns/alns_static_solver.py
```

Destroy operators:

- `random`
- `worst`
- `related`
- `sequence`
- `shaw_ready`
- `shaw_deadline`
- `geographic`
- `route_vehicle`

Repair operators:

- `greedy`
- `regret2`
- `regret3`
- `ratio`
- `deadline`
- `ready`

Los operadores extendidos se pueden apagar con:

```python
alns_enable_extended_operators = False
```

## Outputs

Se guardan en:

```text
outputs/msa_alns/
```

- `committed_trips_instancia_X_replica_Y.csv`
- `dynamic_insertions_instancia_X_replica_Y.csv`
- `summary_instancia_X_replica_Y.csv`
