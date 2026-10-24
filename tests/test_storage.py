"""Persistence contracts that must survive internal code reorganization."""
# ruff: noqa: E402 -- Keep localized error assertions deterministic.

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ["FAINT_LANGUAGE"] = "ko"

from PySide6.QtGui import QColor, QImage

from faint.document import Document
from faint.storage import load_document, save_document


class StorageTests(unittest.TestCase):
    def test_existing_project_schema_and_hidden_layers(self):
        document = Document(11, 9)
        document.layers[0].name = "기존 이름"
        document.layers[0].visible = False
        document.layers[0].image.setPixelColor(3, 4, QColor("#80ff0000"))
        document.background_white = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layers.faint"
            save_document(document, str(path))
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.namelist(), ["document.json", "0.png"])
                metadata = json.loads(archive.read("document.json"))
                self.assertEqual(
                    metadata,
                    {
                        "width": 11,
                        "height": 9,
                        "active": 0,
                        "background_white": True,
                        "layers": [{"name": "기존 이름", "visible": False}],
                    },
                )
            restored = load_document(str(path))
        self.assertTrue(restored.background_white)
        self.assertFalse(restored.layers[0].visible)
        self.assertEqual(restored.layers[0].image, document.layers[0].image)

    def test_failed_encoding_preserves_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.png"
            path.write_bytes(b"existing destination")
            with patch.object(QImage, "save", return_value=False):
                with self.assertRaisesRegex(ValueError, "이미지 저장 실패"):
                    save_document(Document(4, 4), str(path))
            self.assertEqual(path.read_bytes(), b"existing destination")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_export_alpha_and_white_jpeg_background(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Document(4, 4)
            for suffix in ("png", "jpg"):
                path = Path(directory) / ("drawing." + suffix)
                save_document(document, str(path))
                color = QImage(str(path)).pixelColor(0, 0)
                if suffix == "png":
                    self.assertEqual(color.alpha(), 0)
                else:
                    self.assertEqual(color, QColor("white"))

    def test_all_raster_formats_round_trip(self):
        document = Document(12, 10)
        document.layers[0].image.setPixelColor(4, 3, QColor("red"))
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
                with self.subTest(suffix=suffix):
                    path = Path(directory) / ("drawing." + suffix)
                    save_document(document, str(path))
                    restored = load_document(str(path))
                    self.assertEqual(restored.size, document.size)
                    pixel = restored.composite().pixelColor(4, 3)
                    self.assertGreater(pixel.red(), pixel.blue())
                    if suffix in ("png", "webp", "gif"):
                        self.assertEqual(restored.composite().pixelColor(0, 0).alpha(), 0)
                    else:
                        background = restored.composite().pixelColor(0, 0)
                        self.assertEqual(background.alpha(), 255)
                        self.assertGreaterEqual(
                            min(background.red(), background.green(), background.blue()), 245
                        )

    def test_animated_gif_opens_first_frame(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "animation.gif"
            first = Image.new("RGB", (6, 5), "red")
            second = Image.new("RGB", (6, 5), "blue")
            first.save(path, save_all=True, append_images=[second], duration=100, loop=0)
            document = load_document(str(path))
            self.assertEqual(document.composite().pixelColor(0, 0), QColor("red"))
