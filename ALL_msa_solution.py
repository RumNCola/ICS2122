import argparse
import sys
import os
import time

from src.instance_loader import load_default_instances
from src.msa_policy import simular_msa, N_ESCENARIOS, UMBRAL_CONSENSO
from src.constants import NUM_REPLICAS, LABELS_INSTANCIAS

sys.path.insert(0, os.path.dirname(__file__))

"""
Ejecutor de la política online MDP + MSA.

Arquitectura:
    Estado MDP: posiciones/tiempos de camiones + clientes pendientes + tiempo transcurrido
    Acción: asignación de camión para cada cliente que llega
    Política de decisión: argmax valor Q esperado sobre N escenarios futuros muestreados
    Evaluador: rollout greedy

Uso (desde ICS2122/) en terminal:
    
    python ALL_msa_solution.py
    python ALL_msa_solution.py --instancia 0 --replicas 5
    python ALL_msa_solution.py --instancia 0 --replicas 5 --escenarios 50
"""


#--------------------- Runner por instancia --------------------------------

def _barra(r: int):
    t0 = time.perf_counter()
    def cb(idx: int, total: int) -> None:
        elapsed = time.perf_counter() - t0
        eta = elapsed / (idx + 1) * (total - idx - 1) if idx > 0 else 0
        pct = (idx + 1) / total
        bloque = int(pct * 25)
        barra = "█" * bloque + "░" * (25 - bloque)
        print(f"\r  rep {r}  [{barra}] {idx+1}/{total}  {pct*100:.0f}%  ETA {eta:.0f}s   ",
              end="", flush=True)
        if idx + 1 == total:
            print()
    return cb


def correr_msa_en_instancia(datos_instancia, etiqueta: str,
                            idx_instancia: int, n_replicas: int,
                            n_escenarios: int, umbral_consenso: float,
                            verbose: bool = False) -> dict:   #imprimir inf de debug para simulacion 
       
    ganancias = []
    servidos_lista = []
    lista_rechazados= []
    distancias = []
    consenso_prom = []
    tiempos_escenario = []

    for r in range(n_replicas):
        t_inicio = time.perf_counter()
        m = simular_msa(datos_instancia=datos_instancia,
            replica_idx=r, idx_instancia=idx_instancia,
            n_escenarios=n_escenarios, umbral_consenso=umbral_consenso,
            verbose=verbose, on_customer=_barra(r))
        
        transcurrido = time.perf_counter() - t_inicio

        ganancias.append(m["profit_total"])
        servidos_lista.append(m["total_aceptados"])
        lista_rechazados.append(m["total_rechazados"])
        distancias.append(m["distancia_total"])
        consenso_prom.append(m["score_consenso_promedio"])
        tiempos_escenario.append(m["tiempo_promedio_escenarios"])

        print(f"réplica {r:3d}: "
              f"ganancia={m['profit_total']:>8.1f}  "
              f"servidos={m['total_aceptados']:>3d}  "
              f"rechazados={m['total_rechazados']:>3d}  "
              f"consenso={m['score_consenso_promedio']:.2f}  "
              f"tiempo={transcurrido:.1f}s")

    n = n_replicas

    return {
        "instancia": etiqueta,
        "n_replicas": n,
        "ganancia_prom": sum(ganancias)/n,
        "servidos_prom": sum(servidos_lista)/n,
        "rechazados_prom": sum(lista_rechazados)/n,
        "distancia_prom_km": ((sum(distancias)/n)/1000),
        "consenso_prom": sum(consenso_prom)/n,
        "tiempo_escenario_prom": sum(tiempos_escenario)/n,
        "ganancia_min": min(ganancias),
        "ganancia_max": max(ganancias),
        "ganancias": ganancias}  #lista completa para análisis

#####Perdon de acá para abajo usé chatgpt para dejarlo lindo, si quieren le hacen re-work para no usar IA.######

def imprimir_resumen(s: dict) -> None:
    print(f"\n{'─'*60}")
    print(f"  Instancia {s['instancia']}  ({s['n_replicas']} réplicas)")
    print(f"{'─'*60}")
    print(f"  Ganancia promedio recolectada : {s['ganancia_prom']:.1f}")
    print(f"  Clientes servidos promedio    : {s['servidos_prom']:.1f}")
    print(f"  Clientes rechazados promedio  : {s['rechazados_prom']:.1f}")
    print(f"  Distancia promedio recorrida  : {s['distancia_prom_km']:.1f} km")
    print(f"  Puntaje de consenso promedio  : {s['consenso_prom']:.3f}")
    print(f"  Tiempo de escenario promedio  : {s['tiempo_escenario_prom']:.3f} s")
    print(f"  Rango de ganancia [mín, máx]  : [{s['ganancia_min']:.0f}, {s['ganancia_max']:.0f}]")

def main():
    parser = argparse.ArgumentParser(description="Solver SDVRPTW con MDP+MSA")
    parser.add_argument("--instancia", type=int, default=None,
                        help="Índice de instancia 0-3 (default: las 4).")
    parser.add_argument("--replicas", type=int, default=5,
                        help="Número de réplicas a evaluar (default 5).")
    parser.add_argument("--escenarios", type=int, default=N_ESCENARIOS,
                        help=f"Escenarios por época (default {N_ESCENARIOS}).")
    parser.add_argument("--umbral", type=float, default=UMBRAL_CONSENSO,
                        help=f"Umbral de consenso (default {UMBRAL_CONSENSO}).")
    parser.add_argument("--verbose", action="store_true",
                        help="Imprimir salida de depuración por cliente.")
    args = parser.parse_args()

    n_replicas = min(args.replicas, NUM_REPLICAS)

    print("=" * 60)
    print("  MDP + MSA (Consenso y Distancia) + Rollout Greedy")
    print("=" * 60)
    print(f"  N_ESCENARIOS={args.escenarios}  "
          f"UMBRAL_CONSENSO={args.umbral}")
    print()

    print("Cargando instancias...")
    instancias = load_default_instances()

    rango_idx = [args.instancia] if args.instancia is not None else range(4)
    todos_resumenes = []

    for i in rango_idx:
        print(f"\nEjecutando MSA en Instancia {LABELS_INSTANCIAS[i]} "
              f"({n_replicas} réplicas)...")
        s = correr_msa_en_instancia(
            datos_instancia = instancias[i],
            etiqueta        = LABELS_INSTANCIAS[i],
            idx_instancia   = i,
            n_replicas      = n_replicas,
            n_escenarios    = args.escenarios,
            umbral_consenso = args.umbral,
            verbose         = args.verbose,
        )
        todos_resumenes.append(s)
        imprimir_resumen(s)

    if len(todos_resumenes) > 1:
        prom_total = sum(s["ganancia_prom"] for s in todos_resumenes) / len(todos_resumenes)
        print(f"\n{'═'*60}")
        print(f"  Ganancia MSA promedio total (todas las instancias): {prom_total:.1f}")
        print(f"{'═'*60}")


if __name__ == "__main__":
    main()