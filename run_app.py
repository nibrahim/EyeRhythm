"""
EyeRhythm packaging entry-point
===============================

Plain-language goal
-------------------
When developers run from source they often type::

    python -m app.main

When we **package** the app with PyInstaller (Mac ``.app`` or Windows ``.exe``),
the frozen binary needs a single simple script as its entry file. That is
this file: ``run_app.py``.

Why not point PyInstaller at ``app/main.py`` directly?
------------------------------------------------------
This wrapper adds **crash logging**. A windowed app has no visible terminal.
If something fails during import or startup, the user would only see the
window disappear. Here we catch Python exceptions, write a readable log, then
re-raise so the process still exits with an error code.

Where is the crash log?
-----------------------
* Windows: ``%LOCALAPPDATA%\\EyeRhythm\\crash.log``
* macOS: ``~/Library/Logs/EyeRhythm_crash.log`` (if that Logs folder exists)
* otherwise: ``~/EyeRhythm_crash.log``

Note
----
This only catches **Python** exceptions. A native MediaPipe/OpenCV segfault
will still kill the process without a Python traceback.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _log_path() -> Path:
    """
    Choose a sensible place to write a crash report.

    * Windows: ``%LOCALAPPDATA%\\EyeRhythm\\crash.log``
    * macOS: ``~/Library/Logs/EyeRhythm_crash.log`` when that folder exists
    * otherwise: ``~/EyeRhythm_crash.log``
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "EyeRhythm" / "crash.log"
    home = Path.home()
    logs = home / "Library" / "Logs"
    if logs.is_dir():
        return logs / "EyeRhythm_crash.log"
    return home / "EyeRhythm_crash.log"


def _write_crash(exc: BaseException) -> None:
    """
    Best-effort write of a full Python traceback to disk (and stderr).

    Never raises: logging must not hide or replace the original error.
    """
    try:
        path = _log_path()
        # Ensure parent directory exists (e.g. first run on a fresh machine).
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "EyeRhythm failed to start.\n\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        )
        # Also print if a terminal is attached (useful for developers).
        print(f"EyeRhythm crash log: {path}", file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
    except Exception:
        # If even logging fails (disk full, permissions), give up quietly.
        pass


def main() -> None:
    """Import and run the real application entrypoint."""
    # Local import keeps this module light until we actually start the app
    # (and makes crash logging wrap import failures too when used carefully).
    from app.main import main as app_main
    app_main()


if __name__ == "__main__":
    # When this file is executed as a script (or as the PyInstaller entry),
    # wrap the whole startup in a safety net for Python exceptions.
    try:
        main()
    except SystemExit:
        # sys.exit(n) should still work normally — do not treat it as a crash.
        raise
    except BaseException as e:
        # KeyboardInterrupt is a BaseException too; we still log unexpected ones.
        _write_crash(e)
        raise
