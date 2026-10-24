"""Exercise installation and upgrades without compiling or changing user settings."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from shutil import copy2


class InstallTests(unittest.TestCase):
    def test_install_upgrade_and_failed_build(self):
        project = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "source tree"
            (checkout / "tools").mkdir(parents=True)
            (checkout / "assets").mkdir()
            copy2(project / "assets/faint.svg", checkout / "assets/faint.svg")
            copy2(project / "assets/faint-mime.xml", checkout / "assets/faint-mime.xml")
            copy2(project / "tools/project_mime.py", checkout / "tools/project_mime.py")
            copy2(project / "install.sh", checkout / "install.sh")
            copy2(project / "tools/install_desktop.py", checkout / "tools/install_desktop.py")
            build = checkout / "build.sh"
            build.write_text(
                "#!/bin/bash\nset -eu\n"
                '[ "$1" = onefile ]\n'
                '[ "${INSTALL_TEST_FAIL:-0}" = 0 ]\n'
                'cd -- "$(dirname -- "$0")"\nmkdir -p dist\n'
                'printf "%s" "$INSTALL_TEST_VERSION" > dist/faint\n'
            )
            build.chmod(0o755)
            commands = root / "commands"
            commands.mkdir()
            for name in ("update-desktop-database", "kbuildsycoca6", "update-mime-database"):
                stub = commands / name
                stub.write_text("#!/bin/sh\nexit 0\n")
                stub.chmod(0o755)
            destination = root / "installed apps"
            environment = {
                **os.environ,
                "FAINT_INSTALL_DIR": str(destination),
                "XDG_DATA_HOME": str(root / "app data"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "PATH": str(commands) + os.pathsep + os.environ["PATH"],
                "INSTALL_TEST_VERSION": "first",
            }
            command = ["bash", str(checkout / "install.sh")]
            subprocess.run(command, env=environment, check=True, capture_output=True)
            binary = destination / "faint"
            self.assertEqual(binary.read_text(), "first")
            self.assertTrue(os.access(binary, os.X_OK))
            entry = root / "app data/applications/io.github.faint.desktop"
            self.assertIn(f'Exec="{binary}" %F', entry.read_text())
            self.assertIn("MimeType=image/png;image/jpeg;", entry.read_text())
            self.assertIn("Icon=io.github.faint", entry.read_text())
            icon = root / "app data/icons/hicolor/scalable/apps/io.github.faint.svg"
            self.assertEqual(icon.read_bytes(), (project / "assets/faint.svg").read_bytes())
            associations = root / "config/mimeapps.list"
            self.assertIn("application/x-faint=io.github.faint.desktop;", associations.read_text())
            self.assertTrue((root / "app data/mime/packages/io.github.faint.xml").exists())
            environment["INSTALL_TEST_VERSION"] = "second"
            subprocess.run(command, env=environment, check=True, capture_output=True)
            self.assertEqual(binary.read_text(), "second")
            environment["INSTALL_TEST_FAIL"] = "1"
            result = subprocess.run(command, env=environment, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(binary.read_text(), "second")
            self.assertEqual(list(destination.glob(".faint-install.*")), [])

    def test_uninstall_preserves_other_files_and_can_be_repeated(self):
        script = Path(__file__).resolve().parent.parent / "uninstall.sh"
        for custom in (False, True):
            with self.subTest(custom=custom), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                binary_dir = root / ("custom bin" if custom else ".local/bin")
                data = root / ("custom data" if custom else ".local/share")
                applications = data / "applications"
                binary_dir.mkdir(parents=True)
                applications.mkdir(parents=True)
                binary = binary_dir / "faint"
                desktop = applications / "io.github.faint.desktop"
                binary.write_text("binary")
                desktop.write_text("launcher")
                icon = data / "icons/hicolor/scalable/apps/io.github.faint.svg"
                icon.parent.mkdir(parents=True)
                icon.write_text("icon")
                package = data / "mime/packages/io.github.faint.xml"
                package.parent.mkdir(parents=True)
                package.write_text("mime definition")
                config = root / ".config/mimeapps.list"
                config.parent.mkdir()
                config.write_text(
                    "# preserve comment\n[Default Applications]\n"
                    "application/x-faint=io.github.faint.desktop;other.desktop;\n"
                    "image/png=viewer.desktop;\napplication/zip=archive.desktop;\n"
                )
                preserved = [
                    binary_dir / "other-app",
                    applications / "other.desktop",
                    root / "art.png",
                ]
                for path in preserved:
                    path.write_text("preserve")
                commands = root / "commands"
                commands.mkdir()
                for name in ("update-desktop-database", "kbuildsycoca6", "update-mime-database"):
                    stub = commands / name
                    stub.write_text("#!/bin/sh\nexit 0\n")
                    stub.chmod(0o755)
                environment = {
                    key: value
                    for key, value in os.environ.items()
                    if key not in ("FAINT_INSTALL_DIR", "XDG_DATA_HOME", "XDG_CONFIG_HOME")
                }
                environment.update(
                    HOME=str(root), PATH=str(commands) + os.pathsep + os.environ["PATH"]
                )
                if custom:
                    environment.update(FAINT_INSTALL_DIR=str(binary_dir), XDG_DATA_HOME=str(data))
                for _ in range(2):
                    subprocess.run(
                        ["bash", str(script)], env=environment, check=True, capture_output=True
                    )
                self.assertFalse(binary.exists())
                self.assertFalse(desktop.exists())
                self.assertFalse(icon.exists())
                self.assertFalse(package.exists())
                self.assertNotIn("io.github.faint.desktop", config.read_text())
                self.assertIn("application/x-faint=other.desktop;", config.read_text())
                self.assertIn("image/png=viewer.desktop;", config.read_text())
                self.assertIn("application/zip=archive.desktop;", config.read_text())
                self.assertIn("# preserve comment", config.read_text())
                for path in preserved:
                    self.assertEqual(path.read_text(), "preserve")
