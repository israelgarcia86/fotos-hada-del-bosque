"""Estimación de la fecha de una foto o vídeo a partir de metadatos y del nombre del fichero."""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".jpe", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif", ".avif"}
RAW_EXT = {".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".dng", ".orf", ".rw2", ".raf", ".pef", ".srw", ".3fr", ".erf", ".kdc", ".mrw", ".x3f"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".3g2", ".mts", ".m2ts", ".ts", ".wmv", ".webm", ".mpg", ".mpeg", ".flv"}

SOURCE_LABELS = {
    "exif": "metadatos EXIF",
    "video": "metadatos del vídeo",
    "nombre": "nombre del fichero",
    "fichero": "fecha del fichero (poco fiable)",
}
SOURCE_PRIORITY = ["exif", "video", "nombre", "fichero"]

logging.getLogger("exifread").setLevel(logging.ERROR)

try:  # Soporte HEIC/HEIF (iPhone)
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pillow_heif = None


def kind_of(path: str | Path) -> str | None:
    ext = os.path.splitext(str(path))[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in RAW_EXT:
        return "raw"
    if ext in VIDEO_EXT:
        return "video"
    return None


def _valid(d: dt.datetime | None) -> bool:
    return d is not None and 1980 <= d.year <= dt.date.today().year + 1


def _mk(y, mo, d, h=0, mi=0, s=0) -> dt.datetime | None:
    try:
        r = dt.datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(s or 0))
    except (ValueError, TypeError):
        return None
    return r if _valid(r) else None


# ---------------------------------------------------------------- nombre del fichero
_RE_YMD = re.compile(
    r"(?<!\d)((?:19|20)\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])"
    r"(?:[ _T.-]{0,3}(?:at[ _])?([01]\d|2[0-3])[-_.:h]?([0-5]\d)[-_.:m]?([0-5]\d))?(?!\d)"
)
_RE_DMY = re.compile(r"(?<!\d)(0[1-9]|[12]\d|3[01])[-_.](0[1-9]|1[0-2])[-_.]((?:19|20)\d{2})(?!\d)")
_RE_EPOCH_MS = re.compile(r"(?<!\d)(1[2-8]\d{11})(?!\d)")


def date_from_name(name: str) -> dt.datetime | None:
    stem = os.path.splitext(name)[0]
    for m in _RE_YMD.finditer(stem):
        d = _mk(*m.groups())
        if d:
            return d
    for m in _RE_DMY.finditer(stem):
        d = _mk(m.group(3), m.group(2), m.group(1))
        if d:
            return d
    m = _RE_EPOCH_MS.search(stem)
    if m:
        try:
            d = dt.datetime.fromtimestamp(int(m.group(1)) / 1000)
            if _valid(d):
                return d
        except (OverflowError, OSError, ValueError):
            pass
    return None


# ---------------------------------------------------------------- EXIF
_RE_EXIF_DT = re.compile(r"(\d{4})[:\-/](\d{2})[:\-/](\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?")


def _parse_exif_dt(value) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    m = _RE_EXIF_DT.search(str(value))
    return _mk(*m.groups()) if m else None


def exif_date(path: Path) -> dt.datetime | None:
    # 1) Pillow (JPEG, TIFF, PNG, WebP, HEIC...)
    try:
        from PIL import Image

        with Image.open(path) as im:
            ex = im.getexif()
            sub = ex.get_ifd(0x8769) if ex else {}
            for v in (sub.get(36867), sub.get(36868), ex.get(306) if ex else None):
                d = _parse_exif_dt(v)
                if d:
                    return d
    except Exception:
        pass
    # 2) exifread (RAW y casos que Pillow no lee)
    try:
        import exifread

        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        for key in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
            if key in tags:
                d = _parse_exif_dt(tags[key].values)
                if d:
                    return d
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- vídeo
def video_date(path: Path) -> dt.datetime | None:
    try:
        from hachoir.core import config as hconfig
        from hachoir.metadata import extractMetadata
        from hachoir.parser import createParser

        hconfig.quiet = True
        parser = createParser(str(path))
        if not parser:
            return None
        with parser:
            meta = extractMetadata(parser)
        if not meta:
            return None
        for key in ("creation_date", "date_time_original", "last_modification"):
            if meta.has(key):
                v = meta.get(key)
                if isinstance(v, dt.datetime):
                    # QuickTime/MP4 guarda la fecha en UTC: pasamos a hora local.
                    if v.tzinfo is None and path.suffix.lower() in {".mp4", ".mov", ".m4v", ".3gp", ".3g2"}:
                        v = v.replace(tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)
                    elif v.tzinfo is not None:
                        v = v.astimezone().replace(tzinfo=None)
                    if _valid(v):
                        return v
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- estimación final
def estimate(path: Path) -> dict:
    """Devuelve dict con: kind, date (iso|None), src, dates {fuente: iso}, size, mtime."""
    kind = kind_of(path)
    cands: dict[str, dt.datetime] = {}
    if kind in ("image", "raw"):
        d = exif_date(path)
        if d:
            cands["exif"] = d
    elif kind == "video":
        d = video_date(path)
        if d:
            cands["video"] = d
    d = date_from_name(path.name)
    if d:
        cands["nombre"] = d
    try:
        st = os.stat(path)
        size, mtime = st.st_size, st.st_mtime
        md = dt.datetime.fromtimestamp(mtime)
        if _valid(md):
            cands["fichero"] = md
    except OSError:
        size, mtime = 0, 0
    src = next((s for s in SOURCE_PRIORITY if s in cands), None)
    return {
        "kind": kind,
        "date": cands[src].isoformat(timespec="seconds") if src else None,
        "src": src,
        "dates": {k: v.isoformat(timespec="seconds") for k, v in cands.items()},
        "size": size,
        "mtime": mtime,
    }


def parse_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)
