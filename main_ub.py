from src.deterministic_bound import VRPTWConfig, solve_vrptw_hexaly
from src.Ricas_replica_creator import replica
import numpy as np
import pandas as pd


def main(instancia: int = 1):
    # 1. Crear réplicas simuladas
    # instancia puede ser 1, 2, 3 o 4
    # replicas es la cantidad de días/escenarios que quieres samplear
    replicas = 1
    df, csv_path = replica(instancia, replicas)

    print(f"Archivo generado: {csv_path}")
    print(df.head())
    print(df["replica"].value_counts().sort_index())

    # 2. Configurar el problema
    cfg = VRPTWConfig(
        nb_vehicles=3,
        max_trips_per_vehicle=300,
        minimize_vehicles_after_profit = False,
        minimize_trips_after_profit = True,
        minimize_distance_after_profit = True,


        # Según el informe: depot en centro del mapa
        depot_xy=(10000.0, 10000.0),

        # Jornada operacional
        shift_start_sec=9 * 3600,
        shift_end_sec=17 * 3600,

        # 25 km/h en m/s
        vehicle_speed_m_per_s=25_000 / 3600,

        # Distancia Manhattan
        distance_metric="manhattan",

        # Servicio constante de 3 minutos
        service_time_default=180.0,
        force_service_time_default=True,

        # Pickups disponibles desde que aparecen
        pickup_ready_policy="arrival",

        # False = los no atendidos se interpretan como tercerizados
        require_all_customers=False,

        # Ventanas duras
        hard_time_windows=True,

        # Deadline interpretado como último inicio de servicio
        deadline_is_latest_start=True,

        # Delivery requiere carga en depot antes de atenderse
        delivery_must_be_loaded_at_depot=True,

        time_limit_sec=60,
    )

    # 3. Elegir UNA réplica como escenario determinístico con información perfecta
    solution_summaries = []
    for i in range(replicas):
        print(f'Replica {i}')
        replica_id = i

        escenario = (
            df[df["replica"] == replica_id]
            .copy()
            .reset_index(drop=True)
        )
        print(f'Escenario {escenario}')

        print(f"Clientes en escenario {replica_id}: {len(escenario)}")

        # 4. Resolver
        solution = solve_vrptw_hexaly(escenario, cfg, replica_id=replica_id)

        # 5. Revisar resultados
        print('AAA')
        print(solution.summary_as_dict())
        solution_summaries.append(solution.summary_as_dict())
        solution.save_camion_positions_csv(
    f"camion_positions_instancia_{instancia}_replica_{replica_id}.csv",
    include_depot=False
)

    #     rutas = solution.routes_as_dataframe()
    #     viajes = solution.trips_as_dataframe()

    # print(rutas.head())
    # print(viajes.head())

    # 6. Guardar resultados
    solution_summaries_df = pd.DataFrame(solution_summaries)
    solution_summaries_df.to_csv(f"outputs/solution_summaries_instancia_{instancia}_replicas_{replicas}.csv", index=False)
    print(f'Número de réplicas resueltas: {replicas}')
    print(f' --- Atencion ---')
    print(f'Promedio de clientes atendidos: {solution_summaries_df["served_customers"].mean()}')
    print(f'Promedio de clientes no atendidos: {solution_summaries_df["unserved_customers"].mean()}')
    print(f'Promedio de service_rate: {solution_summaries_df["service_rate"].mean()}')
    print(f' --- Ganancias ---')
    print(f'Promedio de profit: {solution_summaries_df["total_profit"].mean()}')
    print(f'Promedio de total_possible_profit: {solution_summaries_df["total_possible_profit"].mean()}')
    print(f'Promedio de profit_rate: {solution_summaries_df["profit_rate"].mean()}')
    print(f' --- MISC ---')
    print(f'Promedio de distancia recorrida: {solution_summaries_df["total_distance_km"].mean()}')
    # rutas.to_csv(f"rutas_instancia_4_replica_{replica_id}.csv", index=False)
    # viajes.to_csv(f"viajes_instancia_4_replica_{replica_id}.csv", index=False)


if __name__ == "__main__":
    np.random.seed(42)
    for i in range(4):
        main(instancia=i + 1)