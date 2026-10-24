"""Palette rendering. Selection borders never replace the displayed color."""

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton, QStyle, QStyledItemDelegate


def paint_swatch(painter, rect, color, radius=5):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    painter.setClipPath(path)
    for y in range(rect.top(), rect.bottom() + 1, 6):
        for x in range(rect.left(), rect.right() + 1, 6):
            painter.fillRect(
                x,
                y,
                6,
                6,
                QColor(
                    "#dddddd" if ((x - rect.left()) // 6 + (y - rect.top()) // 6) % 2 else "#ffffff"
                ),
            )
    painter.fillRect(rect, color)
    painter.restore()


class CurrentColorButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor("#202020")
        self.setFixedSize(42, 42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("COLOR.CHANGE")

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect().adjusted(5, 5, -5, -5)
        paint_swatch(painter, rect, self.color, 7)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.palette().mid().color(), 1))
        painter.drawRoundedRect(QRectF(rect), 7, 7)
        painter.end()


class SwatchDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        color = QColor(index.data(Qt.ItemDataRole.UserRole))
        side = max(1, min(option.rect.width(), option.rect.height()) - 10)
        rect = QRect(QPoint(), QSize(side, side))
        rect.moveCenter(option.rect.center())
        paint_swatch(painter, rect, color)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(option.palette.mid().color(), 0.7))
        painter.drawRoundedRect(QRectF(rect), 5, 5)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QPen(option.palette.highlight().color(), 2))
            painter.drawRoundedRect(QRectF(rect.adjusted(-3, -3, 3, 3)), 7, 7)
        painter.restore()
