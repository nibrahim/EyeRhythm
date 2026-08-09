"""
blink_core — the “brain” of EyeRhythm
=====================================

This package holds the **platform-independent** logic: it does not open windows,
play sounds, or talk to the OS camera API. Those jobs live in the ``app`` package.

What lives here
---------------
* ``detector``   – looks at each webcam frame and decides “was that a blink?”
* ``screentime`` – quietly keeps today’s screen-time minutes and blink totals
                   on disk so they survive restarts and reset at midnight.
* ``interblink_hours`` – research log: min/max/mean/median inter-blink gap
                         for each hour of face-present screen time.

Public exports (what other code should import)
----------------------------------------------
* ``BlinkDetector`` – main class: feed it frames, get blink results back
* ``BlinkConfig``   – tunable knobs (thresholds, timings)
* ``FrameResult``   – one snapshot of “what we know right now” for the UI

Why separate this package?
--------------------------
So the hard science of blink detection can be tested and reused the same way on
Windows, macOS, and Linux. Only the camera/UI layer needs OS-specific code.
"""

# Re-export the main types so callers can write:
#   from blink_core import BlinkDetector
# instead of the longer:
#   from blink_core.detector import BlinkDetector
from .detector import BlinkDetector, BlinkConfig, FrameResult
from .interblink_hours import InterBlinkHourTracker

# Explicit list of names that `from blink_core import *` would expose.
# Also documents the public API of this package.
__all__ = [
    "BlinkDetector",
    "BlinkConfig",
    "FrameResult",
    "InterBlinkHourTracker",
]
