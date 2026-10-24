"""File-manager launches must open the supplied documents, including spaced paths."""
# ruff: noqa: E402
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from faint import app as entrypoint
from faint.window import Window

app = QApplication.instance() or QApplication([])


class LauncherTests(unittest.TestCase):
    def test_open_path_loads_pixels_and_sets_save_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "테스트 image.png"
            image = QImage(13, 7, QImage.Format.Format_ARGB32)
            image.fill(QColor("red"))
            self.assertTrue(image.save(str(path)))
            window = Window()
            try:
                window.open_path(str(path))
                self.assertEqual(window.path, str(path))
                self.assertEqual(window.doc.size, QSize(13, 7))
                self.assertEqual(window.doc.composite().pixelColor(0, 0), QColor("red"))
                self.assertFalse(window.dirty)
            finally:
                window.close()

    def test_command_line_opens_each_file_in_a_window(self):
        application = MagicMock()
        application.arguments.return_value = ["faint", "/tmp/한글 image.png", "/tmp/other.jpg"]
        application.exec.return_value = 0
        first, second = MagicMock(), MagicMock()
        with (
            patch.object(entrypoint, "QApplication", return_value=application),
            patch.object(entrypoint, "Window", side_effect=[first, second]),
            self.assertRaises(SystemExit) as result,
        ):
            entrypoint.main()
        self.assertEqual(result.exception.code, 0)
        first.open_path.assert_called_once_with("/tmp/한글 image.png")
        second.open_path.assert_called_once_with("/tmp/other.jpg")
        first.show.assert_called_once()
        second.show.assert_called_once()
