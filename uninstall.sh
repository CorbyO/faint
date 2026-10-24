#!/usr/bin/env bash
# Remove only the installed executable and launcher, preserving artwork/settings.
set -euo pipefail

if (( $# != 0 )); then
    echo "Usage: ./uninstall.sh" >&2
    exit 2
fi

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

install_dir="${FAINT_INSTALL_DIR:-$HOME/.local/bin}"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
applications_dir="$data_dir/applications"
rm -f -- "$install_dir/faint"
# Removing the MIME-advertising desktop entry unregisters image/project Open With.
rm -f -- "$applications_dir/io.github.faint.desktop"
rm -f -- "$data_dir/icons/hicolor/scalable/apps/io.github.faint.svg"

rm -f -- "$data_dir/mime/packages/io.github.faint.xml"
/usr/bin/python3 "$project_dir/tools/project_mime.py"
if [[ -d "$data_dir/mime" ]] && command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database "$data_dir/mime"
fi

# Cache helpers are optional on desktops other than KDE. A missing applications
# directory means there is no application database to refresh.
if [[ -d "$applications_dir" ]] && command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$applications_dir"
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6
fi

echo "Faint uninstalled and removed from app search and image/project Open With lists."
echo "Saved images, source files and preferences were preserved."
