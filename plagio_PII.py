'''Plagio de mi práctica II, MUY MUY DESORDENADO, TODO TREMENDO REFACTORIZAR, DO NOT TRY TO UNDERSTAND'''

import matplotlib.pyplot as plt

from matplotlib.widgets import Slider, RadioButtons, CheckButtons
from mpl_toolkits.axes_grid1 import make_axes_locatable

g_INSTANCIAS_LIST = []
g_POINTS_LIST = []
g_INSTANCE_INDEX = 0

IMAGE_DPI = 300 # Kinda weird ngl
FIGURE_WIDTH_PX = 1000
FIGURE_HEIGHT_PX = 800

MARKER = " " # or "."
LINEWIDTH = 1
POLYGON_STROKE_WIDTH = 0.1
POLYGON_EDGE_COLOUR = "gray"

cb_square_plots_label = "Plot Cuadrado"
cb_desplazar_ejes_al_origen = "Origen en (0, 0)"
cb_fill_in_shapes_label = "Rellenar -"
cb_show_grid_label = "Mostrar Grilla"
cb_show_gradient_text_boxes_label = "-"
cb_heatmap = "heatmap"
cb_save_images_label = "Guardar Imágenes"

VISUAL_CONFIG_DICT = {
    cb_square_plots_label: False,
    cb_desplazar_ejes_al_origen: False,
    cb_fill_in_shapes_label: True,
    cb_show_grid_label: True,
    cb_show_gradient_text_boxes_label: True,
    cb_heatmap: True,
    cb_save_images_label: True
}

CONTROL_PANEL_WIDTH = 0.225 # Percentage
CONTROL_PANEL_PAD = 0.05
GRADIENT_WIDTH = "4%" # What does this mean?
# ------------------------------------------- END CONSTANTS -----------------------------------------

def save_graph(destination_filepath: str): # This should probably go in another script
    '''e.g. 2400 x 2400 with (8, 8), dpi = 300'''
    print(f"Saving plot to {destination_filepath}")

    plt.savefig(destination_filepath, dpi=IMAGE_DPI)
# --------------------------- Drawing with MatPlotLib -----------------------------

def plot_points(points: list, cell_values: list, ax_plot):
    global VISUAL_CONFIG_DICT # Unnecessary, but explicit

    ax_plot.axhline(0, linewidth=0.5)
    ax_plot.axvline(0, linewidth=0.5)
    ax_plot.set_aspect('equal', adjustable='box')

    ax_plot.set_xlabel("")
    ax_plot.set_ylabel("")

    x1, x2, y1, y2 = (0, 20000, 0, 20000)

    ax_plot.set_xlim(x1, x2)
    ax_plot.set_ylim(y1, y2)
    
    ax_plot.ticklabel_format(style='plain', axis='both', useOffset=False)

    xs = []
    ys = []
    for point in points:
        xs.append(point[0])
        ys.append(point[1])

    l0, = ax_plot.plot(xs, ys, "bo")

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

    periodo_slider = Slider(slider_ax, "Periodo", initial_p, final_p, valstep = periodos_de_interes)

    return periodo_slider

def create_control_panel():
    '''Creates the Control Panel and returns (None, None, radio_modo, check_visuals) Buttons'''
    rp = {"s": 100}
    fp = {"s": 100}
    cp = {"s": 100}

    # Actualmente son los únicos sectores que funcionan, muy creo?
    '''
    labels_sector = (VCL2_vega_str, VCL3_vega_str, VCL2_vega_y_canal_str, VCL3_vega_y_canal_str)
    raxis_sector = plt.axes([0.01, 0.80, CONTROL_PANEL_WIDTH - 0.04, 0.15])
    radio_sector = RadioButtons(raxis_sector, labels_sector, radio_props=rp)
    raxis_sector.set_title("Sector:", loc="left")
    radio_sector.set_active(labels_sector.index(backend.g_CURRENT_SECTOR_STR))
    
    labels_escenario = [e.nombre for e in ALL_ESCENARIOS]
    raxis_escenario = plt.axes([0.01, 0.45, CONTROL_PANEL_WIDTH - 0.04, 0.30])
    radio_escenario = RadioButtons(raxis_escenario, labels_escenario, radio_props=rp)
    raxis_escenario.set_title("Escenario: ", loc="left")
    radio_escenario.set_active(labels_escenario.index(backend.g_CURRENT_ESCENARIO.nombre))
    '''

    labels_instancia = ["I", "II", "III", "IV"]
    raxis_instancia = plt.axes([0.01, 0.20, CONTROL_PANEL_WIDTH - 0.04, 0.20])
    radio_instancia = RadioButtons(raxis_instancia, labels_instancia, radio_props=rp)
    raxis_instancia.set_title("Instancia: ", loc="left")
    radio_instancia.set_active(labels_instancia.index("I")) # Default

    labels_visuals = VISUAL_CONFIG_DICT.keys()
    caxis_visuals = plt.axes([0.01, 0.01, CONTROL_PANEL_WIDTH - 0.04, 0.15])
    check_visuals = CheckButtons(caxis_visuals, labels_visuals, actives=[VISUAL_CONFIG_DICT[key] for key in labels_visuals], frame_props=fp, check_props=cp)
    caxis_visuals.set_title("Visuals: ", loc="left")

    return (None, None, radio_instancia, check_visuals)

