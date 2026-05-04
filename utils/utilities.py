# Archivo con funciones generales que permiten el desarrollo del código. Nada muy específico.
import matplotlib.pyplot as plt


def rtb_feasibility_check(route:list, actual_time: int) -> bool:
    '''
    Funcion que recibe una ruta en formato simulated_data y retorna un booleano si es factible el RTB
    '''

def feasibility_check(route: list, actual_time: int) -> bool:
    '''
    Funcion que recibe una lista de clientes a visitar en formato simulated_data y retorna un booleano si es factible
    '''




def view_raw_data(data, target: str) -> None:

    '''
    Método que imprime en histogramas los datos de todas las isntancias asociadas a scen_{target}_sample.pkl
    Con este metodo saqué los plots de data_analyisis.md
    '''
    for k in range(len(data)):

        if target == 'arrivals':
            puntos      = data[k].arrivals
        elif target == 'deadlines':
            puntos      = data[k].deadlines
        elif target == 'points':
            puntos      = data[k].deadlines #esta no se si funcione, no lo he probado
        elif target == 'ready_times':
            puntos      = data[k].ready_times
        elif target == 'service_times':
            puntos      = data[k].ready_times

        counter     = 0
        total       = 0
        points      = []
        timeborder  = 60 * 60 * 9 # 9 horas
        for i in range(len(puntos)):
            for j in range(len(puntos[i])):
                if int(puntos[i][j]) <= timeborder:
                    counter += 1
                points.append(puntos[i][j])
                total += 1


        print(f'Instancia: {k + 1}, counter: {counter}. Proportion: {100 * counter / total}%')
        plt.title(f'Distribuición de ingreso de solicitudes para la instancia {k + 1}')
        plt.ylabel('Número de solicitudes')
        plt.xlabel('Tiempo (s)')
        plt.axvline(x=timeborder, color='blue', linestyle='--')
        plt.hist(points, 26, rwidth=0.9, color='black')
        plt.show()