''' Many truck me no like capstóngpt, at least this code is gpt free
Lo básico de lo básico, aprovechandosé de la capacidad ilimitada (+ bencina)
1. El camión de pickup solo vuelve al fin del día al depot, 
    moviendose de orden más cercana a más cercana cada segundo
2. Los camiones de deliveries...'''

from src.constants import *
from src.classes import *
from src.instance_loader import *

import math

N_PICKUP = 2
N_DELIVERY = 3
N_CAMIONES = N_PICKUP + N_DELIVERY

VERBOSE_MYOPIC = False
VERBOSE_PICKUP = False
VERBOSE_DELIVERY = False

g_REPLICA = Replica()

OUTPUT_FOLDER_NAME = "sensibilities/c4"

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
        


def get_route_pickup(camion: Camion, t_ss: int, pos_camion, clientes_already_atendidos: list[int]):
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

        if clientes_already_atendidos[i] != INF:
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
def solve_myopic_pickup(clientes_already_atendidos: list[int], identifier = "#pickup") -> list:
    '''Returns (clientes_atendidos: list[int], posiciones_camion: list[(t_ss, pos_tuple)])\n
    clientes_atendidos es una lista de tiempos de atención (INF si no es atendido)\n
    posiciones_camion: es la posición del camión para cada segundo (t, (x, y))'''
    global g_obj_pickup, g_next_pickup_spawn_time # ooooh, me definitely no likey
    global g_REPLICA

    if VERBOSE_PICKUP:
        print(f"Soy el pickup: {identifier}")

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
            route = get_route_pickup(camion, t_ss, camion_pos, clientes_already_atendidos)

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

def solve_M_myopic_pickup(num_trucks = N_PICKUP):
    '''Returns ((atendidos1, atendidos2, ... atendidos_N), (t_pos1, t_pos2, ..., t_posN))'''

    running_atendidos = [INF] * g_REPLICA.num_points

    mega_atendidos = []
    mega_tpos = []
    for truck_index in range(num_trucks):
        atendidos_i, t_pos_i = solve_myopic_pickup(running_atendidos, f"#p{truck_index}")

        mega_atendidos.append(atendidos_i)
        mega_tpos.append(t_pos_i)

        for i in range(len(running_atendidos)):
            a = atendidos_i[i]
            if a != INF:
                running_atendidos[i] = a

    return (mega_atendidos, mega_tpos)

# ------------- DELIVERIES --------------

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


def solve_N_myopic_deliveries(num_trucks = N_DELIVERY) -> list: #Untested
    '''Returns ((atendidos1, atendidos2, ... atendidos_N), (t_pos1, t_pos2, ..., t_posN))'''

    running_atendidos = [INF] * g_REPLICA.num_points

    mega_atendidos = []
    mega_tpos = []
    
    for truck_index in range(num_trucks):
        atendidos_i, t_pos_i = solve_deliveries_camion(running_atendidos, f"#d{truck_index}")

        mega_atendidos.append(atendidos_i)
        mega_tpos.append(t_pos_i)

        for i in range(len(running_atendidos)):
            a = atendidos_i[i]
            if a != INF:
                running_atendidos[i] = a

    return (mega_atendidos, mega_tpos)

def create_df_atendidos(mega_atendidos_pickup, mega_atendidos_delivery):
    df_atendidos = pd.DataFrame()

    for i in range(N_PICKUP):
        df_atendidos[f"tiempos_c{i}"] = mega_atendidos_pickup[i]
    
    for i in range(N_DELIVERY):
        j = N_PICKUP + i
        df_atendidos[f"tiempos_c{j}"] = mega_atendidos_delivery[i]

    return df_atendidos

def calculate_utility_from_df_atendidos(df_atendidos):
    '''Returns (utilidad, [p1, p2, ..., pnum_pickups], [d1, d2, ..., dnum_deliveries])\n
    Con pi = # pickups atendidos por i, di = # deliveries atendidos por i'''
    # WHAT THE F*CK IS A FOR LOOP!!! https://www.youtube.com/watch?v=OUZwAefgisI

    indicadores = df_atendidos["indicador"]

    # pi = # pickups atendidos por i, di = # deliveries atendidos por i
    ps = [0] * (N_CAMIONES)
    ds = [0] * (N_CAMIONES)

    
    for j in range(len(indicadores)):
        for index_camion in range(N_CAMIONES):
            t_i = df_atendidos[f"tiempos_c{index_camion}"][j]

            if t_i < INF:
                if indicadores[j] == PICKUP:
                    ps[index_camion] += 1
                else:
                    ds[index_camion] += 1


        pickups_realizados = sum(ps)
        deliveries_realizados = sum(ds)

        utilidad = pickups_realizados + 2 * deliveries_realizados

    return (utilidad, ps, ds)

def print_desglose_utilidad(df_atendidos):
    utilidad, ps, ds = calculate_utility_from_df_atendidos(df_atendidos)

    print("DESGLOSE UTILIDAD")
    for i in range(N_CAMIONES):
        print(f"El camión {i} realizó {ps[i]}+{ds[i]} = {ps[i]+ds[i]} =  pickups+deliveries")

    print("La solución es factible con 101% certeza")
    print("---")
    u_tot = calc_total_U(df_atendidos)
    u_relativa = utilidad/u_tot
    print(f"La utilidad realizada es de {utilidad}/{u_tot} = {u_relativa*100:.2f}%")



