"""Compare a saved pre-refactor app.py with the current implementation.

Run on the same machine/theme to compare pixels rather than platform-dependent
reference hashes. This intentionally takes an external legacy file so obsolete
application code does not become a second implementation in the repository.
"""
# ruff: noqa: E402 -- Qt platform and repository path must be set before imports.

import argparse
import ast
import importlib.util
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":"):
    os.environ.setdefault("QT_QPA_PLATFORMTHEME", "kde")

# Allow running the script directly from the repository without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from faint import app as current
from faint import canvas, document, imaging
from faint.widgets import layers, palette


def normalized(node):
    class Normalize(ast.NodeTransformer):
        def visit_Name(self, value):
            if value.id == "l":
                value.id = "layer"
            return value

        def visit_ClassDef(self, value):
            return self.strip_doc(value)

        def visit_FunctionDef(self, value):
            return self.strip_doc(value)

        def strip_doc(self, value):
            if (
                value.body
                and isinstance(value.body[0], ast.Expr)
                and isinstance(value.body[0].value, ast.Constant)
                and isinstance(value.body[0].value.value, str)
            ):
                value.body = value.body[1:]
            return self.generic_visit(value)

    return ast.dump(Normalize().visit(node), include_attributes=False)


def check_algorithms(reference):
    before = {
        node.name: node
        for node in ast.parse(reference.read_text()).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    checked = []
    for module, names in [
        (imaging, ("blank", "flood")),
        (document, ("Layer", "Document")),
        (canvas, ("Canvas",)),
        (layers, ("TrashButton", "EyeButton", "LayerPreview", "LayerList", "LayerDock")),
        (palette, ("paint_swatch", "CurrentColorButton", "SwatchDelegate")),
    ]:
        after = {
            node.name: node
            for node in ast.parse(Path(module.__file__).read_text()).body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        }
        for name in names:
            assert normalized(before[name]) == normalized(after[name]), f"Algorithm changed: {name}"
            checked.append(name)
    print(f"Unchanged syntax trees: {len(checked)} core functions/classes")


def capture(window):
    window.show()
    window.activateWindow()
    QApplication.processEvents()
    # Let style focus/enable animations settle before comparing stable pixels.
    QTest.qWait(300)
    return window.grab().toImage()


class MemoryClipboard:
    """Capture offered MIME data without changing the desktop clipboard.

    Keeping legacy QMimeData out of Qt's process-global clipboard also avoids
    the distro Shiboken shutdown bug when two implementations share a process.
    """

    def __init__(self):
        self.mime = None

    def setMimeData(self, mime):
        self.mime = mime

    def image(self):
        return self.mime.imageData() if self.mime is not None else QImage()


def exercise(module, directory):
    window = module.Window()
    images = {"initial": capture(window)}
    canvas = window.canvas
    for tool in window.tool_actions:
        window.set_tool(tool)
        images["tool-" + tool] = capture(window)
    window.set_tool("pixel")
    window.width.setValue(3)
    window.set_color(QColor("#fa314e"))
    canvas.stroke(QPoint(20, 20), QPoint(110, 65))
    window.add_layer()
    window.set_tool("brush")
    window.width.setValue(18)
    window.set_color(QColor("#803399ee"))
    canvas.stroke(QPoint(70, 35), QPoint(150, 100))
    window.swatches.append("#8055ee33")
    window.refresh_palette()
    window.refresh()
    images["painted-layers"] = capture(window)
    window.set_tool("select")
    canvas.selection = QRect(60, 30, 65, 50)
    canvas.capture_selection()
    for endpoint in (QPoint(-20, 20), QPoint(160, 100)):
        canvas.selection_original = QRect(canvas.selection)
        canvas.selection_drag = "move"
        canvas.start = canvas.selection.center()
        canvas.transform_selection(endpoint)
        canvas.selection_drag = canvas.start = None
    images["selection-moved"] = capture(window)
    window.copy()
    clipboard = QApplication.clipboard().image().copy()
    canvas.zoom = 1.3
    canvas.offset = QPointF(35, 28)
    window.refresh()
    images["zoomed"] = capture(window)
    window.toggle_layer(window.doc.active)
    images["hidden-layer"] = capture(window)
    window.toggle_background()
    images["white-background"] = capture(window)
    archives = {}
    for suffix in ("faint", "png", "jpg"):
        window.path = str(directory / ("drawing." + suffix))
        assert window.save()
        if suffix == "faint":
            with zipfile.ZipFile(window.path) as archive:
                archives[suffix] = {name: archive.read(name) for name in archive.namelist()}
        else:
            archives[suffix] = Path(window.path).read_bytes()
    window.dirty = False
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
    return images, clipboard, archives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reference", type=Path, help="Pre-refactor app.py saved outside this repository"
    )
    args = parser.parse_args()
    check_algorithms(args.reference)
    spec = importlib.util.spec_from_file_location("_faint_before_refactor", args.reference)
    legacy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = legacy
    spec.loader.exec_module(legacy)
    global application
    application = QApplication.instance() or QApplication([])
    app = application
    app.setApplicationName("Faint")
    app.setCursorFlashTime(0)
    with (
        patch.object(QApplication, "clipboard", return_value=MemoryClipboard()),
        tempfile.TemporaryDirectory() as directory,
    ):
        root = Path(directory)
        (root / "before").mkdir()
        (root / "after").mkdir()
        before, clipboard_before, files_before = exercise(legacy, root / "before")
        after, clipboard_after, files_after = exercise(current, root / "after")
        for scene in before:
            if before[scene] != after[scene]:
                before[scene].save("/tmp/faint-parity-before.png")
                after[scene].save("/tmp/faint-parity-after.png")
                raise AssertionError(f"Pixel mismatch: {scene}")
        assert clipboard_before == clipboard_after, "Clipboard pixels changed"
        assert files_before == files_after, "Saved archive/image data changed"
    print(f"Identical screenshots: {len(before)} scenes")
    print("Identical selection clipboard and .faint/PNG/JPEG payloads")


if __name__ == "__main__":
    main()
