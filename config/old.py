'''Defuncts'''

def check__depot_instancias(instancias):
    count = 0
    
    epsilon = 0.1
    for instancia in instancias:
        for point_list in instancia.points:
            for point in point_list:
                if abs(point[0] - 10000) + abs(point[1] - 10000) < epsilon:
                    count += 1

    print("Count: ", count)

def show_points(instancia: InstanceData):
    # Mañana agregar un slider para cual de los 100 tiempos mostrar
    fig, ax = plt.subplots()

    point_lists = instancia.points

    xs = []
    ys = []
    for point in point_lists[0]:
        xs.append(point[0])
        ys.append(point[1])

    l0, = ax.plot(xs, ys, "bo")

    plt.title("Representación Realística de Manhattan")

    plt.show()