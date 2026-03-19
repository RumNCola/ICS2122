:: Cargar las variables del entorno desde .env
for /f "delims=" %%x in (.env) do (set "%%x")