def solve_replica_myopic_and_save(output_folder: str, replica = None):
    global g_REPLICA

    g_REPLICA = replica

    if VERBOSE_MYOPIC:
        print(f"Running a Myopic solution of {g_REPLICA}")

    mega_atendidos_pickup, mega_t_pos_pickup = solve_M_myopic_pickup()
    if VERBOSE_MYOPIC:
        print(f"{N_PICKUP} Camión Pickups processed...", len(mega_atendidos_pickup))

    mega_atendidos_deliveries, mega_t_pos_deliveries = solve_N_myopic_deliveries()
    if VERBOSE_MYOPIC:
        print(f"{N_DELIVERY} Camión Deliveries processed...", len(mega_atendidos_deliveries))

    df_atendidos = create_df_atendidos(mega_atendidos_pickup, mega_atendidos_deliveries)

    df_atendidos = add_columna_indicador(df_atendidos, g_REPLICA)

    atendidos_path = os.path.join(output_folder, "clientes_atendidos.csv")
    df_atendidos.to_csv(atendidos_path, index=False)

    print(f"Saved to {atendidos_path}")

    if VERBOSE_MYOPIC:
        print_desglose_utilidad(df_atendidos)

def add_columna_indicador(df, replica: Replica):
    df["indicador"] = replica.indicador

    return df


import pandas as pd

# ------------------ KPI'S ------------------

'''In goes a 'worked' folder, out comes the KPI's'''

from src.constants import *
from src.classes import *
from src.instance_loader import *

import pandas as pd

VERBOSE_KPIS = False

def calc_total_U(df_ca):
    U = 0
    for _id in df_ca["indicador"][1:]: # First is el máldito DEPOT
        
        if _id == PICKUP:
            U += 1
        else:
            U += 2

    return U

def U_relativa_kpi(df_ca):
    U_todos_atendidos = calc_total_U(df_ca)

    u_p_d = calculate_utility_from_df_atendidos(df_ca)
    U_conseguido = u_p_d[0]

    U_relativo = U_conseguido / U_todos_atendidos

    if VERBOSE_KPIS:
        print(f"U_relativo: {U_conseguido}/{U_todos_atendidos} = {U_relativo*100}%")

    return U_relativo

def kpis_dict_from_df_clientes_atendidos(df_ca: pd.DataFrame, replica: Replica):

    kpi_u = U_relativa_kpi(df_ca)

    return {"U_relativa": kpi_u}

def analysis_instancia_path(analysis_path: str, instance_index: int):
    instancia_folder_name = f"Instancia_{LABELS_INSTANCIAS[instance_index]}"

    return os.path.join(analysis_path, instancia_folder_name) 

# TODO: Move this to ALL_FILEPATHS
def analysis_replica_path(analysis_path: str, instance_index: int, replica_index: int):
    path = analysis_instancia_path(analysis_path, instance_index)
    name = f"{LABELS_INSTANCIAS[instance_index]}_replica_{replica_index}"

    return os.path.join(path, name)


def solve_and_save_replicas(analysis_path, instance_index, indices_replicas):
    print("AAAA")
    
    instance = load_instance_data(DATA_SRC[instance_index])

    for r_id in indices_replicas:
        # 1) solve the replica
        out_path = analysis_replica_path(analysis_path, instance_index, r_id)
        replica = get_replica_from_instancia(instance, r_id)

        solve_replica_myopic_and_save(out_path, replica)

    print("BBBBB")

def create_resumen_kpis(analysis_path, indices_instancias, indices_replicas):
    print("CCCC")
    
    
    df = pd.DataFrame()

    i_indices = []
    r_indices = []
    u_rels = []
    
    for instance_index in indices_instancias:
        instance = load_instance_data(DATA_SRC[instance_index])
        for r_id in indices_replicas:
            # 2) Evaluate
            out_path = analysis_replica_path(analysis_path, instance_index, r_id)
            ca_path = os.path.join(out_path, "clientes_atendidos.csv")

            df_ca = pd.read_csv(ca_path)
            replica = get_replica_from_instancia(instance, r_id)
            kpis = kpis_dict_from_df_clientes_atendidos(df_ca, replica)

            i_indices.append(instance_index)
            r_indices.append(r_id)
            u_rels.append(kpis["U_relativa"])


    df["Instancia"] = i_indices
    df["replica"] = r_indices
    df["U_relativa"] = u_rels

    dest_unk = os.path.join(analysis_path, "CamionSummary.csv")
    df.to_csv(dest_unk, index=False)
    print("DDDD")

def create_analysis_directories(analysis_folder_path: str, instance_indexes: list, replicas_indexes: list):
    
    num_written_folders = 0
    for instance_index in instance_indexes:
        num_written_folders += 1

        for replica_index in replicas_indexes:
            replica_path = analysis_replica_path(analysis_folder_path, instance_index, replica_index)
            os.makedirs(replica_path, exist_ok=True)
            num_written_folders += 1

    num_written_folders = num_written_folders

    print(f"Wrote {num_written_folders} folders to {analysis_folder_path}")

def create_myopic_analysis_folder(analysis_path, instancias_indices = [0,1,2,3], num_replicas = 20):
    replicas_indices = list(range(num_replicas))

    create_analysis_directories(analysis_path, instancias_indices, replicas_indices)
    
    for instance_index in instancias_indices:
        solve_and_save_replicas(analysis_path, instance_index, replicas_indices)
    
    create_resumen_kpis(analysis_path, instancias_indices, replicas_indices)

if __name__ == "__main__":
    num_replicas = 10
    instancias_indices = [0, 1, 2, 3]
    
    aname = f"c{N_CAMIONES}_{N_PICKUP}_pkups{N_DELIVERY}_dlvrs_sanalysis"
    analysis_path = os.path.join("outputs", "myopic_outputs", aname)

    create_myopic_analysis_folder(analysis_path, instancias_indices, num_replicas)


