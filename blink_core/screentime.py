"""
Daily screen-time + blink tracker.

Silently accumulates how long the user has been in front of the screen
(a face is visible to the webcam while the app runs) and the total number
of blinks counted that day.

Rules:
  - NOT affected by the blink-counter reset key (R).
  - Persists across app restarts (JSON file in the user's home folder).
  - Automatically resets to zero when the calendar day changes
    (i.e. at 12 midnight local time), even while the app is running.
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

STORAGE_DIR = Path.home() / ".eyerhythm_blinkcounter"
STORAGE_FILE = STORAGE_DIR / "screentime.json"
SAVE_EVERY_S = 15.0     # flush to disk at most this often
MAX_GAP_S = 2.0         # ignore gaps longer than this (app paused/closed)


class ScreenTimeTracker:
    def __init__(self, storage_file: Path | str = STORAGE_FILE):
        self._file = Path(storage_file)
        self._today = date.today().isoformat()
        self._seconds = 0.0
        self._blinks = 0
        self._last_tick: float | None = None
        self._last_save = 0.0
        self._load()

    # ------------------------------------------------------------------ API

    def tick(self, face_present: bool) -> None:
        """Call once per processed frame."""
        self._rollover_if_new_day()
        now = time.monotonic()
        if face_present:
            if self._last_tick is not None:
                delta = now - self._last_tick
                if 0 < delta <= MAX_GAP_S:
                    self._seconds += delta
            self._last_tick = now
        else:
            self._last_tick = None

        if time.time() - self._last_save >= SAVE_EVERY_S:
            self.save()

    def add_blink(self) -> None:
        """Record one counted blink for the daily total (call on blink_just_counted)."""
        self._rollover_if_new_day()
        self._blinks += 1
        self.save()  # flush immediately so a crash still keeps the count

    @property
    def seconds_today(self) -> float:
        self._rollover_if_new_day()
        return self._seconds

    @property
    def blinks_today(self) -> int:
        self._rollover_if_new_day()
        return self._blinks

    @property
    def avg_blinks_per_minute(self) -> float:
        """Total blinks today / screen-time minutes. 0 when no screen time yet."""
        secs = self.seconds_today
        if secs < 1.0:
            return 0.0
        return self.blinks_today * 60.0 / secs

    def formatted(self) -> str:
        """e.g. '1h 24m' or '12m'."""
        total_m = int(self.seconds_today // 60)
        h, m = divmod(total_m, 60)
        return f"{h}h {m:02d}m" if h else f"{m}m"

    def save(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(json.dumps({
                "date": self._today,
                "seconds": round(self._seconds, 1),
                "blinks": int(self._blinks),
            }))
            self._last_save = time.time()
        except OSError:
            pass  # never crash the app over stats persistence

    # ------------------------------------------------------------ internals

    def _load(self) -> None:
        try:
            data = json.loads(self._file.read_text())
            if data.get("date") == self._today:
                self._seconds = float(data.get("seconds", 0.0))
                self._blinks = int(data.get("blinks", 0))
        except (OSError, ValueError):
            pass  # first run or corrupt file -> start at zero

    def _rollover_if_new_day(self) -> None:
        today = date.today().isoformat()
        if today != self._today:      # midnight passed
            self._today = today
            self._seconds = 0.0
            self._blinks = 0
            self.save()
