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
import math
import platform
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from blink_core import BlinkDetector, FrameResult
from blink_core.screentime import ScreenTimeTracker
from blink_core.interblink_hours import InterBlinkHourTracker
from app.beeper import Beeper
from app import preferences
from app.eye_score import ocular_rhythm_index
from app.regularity import RegularityTracker
# Blink-gated CPU pacing (30 fps + post-blink rest / 1 fps no-face).
# Easy rollback: remove this import and restore the previous FACE_FPS=17 /
# NO_FACE_FPS=3 constants + inline interval logic in the camera loop.
from app.frame_pacer import FACE_FPS, FramePacer, NO_FACE_FPS

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
# Rolling window used to judge low-rate *trend* (not a single instant dip).
ALERT_TREND_WINDOW_S = 300.0  # last 5 minutes of face-present rate samples
# Do not store a sample more often than this (keeps the deque small).
ALERT_TREND_SAMPLE_S = 1.0

# Looking down this far (bottom / left-bottom / right-bottom) is off-screen.
# Pitch is negative when looking down. Change this one number to retune.
LOOK_DOWN_OFFSCREEN_DEG = 20.0
# Stay off-screen until pitch rises this many degrees back toward level.
LOOK_DOWN_OFFSCREEN_HYSTERESIS_DEG = 1.5

# Practice coach: metronome for target blink rhythm (~20 blinks/min)
PRACTICE_INTERVAL_S = 3.0
# Read instructions (and full-screen visual cue intro) first, then beep.
PRACTICE_COUNTDOWN_S = 20.0
PRACTICE_DURATION_S = 120.0
# After active practice, hold results (rate + regularity) on screen.
PRACTICE_SUMMARY_S = 20.0

# Camera resilience
READ_FAILS_BEFORE_REOPEN = 8
REOPEN_INITIAL_WAIT_S = 0.4
REOPEN_BACKOFF_MAX_S = 5.0
REOPEN_WARMUP_READS = 10

# Low-power capture profile (target ~20% of one core on typical laptops).
# MediaPipe Face Landmarker dominates CPU — process a small frame; display
# uses the full-res camera crop with landmarks remapped after inference.
#
# Frame *rate* policy (30 fps face / post-blink sleep / 1 fps no-face) lives
# entirely in ``app.frame_pacer`` so it can be rolled back without touching
# detection, screen-time, regularity, or research logging.
PROCESS_MAX_WIDTH = 480          # MediaPipe input width; height keeps aspect
DISPLAY_CAPTURE_MAX_WIDTH = 1280 # camera hint for a sharper Lens crop

# Preview encoding (only when UI requests camera)
PREVIEW_MAX_WIDTH = 640          # displayed crop / full-frame width
PREVIEW_JPEG_QUALITY = 82
PREVIEW_MIN_INTERVAL_S = 0.12  # ~8 fps ceiling for the stream
# Legacy alias (logs / older call sites)
CAPTURE_MAX_WIDTH = PROCESS_MAX_WIDTH


