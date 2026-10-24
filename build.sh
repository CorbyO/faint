#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$project_dir"

mode="${1:-standalone}"
case "$mode" in
    standalone|onefile) ;;
    -h|--help)
        echo "Usage: ./build.sh [standalone|onefile]"
        echo "Default: KDE standalone using system Python/PySide6 and GCC or Clang."
        echo "Missing Fedora Python headers are extracted locally from the matching RPM."
        echo "Set FAINT_KDE=0 for the generic pip-Qt build (uses uv if needed)."
        exit 0
        ;;
    *)
        echo "Unknown build mode: $mode" >&2
        echo "Usage: ./build.sh [standalone|onefile]" >&2
        exit 2
        ;;
esac
if (( $# > 1 )); then
    echo "Usage: ./build.sh [standalone|onefile]" >&2
    exit 2
fi

# Build notes kept here rather than in the project introduction:
# - The KDE branch uses .venv-build-kde with system site-packages. Do not mix
#   pip Qt with distro KDE plugins, even at the same reported Qt version:
#   private ABI symbols can differ. tools/build_kde.sh keeps that set together.
# - The generic branch below installs tools in .venv-build, falls back to a
#   uv-managed Python in .build-tools/python when headers are missing, and uses
#   .venv-build-native for that interpreter. No system package install is needed.
# - Both modes write to dist; onefile writes dist/faint and uses a temporary
#   extraction directory at launch. Folder builds require their full .dist tree.
# The default build uses the same system PySide6/Qt as run.sh.
# FAINT_KDE=0 retains the generic pip-Qt build for non-KDE targets.
if [[ "${FAINT_KDE:-1}" == 1 ]]; then
    exec bash "$project_dir/tools/build_kde.sh" "$mode"
fi

build_venv="$project_dir/.venv-build"
if [[ ! -x "$build_venv/bin/python" ]]; then
    "${PYTHON:-python3}" -m venv "$build_venv"
fi
build_python="$build_venv/bin/python"

has_python_headers() {
    "$1" -c 'import pathlib, sysconfig; raise SystemExit(not (pathlib.Path(sysconfig.get_path("include")) / "Python.h").is_file())'
}

if ! has_python_headers "$build_python"; then
    echo "Python development headers are missing; preparing a project-local Python 3.12."
    if [[ ! -x "$build_venv/bin/uv" ]]; then
        "$build_python" -m pip install uv
    fi
    build_uv="$build_venv/bin/uv"
    export UV_PYTHON_INSTALL_DIR="$project_dir/.build-tools/python"
    export UV_CACHE_DIR="$project_dir/.build-tools/uv-cache"
    "$build_uv" python install --no-bin 3.12
    managed_python="$("$build_uv" python find --managed-python 3.12)"
    build_venv="$project_dir/.venv-build-native"
    if [[ ! -x "$build_venv/bin/python" ]]; then
        "$managed_python" -m venv "$build_venv"
    fi
    build_python="$build_venv/bin/python"
fi
if ! has_python_headers "$build_python"; then
    echo "Python.h is still missing for $build_python" >&2
    exit 1
fi
export PATH="$build_venv/bin:$PATH"

# Install the Linux helper in the build venv, without changing system packages.
if [[ "$(uname -s)" == Linux ]] && ! command -v patchelf >/dev/null 2>&1; then
    "$build_python" -m pip install --only-binary=:all: patchelf
fi
if [[ "$(uname -s)" == Linux ]]; then
    patchelf --version
fi

"$build_python" -m pip install -e "$project_dir"
"$build_python" -m pip install nuitka ordered-set zstandard
qt_translation_flags=()
qt_korean_catalog="$("$build_python" -c 'from pathlib import Path; from PySide6.QtCore import QLibraryInfo; print(Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)) / "qtbase_ko.qm")')"
if [[ -f "$qt_korean_catalog" ]]; then
    qt_translation_flags+=("--include-data-files=$qt_korean_catalog=faint_translations/qtbase_ko.qm")
fi
"$build_python" -m nuitka \
    --mode="$mode" \
    "${qt_translation_flags[@]}" \
    --include-data-files="$project_dir/assets/faint.svg=assets/faint.svg" \
    --enable-plugin=pyside6 \
    --output-dir="$project_dir/dist" \
    --output-filename=faint \
    "$project_dir/run_faint.py"

if [[ "$mode" == standalone ]]; then
    echo "Build complete: $project_dir/dist/run_faint.dist/faint"
    echo "Distribute the entire dist/run_faint.dist directory."
else
    echo "Build complete: $project_dir/dist/faint"
fi
