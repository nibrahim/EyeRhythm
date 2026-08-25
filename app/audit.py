"""
Local settings audit log
========================

Every time the user changes a live setting (ORI threshold, writing angle,
blink sensitivity, …) we append one row with the local date/time, the
setting name, and the old → new values.

File (never uploaded)::

    ~/.eyerhythm_blinkcounter/audit.json
"""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from app.preferences import STORAGE_DIR

AUDIT_FILE = STORAGE_DIR / "audit.json"
MAX_ENTRIES = 400
_lock = threading.RLock()


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _load_raw() -> list[dict[str, Any]]:
    try:
        raw = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if isinstance(raw, dict):
        entries = raw.get("entries", [])
    elif isinstance(raw, list):
        entries = raw
    else:
        return []
    if not isinstance(entries, list):
        return []
    out: list[dict[str, Any]] = []
    for item in entries:
        if isinstance(item, dict) and "at" in item and "setting" in item:
            out.append(item)
    return out


def _write(entries: list[dict[str, Any]]) -> None:
    payload = {"version": 1, "entries": entries[-MAX_ENTRIES:]}
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_FILE.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def record(setting: str, old: Any, new: Any, *, label: str = "") -> None:
    """Append one change. Safe to call from the camera or API thread."""
    entry = {
        "at": _now_iso(),
        "setting": str(setting),
        "from": old,
        "to": new,
    }
    if label:
        entry["label"] = str(label)
    with _lock:
        entries = _load_raw()
        entries.append(entry)
        _write(entries)


def list_entries(limit: int = 40) -> list[dict[str, Any]]:
    """Newest first. ``limit`` 0 → all retained rows."""
    with _lock:
        entries = _load_raw()
    entries.reverse()
    n = int(limit)
    if n > 0:
        return deepcopy(entries[:n])
    return deepcopy(entries)
