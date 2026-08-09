"""
Inter-blink interval research log (per screen-time hour)
========================================================

Plain-language goal
-------------------
While EyeRhythm runs, collect the **time between consecutive blinks**
(inter-blink interval) and summarise it for **each full hour of face-present
screen time**, plus a final partial hour if the day ends mid-hour.

Example
-------
If you accumulate **6 h 45 m** of screen time in a day, the JSON ``records``
array will contain **7 entries** for that date:

* hours 1–6 — each with ~3600 s of face time (``complete: true``)
* hour 7 — the remaining ~45 m (``complete: false`` until that hour
  fills, or the calendar day rolls over)

Each record stores:

* ``date`` — calendar day (local)
* ``start_time`` / ``end_time`` — wall-clock window while that screen hour
  was open (may span breaks away from the camera)
* ``screen_seconds`` — face-present seconds in this hour bucket
* ``min_s`` / ``max_s`` / ``mean_s`` / ``median_s`` — inter-blink gaps
* ``blink_count`` / ``gap_count`` — sample sizes
* ``complete`` — true after a full 3600 s of screen time in the bucket

Privacy
-------
Local JSON only — never uploaded. Path (default)::

    ~/.eyerhythm_blinkcounter/interblink_hours.json
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Same folder as daily screen-time / preferences.
STORAGE_DIR = Path.home() / ".eyerhythm_blinkcounter"
STORAGE_FILE = STORAGE_DIR / "interblink_hours.json"

# One “screen hour” of face-present time.
HOUR_S = 3600.0

# Plausible inter-blink gaps only (same spirit as RegularityTracker).
# Gaps outside this range are treated as breaks / noise, not true IBIs.
MIN_GAP_S = 0.15
MAX_GAP_S = 30.0

# How often we flush while running (seconds). Not every frame.
SAVE_EVERY_S = 15.0

FILE_VERSION = 1


def _wall_iso() -> str:
    """Local wall-clock timestamp, second precision, no timezone suffix."""
    return datetime.now().replace(microsecond=0).isoformat(sep="T")


def _stats_from_gaps(gaps: list[float]) -> dict[str, float | None]:
    """min / max / mean / median for a list of gaps; all None if empty."""
    if not gaps:
        return {
            "min_s": None,
            "max_s": None,
            "mean_s": None,
            "median_s": None,
        }
    return {
        "min_s": round(min(gaps), 4),
        "max_s": round(max(gaps), 4),
        "mean_s": round(statistics.fmean(gaps), 4),
        "median_s": round(statistics.median(gaps), 4),
    }


class InterBlinkHourTracker:
    """
    Research diary: inter-blink stats per cumulative screen-time hour.

    Engine usage
    ------------
    * After ``ScreenTimeTracker.tick(...)``::
          tracker.on_screen_seconds(screen_time.seconds_today)
    * On each counted blink::
          tracker.on_blink(time.monotonic())
    * On quit::
          tracker.save()
    * On startup (after ScreenTimeTracker loads)::
          tracker.sync_screen_seconds(screen_time.seconds_today)

    Hour boundaries use **face-present screen seconds**, not wall-clock hours.
    """

    def __init__(self, storage_file: Path | str = STORAGE_FILE):
        self._file = Path(storage_file)
        self._today = date.today().isoformat()

        # All hour rows (completed + today's open incomplete, if any).
        self._records: list[dict[str, Any]] = []

        # Open bucket state (mirrored into records on save).
        self._hour_index = 1
        self._hour_start_wall: str | None = None
        self._gaps: list[float] = []
        self._blinks_in_hour = 0
        self._hour_start_screen_s = 0.0
        self._screen_seconds = 0.0
        self._last_blink_mono: float | None = None

        self._last_save = 0.0
        self._dirty = False

        self._load()

    # ================================================================== API

    def sync_screen_seconds(self, seconds: float) -> None:
        """
        Align open hour index with ``ScreenTimeTracker`` after startup.

        Does not invent empty historical rows for time already accumulated
        before this research feature existed.
        """
        self._rollover_if_new_day()
        seconds = max(0.0, float(seconds))
        self._screen_seconds = seconds

        # If we restored an incomplete row for today, keep its hour_index.
        open_rec = self._find_open_record(self._today)
        if open_rec is not None:
            try:
                self._hour_index = max(1, int(open_rec.get("hour_index", 1)))
            except (TypeError, ValueError):
                self._hour_index = int(seconds // HOUR_S) + 1
            self._hour_start_screen_s = (self._hour_index - 1) * HOUR_S
            return

        # Otherwise open the hour that matches restored screen totals.
        completed = int(seconds // HOUR_S)
        # If completed hours already exist as complete rows, open after last.
        today_complete = [
            int(r["hour_index"])
            for r in self._records
            if r.get("date") == self._today
            and r.get("complete") is True
            and "hour_index" in r
        ]
        if today_complete:
            self._hour_index = max(max(today_complete) + 1, completed + 1)
        else:
            self._hour_index = completed + 1
        self._hour_start_screen_s = (self._hour_index - 1) * HOUR_S

    def on_screen_seconds(self, seconds: float) -> None:
        """Update face-present total; finalise hour buckets when full."""
        self._rollover_if_new_day()
        seconds = max(0.0, float(seconds))

        if seconds > self._screen_seconds and self._hour_start_wall is None and seconds > 0:
            self._hour_start_wall = _wall_iso()

        while seconds >= self._hour_index * HOUR_S:
            boundary = self._hour_index * HOUR_S
            self._seal_current_hour(
                complete=True,
                end_screen_s=boundary,
                end_wall=_wall_iso(),
            )

        self._screen_seconds = seconds
        self._dirty = True
        self._maybe_autosave()

    def on_blink(self, timestamp_mono: float) -> None:
        """Record a counted blink; store a plausible inter-blink gap."""
        self._rollover_if_new_day()

        if self._hour_start_wall is None:
            self._hour_start_wall = _wall_iso()

        self._blinks_in_hour += 1

        if self._last_blink_mono is not None:
            gap = float(timestamp_mono) - self._last_blink_mono
            if MIN_GAP_S <= gap <= MAX_GAP_S:
                self._gaps.append(gap)

        self._last_blink_mono = float(timestamp_mono)
        self._dirty = True
        self._maybe_autosave()

    def save(self) -> None:
        """
        Persist all hour records.

        The open (incomplete) hour is upserted into ``records`` so a day with
        6 h 45 m always has 7 entries without a separate file section.
        """
        try:
            if self._has_open_data():
                self._upsert_open_record(complete=False, end_wall=_wall_iso())

            self._file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": FILE_VERSION,
                "updated_at": _wall_iso(),
                "description": (
                    "Inter-blink interval stats per screen-time hour. "
                    "One entry per full hour of face-present time, plus a "
                    "final partial hour (complete=false) when applicable."
                ),
                "records": list(self._records),
            }
            self._file.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )
            self._last_save = time.time()
            self._dirty = False
        except OSError:
            pass

    @property
    def records(self) -> list[dict[str, Any]]:
        return list(self._records)

    @property
    def current_hour_index(self) -> int:
        return self._hour_index

    def records_for_date(self, day: str | None = None) -> list[dict[str, Any]]:
        day = day or self._today
        return [r for r in self._records if r.get("date") == day]

    # ============================================================ internals

    def _has_open_data(self) -> bool:
        return (
            self._hour_start_wall is not None
            or len(self._gaps) > 0
            or self._blinks_in_hour > 0
            or self._seconds_in_current_hour() >= 1.0
        )

    def _seconds_in_current_hour(self, end_screen_s: float | None = None) -> float:
        end = self._screen_seconds if end_screen_s is None else end_screen_s
        return max(0.0, float(end) - self._hour_start_screen_s)

    def _find_open_record(self, day: str) -> dict[str, Any] | None:
        for r in reversed(self._records):
            if r.get("date") == day and r.get("complete") is False:
                return r
        return None

    def _find_record_index(self, day: str, hour_index: int) -> int | None:
        for i, r in enumerate(self._records):
            if r.get("date") == day and int(r.get("hour_index", -1)) == hour_index:
                return i
        return None

    def _build_record(
        self,
        *,
        complete: bool,
        end_screen_s: float,
        end_wall: str,
        day: str | None = None,
        include_gaps: bool = False,
    ) -> dict[str, Any]:
        stats = _stats_from_gaps(self._gaps)
        screen_in_hour = max(0.0, end_screen_s - self._hour_start_screen_s)
        if complete:
            screen_in_hour = min(screen_in_hour, HOUR_S)
        rec: dict[str, Any] = {
            "date": day or self._today,
            "hour_index": self._hour_index,
            "start_time": self._hour_start_wall or end_wall,
            "end_time": end_wall,
            "screen_seconds": round(screen_in_hour, 1),
            "blink_count": int(self._blinks_in_hour),
            "gap_count": len(self._gaps),
            **stats,
            "complete": bool(complete),
        }
        # Keep raw gaps only while the hour is still open (restart safety).
        if include_gaps and not complete:
            rec["gaps"] = [round(g, 4) for g in self._gaps]
        return rec

    def _upsert_open_record(self, *, complete: bool, end_wall: str) -> None:
        """Write / refresh the current hour row in ``records``."""
        if (
            self._seconds_in_current_hour() < 1.0
            and self._blinks_in_hour == 0
            and not self._gaps
            and self._hour_start_wall is None
        ):
            return

        rec = self._build_record(
            complete=complete,
            end_screen_s=self._screen_seconds if not complete else self._hour_index * HOUR_S,
            end_wall=end_wall,
            include_gaps=not complete,
        )
        # Drop gaps key from completed rows.
        if complete:
            rec.pop("gaps", None)

        idx = self._find_record_index(rec["date"], rec["hour_index"])
        if idx is None:
            self._records.append(rec)
        else:
            self._records[idx] = rec

    def _seal_current_hour(
        self,
        *,
        complete: bool,
        end_screen_s: float,
        end_wall: str,
        day: str | None = None,
    ) -> None:
        """
        Finalise the open hour into ``records`` and advance to the next bucket.
        """
        day = day or self._today
        screen_in_hour = max(0.0, end_screen_s - self._hour_start_screen_s)

        # Skip totally empty buckets (can happen if totals jump on first sync).
        if (
            screen_in_hour < 1.0
            and self._blinks_in_hour == 0
            and not self._gaps
            and self._hour_start_wall is None
        ):
            if complete:
                self._advance_hour_bucket()
            return

        rec = self._build_record(
            complete=complete,
            end_screen_s=end_screen_s,
            end_wall=end_wall,
            day=day,
            include_gaps=not complete,
        )
        if complete:
            rec.pop("gaps", None)

        idx = self._find_record_index(day, self._hour_index)
        if idx is None:
            self._records.append(rec)
        else:
            self._records[idx] = rec

        self._dirty = True
        self._advance_hour_bucket()

    def _advance_hour_bucket(self) -> None:
        self._hour_index += 1
        self._hour_start_screen_s = (self._hour_index - 1) * HOUR_S
        self._gaps.clear()
        self._blinks_in_hour = 0
        self._hour_start_wall = None
        # Keep last blink time so the first gap of the next hour is still a
        # true inter-blink interval (research continuity across the edge).

    def _maybe_autosave(self) -> None:
        if self._dirty and (time.time() - self._last_save >= SAVE_EVERY_S):
            self.save()

    def _load(self) -> None:
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return

        records = data.get("records")
        if not isinstance(records, list):
            return
        self._records = [r for r in records if isinstance(r, dict)]

        # Restore open incomplete hour for today (including raw gaps).
        open_rec = self._find_open_record(self._today)
        if open_rec is None:
            return
        try:
            self._hour_index = max(1, int(open_rec.get("hour_index", 1)))
            self._hour_start_screen_s = (self._hour_index - 1) * HOUR_S
            start = open_rec.get("start_time")
            self._hour_start_wall = str(start) if start else None
            self._blinks_in_hour = int(open_rec.get("blink_count", 0))
            raw_gaps = open_rec.get("gaps") or []
            if isinstance(raw_gaps, list):
                self._gaps = [
                    float(g) for g in raw_gaps if isinstance(g, (int, float))
                ]
            # Approximate total from completed hours + open screen_seconds.
            open_secs = float(open_rec.get("screen_seconds", 0.0))
            self._screen_seconds = self._hour_start_screen_s + open_secs
        except (TypeError, ValueError):
            self._hour_index = 1
            self._hour_start_screen_s = 0.0
            self._gaps = []
            self._blinks_in_hour = 0
            self._hour_start_wall = None

    def _rollover_if_new_day(self) -> None:
        today = date.today().isoformat()
        if today == self._today:
            return

        old_day = self._today
        if self._has_open_data():
            self._seal_current_hour(
                complete=False,
                end_screen_s=self._screen_seconds,
                end_wall=_wall_iso(),
                day=old_day,
            )
            # Ensure yesterday's last row stays complete=false (partial day).
            # (Already sealed.)

        self._today = today
        self._hour_index = 1
        self._hour_start_screen_s = 0.0
        self._screen_seconds = 0.0
        self._gaps.clear()
        self._blinks_in_hour = 0
        self._hour_start_wall = None
        self._last_blink_mono = None
        self._dirty = True
        self.save()
