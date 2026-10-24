#!/usr/bin/env bash
# Build and install for the current user; never require sudo or change defaults.
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if (( $# != 0 )); then
    echo "Usage: ./install.sh" >&2
    exit 2
fi

"$project_dir/build.sh" onefile

# Install a self-contained binary outside the checkout. Atomic replacement also
# permits reinstalling while the previous executable is running.
install_dir="${FAINT_INSTALL_DIR:-$HOME/.local/bin}"
mkdir -p -- "$install_dir"
install_dir="$(cd -- "$install_dir" && pwd)"
install_temp="$(mktemp "$install_dir/.faint-install.XXXXXX")"
trap 'rm -f -- "$install_temp"' EXIT
install -m 755 -- "$project_dir/dist/faint" "$install_temp"
mv -f -- "$install_temp" "$install_dir/faint"

# Register app search and image/project Open With entries, then refresh desktop caches.
/usr/bin/python3 "$project_dir/tools/install_desktop.py" "$install_dir/faint"
echo "Installed: $install_dir/faint"
echo "Search for Faint in your application menu or choose Open With > Faint for images."
