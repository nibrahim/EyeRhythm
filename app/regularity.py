"""
Blink regularity score
======================

Normal mode (exactly as specified)
----------------------------------
1. Gaps = time between consecutive *counted* blinks
2. CV = (Standard Deviation of gaps) ÷ (Average gap)
3. Regularity Score = max(0, 100 − (100 × CV))

Practice mode (training toward the 3 s beep cadence)
----------------------------------------------------
While the Practice coach is running we still use CV, but also reward how
close each gap is to the beep interval (~3 s). A soft “unlock” grows with
more good samples so the score **climbs toward 100** as the user settles
into rhythm — instead of jumping around on two noisy gaps.

This module is pure math; it does not open the camera or draw UI.
"""

from __future__ import annotations

import statistics
from collections import deque


class RegularityTracker:
    """
    Rolling regularity score from inter-blink gaps.

    Call ``record_blink(timestamp_s)`` each time a blink is counted.
    Pass ``target_interval=3.0`` during Practice for cadence-aware scoring.
    """

    def __init__(self, max_gaps: int = 30, min_gaps: int = 2):
        if min_gaps < 2:
            min_gaps = 2
        self._max_gaps = max(min_gaps, max_gaps)
        self._min_gaps = min_gaps
        self._gaps: deque[float] = deque(maxlen=self._max_gaps)
        self._last_blink_s: float | None = None
        self._score: float | None = None
        self._last_cv: float | None = None
        self._practice_mode = False
        self._target_interval: float | None = None

    def record_blink(
        self,
        timestamp_s: float,
        *,
        target_interval: float | None = None,
    ) -> float | None:
        """
        Record a counted blink at ``timestamp_s`` (monotonic seconds).

        Parameters
        ----------
        target_interval:
            When set (e.g. 3.0 during Practice), score rewards matching this
            cadence as well as gap consistency.
        """
        self._practice_mode = target_interval is not None and target_interval > 0
        self._target_interval = float(target_interval) if self._practice_mode else None

        if self._last_blink_s is not None:
            gap = timestamp_s - self._last_blink_s
            # Keep only plausible inter-blink intervals.
            # During practice, prefer gaps near the coach interval (reject long pauses).
            max_gap = 8.0 if self._practice_mode else 30.0
            min_gap = 0.4 if self._practice_mode else 0.15
            if min_gap <= gap <= max_gap:
                self._gaps.append(gap)
                self._recompute()
        self._last_blink_s = timestamp_s
        return self._score

    def note_break(self) -> None:
        """
        Face left or looked down off-screen.

        The next blink must not form a gap with the last on-screen blink
        (that pause is not rhythm). Keep existing gaps and score so the
        value resumes where it left off — same idea as the blink-rate hold.
        """
        self._last_blink_s = None

    def reset(self) -> None:
        """Clear history (e.g. practice session start)."""
        self._gaps.clear()
        self._last_blink_s = None
        self._score = None
        self._last_cv = None
        self._practice_mode = False
        self._target_interval = None

    @property
    def score(self) -> float | None:
        return self._score

    @property
    def gap_count(self) -> int:
        return len(self._gaps)

    @property
    def coefficient_of_variation(self) -> float | None:
        return self._last_cv

    def _recompute(self) -> None:
        if len(self._gaps) < self._min_gaps:
            self._score = None
            self._last_cv = None
            return

        gaps = list(self._gaps)
        mean = statistics.fmean(gaps)
        if mean <= 0:
            self._score = 0.0
            self._last_cv = None
            return

        std = statistics.stdev(gaps)
        cv = std / mean
        self._last_cv = cv

        # Base formula: max(0, 100 − 100 × CV)
        cv_score = 100.0 - (100.0 * cv)
        if cv_score < 0.0:
            cv_score = 0.0
        if cv_score > 100.0:
            cv_score = 100.0

        if self._practice_mode and self._target_interval:
            target = self._target_interval
            # How close each gap is to the beep cadence (3 s).
            timing_scores: list[float] = []
            for g in gaps:
                err = abs(g - target) / target  # 0 = perfect
                timing_scores.append(max(0.0, 100.0 * (1.0 - min(1.0, err))))
            timing_score = statistics.fmean(timing_scores)

            # Blend: cadence match matters more during practice coaching.
            raw = 0.40 * cv_score + 0.60 * timing_score

            # Gradual unlock: more good samples → score can approach 100.
            # After ~12 gaps (~36 s of on-beat blinking) unlock is complete.
            n = len(gaps)
            unlock = min(1.0, max(0.0, (n - 1) / 11.0))
            # Early on show a readable climb (not stuck near zero).
            score = raw * (0.20 + 0.80 * unlock)
        else:
            score = cv_score

        if score < 0.0:
            score = 0.0
        if score > 100.0:
            score = 100.0
        self._score = round(score, 1)
