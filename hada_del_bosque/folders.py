"""Interpretación de nombres de carpeta: año, mes y nombre de la agrupación."""

from __future__ import annotations

import re
import unicodedata

from . import MONTHS_ES

_EN = ["january", "february", "march", "april", "may", "june",
       "july", "august", "september", "october", "november", "december"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


FULL_MONTHS: dict[str, int] = {}
for i, n in enumerate(MONTHS_ES, 1):
    FULL_MONTHS[n] = i
for i, n in enumerate(_EN, 1):
    FULL_MONTHS[n] = i
FULL_MONTHS["setiembre"] = 9
FULL_MONTHS["sept"] = 9

ABBR_MONTHS: dict[str, int] = dict(FULL_MONTHS)
for i, n in enumerate(MONTHS_ES, 1):
    ABBR_MONTHS[n[:3]] = i
for i, n in enumerate(_EN, 1):
    ABBR_MONTHS[n[:3]] = i

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_RE_YM = re.compile(r"(?<!\d)((?:19|20)\d{2})[-_. ]?(0[1-9]|1[0-2])(?:[-_. ]?(0[1-9]|[12]\d|3[01]))?(?!\d)")
_RE_Y = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def month_from_folder_name(name: str) -> int | None:
    """Para carpetas de mes: '05', '5', '05 - Mayo', 'Mayo', 'may', '2023-05'."""
    s = name.strip()
    m = re.match(r"(?:(?:19|20)\d{2}[-_. ]?)?(0?[1-9]|1[0-2])(?!\d)", s)
    if m:
        return int(m.group(1))
    words = _WORD.findall(s)
    if words:
        return ABBR_MONTHS.get(_norm(words[0]))
    return None


def year_from_folder_name(name: str) -> int | None:
    m = re.match(r"\s*((?:19|20)\d{2})(?!\d)", name)
    return int(m.group(1)) if m else None


def _clean(name: str) -> str:
    name = re.sub(r"^[\s\-_.,·]+|[\s\-_.,·]+$", "", name)
    if " " not in name and "_" in name:
        name = name.replace("_", " ")
    return re.sub(r"\s{2,}", " ", name).strip()


def parse_folder(rel: str) -> tuple[int | None, int | None, str]:
    """Analiza la ruta relativa de una carpeta. Devuelve (año, mes, nombre)."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    if not parts:
        return None, None, ""
    leaf, parents = parts[-1], parts[:-1]
    year = month = None
    name = leaf

    m = _RE_YM.search(name)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        name = name[: m.start()] + " " + name[m.end():]
    else:
        m = _RE_Y.search(name)
        if m:
            year = int(m.group(1))
            name = name[: m.start()] + " " + name[m.end():]

    year_in_leaf = year is not None
    parent_year = False
    for p in reversed(parents):
        if year is None:
            my = _RE_Y.search(p)
            if my:
                year, parent_year = int(my.group(1)), True
                mm = re.search(r"(?<!\d)(?:19|20)\d{2}[-_. ]?(0[1-9]|1[0-2])(?!\d)", p)
                if mm and month is None:
                    month = int(mm.group(1))
                continue
        if month is None:
            mo = month_from_folder_name(p)
            if mo:
                month = mo

    # Nombre de mes dentro del propio nombre, solo si parece una fecha ("Cumple junio 2023")
    if month is None and year_in_leaf:
        for w in _WORD.finditer(name):
            mo = FULL_MONTHS.get(_norm(w.group()))
            if mo:
                month = mo
                name = name[: w.start()] + " " + name[w.end():]
                break

    # "05 Feria" dentro de una carpeta de año
    if month is None and parent_year:
        m = re.match(r"\s*(0[1-9]|1[0-2])(?:\s*[-_.]\s*|\s+)(?=\D)", name)
        if m:
            month = int(m.group(1))
            name = name[m.end():]

    return year, month, _clean(name)


_INVALID_WIN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_folder_name(name: str) -> str:
    """Nombre de carpeta válido en Windows y Linux."""
    s = _INVALID_WIN.sub("-", name).strip().rstrip(". ")
    if s.upper() in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(r"(?i)(COM|LPT)\d", s):
        s = "_" + s
    return s or "Sin nombre"
