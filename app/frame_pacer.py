"""
Blink-gated adaptive frame pacing (CPU saver)
=============================================

Isolated module so the previous fixed ~17 fps (face) / ~3 fps (no-face)
duty cycle in ``engine.py`` can be restored by removing this import and
reverting the few call sites in the camera loop.

Policy (from inter-blink research: mean IBI ≈ 3 s)
--------------------------------------------------
1. While a face is present → run at full rate (``FACE_FPS``, default 30).
2. On each **counted** blink → sleep ``POST_BLINK_SLEEP_S`` (default 0.800 s),
   then resume full rate for the next blink.
3. While no face → drop to ``NO_FACE_FPS`` (default 1) until a face returns.

This only slows processing. After a full minute with no face, ``camera_idle``
releases the webcam (see that module).

Nothing here changes blink counting, screen-time rules, regularity, beeps,
or the research log — only *when* the engine sleeps between frames.

Manual tunables
---------------
* ``POST_BLINK_SLEEP_S``  ← primary knob (post-blink rest; default 0.800)
* ``FACE_FPS``            ← full rate while face present (default 30)
* ``NO_FACE_FPS``         ← hunt rate with no face (default 1)
* ``NO_FACE_GRACE_FRAMES``← consecutive misses before dropping rate

Rollback
--------
1. Delete or ignore this file.
2. In ``app/engine.py``: remove the ``from app.frame_pacer import …`` line
   and restore the previous inline constants + interval / sleep logic
   (see git history for the pre-pacer camera loop).
"""

from __future__ import annotations

import time

# ---------------------------------------------------------------------------
# Manual tunables — edit these freely
# ---------------------------------------------------------------------------

# PRIMARY KNOB: rest after every counted blink before processing again.
# ~0.8 s is safe given mean IBI ≈ 3 s (and stays under screen-time MAX_GAP_S).
# Raise to save more CPU; lower if you need tighter multi-blink resolution.
POST_BLINK_SLEEP_S = 1.0

# Full inference rate while a face is in view (and after post-blink rest).
FACE_FPS = 30.0

# Hunt rate when MediaPipe reports no face (cheap average CPU).
NO_FACE_FPS = 1.0

# Stay at face rate for this many consecutive misses so a brief occlusion
# mid-blink is not forced into the slow hunt rate.
NO_FACE_GRACE_FRAMES = 5

# Derived intervals (do not edit unless you know you need to).
FACE_INTERVAL_S = 1.0 / FACE_FPS
NO_FACE_INTERVAL_S = 1.0 / NO_FACE_FPS


class FramePacer:
    """
    Tracks face/blink events and applies the adaptive sleep policy.

    Engine usage (camera loop only — no other business logic)::

        pacer = FramePacer()
        ...
        drain = 3 if pacer.should_drain_buffer() else 0
        ...
        pacer.observe(face_found=res.face_found,
                      blink_just_counted=res.blink_just_counted)
        ...
        pacer.sleep_for_frame(loop_start)
    """

    def __init__(self, *, post_blink_sleep: bool = True, uncapped: bool = False) -> None:
        self.face_absent_streak = 0
        # Start at full face rate so first-second UX feels responsive.
        self._uncapped = bool(uncapped)
        self._interval_s = 0.0 if self._uncapped else FACE_INTERVAL_S
        self._pending_post_blink_sleep = False
        self._post_blink_sleep = bool(post_blink_sleep) and not self._uncapped

    # ------------------------------------------------------------------ API

    @property
    def interval_s(self) -> float:
        """Target spacing between processed frames (seconds), excluding
        the one-shot post-blink rest."""
        return self._interval_s

    def should_drain_buffer(self) -> bool:
        """
        True when running slowly (no-face hunt): drop a few buffered frames
        so long sleeps do not process a stale backlog.
        """
        return self._interval_s >= NO_FACE_INTERVAL_S * 0.9

    def observe(self, *, face_found: bool, blink_just_counted: bool) -> None:
        """
        Update rate from the latest detection result.

        Call once per successfully processed frame, after
        ``BlinkDetector.process_frame`` (and after blink-side effects).
        """
        if self._uncapped:
            self._interval_s = 0.0
            return
        if face_found:
            # Face is back — run at full 30 fps again.
            self.face_absent_streak = 0
            self._interval_s = FACE_INTERVAL_S
        else:
            self.face_absent_streak += 1
            if self.face_absent_streak >= NO_FACE_GRACE_FRAMES:
                # Nobody in view for a few frames — drop to 1 fps to save CPU.
                self._interval_s = NO_FACE_INTERVAL_S

        # One-shot rest after a counted blink while face is present.
        # (If face was lost on the same frame, prefer hunt pacing instead.)
        if blink_just_counted and face_found and self._post_blink_sleep:
            self._pending_post_blink_sleep = True

    def note_no_signal(self) -> None:
        """Camera read failed / black frame — treat like face absence."""
        if self._uncapped:
            return
        self.face_absent_streak += 1
        if self.face_absent_streak >= NO_FACE_GRACE_FRAMES:
            self._interval_s = NO_FACE_INTERVAL_S

    def sleep_for_frame(self, loop_start: float) -> None:
        """
        End-of-iteration sleep.

        * If a blink was just counted → sleep ``POST_BLINK_SLEEP_S`` once,
          then return (no additional face-interval sleep).
        * Otherwise → pace so this loop iteration takes about ``interval_s``.
        """
        if self._uncapped:
            return
        if self._pending_post_blink_sleep:
            self._pending_post_blink_sleep = False
            if POST_BLINK_SLEEP_S > 0:
                time.sleep(POST_BLINK_SLEEP_S)
            return

        elapsed = time.monotonic() - loop_start
        remaining = self._interval_s - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def describe(self) -> str:
        """Short log line for engine startup."""
        if self._uncapped:
            return "uncapped (hybrid)"
        sleep = (
            f"{POST_BLINK_SLEEP_S:.3f}s" if self._post_blink_sleep else "off"
        )
        return (
            f"face={FACE_FPS:.0f}fps "
            f"no_face={NO_FACE_FPS:.0f}fps "
            f"post_blink_sleep={sleep} "
            f"grace={NO_FACE_GRACE_FRAMES}"
        )
