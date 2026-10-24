"""Canvas rendering and mouse gestures in document and viewport coordinates."""

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .imaging import flood


class Canvas(QWidget):
    """Own gesture state; Window owns document commands and undo checkpoints.

    Document coordinates are pixels. offset/zoom map them to the viewport;
    margin is the legacy logical offset used by handle hit testing."""

    margin = 18

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.lock_cursor = self.make_lock_cursor()
        self.zoom = 1.0
        self.offset = QPointF(18, 18)
        self.pan_last = None
        self.hover_position = None
        self.square_selection = False
        self.setMouseTracking(True)
        self.start = self.last = self.end = None
        self.selection = QRect()
        self.selection_drag = None
        self.selection_pixels = self.selection_base = None
        self.shift_axis = None
        self.resizing = None
        self.preview_rect = None
        self.sync()

    @property
    def doc(self):
        return self.window.doc

    def make_lock_cursor(self):
        pixmap = QPixmap(28, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), 6))
        painter.drawRoundedRect(8, 3, 12, 17, 6, 6)
        painter.setPen(QPen(QColor("#333333"), 3))
        painter.drawRoundedRect(8, 3, 12, 17, 6, 6)
        painter.setBrush(QColor("#f4c542"))
        painter.setPen(QPen(QColor("#333333"), 2))
        painter.drawRoundedRect(4, 13, 20, 16, 2, 2)
        painter.drawLine(14, 19, 14, 24)
        painter.end()
        return QCursor(pixmap, 14, 16)

    def sync(self):
        self.setCursor(self.lock_cursor if not self.window.can_edit() else self.drawing_cursor())
        self.update()

    def drawing_cursor(self):
        return (
            Qt.CursorShape.BlankCursor
            if self.window.tool in ("brush", "eraser", "pixel") and self.hover_position is not None
            else Qt.CursorShape.CrossCursor
        )

    def enterEvent(self, event):
        self.hover_position = event.position()
        self.sync()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_position = None
        self.sync()
        super().leaveEvent(event)

    def selection_rectangle(self, point):
        bounds = QRect(QPoint(), self.doc.size)
        if self.square_selection:
            delta = point - self.start
            x_sign, y_sign = (1 if delta.x() >= 0 else -1), (1 if delta.y() >= 0 else -1)
            x_limit = bounds.right() - self.start.x() if x_sign > 0 else self.start.x()
            y_limit = bounds.bottom() - self.start.y() if y_sign > 0 else self.start.y()
            side = min(max(abs(delta.x()), abs(delta.y())), x_limit, y_limit)
            point = self.start + QPoint(x_sign * side, y_sign * side)
        return QRect(self.start, point).normalized().intersected(bounds)

    def logical_position(self, position):
        return ((position - self.offset) / self.zoom + QPointF(self.margin, self.margin)).toPoint()

    def set_zoom(self, zoom, anchor=None):
        if anchor is None:
            anchor = QPointF(self.rect().center())
        document_point = (anchor - self.offset) / self.zoom
        self.zoom = max(0.1, min(16.0, zoom))
        self.offset = anchor - document_point * self.zoom
        self.window.update_status()
        self.update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if self.start is not None:
                event.accept()
                return
            self.set_zoom(self.zoom * 1.2 ** (event.angleDelta().y() / 120), event.position())
            event.accept()
        else:
            if not self.window.width.isEnabled():
                event.ignore()
                return
            delta = event.angleDelta().y()
            if delta:
                self.window.width.setValue(self.window.width.value() + (1 if delta > 0 else -1))
                event.accept()
            else:
                super().wheelEvent(event)

    def handles(self):
        w, h, m = self.doc.size.width(), self.doc.size.height(), self.margin
        return [
            (QPoint(x + m, y + m), edge)
            for x, y, edge in [
                (0, 0, "nw"),
                (w // 2, 0, "n"),
                (w, 0, "ne"),
                (0, h // 2, "w"),
                (w, h // 2, "e"),
                (0, h, "sw"),
                (w // 2, h, "s"),
                (w, h, "se"),
            ]
        ]

    def edge_at(self, pos):
        for point, edge in self.handles():
            if QRect(point - QPoint(6, 6), QSize(13, 13)).contains(pos):
                return edge
        m = self.margin
        r = QRect(m, m, self.doc.size.width(), self.doc.size.height())
        if m <= pos.x() <= r.right() and abs(pos.y() - m) <= 4:
            return "n"
        if m <= pos.x() <= r.right() and abs(pos.y() - (m + self.doc.size.height())) <= 4:
            return "s"
        if m <= pos.y() <= r.bottom() and abs(pos.x() - m) <= 4:
            return "w"
        if m <= pos.y() <= r.bottom() and abs(pos.x() - (m + self.doc.size.width())) <= 4:
            return "e"
        return None

    def selection_handles(self):
        r = self.selection
        return [
            (QPoint(x, y), edge)
            for x, y, edge in [
                (r.left(), r.top(), "nw"),
                (r.center().x(), r.top(), "n"),
                (r.right(), r.top(), "ne"),
                (r.left(), r.center().y(), "w"),
                (r.right(), r.center().y(), "e"),
                (r.left(), r.bottom(), "sw"),
                (r.center().x(), r.bottom(), "s"),
                (r.right(), r.bottom(), "se"),
            ]
        ]

    def selection_edge(self, point):
        if self.selection.isEmpty():
            return None
        tolerance = max(1, round(6 / self.zoom))
        for handle, edge in self.selection_handles():
            if (
                abs(point.x() - handle.x()) <= tolerance
                and abs(point.y() - handle.y()) <= tolerance
            ):
                return edge
        r = self.selection
        if r.left() <= point.x() <= r.right():
            if abs(point.y() - r.top()) <= tolerance:
                return "n"
            if abs(point.y() - r.bottom()) <= tolerance:
                return "s"
        if r.top() <= point.y() <= r.bottom():
            if abs(point.x() - r.left()) <= tolerance:
                return "w"
            if abs(point.x() - r.right()) <= tolerance:
                return "e"
        return "move" if r.contains(point) else None

    def capture_selection(self):
        """Capture once per selection, not once per drag.

        Keep source pixels outside the canvas intact until deselection.
        selection_base contains the underlying layer without the original cutout."""
        if self.selection_pixels is not None:
            return
        image = self.doc.layers[self.doc.active].image
        # Keep the original pixels and the underlying layer separate across drags.
        # The rendered layer may be clipped, but this source stays intact off-canvas.
        self.selection_pixels = image.copy(self.selection)
        self.selection_base = image.copy()
        painter = QPainter(self.selection_base)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.selection, Qt.GlobalColor.transparent)
        painter.end()

    def constrained_point(self, point, modifiers):
        if not modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.shift_axis = None
            return point
        delta = point - self.start
        if self.window.tool in ("brush", "eraser", "pixel", "line"):
            if self.shift_axis is None and not delta.isNull():
                self.shift_axis = "x" if abs(delta.x()) >= abs(delta.y()) else "y"
            return (
                QPoint(point.x(), self.start.y())
                if self.shift_axis == "x"
                else QPoint(self.start.x(), point.y())
            )
        if self.window.tool in ("rect", "ellipse", "roundrect"):
            length = max(abs(delta.x()), abs(delta.y()))
            return self.start + QPoint(
                length if delta.x() >= 0 else -length, length if delta.y() >= 0 else -length
            )
        return point

    def transform_selection(self, point, modifiers=Qt.KeyboardModifier.NoModifier):
        """Recompose from the unchanged base and original selection on every drag."""
        if not self.window.can_edit():
            return
        delta = point - self.start
        r = QRect(self.selection_original)
        edge = self.selection_drag
        if edge == "move":
            r.translate(delta)
        else:
            if "w" in edge:
                r.setLeft(min(r.right(), r.left() + delta.x()))
            if "e" in edge:
                r.setRight(max(r.left(), r.right() + delta.x()))
            if "n" in edge:
                r.setTop(min(r.bottom(), r.top() + delta.y()))
            if "s" in edge:
                r.setBottom(max(r.top(), r.bottom() + delta.y()))
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                original = self.selection_original
                ratio = original.width() / original.height()
                horizontal = "w" in edge or "e" in edge
                vertical = "n" in edge or "s" in edge
                if horizontal and vertical:
                    scale = max(r.width() / original.width(), r.height() / original.height())
                    width, height = (
                        max(1, round(original.width() * scale)),
                        max(1, round(original.height() * scale)),
                    )
                elif horizontal:
                    width, height = r.width(), max(1, round(r.width() / ratio))
                else:
                    width, height = max(1, round(r.height() * ratio)), r.height()
                left = original.right() - width + 1 if "w" in edge else original.left()
                top = original.bottom() - height + 1 if "n" in edge else original.top()
                if not horizontal:
                    left = original.center().x() - (width - 1) // 2
                if not vertical:
                    top = original.center().y() - (height - 1) // 2
                r = QRect(left, top, width, height)
        image = self.selection_base.copy()
        painter = QPainter(image)
        painter.drawImage(r, self.selection_pixels)
        painter.end()
        self.doc.layers[self.doc.active].image = image
        self.selection = r

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().window())
        p.translate(self.offset - QPointF(self.margin * self.zoom, self.margin * self.zoom))
        p.scale(self.zoom, self.zoom)
        m = self.margin
        p.save()
        p.setClipRect(QRect(QPoint(m, m), self.doc.size))
        for y in range(0, self.doc.size.height(), 16):
            for x in range(0, self.doc.size.width(), 16):
                p.fillRect(
                    m + x,
                    m + y,
                    16,
                    16,
                    QColor("#dddddd" if (x // 16 + y // 16) % 2 else "#ffffff"),
                )
        p.drawImage(m, m, self.doc.composite())
        if self.start is not None and self.window.tool in ("line", "rect", "ellipse", "roundrect"):
            p.translate(m, m)
            self.draw_shape(p)
            p.translate(-m, -m)
        p.restore()
        p.setPen(QPen(QColor("#3088dd"), 1, Qt.PenStyle.DashLine))
        if not self.selection.isEmpty():
            p.drawRect(self.selection.translated(m, m))
            if self.window.tool == "select":
                radius = 3 / self.zoom
                for handle, _ in self.selection_handles():
                    center = handle + QPoint(m, m)
                    p.fillRect(
                        int(center.x() - radius),
                        int(center.y() - radius),
                        max(2, round(radius * 2)),
                        max(2, round(radius * 2)),
                        QColor("#3088dd"),
                    )
        if self.preview_rect is not None:
            p.drawRect(self.preview_rect.translated(m, m))
        p.setPen(QColor("#555555"))
        for point, _ in self.handles():
            p.fillRect(QRect(point - QPoint(3, 3), QSize(7, 7)), QColor("#ffffff"))
            p.drawRect(QRect(point - QPoint(3, 3), QSize(7, 7)))
        if (
            self.hover_position is not None
            and self.window.can_edit()
            and self.window.tool in ("brush", "eraser", "pixel")
            and self.pan_last is None
        ):
            p.resetTransform()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            center = self.hover_position
            if self.start is not None and self.last is not None and not self.resizing:
                center = self.offset + QPointF(self.last) * self.zoom
            radius = max(0.5, self.window.width.value() * self.zoom / 2)
            for color, thickness in [("white", 3), ("black", 1)]:
                p.setPen(QPen(QColor(color), thickness))
                if self.window.tool == "pixel":
                    p.drawRect(
                        QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
                    )
                else:
                    p.drawEllipse(center, radius, radius)

    def draw_shape(self, p):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(
            QPen(
                self.window.color,
                self.window.width.value(),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        r = QRect(self.start, self.end).normalized()
        tool = self.window.tool
        if tool == "line":
            p.drawLine(self.start, self.end)
        elif tool == "ellipse":
            p.drawEllipse(r)
        elif tool == "roundrect":
            p.drawRoundedRect(r, 12, 12)
        else:
            p.drawRect(r)

    def stroke(self, a, b):
        """Pixel uses integer square stamps; brush/eraser retain Qt antialiasing."""
        if not self.window.can_edit():
            return
        p = QPainter(self.doc.layers[self.doc.active].image)
        if self.window.tool == "pixel":
            # Integer Bresenham path with square stamps: no fractional coverage.
            x, y, target_x, target_y = a.x(), a.y(), b.x(), b.y()
            dx, dy = abs(target_x - x), -abs(target_y - y)
            sx, sy = (1 if x < target_x else -1), (1 if y < target_y else -1)
            error = dx + dy
            width = self.window.width.value()
            while True:
                p.fillRect(x - width // 2, y - width // 2, width, width, self.window.color)
                if x == target_x and y == target_y:
                    break
                doubled = error * 2
                if doubled >= dy:
                    error += dy
                    x += sx
                if doubled <= dx:
                    error += dx
                    y += sy
            p.end()
            return
        if self.window.tool == "eraser":
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(
            QPen(
                self.window.color,
                self.window.width.value(),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        if a == b:
            p.drawPoint(a)
        else:
            p.drawLine(a, b)
        p.end()

    def mousePressEvent(self, event):
        self.hover_position = event.position()
        if event.button() == Qt.MouseButton.MiddleButton:
            if self.start is None:
                self.pan_last = event.position()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if self.pan_last is not None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = self.logical_position(event.position())
        point = pos - QPoint(self.margin, self.margin)
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            if self.doc.composite().rect().contains(point):
                self.window.set_color(self.doc.composite().pixelColor(point))
            return
        if not self.window.can_edit():
            self.setCursor(self.lock_cursor)
            return
        selection_edge = self.selection_edge(point) if self.window.tool == "select" else None
        if selection_edge:
            self.window.checkpoint()
            self.start = self.last = self.end = point
            self.selection_drag = selection_edge
            self.selection_original = QRect(self.selection)
            self.capture_selection()
            return
        if self.window.tool == "select" and not self.selection.isEmpty():
            self.window.deselect()
            return
        edge = self.edge_at(pos)
        if edge:
            self.resizing = edge
            self.start = pos - QPoint(self.margin, self.margin)
            self.preview_rect = QRect(QPoint(0, 0), self.doc.size)
            return
        point = pos - QPoint(self.margin, self.margin)
        if not QRect(QPoint(0, 0), self.doc.size).contains(point):
            return
        tool = self.window.tool
        if tool == "picker":
            self.window.set_color(self.doc.composite().pixelColor(point))
            return
        self.start = self.last = self.end = point
        if tool == "select":
            self.square_selection = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.window.deselect()
        else:
            self.window.checkpoint()
            if tool in ("brush", "eraser", "pixel"):
                self.stroke(point, point)
            elif tool == "fill":
                flood(self.doc.layers[self.doc.active].image, point, self.window.color)
        self.update()

    def resize_preview(self, point, modifiers):
        """Compute new bounds without modifying pixels until mouse release."""
        w, h = self.doc.size.width(), self.doc.size.height()
        delta = point - self.start
        edge = self.resizing
        left = min(w - 1, delta.x()) if "w" in edge else 0
        top = min(h - 1, delta.y()) if "n" in edge else 0
        right = max(left + 1, w + delta.x()) if "e" in edge else w
        bottom = max(top + 1, h + delta.y()) if "s" in edge else h
        rect = QRect(left, top, right - left, bottom - top)
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            horizontal = "w" in edge or "e" in edge
            vertical = "n" in edge or "s" in edge
            if horizontal and vertical:
                scale = max(rect.width() / w, rect.height() / h)
                width, height = max(1, round(w * scale)), max(1, round(h * scale))
            elif horizontal:
                width, height = rect.width(), max(1, round(rect.width() * h / w))
            else:
                width, height = max(1, round(rect.height() * w / h)), rect.height()
            left = w - width if "w" in edge else 0
            top = h - height if "n" in edge else 0
            if not horizontal:
                left = (w - width) // 2
            if not vertical:
                top = (h - height) // 2
            rect = QRect(left, top, width, height)
        return rect

    def mouseMoveEvent(self, event):
        self.hover_position = event.position()
        self.update()
        if self.pan_last is not None:
            self.offset += event.position() - self.pan_last
            self.pan_last = event.position()
            self.update()
            return
        pos = self.logical_position(event.position())
        point = pos - QPoint(self.margin, self.margin)
        if not self.window.can_edit():
            self.setCursor(self.lock_cursor)
            return
        if self.start is None:
            edge = (
                self.selection_edge(point) if self.window.tool == "select" else None
            ) or self.edge_at(pos)
            cursor = {
                "n": Qt.CursorShape.SizeVerCursor,
                "s": Qt.CursorShape.SizeVerCursor,
                "e": Qt.CursorShape.SizeHorCursor,
                "w": Qt.CursorShape.SizeHorCursor,
                "nw": Qt.CursorShape.SizeFDiagCursor,
                "se": Qt.CursorShape.SizeFDiagCursor,
                "ne": Qt.CursorShape.SizeBDiagCursor,
                "sw": Qt.CursorShape.SizeBDiagCursor,
            }
            self.setCursor(
                Qt.CursorShape.SizeAllCursor
                if edge == "move"
                else cursor.get(edge, self.drawing_cursor())
            )
            return
        if not self.selection_drag and not self.resizing:
            point = self.constrained_point(point, event.modifiers())
        self.end = point
        if self.selection_drag:
            self.transform_selection(point, event.modifiers())
        elif self.resizing:
            self.preview_rect = self.resize_preview(point, event.modifiers())
        elif self.window.tool in ("brush", "eraser", "pixel"):
            self.stroke(self.last, point)
        elif self.window.tool == "select":
            self.selection = self.selection_rectangle(point)
        self.last = point
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_last = None
            self.sync()
            return
        if event.button() != Qt.MouseButton.LeftButton or self.start is None:
            return
        if not self.window.can_edit():
            self.start = self.last = self.end = self.resizing = self.preview_rect = None
            self.window.deselect()
            self.sync()
            return
        if self.selection_drag:
            point = self.logical_position(event.position()) - QPoint(self.margin, self.margin)
            self.transform_selection(point, event.modifiers())
            self.selection_drag = None
        elif self.resizing:
            point = self.logical_position(event.position()) - QPoint(self.margin, self.margin)
            r = self.resize_preview(point, event.modifiers())
            self.window.checkpoint()
            self.doc.resize(r.width(), r.height(), -r.x(), -r.y())
            self.offset += QPointF(r.x() * self.zoom, r.y() * self.zoom)
            self.window.deselect()
        elif self.window.tool in ("line", "rect", "ellipse", "roundrect"):
            self.end = self.constrained_point(
                self.logical_position(event.position()) - QPoint(self.margin, self.margin),
                event.modifiers(),
            )
            p = QPainter(self.doc.layers[self.doc.active].image)
            self.draw_shape(p)
            p.end()
        elif self.window.tool in ("brush", "eraser", "pixel"):
            point = self.constrained_point(
                self.logical_position(event.position()) - QPoint(self.margin, self.margin),
                event.modifiers(),
            )
            self.stroke(self.last, point)
        elif self.window.tool == "select":
            point = self.logical_position(event.position()) - QPoint(self.margin, self.margin)
            self.selection = self.selection_rectangle(point)
        self.shift_axis = None
        self.start = self.end = self.last = self.resizing = self.preview_rect = None
        self.window.refresh()
