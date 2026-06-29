# In goes clientes_atendidos_df out goes a csv with:
# relative_u | time

from src.constants import *
from src.classes import *
from src.instance_loader import *
from ALL_KPIs_from_worked import *

import pandas as pd

print("Running ALL_gf...")

gf_analysis_path = "outputs/myopic_outputs/25_kmh_sanalysis"

relative_rep_path = "Instancia_II/II_replica_0"

fernandou_csv_path = "FJ_fast/benchmark_info_perfecta/tour_histogram_data_instancia_2_replicas_100.csv"

def part1(df_ca):
    clientes_atendidos = []
    relative_profits = []
    times = []

    total_utility = calc_total_U(df_ca)

    c1 = df_ca["tiempos_c1"]
    c2 = df_ca["tiempos_c2"]
    c3 = df_ca["tiempos_c3"]

    c123 = [c1, c2, c3]
    joined = [INF] * len(c1)
    for cliente_i in range(len(c1)):
        for cj in c123:
            if cj[cliente_i] != INF:
                joined[cliente_i] = cj[cliente_i]

    indicadores = df_ca["indicador"]
    for t_ss in range(START_TIME, END_TIME):
        # Alexa describe efficiency:

        now_atendidos = 0
        now_utility = 0
        for j in range(len(joined)):
            t_atencion = joined[j]
            if t_ss >= t_atencion:
                now_atendidos += 1
                now_utility += 1
                if indicadores[j] == DELIVERY:
                    now_utility += 1

        rel = now_utility/total_utility

        clientes_atendidos.append(now_atendidos)
        relative_profits.append(rel)
        times.append(t_ss)
        
    df_out = pd.DataFrame()
    df_out["tiempo_s"] = times
    df_out["u_rel"] = relative_profits
    df_out["clientes_atendidos"] = clientes_atendidos

    out_path = os.path.join(gf_analysis_path, relative_rep_path, "u_rel_over_time.xlsx")
    df_out.to_excel(out_path, index=False)
    print(f"Wrote {out_path}")

def shitty_int(s):

    return int(float(str(s).replace(",", ".")))

def part_2(df_tours, df_ca): # Saving Feño
    clientes_atendidos = []
    relative_profits = []
    times = []

    replicas = df_tours["replica"]
    MAX_DF_INDEX = 0
    for i in range(len(replicas)):
        if shitty_int(replicas[i]) == 1:
            MAX_DF_INDEX = i
            break

    total_utility = calc_total_U(df_ca)

    tour_return_times = df_tours["return_to_depot_time"][:MAX_DF_INDEX]
    tour_profits = df_tours["total_profit"][:MAX_DF_INDEX]
    tour_atendidos = df_tours["n_customers_tour"][:MAX_DF_INDEX]
    for t_ss in range(START_TIME, END_TIME):
        # Alexa describe efficiency:

        now_atendidos = 0
        now_utility = 0
        for j in range(MAX_DF_INDEX):
            tr_return = shitty_int(tour_return_times[j])
            tr_profit = shitty_int(tour_profits[j])
            tr_atendidos = shitty_int(tour_atendidos[j])

            if t_ss >= tr_return:
                now_atendidos += tr_atendidos
                now_utility += tr_profit

        rel = now_utility/total_utility

        clientes_atendidos.append(now_atendidos)
        relative_profits.append(rel)
        times.append(t_ss)
        
    df_out = pd.DataFrame()
    df_out["tiempo_s"] = times
    df_out["u_rel"] = relative_profits
    df_out["clientes_atendidos"] = clientes_atendidos

    out_path = os.path.join("FJ_fast", "hexalyier.xlsx")
    df_out.to_excel(out_path, index=False)
    print(f"Wrote {out_path}")


df_ca_path = os.path.join(gf_analysis_path, relative_rep_path, "clientes_atendidos.csv")
df_ca = pd.read_csv(df_ca_path)


df_tours = pd.read_csv(fernandou_csv_path, sep=";")

part_2(df_tours, df_ca)
print("Done!")