"""
EyeRhythm processing engine (no UI)
===================================

Owns the camera loop, blink detector, daily stats, beeps, and low-rate alerts.
Exposes a thread-safe snapshot of live metrics for the React UI via the API.

Business logic matches the previous OpenCV-based main loop:
  camera → BlinkDetector → ScreenTimeTracker → optional Beeper / AlertMonitor
  + reconnect after sleep/wake / stream loss.

The GUI is intentionally not here — only numbers, flags, and optional JPEG frames.
"""

from __future__ import annotations

import base64
import platform
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from blink_core import BlinkDetector, FrameResult
from blink_core.screentime import ScreenTimeTracker
from app.beeper import Beeper
from app import preferences
from app.regularity import RegularityTracker

# ---------------------------------------------------------------------------
# Resource root (source run + PyInstaller)
# ---------------------------------------------------------------------------


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


ROOT = resource_root()
MODEL_PATH = str(ROOT / "models" / "face_landmarker.task")

# Low-rate alert (same behaviour as before)
ALERT_BPM_THRESHOLD = 10.0
ALERT_POLL_S = 0.5
# After a fresh start (or face return after a long break), continuous BPM is
# still filling its 60 s window and would look artificially low. Suppress
# alert beeps for this long so we act on real data only.
ALERT_WARMUP_S = 60.0
# Face absence longer than this restarts the alert warmup on re-detection.
FACE_BREAK_S = 60.0

# Practice coach: metronome for target blink rhythm (~20 blinks/min)
PRACTICE_INTERVAL_S = 3.0
# Read instructions first, then beep for two minutes.
PRACTICE_COUNTDOWN_S = 10.0
PRACTICE_DURATION_S = 120.0

# Camera resilience
READ_FAILS_BEFORE_REOPEN = 8
REOPEN_INITIAL_WAIT_S = 0.4
REOPEN_BACKOFF_MAX_S = 5.0
REOPEN_WARMUP_READS = 10

# Low-power capture profile (target ~20% of one core on typical laptops).
# MediaPipe Face Landmarker dominates CPU — process a small frame; display
# uses the full-res camera crop with landmarks remapped after inference.
PROCESS_MAX_WIDTH = 480          # MediaPipe input width; height keeps aspect
DISPLAY_CAPTURE_MAX_WIDTH = 1280 # camera hint for a sharper Lens crop
FACE_FPS = 17.0                  # inference rate while a face is present
NO_FACE_FPS = 3.0                # hunt rate when no face (much cheaper average)
# Stay at FACE_FPS for this many consecutive misses so a blink is not cut short.
NO_FACE_GRACE_FRAMES = 5
FACE_INTERVAL_S = 1.0 / FACE_FPS
NO_FACE_INTERVAL_S = 1.0 / NO_FACE_FPS

# Preview encoding (only when UI requests camera)
PREVIEW_MAX_WIDTH = 640          # displayed crop / full-frame width
PREVIEW_JPEG_QUALITY = 82
PREVIEW_MIN_INTERVAL_S = 0.12  # ~8 fps ceiling for the stream
# Legacy alias (logs / older call sites)
CAPTURE_MAX_WIDTH = PROCESS_MAX_WIDTH


def _log(msg: str) -> None:
    try:
        print(f"[EyeRhythm] {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass


def _frame_is_black(frame) -> bool:
    return frame is None or float(frame.mean()) < 2.0


def _release_camera(cap: cv2.VideoCapture | None) -> None:
    if cap is None:
        return
    try:
        cap.release()
    except Exception:
        pass


def _configure_capture(cap: cv2.VideoCapture) -> tuple[int, int, float]:
    """
    Hint the driver toward a display-friendly capture size and FACE_FPS.

    Inference always downscales to PROCESS_MAX_WIDTH in the loop, so CPU
    savings do not depend on the driver honoring these hints. Height is left
    unset so the camera keeps its native aspect ratio.
    """
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, DISPLAY_CAPTURE_MAX_WIDTH)
        cap.set(cv2.CAP_PROP_FPS, FACE_FPS)
        # Prefer a small buffer so we do not chew through a backlog after sleeps.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # MJPEG can cut USB bandwidth on Windows webcams; skip on macOS —
        # AVFoundation often ignores / mishandles FOURCC.
        if platform.system() == "Windows":
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    except Exception as exc:
        _log(f"capture property set failed (continuing): {exc}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    return w, h, fps


def _downscale_for_process(frame: np.ndarray) -> np.ndarray:
    """Cap width at PROCESS_MAX_WIDTH for MediaPipe; preserve aspect ratio."""
    h, w = frame.shape[:2]
    if w <= PROCESS_MAX_WIDTH:
        return frame
    scale = PROCESS_MAX_WIDTH / float(w)
    nw = PROCESS_MAX_WIDTH
    nh = max(1, int(round(h * scale)))
    return cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)


