'''Esta gueno el visualizador, heatmaps muy xds con los gradient bars'''
# TODO: usar nueva clase de réplica en vez de g_INSTANCE jajajjaja


import matplotlib as mpl
import matplotlib.pyplot as plt

from src.constants import *
from matplotlib.widgets import Slider, RadioButtons, CheckButtons
from mpl_toolkits.axes_grid1 import make_axes_locatable

import pandas as pd

solved_camiones_folder = os.path.join("outputs", "myopic_outputs", "testingv4")

g_BACKGROUND_IMAGE = None
g_INSTANCE_LIST = []
g_INSTANCE_INDEX = 0
g_CURRENT_REPLICA = 0
g_CURRENT_TIME = END_TIME #(START_TIME+END_TIME)//2
g_INSTANCE = None

g_T_POS_CAMIONES_DF = pd.DataFrame()
g_CLIENTES_ATENDIDOS_DF = pd.DataFrame()

IMAGE_DPI = 300 # Kinda weird ngl
FIGURE_WIDTH_PX = 1600
FIGURE_HEIGHT_PX = 900

MARKER_PICKUP = "*b"
MARKER_DELIVERY = "dg"
MARKER_DEPOT = "8k"

TRON_TRAIL = [".c", ".m", ".y"]
MARKERS_CAMIONES = ["Pc", "Pm", "Py"]
MARKERS_ATENDIDOS = ["*c", "dm", "dy"]

MARKER_SIZE = 20
TRON_SIZE = MARKER_SIZE/4

LINEWIDTH = 1
POLYGON_STROKE_WIDTH = 0.1

cb_show_grid_label = "Mostrar Grilla y ejes"
cb_manhattan_background = "Manhattan fotorealístico"   
cb_heatmap = "heatmap"
cb_show_camiones = "Mostrar camiones"
cb_tron_trails = "FJ's Tron Trails"
cb_save_images_label = "Guardar Imágenes"

VISUAL_CONFIG_DICT = {
    cb_show_grid_label: False,
    cb_manhattan_background: False,
    cb_heatmap: False,
    cb_show_camiones: True,
    cb_tron_trails: True,
    cb_save_images_label: False
}

CONTROL_PANEL_WIDTH = 0.225 # Percentage
CONTROL_PANEL_PAD = 0.05

# ------------------------------------------- END CONSTANTS -----------------------------------------
def save_graph(destination_filepath: str): # This should probably go in another script
    '''e.g. 2400 x 2400 with (8, 8), dpi = 300'''
    print(f"Saving plot to {destination_filepath}")

    plt.savefig(destination_filepath, dpi=IMAGE_DPI)
# --------------------------- Drawing with MatPlotLib -----------------------------

def plot_camiones(ax_plot: plt.Axes):
    '''Mi amigo NO conoce los for loops!'''
    global g_T_POS_CAMIONES_DF # Explicit

    time_index = max(0, g_CURRENT_TIME-CAMIONES_START_ss)

    c1_x = g_T_POS_CAMIONES_DF["c1_x"][time_index]
    c1_y = g_T_POS_CAMIONES_DF["c1_y"][time_index]

    c2_x = g_T_POS_CAMIONES_DF["c2_x"][time_index]
    c2_y = g_T_POS_CAMIONES_DF["c2_y"][time_index]

    c3_x = g_T_POS_CAMIONES_DF["c3_x"][time_index]
    c3_y = g_T_POS_CAMIONES_DF["c3_y"][time_index]

    if VISUAL_CONFIG_DICT[cb_tron_trails]:
        # h is for history!
        h1x = g_T_POS_CAMIONES_DF["c1_x"][:time_index]
        h1y = g_T_POS_CAMIONES_DF["c1_y"][:time_index]

        h2x = g_T_POS_CAMIONES_DF["c2_x"][:time_index]
        h2y = g_T_POS_CAMIONES_DF["c2_y"][:time_index]

        h3x = g_T_POS_CAMIONES_DF["c3_x"][:time_index]
        h3y = g_T_POS_CAMIONES_DF["c3_y"][:time_index]

        tt_c1,  = ax_plot.plot(h1x, h1y, TRON_TRAIL[0],  markersize=TRON_SIZE)
        tt_c2,  = ax_plot.plot(h2x, h2y, TRON_TRAIL[1],  markersize=TRON_SIZE)
        tt_c3,  = ax_plot.plot(h3x, h3y, TRON_TRAIL[2],  markersize=TRON_SIZE)

    
    l_c1, = ax_plot.plot(c1_x, c1_y, MARKERS_CAMIONES[0],  markersize=MARKER_SIZE, label="C. #1 (Pickup)\n")
    l_c2, = ax_plot.plot(c2_x, c2_y, MARKERS_CAMIONES[1],  markersize=MARKER_SIZE, label="C. #2 (Delivery)\n")
    l_c3, = ax_plot.plot(c3_x, c3_y, MARKERS_CAMIONES[2],  markersize=MARKER_SIZE, label="C. #3 (Delivery)\n")

