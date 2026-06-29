'''Entra .csv sale visualización (por ahora I1 R0)'''
import os

from ALL_KPIs_from_worked import create_analysis_directories, solve_and_save_replicas, create_resumen_kpis
from ALL_traductor_CR_a_visualizador import create_worked_from_raw_csv
from ALL_visualizador import init_cool_app, launch_cool_app

path_csv_raw = "output_msaperro.csv"
analysis_path = "outputs/CR_analysis_outputs/CRperro"

def create_analysis():
    create_analysis_directories(analysis_path, [0], [0])

    out_path = os.path.join(analysis_path, "Instancia_I", "I_replica_0")
    create_worked_from_raw_csv(path_csv_raw, out_path)
    create_resumen_kpis(analysis_path, [0], [0])


def just_visualize():
    '''Liar liar pants on fire'''
    init_cool_app(analysis_path)
    launch_cool_app()

    print("Utilidad en análisis ;)")




if __name__ == "__main__":
    print("Running ALL_others_to_visualizador.py...")
    
    create_analysis()
    just_visualize()

    

    

