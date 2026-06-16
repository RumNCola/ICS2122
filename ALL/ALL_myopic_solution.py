'''Lo básico de lo básico, aprovechandosé de la capacidad ilimitada (+ bencina)
1. El camión de pickup solo vuelve al fin del día al depot, 
    moviendose de orden más cercana a más cercana cada segundo
2. Los camiones de deliveries...'''

from src.constants import *
from src.classes import *
from src.instance_loader import *

import math

VERBOSE_MYOPIC = False
VERBOSE_PICKUP = False
VERBOSE_DELIVERY = False


N_PICKUP = 1
N_DELIVERY = 2

g_REPLICA = Replica()

OUTPUT_FOLDER_NAME = "testingv8_fastfast"

NONE_INDEX = -1

# States
ATENDIENDO_CLIENTE = "Atendiendo Cliente..."
YENDO_A_CLIENTE = "Yendo a cliente"

LOADED_IN_DEPOT = "LOADED IN DEPOT"
DELIVERING = "DELIVERING"
BACK_TO_DEPOT = "RETURNING TO DEPOT"
LOADING = "LOADING IN DEPOT"


class Camion:

    t_posiciones = []
    visited = []
    timer = 0
    state = 0


    def __init__(self):
        self.t_posiciones = []
        self.visited = []
        self.timer = 0
        self.state = 0


START_ss = hh_mm_ss_to_seconds("09:00:00")
END_ss = hh_mm_ss_to_seconds("17:00:00")

def move_camion(pos_camion, objective_pos):
    '''Returns new_pos, TODO: Fix corners'''

    dy = objective_pos[1] - pos_camion[1]
    dx = objective_pos[0] - pos_camion[0]

    new_x, new_y = pos_camion
    if dx > 0:
        dx = min(dx, VEL_CAMION_MS)
        new_x += dx
    elif dx < 0:
        dx = abs(dx)
        dx = min(dx, VEL_CAMION_MS)

        new_x -= dx
    elif dx == 0:
        
        if dy > 0:
            dy = min(dy, VEL_CAMION_MS)
            new_y += dy
        elif dy < 0: 
            dy = abs(dy)
            dy = min(dy, VEL_CAMION_MS)

            new_y -= dy
        elif dy == 0:
            return objective_pos # Already there

    return [new_x, new_y]

def closest_index_to(origin, point_indexes):
    '''Returns the index of the point closest to origin. NONE_INDEX if point_indexes = []'''
    min_dist = 99999999999
    closest_index = NONE_INDEX

    for index in point_indexes:
        pos = g_REPLICA.points[index]

        d = dist(pos, origin)
        if d < min_dist:
            min_dist = d
            closest_index = index

    return closest_index

g_obj_pickup = NONE_INDEX
g_next_pickup_spawn_time = 0
def update_next_pickup_spawn_time(t_ss):
    global g_next_pickup_spawn_time

    arrival_times = []

    for i in range(g_REPLICA.num_points):
        indicador = g_REPLICA.indicador[i]
        time = g_REPLICA.arrivals[i]

        if indicador != PICKUP:
            continue

        if time >= t_ss: 
            arrival_times.append(time)

    if arrival_times == []:
        g_next_pickup_spawn_time = INF
    else:
        arrival_times = sorted(arrival_times)

        g_next_pickup_spawn_time = arrival_times[0]
        


def get_route_pickup(camion: Camion, t_ss: int, pos_camion):
    '''As of now, just returns closest one lol'''
    global g_next_pickup_spawn_time, g_obj_pickup

    # Rasca para poder en el informe que corre en < 1 s
    nothing_new_has_happened = t_ss < g_next_pickup_spawn_time and g_obj_pickup != NONE_INDEX
    if nothing_new_has_happened:
        # Nothing new has happened, follow old route
        if VERBOSE_PICKUP and t_ss % 300 == 0:
            print(f"> {seconds_to_hh_mm_ss(t_ss)}: Nothing new has happened... continuing to target {g_obj_pickup}")
        return [g_obj_pickup]
    
    update_next_pickup_spawn_time(t_ss)

    # 1. Possible destinations
    possible_pickups = []

    for i in range(g_REPLICA.num_points):
        indicador = g_REPLICA.indicador[i]

        if indicador != PICKUP:
            continue 
        
        time = g_REPLICA.arrivals[i]
        if time > t_ss: 
            continue # Doesn't yet spawn
        
        if camion.visited[i] != INF:
            continue # Already visited

        pos = g_REPLICA.points[i]

        if pos[0] == DEPOT_POS[0] and pos[1] == DEPOT_POS[1]:
            continue # depot

        possible_pickups.append(i)

    # 1.1 No candidates
    if len(possible_pickups) == 0:
        if VERBOSE_PICKUP:
            print("> No hay pickups para atender...")
        
        return [NONE_INDEX]
    
    g_obj_pickup = closest_index_to(pos_camion, possible_pickups)
    return [g_obj_pickup]

