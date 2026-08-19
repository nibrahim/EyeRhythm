"""
Daily screen-time + blink tracker
=================================

Plain-language goal
-------------------
While EyeRhythm is running, we want two simple daily numbers:

1. **How long** was a face visible in front of the camera?  (“screen time”)
2. **How many blinks** did we count during that time?

We also show **average blinks per minute** = blinks ÷ (screen-time minutes).

Why this exists separately from the session blink counter
---------------------------------------------------------
The detector has its own in-memory blink count for the current run. This module
is different: it is the **calendar-day diary**. It:

* is **not** wiped if a future “reset session counter” feature is added
* is saved to a tiny JSON file in the user’s home folder
* **rolls over to zero at local midnight**, even if the app stays open overnight

Privacy
-------
Only three fields are stored locally: today’s date, seconds of face-time, and
blink count. Nothing is uploaded. Path (default)::

    ~/.eyerhythm_blinkcounter/screentime.json
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Where we keep the tiny daily stats file
# ---------------------------------------------------------------------------
# Path.home() = the current user’s home directory (e.g. /Users/you on Mac).
# A hidden folder (starts with ".") keeps the home directory tidy.
STORAGE_DIR = Path.home() / ".eyerhythm_blinkcounter"
STORAGE_FILE = STORAGE_DIR / "screentime.json"

# How often we write to disk while the app is running (seconds).
# We do NOT write every frame — that would wear the disk and slow things down.
# Every 15 seconds is more than enough for “survives a crash”.
SAVE_EVERY_S = 15.0

# If two “face present” ticks are more than this many seconds apart, we assume
# the app was paused, the machine slept, or the user stepped away — so we do
# NOT add that long gap to screen time (would inflate the number unfairly).
MAX_GAP_S = 2.0


class ScreenTimeTracker:
    """
    Keeps today’s face-time and blink total, with automatic midnight reset.

    How to use it (from the main loop)
    ----------------------------------
    * Call ``tick(face_present=True/False)`` once per processed camera frame.
    * Call ``add_blink()`` whenever the detector reports a new counted blink.
    * Read ``seconds_today``, ``blinks_today``, ``avg_blinks_per_minute``,
      or ``formatted()`` for the UI.
    * Call ``save()`` on quit (the main loop already does this).

    Thread safety
    -------------
    Designed to be used from a single thread (the main camera loop). Do not
    call from multiple threads without adding locks.
    """

    def __init__(self, storage_file: Path | str = STORAGE_FILE):
        # Path to the JSON file we read/write.
        self._file = Path(storage_file)

        # Calendar day as text, e.g. "2026-08-01". Compared to date.today()
        # so we notice when midnight passes while the app is still open.
        self._today = date.today().isoformat()

        # Accumulated seconds of “face was visible” for today.
        self._seconds = 0.0

        # How many blinks we have counted for today (daily total for the UI).
        self._blinks = 0

        # Monotonic clock time of the previous tick that saw a face.
        # Used to measure “how much time passed since last good frame”.
        # None means “we were not tracking” (no face, or first frame).
        self._last_tick: float | None = None

        # Wall-clock time of the last successful save (for SAVE_EVERY_S).
        self._last_save = 0.0

        # Pull yesterday’s/today’s data from disk if the file exists.
        self._load()

    # ================================================================== API
    # These methods are what the rest of the app should call.

    def tick(self, face_present: bool) -> None:
        """
        Call once per processed frame.

        Parameters
        ----------
        face_present:
            True if the detector saw a face in this frame.
            Only then do we add elapsed time to “screen time today”.
            If False, we stop the timer until a face appears again
            (user looked away, camera lost, etc.).
        """
        # Always check midnight first so numbers never spill into tomorrow.
        self._rollover_if_new_day()

        # Monotonic clock: keeps ticking steadily even if the user changes
        # the system clock. Perfect for measuring short gaps between frames.
        now = time.monotonic()

        if face_present:
            if self._last_tick is not None:
                # How long since the last face-present frame?
                delta = now - self._last_tick
                # Only count “reasonable” gaps (normal frame spacing is ~0.03s).
                # Huge gaps = sleep / pause — skip those so stats stay honest.
                if 0 < delta <= MAX_GAP_S:
                    self._seconds += delta
            # Remember this moment so the next tick can measure the gap.
            self._last_tick = now
        else:
            # Face gone: freeze the timer. Next face-present tick starts fresh
            # so we do not credit “away from desk” as screen time.
            self._last_tick = None

        # Periodically flush to disk (not every frame).
        if time.time() - self._last_save >= SAVE_EVERY_S:
            self.save()

    def add_blink(self) -> None:
        """
        Record one counted blink for today’s total.

        Call this only when the detector sets ``blink_just_counted=True``
        (a complete open→closed→open cycle that passed all filters).
        """
        self._rollover_if_new_day()
        self._blinks += 1
        # Save immediately: a power loss right after a blink should still
        # keep the count. One tiny file write per blink is cheap.
        self.save()

    @property
    def seconds_today(self) -> float:
        """Total seconds a face was visible today (float)."""
        self._rollover_if_new_day()
        return self._seconds

    @property
    def blinks_today(self) -> int:
        """Total blinks counted today (integer)."""
        self._rollover_if_new_day()
        return self._blinks

    @property
    def avg_blinks_per_minute(self) -> float:
        """
        Daily average rate: total blinks ÷ minutes of screen time.

        Returns 0.0 until there is at least one second of face-time
        (avoids division by zero at startup).
        """
        secs = self.seconds_today
        if secs < 1.0:
            return 0.0
        # blinks * 60 / seconds  ==  blinks per minute
        return self.blinks_today * 60.0 / secs

    def formatted(self) -> str:
        """
        Human-readable screen time for the UI, e.g. ``'1h 24m'`` or ``'12m'``.
        """
        # Whole minutes only (UI does not need seconds).
        total_m = int(self.seconds_today // 60)
        h, m = divmod(total_m, 60)
        # Show hours only when needed, so short sessions stay compact.
        return f"{h}h {m:02d}m" if h else f"{m}m"

    def save(self) -> None:
        """
        Write today’s numbers to the JSON file.

        Failures (disk full, permissions) are swallowed so the app never
        crashes just because stats could not be saved.
        """
        try:
            # Create ~/.eyerhythm_blinkcounter/ if it does not exist yet.
            self._file.parent.mkdir(parents=True, exist_ok=True)
            # Small, readable JSON — easy to inspect by hand if needed.
            self._file.write_text(json.dumps({
                "date": self._today,
                "seconds": round(self._seconds, 1),
                "blinks": int(self._blinks),
            }))
            self._last_save = time.time()
        except OSError:
            # Never crash the app over stats persistence.
            pass

    # ============================================================ internals
    # Helpers used only inside this class.

    def _load(self) -> None:
        """
        Read the JSON file on startup.

        * If the file is for **today**, restore seconds + blinks.
        * If it is for **another day**, ignore it (we start at zero;
          midnight rollover also handles this path while running).
        * If the file is missing or corrupt, start at zero quietly.
        """
        try:
            data = json.loads(self._file.read_text())
            # Only restore if the stored date matches “today”.
            if data.get("date") == self._today:
                self._seconds = float(data.get("seconds", 0.0))
                self._blinks = int(data.get("blinks", 0))
        except (OSError, ValueError):
            # First run, deleted file, or broken JSON → start fresh.
            pass

    def _rollover_if_new_day(self) -> None:
        """
        If the calendar day changed since we last looked, zero the counters.

        This runs on every tick / property read so midnight is handled even
        when the user leaves the app open overnight.
        """
        today = date.today().isoformat()
        if today != self._today:  # midnight passed (or clock jumped forward)
            self._today = today
            self._seconds = 0.0
            self._blinks = 0
            # Persist the fresh day immediately so a crash after midnight
            # does not revive yesterday’s numbers from an old file.
            self.save()
