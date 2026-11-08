"""Ventana principal: paso 1 (revisión de carpetas) y paso 2 (clasificación foto a foto)."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication, QKeySequence, QPixmap
from PySide6.QtWidgets import (QComboBox, QCompleter, QFileDialog, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox,
                               QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from . import APP_NAME, RESOURCES, month_name
from .dates import SOURCE_LABELS, parse_iso
from .dialogs import (CategoryManagerDialog, CopyDialog, OtherCategoryDialog, about, run_scan)
from .store import Store
from .widgets import (ClickLabel, ImageLoader, ImageView, PreviewDialog, VideoThumbnailer, VideoView,
                      fmt_date, with_play_icon)

STYLE = """
QWidget { font-size: 10.5pt; }
QMainWindow, QDialog { background: #f4f7f1; }
#header { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2f5d34, stop:1 #4f8a4a); }
#header QLabel { color: white; }
#apptitle { font-size: 15pt; font-weight: 600; }
#bigtitle { font-size: 20pt; font-weight: 600; color: #2f5d34; }
#steplabel { font-size: 12pt; font-weight: 600; color: #2f5d34; }
#filename { font-size: 12pt; font-weight: 600; }
#datebig { font-size: 12pt; color: #1f4a25; font-weight: 600; }
#muted { color: #5f6b5f; }
#hint { color: #6d4c00; background: #fff4d6; border: 1px solid #f0d58c; border-radius: 6px; padding: 6px; }
#status_ok { color: white; background: #2e7d32; border-radius: 6px; padding: 6px; font-weight: 600; }
#status_bad { color: white; background: #9e3b32; border-radius: 6px; padding: 6px; font-weight: 600; }
#section { color: #2f5d34; font-weight: 600; margin-top: 6px; }
QGroupBox { border: 1px solid #c9d8c4; border-radius: 8px; margin-top: 12px; padding: 8px; background: white; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #2f5d34; font-weight: 600; }
QPushButton { padding: 6px 10px; border: 1px solid #b7c9b1; border-radius: 6px; background: #ffffff; }
QPushButton:hover { background: #eaf3e6; }
QPushButton:disabled { color: #9aa59a; }
QPushButton#primary { background: #3f7a43; color: white; border-color: #2f5d34; font-weight: 600; padding: 8px 14px; }
QPushButton#primary:hover { background: #4b8c4f; }
QPushButton#yes { background: #3f7a43; color: white; font-weight: 600; font-size: 12pt; padding: 10px; }
QPushButton#no { background: #9e3b32; color: white; font-weight: 600; font-size: 12pt; padding: 10px; }
QPushButton#yes[chosen="true"], QPushButton#no[chosen="true"] { border: 4px solid #ffcf40; }
QPushButton[cat="true"] { text-align: left; padding: 8px 10px; }
QPushButton[cat="true"][state="suggested"] { background: #ffe9a8; border: 2px solid #e0a800; font-weight: 600; }
QPushButton[cat="true"][state="assigned"] { background: #2e7d32; color: white; border: 2px solid #1b5e20; font-weight: 600; }
#videobar { background: #263027; }
#videobar QLabel { color: #e8f0e3; }
QProgressBar { border: 1px solid #b7c9b1; border-radius: 5px; text-align: center; background: white; height: 16px; }
QProgressBar::chunk { background: #6aa865; border-radius: 4px; }
"""


def _btn(text, slot, tip="", name=""):
    b = QPushButton(text)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    if tip:
        b.setToolTip(tip)
    if name:
        b.setObjectName(name)
    b.clicked.connect(slot)
    return b


def _repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)


def _max_image_size() -> int:
    s = QGuiApplication.primaryScreen()
    if not s:
        return 2048
    g = s.availableGeometry()
    return int(min(3200, max(g.width(), g.height()) * s.devicePixelRatio()))


class _MonthCombo(QComboBox):
    def __init__(self):
        super().__init__()
        for m in range(1, 13):
            self.addItem(f"{m:02d} · {month_name(m)}", m)

    def month(self) -> int:
        return self.currentData()

    def set_month(self, m: int):
        self.setCurrentIndex(max(0, min(11, (m or 1) - 1)))


# ====================================================================== PASO 1
class ReviewPage(QWidget):
    finished = Signal()

    THUMB = 220

    def __init__(self, store: Store, loader: ImageLoader, parent=None):
        super().__init__(parent)
        self.store, self.loader = store, loader
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.folders: list[str] = []
        self.pos = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        top = QHBoxLayout()
        self.step = QLabel()
        self.step.setObjectName("steplabel")
        top.addWidget(self.step, 1)
        self.bar = QProgressBar()
        self.bar.setFixedWidth(260)
        top.addWidget(self.bar)
        lay.addLayout(top)
        expl = QLabel("Antes de ir foto a foto, dime qué carpetas son ya <b>agrupaciones</b> (un evento, un viaje, "
                      "una celebración…) y cuáles no (Descargas, WhatsApp Images, Cámara…). Las fotos de las carpetas "
                      "agrupadas aparecerán luego con su categoría ya propuesta.")
        expl.setWordWrap(True)
        expl.setObjectName("muted")
        lay.addWidget(expl)
        self.lbl_folder = QLabel()
        self.lbl_folder.setObjectName("filename")
        self.lbl_folder.setWordWrap(True)
        self.lbl_folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl_folder)
        self.lbl_counts = QLabel()
        self.lbl_counts.setObjectName("muted")
        lay.addWidget(self.lbl_counts)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(8)
        self.thumbs: list[QLabel] = []
        self.thumb_rel: list[str | None] = [None] * 8
        self.vthumbs = VideoThumbnailer(self, self.THUMB * 2)
        self.vthumbs.ready.connect(self._vthumb_ready)
        for i in range(8):
            t = ClickLabel()
            t.setToolTip("Clic para ver en grande / reproducir el vídeo")
            t.clicked.connect(lambda i=i: self.preview(i))
            t.setFixedSize(self.THUMB, int(self.THUMB * 0.75))
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setStyleSheet("background:#1c241d; color:#cfe0c9; border-radius:6px;")
            self.grid.addWidget(t, i // 4, i % 4)
            self.thumbs.append(t)
        lay.addWidget(self.grid_host, 0, Qt.AlignmentFlag.AlignHCenter)

        box = QGroupBox("Si es una agrupación, se creará esta categoría (puedes cambiarla):")
        bl = QHBoxLayout(box)
        self.year = QSpinBox()
        self.year.setRange(1900, 2100)
        self.month = _MonthCombo()
        self.name = QLineEdit()
        self.name.returnPressed.connect(lambda: self.decide(True))
        bl.addWidget(QLabel("Año"))
        bl.addWidget(self.year)
        bl.addWidget(QLabel("Mes"))
        bl.addWidget(self.month)
        bl.addWidget(QLabel("Nombre"))
        bl.addWidget(self.name, 1)
        lay.addWidget(box)

        q = QLabel("¿Esta carpeta es ya una agrupación de fotos?")
        q.setObjectName("steplabel")
        q.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(q)
        row = QHBoxLayout()
        self.b_prev = _btn("◀  Anterior  (←)", lambda: self.go(self.pos - 1))
        self.b_yes = _btn("✔  Sí  (S)", lambda: self.decide(True), "Es una agrupación: crear la categoría", "yes")
        self.b_no = _btn("✖  No  (N)", lambda: self.decide(False), "No es una agrupación", "no")
        self.b_next = _btn("Siguiente  (→)  ▶", lambda: self.go(self.pos + 1))
        row.addWidget(self.b_prev)
        row.addStretch(1)
        row.addWidget(self.b_yes, 2)
        row.addWidget(self.b_no, 2)
        row.addStretch(1)
        row.addWidget(self.b_next)
        lay.addLayout(row)
        fin = QHBoxLayout()
        fin.addStretch(1)
        fin.addWidget(_btn("Terminar y pasar a las fotos  ▶▶", self.finish, name="primary"))
        lay.addLayout(fin)
        lay.addStretch(1)
        self.loader.ready.connect(self._thumb_ready)

    # --------------------------------------------------------------
    def start(self):
        self.folders = self.store.folder_list()
        if not self.folders:
            self.finish()
            return
        self.go(min(self.store.data.get("folder_pos", 0), len(self.folders) - 1))
        self.setFocus()

    def go(self, pos: int):
        if not self.folders:
            return
        self.pos = max(0, min(pos, len(self.folders) - 1))
        self.store.data["folder_pos"] = self.pos
        f = self.folders[self.pos]
        info = self.store.folders[f]
        decided = sum(1 for x in self.folders if self.store.folders[x].get("group") is not None)
        self.step.setText(f"Paso 1 de 2 · Revisión de carpetas  —  carpeta {self.pos + 1} de {len(self.folders)}")
        self.bar.setMaximum(len(self.folders))
        self.bar.setValue(decided)
        self.bar.setFormat(f"{decided} de {len(self.folders)} revisadas")
        self.lbl_folder.setText(f"📁  {f}")
        files = self.store.folder_items(f)
        kinds = Counter(self.store.items[r].get("kind") for r in files)
        dates = sorted(d for d in (parse_iso(self.store.items[r].get("date")) for r in files) if d)
        rng = ""
        if dates:
            a, b = dates[0], dates[-1]
            rng = f"  ·  fechas: {month_name(a.month, False)} {a.year}" + (
                f" – {month_name(b.month, False)} {b.year}" if (a.year, a.month) != (b.year, b.month) else "")
        self.lbl_counts.setText(f"{kinds.get('image', 0) + kinds.get('raw', 0)} fotos · {kinds.get('video', 0)} vídeos{rng}")
        if info.get("category") and info["category"] in self.store.categories:
            c = self.store.categories[info["category"]]
            y, m, name = c["year"], c["month"], c["name"]
        else:
            y, m, name = self.store.folder_proposal(f)
        today = dt.date.today()
        self.year.setValue(y or today.year)
        self.month.set_month(m or today.month)
        self.name.setText(name)
        self.b_yes.setProperty("chosen", "true" if info.get("group") is True else "false")
        self.b_no.setProperty("chosen", "true" if info.get("group") is False else "false")
        _repolish(self.b_yes)
        _repolish(self.b_no)
        self._thumb_keys = {}
        self.vthumbs.cancel_pending()
        imgs = [r for r in files if self.store.items[r].get("kind") in ("image", "raw")]
        vids = [r for r in files if self.store.items[r].get("kind") == "video"]
        show = (imgs[:8 - min(len(vids), 2)] + vids)[:8]  # hasta 2 vídeos en el mosaico
        for i, t in enumerate(self.thumbs):
            t.clear()
            t.setVisible(i < len(show))
            self.thumb_rel[i] = show[i] if i < len(show) else None
            if i < len(show):
                r = show[i]
                if self.store.items[r].get("kind") == "video":
                    t.setText("🎬\n" + r.rsplit("/", 1)[-1])
                    self._thumb_keys[r] = t
                    got = self.vthumbs.request(r, self.store.abs_path(r))
                    if got is not None:
                        self._vthumb_ready(r, got)
                    continue
                t.setText("…")
                self._thumb_keys[r] = t
                got = self.loader.request(r, self.store.abs_path(r), self.THUMB * 2)
                if got:
                    self._thumb_ready(r, self.THUMB * 2, *got)
        self.setFocus()

    def _thumb_ready(self, key, size, img, info, err):
        t = getattr(self, "_thumb_keys", {}).get(key)
        if t is None or size != self.THUMB * 2:
            return
        if img is None:
            t.setText("⚠\n" + key.rsplit("/", 1)[-1])
            return
        pm = QPixmap.fromImage(img).scaled(t.size() * t.devicePixelRatioF(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(t.devicePixelRatioF())
        t.setPixmap(pm)

    def _vthumb_ready(self, key, img):
        t = getattr(self, "_thumb_keys", {}).get(key)
        if t is None or img is None:
            return
        pm = QPixmap.fromImage(img).scaled(t.size() * t.devicePixelRatioF(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(t.devicePixelRatioF())
        t.setPixmap(with_play_icon(pm))

    def preview(self, i: int):
        rel = self.thumb_rel[i]
        if not rel:
            return
        PreviewDialog(self.store.abs_path(rel), self.store.items[rel].get("kind") == "video", self).exec()
        self.setFocus()

    def decide(self, yes: bool):
        if not self.folders:
            return
        f = self.folders[self.pos]
        if yes:
            name = self.name.text().strip()
            if not name:
                QMessageBox.warning(self, APP_NAME, "Escribe un nombre para la categoría.")
                self.name.setFocus()
                return
            self.store.set_folder_group(f, True, self.year.value(), self.month.month(), name)
        else:
            self.store.set_folder_group(f, False)
        self.store.save()
        if self.pos + 1 >= len(self.folders):
            undecided = [x for x in self.folders if self.store.folders[x].get("group") is None]
            if undecided:
                self.go(self.folders.index(undecided[0]))
            else:
                self.finish()
        else:
            self.go(self.pos + 1)

    def finish(self):
        self.store.data["phase"] = "photos"
        self.store.save()
        self.finished.emit()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_S:
            self.decide(True)
        elif k == Qt.Key.Key_N:
            self.decide(False)
        elif k == Qt.Key.Key_Left:
            self.go(self.pos - 1)
        elif k == Qt.Key.Key_Right:
            self.go(self.pos + 1)
        else:
            super().keyPressEvent(e)


# ====================================================================== PASO 2
class ClassifyPage(QWidget):
    def __init__(self, store: Store, loader: ImageLoader, parent=None):
        super().__init__(parent)
        self.store, self.loader = store, loader
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.order: list[str] = []
        self.pos = 0
        self.last_used: list[str] = []
        self.cat_buttons: list[tuple[QPushButton, str]] = []
        self.img_size = _max_image_size()

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split)

        # ---- izquierda: foto / vídeo
        self.media = QStackedWidget()
        self.image = ImageView()
        self.video = VideoView()
        self.media.addWidget(self.image)
        self.media.addWidget(self.video)
        split.addWidget(self.media)

        # ---- derecha: panel
        panel = QWidget()
        panel.setMinimumWidth(400)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(12, 10, 12, 10)
        top = QHBoxLayout()
        self.lbl_pos = QLabel()
        self.lbl_pos.setObjectName("steplabel")
        top.addWidget(self.lbl_pos, 1)
        pl.addLayout(top)
        self.bar = QProgressBar()
        pl.addWidget(self.bar)

        self.lbl_name = QLabel()
        self.lbl_name.setObjectName("filename")
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pl.addWidget(self.lbl_name)
        self.lbl_folder = QLabel()
        self.lbl_folder.setObjectName("muted")
        self.lbl_folder.setWordWrap(True)
        pl.addWidget(self.lbl_folder)
        self.lbl_date = QLabel()
        self.lbl_date.setObjectName("datebig")
        self.lbl_date.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_date.setWordWrap(True)
        pl.addWidget(self.lbl_date)
        self.lbl_meta = QLabel()
        self.lbl_meta.setWordWrap(True)
        self.lbl_meta.setTextFormat(Qt.TextFormat.RichText)
        pl.addWidget(self.lbl_meta)
        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)
        pl.addWidget(self.lbl_status)
        self.lbl_hint = QLabel()
        self.lbl_hint.setObjectName("hint")
        self.lbl_hint.setWordWrap(True)
        pl.addWidget(self.lbl_hint)

        # categorías
        self.cat_scroll = QScrollArea()
        self.cat_scroll.setWidgetResizable(True)
        self.cat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cat_host = QWidget()
        self.cat_host.setObjectName("cathost")
        self.cat_scroll.setStyleSheet("QScrollArea, #cathost { background: transparent; }")
        self.cat_lay = QVBoxLayout(self.cat_host)
        self.cat_lay.setContentsMargins(0, 0, 4, 0)
        self.cat_scroll.setWidget(self.cat_host)
        pl.addWidget(self.cat_scroll, 1)

        row = QHBoxLayout()
        row.addWidget(_btn("🔎  Otra categoría…  (O)", self.other_category))
        row.addWidget(_btn("➕  Nueva categoría  (N)", self.show_form))
        pl.addLayout(row)

        # formulario de nueva categoría
        self.form = QGroupBox("Nueva categoría")
        fl = QGridLayout(self.form)
        self.f_year = QSpinBox()
        self.f_year.setRange(1900, 2100)
        self.f_month = _MonthCombo()
        self.f_name = QLineEdit()
        self.f_name.setPlaceholderText("Nombre (p. ej. Feria de Abril)")
        self.f_name.returnPressed.connect(self.create_category)
        self.completer = QCompleter([])
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.f_name.setCompleter(self.completer)
        fl.addWidget(QLabel("Año"), 0, 0)
        fl.addWidget(self.f_year, 0, 1)
        fl.addWidget(QLabel("Mes"), 0, 2)
        fl.addWidget(self.f_month, 0, 3)
        fl.addWidget(self.f_name, 1, 0, 1, 4)
        b_ok = QPushButton("Crear y asignar  (Intro)")
        b_ok.setObjectName("primary")
        b_ok.clicked.connect(self.create_category)
        b_cancel = QPushButton("Cancelar  (Esc)")
        b_cancel.clicked.connect(self.hide_form)
        b_nocat = QPushButton("📅 Solo el mes, sin categoría")
        b_nocat.setToolTip("Asignar a este año y mes, sin carpeta de categoría")
        b_nocat.clicked.connect(self.assign_form_nocat)
        fl.addWidget(b_cancel, 2, 0, 1, 2)
        fl.addWidget(b_ok, 2, 2, 1, 2)
        fl.addWidget(b_nocat, 3, 0, 1, 4)
        self.form.hide()
        pl.addWidget(self.form)

        row2 = QHBoxLayout()
        row2.addWidget(_btn("✖ Descartar (D)", self.discard, "No clasificar esta foto (no se copiará)"))
        row2.addWidget(_btn("↺ Quitar (Supr)", self.clear, "Quitar la clasificación de esta foto"))
        row2.addWidget(_btn("↗ Abrir (A)", self.open_external, "Abrir con el programa del sistema"))
        pl.addLayout(row2)
        nav = QHBoxLayout()
        nav.addWidget(_btn("◀  Anterior (←)", lambda: self.go(self.pos - 1)))
        nav.addWidget(_btn("Siguiente (→)  ▶", lambda: self.go(self.pos + 1)))
        nav.addWidget(_btn("⏭ Pendiente (P)", self.next_pending, "Ir a la siguiente foto sin clasificar"))
        pl.addLayout(nav)

        split.addWidget(panel)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([900, 440])
        self.loader.ready.connect(self._loaded)

    # -------------------------------------------------------------- navegación
    def start(self):
        self.order = self.store.ordered()
        if not self.order:
            self.image.set_image(None, "No hay fotos ni vídeos en esta carpeta.")
            return
        self.go(min(self.store.data.get("position", 0), len(self.order) - 1))
        self.setFocus()

    def refresh(self):
        cur = self.order[self.pos] if self.order else None
        self.order = self.store.ordered()
        if cur in self.order:
            self.pos = self.order.index(cur)
        self.go(self.pos)

    @property
    def rel(self) -> str | None:
        return self.order[self.pos] if self.order and 0 <= self.pos < len(self.order) else None

    def go(self, pos: int):
        if not self.order:
            return
        self.pos = max(0, min(pos, len(self.order) - 1))
        self.hide_form()
        self.show_current()
        self.setFocus()

    def next_pending(self):
        n = len(self.order)
        for k in range(1, n + 1):
            i = (self.pos + k) % n
            if self.store.items[self.order[i]].get("status", "pending") == "pending":
                self.go(i)
                return
        QMessageBox.information(self, APP_NAME, "🎉 ¡No queda ninguna foto pendiente de clasificar!")

    # -------------------------------------------------------------- pintar
    def show_current(self):
        rel = self.rel
        if rel is None:
            return
        it = self.store.items[rel]
        st = self.store.stats()
        n = len(self.order)
        self.lbl_pos.setText(f"Paso 2 de 2 · Foto {self.pos + 1} de {n}")
        self.bar.setMaximum(max(1, st["total"]))
        self.bar.setValue(st["assigned"] + st["discarded"])
        self.bar.setFormat(f"{st['assigned']} clasificadas · {st['discarded']} descartadas · {st['pending']} pendientes")
        name = rel.rsplit("/", 1)[-1]
        folder = rel.rsplit("/", 1)[0] if "/" in rel else "(carpeta principal)"
        kind = it.get("kind")
        icon = "🎬" if kind == "video" else "🖼"
        self.lbl_name.setText(f"{icon}  {name}")
        self.lbl_folder.setText(f"📁 {folder}")
        d = parse_iso(it.get("date"))
        if d:
            src = it.get("date_src")
            warn = " ⚠" if src == "fichero" else ""
            self.lbl_date.setText(f"📅 {fmt_date(d)}{warn}<br><span style='font-size:9.5pt; font-weight:normal; color:#5f6b5f'>"
                                  f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;según {SOURCE_LABELS.get(src, src)}</span>")
        else:
            self.lbl_date.setText("📅 Fecha desconocida")
        self._meta_dates_html = self._other_dates(it)
        self.lbl_meta.setText(self._meta_dates_html)
        # estado
        status = it.get("status", "pending")
        if status == "assigned" and it.get("category") in self.store.categories:
            self.lbl_status.setObjectName("status_ok")
            self.lbl_status.setText(f"✔ Clasificada en: {self.store.category_label(it['category'])}")
            self.lbl_status.show()
        elif status == "discarded":
            self.lbl_status.setObjectName("status_bad")
            self.lbl_status.setText("✖ Descartada (no se copiará)")
            self.lbl_status.show()
        else:
            self.lbl_status.hide()
        _repolish(self.lbl_status)
        sugg = it.get("suggested")
        if sugg and sugg in self.store.categories and status == "pending":
            self.lbl_hint.setText(f"💡 Estaba en la carpeta «{folder}». Categoría propuesta resaltada en amarillo: "
                                  "púlsala para confirmar.")
            self.lbl_hint.show()
        else:
            self.lbl_hint.hide()
        self.build_buttons()
        # medio
        path = self.store.abs_path(rel)
        if kind == "video":
            self.media.setCurrentWidget(self.video)
            self.video.play(path)
        else:
            self.video.stop()
            self.media.setCurrentWidget(self.image)
            got = self.loader.request(rel, path, self.img_size)
            if got:
                self._loaded(rel, self.img_size, *got)
            else:
                self.image.set_image(None, "Cargando…")
        if kind == "video":
            self.loader.request(rel, path, self.img_size, want_image=False)
        # precarga
        for k in (1, 2, -1):
            j = self.pos + k
            if 0 <= j < n:
                r2 = self.order[j]
                if self.store.items[r2].get("kind") != "video":
                    self.loader.request(r2, self.store.abs_path(r2), self.img_size)

    def _other_dates(self, it) -> str:
        dates = it.get("dates") or {}
        chosen = it.get("date_src")
        lines = []
        for src, iso in dates.items():
            if src == chosen:
                continue
            d = parse_iso(iso)
            if d:
                lines.append(f"<span style='color:#5f6b5f'>Otra fecha · {SOURCE_LABELS.get(src, src)}: {d:%d/%m/%Y %H:%M}</span>")
        return "<br>".join(lines)

    def _loaded(self, key, size, img, info, err):
        if key != self.rel or size != self.img_size:
            return
        it = self.store.items[key]
        if it.get("kind") != "video":
            if img is None:
                self.image.set_image(None, f"No se puede mostrar esta imagen:\n{err}\n\nPulsa A para abrirla con el programa del sistema.")
            else:
                self.image.set_image(img)
        rows = [f"<b>{k}:</b> {v}" for k, v in info.items()]
        extra = "<br>".join(rows)
        self.lbl_meta.setText("<br>".join(x for x in (extra, self._meta_dates_html) if x))

    def build_buttons(self):
        while self.cat_lay.count():
            w = self.cat_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.cat_buttons = []
        rel = self.rel
        it = self.store.items[rel]
        main, recent = self.store.suggestions(rel, self.last_used)
        d = parse_iso(it.get("date"))
        nocat_cur = self.store.find_nocat(d.year, d.month) if d else None
        main = [c for c in main if c != nocat_cur]
        recent = [c for c in recent if c != nocat_cur]

        def section(text):
            lab = QLabel(text)
            lab.setObjectName("section")
            self.cat_lay.addWidget(lab)

        def add(cid):
            num = len(self.cat_buttons) + 1
            key = str(num % 10) if num <= 10 else " "
            c = self.store.categories[cid]
            name = "📅 Sin categoría" if c.get("nocat") else c["name"]
            b = QPushButton(f"[{key}]   {name}    ·  {month_name(c['month'], False)} {c['year']}")
            b.setProperty("cat", "true")
            state = ""
            if it.get("status") == "assigned" and it.get("category") == cid:
                state = "assigned"
            elif it.get("status", "pending") == "pending" and it.get("suggested") == cid:
                state = "suggested"
            b.setProperty("state", state)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, c=cid: self.assign(c))
            self.cat_lay.addWidget(b)
            self.cat_buttons.append((b, cid))

        if d:
            b = QPushButton(f"[S]   📅 Sin categoría  ·  solo {month_name(d.month, False)} de {d.year}")
            b.setToolTip("La foto irá directamente a la carpeta del mes, sin carpeta de categoría")
            b.setProperty("cat", "true")
            b.setProperty("state", "assigned" if it.get("status") == "assigned" and nocat_cur
                          and it.get("category") == nocat_cur else "")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(self.assign_nocat)
            self.cat_lay.addWidget(b)
            prev_m = (d.replace(day=1) - dt.timedelta(days=1))
            next_m = (d.replace(day=28) + dt.timedelta(days=4))
            if prev_m.year == next_m.year:
                months = (f"{month_name(prev_m.month, False)}, {month_name(d.month, False)} y "
                          f"{month_name(next_m.month, False)} de {d.year}")
            else:
                months = ", ".join(f"{month_name(x.month, False)} {x.year}" for x in (prev_m, d, next_m))
            section(f"Categorías de {months}")
        else:
            section("Categorías")
        for cid in main:
            add(cid)
        if not main:
            lab = QLabel("Aún no hay categorías en estos meses.\nCrea una nueva (N) o busca otra (O).")
            lab.setObjectName("muted")
            self.cat_lay.addWidget(lab)
        if recent:
            section("Recientes (usadas en fotos de fechas cercanas)" if d else "Usadas recientemente")
            for cid in recent:
                add(cid)
        self.cat_lay.addStretch(1)

    # -------------------------------------------------------------- acciones
    def assign(self, cid: str):
        rel = self.rel
        if rel is None:
            return
        self.store.assign(rel, cid)
        if cid in self.last_used:
            self.last_used.remove(cid)
        self.last_used.insert(0, cid)
        del self.last_used[8:]
        self._advance()

    def assign_nocat(self):
        """Asigna la foto a su mes, sin categoría."""
        if not self.rel:
            return
        d = parse_iso(self.store.items[self.rel].get("date"))
        if d is None:  # sin fecha: hay que elegir el mes en el formulario
            self.show_form()
            return
        self.assign(self.store.nocat(d.year, d.month))

    def assign_form_nocat(self):
        cid = self.store.nocat(self.f_year.value(), self.f_month.month())
        self.form.hide()
        self.assign(cid)

    def discard(self):
        if self.rel:
            self.store.discard(self.rel)
            self._advance()

    def clear(self):
        if self.rel:
            self.store.clear(self.rel)
            self.store.save()
            self.show_current()

    def _advance(self):
        last = self.pos + 1 >= len(self.order)
        self.store.data["position"] = min(self.pos + 1, len(self.order) - 1)
        self.store.save()
        if last:
            self.show_current()
            st = self.store.stats()
            if st["pending"]:
                QMessageBox.information(self, APP_NAME, f"Has llegado a la última foto.\nQuedan {st['pending']} sin clasificar: "
                                        "pulsa P para ir a la siguiente pendiente.")
            else:
                QMessageBox.information(self, APP_NAME, "🎉 ¡Todas las fotos están clasificadas!\n\n"
                                        "Ahora puedes copiarlas a tu carpeta ordenada desde el menú Destino.")
        else:
            self.go(self.pos + 1)

    def other_category(self):
        if not self.rel:
            return
        if not self.store.categories:
            QMessageBox.information(self, APP_NAME, "Todavía no hay ninguna categoría. Crea una con N.")
            return
        d = parse_iso(self.store.items[self.rel].get("date"))
        dlg = OtherCategoryDialog(self.store, d, self)
        if dlg.exec() and dlg.chosen:
            self.assign(dlg.chosen)
        else:
            self.setFocus()

    def show_form(self):
        if not self.rel:
            return
        d = parse_iso(self.store.items[self.rel].get("date")) or dt.datetime.now()
        self.f_year.setValue(d.year)
        self.f_month.set_month(d.month)
        self.f_name.clear()
        names = sorted({c["name"] for c in self.store.categories.values()}, key=str.casefold)
        self.completer.model().setStringList(names)
        self.form.show()
        self.f_name.setFocus()

    def hide_form(self):
        self.form.hide()
        self.setFocus()

    def create_category(self):
        name = self.f_name.text().strip()
        if not name:
            self.f_name.setFocus()
            return
        cid = self.store.new_category(self.f_year.value(), self.f_month.month(), name, "nueva")
        self.form.hide()
        self.assign(cid)

    def open_external(self):
        if self.rel:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.abs_path(self.rel))))

    def keyPressEvent(self, e):
        k = e.key()
        if self.form.isVisible() and k == Qt.Key.Key_Escape:
            self.hide_form()
            return
        if Qt.Key.Key_0 <= k <= Qt.Key.Key_9 and not e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            n = k - Qt.Key.Key_0
            idx = 9 if n == 0 else n - 1
            if idx < len(self.cat_buttons):
                self.assign(self.cat_buttons[idx][1])
            return
        actions = {
            Qt.Key.Key_Right: lambda: self.go(self.pos + 1),
            Qt.Key.Key_Left: lambda: self.go(self.pos - 1),
            Qt.Key.Key_Home: lambda: self.go(0),
            Qt.Key.Key_End: lambda: self.go(len(self.order) - 1),
            Qt.Key.Key_P: self.next_pending,
            Qt.Key.Key_O: self.other_category,
            Qt.Key.Key_N: self.show_form,
            Qt.Key.Key_S: self.assign_nocat,
            Qt.Key.Key_D: self.discard,
            Qt.Key.Key_Delete: self.clear,
            Qt.Key.Key_Backspace: self.clear,
            Qt.Key.Key_A: self.open_external,
            Qt.Key.Key_M: self.video.toggle_mute,
            Qt.Key.Key_Space: self.video.toggle_play,
        }
        fn = actions.get(k)
        if fn:
            fn()
        else:
            super().keyPressEvent(e)


# ====================================================================== ventana
class MainWindow(QMainWindow):
    open_other = Signal()
    restart = Signal()

    def __init__(self, store: Store, is_new: bool):
        super().__init__()
        self.store, self.is_new = store, is_new
        self.setWindowTitle(f"{APP_NAME} — {store.root}")
        self.loader = ImageLoader(self)

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        header = QWidget()
        header.setObjectName("header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 6, 12, 6)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(RESOURCES / "hada.png")).scaled(46, 46, Qt.AspectRatioMode.KeepAspectRatio,
                                                                   Qt.TransformationMode.SmoothTransformation))
        hl.addWidget(logo)
        t = QLabel(APP_NAME)
        t.setObjectName("apptitle")
        hl.addWidget(t)
        hl.addStretch(1)
        self.lbl_root = QLabel(str(store.root))
        hl.addWidget(self.lbl_root)
        cl.addWidget(header)

        self.pages = QStackedWidget()
        self.review = ReviewPage(store, self.loader)
        self.classify = ClassifyPage(store, self.loader)
        self.pages.addWidget(self.review)
        self.pages.addWidget(self.classify)
        cl.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self.review.finished.connect(self.to_photos)
        self._menus()
        self.resize(1400, 880)

    def _menus(self):
        mb = self.menuBar()
        m = mb.addMenu("&Archivo")
        self._act(m, "Abrir otra carpeta…", self.open_other.emit, QKeySequence.StandardKey.Open)
        self._act(m, "Volver a buscar fotos nuevas en la carpeta", self.rescan)
        self._act(m, "Reiniciar todo el trabajo de esta carpeta…", self.ask_restart)
        m.addSeparator()
        self._act(m, "Salir", self.close, QKeySequence.StandardKey.Quit)
        m = mb.addMenu("&Ver")
        self._act(m, "Paso 1: revisión de carpetas", self.to_review)
        self._act(m, "Paso 2: clasificar fotos", self.to_photos)
        m = mb.addMenu("&Categorías")
        self._act(m, "Gestionar categorías…", self.manage)
        m = mb.addMenu("&Destino")
        self._act(m, "Elegir carpeta destino e importar sus categorías…", self.choose_dest)
        self._act(m, "Copiar las fotos clasificadas al destino…", self.copy_dest)
        m = mb.addMenu("A&yuda")
        self._act(m, "Atajos de teclado", self.shortcuts, QKeySequence("F1"))
        self._act(m, "Acerca de", lambda: about(self))

    def _act(self, menu, text, slot, shortcut=None):
        a = QAction(text, self)
        if shortcut is not None:
            a.setShortcut(shortcut)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    # --------------------------------------------------------------
    def begin(self):
        if self.is_new:
            r = QMessageBox.question(
                self, APP_NAME,
                "¿Quieres indicar ya la carpeta <b>destino</b> donde tienes las fotos ordenadas "
                "(Año / Mes / Categoría)?<br><br>Así sus categorías aparecerán como sugerencias desde el principio. "
                "También puedes hacerlo más tarde desde el menú Destino.")
            if r == QMessageBox.StandardButton.Yes:
                self.choose_dest(silent_refresh=True)
        if self.store.data.get("phase") == "folders":
            self.to_review()
        else:
            self.to_photos()

    def to_review(self):
        self.classify.video.stop()
        self.pages.setCurrentWidget(self.review)
        self.review.start()

    def to_photos(self):
        self.store.data["phase"] = "photos"
        self.pages.setCurrentWidget(self.classify)
        self.classify.start()

    def ask_restart(self):
        st = self.store.stats()
        r = QMessageBox.warning(
            self, APP_NAME,
            f"¿Empezar de cero en esta carpeta?\n\nSe descartan las categorías y las {st['assigned']} fotos clasificadas "
            "(útil si has estado haciendo pruebas).\n\nNo se borra ninguna foto, y el progreso actual se guarda "
            "como copia (hada_del_bosque.reiniciado-…json) por si acaso.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Yes:
            self.no_save = True
            self.restart.emit()

    def rescan(self):
        run_scan(self.store, self)
        if self.pages.currentWidget() is self.classify:
            self.classify.refresh()
        else:
            self.review.start()

    def manage(self):
        dlg = CategoryManagerDialog(self.store, self)
        dlg.exec()
        if dlg.changed:
            self._refresh_current()

    def _refresh_current(self):
        if self.pages.currentWidget() is self.classify and self.classify.order:
            self.classify.show_current()
        elif self.pages.currentWidget() is self.review:
            self.review.go(self.review.pos)

    def choose_dest(self, silent_refresh=False):
        start = str(self.store.dest or self.store.root.parent)
        d = QFileDialog.getExistingDirectory(self, "Carpeta destino (donde ya tienes las fotos ordenadas)", start)
        if not d:
            return
        dp = Path(d).resolve()
        if dp == self.store.root.resolve():
            QMessageBox.warning(self, APP_NAME, "El destino no puede ser la misma carpeta que estás ordenando.")
            return
        self.store.data["dest"] = str(dp)
        n = self.store.import_dest_categories(dp)
        self.store.save()
        QMessageBox.information(self, APP_NAME, f"Carpeta destino: {dp}\nCategorías nuevas importadas: {n}")
        if not silent_refresh:
            self._refresh_current()

    def copy_dest(self):
        CopyDialog(self.store, self).exec()
        self._refresh_current()

    def shortcuts(self):
        QMessageBox.information(self, "Atajos de teclado", (
            "<h3>Paso 1 · Carpetas</h3>"
            "<b>S</b> sí, es una agrupación · <b>N</b> no · <b>← →</b> anterior / siguiente<br>"
            "<h3>Paso 2 · Fotos</h3>"
            "<b>1 … 9, 0</b> asignar la categoría con ese número (y pasar a la siguiente)<br>"
            "<b>S</b> sin categoría (solo el mes de la foto)<br>"
            "<b>N</b> nueva categoría · <b>O</b> otra categoría (buscar)<br>"
            "<b>D</b> descartar · <b>Supr</b> quitar clasificación<br>"
            "<b>←  →</b> anterior / siguiente · <b>P</b> siguiente pendiente · <b>Inicio / Fin</b><br>"
            "<b>Espacio</b> pausa del vídeo · <b>M</b> sonido · <b>A</b> abrir con el programa del sistema"))

    def closeEvent(self, e):
        if getattr(self, "no_save", False):
            self.classify.video.stop()
            super().closeEvent(e)
            return
        try:
            self.classify.video.stop()
            if self.classify.order:
                self.store.data["position"] = self.classify.pos
            self.store.save()
        except Exception:
            pass
        super().closeEvent(e)


def start_later(fn):
    QTimer.singleShot(0, fn)
