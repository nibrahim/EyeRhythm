"""
PyInstaller runtime hook — Windows only.

Downloaded zips carry a Mark-of-the-Web (Zone.Identifier) on every extracted
file. The .NET Framework then refuses to load ``Python.Runtime.dll``, and
pywebview cannot open a desktop window:

    Failed to resolve Python.Runtime.Loader.Initialize from ...\\Python.Runtime.dll

This runs *before* application code, so pythonnet never sees a blocked DLL.
Safe to include in the Mac freeze as well: it returns immediately there.
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


_run()
