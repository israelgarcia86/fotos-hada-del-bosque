"""Carga de imágenes (incluye HEIC y RAW) y lectura de información para mostrar."""

from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image, ImageOps

from .dates import kind_of

try:
    import pillow_heif  # noqa: F401  (registrado en dates.py)
except Exception:  # pragma: no cover
    pass

try:
    import rawpy
except Exception:  # pragma: no cover
    rawpy = None

Image.MAX_IMAGE_PIXELS = None


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _open_raw(path: Path) -> Image.Image:
    if rawpy is None:
        raise RuntimeError("Falta 'rawpy' para abrir ficheros RAW")
    with rawpy.imread(str(path)) as raw:
        try:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                return Image.open(io.BytesIO(thumb.data))
            return Image.fromarray(thumb.data)
        except Exception:
            rgb = raw.postprocess(half_size=True, use_camera_wb=True)
            return Image.fromarray(rgb)


def load_image(path: Path, max_w: int, max_h: int) -> Image.Image:
    """Abre la imagen ya girada según EXIF y reducida a como mucho max_w x max_h."""
    kind = kind_of(path)
    if kind == "raw":
        im = _open_raw(path)
    else:
        im = Image.open(path)
        if im.format == "JPEG":
            im.draft("RGB", (max_w, max_h))
    try:
        im.seek(0)
    except Exception:
        pass
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" else "RGB")
    im.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    return im


def image_info(path: Path) -> dict:
    info: dict = {}
    try:
        info["Tamaño"] = human_size(os.path.getsize(path))
    except OSError:
        pass
    kind = kind_of(path)
    if kind == "video":
        try:
            from hachoir.metadata import extractMetadata
            from hachoir.parser import createParser

            parser = createParser(str(path))
            if parser:
                with parser:
                    meta = extractMetadata(parser)
                if meta:
                    if meta.has("width") and meta.has("height"):
                        info["Dimensiones"] = f"{meta.get('width')} × {meta.get('height')}"
                    if meta.has("duration"):
                        dur = meta.get("duration")
                        secs = int(dur.total_seconds())
                        info["Duración"] = f"{secs // 60}:{secs % 60:02d}"
                    for k, label in (("producer", "Grabado con"), ("camera_model", "Cámara")):
                        if meta.has(k):
                            info[label] = str(meta.get(k))
        except Exception:
            pass
        return info
    try:
        if kind == "raw":
            import exifread

            with open(path, "rb") as f:
                tags = exifread.process_file(f, details=False)
            make = str(tags.get("Image Make", "")).strip()
            model = str(tags.get("Image Model", "")).strip()
            if make or model:
                info["Cámara"] = f"{make} {model}".strip()
            return info
        with Image.open(path) as im:
            w, h = im.size
            ex = im.getexif()
            if ex.get(274) in (5, 6, 7, 8):
                w, h = h, w
            info["Dimensiones"] = f"{w} × {h}"
            info["Formato"] = im.format or ""
            make = str(ex.get(271, "") or "").strip().strip("\x00")
            model = str(ex.get(272, "") or "").strip().strip("\x00")
            if make or model:
                cam = model if model.lower().startswith(make.lower()) else f"{make} {model}"
                info["Cámara"] = cam.strip()
            sub = ex.get_ifd(0x8769)
            parts = []
            if sub.get(33437):
                parts.append(f"f/{float(sub[33437]):.1f}")
            if sub.get(33434):
                t = float(sub[33434])
                parts.append(f"1/{round(1 / t)} s" if 0 < t < 1 else f"{t:g} s")
            if sub.get(34855):
                parts.append(f"ISO {sub[34855]}")
            if sub.get(37386):
                parts.append(f"{float(sub[37386]):.0f} mm")
            if parts:
                info["Exposición"] = " · ".join(parts)
            gps = ex.get_ifd(0x8825)
            if gps and 2 in gps and 4 in gps:
                def dms(v, ref):
                    deg = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
                    return -deg if ref in ("S", "W") else deg
                lat = dms(gps[2], gps.get(1, "N"))
                lon = dms(gps[4], gps.get(3, "E"))
                info["GPS"] = f"{lat:.5f}, {lon:.5f}"
    except Exception:
        pass
    return info