def show_heat_map(instancia, num_x_boxes = 10, num_y_boxes = 10):

    counts = []
    for y in range(num_y_boxes):
        counts.append([0]*num_x_boxes)

    point_list = instancia.points

    km_x_width = 20000 // num_x_boxes
    km_y_height = 20000 // num_y_boxes

    for points in point_list:
        for point in points:
            index_x = min(int(point[0] // km_x_width), 9)
            index_y = min(int(point[1] // km_y_height), 9)

            print(index_x, index_y)
            counts[index_y][index_x] += 1


    for y in range(num_y_boxes):
        print(counts[y])


def draw_main_graph(fig: plt.Figure, ax_plot: plt.Axes):
    '''For example, draws the current Sector as a graph of coloured cells'''
    global g_POINTS_LIST, g_INSTANCIAS_LIST

    ax_plot.cla()

    points = g_POINTS_LIST[g_CURRENT_PERIODO]
    
    plot_points(points, None, ax_plot)

    if VISUAL_CONFIG_DICT[cb_heatmap]:
        show_heat_map(g_INSTANCIAS_LIST[g_INSTANCE_INDEX])

    ax_plot.set_title("Representación FOTORealística de Manhattan v2")

    

    fig.canvas.draw_idle()

g_CURRENT_PERIODO = 0
def update_screen_from_rb(periodo_slider: Slider):
    '''periodo_slider (which draws the main graph)'''

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

def launch_cool_app(instancias):
    ''' Shows the Control Panel + sector_plot + Slider\n\nCAUTION: save_images = True, will cause flickering!'''
    global g_POINTS_LIST, g_INSTANCIAS_LIST

    g_INSTANCIAS_LIST = instancias
    g_POINTS_LIST = instancias[0].points

    fig, ax_plot = get_figure_and_ax_plot()

    # Slider
    plt.subplots_adjust(bottom=0.15)
    slider_ax = create_slider_ax(fig)
    periodo_slider = create_periodo_slider(slider_ax)
    
    # ------- Control Panel ---------
    plt.subplots_adjust(left=CONTROL_PANEL_WIDTH+CONTROL_PANEL_PAD)
    radio_sector, radio_escenario, radio_modo, check_visuals = create_control_panel()

    def rb_instancia_func(label):
        print(f"Changing instancia to: {label}")
        global g_POINTS_LIST, g_INSTANCE_INDEX
        g_INSTANCE_INDEX = ["I", "II", "III", "IV"].index(label)

        g_POINTS_LIST = g_INSTANCIAS_LIST[g_INSTANCE_INDEX].points
        update_screen_from_rb(periodo_slider)

    def cb_visual_func(label):
        update_visuals_from_cb(check_visuals)

        update_screen_from_rb(periodo_slider)
             
    radio_modo.on_clicked(rb_instancia_func)
    check_visuals.on_clicked(cb_visual_func)

    # -------- END CONTROL PANEL --------

    def update_from_slider(periodo):
        global g_CURRENT_PERIODO

        g_CURRENT_PERIODO = periodo

        draw_main_graph(fig, ax_plot)

        '''
        if VISUAL_CONFIG_DICT[cb_save_images_label]:
            image_filepath = get_and_create_image_filepath(backend.get_current_nombre_escenario_sector(), backend.g_CURRENT_ESCENARIO, backend.g_CURRENT_PERIODO, backend.g_CURR_MODE, False)
            save_graph(image_filepath)
        '''

    periodo_slider.on_changed(update_from_slider) # Move this to after the for loop if you don't like double image creation

    periodo_slider.set_val(1)

    plt.show()
    


if __name__ == "__main__":
    print("Running App?\n")
