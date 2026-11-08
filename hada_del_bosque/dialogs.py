"""Diálogos: bienvenida, escaneo, otra categoría, gestor de categorías y copia al destino."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressDialog,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from . import APP_NAME, RESOURCES, VERSION, month_name
from .copier import DEFAULT_TEMPLATE, copy_one, infer_template, pending_copies, render_month
from .dates import estimate, month_index
from .store import Store


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


# ------------------------------------------------------------------ bienvenida
class WelcomeDialog(QDialog):
    def __init__(self, last: str | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.chosen: str | None = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(24)
        img = QLabel()
        img.setPixmap(QPixmap(str(RESOURCES / "hada.png")).scaled(
            260, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(img)
        col = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("bigtitle")
        col.addWidget(title)
        txt = QLabel("El hada del bosque te ayuda a ordenar tus fotos y vídeos por año, mes y categoría.\n\n"
                     "Elige la carpeta donde están las fotos que quieres ordenar (se recorrerán también "
                     "todas sus subcarpetas). Tu progreso se guarda automáticamente en esa carpeta.")
        txt.setWordWrap(True)
        col.addWidget(txt)
        col.addStretch(1)
        b = QPushButton("📂  Elegir carpeta…")
        b.setObjectName("primary")
        b.clicked.connect(self.pick)
        col.addWidget(b)
        if last and Path(last).is_dir():
            b2 = QPushButton(f"↻  Continuar con «{Path(last).name}»")
            b2.setToolTip(last)
            b2.clicked.connect(lambda: self._done(last))
            col.addWidget(b2)
        lay.addLayout(col, 1)
        self.last = last
        self.resize(720, 340)

    def pick(self):
        d = QFileDialog.getExistingDirectory(self, "Elige la carpeta con las fotos que quieres ordenar", self.last or str(Path.home()))
        if d:
            self._done(d)

    def _done(self, d):
        self.chosen = d
        self.accept()


# ------------------------------------------------------------------ escaneo
class ScanWorker(QThread):
    progress = Signal(int, int, str)

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.error = ""

    def run(self):
        try:
            self.progress.emit(0, 0, "Buscando fotos y vídeos…")
            found = self.store.list_media()
            need = self.store.sync_files(found)
            n = len(need)
            for i, rel in enumerate(need):
                if self.isInterruptionRequested():
                    break
                try:
                    est = estimate(self.store.abs_path(rel))
                except Exception:  # noqa: BLE001
                    est = {"kind": None, "date": None, "src": None, "dates": {}, "size": 0, "mtime": 0}
                self.store.set_estimate(rel, est)
                if i % 25 == 0:
                    self.progress.emit(i, n, rel)
                if i and i % 500 == 0:
                    self.store.save()
            self.store.rebuild_index()
            self.store.save()
        except Exception as e:  # noqa: BLE001
            self.error = str(e)


def run_scan(store: Store, parent=None) -> bool:
    dlg = QProgressDialog("Buscando fotos y vídeos…", "Cancelar", 0, 0, parent)
    dlg.setWindowTitle(APP_NAME)
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.setMinimumDuration(300)
    dlg.setMinimumWidth(520)
    w = ScanWorker(store)

    def prog(i, n, rel):
        dlg.setMaximum(n)
        dlg.setValue(i)
        if n:
            dlg.setLabelText(f"Leyendo fechas ({i} de {n})…\n{rel}")

    w.progress.connect(prog)
    w.finished.connect(dlg.reset)
    dlg.canceled.connect(w.requestInterruption)
    w.start()
    dlg.exec()
    w.wait()
    if w.error:
        QMessageBox.critical(parent, APP_NAME, f"Error al leer la carpeta:\n{w.error}")
        return False
    return not w.isInterruptionRequested()


# ------------------------------------------------------------------ otra categoría
class OtherCategoryDialog(QDialog):
    def __init__(self, store: Store, ref_date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Otra categoría")
        self.store = store
        self.chosen: str | None = None
        lay = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Escribe para buscar (nombre, año o mes)…")
        self.search.setClearButtonEnabled(True)
        lay.addWidget(self.search)
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Asignar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        usage = store.category_usage()
        cats = sorted(store.categories.items(), key=lambda kv: (kv[1]["year"], kv[1]["month"], kv[1]["name"].casefold()))
        best, best_dist = None, None
        for cid, c in cats:
            n = usage.get(cid, 0)
            it = QListWidgetItem(f"{c['year']} · {c['month']:02d} {month_name(c['month'])} — {c['name']}"
                                 + (f"   ({n} fotos)" if n else ""))
            it.setData(Qt.ItemDataRole.UserRole, cid)
            it.setData(Qt.ItemDataRole.UserRole + 1, norm(f"{c['name']} {c['year']} {month_name(c['month'])} {c['month']:02d}"))
            self.list.addItem(it)
            if ref_date is not None:
                dist = abs(month_index(c["year"], c["month"]) - month_index(ref_date.year, ref_date.month))
                if best_dist is None or dist < best_dist:
                    best, best_dist = it, dist
        if best:
            self.list.setCurrentItem(best)
            self.list.scrollToItem(best, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._accept)
        self.list.itemDoubleClicked.connect(lambda _: self._accept())
        self.resize(560, 520)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.search.hasFocus():
            self.list.setFocus()
            self.list.keyPressEvent(e)
            return
        super().keyPressEvent(e)

    def _filter(self, text):
        words = norm(text).split()
        first = None
        for i in range(self.list.count()):
            it = self.list.item(i)
            hay = it.data(Qt.ItemDataRole.UserRole + 1)
            ok = all(w in hay for w in words)
            it.setHidden(not ok)
            if ok and first is None:
                first = it
        if first and (self.list.currentItem() is None or self.list.currentItem().isHidden()):
            self.list.setCurrentItem(first)

    def _accept(self):
        it = self.list.currentItem()
        if it and not it.isHidden():
            self.chosen = it.data(Qt.ItemDataRole.UserRole)
            self.accept()


# ------------------------------------------------------------------ gestor de categorías
class CategoryManagerDialog(QDialog):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestionar categorías")
        self.store = store
        self.changed = False
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Haz doble clic en Año, Mes o Nombre para cambiarlos. "
                             "Renombrar aquí no renombra carpetas ya existentes en el destino."))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Año", "Mes", "Nombre", "Fotos", "Origen"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        bdel = QPushButton("🗑  Eliminar categoría")
        bdel.clicked.connect(self._delete)
        row.addWidget(bdel)
        row.addStretch(1)
        bclose = QPushButton("Cerrar")
        bclose.clicked.connect(self.accept)
        row.addWidget(bclose)
        lay.addLayout(row)
        self._fill()
        self.table.cellChanged.connect(self._edited)
        self.resize(760, 560)

    ORIGINS = {"carpeta": "carpeta de origen", "destino": "carpeta destino", "nueva": "creada a mano"}

    def _fill(self):
        self._loading = True
        usage = self.store.category_usage()
        cats = sorted(self.store.categories.items(), key=lambda kv: (kv[1]["year"], kv[1]["month"], kv[1]["name"].casefold()))
        self.table.setRowCount(len(cats))
        for r, (cid, c) in enumerate(cats):
            vals = [str(c["year"]), f"{c['month']:02d} {month_name(c['month'])}", c["name"], str(usage.get(cid, 0)),
                    self.ORIGINS.get(c.get("origin"), c.get("origin", ""))]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setData(Qt.ItemDataRole.UserRole, cid)
                if col >= 3:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, col, it)
        self._loading = False

    def _edited(self, row, col):
        if self._loading:
            return
        it = self.table.item(row, col)
        cid = it.data(Qt.ItemDataRole.UserRole)
        c = self.store.categories[cid]
        text = it.text().strip()
        y, m, name = c["year"], c["month"], c["name"]
        try:
            if col == 0:
                y = int(text)
                assert 1900 <= y <= 2100
            elif col == 1:
                from .folders import month_from_folder_name
                m = month_from_folder_name(text)
                assert m
            elif col == 2:
                name = text
                assert name
        except (ValueError, AssertionError):
            QMessageBox.warning(self, APP_NAME, "Valor no válido.")
            self._fill()
            return
        other = self.store.find_category(y, m, name)
        if other and other != cid:
            QMessageBox.warning(self, APP_NAME, "Ya existe una categoría con ese año, mes y nombre.")
            self._fill()
            return
        c["year"], c["month"], c["name"] = y, m, name
        c.pop("dest_rel", None)
        self.changed = True
        self.store.rebuild_index()
        self.store.save()
        self._fill()

    def _delete(self):
        rows = {i.row() for i in self.table.selectedItems()}
        if not rows:
            return
        cids = {self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows}
        usage = self.store.category_usage()
        n = sum(usage.get(c, 0) for c in cids)
        msg = f"¿Eliminar {len(cids)} categoría(s)?"
        if n:
            msg += f"\n\n{n} foto(s) clasificadas en ellas volverán a quedar pendientes."
        if QMessageBox.question(self, APP_NAME, msg) != QMessageBox.StandardButton.Yes:
            return
        for c in cids:
            self.store.delete_category(c)
        self.changed = True
        self.store.save()
        self._fill()


# ------------------------------------------------------------------ copia al destino
class CopyWorker(QThread):
    progress = Signal(int, int, str)

    def __init__(self, store: Store, dest: Path, template: str, rels: list[str]):
        super().__init__()
        self.store, self.dest, self.template, self.rels = store, dest, template, rels
        self.copied = self.existing = 0
        self.errors: list[str] = []

    def run(self):
        n = len(self.rels)
        for i, rel in enumerate(self.rels):
            if self.isInterruptionRequested():
                break
            self.progress.emit(i, n, rel)
            try:
                state, _ = copy_one(self.store, self.dest, rel, self.template)
                if state == "copiado":
                    self.copied += 1
                else:
                    self.existing += 1
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"{rel}: {e}")
            if i % 20 == 0:
                self.store.save()
        self.store.save()


class CopyDialog(QDialog):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Copiar las fotos clasificadas al destino")
        lay = QVBoxLayout(self)
        intro = QLabel("Las fotos y vídeos clasificados se <b>copian</b> (nunca se mueven ni se borran) a:<br>"
                       "<tt>DESTINO / Año / Mes / Categoría /</tt><br>"
                       "Si ya existen las carpetas del año, del mes o de la categoría, se reutilizan. "
                       "Si un fichero idéntico ya está allí, no se duplica.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        drow = QHBoxLayout()
        self.dest_edit = QLineEdit(str(store.dest or ""))
        self.dest_edit.setReadOnly(True)
        bdest = QPushButton("Cambiar…")
        bdest.clicked.connect(self._pick)
        drow.addWidget(self.dest_edit, 1)
        drow.addWidget(bdest)
        form.addRow("Carpeta destino:", drow)
        self.tpl = QLineEdit(store.data.get("month_template") or (infer_template(store.dest) if store.dest else None) or DEFAULT_TEMPLATE)
        self.tpl.setToolTip("{MM} = 05   {M} = 5   {Mes} = Mayo   {mes} = mayo   {MES} = MAYO")
        form.addRow("Nombre de carpeta de mes nueva:", self.tpl)
        self.preview = QLabel()
        form.addRow("Ejemplo:", self.preview)
        lay.addLayout(form)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        bb = QDialogButtonBox()
        self.bcopy = bb.addButton("Copiar ahora", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton("Cerrar", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self._copy)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.tpl.textChanged.connect(self._refresh)
        self._refresh()
        self.resize(640, 360)

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta destino (donde ya tienes las fotos ordenadas)", self.dest_edit.text() or str(Path.home()))
        if not d:
            return
        dp = Path(d).resolve()
        if dp == self.store.root.resolve():
            QMessageBox.warning(self, APP_NAME, "El destino no puede ser la misma carpeta que estás ordenando.")
            return
        self.store.data["dest"] = str(dp)
        n = self.store.import_dest_categories(dp)
        t = infer_template(dp)
        if t:
            self.tpl.setText(t)
        self.store.save()
        self.dest_edit.setText(str(dp))
        if n:
            QMessageBox.information(self, APP_NAME, f"Se han importado {n} categorías nuevas desde el destino.")
        self._refresh()

    def _refresh(self):
        t = self.tpl.text().strip() or DEFAULT_TEMPLATE
        self.preview.setText(f"<tt>2023 / {render_month(t, 5)} / Feria</tt>")
        rels = pending_copies(self.store)
        cats = {self.store.items[r]["category"] for r in rels}
        st = self.store.stats()
        done = sum(1 for it in self.store.items.values() if it.get("copied"))
        self.summary.setText(
            f"<b>{len(rels)}</b> fichero(s) clasificados pendientes de copiar, en {len(cats)} categoría(s).<br>"
            f"Ya copiados anteriormente: {done}.<br>"
            f"Sin clasificar todavía: {st['pending']} · Descartados: {st['discarded']} (estos no se copian).")
        self.bcopy.setEnabled(bool(rels) and bool(self.dest_edit.text()))

    def _copy(self):
        dest = Path(self.dest_edit.text())
        if not dest.is_dir():
            QMessageBox.warning(self, APP_NAME, "Elige primero una carpeta destino válida.")
            return
        t = self.tpl.text().strip() or DEFAULT_TEMPLATE
        self.store.data["month_template"] = t
        rels = pending_copies(self.store)
        dlg = QProgressDialog("Copiando…", "Detener", 0, len(rels), self)
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setMinimumWidth(520)
        w = CopyWorker(self.store, dest, t, rels)
        w.progress.connect(lambda i, n, r: (dlg.setValue(i), dlg.setLabelText(f"Copiando {i + 1} de {n}…\n{r}")))
        w.finished.connect(dlg.reset)
        dlg.canceled.connect(w.requestInterruption)
        w.start()
        dlg.exec()
        w.wait()
        msg = f"Copiados: {w.copied}\nYa estaban en el destino: {w.existing}"
        if w.errors:
            msg += f"\nErrores: {len(w.errors)}\n\n" + "\n".join(w.errors[:10])
        QMessageBox.information(self, APP_NAME, msg)
        self._refresh()


def about(parent):
    box = QMessageBox(parent)
    box.setWindowTitle("Acerca de")
    box.setIconPixmap(QPixmap(str(RESOURCES / "hada.png")).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                                                                   Qt.TransformationMode.SmoothTransformation))
    box.setText(f"<h3>{APP_NAME}</h3>Versión {VERSION}<br><br>Clasifica fotos y vídeos por año, mes y categoría, "
                "y cópialos a tu carpeta ordenada.")
    box.exec()
