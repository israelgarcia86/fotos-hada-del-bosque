@echo off
rem ===== Fotos del hada del bosque - lanzador para Windows (opcion con Python instalado) =====
rem La primera vez crea un entorno en la carpeta .venv e instala lo necesario (unos minutos).
rem Las siguientes veces arranca directamente.
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" goto run

echo Preparando el hada del bosque por primera vez...
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo No se ha encontrado Python. Instalalo desde https://www.python.org/downloads/
    echo marcando la casilla "Add python.exe to PATH" y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Ha fallado la instalacion de los componentes. Revisa la conexion a internet.
    rmdir /s /q .venv
    pause
    exit /b 1
)

:run
start "" ".venv\Scripts\pythonw.exe" run.py
