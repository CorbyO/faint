#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_dir"
mode="${1:-standalone}"
system_python="${FAINT_SYSTEM_PYTHON:-/usr/bin/python3}"
"$system_python" -c 'from PySide6.QtCore import qVersion; print("Building with system Qt", qVersion())'
build_venv="$project_dir/.venv-build-kde"
if [[ ! -x "$build_venv/bin/python" ]]; then
    "$system_python" -m venv --system-site-packages "$build_venv"
fi
build_python="$build_venv/bin/python"
export PATH="$build_venv/bin:$PATH"
# Do not install PySide6 from pip: the system Qt and KDE plugins must stay together.
"$build_python" -m pip install 'nuitka==4.3.1' ordered-set zstandard patchelf 'Pillow>=10.1'
header_dir="$("$build_python" -c 'import sysconfig; print(sysconfig.get_path("include"))')"
if [[ ! -f "$header_dir/Python.h" ]]; then
    if ! command -v dnf >/dev/null || ! command -v rpm2cpio >/dev/null || ! command -v cpio >/dev/null; then
        echo "Install the development headers matching $system_python to preserve system KDE styling." >&2
        exit 1
    fi
    package="$(rpm -q --qf 'python3-devel-%{VERSION}-%{RELEASE}.%{ARCH}' python3)"
    rpm_dir="$project_dir/.build-tools/rpms"
    header_root="$project_dir/.build-tools/headers/$package"
    mkdir -p "$rpm_dir" "$header_root"
    if [[ ! -f "$rpm_dir/$package.rpm" ]]; then
        dnf --setopt=cachedir="$project_dir/.build-tools/dnf-cache" \
            --setopt=logdir="$project_dir/.build-tools/dnf-logs" \
            download --destdir="$rpm_dir" "$package"
    fi
    if [[ ! -f "$header_root$header_dir/Python.h" ]]; then
        rpm2cpio "$rpm_dir/$package.rpm" | cpio -idm --quiet --no-absolute-filenames --directory="$header_root"
    fi
    original_include="$header_dir"
    header_dir="$header_root$original_include"
    for config in "$original_include"/pyconfig-*.h; do
        [[ ! -f "$config" ]] || cp -- "$config" "$header_dir/"
    done
fi
# python3-devel normally supplies the unversioned linker name. Recreate it
# locally when only the runtime .so.1.0 is installed on the immutable host.
link_dir="$project_dir/.build-tools/kde-link"
mkdir -p "$link_dir"
"$build_python" - "$link_dir" <<'PYTHON'
from pathlib import Path
import sys, sysconfig
source = Path(sysconfig.get_config_var('LIBDIR')) / sysconfig.get_config_var('INSTSONAME')
if not source.is_file():
    raise SystemExit(f'Missing Python runtime library: {source}')
target = Path(sys.argv[1]) / sysconfig.get_config_var('LDLIBRARY')
if target.is_symlink():
    target.unlink()
if not target.exists():
    target.symlink_to(source)
PYTHON
export LDFLAGS="-L'$link_dir' ${LDFLAGS:-}"
export FAINT_PYTHON_HEADERS="$header_dir"
export PYTHONHASHSEED=0
# Separate build caches from the previous pip-Qt build.
qt_translation_flags=()
qt_korean_catalog="$("$build_python" -c 'from pathlib import Path; from PySide6.QtCore import QLibraryInfo; print(Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)) / "qtbase_ko.qm")')"
if [[ -f "$qt_korean_catalog" ]]; then
    qt_translation_flags+=("--include-data-files=$qt_korean_catalog=faint_translations/qtbase_ko.qm")
fi
"$build_python" -S -X frozen_modules=off "$project_dir/tools/nuitka_kde.py" \
    --mode="$mode" \
    "${qt_translation_flags[@]}" \
    --include-data-files="$project_dir/assets/faint.svg=assets/faint.svg" \
    --enable-plugin=pyside6 \
    --user-package-configuration-file="$project_dir/tools/kde.nuitka-package.config.yml" \
    --include-qt-plugins=styles,platformthemes \
    --output-dir="$project_dir/dist" \
    --output-filename=faint \
    --assume-yes-for-downloads \
    "$project_dir/run_faint.py"
if [[ "$mode" == standalone ]]; then
    echo "KDE build complete: $project_dir/dist/run_faint.dist/faint"
    echo "Distribute the entire dist/run_faint.dist directory."
else
    echo "KDE build complete: $project_dir/dist/faint"
fi
