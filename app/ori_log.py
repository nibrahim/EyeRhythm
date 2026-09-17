"""
Ocular Rhythm Index history for Reports
=======================================

While a face is on-screen, the engine samples ORI and screen time and
we fold those samples into **5-minute bins** for each local calendar day.
Reports (ocular rhythm and screen time) read this file — never the live
5-minute Trace buffer.

File (local only)::

    ~/.eyerhythm_blinkcounter/ori_history.json
"""

from __future__ import annotations

import json
import threading
import time
from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.preferences import STORAGE_DIR

HISTORY_FILE = STORAGE_DIR / "ori_history.json"
BIN_MINUTES = 5
BINS_PER_DAY = (24 * 60) // BIN_MINUTES  # 288
SAMPLE_S = 5.0
SAVE_EVERY_S = 30.0
KEEP_DAYS = 400
MAX_TICK_GAP_S = 8.0

_lock = threading.RLock()


def _today() -> str:
    return date.today().isoformat()


def _bin_index(now: datetime | None = None) -> int:
    t = now or datetime.now()
    minutes = t.hour * 60 + t.minute
    return min(BINS_PER_DAY - 1, minutes // BIN_MINUTES)


def _empty_store() -> dict[str, Any]:
    return {"version": 1, "days": {}}


class OriHistory:
    """
    5-minute ORI bins keyed by ISO date.

    Call ``sample()`` from the camera loop (throttled internally).
    Call ``save()`` on quit.
    """

    def __init__(self, path: Path | str = HISTORY_FILE):
        self._path = Path(path)
        self._last_sample_at = 0.0
        self._last_save_at = 0.0
        self._dirty = False
        with _lock:
            self._data = self._read()

    def _read(self) -> dict[str, Any]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return _empty_store()
        if not isinstance(raw, dict):
            return _empty_store()
        days = raw.get("days")
        if not isinstance(days, dict):
            days = {}
        return {"version": 1, "days": days}

    def save(self, *, force: bool = False) -> None:
        with _lock:
            if not force and not self._dirty:
                return
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._prune_locked()
                self._path.write_text(
                    json.dumps(self._data, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                self._dirty = False
                self._last_save_at = time.monotonic()
            except OSError:
                pass

    def _prune_locked(self) -> None:
        days = self._data.get("days")
        if not isinstance(days, dict) or len(days) <= KEEP_DAYS:
            return
        keys = sorted(k for k in days.keys() if isinstance(k, str))
        extra = len(keys) - KEEP_DAYS
        if extra <= 0:
            return
        for k in keys[:extra]:
            days.pop(k, None)

    def sample(
        self,
        ori: float | None,
        present: bool,
        blinks: int = 0,
    ) -> None:
        """
        Fold one live reading into today's 5-minute bin.

        Face-absent ticks do not change the ORI average (those minutes stay
        gaps on the daily chart). Blinks still count only while present.
        """
        now_m = time.monotonic()
        if (now_m - self._last_sample_at) < SAMPLE_S and not blinks:
            return
        dt = now_m - self._last_sample_at if self._last_sample_at > 0 else SAMPLE_S
        if dt > MAX_TICK_GAP_S:
            dt = SAMPLE_S
        self._last_sample_at = now_m

        day = _today()
        idx = str(_bin_index())
        with _lock:
            days = self._data.setdefault("days", {})
            if not isinstance(days, dict):
                days = {}
                self._data["days"] = days
            rec = days.get(day)
            if not isinstance(rec, dict):
                rec = {"bins": {}}
                days[day] = rec
            bins = rec.setdefault("bins", {})
            if not isinstance(bins, dict):
                bins = {}
                rec["bins"] = bins
            cell = bins.get(idx)
            if not isinstance(cell, dict):
                cell = {"ori_sum": 0.0, "n": 0, "screen_s": 0.0, "blinks": 0}
                bins[idx] = cell
            if present:
                cell["screen_s"] = round(float(cell.get("screen_s", 0.0)) + dt, 2)
                if ori is not None:
                    try:
                        value = float(ori)
                    except (TypeError, ValueError):
                        value = None
                    if value is not None and value == value:  # not NaN
                        cell["ori_sum"] = round(
                            float(cell.get("ori_sum", 0.0)) + value, 3
                        )
                        cell["n"] = int(cell.get("n", 0)) + 1
                if blinks:
                    cell["blinks"] = int(cell.get("blinks", 0)) + int(blinks)
            self._dirty = True
            if now_m - self._last_save_at >= SAVE_EVERY_S:
                # Release is fine: save() re-acquires.
                pass
        if now_m - self._last_save_at >= SAVE_EVERY_S:
            self.save()

    def available_days(self) -> list[str]:
        with _lock:
            days = self._data.get("days", {})
            if not isinstance(days, dict):
                return []
            keys = sorted(k for k in days.keys() if isinstance(k, str))
        today = _today()
        if today not in keys:
            keys.append(today)
            keys.sort()
        return keys

    def daily(self, day: str) -> dict[str, Any]:
        day = str(day)
        with _lock:
            rec = self._data.get("days", {}).get(day, {})
            bins = rec.get("bins", {}) if isinstance(rec, dict) else {}
            if not isinstance(bins, dict):
                bins = {}
            bins = deepcopy(bins)
        points: list[dict[str, Any]] = []
        ori_vals: list[float] = []
        screen_s = 0.0
        blinks = 0
        below_s = 0.0
        for i in range(BINS_PER_DAY):
            hh = (i * BIN_MINUTES) // 60
            mm = (i * BIN_MINUTES) % 60
            cell = bins.get(str(i), {})
            if not isinstance(cell, dict):
                cell = {}
            n = int(cell.get("n", 0) or 0)
            mean = None
            if n > 0:
                mean = round(float(cell.get("ori_sum", 0.0)) / n, 1)
                ori_vals.append(mean)
            ss = float(cell.get("screen_s", 0.0) or 0.0)
            bb = int(cell.get("blinks", 0) or 0)
            screen_s += ss
            blinks += bb
            points.append({
                "i": i,
                "t": f"{hh:02d}:{mm:02d}",
                "ori": mean,
                "screen_s": round(ss, 1),
                "blinks": bb,
            })
        return {
            "kind": "daily",
            "date": day,
            "bin_minutes": BIN_MINUTES,
            "points": points,
            "summary": _summary(ori_vals, screen_s, blinks),
        }

    def weekly(self, day: str) -> dict[str, Any]:
        try:
            anchor = date.fromisoformat(str(day)[:10])
        except ValueError:
            anchor = date.today()
        start = anchor - timedelta(days=anchor.weekday())  # Monday
        days_out: list[dict[str, Any]] = []
        ori_vals: list[float] = []
        screen_s = 0.0
        blinks = 0
        for i in range(7):
            d = start + timedelta(days=i)
            iso = d.isoformat()
            pack = self.daily(iso)
            mean = pack["summary"]["mean_ori"]
            ss = pack["summary"]["screen_s"]
            bb = pack["summary"]["blinks"]
            if mean is not None:
                ori_vals.append(float(mean))
            screen_s += ss
            blinks += bb
            days_out.append({
                "date": iso,
                "label": d.strftime("%a"),
                "ori": mean,
                "screen_s": ss,
                "blinks": bb,
            })
        return {
            "kind": "weekly",
            "week_start": start.isoformat(),
            "week_end": (start + timedelta(days=6)).isoformat(),
            "days": days_out,
            "summary": _summary(ori_vals, screen_s, blinks),
        }

    def monthly(self, year: int, month: int) -> dict[str, Any]:
        try:
            y, m = int(year), int(month)
            n_days = monthrange(y, m)[1]
        except (TypeError, ValueError):
            today = date.today()
            y, m, n_days = today.year, today.month, monthrange(
                today.year, today.month
            )[1]
        days_out: list[dict[str, Any]] = []
        ori_vals: list[float] = []
        screen_s = 0.0
        blinks = 0
        for d in range(1, n_days + 1):
            iso = date(y, m, d).isoformat()
            pack = self.daily(iso)
            mean = pack["summary"]["mean_ori"]
            ss = pack["summary"]["screen_s"]
            bb = pack["summary"]["blinks"]
            if mean is not None:
                ori_vals.append(float(mean))
            screen_s += ss
            blinks += bb
            days_out.append({
                "date": iso,
                "label": str(d),
                "ori": mean,
                "screen_s": ss,
                "blinks": bb,
            })
        return {
            "kind": "monthly",
            "year": y,
            "month": m,
            "days": days_out,
            "summary": _summary(ori_vals, screen_s, blinks),
        }


def _summary(
    ori_vals: list[float],
    screen_s: float,
    blinks: int,
) -> dict[str, Any]:
    mean = round(sum(ori_vals) / len(ori_vals), 1) if ori_vals else None
    return {
        "mean_ori": mean,
        "screen_s": round(float(screen_s), 1),
        "blinks": int(blinks),
        "days_with_data": len(ori_vals),
    }
