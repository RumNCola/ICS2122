'''CONSTANTES específicas al problema'''

PICKUP = True
DELIVERY = False

WIDTH_MAPA = 20000 # metros
HEIGHT_MAPA = 20000 # metros

DEPOT_POS = (10000, 10000)

NUM_REPLICAS = 100

NUM_CAMIONES = 3

LABELS_INSTANCIAS = ["I", "II", "III", "IV"]

def seconds_to_hh_mm_ss(seconds_since_0000):
    seconds_since_0000 = int(seconds_since_0000)

    hh = seconds_since_0000//3600

    seconds_since_the_hour = seconds_since_0000 - hh*3600
    mm = seconds_since_the_hour // 60

    ss = seconds_since_the_hour - 60*mm

    return f"{hh:02}:{mm:02}:{ss:02}"

def hh_mm_ss_to_seconds(hh_mm_ss):
    hh, mm, ss = [int(d) for d in hh_mm_ss.split(":")]

    seconds_since_00 = hh*3600 + mm*60 + ss

    return seconds_since_00

START_TIME = hh_mm_ss_to_seconds("8:30:00")
END_TIME = hh_mm_ss_to_seconds("17:00:00")


if __name__ == "__main__":
    print(hh_mm_ss_to_seconds("12:05:43"))
    print(seconds_to_hh_mm_ss("7200"), seconds_to_hh_mm_ss("7261"))

    print(hh_mm_ss_to_seconds(seconds_to_hh_mm_ss(120324)))
    print(seconds_to_hh_mm_ss(hh_mm_ss_to_seconds("21:59:20")))

    print(START_TIME, END_TIME)

import os
MANHATTAN_FILEPATH = os.path.join("images", "ImageSources", "GoogleEarthManhattan.png")