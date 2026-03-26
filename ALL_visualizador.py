'''Plagio de mi práctica II, MUY MUY DESORDENADO, TODO TREMENDO REFACTORIZAR, DO NOT TRY TO UNDERSTAND'''

import matplotlib.pyplot as plt

from src.constants import *
from matplotlib.widgets import Slider, RadioButtons, CheckButtons
from mpl_toolkits.axes_grid1 import make_axes_locatable

g_INSTANCE_LIST = []
g_INSTANCE_INDEX = 0
g_CURRENT_PERIODO = 0
g_INSTANCE = None

IMAGE_DPI = 300 # Kinda weird ngl
FIGURE_WIDTH_PX = 1000
FIGURE_HEIGHT_PX = 800

MARKER_PICKUP = "*b"
MARKER_DELIVERY = ".r"
MARKER_DEPOT = ".g"

LINEWIDTH = 1
POLYGON_STROKE_WIDTH = 0.1

cb_show_grid_label = "Mostrar Grilla"
cb_manhattan_background = "Fondo Foto-Realísitico"   
cb_heatmap = "heatmap"
cb_save_images_label = "Guardar Imágenes"

VISUAL_CONFIG_DICT = {
    cb_show_grid_label: True,
    cb_manhattan_background: False,
    cb_heatmap: False,
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

def plot_points(points: list, indicadores: list, ax_plot):
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

        x, y = point

        if (x, y) == DEPOT_POS:
            continue

        if indicador:
            xs_pickups.append(x)
            ys_pickups.append(y)
        else:
            xs_delivery.append(x)
            ys_delivery.append(y)

    l0, = ax_plot.plot(xs_pickups, ys_pickups, MARKER_PICKUP)
    l1, = ax_plot.plot(xs_delivery, ys_delivery, MARKER_DELIVERY)
    l2, = ax_plot.plot(*DEPOT_POS, MARKER_DEPOT)

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
def create_slider_ax(fig):
    s_width = 1 - 2*(CONTROL_PANEL_WIDTH + slider_pad)
    slider_rect = [CONTROL_PANEL_WIDTH + slider_pad, 0.05, s_width, 0.03] # left, bottom, width, height as fractions of figure
    slider_ax = fig.add_axes(slider_rect)
    
    return slider_ax

def create_periodo_slider(slider_ax):
    periodos_de_interes = range(100)

    initial_p = periodos_de_interes[0]
    final_p = periodos_de_interes[-1]

    periodo_slider = Slider(slider_ax, "Period", initial_p, final_p, valstep = periodos_de_interes)

    return periodo_slider

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
    '''TODO'''
    counts = []
    for y in range(num_y_boxes):
        counts.append([0]*num_x_boxes)

    point_list = instancia.points

    km_x_width = 20000 // num_x_boxes
    km_y_height = 20000 // num_y_boxes

    for points in point_list:
        for point in points:
            x, y = point

            if (x, y) == DEPOT_POS:
                continue

            index_x = min(int(x // km_x_width), num_x_boxes-1)
            index_y = min(int(y // km_y_height), num_y_boxes-1)

            counts[index_y][index_x] += 1

    ax_plot.imshow(counts , interpolation = 'nearest', origin = 'lower')



def draw_main_graph(fig: plt.Figure, ax_plot: plt.Axes):
    '''Redibuja el plot del centro (con los puntos pickups/deliverys, etc.) nuevamente'''
    global g_INSTANCE

    ax_plot.cla()

    points = g_INSTANCE.points[g_CURRENT_PERIODO]
    indicadores = g_INSTANCE.indicador[g_CURRENT_PERIODO]
    
    

    if VISUAL_CONFIG_DICT[cb_heatmap]:
        show_heatmap(ax_plot, g_INSTANCE_LIST[g_INSTANCE_INDEX], 40, 40)
        ax_plot.set_title(f"Heatmap Instancia {LABELS_INSTANCIAS[g_INSTANCE_INDEX]}")

    else:
        plot_points(points, indicadores, ax_plot)
        ax_plot.set_title("Representación FOTORealística de Manhattan v3")

    fig.canvas.draw_idle()


def update_screen_from_rb(periodo_slider: Slider):
    '''Updates periodo_slider (which draws the main graph)'''

    periodo_slider.valstep = list(range(100))
    periodo_slider.set_val(g_CURRENT_PERIODO)

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

from src.instance_loader import *
def init_cool_app():
    global g_INSTANCE_LIST, g_INSTANCE, g_INSTANCE_INDEX

    g_INSTANCE_LIST = load_default_instances()

    g_INSTANCE = g_INSTANCE_LIST[g_INSTANCE_INDEX]

    print("Initialized correctly")
    

def launch_cool_app():
    '''Initializes and shows the Control Panel + sector_plot + Slider\n\nCAUTION: save_images = True, will cause flickering!'''

    # Move outside later
    init_cool_app()

    fig, ax_plot = get_figure_and_ax_plot()

    # Slider
    plt.subplots_adjust(bottom=0.15)
    slider_ax = create_slider_ax(fig)
    periodo_slider = create_periodo_slider(slider_ax)
    
    # ------- Control Panel ---------
    plt.subplots_adjust(left=CONTROL_PANEL_WIDTH+CONTROL_PANEL_PAD)
    radio_instances, check_visuals = create_control_panel()

    def rb_instance_func(label):
        '''Changes the current Instance being displayed'''
        global g_INSTANCE_LIST, g_INSTANCE, g_INSTANCE_INDEX
        print(f"Changing instancia to: {label}")
        
        g_INSTANCE_INDEX = LABELS_INSTANCIAS.index(label)
        g_INSTANCE = g_INSTANCE_LIST[g_INSTANCE_INDEX]

        update_screen_from_rb(periodo_slider)

    def cb_visual_func(label): # label is not used on purpose
        update_visuals_from_cb(check_visuals)

        update_screen_from_rb(periodo_slider)
             
    radio_instances.on_clicked(rb_instance_func)
    check_visuals.on_clicked(cb_visual_func)

    # -------- END CONTROL PANEL --------

    def update_from_slider(periodo):
        global g_CURRENT_PERIODO
        g_CURRENT_PERIODO = periodo

        draw_main_graph(fig, ax_plot)

    periodo_slider.on_changed(update_from_slider)
    periodo_slider.set_val(1)

    plt.show()

if __name__ == "__main__":
    print("Running ALL_visualizador.py?\n")

    launch_cool_app()
