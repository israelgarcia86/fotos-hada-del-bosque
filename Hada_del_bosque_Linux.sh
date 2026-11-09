#!/usr/bin/env bash
# ===== Fotos del hada del bosque - lanzador para Linux =====
# La primera vez crea un entorno en la carpeta .venv e instala lo necesario (unos minutos).
# Las siguientes veces arranca directamente.
cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python" ]; then
    echo "Preparando el hada del bosque por primera vez..."
    if ! python3 -m venv .venv; then
        echo
        echo "No se ha podido crear el entorno de Python."
        echo "En Ubuntu/Debian instala lo necesario con:  sudo apt install python3-venv"
        rm -rf .venv
        exit 1
    fi
    .venv/bin/python -m pip install --upgrade pip
    if ! .venv/bin/python -m pip install -r requirements.txt; then
        echo
        echo "Ha fallado la instalación de los componentes. Revisa la conexión a internet."
        rm -rf .venv
        exit 1
    fi
fi

exec .venv/bin/python run.py "$@"
