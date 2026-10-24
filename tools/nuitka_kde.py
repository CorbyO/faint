"""Run pinned Nuitka with locally extracted headers for the system Python."""
import os
from pathlib import Path
import runpy
import site
import sys

# -S prevents Nuitka's re-execution from dropping the header override. Rebuild
# the regular venv import paths explicitly, including system PySide6.
site.main()

header_dir = Path(os.environ['FAINT_PYTHON_HEADERS']).resolve()
if not (header_dir / 'Python.h').is_file():
    raise SystemExit(f'Missing Python.h: {header_dir}')

import nuitka.PythonVersions

# Nuitka 4.3.1 searches only /usr/include. Supply an equivalent directory from
# the matching distro development RPM without installing it into the host OS.
def local_include_path(**kwargs):
    return str(header_dir)

nuitka.PythonVersions.getTargetPythonIncludePath = local_include_path
runpy.run_module('nuitka', run_name='__main__', alter_sys=True)
