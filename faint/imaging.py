"""Low-level raster operations shared by the document and drawing tools."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


def blank(w, h):
    image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    return image


def flood(image, point, color):
    x, y = point.x(), point.y()
    if not image.rect().contains(point):
        return
    # Work in straight alpha so exact comparisons also work for translucent colors.
    work = image.convertToFormat(QImage.Format.Format_ARGB32)
    old, new = work.pixel(x, y), color.rgba()
    if old == new:
        return
    stack = [(x, y)]
    w, h = work.width(), work.height()
    while stack:
        x, y = stack.pop()
        if work.pixel(x, y) != old:
            continue
        left = x
        while left > 0 and work.pixel(left - 1, y) == old:
            left -= 1
        above = below = False
        while left < w and work.pixel(left, y) == old:
            work.setPixel(left, y, new)
            if y > 0:
                match = work.pixel(left, y - 1) == old
                if match and not above:
                    stack.append((left, y - 1))
                above = match
            if y + 1 < h:
                match = work.pixel(left, y + 1) == old
                if match and not below:
                    stack.append((left, y + 1))
                below = match
            left += 1
    image.swap(work)
