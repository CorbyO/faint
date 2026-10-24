"""Manage only Faint's project association; leave image and archive defaults alone."""

import os
from pathlib import Path

MIME = "application/x-faint"
DESKTOP = "io.github.faint.desktop"


def association_files():
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return config / "mimeapps.list", sorted(
        {
            *config.glob("*mimeapps.list"),
            *(data / "applications").glob("*mimeapps.list"),
        }
    )


def update_file(path, install=False):
    """Edit just our MIME entry, preserving comments and unrelated preferences."""
    lines = path.read_text().splitlines(keepends=True) if path.exists() else []
    result = []
    section = ""
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        if section in ("Default Applications", "Added Associations", "Removed Associations"):
            key, separator, value = line.partition("=")
            if separator and key.strip() == MIME:
                apps = [app for app in value.strip().split(";") if app and app != DESKTOP]
                if install and section == "Default Applications":
                    apps.insert(0, DESKTOP)
                    found = True
                if apps:
                    result.append(f"{MIME}={';'.join(apps)};\n")
                continue
        result.append(line)
    if install and not found:
        # Reuse an existing defaults section rather than creating a duplicate.
        index = next(
            (i + 1 for i, line in enumerate(result) if line.strip() == "[Default Applications]"),
            None,
        )
        entry = f"{MIME}={DESKTOP};\n"
        if index is None:
            if result and not result[-1].endswith("\n"):
                result[-1] += "\n"
            result.extend(["\n[Default Applications]\n", entry])
        else:
            result.insert(index, entry)
    content = "".join(result)
    if content != "".join(lines):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def set_project_default():
    primary, existing = association_files()
    update_file(primary, install=True)
    # Desktop-specific user defaults take precedence over the generic file.
    for path in existing:
        if path != primary and path.name != "mimeapps.list":
            update_file(path, install=True)


def remove_project_associations():
    _, existing = association_files()
    for path in existing:
        update_file(path)


if __name__ == "__main__":
    remove_project_associations()
