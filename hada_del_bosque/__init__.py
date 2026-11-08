"""Fotos del hada del bosque: clasificador de fotos y vídeos por año, mes y categoría."""

from pathlib import Path

APP_NAME = "Fotos del hada del bosque"
APP_ID = "FotosDelHadaDelBosque"
VERSION = "1.1.0"
STATE_FILENAME = "hada_del_bosque.json"

RESOURCES = Path(__file__).resolve().parent / "resources"

MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def month_name(m: int, capital: bool = True) -> str:
    if not m or not 1 <= m <= 12:
        return "?"
    n = MONTHS_ES[m - 1]
    return n.capitalize() if capital else n