def panic_check(camion: Camion, t_ss, camion_pos, be_verbose: bool):
    time_remaining = END_TIME - t_ss
    conservative_remaining_dist = VEL_CAMION_MS * (time_remaining-1)

    if dist(camion_pos, DEPOT_POS) > conservative_remaining_dist:
        if be_verbose and camion.state != BACK_TO_DEPOT:
            print("AHHH!!! OUTTA TIME GOING BACK TO DEPOOOOT")

        camion.state = BACK_TO_DEPOT

# Pickup no tiene restricciones de tiempo, se mueve al más cercano
def solve_myopic_pickup() -> list:
    '''Returns (clientes_atendidos: list[int], posiciones_camion: list[(t_ss, pos_tuple)])\n
    clientes_atendidos es una lista de tiempos de atención (INF si no es atendido)\n
    posiciones_camion: es la posición del camión para cada segundo (t, (x, y))'''
    global g_obj_pickup, g_next_pickup_spawn_time # ooooh, me definitely no likey
    global g_REPLICA

    # Primera simulación son 28800 segundos, un update por segundo
    # (TODO: Considerar updatear más inteligentemente, solo cuando ocurre una acción por ejemplo)
    g_obj_pickup = NONE_INDEX
    g_next_pickup_spawn_time = 0

    camion = Camion()
    camion.state = YENDO_A_CLIENTE

    camion.visited = [INF] * g_REPLICA.num_points
    camion.t_posiciones = []
    camion.t_posiciones.append([START_ss, DEPOT_POS])
    curr_obj_index = NONE_INDEX
    curr_obj_pos = DEPOT_POS

    atendiendo_timer = 0
    
    ts = T_SS_CAMION

    for t_ss in ts[1:]:
        prev_pos = camion.t_posiciones[-1][1]
        camion_pos = [prev_pos[0], prev_pos[1]] # Python be dumb (Reference pass)

        if t_ss % 1800 == 0 and VERBOSE_PICKUP:
            print(f"{seconds_to_hh_mm_ss(t_ss)}: ({camion_pos}) -> ({curr_obj_pos})")
        
        new_pos = camion_pos
        panic_check(camion, t_ss, camion_pos, VERBOSE_PICKUP)

        if camion.state == ATENDIENDO_CLIENTE:
            if atendiendo_timer >= 1:
                atendiendo_timer -= 1

                if atendiendo_timer == 0:
                    if VERBOSE_PICKUP:
                        print(f"> {seconds_to_hh_mm_ss(t_ss)}: Se termino de atender a {curr_obj_index}")
                    camion.visited[curr_obj_index] = t_ss

                    camion.state = YENDO_A_CLIENTE
                    g_obj_pickup = NONE_INDEX

        if camion.state == YENDO_A_CLIENTE:
            route = get_route_pickup(camion, t_ss, camion_pos)

            if route == NONE_INDEX:
                if VERBOSE_PICKUP:
                    print("No hay clientes para atender!")

                curr_obj_index = None
                curr_obj_pos = camion_pos
            else:
                curr_obj_index = route[0]
                curr_obj_pos = g_REPLICA.points[curr_obj_index]

            # 3. Go to current_objective
            new_pos = move_camion(camion_pos, curr_obj_pos)
            
            if dist(new_pos, curr_obj_pos) == 0 and curr_obj_index != None:
                # Llegamos!!!
                camion.state = ATENDIENDO_CLIENTE
                atendiendo_timer = TIEMPO_DE_SERVICIO_PICKUP
                if VERBOSE_PICKUP:
                    print(f"> {seconds_to_hh_mm_ss(t_ss)}: Comenzando a atender cliente {curr_obj_index} en {curr_obj_pos}")

        if camion.state == BACK_TO_DEPOT:
            new_pos = move_camion(camion_pos, DEPOT_POS)

        camion.t_posiciones.append([t_ss, new_pos])
        
    return (camion.visited, camion.t_posiciones)

