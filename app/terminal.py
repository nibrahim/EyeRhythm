"""
Terminal reporter
=================

Prints the engine's live numbers to stdout for ``--headless`` runs, where
there is no window or browser:

* one line for each counted blink
* one line when the low-ORI Alert turns on or off
* one status line every few seconds

It only reads from the engine, through the same callbacks and snapshot the
Dock icon and the local server use. Diagnostics stay on stderr, so the
numbers can be read alone with ``2>/dev/null``.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable

DEFAULT_INTERVAL_S = 5.0


def _number(value: float | None) -> str:
    """Whole number, or ``--`` while the engine has no value yet."""
    return "--" if value is None else f"{value:.0f}"


def _face_label(snap) -> str:
    """Where the face is, in the engine's own direction words."""
    if not snap.face_found:
        return "no face"
    label = snap.face_direction or "unknown"
    return f"{label} (off-screen)" if snap.off_screen else label


def format_status(snap) -> str:
    """One line for an ``EngineSnapshot``."""
    if not snap.camera_ok:
        return f"camera: {snap.camera_message}"
    parts = [
        f"rate {snap.continuous_bpm:.1f}/min",
        f"avg {snap.average_bpm:.1f}/min",
        f"ORI {_number(snap.ocular_rhythm_index)}",
        f"regularity {_number(snap.regularity)}",
        f"today {snap.blinks_today}",
        f"screen {snap.screen_time}",
        f"fps {snap.fps:.1f}",
        f"face {_face_label(snap)}",
    ]
    if snap.low_light:
        parts.append("low light")
    return "  ".join(parts)


class TerminalReporter:
    """Writes engine events and periodic status lines to the terminal."""

    def __init__(
        self,
        engine,
        *,
        interval_s: float = DEFAULT_INTERVAL_S,
        write: Callable[[str], None] | None = None,
    ) -> None:
        self._engine = engine
        self._interval_s = interval_s
        self._write = write or self._print
        # Blinks and status lines arrive on different threads.
        self._lock = threading.Lock()
        # Counted here because a pulse can fire before the snapshot updates.
        self._blinks = 0

    def bind(self) -> None:
        """Subscribe to the engine. Call before ``engine.start()``."""
        self._engine.on_blink_pulse(self._on_blink)
        self._engine.on_alert_active_change(self._on_alert)

    def report_status(self) -> None:
        self._emit(format_status(self._engine.snapshot()))

    def run(self) -> None:
        """Print status lines until interrupted."""
        while True:
            time.sleep(self._interval_s)
            self.report_status()

    def _on_blink(self) -> None:
        with self._lock:
            self._blinks += 1
            count = self._blinks
        self._emit(f"blink {count}")

    def _on_alert(self, active: bool) -> None:
        self._emit("ALERT: blink rhythm is low" if active else "alert cleared")

    def _emit(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._write(f"{stamp}  {text}")

    @staticmethod
    def _print(line: str) -> None:
        """Never crash the engine's threads if the terminal is gone."""
        try:
            print(line, flush=True)
        except OSError:
            pass
