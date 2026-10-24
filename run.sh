#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$project_dir"

# Use KDE's system Qt/PySide6 even when a build venv is activated.
exec /usr/bin/python3 -m faint "$@"
