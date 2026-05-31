import numpy as np
import pandas as pd

def replica(instancia, replicas):
    if instancia == 1:
        T_inicio = min(31505, 31506)#31500    # 8:45
        T_delivery = 54353 #55800 #15.30
        T_pickup = 55258 #56700 #15.45
        T_max = max(T_delivery, T_pickup)
        T_fin = 61200 #17:00

        indicador = []
        arrivals = []
        deadlines = []
        x = []
        y = []
        profits = []
        ready_times = []
        service_times = []
        rep = []

        for j in range(replicas):
            t_actual = T_inicio #8:45
            pik = np.random.normal(314.2798, 33.58643)
            deliv = np.random.lognormal(5.218481, 0.02206462)

            t_hasta_prox_pickup = np.random.exponential(pik)
            t_hasta_prox_deliv = np.random.exponential(deliv)
            
            while t_actual < T_max:
                
                if min(t_hasta_prox_pickup, t_hasta_prox_deliv) == t_hasta_prox_pickup: #Se viene pickup
                    t_actual += t_hasta_prox_pickup
                    t_hasta_prox_deliv -= t_hasta_prox_pickup

                    t_hasta_prox_pickup = np.random.exponential(pik) #Reponer evento


                    if t_actual > T_pickup: #Llego tarde po
                        break

                    arrivals.append(t_actual)
                
                    #Indicador
                    ind = "True"
                    indicador.append(ind)

                    #Ready time
                    redi = t_actual
                    ready_times.append(redi)

                    #Deadline
                    dead = T_fin #Fin de horizonte
                    deadlines.append(dead)

                    #Profits
                    pft = 1
                    profits.append(pft)

                    #Service
                    service_times.append(180)

                    # x e y
                    x_i = np.random.uniform(1.55004, 19998.52)
                    y_i = np.random.uniform(4.065066, 19999.74)
                    x.append(x_i)
                    y.append(y_i)

                    rep.append(j)
            
                elif min(t_hasta_prox_pickup, t_hasta_prox_deliv) == t_hasta_prox_deliv: #Se viene deliv
                    t_actual += t_hasta_prox_deliv
                    t_hasta_prox_pickup -= t_hasta_prox_deliv

                    t_hasta_prox_deliv = np.random.exponential(deliv) #Reponer evento


                    if t_actual > T_delivery: #Llego tarde po
                        t_hasta_prox_deliv = np.inf
                        continue

                    arrivals.append(t_actual)
                
                    #Indicador
                    ind = "False"
                    indicador.append(ind)

                    #Ready time
                    redi = t_actual + 900
                    ready_times.append(redi)

                    #Deadline
                    dead = redi + 10800
                    deadlines.append(dead)

                    #Profits
                    pft = 2
                    profits.append(pft)

                    #Service
                    service_times.append(180)

                    # x e y
                    x_i = np.random.uniform(2.686488, 19998.38)
                    y_i = np.random.uniform(0.795993, 19999.67)
                    x.append(x_i)
                    y.append(y_i)

                    rep.append(j)
                    
                
    
    elif instancia == 2:
        
        T_inicio = 31501  # 8:45
        T_delivery = 54359 #55800 #15.30
        T_pickup = 55258 #56700 #15.45
        T_max = max(T_delivery, T_pickup)
        T_fin = 61200 #17:00

        corte1_pik = 39600
        corte1_del = 39000
        corte2_pik = 47400
        corte2_del = 46950

        indicador = []
        arrivals = []
        deadlines = []
        x = []
        y = []
        profits = []
        ready_times = []
        service_times = []
        rep = []

        for j in range(replicas):
            t_actual = T_inicio

            pik_zona1 = np.random.lognormal(6.387441, 0.02359802)
            del_zona1 = np.random.lognormal(5.635524, 0.0265168)
            pik_zona2 = np.random.lognormal(5.499977, 0.02673697)
            del_zona2 = np.random.lognormal(4.745147, 0.03205996)
            pik_zona3 = np.random.lognormal(5.955706, 0.02492952)
            del_zona3 = np.random.lognormal(5.242182, 0.03163123)
            
            t_hasta_prox_pickup = np.random.exponential(pik_zona1) #Generar primeros datos
            t_hasta_prox_deliv = np.random.exponential(del_zona1)

            while t_actual <= T_max:
                if min(t_hasta_prox_pickup, t_hasta_prox_deliv) == t_hasta_prox_pickup: #Viene un pikup
                    t_actual += t_hasta_prox_pickup #Avanzar tiempo
                    t_hasta_prox_deliv -= t_hasta_prox_pickup

                    if t_actual < corte1_pik: #Zona 1
                        t_hasta_prox_pickup = np.random.exponential(pik_zona1) #Reponer evento
                    elif t_actual < corte2_pik: #Zona 2
                        t_hasta_prox_pickup = np.random.exponential(pik_zona2)
                    else: #Zona 3
                        t_hasta_prox_pickup = np.random.exponential(pik_zona3)


                    if t_actual > T_pickup: #Llego tarde po
                        break

                    arrivals.append(t_actual)
                
                    #Indicador
                    ind = "True"
                    indicador.append(ind)

                    #Ready time
                    redi = t_actual
                    ready_times.append(redi)

                    #Deadline
                    dead = T_fin #Fin de horizonte
                    deadlines.append(dead)

                    #Profits
                    pft = 1
                    profits.append(pft)

                    #Service
                    service_times.append(180)

                    # x e y
                    x_i = np.random.uniform(0.795993, 19998.65)
                    y_i = np.random.uniform(1.502554, 19999.33)
                    x.append(x_i)
                    y.append(y_i)

                    rep.append(j)
                
                elif min(t_hasta_prox_pickup, t_hasta_prox_deliv) == t_hasta_prox_deliv: #Se viene deliv
                    t_actual += t_hasta_prox_deliv
                    t_hasta_prox_pickup -= t_hasta_prox_deliv

                    if t_actual < corte1_del: #Zona 1
                        t_hasta_prox_deliv = np.random.exponential(del_zona1) #Reponer evento
                    elif t_actual < corte2_del: #Zona 2
                        t_hasta_prox_deliv = np.random.exponential(del_zona2)
                    else: #Zona 3
                        t_hasta_prox_deliv = np.random.exponential(del_zona3)

                    if t_actual > T_delivery: #Llego tarde po
                        t_hasta_prox_deliv = np.inf
                        continue

                    arrivals.append(t_actual)
                
                    #Indicador
                    ind = "False"
                    indicador.append(ind)

                    #Ready time
                    redi = t_actual + 900
                    ready_times.append(redi)

                    #Deadline
                    dead = redi + 10800
                    deadlines.append(dead)

                    #Profits
                    pft = 2
                    profits.append(pft)

                    #Service
                    service_times.append(180)

                    # x e y
                    x_i = np.random.uniform(2.686488, 19999.67)
                    y_i = np.random.uniform(0.5494509, 19999.74)
                    x.append(x_i)
                    y.append(y_i)

                    rep.append(j)


    elif instancia == 3:
        
        T_inicio = 31501    # 8:45
        T_delivery = 54354 #55800 #15.30
        T_pickup = 55259 #56700 #15.45
        T_max = max(T_delivery, T_pickup)
        T_fin = 61200 #17:00

        # Para pikup: 39300 y 47100
        # Para delivery: 39000 y 46800
        corte1_pik = 39300
        corte1_del = 39000
        corte2_pik = 47100
        corte2_del = 46800

        indicador = []
        arrivals = []
        deadlines = []
        x = []
        y = []
        profits = []
        ready_times = []
        service_times = []
        rep = []

        for j in range(replicas):
            t_actual = T_inicio

            pik_zona1 = np.random.lognormal(6.368066, 0.02345632)
            del_zona1 = np.random.lognormal(5.685787, 0.0270395)
            pik_zona2 = np.random.lognormal(5.436013, 0.02660795)
            del_zona2 = np.random.lognormal(4.743367, 0.03359863)
            pik_zona3 = np.random.lognormal(5.938961, 0.02506371)
            del_zona3 = np.random.lognormal(5.243111, 0.02788642)

            t_hasta_prox_pickup = np.random.exponential(pik_zona1) #Primeros tiempos
            t_hasta_prox_deliv = np.random.exponential(del_zona1)

            while t_actual <= T_max:

                if min(t_hasta_prox_pickup, t_hasta_prox_deliv) == t_hasta_prox_pickup: #Viene un pikup
                    t_actual += t_hasta_prox_pickup #Avanzar tiempo
                    t_hasta_prox_deliv -= t_hasta_prox_pickup

                    if t_actual < corte1_pik: #Antes de las 11
                        t_hasta_prox_pickup = np.random.exponential(pik_zona1) #Reponer evento
                    elif t_actual < corte2_pik: #Entre 11 y 13
                        t_hasta_prox_pickup = np.random.exponential(pik_zona2)
                    else: #Despues de las 13
                        t_hasta_prox_pickup = np.random.exponential(pik_zona3)


                    if t_actual > T_pickup: #Llego tarde po
                        break

                    arrivals.append(t_actual)
                
                    #Indicador
                    ind = "True"
                    indicador.append(ind)

                    #Ready time
                    redi = t_actual
                    ready_times.append(redi)

                    #Deadline
                    dead = T_fin #Fin de horizonte
                    deadlines.append(dead)

                    #Profits
                    pft = 1
                    profits.append(pft)

                    #Service
                    service_times.append(180)

                    #X e Y
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

                elif min(t_hasta_prox_pickup, t_hasta_prox_deliv) == t_hasta_prox_deliv: #Se viene deliv
                    t_actual += t_hasta_prox_deliv
                    t_hasta_prox_pickup -= t_hasta_prox_deliv

                    if t_actual < corte1_del: #Antes de las 11
                        t_hasta_prox_deliv = np.random.exponential(del_zona1) #Reponer evento
                    elif t_actual < corte2_del: #Entre 11 y 13
                        t_hasta_prox_deliv = np.random.exponential(del_zona2)
                    else: #Despues de las 13
                        t_hasta_prox_deliv = np.random.exponential(del_zona3)

                    if t_actual > T_delivery: #Llego tarde po
                        t_hasta_prox_deliv = np.inf
                        continue

                    arrivals.append(t_actual)
                
                    #Indicador
                    ind = "False"
                    indicador.append(ind)

                    #Ready time
                    redi = t_actual + 900
                    ready_times.append(redi)

                    #Deadline
                    dead = redi + 10800
                    deadlines.append(dead)

                    #Profits
                    pft = 2
                    profits.append(pft)

                    #Service
                    service_times.append(180)

                    # x e y
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
                    
                    rep.append(j)

                    
    elif instancia == 4:
        
        T_inicio = 31501    # 8:45
        T_delivery = 54354 #55800 #15.30
        T_pickup = 55259 #56700 #15.45
        T_max = max(T_delivery, T_pickup)
        T_fin = 61200 #17:00

        # Los breaks son (al ojo con tabla)
        # Para pikup: 39500 y 47100
        # Para delivery: 39300 y 46800
        corte1_pik = 39500
        corte1_del = 39300
        corte2_pik = 47100
        corte2_del = 46800

        indicador = []
        arrivals = []
        deadlines = []
        x = []
        y = []
        profits = []
        ready_times = []
        service_times = []
        rep = []

        for j in range(replicas):
            t_actual = T_inicio

            pik_zona1 = np.random.lognormal(6.353319, 0.02311884)
            del_zona1 = np.random.lognormal(5.671931, 0.02750992)
            pik_zona2 = np.random.lognormal(5.434246, 0.02687241)
            del_zona2 = np.random.lognormal(4.742206, 0.03386624)
            pik_zona3 = np.random.lognormal(5.938961, 0.02506371)
            del_zona3 = np.random.lognormal(5.243111, 0.02788642)

            t_hasta_prox_pickup = np.random.exponential(pik_zona1) #Primeros clientes
            t_hasta_prox_deliv = np.random.exponential(del_zona1)

            while t_actual <= T_max:
                if min(t_hasta_prox_pickup, t_hasta_prox_deliv) == t_hasta_prox_pickup: #Viene un pikup
                    t_actual += t_hasta_prox_pickup #Avanzar tiempo
                    t_hasta_prox_deliv -= t_hasta_prox_pickup

                    if t_actual < corte1_pik: #Antes de las 11
                        t_hasta_prox_pickup = np.random.exponential(pik_zona1) #Reponer evento
                    elif t_actual < corte2_pik: #Entre 11 y 13
                        t_hasta_prox_pickup = np.random.exponential(pik_zona2)
                    else: #Despues de las 13
                        t_hasta_prox_pickup = np.random.exponential(pik_zona3)


                    if t_actual > T_pickup: #Llego tarde po
                        break

                    arrivals.append(t_actual)
                
                    #Indicador
                    ind = "True"
                    indicador.append(ind)

                    #Ready time
                    redi = t_actual
                    ready_times.append(redi)

                    #Deadline
                    dead = T_fin #Fin de horizonte
                    deadlines.append(dead)

                    #Profits
                    pft = 1
                    profits.append(pft)

                    #Service
                    service_times.append(180)

                    # x e y
                    p_der = 0.5000
                    p_izqa = 0.2515

                    u = np.random.uniform(0,1)
                    if u < p_der: #Derecha
                        x_i = np.random.normal(15009.78, 1995.241)
                        if x_i > 20000: #Meter a cuadrilla
                            x_i = 20000
                        if x_i < 0:
                            x_i = 0
                        
                        y_i = np.random.beta(2.833369, 2.681914)
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

                elif min(t_hasta_prox_pickup, t_hasta_prox_deliv) == t_hasta_prox_deliv: #Se viene deliv
                    t_actual += t_hasta_prox_deliv
                    t_hasta_prox_pickup -= t_hasta_prox_deliv

                    if t_actual < corte1_del: #Antes de las 11
                        t_hasta_prox_deliv = np.random.exponential(del_zona1) #Reponer evento
                    elif t_actual < corte2_del: #Entre 11 y 13
                        t_hasta_prox_deliv = np.random.exponential(del_zona2)
                    else: #Despues de las 13
                        t_hasta_prox_deliv = np.random.exponential(del_zona3)

                    if t_actual > T_delivery: #Llego tarde po
                        t_hasta_prox_deliv = np.inf
                        continue

                    arrivals.append(t_actual)
                
                    #Indicador
                    ind = "False"
                    indicador.append(ind)

                    #Ready time
                    redi = t_actual + 900
                    ready_times.append(redi)

                    #Deadline
                    dead = redi + 10800
                    deadlines.append(dead)

                    #Profits
                    pft = 2
                    profits.append(pft)

                    #Service
                    service_times.append(180)

                    # x e y
                    p_der = 0.5061
                    p_izqa = 0.2455

                    u = np.random.uniform(0,1)
                    if u < p_der: #Derecha
                        x_i = np.random.normal(14972.16, 2032.986)
                        if x_i > 20000: #Meter a cuadrilla
                            x_i = 20000
                        if x_i < 0:
                            x_i = 0
                        
                        y_i = np.random.beta(3.24094, 3.224951)
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
                
                    rep.append(j)
            


    ##### Ayuda de chat desde aqui #####
    datos = {
        "replica": rep,
        "arrivals": arrivals,
        "deadlines": deadlines,
        "indicador": indicador,
        "x": x,
        "y": y,
        "profits": profits,
        "ready times": ready_times,
        "service times": service_times
    }

    df = pd.DataFrame(datos)
    df.to_excel(f"replica_inst{instancia}_x{replicas}.xlsx", index=False)

    return df, f"replica_inst{instancia}_x{replicas}.xlsx"