@echo off
:: Este módulo será el encargado de ejecutar el programa principal, cargando las variables del entorno.

:: instalacion de requirements si corresponde Descomentar si es la primera ejecución
:: pip install -r requirements.txt

:: Activación de variables de entorno
call .venv\Scripts\activate.bat

:: Cargar variables de entorno desde .env
for /f "delims=" %%x in (.env) do (set "%%x")

:: Ejecutar el programa principal
python main.py

:: Pausa para ver resultados
pause