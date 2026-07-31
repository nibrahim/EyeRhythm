"""
Cross-platform blink beep using only what ships with the OS.

  Windows -> winsound.Beep (built into the standard library)
  macOS   -> afplay with a built-in system sound
  Linux   -> terminal bell as a last resort

Beeps play on a background thread so the main loop never stalls.
"""

import platform
import subprocess
import sys
import threading


class Beeper:
    def __init__(self):
        self._system = platform.system()
        self._lock = threading.Lock()
        self._busy = False

    def beep(self) -> None:
        """Fire-and-forget beep; skips if the previous one is still playing."""
        with self._lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._play, daemon=True).start()

    # ------------------------------------------------------------ internals

    def _play(self) -> None:
        try:
            if self._system == "Windows":
                import winsound
                winsound.Beep(700, 200)  # 1.2 kHz, 60 ms
            elif self._system == "Darwin":
                subprocess.run(
                    ["afplay", "/System/Library/Sounds/Tink.aiff"],
                    check=False, timeout=2,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                sys.stdout.write("\a")
                sys.stdout.flush()
        except Exception:
            pass  # audio must never crash the app
        finally:
            with self._lock:
                self._busy = False
