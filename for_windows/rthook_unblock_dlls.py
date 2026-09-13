"""
PyInstaller runtime hook — Windows only.

1. Strip Mark-of-the-Web (Zone.Identifier) from DLLs so pythonnet / OpenCV /
   NumPy can load after a downloaded Setup or zip.
2. Register ``os.add_dll_directory`` for ``_internal`` and ``*.libs`` folders.
   Python 3.8+ ignores PATH for extension DLLs; without this, NumPy fails with
   ``DLL load failed while importing _multiarray_umath``.

Safe to include in the Mac freeze: it returns immediately there.
"""

from __future__ import annotations

import os
import sys


def _unblock_tree(root: str) -> None:
    if not root or not os.path.isdir(root):
        return
    try:
        delete_file = __import__("ctypes").windll.kernel32.DeleteFileW
    except Exception:
        return
    for dirpath, _dirs, filenames in os.walk(root):
        for name in filenames:
            lower = name.lower()
            if not lower.endswith((".dll", ".exe", ".pyd")):
                continue
            ads = os.path.join(dirpath, name) + ":Zone.Identifier"
            try:
                delete_file(ads)
            except Exception:
                pass


def _add_dll_dirs(root: str) -> None:
    if sys.platform != "win32" or not root or not os.path.isdir(root):
        return
    add = getattr(os, "add_dll_directory", None)
    if add is None:
        return
    seen: set[str] = set()

    def _add(path: str) -> None:
        if not path or not os.path.isdir(path):
            return
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            return
        seen.add(key)
        try:
            add(path)
        except (OSError, ValueError):
            pass

    _add(root)
    try:
        for name in os.listdir(root):
            full = os.path.join(root, name)
            if not os.path.isdir(full):
                continue
            lower = name.lower()
            if lower.endswith(".libs") or lower in {"cv2", "numpy", "mediapipe", "webview"}:
                _add(full)
    except OSError:
        pass
    for sub in (
        "numpy.libs",
        "cv2",
        os.path.join("cv2", ".libs"),
        os.path.join("webview", "lib"),
    ):
        _add(os.path.join(root, sub))


def _run() -> None:
    if sys.platform != "win32":
        return
    roots = []
    exe = getattr(sys, "executable", "") or ""
    if exe:
        roots.append(os.path.dirname(os.path.abspath(exe)))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(str(meipass))
    seen: set[str] = set()
    for root in roots:
        key = os.path.normcase(os.path.abspath(root))
        if key in seen:
            continue
        seen.add(key)
        _unblock_tree(root)
        _add_dll_dirs(root)


_run()
