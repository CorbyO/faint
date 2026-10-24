"""Application commands and coordination of document, canvas, and UI widgets."""

import json
from pathlib import Path

from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QEvent,
    QIODevice,
    QMimeData,
    QPoint,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import QAction, QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QFileDialog,
    QInputDialog,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
)

from .canvas import Canvas
from .dialogs import CanvasSizeDialog
from .document import Document, Layer
from .i18n import localize_tree, manager, tr
from .imaging import blank
from .storage import RASTER_FORMATS, load_document, save_document
from .tools import DEFAULT_TOOL_WIDTHS, TOOL_BY_KEY
from .ui import build_window_ui
from .widgets.layers import LayerPreview


class Window(QMainWindow):
    """Coordinate UI commands without embedding widget painting or serialization."""

    def __init__(self):
        super().__init__()
        self.doc = Document()
        self._i18n = manager()
        self.setAcceptDrops(True)
        self.path = None
        self.dirty = False
        self.undo_stack, self.redo_stack = [], []
        self.tool = "brush"
        self.tool_widths = dict(DEFAULT_TOOL_WIDTHS)
        self.color = QColor("#202020")
        self.swatches = [
            "#202020",
            "#ffffff",
            "#ef4444",
            "#f59e0b",
            "#facc15",
            "#22c55e",
            "#06b6d4",
            "#3b82f6",
            "#8b5cf6",
            "#ec4899",
        ]
        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self.resize(1100, 800)
        self.build_ui()
        self.refresh()
        self._i18n.languageChanged.connect(self.retranslate)
        QApplication.instance().installEventFilter(self)

    @staticmethod
    def dropped_image_paths(mime):
        return [
            url.toLocalFile()
            for url in mime.urls()
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in RASTER_FORMATS
        ]

    def dragEnterEvent(self, event):
        if self.dropped_image_paths(event.mimeData()):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        paths = self.dropped_image_paths(event.mimeData())
        images = [(path, QImage(path)) for path in paths]
        valid = [(path, image) for path, image in images if not image.isNull()]
        if not valid:
            event.ignore()
            return
        self.deselect()
        self.checkpoint()
        for path, image in valid:
            self.doc.paste(image)
        self.refresh()
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        failed = [Path(path).name for path, image in images if image.isNull()]
        if failed:
            QMessageBox.warning(self, tr("ERROR.IMPORT_IMAGE"), "\n".join(failed))

    def eventFilter(self, watched, event):
        if (
            self.isActiveWindow()
            and QApplication.activeModalWidget() is None
            and event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress)
        ):
            control = event.modifiers() & Qt.KeyboardModifier.ControlModifier
            callbacks = {
                Qt.Key.Key_Z: self.undo,
                Qt.Key.Key_Y: self.redo,
                Qt.Key.Key_E: self.resize_canvas_dialog,
            }
            callback = callbacks.get(event.key()) if control else None
            if event.key() == Qt.Key.Key_Delete and not self.canvas.selection.isEmpty():
                callback = self.clear_selection
            if control and event.key() == Qt.Key.Key_C and not self.canvas.selection.isEmpty():
                callback = (
                    self.copy_merged
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                    else self.copy
                )
            if control and event.key() == Qt.Key.Key_V and self.clipboard_image() is not None:
                callback = self.paste
            if callback:
                event.accept()
                if event.type() == QEvent.Type.KeyPress:
                    if (
                        event.key() == Qt.Key.Key_Z
                        and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                    ):
                        self.redo()
                    else:
                        callback()
                return True
        return super().eventFilter(watched, event)

    def action(self, menu, label, callback, shortcut=None):
        action = QAction(label, self)
        action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
        menu.addAction(action)
        return action

    def build_ui(self):
        build_window_ui(self)

    def set_tool(self, tool):
        if tool != self.tool:
            self.deselect()
        self.tool = tool
        self.width.blockSignals(True)
        self.width.setEnabled(tool in self.tool_widths)
        if tool in self.tool_widths:
            self.width.setValue(self.tool_widths[tool])
        self.width.blockSignals(False)
        self.update_status()
        self.canvas.sync()
        for key, action in self.tool_actions.items():
            action.setChecked(key == tool)

    def width_changed(self, value):
        if self.tool in self.tool_widths:
            self.tool_widths[self.tool] = value
        self.canvas.update()

    def set_color(self, color):
        self.color = QColor(color)
        if hasattr(self, "color_button"):
            self.color_button.color = QColor(color)
            self.color_button.setToolTip(
                tr("COLOR.CURRENT_HINT", color=color.name(QColor.NameFormat.HexArgb))
            )
            self.color_button.update()

    def choose_color(self):
        color = QColorDialog.getColor(
            self.color,
            self,
            tr("DIALOG.CHOOSE_COLOR"),
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self.set_color(color)

    def checkpoint(self):
        """Start one undoable edit; redo becomes invalid after any new edit."""
        self.undo_stack.append(self.doc.snapshot())
        # Full-image snapshots deliberately trade memory for exact undo, including
        # pixels removed by canvas cropping. Keep the existing 30-edit limit.
        self.undo_stack = self.undo_stack[-30:]
        self.redo_stack.clear()
        self.dirty = True

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.doc.snapshot())
            self.doc.restore(self.undo_stack.pop())
            self.dirty = True
            self.deselect()
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.doc.snapshot())
            self.doc.restore(self.redo_stack.pop())
            self.dirty = True
            self.deselect()
            self.refresh()

    def refresh(self):
        """Rebuild layer previews with signals blocked to avoid accidental edits."""
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for index in reversed(range(len(self.doc.layers))):
            layer = self.doc.layers[index]
            item = QListWidgetItem()
            item.setSizeHint(QSize(180, 92))
            self.layer_list.addItem(item)
            preview = LayerPreview(
                layer.image,
                layer.visible,
                lambda checked=False, i=index: self.toggle_layer(i),
                delete_callback=lambda checked=False, i=index: self.delete_layer(i),
            )
            self.layer_list.setItemWidget(item, preview)
        thumbnail_size = self.doc.size.scaled(160, 76, Qt.AspectRatioMode.KeepAspectRatio)
        background = blank(max(1, thumbnail_size.width()), max(1, thumbnail_size.height()))
        if self.doc.background_white:
            background.fill(Qt.GlobalColor.white)
        item = QListWidgetItem()
        item.setSizeHint(QSize(180, 92))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.layer_list.addItem(item)
        self.layer_list.setItemWidget(
            item,
            LayerPreview(
                background, self.doc.background_white, self.toggle_background, background=True
            ),
        )
        self.layer_list.setCurrentRow(len(self.doc.layers) - 1 - self.doc.active)
        self.layer_list.blockSignals(False)
        self.update_merge_button()
        self.canvas.sync()
        self.undo_action.setEnabled(bool(self.undo_stack))
        self.redo_action.setEnabled(bool(self.redo_stack))
        self.retranslate()

    def update_title(self):
        self.setWindowTitle(
            f"{'*' if self.dirty else ''}{Path(self.path).name if self.path else tr('COMMON.NEW_IMAGE')} — Faint"
        )

    def retranslate(self):
        """Update labels without rebuilding widgets or changing editing state."""
        localize_tree(self)
        for preview in self.findChildren(LayerPreview):
            preview.update_translation_layout()
        self.set_color(self.color)
        self.update_title()
        self.update_status()
        for code, action in self.language_actions.items():
            action.setChecked(code == self._i18n.language)

    def update_status(self):
        self.tool_status.setText(
            f"{self.tool_actions[self.tool].text()} · {tr(TOOL_BY_KEY[self.tool].hint)} · {tr('STATUS.PICK_COLOR_HINT')}"
        )
        if not self.doc.layers:
            self.tool_status.setText(tr("STATUS.NO_LAYERS"))
        elif not self.can_edit():
            self.tool_status.setText(tr("STATUS.HIDDEN_LAYER_LOCKED"))
        self.size_status.setText(f"{self.doc.size.width()} × {self.doc.size.height()} px   |")
        self.zoom_button.setText(f"{self.canvas.zoom * 100:.1f}".rstrip("0").rstrip(".") + "%")

    def edit_zoom(self):
        value, accepted = QInputDialog.getDouble(
            self, tr("DIALOG.ZOOM"), tr("DIALOG.ZOOM_PERCENT"), self.canvas.zoom * 100, 10, 1600, 1
        )
        if accepted:
            self.canvas.set_zoom(value / 100)

    def can_edit(self):
        return (
            bool(self.doc.layers)
            and 0 <= self.doc.active < len(self.doc.layers)
            and self.doc.layers[self.doc.active].visible
        )

    def resize_canvas_dialog(self):
        if not self.can_edit():
            return
        dialog = CanvasSizeDialog(self.doc.size, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            size = dialog.canvas_size()
            if size != self.doc.size:
                self.deselect()
                self.checkpoint()
                self.doc.resize(size.width(), size.height())
                self.refresh()

    def layer_selected(self, row):
        if 0 <= row < len(self.doc.layers):
            index = len(self.doc.layers) - 1 - row
            if index != self.doc.active:
                self.deselect()
            self.doc.active = index
            self.canvas.sync()
            self.update_status()

    def selected_layer_indices(self):
        count = len(self.doc.layers)
        return sorted(
            count - 1 - self.layer_list.row(item)
            for item in self.layer_list.selectedItems()
            if 0 <= self.layer_list.row(item) < count
        )

    def update_merge_button(self):
        self.merge_button.setEnabled(len(self.selected_layer_indices()) >= 2)

    def merge_layers(self):
        """Composite selected paint layers bottom to top, including hidden pixels."""
        indices = self.selected_layer_indices()
        if len(indices) < 2:
            return
        self.deselect()
        self.checkpoint()
        image = blank(self.doc.size.width(), self.doc.size.height())
        painter = QPainter(image)
        for index in indices:
            layer = self.doc.layers[index]
            painter.drawImage(0, 0, layer.image)
        painter.end()
        merged = Layer("합친 레이어", image, any(self.doc.layers[i].visible for i in indices))
        # Place the result where the topmost selected layer was.
        target = indices[-1] - len(indices) + 1
        selected = set(indices)
        self.doc.layers = [layer for i, layer in enumerate(self.doc.layers) if i not in selected]
        self.doc.layers.insert(target, merged)
        self.doc.active = target
        self.refresh()

    def toggle_layer(self, index):
        self.deselect()
        self.checkpoint()
        self.doc.layers[index].visible = not self.doc.layers[index].visible
        self.refresh()

    def toggle_background(self):
        self.deselect()
        self.checkpoint()
        self.doc.background_white = not self.doc.background_white
        self.refresh()

    def reorder_layer(self, source_row, insertion_row):
        count = len(self.doc.layers)
        if not 0 <= source_row < count:
            return
        insertion_row = max(0, min(count, insertion_row))
        target_row = insertion_row - (1 if source_row < insertion_row else 0)
        if source_row == target_row:
            return
        self.deselect()
        self.checkpoint()
        active = self.doc.layers[self.doc.active]
        layers = list(reversed(self.doc.layers))
        layers.insert(target_row, layers.pop(source_row))
        self.doc.layers = list(reversed(layers))
        self.doc.active = next(i for i, layer in enumerate(self.doc.layers) if layer is active)
        self.refresh()

    def add_layer(self):
        self.deselect()
        self.checkpoint()
        self.doc.active += 1
        self.doc.layers.insert(
            self.doc.active,
            Layer(
                f"레이어 {len(self.doc.layers) + 1}",
                blank(self.doc.size.width(), self.doc.size.height()),
            ),
        )
        self.refresh()

    def remove_layer(self):
        self.delete_layer(self.doc.active)

    def delete_layer(self, index):
        if not 0 <= index < len(self.doc.layers):
            return
        self.deselect()
        self.checkpoint()
        active = self.doc.active
        self.doc.layers.pop(index)
        self.doc.active = min(
            max(0, active - (1 if index < active else 0)), len(self.doc.layers) - 1
        )
        self.refresh()

    def deselect(self):
        """Commit the displayed result by releasing the floating selection buffers."""
        self.canvas.selection = QRect()
        self.canvas.selection_pixels = self.canvas.selection_base = None
        self.canvas.selection_drag = None
        self.canvas.update()

    def select_all(self):
        if not self.can_edit():
            return
        self.set_tool("select")
        self.deselect()
        self.canvas.selection = QRect(QPoint(), self.doc.size)
        self.canvas.update()

    @staticmethod
    def copy_image_to_clipboard(image):
        """Offer both native Qt image data and PNG for other apps and KDE history."""
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            return
        mime = QMimeData()
        mime.setImageData(image)
        mime.setData("image/png", data)
        QApplication.clipboard().setMimeData(mime)

    def copy(self):
        r = self.canvas.selection
        if not r.isEmpty():
            if self.canvas.selection_pixels is not None:
                image = self.canvas.selection_pixels.scaled(
                    r.size(), Qt.AspectRatioMode.IgnoreAspectRatio
                )
            else:
                image = self.doc.layers[self.doc.active].image.copy(r)
            self.copy_image_to_clipboard(image)

    def copy_merged(self):
        r = self.canvas.selection
        if not r.isEmpty():
            self.copy_image_to_clipboard(self.doc.composite().copy(r))

    def clear_selection(self):
        if not self.can_edit() or self.canvas.selection.isEmpty():
            return
        self.checkpoint()
        self.canvas.capture_selection()
        self.doc.layers[self.doc.active].image = self.canvas.selection_base.copy()
        self.deselect()
        self.refresh()

    def cut(self):
        if not self.can_edit():
            return
        self.copy()
        self.clear_selection()

    def clipboard_image(self):
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if not image.isNull():
            return image
        mime = clipboard.mimeData()
        if mime is not None:
            for url in mime.urls():
                if url.isLocalFile():
                    image = QImage(url.toLocalFile())
                    if not image.isNull():
                        return image
        return None

    def paste(self):
        # Pasting creates a new visible layer, so a hidden active layer must not
        # block it. Document.paste also grows the canvas to fit the clipboard.
        image = self.clipboard_image()
        if image is not None:
            self.checkpoint()
            self.doc.paste(image)
            self.deselect()
            self.refresh()

    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            tr("DIALOG.SAVE_ASK_TITLE"),
            tr("DIALOG.SAVE_ASK_DESCRIPTION"),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def new(self):
        if not self.confirm_discard():
            return
        self.doc = Document()
        self.path = None
        self.reset_history()

    def reset_history(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self.deselect()
        self.refresh()

    def open(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("COMMON.OPEN"), "", tr("FILE_FILTER.IMAGES"))
        if not path:
            return
        self.open_path(path)

    def open_path(self, path):
        """Open a file from the dialog or desktop launcher using the same logic."""
        try:
            doc = load_document(path)
            self.doc, self.path = doc, path
            self.reset_history()
        except Exception as exc:
            QMessageBox.warning(self, tr("ERROR.OPEN_FILE"), str(exc))

    def save(self, save_as=False):
        path = self.path
        if save_as or not path:
            path, chosen = QFileDialog.getSaveFileName(
                self,
                tr("COMMON.SAVE"),
                path or tr("FILE.UNTITLED"),
                tr("FILE_FILTER.SAVE"),
            )
            if not path:
                return False
            if not Path(path).suffix:
                # The file filter's extension is language independent.
                import re

                match = re.search(r"\(\*(\.[a-z]+)", chosen)
                path += match.group(1) if match else ".faint"
        try:
            save_document(self.doc, path)
            self.path, self.dirty = path, False
            self.refresh()
            return True
        except Exception as exc:
            QMessageBox.warning(self, tr("ERROR.SAVE_FILE"), str(exc))
            return False

    def refresh_palette(self):
        self.palette_list.clear()
        for color in self.swatches:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, color)
            item.setToolTip(color)
            item.setSizeHint(QSize(34, 44))
            item.setBackground(QColor(color))
            item.setForeground(QColor("black" if QColor(color).lightness() > 128 else "white"))
            self.palette_list.addItem(item)

    def add_swatch(self):
        color = self.color.name(QColor.NameFormat.HexArgb)
        if color not in self.swatches:
            self.swatches.append(color)
        self.refresh_palette()

    def remove_swatch(self):
        row = self.palette_list.currentRow()
        if row >= 0:
            self.swatches.pop(row)
            self.refresh_palette()

    def save_palette(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("PALETTE.SAVE"), "palette.json", tr("FILE_FILTER.PALETTE")
        )
        if path:
            try:
                Path(path).write_text(json.dumps(self.swatches, indent=2), encoding="utf-8")
            except OSError as exc:
                QMessageBox.warning(self, tr("ERROR.SAVE_FILE"), str(exc))

    def load_palette(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("PALETTE.LOAD"), "", tr("FILE_FILTER.PALETTE")
        )
        if path:
            try:
                colors = json.loads(Path(path).read_text(encoding="utf-8"))
                if not isinstance(colors, list) or not all(
                    isinstance(c, str) and QColor(c).isValid() for c in colors
                ):
                    raise ValueError(tr("ERROR.INVALID_PALETTE"))
                self.swatches = colors
                self.refresh_palette()
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, tr("ERROR.OPEN_FILE"), str(exc))

    def closeEvent(self, event):
        if self.confirm_discard():
            event.accept()
        else:
            event.ignore()