def look_down_offscreen(
    pitch_deg: float | None,
    *,
    currently_off: bool,
    angle_deg: float | None = None,
    direction: str | None = None,
    threshold_deg: float = LOOK_DOWN_OFFSCREEN_DEG,
    hysteresis_deg: float = LOOK_DOWN_OFFSCREEN_HYSTERESIS_DEG,
) -> bool:
    """
    True when the user is looking down and the Look-angle card is past 20°.

    The card shows the combined face-to-camera angle (yaw + pitch). A
    down-left / down-right glance can be 25° on the card while pitch is
    only −12°, which used to miss off-screen. We now use that same card
    angle once the face is aimed downward (``bottom`` / ``left-bottom`` /
    ``right-bottom``). Pure left/right (no down) stays on-screen.
    """
    looking_down = isinstance(direction, str) and direction.endswith("bottom")
    if not looking_down:
        try:
            looking_down = (
                pitch_deg is not None and float(pitch_deg) <= -8.0
            )
        except (TypeError, ValueError):
            looking_down = False
    if not looking_down:
        return False

    measure: float | None = None
    for raw in (angle_deg, pitch_deg):
        if raw is None:
            continue
        try:
            value = abs(float(raw))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            measure = value
            break
    if measure is None:
        return False

    limit = float(threshold_deg)
    if currently_off:
        limit = max(0.0, limit - float(hysteresis_deg))
    return measure >= limit


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
    Background beeps while face present and rate is low — with trend guard.

    Beep only when **all** of these hold:
      * face is present,
      * face-break / first-face warmup is finished,
      * **current** continuous BPM is below ``ALERT_BPM_THRESHOLD`` (10)
        but **not zero** (0 means no usable face / empty window — ignored),
      * **average** continuous BPM over the last ``ALERT_TREND_WINDOW_S``
        (5 minutes of **genuine** face-present, non-zero samples) is also
        below that threshold.

    Samples with BPM ≤ 0 are never stored in the trend and never count as
    “low rate” (those are no-face / unusable readings, not genuine low blinking).

    As soon as the **current** rate rises to ≥ threshold, beeps stop
    immediately (even if the 5-minute average is still low).

    Alert beeps are also suppressed for ``ALERT_WARMUP_S`` (default 60 s) after:
      * construction / first face of the session, and
      * face re-detection after an absence of ``FACE_BREAK_S`` or more.
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
        # True while the latest update reported a face.
        self._face_present = False
        # Monotonic time when the current no-face stretch began (None if face
        # is present or we have not yet observed a loss after a face).
        self._absent_since: float | None = time.monotonic()
        # Have we ever seen a face this process lifetime?
        self._ever_had_face = False
        # Rolling 5-minute face-present rate history: (monotonic_t, bpm).
        self._trend: deque[tuple[float, float]] = deque()
        self._last_trend_sample_at = 0.0

    def update(self, bpm: float, face_found: bool) -> None:
        """
        Feed latest detection. Safe to call every camera frame whether or not
        the alert thread is running (state is kept warm for face-break logic).
        """
        with self._lock:
            now = time.monotonic()
            if face_found:
                if not self._face_present:
                    # Rising edge: face just (re)appeared.
                    self._on_face_reappeared(now)
                self._face_present = True
                self._ever_had_face = True
                self._absent_since = None
                # Only genuine rates (BPM > 0). Zero is treated as no usable
                # face / empty window — must not inflate “low rate” time.
                if float(bpm) > 0.0:
                    self._record_trend_sample(now, float(bpm))
            else:
                if self._face_present:
                    # Falling edge: start the absence clock exactly once.
                    self._absent_since = now
                elif self._absent_since is None:
                    # Never saw a face yet, or state was reset — count as absent.
                    self._absent_since = now
                self._face_present = False
            self._bpm = float(bpm)
            self._face_found = bool(face_found)
            self._prune_trend(now)

    def _record_trend_sample(self, now: float, bpm: float) -> None:
        """
        Append a genuine face-present rate sample (throttled); caller holds lock.

        BPM must be > 0 — zeros are no-face / empty-window noise and must not
        enter the 5-minute low-rate trend.
        """
        if bpm <= 0.0:
            return
        if (now - self._last_trend_sample_at) < ALERT_TREND_SAMPLE_S:
            # Refresh the latest sample's bpm so the head stays current
            # (only with a genuine non-zero reading).
            if self._trend:
                t0, _ = self._trend[-1]
                if now - t0 < ALERT_TREND_SAMPLE_S * 1.5:
                    self._trend[-1] = (t0, bpm)
                    return
            return
        self._trend.append((now, bpm))
        self._last_trend_sample_at = now

    def _prune_trend(self, now: float) -> None:
        """Drop samples older than the 5-minute window; caller holds lock."""
        cutoff = now - ALERT_TREND_WINDOW_S
        while self._trend and self._trend[0][0] < cutoff:
            self._trend.popleft()

    def _trend_average_bpm(self, now: float) -> float | None:
        """
        Time-weighted average of continuous BPM over the last 5 minutes.

        Uses only genuine samples (BPM > 0). Zero-rate gaps are skipped so
        no-face / empty-window zeros cannot drag the average down.
        None if there is no usable history yet.
        """
        self._prune_trend(now)
        # Keep only positive-rate samples (defensive if any zeros slipped in).
        pts = [(t, v) for t, v in self._trend if v > 0.0]
        if not pts:
            return None
        # Time-weight consecutive genuine samples; do not bridge long gaps
        # with a zero-rate span (those gaps are not “low blinking”).
        total_w = 0.0
        total_v = 0.0
        max_bridge = ALERT_TREND_SAMPLE_S * 3.0  # ~3 s between samples
        for i, (t, v) in enumerate(pts):
            if i + 1 < len(pts):
                t_next = pts[i + 1][0]
                dt = max(0.0, t_next - t)
                # Large hole = face/zero gap — do not count that empty time.
                if dt > max_bridge:
                    dt = ALERT_TREND_SAMPLE_S
            else:
                # Last sample: only extend a short tail to ``now`` if still live.
                dt = min(max(0.0, now - t), ALERT_TREND_SAMPLE_S)
            if dt <= 0:
                continue
            total_w += dt
            total_v += v * dt
        if total_w <= 0:
            return float(pts[-1][1])
        return total_v / total_w

    def _should_beep_locked(self, now: float) -> bool:
        """
        Beep gate (caller holds lock):
          current bpm is a genuine low rate (0 < bpm < threshold)
          AND 5-min average of genuine samples < threshold
          AND face present  AND  not in face-break warmup.
        Current rate ≥ threshold → False immediately (stop beeps).
        Current rate ≤ 0 → False (not a genuine low-blink reading).
        """
        if not self._face_found:
            return False
        if now < self._suppress_until:
            return False
        # Zero is not a genuine low count (no-face / empty window).
        if self._bpm <= 0.0:
            return False
        # Immediate stop when current rate is healthy again.
        if self._bpm >= self._threshold:
            return False
        avg = self._trend_average_bpm(now)
        if avg is None or avg <= 0.0:
            return False
        # Trend over last 5 minutes must also be below threshold.
        return avg < self._threshold

    def _on_face_reappeared(self, now: float) -> None:
        """Apply warmup after first face or after a long absence (caller holds lock)."""
        if not self._ever_had_face:
            self._suppress_until = max(self._suppress_until, now + ALERT_WARMUP_S)
            _log(
                f"alert warmup {int(ALERT_WARMUP_S)}s "
                "(fresh start / first face)"
            )
            return

        if self._absent_since is None:
            # Should not happen on a rising edge; be safe.
            return

        gap = now - self._absent_since
        if gap >= FACE_BREAK_S:
            # Long break: wait a full minute of face-present time before
            # low-rate alerts can fire (BPM window was empty / stale).
            self._suppress_until = now + ALERT_WARMUP_S
            _log(
                f"alert warmup {int(ALERT_WARMUP_S)}s "
                f"(face back after {gap:.0f}s break)"
            )

    def start(self) -> None:
        """
        Start the beep thread. Does **not** clear ``_suppress_until`` or
        absence tracking — face-break warmup must survive toggle off/on.
        """
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="AlertMonitor", daemon=True)
        self._thread.start()
        with self._lock:
            remaining = max(0.0, self._suppress_until - time.monotonic())
        if remaining > 1.0:
            _log(f"alert started — warmup {remaining:.0f}s still active")

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
                now = time.monotonic()
                # Keep trend head fresh even between sparse camera frames
                # (genuine non-zero rates only).
                if self._face_found and self._bpm > 0.0:
                    self._record_trend_sample(now, self._bpm)
                should = self._should_beep_locked(now)
            if should:
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
        self._started_wall: float = 0.0

    def start(self) -> None:
        # Restart cleanly if already running (new practice session).
        self.stop()
        self._stop.clear()
        now = time.monotonic()
        self._started_at = now
        self._ends_at = now + self._duration_s
        # Wall clock of active start — UI keys ball disappear to this + n×interval.
        self._started_wall = time.time()
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
        self._started_wall = 0.0

    @property
    def started_wall(self) -> float:
        """Wall-clock epoch when the coach started (0 if idle)."""
        return float(getattr(self, "_started_wall", 0.0) or 0.0)

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
        """
        Beep at the *end* of each interval (not immediately).

        That lines up with the full-screen ball animation: the ball travels
        for ``interval_s`` and arrives at the next waypoint on the beep.
        """
        finished_naturally = False
        try:
            while not self._stop.is_set():
                remaining = self.remaining_s
                if remaining <= 0:
                    finished_naturally = True
                    break
                wait = min(self._interval_s, remaining)
                if self._stop.wait(wait):
                    break
                # Beep only after a full interval so arrivals stay on cadence.
                # A truncated final wait (session end) does not get a beep.
                if wait + 1e-3 >= self._interval_s:
                    self._beeper.beep()
                if self.remaining_s <= 0:
                    finished_naturally = True
                    break
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
    # Ocular Rhythm Index — 70 % rate + 30 % regularity (0–100).
    ocular_rhythm_index: float | None = None
    ocular_rhythm_full: bool = False
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
    # Face/eye axis vs camera optical axis (None when no face).
    face_angle_deg: float | None = None
    face_yaw_deg: float | None = None
    face_pitch_deg: float | None = None
    # "straight" | "left" | "right-top" | …  (None when no face)
    face_direction: str | None = None
    # Looking down past LOOK_DOWN_OFFSCREEN_DEG (bottom / left-bottom / right-bottom).
    off_screen: bool = False

    # Toggles
    beep: bool = False
    alert: bool = False
    ontop: bool = False
    practice: bool = False
    # "off" | "countdown" | "active" | "summary"
    practice_phase: str = "off"
    # Seconds left in the pre-start countdown (read instructions).
    practice_countdown_s: float = 0.0
    # Total countdown length (UI progress / full-screen intro).
    practice_countdown_total_s: float = PRACTICE_COUNTDOWN_S
    # Seconds left in the active beeping practice (0 when not active).
    practice_remaining_s: float = 0.0
    # Beep / ball travel interval (seconds).
    practice_interval_s: float = PRACTICE_INTERVAL_S
    # Wall-clock epoch when active practice (beeps + ball) began; 0 if idle.
    practice_active_started_at: float = 0.0
    # Post-practice results screen (seconds left; 0 when not in summary).
    practice_summary_s: float = 0.0
    # Frozen results shown on the summary screen.
    practice_result_blinks: int = 0
    practice_result_bpm: float = 0.0
    practice_result_regularity: float | None = None
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
        # Research log: inter-blink min/max/mean/median per screen-time hour.
        self._interblink_hours = InterBlinkHourTracker()
        self._interblink_hours.sync_screen_seconds(self._screen_time.seconds_today)
        self._regularity = RegularityTracker()
        self._detector: BlinkDetector | None = None
        self._last_blink_at = 0.0
        self._last_alert_beep_at = 0.0
        self._look_off_screen = False
        # Freeze rate + regularity while looking down / no-face.
        self._rate_present = False
        self._rate_absent_mono: float | None = None
        self._held_bpm = 0.0
        self._held_regularity: float | None = None
        # Practice session: countdown → active → summary.
        self._practice_phase = "off"  # off | countdown | active | summary
        self._countdown_stop = threading.Event()
        self._countdown_thread: threading.Thread | None = None
        self._countdown_ends: float | None = None
        # Wall-clock epoch when active practice began (for UI animation sync).
        self._practice_active_started_at: float = 0.0
        # Blinks counted only while practice_phase == "active".
        self._practice_blinks = 0
        # Summary hold after natural finish.
        self._summary_stop = threading.Event()
        self._summary_thread: threading.Thread | None = None
        self._summary_ends: float | None = None
        self._practice_result_blinks = 0
        self._practice_result_bpm = 0.0
        self._practice_result_regularity: float | None = None

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
            practice_countdown_total_s=float(PRACTICE_COUNTDOWN_S),
            practice_remaining_s=0.0,
            practice_interval_s=float(PRACTICE_INTERVAL_S),
            practice_active_started_at=0.0,
            practice_summary_s=0.0,
            practice_result_blinks=0,
            practice_result_bpm=0.0,
            practice_result_regularity=None,
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
        try:
            self._interblink_hours.save()
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
        """Start instruction countdown, then active beeping + visual practice."""
        self._stop_practice_session(clear_toggle=False)
        self._countdown_stop.clear()
        self._countdown_ends = time.monotonic() + PRACTICE_COUNTDOWN_S
        self._practice_active_started_at = 0.0
        self._practice_blinks = 0
        self._practice_result_blinks = 0
        self._practice_result_bpm = 0.0
        self._practice_result_regularity = None
        with self._lock:
            self._states["practice"] = True
            self._practice_phase = "countdown"
            self._snap.practice = True
            self._snap.practice_phase = "countdown"
            self._snap.practice_countdown_s = float(PRACTICE_COUNTDOWN_S)
            self._snap.practice_countdown_total_s = float(PRACTICE_COUNTDOWN_S)
            self._snap.practice_remaining_s = 0.0
            self._snap.practice_interval_s = float(PRACTICE_INTERVAL_S)
            self._snap.practice_active_started_at = 0.0
            self._snap.practice_summary_s = 0.0
            self._snap.practice_result_blinks = 0
            self._snap.practice_result_bpm = 0.0
            self._snap.practice_result_regularity = None
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
        self._practice_blinks = 0
        # Start coach first, then publish its wall clock so UI beeps/disappear match.
        self._practice.start()
        started_wall = self._practice.started_wall or time.time()
        self._practice_active_started_at = started_wall
        with self._lock:
            self._practice_phase = "active"
            self._snap.practice_phase = "active"
            self._snap.practice_countdown_s = 0.0
            self._snap.practice_remaining_s = float(PRACTICE_DURATION_S)
            self._snap.practice_interval_s = float(PRACTICE_INTERVAL_S)
            self._snap.practice_active_started_at = started_wall
            self._snap.practice_summary_s = 0.0
            self._snap.regularity = None
            self._snap.regularity_ready = False
            self._snap.regularity_gaps = 0
        _log(f"practice active for {int(PRACTICE_DURATION_S)}s")

    def _stop_summary_thread(self) -> None:
        self._summary_stop.set()
        t = self._summary_thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2.0)
        self._summary_thread = None
        self._summary_ends = None

    def _stop_practice_session(self, *, clear_toggle: bool = True) -> None:
        """Cancel countdown + coach + summary; optionally clear the practice toggle."""
        self._countdown_stop.set()
        t = self._countdown_thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2.0)
        self._countdown_thread = None
        self._countdown_ends = None
        self._practice.stop()
        self._stop_summary_thread()
        self._practice_active_started_at = 0.0
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
            self._snap.practice_active_started_at = 0.0
            self._snap.practice_summary_s = 0.0

    def _on_practice_finished(self) -> None:
        """
        Active coach finished naturally → freeze results and hold summary
        for PRACTICE_SUMMARY_S, then fully close practice.
        """
        self._practice_active_started_at = 0.0
        # Session blink rate: blinks during active practice ÷ practice minutes.
        minutes = max(1e-6, PRACTICE_DURATION_S / 60.0)
        blinks = int(self._practice_blinks)
        bpm = round(blinks / minutes, 1)
        reg = self._regularity.score
        self._practice_result_blinks = blinks
        self._practice_result_bpm = bpm
        self._practice_result_regularity = reg

        self._stop_summary_thread()
        self._summary_stop.clear()
        self._summary_ends = time.monotonic() + PRACTICE_SUMMARY_S
        with self._lock:
            self._states["practice"] = True
            self._practice_phase = "summary"
            self._snap.practice = True
            self._snap.practice_phase = "summary"
            self._snap.practice_countdown_s = 0.0
            self._snap.practice_remaining_s = 0.0
            self._snap.practice_active_started_at = 0.0
            self._snap.practice_summary_s = float(PRACTICE_SUMMARY_S)
            self._snap.practice_result_blinks = blinks
            self._snap.practice_result_bpm = bpm
            self._snap.practice_result_regularity = reg
        self._summary_thread = threading.Thread(
            target=self._summary_run, name="PracticeSummary", daemon=True)
        self._summary_thread.start()
        _log(
            f"practice summary {int(PRACTICE_SUMMARY_S)}s — "
            f"blinks={blinks} bpm={bpm} reg={reg}"
        )

    def _summary_run(self) -> None:
        """Hold results on screen, then end practice and close the overlay."""
        while not self._summary_stop.is_set():
            left = 0.0
            if self._summary_ends is not None:
                left = max(0.0, self._summary_ends - time.monotonic())
            with self._lock:
                self._snap.practice_summary_s = round(left, 1)
                self._snap.practice_phase = "summary"
                self._snap.practice = True
                self._snap.practice_result_blinks = self._practice_result_blinks
                self._snap.practice_result_bpm = self._practice_result_bpm
                self._snap.practice_result_regularity = (
                    self._practice_result_regularity
                )
            if left <= 0:
                break
            if self._summary_stop.wait(0.1):
                return
        if self._summary_stop.is_set():
            return
        # Summary done → fully close practice (window returns to normal).
        with self._lock:
            self._states["practice"] = False
            self._practice_phase = "off"
            self._snap.practice = False
            self._snap.practice_phase = "off"
            self._snap.practice_summary_s = 0.0
            self._snap.practice_remaining_s = 0.0
            self._snap.practice_active_started_at = 0.0
        self._summary_ends = None
        self._summary_thread = None
        _log("practice summary finished — session closed")

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

    def _sync_presence_hold(
        self,
        present: bool,
        res: FrameResult,
        ts_ms: int,
    ) -> None:
        """
        Freeze blink rate and regularity while off-screen / no-face.

        On return, shift only the 60s rate window so BPM continues from the
        last on-screen value. Regularity keeps its last score (the pause is
        not an inter-blink gap).
        """
        now = time.monotonic()
        if present:
            if not self._rate_present and self._rate_absent_mono is not None:
                gap_ms = (now - self._rate_absent_mono) * 1000.0
                if gap_ms > 250.0 and self._detector is not None:
                    self._detector.hold_rate_across_gap(gap_ms)
                    res.blinks_per_minute = self._detector.blinks_per_minute_at(
                        ts_ms)
            self._rate_present = True
            self._rate_absent_mono = None
            self._held_bpm = float(res.blinks_per_minute or 0.0)
            if self._regularity.score is not None:
                self._held_regularity = self._regularity.score
            return
        if self._rate_present:
            self._rate_absent_mono = now
            self._regularity.note_break()
        self._rate_present = False

    def _update_look_down_offscreen(self, res: FrameResult) -> bool:
        """Hysteresis around LOOK_DOWN_OFFSCREEN_DEG. False when no face."""
        if not res.face_found:
            self._look_off_screen = False
            return False
        self._look_off_screen = look_down_offscreen(
            res.face_pitch_deg,
            currently_off=self._look_off_screen,
            angle_deg=res.face_angle_deg,
            direction=res.face_direction,
        )
        return self._look_off_screen

    @staticmethod
    def _ori_fields(bpm: float, regularity: float | None) -> dict:
        """Ocular Rhythm Index fields for EngineSnapshot."""
        reg = regularity
        ori = ocular_rhythm_index(bpm, reg)
        return {
            "ocular_rhythm_index": ori,
            "ocular_rhythm_full": (
                ori is not None and reg is not None
            ),
        }

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
            self._snap.practice_interval_s = float(PRACTICE_INTERVAL_S)
            self._snap.practice_countdown_total_s = float(PRACTICE_COUNTDOWN_S)
            self._snap.practice_active_started_at = (
                self._practice_active_started_at
                if self._practice_phase == "active"
                else 0.0
            )
            self._snap.practice_result_blinks = self._practice_result_blinks
            self._snap.practice_result_bpm = self._practice_result_bpm
            self._snap.practice_result_regularity = self._practice_result_regularity
            self._snap.last_blink_at = self._last_blink_at
            self._snap.last_alert_beep_at = self._last_alert_beep_at
            self._snap.off_screen = self._look_off_screen
            if self._practice_phase == "countdown" and self._countdown_ends is not None:
                self._snap.practice_countdown_s = round(
                    max(0.0, self._countdown_ends - time.monotonic()), 1)
                self._snap.practice_remaining_s = 0.0
                self._snap.practice_summary_s = 0.0
            elif self._practice_phase == "active":
                self._snap.practice_countdown_s = 0.0
                self._snap.practice_remaining_s = round(
                    self._practice.remaining_s, 1)
                self._snap.practice_summary_s = 0.0
            elif self._practice_phase == "summary" and self._summary_ends is not None:
                self._snap.practice_countdown_s = 0.0
                self._snap.practice_remaining_s = 0.0
                self._snap.practice_summary_s = round(
                    max(0.0, self._summary_ends - time.monotonic()), 1)
            else:
                self._snap.practice_countdown_s = 0.0
                self._snap.practice_remaining_s = 0.0
                self._snap.practice_summary_s = 0.0
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
        # Adaptive FPS / post-blink rest — see app/frame_pacer.py.
        pacer = FramePacer()
        _log(
            f"low-power profile: process_width={PROCESS_MAX_WIDTH} "
            f"preview_width={PREVIEW_MAX_WIDTH} "
            f"{pacer.describe()}"
        )

        try:
            while not self._stop.is_set():
                loop_start = time.monotonic()
                # In no-face mode the camera may buffer many frames; drain a few.
                drain = 3 if pacer.should_drain_buffer() else 0
                ok, frame = _read_frame(cap, drain=drain)

                if not ok or _frame_is_black(frame):
                    read_fails += 1
                    pacer.note_no_signal()
                    self._screen_time.tick(False)
                    self._sync_presence_hold(False, last_res, 0)
                    self._alert.update(self._held_bpm, False)
                    self._look_off_screen = False
                    held_reg = (
                        self._held_regularity
                        if self._held_regularity is not None
                        else self._regularity.score
                    )
                    self._publish(
                        face_found=False,
                        camera_ok=False,
                        camera_message="reconnecting…" if read_fails >= 3
                        else "no signal",
                        continuous_bpm=round(self._held_bpm, 1),
                        average_bpm=self._screen_time.avg_blinks_per_minute,
                        **self._ori_fields(self._held_bpm, held_reg),
                        screen_time=self._screen_time.formatted(),
                        screen_time_seconds=self._screen_time.seconds_today,
                        blinks_today=self._screen_time.blinks_today,
                        fps=round(fps, 1),
                        regularity=self._held_regularity
                        if self._held_regularity is not None
                        else self._regularity.score,
                        regularity_ready=(
                            self._held_regularity is not None
                            or self._regularity.score is not None
                        ),
                        regularity_gaps=self._regularity.gap_count,
                        face_angle_deg=None,
                        face_yaw_deg=None,
                        face_pitch_deg=None,
                        face_direction=None,
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
                    self._sync_presence_hold(False, last_res, ts_ms)
                    self._alert.update(self._held_bpm, False)
                    pacer.sleep_for_frame(loop_start)
                    continue

                last_res = res
                off_screen = self._update_look_down_offscreen(res)
                if (
                    off_screen
                    and res.blink_just_counted
                    and self._detector is not None
                ):
                    self._detector.discard_last_blink()
                    res.blink_just_counted = False
                    res.blink_count = self._detector._blink_count
                    res.blinks_per_minute = self._detector.blinks_per_minute_at(
                        ts_ms)

                present = bool(res.face_found) and not off_screen
                self._sync_presence_hold(present, res, ts_ms)
                self._screen_time.tick(present)
                # Keep research hour buckets aligned with face-present time.
                try:
                    self._interblink_hours.on_screen_seconds(
                        self._screen_time.seconds_today)
                except Exception:
                    pass

                if res.blink_just_counted:
                    self._screen_time.add_blink()
                    blink_mono = time.monotonic()
                    # Research: inter-blink gaps for every counted blink
                    # (including practice — useful for cadence studies).
                    try:
                        self._interblink_hours.on_blink(blink_mono)
                    except Exception:
                        pass
                    # During practice countdown, ignore gaps (user is reading).
                    # During active practice, score against the 3 s beep cadence.
                    with self._lock:
                        phase = self._practice_phase
                    if phase == "active":
                        # Practice-only blink tally for the end-of-session rate.
                        self._practice_blinks += 1
                        self._regularity.record_blink(
                            blink_mono,
                            target_interval=PRACTICE_INTERVAL_S,
                        )
                    elif phase == "off":
                        self._regularity.record_blink(blink_mono)
                    # phase == "countdown" | "summary": do not update regularity
                    self._note_blink_pulse()
                    # During the 10s instruction countdown, skip blink-beeps.
                    if self._states["beep"] and phase != "countdown":
                        self._beeper.beep()

                # Adaptive FPS only (face 30 / no-face 1 + post-blink rest).
                # All other business logic above is unchanged.
                pacer.observe(
                    face_found=res.face_found,
                    blink_just_counted=res.blink_just_counted,
                )

                live_bpm = (
                    float(res.blinks_per_minute)
                    if present
                    else float(self._held_bpm)
                )
                live_reg = self._regularity.score
                if not present and self._held_regularity is not None:
                    live_reg = self._held_regularity
                self._alert.update(live_bpm, present)

                frames += 1
                now = time.monotonic()
                if now - fps_t >= 1.0:
                    fps = frames / (now - fps_t)
                    frames, fps_t = 0, now

                if want_preview:
                    self._encode_preview(display_frame, res)

                self._publish(
                    continuous_bpm=round(live_bpm, 1),
                    average_bpm=round(self._screen_time.avg_blinks_per_minute, 1),
                    **self._ori_fields(live_bpm, live_reg),
                    screen_time=self._screen_time.formatted(),
                    screen_time_seconds=self._screen_time.seconds_today,
                    fps=round(fps, 1),
                    regularity=live_reg,
                    regularity_ready=live_reg is not None,
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
                    face_angle_deg=res.face_angle_deg,
                    face_yaw_deg=res.face_yaw_deg,
                    face_pitch_deg=res.face_pitch_deg,
                    face_direction=res.face_direction,
                    off_screen=off_screen,
                    running=True,
                )

                # Pace: full fps, or POST_BLINK_SLEEP_S after a blink, or 1 fps.
                pacer.sleep_for_frame(loop_start)

        finally:
            _log("engine stopping")
            self._alert.stop()
            self._stop_practice_session()
            try:
                self._screen_time.save()
            except Exception:
                pass
            try:
                self._interblink_hours.save()
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
