"""Componentes reutilizables: carga de imágenes en segundo plano, visor de imagen y de vídeo."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QRectF, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider,
                               QVBoxLayout, QWidget)

from . import month_name
from .media import image_info, load_image

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def fmt_date(d, with_time=True) -> str:
    s = f"{DIAS[d.weekday()]}, {d.day} de {month_name(d.month, False)} de {d.year}"
    if with_time and (d.hour or d.minute or d.second):
        s += f" · {d:%H:%M}"
    return s


def pil_to_qimage(im) -> QImage:
    w, h = im.size
    data = im.tobytes("raw", "RGBA")
    return QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()


# ------------------------------------------------------------------ cargador
class _Signals(QObject):
    loaded = Signal(str, int, object, object, str)  # clave, tamaño, QImage|None, info, error


class _LoadTask(QRunnable):
    def __init__(self, key: str, path: Path, size: int, want_image: bool, signals: _Signals):
        super().__init__()
        self.key, self.path, self.size, self.want_image, self.signals = key, path, size, want_image, signals

    def run(self):
        img, err = None, ""
        info = {}
        try:
            info = image_info(self.path)
        except Exception:
            pass
        if self.want_image:
            try:
                img = pil_to_qimage(load_image(self.path, self.size, self.size))
            except Exception as e:  # noqa: BLE001
                err = str(e) or e.__class__.__name__
        self.signals.loaded.emit(self.key, self.size, img, info, err)


class ImageLoader(QObject):
    """Carga imágenes en hilos y mantiene una pequeña caché."""

    ready = Signal(str, int, object, object, str)

    def __init__(self, parent=None, cache_size=12):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self.cache: OrderedDict[tuple[str, int], tuple] = OrderedDict()
        self.pending: set[tuple[str, int]] = set()
        self.cache_size = cache_size
        self.signals = _Signals()
        self.signals.loaded.connect(self._on_loaded)

    def request(self, key: str, path: Path, size: int, want_image: bool = True) -> tuple | None:
        k = (key, size)
        if k in self.cache:
            self.cache.move_to_end(k)
            return self.cache[k]
        if k not in self.pending:
            self.pending.add(k)
            self.pool.start(_LoadTask(key, path, size, want_image, self.signals))
        return None

    def _on_loaded(self, key, size, img, info, err):
        k = (key, size)
        self.pending.discard(k)
        self.cache[k] = (img, info, err)
        while len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        self.ready.emit(key, size, img, info, err)


# ------------------------------------------------------------------ visor de imagen
class ImageView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix: QPixmap | None = None
        self._scaled: QPixmap | None = None
        self._msg = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(300, 300)

    def set_image(self, img: QImage | None, msg: str = ""):
        self._pix = QPixmap.fromImage(img) if img is not None and not img.isNull() else None
        self._scaled = None
        self._msg = msg
        self.update()

    def resizeEvent(self, e):
        self._scaled = None
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1c241d"))
        if self._pix:
            dpr = self.devicePixelRatioF()
            if self._scaled is None:
                target = self.size() * dpr
                pw, ph = self._pix.width(), self._pix.height()
                if pw <= target.width() and ph <= target.height():
                    self._scaled = self._pix
                else:
                    self._scaled = self._pix.scaled(target, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation)
            sw, sh = self._scaled.width() / dpr, self._scaled.height() / dpr
            r = QRectF((self.width() - sw) / 2, (self.height() - sh) / 2, sw, sh)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(r, self._scaled, QRectF(self._scaled.rect()))
        if self._msg:
            p.setPen(QColor("#e8f0e3"))
            f = QFont(self.font())
            f.setPointSize(13)
            p.setFont(f)
            p.drawText(self.rect().adjusted(20, 20, -20, -20), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._msg)
        p.end()


# ------------------------------------------------------------------ visor de vídeo
class VideoView(QWidget):
    """Reproductor de vídeo con Qt Multimedia (no requiere instalar nada más)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.available = False
        self.muted = True
        self.setObjectName("videoview")
        self.setStyleSheet("#videoview { background: #000; }")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget

            self.video = QVideoWidget(self)
            self.video.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.video.setStyleSheet("background:#000")
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.audio.setMuted(True)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            self.player.setLoops(QMediaPlayer.Loops.Infinite)
            self.player.positionChanged.connect(self._pos)
            self.player.durationChanged.connect(self._dur)
            self.player.errorOccurred.connect(self._err)
            self.player.playbackStateChanged.connect(self._state)
            self._QMediaPlayer = QMediaPlayer
            lay.addWidget(self.video, 1)
            self.available = True
        except Exception as e:  # noqa: BLE001
            self.video = QLabel(f"No se puede reproducir vídeo en este equipo:\n{e}")
            self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(self.video, 1)
        bar = QWidget(self)
        bar.setObjectName("videobar")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(8, 4, 8, 4)
        self.btn_play = QPushButton("⏸")
        self.btn_play.setToolTip("Reproducir / pausa (Espacio)")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.lbl_time = QLabel("0:00 / 0:00")
        self.btn_mute = QPushButton("🔇 Sonido")
        self.btn_mute.setToolTip("Activar / silenciar sonido (M)")
        for w in (self.btn_play, self.slider, self.btn_mute):
            w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hl.addWidget(self.btn_play)
        hl.addWidget(self.slider, 1)
        hl.addWidget(self.lbl_time)
        hl.addWidget(self.btn_mute)
        lay.addWidget(bar)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_mute.clicked.connect(self.toggle_mute)
        self.slider.sliderMoved.connect(lambda v: self.available and self.player.setPosition(v))
        self.error_label = QLabel("", self)
        self.error_label.setStyleSheet("color:#ffd27a; background:rgba(0,0,0,150); padding:8px;")
        self.error_label.hide()

    def play(self, path: Path):
        self.error_label.hide()
        if not self.available:
            return
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.audio.setMuted(self.muted)
        self.player.play()

    def stop(self):
        if self.available:
            self.player.stop()
            self.player.setSource(QUrl())

    def toggle_play(self):
        if not self.available:
            return
        if self.player.playbackState() == self._QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.available:
            self.audio.setMuted(self.muted)
        self.btn_mute.setText("🔇 Sonido" if self.muted else "🔊 Sonido")

    @staticmethod
    def _t(ms):
        s = int(ms // 1000)
        return f"{s // 60}:{s % 60:02d}"

    def _pos(self, ms):
        if not self.slider.isSliderDown():
            self.slider.setValue(int(ms))
        self.lbl_time.setText(f"{self._t(ms)} / {self._t(self.player.duration())}")

    def _dur(self, ms):
        self.slider.setRange(0, int(ms))

    def _state(self, st):
        playing = st == self._QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setText("⏸" if playing else "▶")

    def _err(self, err, msg):
        if err != self._QMediaPlayer.Error.NoError:
            self.error_label.setText(f"No se pudo reproducir: {msg}\nPuedes abrirlo con el reproductor del sistema (tecla A).")
            self.error_label.adjustSize()
            self.error_label.move(10, 10)
            self.error_label.show()


# ------------------------------------------------------------------ miniaturas de vídeo
class VideoThumbnailer(QObject):
    """Saca un fotograma de cada vídeo (uno detrás de otro) con Qt Multimedia."""

    ready = Signal(str, object)  # clave, QImage|None

    def __init__(self, parent=None, size=480):
        super().__init__(parent)
        self.size = size
        self.cache: dict[str, QImage | None] = {}
        self.queue: list[tuple[str, Path]] = []
        self.busy: str | None = None
        self.available = False
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QVideoSink

            self.player = QMediaPlayer(self)
            self.sink = QVideoSink(self)
            self.player.setVideoSink(self.sink)
            self.sink.videoFrameChanged.connect(self._frame)
            self.player.errorOccurred.connect(lambda *a: self.busy and self._done(None))
            self.available = True
        except Exception:  # noqa: BLE001
            pass
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.busy and self._done(None))

    def request(self, key: str, path: Path):
        if key in self.cache:
            return self.cache[key]
        if self.available and key != self.busy and all(k != key for k, _ in self.queue):
            self.queue.append((key, path))
            self._next()
        return None

    def cancel_pending(self):
        self.queue.clear()

    def _next(self):
        if self.busy or not self.queue:
            return
        self.busy, path = self.queue.pop(0)
        self._frames = 0
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()
        self.timer.start(6000)

    def _frame(self, frame):
        if not self.busy or not frame.isValid():
            return
        self._frames += 1
        if frame.startTime() < 400_000 and self._frames < 12:  # evitar el primer fotograma (a menudo negro)
            return
        img = frame.toImage()
        if img.isNull():
            return
        self._done(img.scaled(self.size, self.size, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation))

    def _done(self, img):
        key = self.busy
        self.busy = None
        self.timer.stop()
        self.cache[key] = img
        QTimer.singleShot(0, self._reset_and_next)
        self.ready.emit(key, img)

    def _reset_and_next(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self._next()


def with_play_icon(pm: QPixmap) -> QPixmap:
    """Dibuja un triángulo de «play» sobre una miniatura."""
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    w, h = out.width() / out.devicePixelRatio(), out.height() / out.devicePixelRatio()
    r = min(w, h) * 0.16
    cx, cy = w / 2, h / 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 150))
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawPolygon(QPolygonF([QPointF(cx - r * 0.35, cy - r * 0.5), QPointF(cx - r * 0.35, cy + r * 0.5),
                             QPointF(cx + r * 0.55, cy)]))
    p.end()
    return out


class ClickLabel(QLabel):
    clicked = Signal()

    def __init__(self, *a):
        super().__init__(*a)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class PreviewDialog(QDialog):
    """Vista ampliada de una foto o reproducción de un vídeo (Esc para cerrar)."""

    def __init__(self, path: Path, is_video: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(path.name)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.video = None
        if is_video:
            self.video = VideoView(self)
            lay.addWidget(self.video)
            self.video.play(path)
        else:
            view = ImageView(self)
            lay.addWidget(view)
            try:
                view.set_image(pil_to_qimage(load_image(path, 2400, 2400)))
            except Exception as e:  # noqa: BLE001
                view.set_image(None, f"No se puede mostrar:\n{e}")
        scr = self.screen().availableGeometry() if self.screen() else None
        if scr:
            self.resize(int(scr.width() * 0.7), int(scr.height() * 0.75))
        else:
            self.resize(1000, 700)

    def keyPressEvent(self, e):
        if self.video and e.key() == Qt.Key.Key_Space:
            self.video.toggle_play()
            return
        if self.video and e.key() == Qt.Key.Key_M:
            self.video.toggle_mute()
            return
        super().keyPressEvent(e)

    def done(self, r):
        if self.video:
            self.video.stop()
        super().done(r)
