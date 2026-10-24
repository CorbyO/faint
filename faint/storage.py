"""Raster image and .faint project serialization, without UI side effects.

A project is a ZIP containing document.json and numbered layer PNGs. Preserve
JSON field names and bottom-to-top layer order for existing project files.
Layer names remain in the archive even though the UI only shows thumbnails.
JPEG export flattens onto white at quality 95; PNG preserves composite alpha.
"""

import json
import os
import zipfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter

from .document import Document, Layer
from .i18n import tr
from .imaging import blank

RASTER_FORMATS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".gif": "GIF",
}


def save_gif(image, path):
    """GIF is indexed, single-frame, and supports only binary transparency.

    Reserve one palette entry for transparent pixels instead of letting color
    quantization turn them into opaque black. Qt cannot encode GIF itself.
    """
    from PIL import (
        GifImagePlugin,  # noqa: F401 -- Register the bundled GIF encoder.
        Image,
    )

    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    pixels = Image.frombytes(
        "RGBA",
        (rgba.width(), rgba.height()),
        bytes(rgba.constBits()),
        "raw",
        "RGBA",
        rgba.bytesPerLine(),
    )
    indexed = pixels.convert("RGB").quantize(colors=255)
    transparent = pixels.getchannel("A").point(lambda alpha: 255 if alpha < 128 else 0)
    indexed.paste(255, mask=transparent)
    indexed.save(path, format="GIF", transparency=255, optimize=False)


def load_document(path):
    """Read the existing archive schema or import a raster as one paint layer."""
    if Path(path).suffix.lower() == ".faint":
        with zipfile.ZipFile(path) as archive:
            meta = json.loads(archive.read("document.json"))
            doc = Document(meta["width"], meta["height"])
            doc.layers = []
            for i, layer in enumerate(meta["layers"]):
                image = QImage.fromData(archive.read(f"{i}.png"))
                if image.isNull() or image.size() != doc.size:
                    raise ValueError(tr("ERROR.INVALID_LAYER_IMAGE"))
                doc.layers.append(
                    Layer(
                        layer["name"],
                        image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied),
                        layer["visible"],
                    )
                )
            doc.active = min(max(0, meta.get("active", 0)), len(doc.layers) - 1)
            doc.background_white = bool(meta.get("background_white", False))
    else:
        image = QImage(path)
        if image.isNull():
            raise ValueError(tr("ERROR.READ_IMAGE"))
        doc = Document(image.width(), image.height())
        doc.layers = [
            Layer(Path(path).stem, image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied))
        ]
    return doc


def save_document(doc, path):
    """Serialize beside the destination, replacing it only after success.

    PNG preserves alpha; JPEG composites onto white. Project files preserve
    each layer, active index and the separate background flag."""
    suffix = Path(path).suffix.lower()
    # Write beside the destination, then replace only after serialization succeeds.
    import tempfile

    fd, temporary = tempfile.mkstemp(prefix=".faint-", dir=str(Path(path).absolute().parent))
    os.close(fd)
    try:
        if suffix == ".faint":
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "document.json",
                    json.dumps(
                        {
                            "width": doc.size.width(),
                            "height": doc.size.height(),
                            "active": doc.active,
                            "background_white": doc.background_white,
                            "layers": [
                                {"name": layer.name, "visible": layer.visible}
                                for layer in doc.layers
                            ],
                        },
                        ensure_ascii=False,
                    ),
                )
                for i, layer in enumerate(doc.layers):
                    data = QByteArray()
                    buffer = QBuffer(data)
                    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                    if not layer.image.save(buffer, "PNG"):
                        raise ValueError(tr("ERROR.SAVE_LAYER"))
                    archive.writestr(f"{i}.png", bytes(data))
        elif suffix in RASTER_FORMATS:
            image = doc.composite()
            if suffix in (".jpg", ".jpeg", ".bmp"):
                white = blank(image.width(), image.height())
                white.fill(Qt.GlobalColor.white)
                p = QPainter(white)
                p.drawImage(0, 0, image)
                p.end()
                image = white
            if suffix == ".gif":
                save_gif(image, temporary)
            elif not image.save(temporary, RASTER_FORMATS[suffix], 95):
                raise ValueError(tr("ERROR.SAVE_IMAGE"))
        else:
            raise ValueError(tr("ERROR.SUPPORTED_FORMATS"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
