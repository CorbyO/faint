"""Layer thumbnails, visibility controls, deletion, and the drag lifecycle."""

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QDrag, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractItemView, QDockWidget, QListWidget, QPushButton, QWidget


class TrashButton(QPushButton):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(28, 26)
        self.setToolTip("LAYER.DELETE")
        self.setAccessibleName("LAYER.DELETE")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())
        painter.setPen(QPen(self.palette().text().color(), 1.8))
        painter.drawLine(5, 7, 23, 7)
        painter.drawRect(11, 3, 6, 4)
        painter.drawRoundedRect(8, 8, 12, 15, 2, 2)
        painter.drawLine(12, 11, 12, 20)
        painter.drawLine(16, 11, 16, 20)
        painter.end()


class EyeButton(QPushButton):
    def __init__(self, visible, parent):
        super().__init__(parent)
        self.visible_layer = visible
        self.setFixedSize(28, 26)
        self.setToolTip("LAYER.HIDE" if visible else "LAYER.SHOW")
        self.setAccessibleName(self.toolTip())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())
        painter.setPen(QPen(self.palette().text().color(), 1.8))
        path = QPainterPath(QPointF(3, 13))
        if self.visible_layer:
            path.quadTo(14, 1, 25, 13)
            path.quadTo(14, 25, 3, 13)
            painter.drawPath(path)
            painter.setBrush(self.palette().text())
            painter.drawEllipse(QPointF(14, 13), 3, 3)
        else:
            path.quadTo(14, 24, 25, 13)
            painter.drawPath(path)
            for x, y in [(7, 16), (14, 18), (21, 16)]:
                painter.drawLine(x, y, x, y + 4)
        painter.end()


class LayerPreview(QWidget):
    def __init__(
        self, image, visible, callback, background=False, parent=None, delete_callback=None
    ):
        super().__init__(parent)
        self.background = background
        self.image = image.scaled(
            160, 76, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        if background:
            self.toggle = QPushButton(
                "BACKGROUND.WHITE" if visible else "BACKGROUND.TRANSPARENT", self
            )
            self.toggle.setFixedSize(52, 26)
            self.toggle.setToolTip("BACKGROUND.TOGGLE_HINT")
        else:
            self.toggle = EyeButton(visible, self)
        self.toggle.clicked.connect(callback)
        self.delete_button = None
        if delete_callback is not None:
            self.delete_button = TrashButton(self)
            self.delete_button.clicked.connect(delete_callback)

    def update_translation_layout(self):
        # Preserve the Korean control size, but let longer translations fit.
        if self.background:
            self.toggle.setFixedWidth(
                max(52, self.toggle.fontMetrics().horizontalAdvance(self.toggle.text()) + 18)
            )
        self.toggle.move(self.width() - self.toggle.width() - 4, 3)
        if self.delete_button is not None:
            self.delete_button.move(
                self.width() - self.delete_button.width() - 4,
                self.height() - self.delete_button.height() - 3,
            )

    def resizeEvent(self, event):
        self.update_translation_layout()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRect(QPoint(), self.image.size())
        rect.moveCenter(self.rect().center())
        painter.save()
        painter.setClipRect(rect)
        for y in range(rect.top(), rect.bottom() + 1, 8):
            for x in range(rect.left(), rect.right() + 1, 8):
                painter.fillRect(
                    x,
                    y,
                    8,
                    8,
                    QColor(
                        "#dddddd"
                        if ((x - rect.left()) // 8 + (y - rect.top()) // 8) % 2
                        else "#ffffff"
                    ),
                )
        painter.drawImage(rect.topLeft(), self.image)
        painter.restore()
        painter.setPen(QColor("#888888"))
        painter.drawRect(rect)
        painter.end()


class LayerList(QListWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setMinimumWidth(210)

    def mousePressEvent(self, event):
        self.drag_row = self.indexAt(event.position().toPoint()).row()
        super().mousePressEvent(event)

    def startDrag(self, actions):
        """Own the drag to prevent Qt from deleting the source after a custom drop."""
        if (
            0 <= getattr(self, "drag_row", -1) < len(self.window.doc.layers)
            and self.currentRow() == self.drag_row
        ):
            # Own the drag lifecycle: QAbstractItemView.startDrag would remove the
            # source row again after our drop handler has rebuilt the layer list.
            item = self.currentItem()
            drag = QDrag(self)
            drag.setMimeData(self.mimeData([item]))
            preview = self.itemWidget(item)
            if preview is not None:
                drag.setPixmap(preview.grab())
            drag.exec(Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        source = self.currentRow()
        target = self.indexAt(event.position().toPoint()).row()
        if target < 0:
            target = len(self.window.doc.layers)
        elif event.position().y() > self.visualItemRect(self.item(target)).center().y():
            target += 1
        self.window.reorder_layer(source, target)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class LayerDock(QDockWidget):
    def closeEvent(self, event):
        event.ignore()
