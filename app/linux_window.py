"""
Linux desktop window checks
===========================

pywebview draws the Linux window with Qt (PySide6). Three things need
handling before it starts:

* ``opencv-python`` bundles its own Qt plugins and points
  ``QT_QPA_PLATFORM_PLUGIN_PATH`` at them on import, so Qt loads the wrong ones.
* Qt on X11 needs the system library ``libxcb-cursor``. Without it Qt aborts
  the whole process, which the browser fallback cannot catch, so check first.
* pywebview tries GTK first and logs a traceback when it is not installed.
"""

from __future__ import annotations

import ctypes.util
import importlib.util
import os
import sys


def _clear_opencv_qt_paths() -> None:
    """Undo what ``import cv2`` set, leaving any value the user chose."""
    for name in ("QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_FONTDIR"):
        if "cv2" in os.environ.get(name, ""):
            del os.environ[name]


def _uses_qt() -> bool:
    """False when GTK is available and pywebview would pick it first."""
    wanted = os.environ.get("PYWEBVIEW_GUI", "").lower()
    if wanted:
        return wanted != "gtk"
    if "KDE_FULL_SESSION" in os.environ:
        return True
    return importlib.util.find_spec("gi") is None


def prepare_window() -> str | None:
    """
    Get the environment ready for the desktop window.

    Returns why the window cannot open, or None when it should work.
    """
    if not sys.platform.startswith("linux"):
        return None
    _clear_opencv_qt_paths()
    if not _uses_qt():
        return None
    os.environ.setdefault("PYWEBVIEW_GUI", "qt")

    wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
    )
    x11 = bool(os.environ.get("DISPLAY"))
    if not wayland and not x11:
        return "no graphical session found"

    qt_platform = os.environ.get("QT_QPA_PLATFORM", "")
    uses_xcb = qt_platform.startswith("xcb") or (not qt_platform and not wayland)
    if uses_xcb and ctypes.util.find_library("xcb-cursor") is None:
        return "Qt on X11 needs libxcb-cursor (on Debian or Ubuntu: sudo apt install libxcb-cursor0)"
    return None
