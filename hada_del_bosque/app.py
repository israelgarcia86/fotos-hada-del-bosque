"""Punto de entrada de la aplicación."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_ID, APP_NAME, RESOURCES, VERSION


def selftest(out: str | None) -> int:
    """Comprobación rápida de que todas las piezas están incluidas (la usa GitHub al crear el .exe)."""
    lines = []
    ok = True
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([sys.argv[0]])
        import io

        from PIL import Image

        from . import dates, media  # noqa: F401
        from .main_window import MainWindow  # noqa: F401
        from .widgets import VideoView

        lines.append(f"{APP_NAME} {VERSION}")
        buf = io.BytesIO()
        Image.new("RGB", (64, 48), (10, 120, 40)).save(buf, format="HEIF")
        buf.seek(0)
        lines.append(f"HEIC: {Image.open(buf).size}")
        import rawpy  # noqa: F401
        lines.append("RAW: rawpy OK")
        from hachoir.parser import createParser  # noqa: F401
        from hachoir.metadata import extractMetadata  # noqa: F401
        lines.append("hachoir OK")
        v = VideoView()
        lines.append(f"Vídeo: {'OK' if v.available else 'NO DISPONIBLE'}")
        ok = ok and v.available
        lines.append("Icono: " + ("OK" if (RESOURCES / "hada.png").exists() else "FALTA"))
        ok = ok and (RESOURCES / "hada.png").exists()
        del app
    except Exception:  # noqa: BLE001
        ok = False
        lines.append(traceback.format_exc())
    lines.append("OK" if ok else "FALLO")
    text = "\n".join(lines)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv:
        i = argv.index("--selftest")
        return selftest(argv[i + 1] if len(argv) > i + 1 else None)

    if sys.platform == "win32":  # icono propio en la barra de tareas de Windows
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setWindowIcon(QIcon(str(RESOURCES / "hada.png")))
    from .dialogs import WelcomeDialog, run_scan
    from .main_window import STYLE, MainWindow
    from .store import Store

    app.setStyleSheet(STYLE)
    settings = QSettings(APP_ID, APP_ID)
    windows: list = []

    def open_folder(initial: str | None = None) -> bool:
        root = initial
        if not root:
            dlg = WelcomeDialog(settings.value("last_folder", "", str) or None)
            if not dlg.exec() or not dlg.chosen:
                return False
            root = dlg.chosen
        rootp = Path(root).resolve()
        try:
            store, is_new = Store.open(rootp)
            if is_new:
                store.save()  # comprueba que se puede escribir en la carpeta
        except PermissionError:
            QMessageBox.critical(None, APP_NAME, f"No se puede escribir en la carpeta:\n{rootp}\n\n"
                                 "El programa necesita guardar ahí su fichero de progreso.")
            return False
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(None, APP_NAME, f"No se pudo abrir el fichero de progreso:\n{e}")
            return False
        settings.setValue("last_folder", str(rootp))
        if not run_scan(store):
            if is_new and not store.items:
                return False
        win = MainWindow(store, is_new)

        def other():
            if open_folder():
                win.close()

        win.open_other.connect(other)
        windows.append(win)
        win.show()
        QTimer.singleShot(50, win.begin)
        return True

    initial = next((a for a in argv[1:] if not a.startswith("-") and Path(a).is_dir()), None)
    if not open_folder(initial):
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
