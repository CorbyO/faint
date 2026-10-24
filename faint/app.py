"""Public entry point. Desktop setup happens before QApplication is constructed."""

import argparse
import json
import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog

from .canvas import Canvas
from .dialogs import CanvasSizeDialog

# Keep the original imports available for callers of faint.app.
from .document import Document, Layer
from .imaging import blank, flood
from .window import Window

__all__ = [
    "Canvas",
    "CanvasSizeDialog",
    "Document",
    "Layer",
    "Window",
    "blank",
    "flood",
    "QFileDialog",
    "QInputDialog",
    "main",
]


def main():
    # Bundled Qt may fall back to Fusion instead of detecting the KDE theme.
    # Select KDE explicitly while preserving an intentional user override.
    if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":"):
        os.environ.setdefault("QT_QPA_PLATFORMTHEME", "kde")
    if "__compiled__" in globals():
        from faint.qt_compat import install_compiled_signal_bridge

        install_compiled_signal_bridge()
    app = QApplication(sys.argv)
    app.setApplicationName("Faint")
    app.setDesktopFileName("io.github.faint")
    # The checkout and Nuitka bundle share this asset layout. Wheels install
    # their copy in the interpreter's shared data directory instead.
    icon_path = Path(__file__).resolve().parent.parent / "assets" / "faint.svg"
    if not icon_path.is_file():
        icon_path = Path(sys.prefix) / "share" / "faint" / "faint.svg"
    app.setWindowIcon(QIcon(str(icon_path)))
    parser = argparse.ArgumentParser(description="Faint paint editor")
    parser.add_argument("files", nargs="*", help="PNG, JPEG, WebP, BMP, GIF or .faint files to open")
    parser.add_argument("--check-theme", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--theme-screenshot", help=argparse.SUPPRESS)
    options = parser.parse_args(app.arguments()[1:])
    # Keep a reference to every window when a file manager passes several files.
    windows = []
    for path in options.files or [None]:
        window = Window()
        if path is not None:
            window.open_path(path)
        window.show()
        windows.append(window)
    window = windows[0]
    # Build/regression diagnostic: create the real window, report its effective
    # theme, optionally capture it, then exit without entering the event loop.
    if "--check-theme" in sys.argv:
        from PySide6.QtCore import qVersion

        app.processEvents()
        if "--theme-screenshot" in sys.argv:
            index = sys.argv.index("--theme-screenshot")
            window.grab().save(sys.argv[index + 1])
        print(
            json.dumps(
                {
                    "qt": qVersion(),
                    "icon_loaded": not app.windowIcon().isNull(),
                    "language": window._i18n.language,
                    "style": app.style().objectName(),
                    "platform_theme": os.environ.get("QT_QPA_PLATFORMTHEME"),
                    "window": app.palette().window().color().name(),
                    "text": app.palette().windowText().color().name(),
                    "font": app.font().toString(),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        window.close()
        return
    sys.exit(app.exec())
