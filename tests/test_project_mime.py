"""Custom project defaults must not change image or ZIP handlers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.project_mime import remove_project_associations, set_project_default


class ProjectMimeTests(unittest.TestCase):
    def test_desktop_overrides_and_cleanup_preserve_other_associations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            config.mkdir()
            original = (
                "# existing preferences\n[Default Applications]\n"
                "image/png=viewer.desktop;\napplication/zip=archive.desktop;\n"
                "application/x-faint=archive.desktop;\n"
                "[Added Associations]\napplication/x-faint=io.github.faint.desktop;other.desktop;\n"
                "[Removed Associations]\napplication/x-faint=io.github.faint.desktop;blocked.desktop;\n"
            )
            desktop = config / "kde-mimeapps.list"
            desktop.write_text(original)
            with patch.dict(
                os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_DATA_HOME": str(root / "data")}
            ):
                set_project_default()
                installed = desktop.read_text()
                self.assertIn(
                    "application/x-faint=io.github.faint.desktop;archive.desktop;", installed
                )
                set_project_default()
                self.assertEqual(desktop.read_text(), installed)
                remove_project_associations()
                cleaned = desktop.read_text()
                self.assertNotIn("io.github.faint.desktop", cleaned)
                self.assertIn("application/x-faint=archive.desktop;", cleaned)
                self.assertIn("application/x-faint=other.desktop;", cleaned)
                self.assertIn("application/x-faint=blocked.desktop;", cleaned)
                for line in (
                    "# existing preferences",
                    "image/png=viewer.desktop;",
                    "application/zip=archive.desktop;",
                ):
                    self.assertIn(line, cleaned)
