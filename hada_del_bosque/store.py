"""Estado persistente en JSON (se guarda tras cada acción, de forma atómica).

Todas las rutas se guardan RELATIVAS a la carpeta raíz y con '/' como separador,
así el mismo JSON sirve en Linux y en Windows.
"""

from __future__ import annotations

import bisect
import datetime as dt
import json
import os
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import APP_NAME, STATE_FILENAME, VERSION
from .dates import kind_of, month_index, parse_iso
from .folders import (month_from_folder_name, parse_folder,
                      year_from_folder_name)

SKIP_DIRS = {"$recycle.bin", "system volume information", "@eadir", "__pycache__", ".thumbnails", "lost+found"}

RECENT_DAYS = 62  # "dos meses" alrededor de la fecha de la foto


def to_rel(root: Path, p: Path) -> str:
    return Path(os.path.relpath(p, root)).as_posix()


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / STATE_FILENAME
        self.data: dict = {}
        self._cat_dates: dict[str, list[str]] = defaultdict(list)

    # ------------------------------------------------------------ carga / guardado
    @classmethod
    def open(cls, root: Path) -> tuple["Store", bool]:
        s = cls(root)
        is_new = not s.path.exists()
        if is_new:
            s.data = {
                "app": APP_NAME,
                "version": 1,
                "created": dt.datetime.now().isoformat(timespec="seconds"),
                "phase": "folders",
                "dest": None,
                "month_template": None,
                "folders": {},
                "folder_pos": 0,
                "categories": {},
                "next_cat": 1,
                "items": {},
                "position": 0,
            }
        else:
            try:
                with open(s.path, encoding="utf-8") as f:
                    s.data = json.load(f)
            except (json.JSONDecodeError, OSError):
                bak = s.path.with_suffix(".json.bak")
                with open(bak, encoding="utf-8") as f:
                    s.data = json.load(f)
            try:  # copia de seguridad al abrir
                shutil.copy2(s.path, s.path.with_suffix(".json.bak"))
            except OSError:
                pass
        s.rebuild_index()
        return s, is_new

    @classmethod
    def reset(cls, root: Path) -> Path | None:
        """Aparta el fichero de progreso (no se borra: se renombra como copia) para empezar de cero."""
        path = Path(root) / STATE_FILENAME
        if not path.exists():
            return None
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"hada_del_bosque.reiniciado-{ts}.json")
        os.replace(path, backup)
        path.with_suffix(".json.bak").unlink(missing_ok=True)
        return backup

    def save(self) -> None:
        self.data["app_version"] = VERSION
        self.data["saved"] = dt.datetime.now().isoformat(timespec="seconds")
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        for i in range(10):
            try:
                os.replace(tmp, self.path)
                return
            except PermissionError:  # Windows: antivirus/indexador con el fichero abierto
                time.sleep(0.1 * (i + 1))
        os.replace(tmp, self.path)

    # ------------------------------------------------------------ accesos
    @property
    def items(self) -> dict:
        return self.data["items"]

    @property
    def categories(self) -> dict:
        return self.data["categories"]

    @property
    def folders(self) -> dict:
        return self.data["folders"]

    def abs_path(self, rel: str) -> Path:
        return self.root.joinpath(*rel.split("/"))

    @property
    def dest(self) -> Path | None:
        d = self.data.get("dest")
        return Path(d) if d else None

    # ------------------------------------------------------------ escaneo
    def list_media(self) -> list[str]:
        exclude = []
        if self.dest:
            try:
                exclude.append(self.dest.resolve())
            except OSError:
                pass
        out = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dp = Path(dirpath)
            keep = []
            for d in dirnames:
                if d.startswith(".") or d.lower() in SKIP_DIRS:
                    continue
                try:
                    if (dp / d).resolve() in exclude:
                        continue
                except OSError:
                    continue
                keep.append(d)
            dirnames[:] = sorted(keep)
            for fn in filenames:
                if fn.startswith(".") or not kind_of(fn):
                    continue
                out.append(to_rel(self.root, dp / fn))
        return out

    def sync_files(self, found: list[str]) -> list[str]:
        """Añade los nuevos ficheros, marca los desaparecidos. Devuelve los que necesitan fecha."""
        items = self.items
        found_set = set(found)
        need = []
        for rel in found:
            it = items.get(rel)
            if it is None:
                items[rel] = {"status": "pending", "category": None, "suggested": None}
                need.append(rel)
            else:
                it.pop("missing", None)
                if "date_src" not in it:
                    need.append(rel)
        for rel in list(items):
            if rel not in found_set:
                if items[rel].get("status") == "pending" and not items[rel].get("copied"):
                    del items[rel]
                else:
                    items[rel]["missing"] = True
        # carpetas con fotos directamente dentro
        folder_counts = Counter(rel.rsplit("/", 1)[0] if "/" in rel else "" for rel in found)
        for f in folder_counts:
            if f and f not in self.folders:
                self.folders[f] = {"group": None, "category": None}
        for f in list(self.folders):
            if f not in folder_counts and self.folders[f].get("group") is None:
                del self.folders[f]
        return need

    def set_estimate(self, rel: str, est: dict) -> None:
        it = self.items[rel]
        it["kind"] = est["kind"]
        it["date"] = est["date"]
        it["date_src"] = est["src"]
        it["dates"] = est["dates"]
        it["size"] = est["size"]

    # ------------------------------------------------------------ orden
    def ordered(self) -> list[str]:
        live = [r for r, it in self.items.items() if not it.get("missing")]
        return sorted(live, key=lambda r: (self.items[r].get("date") is None, self.items[r].get("date") or "", r))

    def folder_list(self) -> list[str]:
        return sorted(self.folders, key=lambda s: s.casefold())

    def folder_items(self, folder: str) -> list[str]:
        pref = folder + "/"
        return sorted(r for r, it in self.items.items()
                      if r.startswith(pref) and "/" not in r[len(pref):] and not it.get("missing"))

    # ------------------------------------------------------------ categorías
    def new_category(self, year: int, month: int, name: str, origin: str, **extra) -> str:
        name = name.strip()
        found = self.find_category(year, month, name)
        if found:
            for k, v in extra.items():
                self.categories[found].setdefault(k, v)
            return found
        cid = f"c{self.data['next_cat']}"
        self.data["next_cat"] += 1
        self.categories[cid] = {"year": int(year), "month": int(month), "name": name,
                                "origin": origin, "created": dt.datetime.now().isoformat(timespec="seconds"), **extra}
        return cid

    def find_category(self, year: int, month: int, name: str) -> str | None:
        key = name.strip().casefold()
        for cid, c in self.categories.items():
            if c.get("nocat"):
                continue
            if c["year"] == int(year) and c["month"] == int(month) and c["name"].casefold() == key:
                return cid
        return None

    def find_nocat(self, year: int, month: int) -> str | None:
        for cid, c in self.categories.items():
            if c.get("nocat") and c["year"] == int(year) and c["month"] == int(month):
                return cid
        return None

    def nocat(self, year: int, month: int) -> str:
        """Categoría especial «sin categoría» de un mes: las fotos van directamente a la carpeta del mes."""
        cid = self.find_nocat(year, month)
        if cid:
            return cid
        cid = f"c{self.data['next_cat']}"
        self.data["next_cat"] += 1
        self.categories[cid] = {"year": int(year), "month": int(month), "name": "", "nocat": True,
                                "origin": "mes", "created": dt.datetime.now().isoformat(timespec="seconds")}
        return cid

    def category_label(self, cid: str | None) -> str:
        from . import month_name
        c = self.categories.get(cid or "")
        if not c:
            return "—"
        name = "(sin categoría)" if c.get("nocat") else c["name"]
        return f"{c['year']} · {c['month']:02d} {month_name(c['month'])} — {name}"

    def category_usage(self) -> Counter:
        return Counter(it["category"] for it in self.items.values()
                       if it.get("status") == "assigned" and it.get("category"))

    def delete_category(self, cid: str) -> None:
        for it in self.items.values():
            if it.get("category") == cid:
                it["category"] = None
                it["status"] = "pending"
            if it.get("suggested") == cid:
                it["suggested"] = None
        for f in self.folders.values():
            if f.get("category") == cid:
                f["category"] = None
                f["group"] = None
        self.categories.pop(cid, None)
        self.rebuild_index()

    # ------------------------------------------------------------ asignaciones
    def assign(self, rel: str, cid: str) -> None:
        it = self.items[rel]
        it["category"] = cid
        it["status"] = "assigned"
        it["when"] = dt.datetime.now().isoformat(timespec="seconds")
        self.rebuild_index()

    def discard(self, rel: str) -> None:
        it = self.items[rel]
        it["category"] = None
        it["status"] = "discarded"
        self.rebuild_index()

    def clear(self, rel: str) -> None:
        it = self.items[rel]
        it["category"] = None
        it["status"] = "pending"
        self.rebuild_index()

    def rebuild_index(self) -> None:
        """Índice categoría -> fechas de las fotos asignadas (para 'recientes')."""
        idx: dict[str, list[str]] = defaultdict(list)
        for it in self.data.get("items", {}).values():
            if it.get("status") == "assigned" and it.get("category") and it.get("date"):
                idx[it["category"]].append(it["date"])
        for v in idx.values():
            v.sort()
        self._cat_dates = idx

    def stats(self) -> dict:
        c = Counter(it.get("status", "pending") for it in self.items.values() if not it.get("missing"))
        return {"total": sum(c.values()), "assigned": c["assigned"], "discarded": c["discarded"], "pending": c["pending"]}

    # ------------------------------------------------------------ sugerencias
    def suggestions(self, rel: str, last_used: list[str]) -> tuple[list[str], list[str]]:
        """Devuelve (categorías del mes anterior/actual/siguiente, recientes por fecha)."""
        it = self.items[rel]
        d = parse_iso(it.get("date"))
        sugg = it.get("suggested")
        main: list[str] = []
        recent: list[str] = []
        if d is None:
            recent = [c for c in last_used if c in self.categories]
        else:
            mi = month_index(d.year, d.month)
            for cid, c in self.categories.items():
                if abs(month_index(c["year"], c["month"]) - mi) <= 1:
                    main.append(cid)
            lo = (d - dt.timedelta(days=RECENT_DAYS)).isoformat(timespec="seconds")
            hi = (d + dt.timedelta(days=RECENT_DAYS)).isoformat(timespec="seconds")
            for cid, dates in self._cat_dates.items():
                if cid in main or cid not in self.categories:
                    continue
                i = bisect.bisect_left(dates, lo)
                if i < len(dates) and dates[i] <= hi:
                    recent.append(cid)
        for extra in (sugg, it.get("category")):
            if extra and extra in self.categories and extra not in main and extra not in recent:
                main.insert(0, extra)

        def key(cid):
            c = self.categories[cid]
            return (c["year"], c["month"], c["name"].casefold())

        main.sort(key=key)
        if d is not None:
            recent.sort(key=key)
        return main, recent

    # ------------------------------------------------------------ revisión de carpetas
    def folder_proposal(self, folder: str) -> tuple[int | None, int | None, str]:
        y, m, name = parse_folder(folder)
        dates = [parse_iso(self.items[r].get("date")) for r in self.folder_items(folder)]
        dates = [d for d in dates if d]
        if dates and (y is None or m is None):
            if y is None:
                common = Counter((d.year, d.month) for d in dates).most_common(1)[0][0]
                y, m2 = common
                m = m or m2
            else:
                same = [d for d in dates if d.year == y] or dates
                m = Counter(d.month for d in same).most_common(1)[0][0]
        if not name:
            name = folder.rsplit("/", 1)[-1]
        return y, m, name

    def set_folder_group(self, folder: str, is_group: bool, year=None, month=None, name=None) -> None:
        f = self.folders[folder]
        old = f.get("category")
        files = self.folder_items(folder)
        if is_group:
            cid = self.new_category(year, month, name, "carpeta", src_folder=folder)
            if old and old != cid:
                self._release_folder_category(old, files)
            f["group"], f["category"] = True, cid
            for r in files:
                self.items[r]["suggested"] = cid
        else:
            if old:
                self._release_folder_category(old, files)
            f["group"], f["category"] = False, None
            for r in files:
                if self.items[r].get("suggested"):
                    self.items[r]["suggested"] = None

    def _release_folder_category(self, cid: str, files: list[str]) -> None:
        for r in files:
            if self.items[r].get("suggested") == cid:
                self.items[r]["suggested"] = None
        used = any(it.get("category") == cid or it.get("suggested") == cid for it in self.items.values())
        used = used or any(f.get("category") == cid for f in self.folders.values() if f.get("category"))
        c = self.categories.get(cid)
        if c and not used and c.get("origin") == "carpeta":
            del self.categories[cid]

    # ------------------------------------------------------------ destino
    def import_dest_categories(self, dest: Path) -> int:
        """Lee DEST/AAAA/<mes>/<categoría> y crea esas categorías."""
        n = 0
        try:
            years = [p for p in dest.iterdir() if p.is_dir()]
        except OSError:
            return 0
        for yp in years:
            y = year_from_folder_name(yp.name)
            if not y:
                continue
            try:
                months = [p for p in yp.iterdir() if p.is_dir()]
            except OSError:
                continue
            for mp in months:
                mo = month_from_folder_name(mp.name)
                if not mo:
                    continue
                try:
                    cats = [p for p in mp.iterdir() if p.is_dir() and not p.name.startswith(".")]
                except OSError:
                    continue
                for cp in cats:
                    before = len(self.categories)
                    self.new_category(y, mo, cp.name, "destino", dest_rel=to_rel(dest, cp))
                    n += len(self.categories) - before
        return n