def tiempo_de_finalizada_atencion(curr_pos, candidate_index, curr_time):
    next_pos = g_REPLICA.points[candidate_index]

    travel_time = dist(curr_pos, next_pos) / VEL_CAMION_MS # t = d / v

    final_time = curr_time + travel_time + TIEMPO_DE_SERVICIO_DELIVERY

    final_time = int(math.ceil(final_time)) # integer
    return final_time


def closest_index_but_delivery(curr_pos, curr_candidates, predicted_curr_time):
    '''Returns the closest index, s.t. llego a tiempo!!! Returns '''

    filtered_candidates = []
    for candidate in curr_candidates:
        tiempo_finalizado_atencion = tiempo_de_finalizada_atencion(curr_pos, candidate, predicted_curr_time)

        if tiempo_finalizado_atencion <= g_REPLICA.deadlines[candidate]:
            filtered_candidates.append(candidate)

    return closest_index_to(curr_pos, filtered_candidates)



DELIVERY_ROUTE_LEN = 10
def create_delivery_route(visited, already_visited, t_ss, camion_pos) -> list:
    '''Returns a list of indexes to visit'''

    # TODO: TSP (soy muy flojo)
    candidates = []
    for i in range(g_REPLICA.num_points):

        if g_REPLICA.indicador[i] != DELIVERY:
            continue
            
        time = g_REPLICA.ready_times[i]
        if time > t_ss: 
            continue # Isn't yet ready
        
        if visited[i] < INF:
            continue # Already visited

        if already_visited[i] < INF:
            continue # Other truck

        pos = g_REPLICA.points[i]

        if pos[0] == DEPOT_POS[0] and pos[1] == DEPOT_POS[1]:
            continue # depot

        candidates.append(i)

    # Here do something more smart to select candidates xd

    if len(candidates) == 0:
        return []

    len_route = min(DELIVERY_ROUTE_LEN, len(candidates))
    
    route = []

    curr_pos = DEPOT_POS

    predicted_curr_time = t_ss
    while len(route) < len_route:
        curr_candidates = [c for c in candidates if c not in route]
        
        next_destination = closest_index_but_delivery(curr_pos, curr_candidates, predicted_curr_time)
        if next_destination == NONE_INDEX:
            # No more candidates!
            break

        next_pos = g_REPLICA.points[next_destination]

        route.append(next_destination)

        predicted_curr_time = tiempo_de_finalizada_atencion(curr_pos, next_destination, predicted_curr_time)
        curr_pos = next_pos

    return route

def solve_deliveries_camion(already_visited: list[float], id_str = "<undefined>") -> list:
    '''Returns (atendidos, t_pos_camion)
    Resuelve los deliveries de 1 camión'''

    if VERBOSE_DELIVERY:
        print(f"Soy el camión {id_str}")

    camion = Camion()

    visited = [INF] * g_REPLICA.num_points

    camion.t_posiciones.append([START_ss, DEPOT_POS])
    camion.state = LOADED_IN_DEPOT
    camion.timer = 0

    route = [] # A route is a series of indexes
    route_progress = 0

    objective_pos = DEPOT_POS

    ts = T_SS_CAMION

    for t_ss in ts[1:]:
        camion_pos = camion.t_posiciones[-1][1]

        # Camion:
        # 1. Depot (Creates Route...)
        # 2. InRoute (Follows Route...)
        # 1 -> 2 -> 1 -> 2 -> ...

        if t_ss % 300 == 0 and VERBOSE_DELIVERY:
            print(f"{seconds_to_hh_mm_ss(t_ss)}: {camion.state} ({[round(float(x), 2) for x in camion_pos]}) -> ({objective_pos}). ROUTE: {route_progress}/{route}")


        if camion.state == LOADING:
            camion.timer -= 1
            objective_pos = DEPOT_POS

            if camion.timer == 0:
                camion.state = LOADED_IN_DEPOT

        
        if camion.state == LOADED_IN_DEPOT:
            route = create_delivery_route(visited, already_visited, t_ss, camion_pos)

            if len(route) == 0:
                objective_pos = DEPOT_POS
                
            else: 
                camion.state = DELIVERING
                route_progress = 0

                camion.timer = TIEMPO_DE_SERVICIO_DELIVERY

        panic_check(camion, t_ss, camion_pos, VERBOSE_DELIVERY)

        if camion.state == DELIVERING:
            objective_index = route[route_progress]

            objective_pos = g_REPLICA.points[objective_index]

            if dist(objective_pos, camion_pos) == 0:
                camion.timer -= 1

                if camion.timer == 0:
                    camion.timer = TIEMPO_DE_SERVICIO_DELIVERY

                    visited[objective_index] = t_ss # Add que camión lo atendió quizá
                    route_progress += 1

            if route_progress == len(route):
                camion.state = BACK_TO_DEPOT


        if camion.state == BACK_TO_DEPOT:
            objective_pos = DEPOT_POS

            if dist(camion_pos, DEPOT_POS) == 0:
                camion.timer = TIEMPO_DELIVERY_LOADING
                camion.state = LOADING

        # Mueve el camión
        new_pos = move_camion(camion_pos, objective_pos)

        camion.t_posiciones.append([t_ss, new_pos])
    
    if VERBOSE_DELIVERY:
        count = len([v for v in visited if v < INF])
        print(f"Delivered to {count}")

    return (visited, camion.t_posiciones)


