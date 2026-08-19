"""
Cross-platform short “beep” / click sounds
==========================================

Plain-language goal
-------------------
When the user turns on “beep on blink”, low-rate alert, or practice mode,
we need a short sound. We deliberately avoid shipping audio files or heavy
audio libraries.

How each OS is handled
----------------------
* **Windows** – built-in ``winsound.Beep`` (pure standard library)
* **macOS**   – short clip of a system sound via ``afplay`` (non-blocking)
* **Linux**   – terminal bell character as a last resort

Important design choices
------------------------
1. Beeps never block the camera/UI loop.
2. Overlapping requests are **queued**, not dropped forever: if a beep is
   requested during the short cooldown after a sound, we keep a small pending
   count and drain it when free. Blink-on-beep therefore does not go silent
   after a burst of sounds (the previous design discarded every request while
   “busy”, and on macOS ``afplay`` of a full AIFF held busy for ~1.5 s).
3. macOS ``afplay`` has large process-startup cost and system AIFF files are
   often >1 s long. We cap playback with ``-t`` and start the process without
   waiting, so the next beep can be scheduled after a short cooldown.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import threading
import time
from typing import Callable


# Minimum gap between starting two beeps. Long enough to avoid a harsh stack
# of identical clicks; short enough that a normal blink gap (~2–5 s) always
# gets a free slot immediately.
_COOLDOWN_S = 0.15

# Cap queued beeps so a runaway alert thread cannot grow an unbounded backlog.
_MAX_PENDING = 8

# macOS: play only the first N seconds of the system sound (avoids multi-second
# Tink/Pop tails that used to hold the old busy-flag for ~1.5 s per beep).
_MAC_CLIP_S = 0.10
_MAC_SOUND = "/System/Library/Sounds/Tink.aiff"


class Beeper:
    """
    Fire-and-forget short sounds with a small pending queue.

    Usage
    -----
        beeper = Beeper(on_beep=lambda: ...)
        beeper.beep()   # returns immediately; sound plays in the background
    """

    def __init__(self, on_beep: Callable[[], None] | None = None):
        # Cache OS name once: "Windows", "Darwin" (macOS), or "Linux", etc.
        self._system = platform.system()

        self._lock = threading.Lock()
        # True while the worker is running (playing or draining the queue).
        self._worker_active = False
        # Extra beeps requested while the worker was occupied.
        self._pending = 0
        # Optional callback when a beep is actually started (UI pulse).
        self._on_beep = on_beep

    def beep(self) -> None:
        """
        Request a short sound.

        Safe to call many times per second from the main loop or the alert
        thread. While a sound is in progress / cooling down, further requests
        are queued (up to ``_MAX_PENDING``) so blink events are not lost.
        """
        with self._lock:
            if self._worker_active:
                # Already playing: remember this extra blink for later.
                if self._pending < _MAX_PENDING:
                    self._pending += 1
                return
            self._worker_active = True
            self._pending = 0

        # daemon=True: if the app exits mid-beep, the process can still end.
        threading.Thread(target=self._worker, daemon=True).start()

    # ------------------------------------------------------------ internals

    def _worker(self) -> None:
        """Play once, then drain the pending queue until empty."""
        try:
            while True:
                if self._on_beep is not None:
                    try:
                        self._on_beep()
                    except Exception:
                        pass

                self._play()
                # Cooldown so we do not spawn a storm of audio processes.
                time.sleep(_COOLDOWN_S)

                with self._lock:
                    if self._pending <= 0:
                        self._worker_active = False
                        return
                    self._pending -= 1
        except Exception:
            # Never leave the worker marked active after an unexpected error.
            with self._lock:
                self._worker_active = False
                self._pending = 0

    def _play(self) -> None:
        """Actually produce sound on this OS. Failures are silent."""
        try:
            if self._system == "Windows":
                # Frequency 700 Hz, duration 100 ms — short click-like tone.
                import winsound
                winsound.Beep(700, 100)

            elif self._system == "Darwin":
                # Non-blocking: waiting on afplay alone can take ~1 s of
                # process startup, which made the old busy-flag drop later
                # blinks. Start the player and return; the worker cooldown
                # spaces starts without blocking on process exit.
                # start_new_session detaches the child from our process group.
                subprocess.Popen(
                    [
                        "afplay",
                        "-t",
                        str(_MAC_CLIP_S),
                        "-v",
                        "0.7",
                        _MAC_SOUND,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

            else:
                # Linux / other: ASCII bell. Only works if the terminal can ring.
                sys.stdout.write("\a")
                sys.stdout.flush()

        except Exception:
            # Audio must NEVER crash the app. Missing sound files, no speaker,
            # sandbox restrictions, etc. are all treated as “no sound this time”.
            pass
