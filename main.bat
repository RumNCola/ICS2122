@echo off
:: Este módulo será el encargado de ejecutar el programa principal, cargando las variables del entorno.

:: instalacion de requirements si corresponde Descomentar si es la primera ejecución
:: pip install -r requirements.txt
:: python -m pip install --upgrade pip

:: Activación de variables de entorno
call .venv\Scripts\activate.bat

:: Cargar variables de entorno desde load.env
call environment/load.env.bat

:: Ejecutar el programa principal
python main.py

:: Pausa para ver resultados
pause