def solve_myopic_deliveries() -> list:
    '''Returns ((atendidos2, atendidos3), (t_pos2, t_pos3))'''

    # Camión 2
    atendidos2, t_pos2 = solve_deliveries_camion([INF] * g_REPLICA.num_points, "#2")

    # Camión 3
    atendidos3, t_pos3 = solve_deliveries_camion(atendidos2, "#3")

    return ((atendidos2, atendidos3), (t_pos2, t_pos3))

def create_df_pos_rows(t_pos1, t_pos2, t_pos3):
    '''Each row is (t, c1x, c1y, c2x, c2y, c3x, c3y)'''

    good = len(t_pos1) == len(t_pos2) and len(t_pos2) == len(t_pos3)

    if not good:
        print("> Implement me in create_rows()")
        print(len(t_pos1), len(t_pos2), len(t_pos3))
        exit()

    rows = []

    for i in range(len(t_pos1)):
        t1 = t_pos1[i][0] # Asumiremos todos tienen el mismo t xd
        c1x, c1y = t_pos1[i][1]
        c2x, c2y = t_pos2[i][1]
        c3x, c3y = t_pos3[i][1]

        row = [t1, c1x, c1y, c2x, c2y, c3x, c3y]
        rows.append(row)

    return rows

def create_df_pos(t_pos_camion_pickup, t_pos_camion_2y3):

    df_pos = pd.DataFrame(columns=["t", "c1_x", "c1_y", "c2_x", "c2_y", "c3_x", "c3_y"])

    rows = create_df_pos_rows(t_pos_camion_pickup, t_pos_camion_2y3[0], t_pos_camion_2y3[1])

    # A lot faster than row by row xd
    for x in range(len(df_pos.columns)):
        column_str = df_pos.columns[x]
        df_pos[column_str] = [row[x] for row in rows]

    return df_pos

def create_df_atendidos(clientes_atendidos_pickup, clientes_atendidos_delivery2y3):
    a1 = clientes_atendidos_pickup
    a2, a3 = clientes_atendidos_delivery2y3

    df_atendidos = pd.DataFrame()

    df_atendidos["tiempos_c1"] = a1
    df_atendidos["tiempos_c2"] = a2
    df_atendidos["tiempos_c3"] = a3

    return df_atendidos

def calculate_utility_from_df_atendidos(df_atendidos):
    '''Returns (utilidad, [p1, p2, p3], [d1, d2 d3])\n
    Con pi = # pickups atendidos por i, di = # deliveries atendidos por i'''
    # WHAT THE F*CK IS A FOR LOOP!!! https://www.youtube.com/watch?v=OUZwAefgisI

    indicadores = df_atendidos["indicador"]

    # pi = # pickups atendidos por i, di = # deliveries atendidos por i
    p1 = 0
    d1 = 0
    p2 = 0
    d2 = 0
    p3 = 0
    d3 = 0

    for j in range(len(df_atendidos["tiempos_c1"])):
        t1 = df_atendidos["tiempos_c1"][j]
        t2 = df_atendidos["tiempos_c2"][j]
        t3 = df_atendidos["tiempos_c3"][j]
        if t1 < INF:
            if indicadores[j] == PICKUP:
                p1 += 1
            else:
                d1 += 1

        if t2 < INF:
            if indicadores[j] == PICKUP:
                p2 += 1
            else:
                d2 += 1

        if t3 < INF:
            if indicadores[j] == PICKUP:
                p3 += 1
            else:
                d3 += 1

    num_pickups = p1 + p2 + p3
    num_deliveries = d1 + d2 + d3 

    utilidad = num_pickups + 2 * num_deliveries

    return (utilidad, [p1, p2, p3], [d1, d2, d3])