def get_atendidos_xs_ys(tiempos_camion_i, points):
    '''Returns [xs: list[float], ys: list[float]]'''

    xs = []
    ys = []

    for j in range(len(tiempos_camion_i)):

        t_camion_i_point_j = tiempos_camion_i[j]

        if g_CURRENT_TIME >= t_camion_i_point_j:
            px, py = points[j]
            xs.append(px)
            ys.append(py)

    return [xs, ys]


def plot_atendidos(ax_plot: plt.Axes, points):
    global g_CLIENTES_ATENDIDOS_DF # Explicit

    tiempos_c1 = g_CLIENTES_ATENDIDOS_DF["tiempos_c1"]
    tiempos_c2 = g_CLIENTES_ATENDIDOS_DF["tiempos_c2"]
    tiempos_c3 = g_CLIENTES_ATENDIDOS_DF["tiempos_c3"]

    atendidos1 = get_atendidos_xs_ys(tiempos_c1, points)
    atendidos2 = get_atendidos_xs_ys(tiempos_c2, points)
    atendidos3 = get_atendidos_xs_ys(tiempos_c3, points)
        

    # Después es fácil cambiar los markers para cuando se separen
    l_a1, = ax_plot.plot(atendidos1[0], atendidos1[1], MARKERS_ATENDIDOS[0],  markersize=MARKER_SIZE, label=f"{len(atendidos1[0])} Atendidos (#1)\n")
    l_a2, = ax_plot.plot(atendidos2[0], atendidos2[1], MARKERS_ATENDIDOS[1],  markersize=MARKER_SIZE, label=f"{len(atendidos2[0])} Atendidos (#2)\n")
    l_a3, = ax_plot.plot(atendidos3[0], atendidos3[1], MARKERS_ATENDIDOS[2],  markersize=MARKER_SIZE, label=f"{len(atendidos3[0])} Atendidos (#3)\n")


def plot_points(points: list, indicadores: list, arrivals: list, ax_plot: plt.Axes):
    global VISUAL_CONFIG_DICT # Unnecessary, but explicit

    ax_plot.axhline(0, linewidth=0.5)
    ax_plot.axvline(0, linewidth=0.5)
    ax_plot.set_aspect('equal', adjustable='box')

    ax_plot.set_xlabel("x [m]")
    ax_plot.set_ylabel("y [m]")

    ax_plot.set_xlim(0, WIDTH_MAPA)
    ax_plot.set_ylim(0, HEIGHT_MAPA)
    
    ax_plot.ticklabel_format(style='plain', axis='both', useOffset=False)

    xs_pickups = []
    ys_pickups = []

    xs_delivery = []
    ys_delivery = []
    for i in range(len(points)):
        point = points[i]
        indicador = indicadores[i]

        # Solo muestra si ya existen
        arrival_time = arrivals[i]

        if g_CURRENT_TIME < arrival_time:
            # Do not include point
            continue 

        x, y = point

        if (x, y) == DEPOT_POS:
            continue

        if indicador == PICKUP:
            xs_pickups.append(x)
            ys_pickups.append(y)

        else:
            xs_delivery.append(x)
            ys_delivery.append(y)

    if VISUAL_CONFIG_DICT[cb_manhattan_background]:
        ax_plot.imshow(g_BACKGROUND_IMAGE, extent=[0, WIDTH_MAPA, 0, HEIGHT_MAPA])

    l0, = ax_plot.plot(xs_pickups, ys_pickups, MARKER_PICKUP, markersize=MARKER_SIZE, label=f"{len(xs_pickups)} Pickups\n")
    l1, = ax_plot.plot(xs_delivery, ys_delivery, MARKER_DELIVERY,  markersize=MARKER_SIZE, label=f"{len(xs_delivery)} Deliveries\n")
    l2, = ax_plot.plot(*DEPOT_POS, MARKER_DEPOT,  markersize=MARKER_SIZE, label="1 Supply Depot\n")
    
    # Se plottea encima:
    if VISUAL_CONFIG_DICT[cb_show_camiones]:
        plot_camiones(ax_plot)
        plot_atendidos(ax_plot, points)
    

    ax_plot.legend(loc='upper right', fontsize = "large")

    #print("# pickups: \t", len(xs_pickups))
    #print("# deliveries: \t", len(xs_delivery))

