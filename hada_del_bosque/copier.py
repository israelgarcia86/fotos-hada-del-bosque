"""Copia de las fotos clasificadas a la carpeta destino: DESTINO/AAAA/<mes>/<categoría>/."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path

from . import MONTHS_ES, month_name
from .folders import month_from_folder_name, safe_folder_name, year_from_folder_name
from .store import Store, to_rel

DEFAULT_TEMPLATE = "{MM} - {Mes}"


def render_month(template: str, month: int) -> str:
    return (template.replace("{MM}", f"{month:02d}").replace("{M}", str(month))
            .replace("{Mes}", month_name(month)).replace("{mes}", month_name(month, False))
            .replace("{MES}", month_name(month).upper()))


def infer_template(dest: Path) -> str | None:
    """Deduce cómo se llaman las carpetas de mes que ya existen en el destino."""
    try:
        years = sorted((p for p in dest.iterdir() if p.is_dir() and year_from_folder_name(p.name)), reverse=True)
    except OSError:
        return None
    for yp in years:
        try:
            months = sorted(p for p in yp.iterdir() if p.is_dir())
        except OSError:
            continue
        for mp in months:
            mo = month_from_folder_name(mp.name)
            if not mo:
                continue
            t = mp.name
            for variant, token in ((month_name(mo).upper(), "{MES}"), (month_name(mo), "{Mes}"), (month_name(mo, False), "{mes}")):
                if variant in t and variant.lower() != variant.upper():
                    t = t.replace(variant, token, 1)
                    break
            t = re.sub(rf"(?<!\d){mo:02d}(?!\d)", "{MM}", t, count=1) if "{MM}" not in t else t
            if "{MM}" not in t:
                t = re.sub(rf"(?<!\d){mo}(?!\d)", "{M}", t, count=1)
            if "{" in t:
                return t
    return None


def _find_child(parent: Path, pred) -> Path | None:
    try:
        for p in sorted(parent.iterdir()):
            if p.is_dir() and pred(p.name):
                return p
    except OSError:
        pass
    return None


def category_dir(store: Store, dest: Path, cid: str, template: str, create: bool = True) -> Path:
    c = store.categories[cid]
    if c.get("dest_rel"):
        p = dest.joinpath(*c["dest_rel"].split("/"))
        if p.is_dir() or not create:
            return p
    ydir = _find_child(dest, lambda n: year_from_folder_name(n) == c["year"]) or dest / str(c["year"])
    mdir = (_find_child(ydir, lambda n: month_from_folder_name(n) == c["month"]) if ydir.exists() else None) \
        or ydir / safe_folder_name(render_month(template, c["month"]))
    key = c["name"].strip().casefold()
    cdir = (_find_child(mdir, lambda n: n.strip().casefold() == key) if mdir.exists() else None) \
        or mdir / safe_folder_name(c["name"])
    if create:
        cdir.mkdir(parents=True, exist_ok=True)
        c["dest_rel"] = to_rel(dest, cdir)
    return cdir


def pending_copies(store: Store) -> list[str]:
    out = []
    for rel, it in store.items.items():
        if it.get("status") != "assigned" or not it.get("category") or it.get("missing"):
            continue
        if it.get("copied") and it.get("copied_cat") == it["category"]:
            continue
        out.append(rel)
    return sorted(out)


def _same_file(a: Path, b: Path) -> bool:
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
    except OSError:
        return False

    def h(p):
        d = hashlib.sha1()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                d.update(chunk)
        return d.digest()

    return h(a) == h(b)


def copy_one(store: Store, dest: Path, rel: str, template: str) -> tuple[str, str]:
    """Copia un fichero. Devuelve (estado, ruta relativa en destino). estado: copiado|ya_existia."""
    it = store.items[rel]
    src = store.abs_path(rel)
    cdir = category_dir(store, dest, it["category"], template)
    target = cdir / src.name
    state = "copiado"
    if target.exists():
        if _same_file(src, target):
            state = "ya_existia"
        else:
            stem, ext = os.path.splitext(src.name)
            i = 1
            while True:
                target = cdir / f"{stem} ({i}){ext}"
                if not target.exists():
                    break
                if _same_file(src, target):
                    state = "ya_existia"
                    break
                i += 1
    if state == "copiado":
        tmp = target.with_name(target.name + ".copiando")
        shutil.copy2(src, tmp)
        os.replace(tmp, target)
    it["copied"] = to_rel(dest, target)
    it["copied_cat"] = it["category"]
    return state, it["copied"]


__all__ = ["DEFAULT_TEMPLATE", "render_month", "infer_template", "category_dir", "pending_copies", "copy_one", "MONTHS_ES"]
