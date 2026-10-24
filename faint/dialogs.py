"""Canvas size inputs and linked dimension controls."""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from .i18n import localize_tree


class CanvasSizeDialog(QDialog):
    def __init__(self, size, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DIALOG.CANVAS_SIZE")
        self.ratio = size.width() / size.height()
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.width_input = QSpinBox()
        self.height_input = QSpinBox()
        for spin, value in ((self.width_input, size.width()), (self.height_input, size.height())):
            spin.setRange(1, max(32768, value))
            spin.setValue(value)
            spin.setSuffix(" px")
        self.aspect_lock = QCheckBox("DIALOG.LOCK_ASPECT_RATIO")
        form.addRow("COMMON.WIDTH", self.width_input)
        form.addRow("COMMON.HEIGHT", self.height_input)
        form.addRow(self.aspect_lock)
        layout.addLayout(form)
        layout.addWidget(QLabel("DIALOG.CANVAS_SIZE_DESCRIPTION"))
        self.width_input.valueChanged.connect(lambda: self.link_dimension(True))
        self.height_input.valueChanged.connect(lambda: self.link_dimension(False))
        self.aspect_lock.toggled.connect(self.lock_changed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        localize_tree(self)

    def lock_changed(self, locked):
        # Lock the dimensions currently shown, rather than the original canvas
        # ratio: users may edit both dimensions before enabling the lock.
        if locked:
            self.ratio = self.width_input.value() / self.height_input.value()

    def link_dimension(self, width_changed):
        if not self.aspect_lock.isChecked():
            return
        source = self.width_input if width_changed else self.height_input
        target = self.height_input if width_changed else self.width_input
        factor = 1 / self.ratio if width_changed else self.ratio
        desired = round(source.value() * factor)
        value = max(target.minimum(), min(target.maximum(), desired))
        target.blockSignals(True)
        target.setValue(value)
        target.blockSignals(False)
        if value != desired:
            source.blockSignals(True)
            source.setValue(round(value / factor))
            source.blockSignals(False)

    def canvas_size(self):
        return QSize(self.width_input.value(), self.height_input.value())
