"""Language selection must never change an in-progress painting session."""
# ruff: noqa: E402 -- Select offscreen Qt before importing GUI modules.

import os
import tempfile
import unittest
from pathlib import Path
from string import Formatter
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEvent, QLocale, QRect, QSettings, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from faint import i18n
from faint.dialogs import CanvasSizeDialog
from faint.window import Window

app = QApplication.instance() or QApplication([])


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = QSettings(
            str(Path(self.directory.name) / "language.ini"), QSettings.Format.IniFormat
        )
        with patch.dict(os.environ, {"FAINT_LANGUAGE": "ko"}):
            self.language = i18n.LanguageManager(self.settings)
        self.previous = i18n._manager
        i18n._manager = self.language
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.dirty = False
            window.close()
            window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.removeTranslator(self.language.qt_translator)
        app.removeTranslator(self.language.qt_base)
        i18n._manager = self.previous
        self.directory.cleanup()

    def window(self):
        window = Window()
        self.windows.append(window)
        return window

    def test_live_switch_preserves_document_and_selection(self):
        window = self.window()
        window.doc.layers[0].image.setPixelColor(10, 10, QColor("red"))
        window.add_layer()
        window.set_tool("select")
        window.canvas.selection = QRect(10, 10, 30, 20)
        window.canvas.capture_selection()
        before = window.doc.snapshot()
        selection = QRect(window.canvas.selection)
        pixels = window.canvas.selection_pixels.copy()
        history = len(window.undo_stack)
        window.layer_list.item(0).setSelected(True)
        window.layer_list.item(1).setSelected(True)
        chosen = window.selected_layer_indices()
        window.language_actions["en"].trigger()
        self.assertEqual(window.tool_actions["brush"].text(), "Brush")
        self.assertEqual(window.menuBar().actions()[0].text(), "File")
        self.assertEqual(window.merge_button.text(), "Merge")
        self.assertIn("Drag to select", window.tool_status.text())
        self.assertEqual(window.doc.size, before[0])
        self.assertEqual(window.doc.active, before[2])
        for old, current in zip(before[1], window.doc.layers):
            self.assertEqual(old.image, current.image)
        self.assertEqual(window.canvas.selection, selection)
        self.assertEqual(window.canvas.selection_pixels, pixels)
        self.assertEqual(window.selected_layer_indices(), chosen)
        self.assertEqual(len(window.undo_stack), history)
        self.assertEqual(self.settings.value("ui/language"), "en")
        window.language_actions["ko"].trigger()
        self.assertEqual(window.tool_actions["brush"].text(), "브러시")
        self.assertEqual(window.menuBar().actions()[0].text(), "파일")
        self.assertIn("드래그로 선택", window.tool_status.text())
        self.assertEqual(window.canvas.selection, selection)

    def test_english_dialog_and_new_layer_controls(self):
        window = self.window()
        self.language.set_language("en", persist=False)
        window.add_layer()
        preview = window.layer_list.itemWidget(window.layer_list.item(0))
        self.assertEqual(preview.toggle.toolTip(), "Hide layer")
        self.assertEqual(preview.delete_button.toolTip(), "Delete layer")
        background = window.layer_list.itemWidget(
            window.layer_list.item(window.layer_list.count() - 1)
        )
        self.assertEqual(background.toggle.text(), "Transparent")
        self.assertGreaterEqual(
            background.toggle.width(),
            background.toggle.fontMetrics().horizontalAdvance("Transparent"),
        )
        self.assertEqual(window.tool_actions["brush"].toolTip(), "Brush (B)")
        self.assertIn("Current color", window.color_button.toolTip())
        dialog = CanvasSizeDialog(QSize(800, 600), window)
        self.assertEqual(dialog.windowTitle(), "Canvas size")
        self.assertEqual(dialog.aspect_lock.text(), "Lock aspect ratio")
        buttons = dialog.findChild(QDialogButtonBox)
        self.assertIn("Cancel", buttons.button(QDialogButtonBox.StandardButton.Cancel).text())
        dialog.deleteLater()

    def test_preference_and_locale_fallback(self):
        self.settings.setValue("ui/language", "en")
        with patch.dict(os.environ, {"FAINT_LANGUAGE": ""}):
            self.assertEqual(i18n.initial_language(self.settings), "en")
            self.settings.remove("ui/language")
            with patch.object(QLocale, "system", return_value=QLocale("ko_KR")):
                self.assertEqual(i18n.initial_language(self.settings), "ko")
            with patch.object(QLocale, "system", return_value=QLocale("fr_FR")):
                self.assertEqual(i18n.initial_language(self.settings), "en")
        with self.assertRaises(ValueError):
            self.language.set_language("fr", persist=False)

    def test_catalogue_keys_and_placeholders(self):
        for key, translations in i18n.MESSAGES.items():
            with self.subTest(key=key):
                self.assertRegex(key, r"^[A-Z][A-Z0-9_]*(\.[A-Z][A-Z0-9_]*)+$")
                self.assertEqual(set(translations), set(i18n.SUPPORTED_LANGUAGES))

                def fields(text):
                    return {
                        field for _, field, _, _ in Formatter().parse(text) if field is not None
                    }

                self.assertEqual(fields(translations["en"]), fields(translations["ko"]))
        for code in i18n.SUPPORTED_LANGUAGES:
            self.language.set_language(code, persist=False)
            for key, translations in i18n.MESSAGES.items():
                self.assertEqual(i18n.tr(key), translations[code])
        with self.assertRaises(KeyError):
            i18n.tr("UNKNOWN.KEY")

    def test_project_data_is_not_translated(self):
        window = self.window()
        name = window.doc.layers[0].name
        self.language.set_language("en", persist=False)
        self.assertEqual(window.doc.layers[0].name, name)
        self.assertEqual(
            i18n.tr("COLOR.CURRENT_HINT", color="#123456"),
            "Current color #123456 · Click to change",
        )
