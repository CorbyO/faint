import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['FAINT_LANGUAGE'] = 'ko'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem, QStyle, QDialog
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt, QMimeData, QUrl
from PySide6.QtGui import QColor, QImage, QWheelEvent, QMouseEvent, QPixmap, QPainter, QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from faint.app import Document, Window, blank, flood, CanvasSizeDialog

app = QApplication.instance() or QApplication([])

class PaintTests(unittest.TestCase):
    def test_resize_and_paste_preserve_pixels(self):
        doc = Document(4, 4)
        doc.layers[0].image.setPixelColor(1, 1, QColor('red'))
        state = doc.snapshot()
        doc.resize(8, 7, 2, 1)
        self.assertEqual(doc.composite().pixelColor(3, 2), QColor('red'))
        self.assertEqual(doc.composite().pixelColor(0, 0).alpha(), 0)
        doc.restore(state)
        image = blank(10, 6)
        image.setPixelColor(9, 5, QColor('blue'))
        doc.paste(image)
        self.assertEqual(len(doc.layers), 2)
        self.assertEqual(doc.size.width(), 10)
        self.assertEqual(doc.composite().pixelColor(9, 5), QColor('blue'))
        self.assertEqual(doc.composite().pixelColor(1, 1), QColor('red'))

    def test_fill_respects_boundary_and_alpha(self):
        image = blank(5, 5)
        for y in range(5): image.setPixelColor(2, y, QColor('black'))
        flood(image, QPoint(0, 0), QColor('#80ff0000'))
        self.assertEqual(image.pixelColor(0, 0).alpha(), 128)
        self.assertEqual(image.pixelColor(4, 0).alpha(), 0)
        self.assertEqual(image.pixelColor(2, 0), QColor('black'))

    def test_canvas_drag_resize_and_brush(self):
        window = Window()
        window.doc = Document(60, 40)
        window.refresh()
        canvas = window.canvas
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
        QTest.mouseMove(canvas, QPoint(45, 35))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(45, 35))
        self.assertGreater(window.doc.layers[0].image.pixelColor(12, 12).alpha(), 0)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(78, 58))
        QTest.mouseMove(canvas, QPoint(98, 68))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(98, 68))
        self.assertEqual(window.doc.size.width(), 80)
        self.assertEqual(window.doc.size.height(), 50)
        window.undo()
        self.assertEqual(window.doc.size.width(), 60)
        window.dirty = False
        window.close()

    def test_view_navigation_and_panels(self):
        window = Window()
        window.show()
        app.processEvents()
        canvas = window.canvas
        original = QPointF(canvas.offset)
        QTest.mousePress(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(100, 100))
        QTest.mouseMove(canvas, QPoint(140, 130))
        QTest.mouseRelease(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(140, 130))
        self.assertEqual(canvas.offset, original + QPointF(40, 30))
        self.assertFalse(window.dirty)
        anchor = QPointF(200, 150)
        before = (anchor-canvas.offset)/canvas.zoom
        event = QWheelEvent(anchor, anchor, QPoint(), QPoint(0, 120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(canvas, event)
        self.assertAlmostEqual(canvas.zoom, 1.2)
        after = (anchor-canvas.offset)/canvas.zoom
        self.assertAlmostEqual(before.x(), after.x())
        self.assertAlmostEqual(before.y(), after.y())
        offset = QPointF(canvas.offset)
        window.doc.resize(1000, 700)
        window.refresh()
        self.assertEqual(canvas.offset, offset)
        self.assertTrue(all(not window.palette_list.item(i).text() for i in range(window.palette_list.count())))
        item = window.palette_list.item(2)
        window.palette_list.itemClicked.emit(item)
        self.assertEqual(window.color, QColor(window.swatches[2]))
        window.layer_dock.close()
        self.assertTrue(window.layer_dock.isVisible())
        self.assertTrue(window.layer_dock.isVisible())
        # Painting remains in document coordinates after zoom and pan.
        point = (canvas.offset + QPointF(50, 50)*canvas.zoom).toPoint()
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=point)
        self.assertGreater(window.doc.layers[0].image.pixelColor(50, 50).alpha(), 0)
        window.dirty = False
        window.close()

    def test_selection_edit_alt_picker_and_focused_shortcuts(self):
        window = Window()
        window.show()
        window.activateWindow()
        app.processEvents()
        canvas = window.canvas
        window.doc = Document(200, 160)
        window.doc.layers[0].image.fill(QColor('red'))
        window.refresh()
        window.set_tool('select')
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(48, 48))
        QTest.mouseMove(canvas, QPoint(88, 88))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(88, 88))
        self.assertEqual(canvas.selection.width(), 41)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(68, 68))
        QTest.mouseMove(canvas, QPoint(98, 98))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(98, 98))
        self.assertEqual(canvas.selection.x(), 60)
        self.assertEqual(window.doc.layers[0].image.pixelColor(35, 35).alpha(), 0)
        self.assertEqual(window.doc.layers[0].image.pixelColor(65, 65), QColor('red'))
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(118, 118))
        QTest.mouseMove(canvas, QPoint(138, 138))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(138, 138))
        self.assertEqual(canvas.selection.width(), 61)
        self.assertEqual(window.doc.layers[0].image.pixelColor(115, 115), QColor('red'))
        window.set_color(QColor('blue'))
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier, QPoint(100, 100))
        self.assertEqual(window.color, QColor('red'))
        self.assertEqual(window.tool, 'select')
        window.width.setFocus()
        QTest.keyClick(window.width, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(window.doc.layers[0].image.pixelColor(35, 35).alpha(), 0)
        QTest.keyClick(window.width, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(window.doc.layers[0].image.pixelColor(35, 35), QColor('red'))
        QTest.keyClick(window.width, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(window.doc.layers[0].image.pixelColor(35, 35).alpha(), 0)
        image = blank(240, 180)
        image.fill(QColor('blue'))
        app.clipboard().setImage(image)
        QTest.keyClick(window.width, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(window.doc.layers), 2)
        self.assertEqual(window.doc.size.width(), 240)
        self.assertIn('240 × 180 px', window.size_status.text())
        self.assertIn('100%', window.zoom_button.text())
        self.assertIn('사각 선택', window.tool_status.text())
        window.dirty = False
        window.close()

    def test_selection_preserves_original_pixels_and_background(self):
        window = Window()
        window.show()
        window.activateWindow()
        app.processEvents()
        window.doc = Document(220, 160)
        image = window.doc.layers[0].image
        for y in range(20, 60):
            for x in range(20, 40): image.setPixelColor(x, y, QColor('red'))
            for x in range(80, 120): image.setPixelColor(x, y, QColor('green'))
        window.refresh()
        window.set_tool('select')
        canvas = window.canvas
        def drag(a, b):
            a, b = a+QPoint(18, 18), b+QPoint(18, 18)
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=a)
            QTest.mouseMove(canvas, b)
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=b)
        drag(QPoint(20, 20), QPoint(59, 59))
        drag(QPoint(40, 40), QPoint(100, 40))
        drag(QPoint(100, 40), QPoint(160, 40))
        image = window.doc.layers[0].image
        self.assertEqual(image.pixelColor(85, 30), QColor('green'))
        self.assertEqual(image.pixelColor(145, 30), QColor('red'))
        self.assertEqual(image.pixelColor(165, 30).alpha(), 0)
        # Move partly outside the canvas, release, then bring the same source back.
        drag(QPoint(160, 40), QPoint(225, 40))
        drag(QPoint(225, 40), QPoint(40, 90))
        image = window.doc.layers[0].image
        self.assertEqual(image.pixelColor(25, 80), QColor('red'))
        self.assertEqual(image.pixelColor(45, 80).alpha(), 0)
        window.width.setFocus()
        QTest.keyClick(window.width, Qt.Key.Key_Delete)
        self.assertTrue(canvas.selection.isEmpty())
        self.assertEqual(window.doc.layers[0].image.pixelColor(25, 80).alpha(), 0)
        self.assertEqual(window.doc.layers[0].image.pixelColor(85, 30), QColor('green'))
        window.undo()
        self.assertEqual(window.doc.layers[0].image.pixelColor(25, 80), QColor('red'))
        window.set_tool('select')
        canvas.selection = QRect(20, 70, 40, 40)
        window.set_tool('brush')
        self.assertTrue(canvas.selection.isEmpty())
        self.assertIsNone(canvas.selection_pixels)
        window.dirty = False
        window.close()

    def test_shift_brush_and_equal_aspect_shapes(self):
        window = Window()
        window.doc = Document(180, 160)
        window.show()
        app.processEvents()
        canvas = window.canvas
        shift = Qt.KeyboardModifier.ShiftModifier
        def shifted_drag(start, end):
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, shift, start)
            event = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(end), QPointF(end),
                                Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, shift)
            QApplication.sendEvent(canvas, event)
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, shift, end)
        shifted_drag(QPoint(48, 48), QPoint(118, 78))
        image = window.doc.layers[0].image
        self.assertGreater(image.pixelColor(95, 30).alpha(), 0)
        self.assertEqual(image.pixelColor(95, 55).alpha(), 0)
        shifted_drag(QPoint(58, 68), QPoint(78, 128))
        self.assertGreater(window.doc.layers[0].image.pixelColor(40, 105).alpha(), 0)
        for tool in ('rect', 'ellipse', 'roundrect'):
            window.set_tool(tool)
            canvas.start = QPoint(20, 20)
            end = canvas.constrained_point(QPoint(70, 45), shift)
            self.assertEqual(abs(end.x()-20), abs(end.y()-20))
            canvas.start = None
        window.dirty = False
        window.close()

    def test_thumbnail_layers_background_and_reordering(self):
        window = Window()
        window.show()
        app.processEvents()
        window.doc = Document(12, 12)
        window.doc.layers[0].image.setPixelColor(2, 2, QColor('red'))
        window.add_layer()
        window.doc.layers[1].image.setPixelColor(2, 2, QColor('blue'))
        window.refresh()
        self.assertEqual(window.layer_list.count(), 3)
        self.assertTrue(all(not window.layer_list.item(i).text() for i in range(3)))
        self.assertFalse(window.layer_list.item(2).flags() & Qt.ItemFlag.ItemIsDragEnabled)
        window.layer_list.itemWidget(window.layer_list.item(0)).toggle.click()
        self.assertFalse(window.doc.layers[1].visible)
        self.assertEqual(window.doc.composite().pixelColor(2, 2), QColor('red'))
        window.layer_list.itemWidget(window.layer_list.item(0)).toggle.click()
        self.assertTrue(window.doc.layers[1].visible)
        window.reorder_layer(0, 2)
        self.assertEqual(window.doc.composite().pixelColor(2, 2), QColor('red'))
        self.assertEqual(window.doc.active, 0)
        window.undo()
        self.assertEqual(window.doc.composite().pixelColor(2, 2), QColor('blue'))
        window.layer_list.itemWidget(window.layer_list.item(2)).toggle.click()
        self.assertTrue(window.doc.background_white)
        self.assertEqual(window.doc.composite().pixelColor(0, 0), QColor('white'))
        window.undo()
        self.assertFalse(window.doc.background_white)
        self.assertEqual(window.doc.composite().pixelColor(0, 0).alpha(), 0)
        window.reorder_layer(2, 0)
        self.assertEqual(len(window.doc.layers), 2)
        window.toggle_background()
        with tempfile.TemporaryDirectory() as directory:
            window.path = str(Path(directory)/'background.faint')
            self.assertTrue(window.save())
            with patch('faint.app.QFileDialog.getOpenFileName', return_value=(window.path, '')):
                window.open()
            self.assertTrue(window.doc.background_white)
        window.dirty = False
        window.close()

    def test_hidden_layer_blocks_content_edits(self):
        window = Window()
        window.show()
        app.processEvents()
        canvas = window.canvas
        window.doc.layers[0].image.fill(QColor('red'))
        window.toggle_layer(0)
        before = window.doc.layers[0].image.copy()
        history_count = len(window.undo_stack)
        for tool in ('brush', 'eraser', 'select', 'rect', 'fill'):
            window.set_tool(tool)
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
            QTest.mouseMove(canvas, QPoint(100, 100))
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
        canvas.selection = QRect(40, 40, 20, 20)
        window.clear_selection()
        window.cut()
        window.resize_canvas_dialog()
        self.assertEqual(window.doc.layers[0].image, before)
        self.assertEqual(window.doc.size, QSize(800, 600))
        self.assertEqual(len(window.doc.layers), 1)
        self.assertEqual(len(window.undo_stack), history_count)
        self.assertFalse(canvas.cursor().pixmap().isNull())
        window.toggle_layer(0)
        window.set_tool('brush')
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
        self.assertNotEqual(window.doc.layers[0].image, before)
        window.dirty = False
        window.close()

    def test_trash_button_removes_its_layer_and_last_layer(self):
        window = Window()
        window.add_layer()
        original_active = window.doc.layers[1]
        bottom = window.layer_list.itemWidget(window.layer_list.item(1))
        self.assertIsNotNone(bottom.delete_button)
        bottom.delete_button.click()
        self.assertEqual(len(window.doc.layers), 1)
        self.assertIs(window.doc.layers[0], original_active)
        window.layer_list.itemWidget(window.layer_list.item(0)).delete_button.click()
        self.assertEqual(len(window.doc.layers), 0)
        self.assertIsNone(window.layer_list.itemWidget(window.layer_list.item(0)).delete_button)
        window.undo()
        self.assertEqual(len(window.doc.layers), 1)
        window.delete_layer(0)
        with tempfile.TemporaryDirectory() as directory:
            window.path = str(Path(directory)/'empty.faint')
            self.assertTrue(window.save())
            with patch('faint.app.QFileDialog.getOpenFileName', return_value=(window.path, '')):
                window.open()
            self.assertEqual(len(window.doc.layers), 0)
        app.clipboard().setImage(blank(20, 20))
        window.paste()
        self.assertEqual(len(window.doc.layers), 1)
        window.dirty = False
        window.close()

    def test_shift_selection_preserves_ratio_for_edges_and_corners(self):
        window = Window()
        canvas = window.canvas
        window.set_tool('select')
        canvas.selection = QRect(30, 30, 60, 30)
        canvas.capture_selection()
        for edge, delta in [('se', QPoint(40, 30)), ('nw', QPoint(-40, -30)),
                            ('e', QPoint(40, 0)), ('n', QPoint(0, -20))]:
            canvas.selection_original = QRect(30, 30, 60, 30)
            canvas.selection_drag = edge
            canvas.start = QPoint(50, 50)
            canvas.transform_selection(canvas.start+delta, Qt.KeyboardModifier.ShiftModifier)
            self.assertAlmostEqual(canvas.selection.width()/canvas.selection.height(), 2.0, delta=0.04)
        canvas.start = None
        window.dirty = False
        window.close()

    def test_palette_keeps_color_when_selected(self):
        window = Window()
        window.palette_list.setCurrentRow(2)
        delegate = window.palette_list.itemDelegate()
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 28, 28)
        option.state = QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_Enabled
        pixmap = QPixmap(28, 28)
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)
        delegate.paint(painter, option, window.palette_list.model().index(2, 0))
        painter.end()
        self.assertEqual(pixmap.toImage().pixelColor(14, 14), QColor(window.swatches[2]))
        window.close()

    def test_canvas_size_dialog_ratio_and_history(self):
        dialog = CanvasSizeDialog(QSize(800, 600))
        dialog.aspect_lock.setChecked(True)
        dialog.width_input.setValue(1200)
        self.assertEqual(dialog.height_input.value(), 900)
        dialog.height_input.setValue(300)
        self.assertEqual(dialog.width_input.value(), 400)
        dialog.aspect_lock.setChecked(False)
        dialog.width_input.setValue(500)
        self.assertEqual(dialog.height_input.value(), 300)
        window = Window()
        window.doc.layers[0].image.setPixelColor(10, 10, QColor('red'))
        window.show()
        window.activateWindow()
        app.processEvents()
        window.width.setFocus()
        with patch('faint.app.CanvasSizeDialog.exec', return_value=QDialog.DialogCode.Accepted), patch('faint.app.CanvasSizeDialog.canvas_size', return_value=QSize(1000, 700)):
            QTest.keyClick(window.width, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(window.doc.size, QSize(1000, 700))
        self.assertEqual(window.doc.layers[0].image.pixelColor(10, 10), QColor('red'))
        window.undo()
        self.assertEqual(window.doc.size, QSize(800, 600))
        window.dirty = False
        window.close()

    def test_paste_into_new_layer_from_hidden_layer(self):
        window = Window()
        window.show()
        window.activateWindow()
        app.processEvents()
        window.doc = Document(20, 20)
        window.doc.layers[0].image.fill(QColor('red'))
        window.toggle_layer(0)
        original = window.doc.layers[0].image.copy()
        image = blank(30, 25)
        image.fill(QColor('blue'))
        app.clipboard().setImage(image)
        window.width.setFocus()
        QTest.keyClick(window.width, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(window.doc.layers), 2)
        self.assertTrue(window.can_edit())
        self.assertEqual(window.doc.active, 1)
        self.assertFalse(window.doc.layers[0].visible)
        self.assertEqual(window.doc.layers[0].image.copy(QRect(0, 0, 20, 20)), original)
        self.assertEqual(window.doc.size, QSize(30, 25))
        self.assertEqual(window.doc.layers[1].image.pixelColor(0, 0), QColor('blue'))
        window.undo()
        self.assertEqual(window.doc.size, QSize(20, 20))
        self.assertFalse(window.can_edit())
        window.dirty = False
        window.close()

    def test_shift_initial_selection_stays_square_and_inside_canvas(self):
        window = Window()
        window.doc = Document(140, 100)
        window.set_tool('select')
        window.show()
        app.processEvents()
        canvas = window.canvas
        for start, end in [(QPoint(30, 30), QPoint(90, 60)), (QPoint(80, 70), QPoint(-10, 20))]:
            window.deselect()
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, start+QPoint(18, 18))
            QTest.mouseMove(canvas, end+QPoint(18, 18))
            # The square constraint is latched when the selection begins.
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end+QPoint(18, 18))
            self.assertEqual(canvas.selection.width(), canvas.selection.height())
            self.assertTrue(QRect(QPoint(), window.doc.size).contains(canvas.selection))
        window.close()

    def test_brush_outline_matches_width_and_zoom(self):
        window = Window()
        window.show()
        app.processEvents()
        canvas = window.canvas
        window.doc.background_white = True
        window.width.setValue(40)
        canvas.zoom = 2
        canvas.hover_position = QPointF(150, 150)
        canvas.sync()
        with_ring = canvas.grab().toImage()
        self.assertEqual(canvas.cursor().shape(), Qt.CursorShape.BlankCursor)
        canvas.hover_position = None
        without_ring = canvas.grab().toImage()
        self.assertNotEqual(with_ring.pixelColor(189, 150), without_ring.pixelColor(189, 150))
        self.assertEqual(with_ring.pixelColor(150, 150), without_ring.pixelColor(150, 150))
        self.assertEqual(with_ring.pixelColor(195, 150), without_ring.pixelColor(195, 150))
        window.set_tool('eraser')
        window.width.setValue(40)
        canvas.hover_position = QPointF(150, 150)
        self.assertEqual(canvas.grab().toImage().pixelColor(189, 150), with_ring.pixelColor(189, 150))
        window.close()

    def test_drag_lifecycle_keeps_all_layer_widgets(self):
        window = Window()
        window.add_layer()
        window.show()
        app.processEvents()
        layers = window.layer_list
        layers.setCurrentRow(0)
        layers.drag_row = 0
        bottom = layers.visualItemRect(layers.item(1)).bottomLeft()+QPoint(10, 0)
        class Drop:
            def source(self): return layers
            def position(self): return QPointF(bottom)
            def setDropAction(self, action): self.action = action
            def accept(self): self.accepted = True
        event = Drop()
        with patch('faint.widgets.layers.QDrag') as drag_class:
            drag_class.return_value.exec.side_effect = lambda action: layers.dropEvent(event)
            layers.startDrag(Qt.DropAction.MoveAction)
            drag_class.return_value.exec.assert_called_once()
        app.processEvents()
        self.assertEqual(layers.count(), 3)
        self.assertTrue(all(layers.itemWidget(layers.item(i)) is not None for i in range(3)))
        self.assertEqual(len(window.doc.layers), 2)
        self.assertEqual(window.doc.active, 0)
        window.dirty = False
        window.close()

    def test_image_file_drop_adds_layers_and_ignores_projects(self):
        window = Window()
        window.show()
        app.processEvents()
        window.doc = Document(10, 10)
        window.toggle_layer(0)
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for extension, color, size in [('png', 'red', (30, 20)), ('JPG', 'blue', (40, 35))]:
                image = blank(*size)
                image.fill(QColor(color))
                path = str(Path(directory)/('image.'+extension))
                self.assertTrue(image.save(path))
                paths.append(path)
            project = str(Path(directory)/'ignored.faint')
            Path(project).write_text('not an image')
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(path) for path in paths+[project]])
            enter = QDragEnterEvent(QPoint(100, 100), Qt.DropAction.CopyAction, mime,
                                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(window, enter)
            self.assertTrue(enter.isAccepted())
            drop = QDropEvent(QPointF(100, 100), Qt.DropAction.CopyAction, mime,
                              Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(window, drop)
            self.assertTrue(drop.isAccepted())
            self.assertEqual(drop.dropAction(), Qt.DropAction.CopyAction)
            self.assertEqual(len(window.doc.layers), 3)
            self.assertEqual(window.doc.size, QSize(40, 35))
            self.assertFalse(window.doc.layers[0].visible)
            self.assertTrue(window.can_edit())
            self.assertEqual(window.doc.layers[1].image.pixelColor(0, 0), QColor('red'))
            self.assertGreater(window.doc.layers[2].image.pixelColor(0, 0).blue(), 240)
            window.undo()
            self.assertEqual(len(window.doc.layers), 1)
            self.assertEqual(window.doc.size, QSize(10, 10))
            mime.setUrls([QUrl.fromLocalFile(project)])
            enter = QDragEnterEvent(QPoint(100, 100), Qt.DropAction.CopyAction, mime,
                                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(window, enter)
            self.assertFalse(enter.isAccepted())
        window.dirty = False
        window.close()

    def test_copy_shortcuts_and_tool_shortcuts(self):
        window = Window()
        window.show()
        window.activateWindow()
        app.processEvents()
        window.doc = Document(40, 40)
        window.doc.layers[0].image.fill(QColor('red'))
        window.add_layer()
        window.doc.layers[1].image.setPixelColor(10, 10, QColor('blue'))
        window.set_tool('select')
        window.canvas.selection = QRect(5, 5, 20, 20)
        window.width.setFocus()
        QTest.keyClick(window.width, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(app.clipboard().image().size(), QSize(20, 20))
        self.assertEqual(app.clipboard().image().pixelColor(0, 0).alpha(), 0)
        QTest.keyClick(window.width, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(app.clipboard().image().pixelColor(0, 0), QColor('red'))
        self.assertEqual(app.clipboard().image().pixelColor(5, 5), QColor('blue'))
        window.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        window.canvas.setFocus()
        for key, tool in [(Qt.Key.Key_B, 'brush'), (Qt.Key.Key_E, 'eraser'), (Qt.Key.Key_S, 'select'),
                          (Qt.Key.Key_L, 'line'), (Qt.Key.Key_R, 'rect'), (Qt.Key.Key_C, 'ellipse'), (Qt.Key.Key_F, 'fill')]:
            QTest.keyClick(window.canvas, key)
            self.assertEqual(window.tool, tool)
            self.assertIn(window.tool_actions[tool].shortcut().toString(), window.tool_actions[tool].toolTip())
        QTest.keyClick(window.canvas, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(window.tool, 'roundrect')
        window.dirty = False
        window.close()

    def test_shift_select_and_merge_layers(self):
        window = Window()
        window.show()
        app.processEvents()
        window.doc = Document(40, 40)
        window.doc.layers[0].image.fill(QColor('red'))
        window.add_layer()
        window.doc.layers[1].image.setPixelColor(10, 10, QColor('blue'))
        window.refresh()
        layers = window.layer_list
        top = layers.visualItemRect(layers.item(0)).center()
        bottom = layers.visualItemRect(layers.item(1)).center()
        QTest.mouseClick(layers.viewport(), Qt.MouseButton.LeftButton, pos=top)
        QTest.mouseClick(layers.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, bottom)
        self.assertEqual(window.selected_layer_indices(), [0, 1])
        self.assertTrue(window.merge_button.isEnabled())
        window.merge_button.click()
        self.assertEqual(len(window.doc.layers), 1)
        self.assertEqual(window.doc.layers[0].image.pixelColor(0, 0), QColor('red'))
        self.assertEqual(window.doc.layers[0].image.pixelColor(10, 10), QColor('blue'))
        self.assertFalse(window.merge_button.isEnabled())
        window.undo()
        self.assertEqual(len(window.doc.layers), 2)
        window.dirty = False
        window.close()

    def test_plain_wheel_changes_width_without_zooming(self):
        window = Window()
        canvas = window.canvas
        for delta, expected in [(120, 5), (-120, 4)]:
            event = QWheelEvent(QPointF(80, 80), QPointF(80, 80), QPoint(), QPoint(0, delta),
                                Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                Qt.ScrollPhase.NoScrollPhase, False)
            QApplication.sendEvent(canvas, event)
            self.assertEqual(window.width.value(), expected)
            self.assertEqual(canvas.zoom, 1)
        window.close()

    def test_png_clipboard_mime_for_both_copy_modes(self):
        window = Window()
        window.doc = Document(30, 30)
        window.doc.layers[0].image.setPixelColor(10, 10, QColor('#80ff0000'))
        window.set_tool('select')
        window.canvas.selection = QRect(5, 5, 10, 10)
        for copy in (window.copy, window.copy_merged):
            copy()
            mime = app.clipboard().mimeData()
            self.assertTrue(mime.hasFormat('image/png'))
            image = QImage.fromData(mime.data('image/png'), 'PNG')
            self.assertEqual(image.size(), QSize(10, 10))
            self.assertEqual(image.pixelColor(5, 5).alpha(), 128)
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            self.assertFalse(app.clipboard().image().isNull())
        window.close()

    def test_click_outside_selection_deselects_without_editing(self):
        window = Window()
        window.show()
        app.processEvents()
        window.set_tool('select')
        canvas = window.canvas
        canvas.selection = QRect(20, 20, 40, 40)
        before = window.doc.layers[0].image.copy()
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(120, 120))
        self.assertTrue(canvas.selection.isEmpty())
        self.assertEqual(window.doc.layers[0].image, before)
        self.assertFalse(window.dirty)
        window.close()

    def test_pixel_tool_has_no_antialiasing_and_remembers_widths(self):
        window = Window()
        window.show()
        window.activateWindow()
        app.processEvents()
        window.width.setValue(13)
        window.set_tool('eraser')
        window.width.setValue(21)
        window.set_tool('brush')
        self.assertEqual(window.width.value(), 13)
        window.set_tool('pixel')
        self.assertEqual(window.width.value(), 1)
        window.set_color(QColor('black'))
        canvas = window.canvas
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(48, 48))
        QTest.mouseMove(canvas, QPoint(68, 57))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(68, 57))
        image = window.doc.layers[0].image
        pixels = [(x, y) for x in range(25, 60) for y in range(25, 50) if image.pixelColor(x, y).alpha()]
        self.assertEqual(len(pixels), 21)
        self.assertTrue(all(image.pixelColor(x, y).alpha() == 255 for x, y in pixels))
        for tool in ('select', 'picker', 'fill'):
            window.set_tool(tool)
            self.assertFalse(window.width.isEnabled())
        window.set_tool('eraser')
        self.assertTrue(window.width.isEnabled())
        self.assertEqual(window.width.value(), 21)
        canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        canvas.setFocus()
        QTest.keyClick(canvas, Qt.Key.Key_P)
        self.assertEqual(window.tool, 'pixel')
        self.assertEqual(window.width.value(), 1)
        window.dirty = False
        window.close()

    def test_shift_canvas_resize_and_zoom_input(self):
        window = Window()
        window.doc = Document(120, 60)
        window.refresh()
        window.show()
        app.processEvents()
        canvas = window.canvas
        shift = Qt.KeyboardModifier.ShiftModifier
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, shift, QPoint(138, 78))
        end = QPoint(198, 98)
        event = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(end), QPointF(end),
                            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, shift)
        QApplication.sendEvent(canvas, event)
        self.assertEqual(canvas.preview_rect.width(), 180)
        self.assertEqual(canvas.preview_rect.height(), 90)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, shift, end)
        self.assertEqual(window.doc.size, QSize(180, 90))
        window.undo()
        self.assertEqual(window.doc.size, QSize(120, 60))
        for edge in ('n', 's', 'e', 'w', 'nw', 'se'):
            canvas.resizing = edge
            canvas.start = QPoint(100, 50)
            rect = canvas.resize_preview(QPoint(130, 70), shift)
            self.assertAlmostEqual(rect.width()/rect.height(), 2, delta=0.04)
        canvas.resizing = canvas.start = None
        center = QPointF(canvas.rect().center())
        document_point = (center-canvas.offset)/canvas.zoom
        with patch('faint.app.QInputDialog.getDouble', return_value=(175.5, True)):
            window.zoom_button.click()
        self.assertAlmostEqual(canvas.zoom, 1.755)
        self.assertEqual(window.zoom_button.text(), '175.5%')
        after = (center-canvas.offset)/canvas.zoom
        self.assertAlmostEqual(after.x(), document_point.x())
        self.assertAlmostEqual(after.y(), document_point.y())
        with patch('faint.app.QInputDialog.getDouble', return_value=(50, False)):
            window.zoom_button.click()
        self.assertAlmostEqual(canvas.zoom, 1.755)
        window.dirty = False
        window.close()

    def test_window_history_clipboard_and_io(self):
        window = Window()
        window.doc = Document(4, 4)
        image = blank(8, 6)
        image.fill(QColor('red'))
        app.clipboard().setImage(image)
        window.paste()
        self.assertEqual(window.doc.size.width(), 8)
        window.undo()
        self.assertEqual(window.doc.size.width(), 4)
        window.redo()
        self.assertEqual(len(window.doc.layers), 2)
        with tempfile.TemporaryDirectory() as directory:
            project = str(Path(directory)/'test.faint')
            window.path = project
            self.assertTrue(window.save())
            window.dirty = False
            with patch('faint.app.QFileDialog.getOpenFileName', return_value=(project, '')):
                window.open()
            self.assertEqual(len(window.doc.layers), 2)
            self.assertEqual(window.doc.composite().pixelColor(0, 0), QColor('red'))
            for extension in ('png', 'jpg'):
                window.path = str(Path(directory)/('test.'+extension))
                self.assertTrue(window.save())
                self.assertTrue(Path(window.path).stat().st_size > 0)
        window.dirty = False
        window.close()

if __name__ == '__main__': unittest.main()