def _resize_to_preview_width(frame: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Scale ``frame`` so its width is PREVIEW_MAX_WIDTH.

    Returns ``(resized, scale)`` where ``scale`` maps original-crop pixels →
    preview pixels (landmarks multiply by this after crop-local conversion).
    """
    h, w = frame.shape[:2]
    if w <= 0:
        return frame, 1.0
    if w == PREVIEW_MAX_WIDTH:
        return frame, 1.0
    scale = PREVIEW_MAX_WIDTH / float(w)
    nw = PREVIEW_MAX_WIDTH
    nh = max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    return cv2.resize(frame, (nw, nh), interpolation=interp), scale


def open_camera(index: int, *, quiet: bool = False) -> cv2.VideoCapture | None:
    """Open webcam with OS-appropriate backends; verify non-black frames."""
    system = platform.system()
    if system == "Windows":
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    elif system == "Darwin":
        backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    else:
        backends = [cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            _release_camera(cap)
            continue

        w, h, cam_fps = _configure_capture(cap)

        good = False
        actual_w, actual_h = w, h
        for _ in range(15):
            ok, frame = cap.read()
            if ok and not _frame_is_black(frame):
                good = True
                actual_h, actual_w = frame.shape[:2]
                break
            time.sleep(0.05)

        if good:
            if not quiet:
                _log(
                    f"camera {index} opened (backend={backend}) "
                    f"capture={actual_w}x{actual_h} "
                    f"(process max width {PROCESS_MAX_WIDTH}, "
                    f"preview max width {PREVIEW_MAX_WIDTH}, "
                    f"adaptive {NO_FACE_FPS:.0f}/{FACE_FPS:.0f} fps no-face/face, "
                    f"driver fps≈{cam_fps:.1f})"
                )
            return cap
        _release_camera(cap)

    return None


def _read_frame(cap: cv2.VideoCapture | None, *, drain: int = 0):
    """
    Read one frame. If ``drain`` > 0, grab and drop that many buffered frames
    first so long sleeps (no-face mode) do not process a stale backlog.
    """
    if cap is None:
        return False, None
    try:
        for _ in range(max(0, int(drain))):
            if not cap.grab():
                break
        ok, frame = cap.read()
        if not ok or frame is None:
            return False, None
        return True, frame
    except Exception as exc:
        _log(f"camera read error: {exc}")
        return False, None


def _reopen_camera(cap: cv2.VideoCapture | None, index: int,
                   attempt: int) -> cv2.VideoCapture | None:
    _release_camera(cap)
    wait = min(REOPEN_BACKOFF_MAX_S,
               REOPEN_INITIAL_WAIT_S * (1.5 ** min(attempt, 8)))
    _log(f"camera lost — reconnect attempt {attempt + 1} "
         f"(waiting {wait:.1f}s; common after display/system sleep)")
    time.sleep(wait)

    new_cap = open_camera(index, quiet=True)
    if new_cap is not None:
        for _ in range(REOPEN_WARMUP_READS):
            ok, frame = _read_frame(new_cap)
            if ok and not _frame_is_black(frame):
                break
            time.sleep(0.03)
        _log("camera reconnected")
    return new_cap


# ===========================================================================
# Alert monitor (same idea as previous main.py)
# ===========================================================================

class AlertMonitor:
    """
    Background beeps while face present and rate below threshold.

    Alert beeps are suppressed for ``ALERT_WARMUP_S`` after:
      * construction (fresh app start — continuous BPM has no data yet), and
      * face re-detection after an absence of ``FACE_BREAK_S`` or more
        (window is empty / stale; gather a full minute before acting).
    """

    def __init__(
        self,
        beeper: Beeper,
        threshold: float = ALERT_BPM_THRESHOLD,
        poll_s: float = ALERT_POLL_S,
        on_alert_beep=None,
    ):
        self._beeper = beeper
        self._threshold = threshold
        self._poll_s = poll_s
        self._on_alert_beep = on_alert_beep
        self._lock = threading.Lock()
        self._bpm = 0.0
        self._face_found = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Fresh start: do not beep until one minute of data has accumulated.
        self._suppress_until = time.monotonic() + ALERT_WARMUP_S
        self._last_face_at: float | None = None
        self._had_face = False

    def update(self, bpm: float, face_found: bool) -> None:
        with self._lock:
            now = time.monotonic()
            if face_found:
                if not self._had_face:
                    # Face just (re)appeared.
                    if self._last_face_at is None:
                        # First face of the session: ensure a full warmup from
                        # now so we gather data even if camera started late.
                        self._suppress_until = max(
                            self._suppress_until, now + ALERT_WARMUP_S)
                        _log(
                            f"alert warmup {int(ALERT_WARMUP_S)}s "
                            "(fresh start / first face)"
                        )
                    else:
                        gap = now - self._last_face_at
                        if gap >= FACE_BREAK_S:
                            # Long break: restart warmup so BPM can refill.
                            self._suppress_until = now + ALERT_WARMUP_S
                            _log(
                                f"alert warmup {int(ALERT_WARMUP_S)}s "
                                f"(face back after {gap:.0f}s break)"
                            )
                self._had_face = True
                self._last_face_at = now
            else:
                self._had_face = False
                # Keep _last_face_at so we can measure the break length.
            self._bpm = bpm
            self._face_found = face_found

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="AlertMonitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                bpm = self._bpm
                face = self._face_found
                warming_up = time.monotonic() < self._suppress_until
            # Only beep when face is present, rate is low, and warmup is done.
            if face and not warming_up and bpm < self._threshold:
                self._beeper.beep()
                if self._on_alert_beep is not None:
                    try:
                        self._on_alert_beep()
                    except Exception:
                        pass
            self._stop.wait(self._poll_s)


class PracticeCoach:
    """
    Metronome for blink practice: one short beep every 3 seconds.

    Runs for a fixed duration (default 120s) then stops and notifies the engine
    via ``on_finished``. Cadence ≈ 20 blinks/min (healthy target range).
    """

    def __init__(
        self,
        beeper: Beeper,
        interval_s: float = PRACTICE_INTERVAL_S,
        duration_s: float = PRACTICE_DURATION_S,
        on_finished=None,
    ):
        self._beeper = beeper
        self._interval_s = max(0.5, float(interval_s))
        self._duration_s = max(1.0, float(duration_s))
        self._on_finished = on_finished
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: float | None = None
        self._ends_at: float | None = None

    def start(self) -> None:
        # Restart cleanly if already running (new practice session).
        self.stop()
        self._stop.clear()
        now = time.monotonic()
        self._started_at = now
        self._ends_at = now + self._duration_s
        self._thread = threading.Thread(
            target=self._run, name="PracticeCoach", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
        self._thread = None
        self._started_at = None
        self._ends_at = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def remaining_s(self) -> float:
        if self._ends_at is None:
            return 0.0
        return max(0.0, self._ends_at - time.monotonic())

    @property
    def ends_at_wall(self) -> float | None:
        """Wall-clock epoch when practice should end (for UI countdown)."""
        if self._ends_at is None or self._started_at is None:
            return None
        # Convert monotonic remaining → wall time.
        return time.time() + self.remaining_s

    def _run(self) -> None:
        finished_naturally = False
        try:
            # Immediate first beep so the user hears the pace right away.
            self._beeper.beep()
            while not self._stop.is_set():
                remaining = self.remaining_s
                if remaining <= 0:
                    finished_naturally = True
                    break
                wait = min(self._interval_s, remaining)
                if self._stop.wait(wait):
                    break
                if self.remaining_s <= 0:
                    finished_naturally = True
                    break
                self._beeper.beep()
        finally:
            self._started_at = None
            self._ends_at = None
            self._thread = None
            if finished_naturally and self._on_finished is not None:
                try:
                    self._on_finished()
                except Exception:
                    pass


# ===========================================================================
# Public snapshot for the UI
# ===========================================================================

@dataclass
class EngineSnapshot:
    """JSON-serialisable live state for the React dashboard."""

    # Core metrics
    continuous_bpm: float = 0.0
    average_bpm: float = 0.0
    screen_time: str = "0m"
    screen_time_seconds: float = 0.0
    fps: float = 0.0
    regularity: float | None = None
    regularity_ready: bool = False
    regularity_gaps: int = 0

    # Context
    blinks_today: int = 0
    session_blinks: int = 0
    eyes_closed: bool = False
    face_found: bool = False
    blink_score: float = 0.0

    # Status / diagnostics
    camera_ok: bool = False
    camera_message: str = "starting"
    is_frontal: bool = True
    has_glasses: bool = False
    low_light: bool = False

    # Toggles
    beep: bool = False
    alert: bool = False
    ontop: bool = False
    practice: bool = False
    # "off" | "countdown" | "active"
    practice_phase: str = "off"
    # Seconds left in the 10s pre-start countdown (read instructions).
    practice_countdown_s: float = 0.0
    # Seconds left in the active beeping practice (0 when not active).
    practice_remaining_s: float = 0.0
    # UI pulse markers (wall-clock). Separate signals for each control dot.
    last_blink_at: float = 0.0       # counted blink → Beep/Practice orange
    last_alert_beep_at: float = 0.0  # alert metronome → Alert red

    # Placeholders for future cards (always null for now)
    future_a: None = None
    future_b: None = None

    # Meta
    running: bool = False
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ===========================================================================
# Engine
# ===========================================================================

class EyeRhythmEngine:
    """
    Background camera + detection loop.

    Start with ``start()``, stop with ``stop()``.
    UI reads ``snapshot()`` and optionally ``latest_preview_jpeg()``.
    """

    def __init__(self, camera_index: int = 0, model_path: str = MODEL_PATH):
        self.camera_index = camera_index
        self.model_path = model_path

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self._beeper = Beeper()
        self._alert = AlertMonitor(
            self._beeper,
            on_alert_beep=self._note_alert_beep,
        )
        self._practice = PracticeCoach(
            self._beeper,
            on_finished=self._on_practice_finished,
        )
        self._screen_time = ScreenTimeTracker()
        self._regularity = RegularityTracker()
        self._detector: BlinkDetector | None = None
        self._last_blink_at = 0.0
        self._last_alert_beep_at = 0.0
        # Practice session: countdown thread before beeps start.
        self._practice_phase = "off"  # off | countdown | active
        self._countdown_stop = threading.Event()
        self._countdown_thread: threading.Thread | None = None
        self._countdown_ends: float | None = None

        # Restore last session toggles (Beep / Alert / On top only).
        # Practice is always session-local and never restored.
        saved = preferences.get_toggles()
        self._states = {
            "beep": bool(saved.get("beep", False)),
            "alert": bool(saved.get("alert", False)),
            "ontop": bool(saved.get("ontop", False)),
            "practice": False,
        }
        self._snap = EngineSnapshot(
            beep=self._states["beep"],
            alert=self._states["alert"],
            ontop=self._states["ontop"],
            practice=False,
            practice_phase="off",
            practice_countdown_s=0.0,
            practice_remaining_s=0.0,
        )
        self._preview_jpeg: bytes | None = None
        self._preview_wanted = False
        self._last_preview_at = 0.0
        self._ontop_listeners: list = []

    # ---- public control -----------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        # Re-apply side-car monitors if they were on last time.
        if self._states.get("alert"):
            self._alert.start()
        # Practice is never auto-started from preferences.
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="EyeRhythmEngine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._alert.stop()
        self._stop_practice_session()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=5.0)
        self._thread = None
        try:
            self._screen_time.save()
        except Exception:
            pass
        # Persist durable toggles only (not practice).
        try:
            tgl = self.get_toggles()
            preferences.set_toggles(
                beep=tgl["beep"],
                alert=tgl["alert"],
                ontop=tgl["ontop"],
            )
        except Exception:
            pass

    def snapshot(self) -> EngineSnapshot:
        with self._lock:
            s = EngineSnapshot(**asdict(self._snap))
            return s

    def latest_preview_jpeg(self) -> bytes | None:
        with self._lock:
            return self._preview_jpeg

    def set_preview_wanted(self, wanted: bool) -> None:
        with self._lock:
            self._preview_wanted = bool(wanted)
            if not wanted:
                self._preview_jpeg = None

    def set_toggle(self, name: str, value: bool | None = None) -> dict[str, bool]:
        """
        Set or flip a toggle: beep | alert | ontop | practice.

        If ``value`` is None, flip current state.
        """
        if name not in self._states:
            raise ValueError(f"unknown toggle: {name}")
        with self._lock:
            if value is None:
                self._states[name] = not self._states[name]
            else:
                self._states[name] = bool(value)
            new_val = self._states[name]

            if name == "alert":
                if new_val:
                    self._alert.start()
                else:
                    self._alert.stop()

            if name == "practice":
                if new_val:
                    # 10 s instruction countdown, then 2 min of beeps.
                    # (Must release lock before starting threads that may join.)
                    pass
                else:
                    pass

            if name == "ontop":
                for cb in list(self._ontop_listeners):
                    try:
                        cb(new_val)
                    except Exception:
                        pass

            self._snap.beep = self._states["beep"]
            self._snap.alert = self._states["alert"]
            self._snap.ontop = self._states["ontop"]
            self._snap.practice = self._states["practice"]
            # Persist durable toggles only — practice is session-local.
            try:
                preferences.set_toggles(
                    beep=self._states["beep"],
                    alert=self._states["alert"],
                    ontop=self._states["ontop"],
                )
            except Exception:
                pass
            practice_on = self._states["practice"] and name == "practice"
            practice_off = (not self._states["practice"]) and name == "practice"

        # Start/stop practice outside the lock to avoid deadlocks with join().
        if practice_on:
            self._begin_practice_session()
        elif practice_off:
            self._stop_practice_session()

        with self._lock:
            return dict(self._states)

    def _begin_practice_session(self) -> None:
        """Start 10s countdown, then active beeping practice."""
        self._stop_practice_session(clear_toggle=False)
        self._countdown_stop.clear()
        self._countdown_ends = time.monotonic() + PRACTICE_COUNTDOWN_S
        with self._lock:
            self._states["practice"] = True
            self._practice_phase = "countdown"
            self._snap.practice = True
            self._snap.practice_phase = "countdown"
            self._snap.practice_countdown_s = float(PRACTICE_COUNTDOWN_S)
            self._snap.practice_remaining_s = 0.0
            # Clear regularity now so the card shows “warming up” during prep.
            self._regularity.reset()
            self._snap.regularity = None
            self._snap.regularity_ready = False
            self._snap.regularity_gaps = 0
        self._countdown_thread = threading.Thread(
            target=self._countdown_run, name="PracticeCountdown", daemon=True)
        self._countdown_thread.start()
        _log(f"practice countdown {int(PRACTICE_COUNTDOWN_S)}s — read instructions")

    def _countdown_run(self) -> None:
        while not self._countdown_stop.is_set():
            left = 0.0
            if self._countdown_ends is not None:
                left = max(0.0, self._countdown_ends - time.monotonic())
            with self._lock:
                self._snap.practice_countdown_s = round(left, 1)
                self._snap.practice_phase = "countdown"
            if left <= 0:
                break
            if self._countdown_stop.wait(0.1):
                return
        if self._countdown_stop.is_set():
            return
        # Countdown done → active practice with fresh regularity.
        self._regularity.reset()
        with self._lock:
            self._practice_phase = "active"
            self._snap.practice_phase = "active"
            self._snap.practice_countdown_s = 0.0
            self._snap.practice_remaining_s = float(PRACTICE_DURATION_S)
            self._snap.regularity = None
            self._snap.regularity_ready = False
            self._snap.regularity_gaps = 0
        self._practice.start()
        _log(f"practice active for {int(PRACTICE_DURATION_S)}s")

    def _stop_practice_session(self, *, clear_toggle: bool = True) -> None:
        """Cancel countdown + coach; optionally clear the practice toggle."""
        self._countdown_stop.set()
        t = self._countdown_thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2.0)
        self._countdown_thread = None
        self._countdown_ends = None
        self._practice.stop()
        with self._lock:
            self._practice_phase = "off"
            if clear_toggle:
                self._states["practice"] = False
            self._snap.practice = self._states.get("practice", False) and not clear_toggle
            if clear_toggle:
                self._snap.practice = False
            self._snap.practice_phase = "off"
            self._snap.practice_countdown_s = 0.0
            self._snap.practice_remaining_s = 0.0

    def _on_practice_finished(self) -> None:
        """Called by PracticeCoach when the timed session ends naturally."""
        with self._lock:
            self._states["practice"] = False
            self._practice_phase = "off"
            self._snap.practice = False
            self._snap.practice_phase = "off"
            self._snap.practice_countdown_s = 0.0
            self._snap.practice_remaining_s = 0.0
        _log(f"practice session finished ({int(PRACTICE_DURATION_S)}s)")

    def _note_blink_pulse(self) -> None:
        """UI: orange pulse on Beep (if on) / Practice (if on) dots."""
        with self._lock:
            self._last_blink_at = time.time()
            self._snap.last_blink_at = self._last_blink_at

    def _note_alert_beep(self) -> None:
        """UI: red pulse on Alert dot when low-rate alert beeps."""
        with self._lock:
            self._last_alert_beep_at = time.time()
            self._snap.last_alert_beep_at = self._last_alert_beep_at

    def get_toggles(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._states)

    def on_ontop_change(self, callback) -> None:
        """Register a callback(bool) when always-on-top changes (for pywebview)."""
        self._ontop_listeners.append(callback)

    # ---- internals ----------------------------------------------------

    def _publish(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._snap, k):
                    setattr(self._snap, k, v)
            self._snap.beep = self._states["beep"]
            self._snap.alert = self._states["alert"]
            self._snap.ontop = self._states["ontop"]
            self._snap.practice = self._states["practice"]
            self._snap.practice_phase = self._practice_phase
            self._snap.last_blink_at = self._last_blink_at
            self._snap.last_alert_beep_at = self._last_alert_beep_at
            if self._practice_phase == "countdown" and self._countdown_ends is not None:
                self._snap.practice_countdown_s = round(
                    max(0.0, self._countdown_ends - time.monotonic()), 1)
                self._snap.practice_remaining_s = 0.0
            elif self._practice_phase == "active":
                self._snap.practice_countdown_s = 0.0
                self._snap.practice_remaining_s = round(
                    self._practice.remaining_s, 1)
            else:
                self._snap.practice_countdown_s = 0.0
                self._snap.practice_remaining_s = 0.0
            self._snap.timestamp = time.time()

    def _face_roi_xyxy(
        self,
        frame: np.ndarray,
        res: FrameResult,
        *,
        pad: float = 0.35,
    ) -> tuple[int, int, int, int] | None:
        """
        Bounding box around the face mesh, with padding, clamped to the frame.

        Returns ``(x1, y1, x2, y2)`` in pixel coords, or ``None`` if no face.
        Uses a square crop (fits the Lens stage better).
        """
        if not res.face_found or not res.all_points:
            return None
        h, w = frame.shape[:2]
        xs = [float(p[0]) * w for p in res.all_points]
        ys = [float(p[1]) * h for p in res.all_points]
        if not xs or not ys:
            return None

        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        bw = max(1.0, x2 - x1)
        bh = max(1.0, y2 - y1)

        # Expand by padding.
        x1 -= bw * pad
        x2 += bw * pad
        y1 -= bh * pad
        y2 += bh * pad

        # Square crop centred on the face (stable look in the avatar stage).
        cx = 0.5 * (x1 + x2)
        cy = 0.5 * (y1 + y2)
        side = max(x2 - x1, y2 - y1)
        half = 0.5 * side
        x1, x2 = cx - half, cx + half
        y1, y2 = cy - half, cy + half

        ix1 = int(max(0, min(w - 1, x1)))
        iy1 = int(max(0, min(h - 1, y1)))
        ix2 = int(max(0, min(w, x2)))
        iy2 = int(max(0, min(h, y2)))
        if ix2 - ix1 < 24 or iy2 - iy1 < 24:
            return None
        return ix1, iy1, ix2, iy2

    def _draw_eye_outlines(
        self,
        frame: np.ndarray,
        res: FrameResult,
        *,
        origin_xy: tuple[int, int] = (0, 0),
        src_wh: tuple[int, int] | None = None,
        display_scale: float = 1.0,
    ) -> None:
        """
        Draw hollow red eye outlines only while eyes are closed (blink).

        Eyes open / no face → leave the stream raw.
        Landmarks are normalized (0…1) on the *source* camera frame (same
        geometry as the process frame). ``origin_xy`` / ``src_wh`` map into
        the crop; ``display_scale`` remaps crop pixels after the crop is
        resized to the preview display size.
        """
        if not res.face_found or not res.eyes_closed:
            return
        fh, fw = frame.shape[:2]
        if src_wh is None:
            src_w, src_h = fw / max(display_scale, 1e-6), fh / max(display_scale, 1e-6)
            ox, oy = 0.0, 0.0
        else:
            src_w, src_h = float(src_wh[0]), float(src_wh[1])
            ox, oy = float(origin_xy[0]), float(origin_xy[1])
        scale = float(display_scale) if display_scale > 0 else 1.0

        def to_px(nx: float, ny: float) -> tuple[int, int]:
            x = int(round((float(nx) * src_w - ox) * scale))
            y = int(round((float(ny) * src_h - oy) * scale))
            return x, y

        # Hollow outline only — lid/iris stay visible under the stroke.
        outline_color = (40, 40, 230)  # BGR red
        thickness = max(1, int(round(2 * scale))) if scale >= 0.75 else 2

        for pts in (res.left_eye_points, res.right_eye_points):
            if not pts or len(pts) < 3:
                continue
            poly: list[tuple[int, int]] = []
            for nx, ny in pts:
                x, y = to_px(nx, ny)
                # Clamp lightly so a point just outside still contributes to the curve
                x = max(-2, min(fw + 1, x))
                y = max(-2, min(fh + 1, y))
                poly.append((x, y))
            arr = np.asarray(poly, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(
                frame,
                [arr],
                isClosed=True,
                color=outline_color,
                thickness=thickness,
                lineType=cv2.LINE_AA,
            )

    def _encode_preview(self, display_frame: np.ndarray, res: FrameResult) -> None:
        """
        Build a JPEG from the *full-resolution* camera frame.

        Face ROI is computed in display-frame pixels from normalized landmarks
        (valid because process frames are a uniform scale of the same image).
        The crop is then resized to PREVIEW_MAX_WIDTH; eye outlines are drawn
        with coordinates remapped by the same scale.
        """
        now = time.monotonic()
        if now - self._last_preview_at < PREVIEW_MIN_INTERVAL_S:
            return
        self._last_preview_at = now

        h, w = display_frame.shape[:2]
        roi = self._face_roi_xyxy(display_frame, res) if res.face_found else None

        if roi is not None:
            x1, y1, x2, y2 = roi
            out = display_frame[y1:y2, x1:x2].copy()
            out, disp_scale = _resize_to_preview_width(out)
            self._draw_eye_outlines(
                out,
                res,
                origin_xy=(x1, y1),
                src_wh=(w, h),
                display_scale=disp_scale,
            )
        else:
            # No face → full camera frame, scaled to preview width.
            out = display_frame.copy()
            out, disp_scale = _resize_to_preview_width(out)
            self._draw_eye_outlines(
                out, res, display_scale=disp_scale)

        ok, buf = cv2.imencode(
            ".jpg", out,
            [int(cv2.IMWRITE_JPEG_QUALITY), PREVIEW_JPEG_QUALITY])
        if ok:
            with self._lock:
                self._preview_jpeg = buf.tobytes()

    def _run(self) -> None:
        _log("engine starting")
        self._publish(running=True, camera_message="opening camera",
                      camera_ok=False)

        # Detector may fail if model missing — surface that to UI.
        try:
            self._detector = BlinkDetector(self.model_path)
        except Exception as exc:
            _log(f"detector init failed: {exc}")
            self._publish(
                running=False,
                camera_ok=False,
                camera_message=f"model/detector error: {exc}",
            )
            return

        cap = open_camera(self.camera_index)
        if cap is None:
            self._publish(
                camera_ok=False,
                camera_message=f"camera {self.camera_index} not usable",
            )
        else:
            self._publish(camera_ok=True, camera_message="live")

        t0 = time.monotonic()
        fps, frames = 0.0, 0
        fps_t = t0
        last_ts_ms = -1
        read_fails = 0
        reopen_attempt = 0
        last_res = FrameResult()
        face_absent_streak = 0
        # Start at face rate so first-second UX feels responsive.
        frame_interval_s = FACE_INTERVAL_S
        _log(
            f"low-power profile: process_width={PROCESS_MAX_WIDTH} "
            f"preview_width={PREVIEW_MAX_WIDTH} "
            f"face={FACE_FPS:.0f}fps no_face={NO_FACE_FPS:.0f}fps "
            f"grace={NO_FACE_GRACE_FRAMES}"
        )

        try:
            while not self._stop.is_set():
                loop_start = time.monotonic()
                # In no-face mode the camera may buffer many frames; drain a few.
                drain = 3 if frame_interval_s >= NO_FACE_INTERVAL_S * 0.9 else 0
                ok, frame = _read_frame(cap, drain=drain)

                if not ok or _frame_is_black(frame):
                    read_fails += 1
                    face_absent_streak += 1
                    if face_absent_streak >= NO_FACE_GRACE_FRAMES:
                        frame_interval_s = NO_FACE_INTERVAL_S
                    self._screen_time.tick(False)
                    self._alert.update(last_res.blinks_per_minute, False)
                    self._publish(
                        face_found=False,
                        camera_ok=False,
                        camera_message="reconnecting…" if read_fails >= 3
                        else "no signal",
                        continuous_bpm=last_res.blinks_per_minute,
                        average_bpm=self._screen_time.avg_blinks_per_minute,
                        screen_time=self._screen_time.formatted(),
                        screen_time_seconds=self._screen_time.seconds_today,
                        blinks_today=self._screen_time.blinks_today,
                        fps=round(fps, 1),
                        regularity=self._regularity.score,
                        regularity_ready=self._regularity.score is not None,
                        regularity_gaps=self._regularity.gap_count,
                    )

                    if read_fails >= READ_FAILS_BEFORE_REOPEN:
                        cap = _reopen_camera(cap, self.camera_index, reopen_attempt)
                        reopen_attempt += 1
                        read_fails = 0
                        if cap is not None:
                            self._publish(camera_ok=True, camera_message="live")
                    time.sleep(0.02)
                    continue

                if read_fails or reopen_attempt:
                    if reopen_attempt:
                        _log("camera stream healthy again")
                    read_fails = 0
                    reopen_attempt = 0
                    self._publish(camera_ok=True, camera_message="live")

                # Keep full camera frame for Lens; process a smaller copy.
                display_frame = frame
                process_frame = _downscale_for_process(frame)

                ts_ms = max(int((time.monotonic() - t0) * 1000), last_ts_ms + 1)
                last_ts_ms = ts_ms

                with self._lock:
                    want_preview = self._preview_wanted

                try:
                    # Skip mesh packing unless the Lens preview is open.
                    # Landmarks are normalized — valid on display_frame too
                    # because process_frame is a uniform scale of the same image.
                    res = self._detector.process_frame(
                        process_frame, ts_ms, include_mesh=want_preview)
                except Exception as exc:
                    _log(f"frame processing error (skipped): {exc}")
                    self._screen_time.tick(False)
                    elapsed = time.monotonic() - loop_start
                    remaining = frame_interval_s - elapsed
                    if remaining > 0:
                        time.sleep(remaining)
                    continue

                last_res = res
                self._screen_time.tick(res.face_found)

                # Adaptive duty cycle: full rate with face, crawl when alone.
                if res.face_found:
                    face_absent_streak = 0
                    frame_interval_s = FACE_INTERVAL_S
                else:
                    face_absent_streak += 1
                    if face_absent_streak >= NO_FACE_GRACE_FRAMES:
                        frame_interval_s = NO_FACE_INTERVAL_S

                if res.blink_just_counted:
                    self._screen_time.add_blink()
                    # During practice countdown, ignore gaps (user is reading).
                    # During active practice, score against the 3 s beep cadence.
                    with self._lock:
                        phase = self._practice_phase
                    if phase == "active":
                        self._regularity.record_blink(
                            time.monotonic(),
                            target_interval=PRACTICE_INTERVAL_S,
                        )
                    elif phase == "off":
                        self._regularity.record_blink(time.monotonic())
                    # phase == "countdown": do not update regularity
                    self._note_blink_pulse()
                    # During the 10s instruction countdown, skip blink-beeps.
                    if self._states["beep"] and phase != "countdown":
                        self._beeper.beep()

                self._alert.update(res.blinks_per_minute, res.face_found)

                frames += 1
                now = time.monotonic()
                if now - fps_t >= 1.0:
                    fps = frames / (now - fps_t)
                    frames, fps_t = 0, now

                if want_preview:
                    self._encode_preview(display_frame, res)

                reg = self._regularity.score
                self._publish(
                    continuous_bpm=round(res.blinks_per_minute, 1),
                    average_bpm=round(self._screen_time.avg_blinks_per_minute, 1),
                    screen_time=self._screen_time.formatted(),
                    screen_time_seconds=self._screen_time.seconds_today,
                    fps=round(fps, 1),
                    regularity=reg,
                    regularity_ready=reg is not None,
                    regularity_gaps=self._regularity.gap_count,
                    blinks_today=self._screen_time.blinks_today,
                    session_blinks=res.blink_count,
                    eyes_closed=res.eyes_closed,
                    face_found=res.face_found,
                    blink_score=round(res.blink_score, 3),
                    camera_ok=True,
                    camera_message="live",
                    is_frontal=res.is_frontal,
                    has_glasses=res.has_glasses,
                    low_light=res.low_light,
                    running=True,
                )

                # Pace to current adaptive interval (face 17 / no-face 3).
                elapsed = time.monotonic() - loop_start
                remaining = frame_interval_s - elapsed
                if remaining > 0:
                    time.sleep(remaining)

        finally:
            _log("engine stopping")
            self._alert.stop()
            self._stop_practice_session()
            try:
                self._screen_time.save()
            except Exception:
                pass
            if self._detector is not None:
                try:
                    self._detector.close()
                except Exception:
                    pass
            _release_camera(cap)
            self._publish(running=False, camera_message="stopped", camera_ok=False)


def preview_data_url(jpeg_bytes: bytes | None) -> str | None:
    """Return a data-URL for the React <img>, or None."""
    if not jpeg_bytes:
        return None
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"