def get_figure_and_ax_plot():
    default_dpi = 100 # Default for matplotlib
    fig_width_inches = FIGURE_WIDTH_PX/default_dpi
    fig_height_inches = FIGURE_HEIGHT_PX/default_dpi

    fig, ax_plot = plt.subplots(figsize=(fig_width_inches, fig_height_inches))

    return (fig, ax_plot)


# ------------------ CONTROL PANEL & SLIDER ---------------------

slider_pad = 0.05
def create_slider_ax(fig, bottom = 0.05):
    s_width = 1 - 2*(CONTROL_PANEL_WIDTH + slider_pad)
    slider_rect = [CONTROL_PANEL_WIDTH + slider_pad, bottom, s_width, 0.03] # left, bottom, width, height as fractions of figure
    slider_ax = fig.add_axes(slider_rect)
    
    return slider_ax

def create_replica_slider(slider_ax):
    replicas_de_interes = range(NUM_REPLICAS)

    initial_p = replicas_de_interes[0]
    final_p = replicas_de_interes[-1]

    replica_slider = Slider(slider_ax, "Replica", initial_p, final_p, valstep = replicas_de_interes)

    return replica_slider

def get_discretized_time(precision_in_seconds = 60):
    '''returns a list of seconds!'''

    work_time_s = END_TIME - START_TIME
    num_steps = int(work_time_s / precision_in_seconds)

    discretized_time = []
    for step in range(num_steps):
        discretized_time.append(int(START_TIME + step*precision_in_seconds)) # Rounds down

    discretized_time.append(END_TIME)

    return discretized_time

def create_time_slider(slider_ax):
    times_of_interest = get_discretized_time()

    initial_t = times_of_interest[0]
    final_t = times_of_interest[-1]

    time_slider = Slider(slider_ax, "Tiempo", initial_t, final_t, valstep = times_of_interest)

    return time_slider

def create_control_panel():
    '''Creates the Control Panel and returns (radio_instances, check_visuals) Buttons'''
    global g_INSTANCE_INDEX

    rp = {"s": 100}
    fp = {"s": 100}
    cp = {"s": 100}

    raxis_instancia = plt.axes([0.01, 0.20, CONTROL_PANEL_WIDTH - 0.04, 0.20])
    radio_instances = RadioButtons(raxis_instancia, LABELS_INSTANCIAS, radio_props=rp)
    raxis_instancia.set_title("Instancia: ", loc="left")
    radio_instances.set_active(g_INSTANCE_INDEX) # Default

    labels_visuals = VISUAL_CONFIG_DICT.keys()
    caxis_visuals = plt.axes([0.01, 0.01, CONTROL_PANEL_WIDTH - 0.04, 0.15])
    check_visuals = CheckButtons(caxis_visuals, labels_visuals, actives=[VISUAL_CONFIG_DICT[key] for key in labels_visuals], frame_props=fp, check_props=cp)
    caxis_visuals.set_title("Visuals: ", loc="left")

    return (radio_instances, check_visuals)

