#!/usr/bin/env python3
"""Register Faint and its project format; preserve raster image defaults."""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from project_mime import set_project_default


def desktop_quote(value):
    # Desktop Exec escaping differs from shell quoting; '%' is a field code.
    value = str(value).replace("%", "%%")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return '"' + value + '"'


def main():
    project = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", nargs="?", type=Path, default=project / "dist/faint")
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        parser.error("Choose an executable Faint binary or run.sh")
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    applications = data / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    icon_directory = data / "icons" / "hicolor" / "scalable" / "apps"
    icon_directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project / "assets/faint.svg", icon_directory / "io.github.faint.svg")
    packages = data / "mime" / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project / "assets/faint-mime.xml", packages / "io.github.faint.xml")
    subprocess.run(["update-mime-database", str(data / "mime")], check=True)
    entry = applications / "io.github.faint.desktop"
    entry.write_text(
        "[Desktop Entry]\nType=Application\nName=Faint\n"
        "Comment=Lightweight layered paint editor\n"
        "Comment[ko]=가벼운 레이어 그림판\n"
        f"Exec={desktop_quote(executable)} %F\n"
        "Icon=io.github.faint\nTerminal=false\n"
        "Categories=Graphics;2DGraphics;RasterGraphics;\n"
        "MimeType=image/png;image/jpeg;image/webp;image/bmp;image/gif;application/x-faint;\nStartupNotify=true\n",
        encoding="utf-8",
    )
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(applications)], check=True)
    set_project_default()
    # KDE uses its own service cache for app search and Open With menus.
    if shutil.which("kbuildsycoca6"):
        subprocess.run(["kbuildsycoca6"], check=True)
    print(f"Registered Faint: {entry}\nExecutable: {executable}")


if __name__ == "__main__":
    main()
