"""
Camera idle policy (battery saver)
==================================

When nobody is in front of the screen, keeping the webcam open still
draws power. This module is the on/off policy; the engine opens and
closes the device.

1. **Live** — camera on, detect as usual.
2. After **1 minute** with no face, go **sleep** — camera released.
3. Every **2 minutes**, **peek**: open the camera briefly.
4. If a face stays for **30 seconds**, return to live.
   Otherwise sleep again and peek in another 2 minutes.

Face-down / off-screen still counts as a face (the camera stays on).
Only MediaPipe “no face” starts the idle timer.
"""

from __future__ import annotations

# No face for this long → release the webcam.
ABSENT_BEFORE_SLEEP_S = 60.0
# Camera stays off between peeks.
SLEEP_BETWEEN_PEEKS_S = 120.0
# How long a peek may hunt with nobody there before giving up.
PEEK_NO_FACE_S = 5.0
# Continuous face required during a peek before full live mode.
CONFIRM_FACE_S = 30.0
# Ignore a short drop during the 30 s confirm (blink / brief occlusion).
CONFIRM_GRACE_S = 1.0


class CameraIdlePolicy:
    """
    Pure state machine. The engine feeds ``note_face`` once per processed
    frame and acts on the returned phase.

    Phases: ``live`` | ``peek`` | ``sleep``.
    """

    def __init__(self) -> None:
        self.phase = "live"
        self._absent_since: float | None = None
        self._peek_since: float | None = None
        self._confirm_since: float | None = None
        self._confirm_lost_since: float | None = None

    def reset_to_live(self) -> None:
        """Force full camera use (practice, Lens, or a successful confirm)."""
        self.phase = "live"
        self._absent_since = None
        self._peek_since = None
        self._confirm_since = None
        self._confirm_lost_since = None

    def begin_peek(self, now: float) -> None:
        """Camera has just been reopened for a presence check."""
        self.phase = "peek"
        self._peek_since = now
        self._confirm_since = None
        self._confirm_lost_since = None
        self._absent_since = None

    def begin_sleep(self) -> None:
        self.phase = "sleep"
        self._absent_since = None
        self._peek_since = None
        self._confirm_since = None
        self._confirm_lost_since = None

    def note_face(self, found: bool, now: float) -> str:
        """
        Update from one detection. Returns the phase to be in afterwards
        (``live``, ``peek``, or ``sleep``).
        """
        if self.phase == "sleep":
            return "sleep"
        if self.phase == "peek":
            return self._note_peek(found, now)
        return self._note_live(found, now)

    def _note_live(self, found: bool, now: float) -> str:
        if found:
            self._absent_since = None
            return "live"
        if self._absent_since is None:
            self._absent_since = now
        if now - self._absent_since >= ABSENT_BEFORE_SLEEP_S:
            self.begin_sleep()
            return "sleep"
        return "live"

    def _note_peek(self, found: bool, now: float) -> str:
        if found:
            self._confirm_lost_since = None
            if self._confirm_since is None:
                self._confirm_since = now
            if now - self._confirm_since >= CONFIRM_FACE_S:
                self.reset_to_live()
                return "live"
            return "peek"

        # Face missing during peek.
        if self._confirm_since is not None:
            if self._confirm_lost_since is None:
                self._confirm_lost_since = now
            if now - self._confirm_lost_since >= CONFIRM_GRACE_S:
                self.begin_sleep()
                return "sleep"
            return "peek"

        started = self._peek_since if self._peek_since is not None else now
        if now - started >= PEEK_NO_FACE_S:
            self.begin_sleep()
            return "sleep"
        return "peek"
