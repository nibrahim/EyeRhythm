"""Thin entry-point used by PyInstaller (and for local runs).

When packaged as a windowed .app, stdout/stderr are invisible, so any
startup crash is written to a log file the user can open.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path


def _log_path() -> Path:
    # ~/Library/Logs on macOS, else home
    home = Path.home()
    logs = home / "Library" / "Logs"
    if logs.is_dir():
        return logs / "EyeRhythm_crash.log"
    return home / "EyeRhythm_crash.log"


def _write_crash(exc: BaseException) -> None:
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "EyeRhythm failed to start.\n\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        )
        # also try stderr in case we're launched from Terminal
        print(f"EyeRhythm crash log: {path}", file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
    except Exception:
        pass


def main() -> None:
    from app.main import main as app_main
    app_main()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:
        _write_crash(e)
        raise