def show_heatmap(ax_plot: plt.Axes, instancia, num_x_boxes = 10, num_y_boxes = 10):
    '''TODO: Fix gradient!!!'''
    counts = []
    for y in range(num_y_boxes):
        counts.append([0]*num_x_boxes)

    point_list = instancia.points

    km_x_width = 20000 // num_x_boxes
    km_y_height = 20000 // num_y_boxes

    num_total_points = 0
    for points in point_list:
        for point in points:
            x, y = point

            if (x, y) == DEPOT_POS:
                continue

            index_x = min(int(x // km_x_width), num_x_boxes-1)
            index_y = min(int(y // km_y_height), num_y_boxes-1)

            counts[index_y][index_x] += 1

            num_total_points += 1

    freqs = []
    for y in range(num_y_boxes):
        freqs.append([0]*num_x_boxes)
        for x in range(num_x_boxes):
            freqs[y][x] = counts[y][x]/num_total_points

    image = ax_plot.imshow(freqs, interpolation = 'nearest', origin = 'lower', vmin = 0, vmax = 0.001)

    #plt.colorbar(image)



def draw_main_graph(fig: plt.Figure, ax_plot: plt.Axes):
    '''Redibuja el plot del centro (con los puntos pickups/deliverys, etc.) nuevamente'''
    global g_INSTANCE, g_INSTANCE_INDEX, g_CURRENT_REPLICA

    ax_plot.cla()

    points = g_INSTANCE.points[g_CURRENT_REPLICA]
    indicadores = g_INSTANCE.indicador[g_CURRENT_REPLICA]
    arrivals = g_INSTANCE.arrivals[g_CURRENT_REPLICA]
    
    if VISUAL_CONFIG_DICT[cb_heatmap]:
        show_heatmap(ax_plot, g_INSTANCE_LIST[g_INSTANCE_INDEX], 40, 40)
        ax_plot.set_title(f"Heatmap Instancia {LABELS_INSTANCIAS[g_INSTANCE_INDEX]}")

    else:
        plot_points(points, indicadores, arrivals, ax_plot)
        ax_plot.set_title(f"Representación Instancia {LABELS_INSTANCIAS[g_INSTANCE_INDEX]}, réplica {g_CURRENT_REPLICA}")

    fig.canvas.draw_idle()


def update_screen_from_rb(replica_slider: Slider):
    '''Updates replica_slider (which draws the main graph)'''

    replica_slider.valstep = list(range(100))
    replica_slider.set_val(g_CURRENT_REPLICA)

def set_image_size(width_px, height_px, dpi):
    global FIGURE_HEIGHT_PX, FIGURE_WIDTH_PX, IMAGE_DPI
    IMAGE_DPI = dpi
    FIGURE_WIDTH_PX = width_px / (dpi/100)
    FIGURE_HEIGHT_PX = height_px / (dpi/100) # VOS CONFÍA PERRO


def launch_image_app(periodos_save_images = [1]):
    '''Todo'''
    return


def update_visuals_from_cb(check_buttons: CheckButtons):
    global VISUAL_CONFIG_DICT

    checked_labels = check_buttons.get_checked_labels()

    for key in VISUAL_CONFIG_DICT.keys():
        VISUAL_CONFIG_DICT[key] = (key in checked_labels)

    print(f"Updated Visuals from Check Buttons")

import numpy as np
from PIL import Image
from src.instance_loader import *
def init_cool_app():
    global g_INSTANCE_LIST, g_INSTANCE, g_INSTANCE_INDEX, g_BACKGROUND_IMAGE, g_T_POS_CAMIONES_DF, g_CLIENTES_ATENDIDOS_DF

    g_INSTANCE_LIST = load_default_instances()

    g_INSTANCE = g_INSTANCE_LIST[g_INSTANCE_INDEX]

    g_BACKGROUND_IMAGE = np.asarray(Image.open(MANHATTAN_FILEPATH))

    g_T_POS_CAMIONES_DF = pd.read_csv(os.path.join(solved_camiones_folder, "posiciones_camiones.csv"))
    g_CLIENTES_ATENDIDOS_DF = pd.read_csv(os.path.join(solved_camiones_folder, "clientes_atendidos.csv"))

    print("Initialized correctly")
    

def launch_cool_app():
    '''Initializes and shows the Control Panel + sector_plot + Slider\n\nCAUTION: save_images = True, will cause flickering!'''

    # Move outside later
    init_cool_app()

    fig, ax_plot = get_figure_and_ax_plot()

    # Sliders
    plt.subplots_adjust(bottom=0.15)
    replica_slider_ax = create_slider_ax(fig, bottom=0.02)
    replica_slider = create_replica_slider(replica_slider_ax)

    time_slider_ax = create_slider_ax(fig, bottom=0.07)
    time_slider = create_time_slider(time_slider_ax)
    
    # ------- Control Panel ---------
    plt.subplots_adjust(left=CONTROL_PANEL_WIDTH+CONTROL_PANEL_PAD)
    radio_instances, check_visuals = create_control_panel()

    def rb_instance_func(label):
        '''Changes the current Instance being displayed'''
        global g_INSTANCE_LIST, g_INSTANCE, g_INSTANCE_INDEX
        print(f"Changing instancia to: {label}")
        
        g_INSTANCE_INDEX = LABELS_INSTANCIAS.index(label)
        g_INSTANCE = g_INSTANCE_LIST[g_INSTANCE_INDEX]

        update_screen_from_rb(replica_slider)

    def cb_visual_func(label): # label is not used on purpose
        update_visuals_from_cb(check_visuals)

        update_screen_from_rb(replica_slider)
             
    radio_instances.on_clicked(rb_instance_func)
    check_visuals.on_clicked(cb_visual_func)

    # -------- END CONTROL PANEL --------

    def update_from_replica_slider(replica):
        global g_CURRENT_REPLICA
        g_CURRENT_REPLICA = replica

        draw_main_graph(fig, ax_plot)

    def update_from_time_slider(time):
        global g_CURRENT_TIME
        g_CURRENT_TIME = time

        time_slider.valtext.set_text(seconds_to_hh_mm_ss(g_CURRENT_TIME))
        draw_main_graph(fig, ax_plot)

    replica_slider.on_changed(update_from_replica_slider)
    replica_slider.set_val(g_CURRENT_REPLICA)

    time_slider.on_changed(update_from_time_slider)
    time_slider.set_val(g_CURRENT_TIME)

    plt.show()

if __name__ == "__main__":
    print("Running ALL_visualizador.py!\n")

    launch_cool_app()