def print_desglose_utilidad(df_atendidos):
    utilidad, ps, ds = calculate_utility_from_df_atendidos(df_atendidos)

    print("DESGLOSE UTILIDAD")
    print(f"El camión 1 realizó {ps[0]}+{ds[0]} = {ps[0]+ds[0]} =  pickups+deliveries")
    print(f"El camión 2 realizó {ps[1]}+{ds[1]} = {ps[1]+ds[1]} = pickups+deliveries")
    print(f"El camión 3 realizó {ps[2]}+{ds[2]} = {ps[2]+ds[2]} = pickups+deliveries")
    print("La solución es factible con 90% certeza")
    print("---")
    print(f"La utilidad total es de {utilidad}")



def solve_replica_myopic_and_save(output_folder: str, replica = None):
    global g_REPLICA

    g_REPLICA = replica

    if VERBOSE_MYOPIC:
        print(f"Running a Myopic solution of {g_REPLICA}")

    clientes_atendidos_pickup, t_pos_camion_pickup = solve_myopic_pickup()
    if VERBOSE_MYOPIC:
        print("Pickup processed...")

    clientes_atendidos_delivery2y3, t_pos_camion_2y3 = solve_myopic_deliveries()
    if VERBOSE_MYOPIC:
        print("Deliveries processed...")

    df_pos = create_df_pos(t_pos_camion_pickup, t_pos_camion_2y3)

    pos_path = os.path.join(output_folder, "posiciones_camiones.csv")
    df_pos.to_csv(pos_path, index=False)

    print(f"Saved to {pos_path}")

    df_atendidos = create_df_atendidos(clientes_atendidos_pickup, clientes_atendidos_delivery2y3)

    df_atendidos = add_columna_rappi(df_atendidos, g_REPLICA)

    df_atendidos = add_columna_indicador(df_atendidos, g_REPLICA)

    atendidos_path = os.path.join(output_folder, "clientes_atendidos.csv")
    df_atendidos.to_csv(atendidos_path, index=False)

    print(f"Saved to {atendidos_path}")

    # Calcula utilidad
    if VERBOSE_MYOPIC:
        print_desglose_utilidad(df_atendidos)


def add_columna_rappi(df_atendidos, replica: Replica):
    '''Modifica df_atendidos, que debe ya tener las columnas tiempos_c1, tiempos_c2, tiempos_c3'''

    t_c1 = df_atendidos["tiempos_c1"]
    t_c2 = df_atendidos["tiempos_c2"]
    t_c3 = df_atendidos["tiempos_c3"]
    
    t_rappis = []
    for j in range(len(t_c1)):
        t1 = t_c1[j]
        t2 = t_c2[j]
        t3 = t_c3[j]
        no_atendido = (t1 >= INF) and (t2 >= INF) and (t3 >= INF)

        t_sale_el_rappi = INF

        if no_atendido:
            pos_cliente = replica.points[j]
            tipo_cliente = replica.indicador[j]
            deadline_cliente = min(replica.deadlines[j], END_TIME) # Esto es insólito!!!

            rappi_duration = duracion_rappi(pos_cliente, tipo_cliente)

            t_sale_el_rappi = deadline_cliente - rappi_duration
            
        t_rappis.append(t_sale_el_rappi)


    df_atendidos["t_sale_el_rappi"] = t_rappis

    return df_atendidos

def add_columna_indicador(df, replica: Replica):
    df["indicador"] = replica.indicador

    return df


import pandas as pd


if __name__ == "__main__":
    instance_I = load_instance_data(DATA_SRC[0])
    g_REPLICA = get_replica_from_instancia(instance_I, 0)

    output_folder = os.path.join("outputs", "myopic_outputs", OUTPUT_FOLDER_NAME)
    solve_replica_myopic_and_save(output_folder, g_REPLICA)


