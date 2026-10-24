"""Layered image state, independent of window widgets and file dialogs."""

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter

from .imaging import blank


@dataclass
class Layer:
    """One full-canvas image. Names are retained for project-file compatibility."""

    name: str
    image: QImage
    visible: bool = True


class Document:
    """Layers are stored bottom to top; the fixed background is separate.

    active is -1 only when no paint layers remain."""

    def __init__(self, w=800, h=600):
        self.size = QSize(w, h)
        self.layers = [Layer("레이어 1", blank(w, h))]
        self.active = 0
        self.background_white = False

    def snapshot(self):
        """Copy image data so later strokes cannot mutate undo history."""
        return (
            QSize(self.size),
            [Layer(layer.name, layer.image.copy(), layer.visible) for layer in self.layers],
            self.active,
            self.background_white,
        )

    def restore(self, state):
        self.size, self.layers, self.active, self.background_white = state

    def composite(self):
        result = blank(self.size.width(), self.size.height())
        if self.background_white:
            result.fill(Qt.GlobalColor.white)
        p = QPainter(result)
        for layer in self.layers:
            if layer.visible:
                p.drawImage(0, 0, layer.image)
        p.end()
        return result

    def resize(self, w, h, dx=0, dy=0):
        """Change canvas bounds without scaling pixels; dx/dy place existing content."""
        w, h = max(1, w), max(1, h)
        for layer in self.layers:
            image = blank(w, h)
            p = QPainter(image)
            p.drawImage(dx, dy, layer.image)
            p.end()
            layer.image = image
        self.size = QSize(w, h)

    def paste(self, image):
        """Insert above the active layer, expanding only to the right and bottom."""
        self.resize(max(self.size.width(), image.width()), max(self.size.height(), image.height()))
        target = blank(self.size.width(), self.size.height())
        p = QPainter(target)
        p.drawImage(0, 0, image)
        p.end()
        self.active += 1
        self.layers.insert(self.active, Layer("붙여넣은 이미지", target))
