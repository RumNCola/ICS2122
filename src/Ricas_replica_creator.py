import numpy as np
import polars as pl
import os
import time
from datetime import datetime

out_folder = "simulated_data"

def replica(instancia, replicas, t0 = 8.5 * 60 * 60):
    '''
    Método que samplea {replicas} escenarios distintos según la {instancia} y retorna los datos asociados, desde t0 hasta 17:00 en un
    dataframe de polars. Además, guarda el material sampleado en un .parquet.
    '''
    if instancia == 1:
        cant = np.random.randint(161, 232, replicas) #Cantidad de clientes a simular

        indicador = []
        arrivals = []
        deadlines = []
        x = []
        y = []
        profits = []
        ready_times = []
        service_times = []
        rep = []

        p_delivery = 0.6209366
        for j in range(len(cant)):
            for i in range(cant[j]):

                # Indicador primero
                u = np.random.uniform(0,1)
                if u < p_delivery:
                    ind = "False"
                    indicador.append(ind) #Salio delivery
                else:
                    ind = "True"
                    indicador.append(ind) #Salio pickup

                # Tiempos de llegada
                if ind == "False":
                    arrival = np.random.uniform(31500, 55800) #De 8.45 a 15.30
                    arrivals.append(arrival)
                elif ind == "True":
                    arrival = np.random.uniform(31500, 56700) #De 8.45 a 15.45
                    arrivals.append(arrival)
                
                # ready times
                if ind == "False":
                    redi = arrival + 900 #15 min despues
                    ready_times.append(redi)
                elif ind == "True":
                    redi = arrival
                    ready_times.append(redi)
                
                # deadlines
                if ind == "False":
                    dead = redi + 10800 #3 hrs despues de redi
                    deadlines.append(dead)
                elif ind == "True":
                    dead = 61200 #Fin de horizonte
                    deadlines.append(dead)
                
                # Profits
                if ind == "False":
                    pft = 2
                    profits.append(pft)
                elif ind == "True":
                    pft = 1
                    profits.append(pft)

                # Service time
                service_times.append(180)

                # x e y
                x_i = np.random.uniform(0, 20000)
                y_i = np.random.uniform(0, 20000)
                x.append(x_i)
                y.append(y_i)

                rep.append(j)
    
    elif instancia == 2:
        cant = np.random.randint(171, 235, replicas) #Cantidad de clientes a simular
        p_delivery = 0.6701915

        indicador = []
        arrivals = []
        deadlines = []
        x = []
        y = []
        profits = []
        ready_times = []
        service_times = []
        rep = []

        for j in range(len(cant)):
            for i in range(cant[j]):

                # Indicador primero
                u = np.random.uniform(0,1)
                if u < p_delivery:
                    ind = "False"
                    indicador.append(ind) #Salio delivery
                else:
                    ind = "True"
                    indicador.append(ind) #Salio pickup

                # Tiempos de llegada
                if ind == "False":
                    p_zona1 = 0.1943
                    p_zona2 = 0.4948

                    u = np.random.uniform(0,1)
                    if u < p_zona1:
                        arrival = np.random.uniform(31500, 39600) #De 8.45 a 11:00
                        arrivals.append(arrival)
                    elif u < p_zona1 + p_zona2:
                        arrival = np.random.uniform(39600, 46800) #De 11:00 a 13:00
                        arrivals.append(arrival)
                    else:
                        arrival = np.random.uniform(46800, 55800) # De 13:00 a 15:30
                        arrivals.append(arrival)
                elif ind == "True":
                    p_zona1 = 0.2090
                    p_zona2 = 0.4727

                    u = np.random.uniform(0,1)
                    if u < p_zona1:
                        arrival = np.random.uniform(31500, 39600) #De 8.45 a 11:00
                        arrivals.append(arrival)
                    elif u < p_zona1 + p_zona2:
                        arrival = np.random.uniform(39600, 46800) #De 11:00 a 13:00
                        arrivals.append(arrival)
                    else:
                        arrival = np.random.uniform(46800, 56700) # De 13:00 a 15:45
                        arrivals.append(arrival)
                
                # ready times
                if ind == "False":
                    redi = arrival + 900 #15 min despues
                    ready_times.append(redi)
                elif ind == "True":
                    redi = arrival
                    ready_times.append(redi)
                
                # deadlines
                if ind == "False":
                    dead = redi + 10800 #3 hrs despues de redi
                    deadlines.append(dead)
                elif ind == "True":
                    dead = 61200 #Fin de horizonte
                    deadlines.append(dead)
                
                # Profits
                if ind == "False":
                    pft = 2
                    profits.append(pft)
                elif ind == "True":
                    pft = 1
                    profits.append(pft)

                # Service time
                service_times.append(180)

                # x e y
                x_i = np.random.uniform(0, 20000)
                y_i = np.random.uniform(0, 20000)
                x.append(x_i)
                y.append(y_i)
            
                rep.append(j)
            
    elif instancia == 3:
        cant = np.random.randint(165, 247, replicas) #Cantidad de clientes a simular
        p_delivery = 0.6608995

        indicador = []
        arrivals = []
        deadlines = []
        x = []
        y = []
        profits = []
        ready_times = []
        service_times = []
        rep = []

        for j in range(len(cant)):
            for i in range(cant[j]):

                # Indicador primero
                u = np.random.uniform(0,1)
                if u < p_delivery:
                    ind = "False"
                    indicador.append(ind) #Salio delivery
                else:
                    ind = "True"
                    indicador.append(ind) #Salio pickup

                # Tiempos de llegada
                if ind == "False": #Delivery
                    p_zona1 = 0.2231
                    p_zona2 = 0.4774

                    u = np.random.uniform(0,1)
                    if u < p_zona1:
                        arrival = np.random.uniform(31500, 39600) #De 8.45 a 11:00
                        arrivals.append(arrival)
                    elif u < p_zona1 + p_zona2:
                        arrival = np.random.uniform(39600, 46800) #De 11:00 a 13:00
                        arrivals.append(arrival)
                    else:
                        arrival = np.random.uniform(46800, 55800) # De 13:00 a 15:30
                        arrivals.append(arrival)
                elif ind == "True": #Pickup
                    p_zona1 = 0.2253
                    p_zona2 = 0.4479

                    u = np.random.uniform(0,1)
                    if u < p_zona1:
                        arrival = np.random.uniform(31500, 39600) #De 8.45 a 11:00
                        arrivals.append(arrival)
                    elif u < p_zona1 + p_zona2:
                        arrival = np.random.uniform(39600, 46800) #De 11:00 a 13:00
                        arrivals.append(arrival)
                    else:
                        arrival = np.random.uniform(46800, 56700) # De 13:00 a 15:45
                        arrivals.append(arrival)
                
                # ready times
                if ind == "False":
                    redi = arrival + 900 #15 min despues
                    ready_times.append(redi)
                elif ind == "True":
                    redi = arrival
                    ready_times.append(redi)
                
                # deadlines
                if ind == "False":
                    dead = redi + 10800 #3 hrs despues de redi
                    deadlines.append(dead)
                elif ind == "True":
                    dead = 61200 #Fin de horizonte
                    deadlines.append(dead)
                
                # Profits
                if ind == "False":
                    pft = 2
                    profits.append(pft)
                elif ind == "True":
                    pft = 1
                    profits.append(pft)

                # Service time
                service_times.append(180)

                # x e y
                if ind == "False":#Delivery
                    p_arriba = 0.5068
                    u = np.random.uniform(0,1)
                    if u < p_arriba: #Arriba
                        x_i = np.random.normal(10022.78, 2862.292)
                        if x_i < 0:
                            x_i = 0
                        if x_i > 20000:
                            x_i = 20000
                        y_i = np.random.normal(14712.9, 2004.336)
                        if y_i < 0:
                            y_i = 0
                        if y_i > 20000:
                            y_i = 20000

                        x.append(x_i)
                        y.append(y_i)
                    else: # Abajo
                        p_cola = 0.012
                        if np.random.uniform(0,1) < p_cola:
                            if np.random.uniform(0,1) < 0.5:
                                x_i = np.random.uniform(0,200)
                            else:
                                x_i = np.random.uniform(19800, 20000)
                        else:
                            x_i = np.random.beta(1.775272, 1.79102) #Entrega en [0,1]
                            x_i = 20000*x_i #Transformar a [0,20000]
                            if x_i < 0:
                                x_i = 0
                            if x_i > 20000:
                                x_i = 20000

                        y_i = np.random.normal(4943.167, 2123.399)
                        if y_i < 0:
                            y_i = 0
                        if y_i > 20000:
                            y_i = 20000
                            
                        x.append(x_i)
                        y.append(y_i)

                elif ind == "True": #Pickup
                    p_arriba = 0.5015
                    u = np.random.uniform(0,1)
                    if u < p_arriba:
                        x_i = np.random.normal(10037.04, 2922.686)
                        if x_i < 0:
                            x_i = 0
                        if x_i > 20000:
                            x_i = 20000

                        y_i = np.random.normal(14750.37, 1975.571)
                        if y_i < 0:
                            y_i = 0
                        if y_i > 20000:
                            y_i = 20000

                        x.append(x_i)
                        y.append(y_i)
                    else:
                        p_cola = 0.013
                        if np.random.uniform(0,1) < p_cola:
                            if np.random.uniform(0,1) < 0.5:
                                x_i = np.random.uniform(0, 200)
                            else:
                                x_i = np.random.uniform(19800, 20000)
                        else:
                            x_i = np.random.beta(1.836308, 1.846874) #Entrega en [0,1]
                            x_i = 20000*x_i #Transformar a [0,20000]
                            if x_i < 0:
                                x_i = 0
                            if x_i > 20000:
                                x_i = 20000
                        
                        y_i = np.random.normal(4943.167, 2123.399)
                        if y_i < 0:
                            y_i = 0
                        if y_i > 20000:
                            y_i = 20000
                            
                        x.append(x_i)
                        y.append(y_i)

                rep.append(j)

    elif instancia == 4:
        cant = np.random.randint(165, 247, replicas) #Cantidad de clientes a simular
        p_delivery = 0.6608995

        indicador = []
        arrivals = []
        deadlines = []
        x = []
        y = []
        profits = []
        ready_times = []
        service_times = []
        rep = []

        for j in range(len(cant)):
            for i in range(cant[j]):

                # Indicador primero
                u = np.random.uniform(0,1)
                if u < p_delivery:
                    ind = "False"
                    indicador.append(ind) #Salio delivery
                else:
                    ind = "True"
                    indicador.append(ind) #Salio pickup

                # Tiempos de llegada
                if ind == "False": #Delivery
                    p_zona1 = 0.2086
                    p_zona2 = 0.5017

                    u = np.random.uniform(0,1)
                    if u < p_zona1:
                        arrival = np.random.uniform(31500, 39600) #De 8.45 a 11:00
                        arrivals.append(arrival)
                    elif u < p_zona1 + p_zona2:
                        arrival = np.random.uniform(39600, 46800) #De 11:00 a 13:00
                        arrivals.append(arrival)
                    else:
                        arrival = np.random.uniform(46800, 55800) # De 13:00 a 15:30
                        arrivals.append(arrival)
                elif ind == "True": #Pickup
                    p_zona1 = 0.2032
                    p_zona2 = 0.4774

                    u = np.random.uniform(0,1)
                    if u < p_zona1:
                        arrival = np.random.uniform(31500, 39600) #De 8.45 a 11:00
                        arrivals.append(arrival)
                    elif u < p_zona1 + p_zona2:
                        arrival = np.random.uniform(39600, 46800) #De 11:00 a 13:00
                        arrivals.append(arrival)
                    else:
                        arrival = np.random.uniform(46800, 56700) # De 13:00 a 15:45
                        arrivals.append(arrival)
                
                # ready times
                if ind == "False":
                    redi = arrival + 900 #15 min despues
                    ready_times.append(redi)
                elif ind == "True":
                    redi = arrival
                    ready_times.append(redi)
                
                # deadlines
                if ind == "False":
                    dead = redi + 10800 #3 hrs despues de redi
                    deadlines.append(dead)
                elif ind == "True":
                    dead = 61200 #Fin de horizonte
                    deadlines.append(dead)
                
                # Profits
                if ind == "False":
                    pft = 2
                    profits.append(pft)
                elif ind == "True":
                    pft = 1
                    profits.append(pft)

                # Service time
                service_times.append(180)

                # x e y
                if ind == "False":#Delivery
                    p_der = 0.5061
                    p_izqa = 0.2455

                    u = np.random.uniform(0,1)
                    if u < p_der: #Derecha
                        x_i = np.random.normal(14972.16, 2032.986)
                        if x_i > 20000: #Meter a cuadrilla
                            x_i = 20000
                        if x_i < 0:
                            x_i = 0
                        
                        y_i = np.random.beta(3.208858, 3.186452)
                        y_i = 20000*y_i
                        if y_i > 20000: #Meter a cuadrilla
                            y_i = 20000
                        if y_i < 0:
                            y_i = 0
                        
                        x.append(x_i)
                        y.append(y_i)
                    elif u < p_der + p_izqa: #Izquierda arriba
                        x_i = np.random.normal(4961.03, 2055.79)
                        if x_i < 0:
                            x_i = 0
                        elif x_i > 20000:
                            x_i = 20000
                        
                        y_i = np.random.normal(14970.59, 2060.453)
                        if y_i > 20000:
                            y_i = 20000
                        elif y_i < 0:
                            y_i = 0
                        
                        x.append(x_i)
                        y.append(y_i)
                    else: #Izquierda abajo
                        x_i = np.random.normal(4956.316, 2041.85)
                        if x_i < 0:
                            x_i = 0
                        elif x_i > 20000:
                            x_i = 20000
                        
                        y_i = np.random.normal(5008.544, 2041.99)
                        if y_i < 0:
                            y_i = 0
                        elif y_i > 20000:
                            y_i = 20000
                        
                        x.append(x_i)
                        y.append(y_i)
                
                elif ind == "True":#pickup
                    p_der = 0.5000
                    p_izqa = 0.2515

                    u = np.random.uniform(0,1)
                    if u < p_der: #Derecha
                        x_i = np.random.normal(15009.78, 1995.241)
                        if x_i > 20000: #Meter a cuadrilla
                            x_i = 20000
                        if x_i < 0:
                            x_i = 0
                        
                        y_i = np.random.beta(3.050116, 3.046799)
                        y_i = 20000*y_i
                        if y_i > 20000: #Meter a cuadrilla
                            y_i = 20000
                        if y_i < 0:
                            y_i = 0
                        
                        x.append(x_i)
                        y.append(y_i)
                    elif u < p_der + p_izqa: #Izquierda arriba
                        x_i = np.random.normal(4949.299, 2046.547)
                        if x_i < 0:
                            x_i = 0
                        elif x_i > 20000:
                            x_i = 20000
                        
                        y_i = np.random.normal(15000.59, 2014.086)
                        if y_i > 20000:
                            y_i = 20000
                        elif y_i < 0:
                            y_i = 0
                        
                        x.append(x_i)
                        y.append(y_i)
                    else: #Izquierda abajo
                        x_i = np.random.normal(5021.175, 2067.657)
                        if x_i < 0:
                            x_i = 0
                        elif x_i > 20000:
                            x_i = 20000
                        
                        y_i = np.random.normal(4996.648, 2002.915)
                        if y_i < 0:
                            y_i = 0
                        elif y_i > 20000:
                            y_i = 20000
                        
                        x.append(x_i)
                        y.append(y_i)

                rep.append(j)

    datos_dict = {
        "replica": rep,
        "arrivals": arrivals,
        "deadlines": deadlines,
        "indicador": indicador,
        "x": x,
        "y": y,
        "profits": profits,
        "ready_times": ready_times,
        "service_times": service_times
    }
    
    df = pl.DataFrame(datos_dict, schema=[i for i in datos_dict.keys()], strict=False)
    timestamp_raw = datetime.now()
    timestamp_no_ms = str(timestamp_raw).split(".")[0]
    timestamp = timestamp_no_ms.replace(" ", "_").replace(":", "-")

    filename = f"Instancia_{instancia}_{replicas}_replicas_{timestamp}.parquet"

    filepath = os.path.join(out_folder, filename)
    try:
        os.makedirs(out_folder)
    except Exception as e:
        pass
    df.write_parquet(filepath)
    return df.filter(pl.col('arrivals') >= t0)

if __name__ == "__main__":
    print("Running Replica.py...")
    t0 = time.time()
    data = replica(4, 100)
    # print(data.filter(pl.col('arrivals') <= 9 * 60 * 60))
    print(f'Tiempo de ejecución (s): {(time.time() - t0)}')
    print(type(data[1]))
    client = data[1]
    print(data[1])
    print(client['y'][0])
    print(type(float(client['y'][0])))
    # for i in range(len(data)):
        # print(data[i])
