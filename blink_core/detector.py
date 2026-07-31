"""
blink_core.detector
===================
Platform-independent eye blink detection business logic (Phase 1).

Works identically on Windows, macOS and Linux. Only the camera capture
layer (app/main.py) differs per platform.

Approach (reliability + speed focused):
  1. MediaPipe Face Landmarker (Apache 2.0) -> 478 facial landmarks
     + 52 blendshape scores per frame, real-time on CPU.
  2. Two independent eye-closure signals are fused:
       a) Blendshape scores `eyeBlinkLeft` / `eyeBlinkRight`
          (learned, robust across identities and eyeglasses)
       b) Eye Aspect Ratio (EAR, Soukupova & Cech 2016) computed
          from eye landmarks (geometric, interpretable fallback)
  3. A hysteresis state machine turns the noisy per-frame signal into
     discrete blink events (OPEN -> CLOSING -> OPEN = 1 blink), with
     debouncing so a single blink is never counted twice.

Improvements for fewer false positives / false negatives:
  - Frontal-face gate: left-eye→mouth and right-eye→mouth distances must
    agree within ~15 %.  Large asymmetry (head turned / moving) discards
    a candidate blink.
  - Adaptive low-light enhancement (CLAHE on L channel) applied only when
    mean luminance is low, improving landmark quality under dim lighting.
  - Lightweight glasses detector (horizontal edge energy on the nose-bridge
    ROI).  When glasses are present the close threshold is relaxed so that
    weaker blendshape / EAR signals still register.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision


# --------------------------------------------------------------------------
# Landmark indices (MediaPipe 478-point face mesh)
# EAR uses 6 points per eye: [outer corner, upper1, upper2,
#                             inner corner, lower2, lower1]
# --------------------------------------------------------------------------
LEFT_EYE_EAR_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_EAR_IDX = [362, 385, 387, 263, 373, 380]

LEFT_EYE_OUTLINE_IDX = [33, 7, 163, 144, 145, 153, 154, 155, 133,
                        173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE_OUTLINE_IDX = [362, 382, 381, 380, 374, 373, 390, 249, 263,
                         466, 388, 387, 386, 385, 384, 398]

# Mouth centre (upper + lower lip midpoints)
MOUTH_UPPER_IDX = 13
MOUTH_LOWER_IDX = 14

# Nose-bridge points used for glasses ROI (rough mid-face)
NOSE_BRIDGE_IDX = [6, 168, 197, 195, 5]


@dataclass
class BlinkConfig:
    """Tunable parameters of the blink state machine.

    Thresholds are ADAPTIVE: the detector tracks each person's own
    open-eye baseline (rolling 25th percentile over ~10 s) and places
    the close/open thresholds relative to it. This is what makes the
    counter reliable across different faces, eye shapes and eyeglasses
    instead of relying on one fixed magic number.
    """
    # Blink score must rise this far above the open-eye baseline
    close_delta: float = 0.25
    # ... and fall back to baseline + open_delta to re-open (hysteresis)
    open_delta: float = 0.12
    # Absolute clamps for the adaptive close threshold
    close_min: float = 0.30
    close_max: float = 0.60
    # Absolute clamps for the adaptive open threshold
    open_min: float = 0.20
    # EAR fallback (used if blendshapes are unavailable): eye counts as
    # closed when EAR drops below this fraction of the open-eye baseline
    ear_close_ratio: float = 0.72
    ear_open_ratio: float = 0.85
    # Rolling window (frames) used to estimate the open-eye baseline
    baseline_window: int = 300
    # A closure shorter than this (seconds) is treated as landmark noise
    min_blink_duration_s: float = 0.03
    # A closure longer than this is not a blink (eyes deliberately shut);
    # it is still counted once when the eyes reopen.
    long_closure_s: float = 0.8
    # Refractory period after a counted blink (debounce)
    refractory_s: float = 0.08

    # ---- anti false-positive / false-negative knobs -------------------
    # max(dL, dR) / min(dL, dR)  of eye-centres → mouth-centre distances.
    # Larger than this ⇒ head is turned / moving → discard candidate blink.
    face_turn_max_ratio: float = 1.15
    # When glasses are detected, reduce close_delta by this amount so that
    # weaker signals still cross the threshold.
    glasses_close_delta_reduction: float = 0.08
    # Mean gray value below which CLAHE enhancement is applied.
    low_light_mean: float = 70.0
    # Sobel-x mean energy on the nose-bridge ROI above which glasses are
    # considered present (tuned for typical webcam resolutions).
    glasses_edge_threshold: float = 14.0
    # Number of recent frames to smooth the glasses decision.
    glasses_smooth_window: int = 9


@dataclass
class FrameResult:
    """Everything the UI layer needs to render one frame."""
    face_found: bool = False
    blink_count: int = 0
    eyes_closed: bool = False
    blink_score: float = 0.0        # fused eye-closure score 0..1
    ear_left: float = 0.0
    ear_right: float = 0.0
    ear_avg: float = 0.0
    blend_left: float = 0.0
    blend_right: float = 0.0
    blinks_per_minute: float = 0.0
    blink_just_counted: bool = False
    left_eye_points: list = field(default_factory=list)   # normalized (x, y)
    right_eye_points: list = field(default_factory=list)
    all_points: list = field(default_factory=list)         # all 478 landmarks
    # diagnostic flags (optional for UI / debugging)
    is_frontal: bool = True
    has_glasses: bool = False
    low_light: bool = False


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _percentile(values, pct: float) -> float:
    """Percentile of an iterable without numpy (tiny windows only)."""
    data = sorted(values)
    if not data:
        return 0.0
    k = (len(data) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(data) - 1)
    frac = k - lo
    return data[lo] * (1.0 - frac) + data[hi] * frac


def eye_aspect_ratio(landmarks, idx) -> float:
    """EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)."""
    p1, p2, p3, p4, p5, p6 = (landmarks[i] for i in idx)
    horizontal = _dist(p1, p4)
    if horizontal <= 1e-6:
        return 0.0
    return (_dist(p2, p6) + _dist(p3, p5)) / (2.0 * horizontal)


def _landmark_center(landmarks, idxs):
    """Average of a set of landmark indices → simple object with .x/.y."""
    n = len(idxs)
    xs = sum(landmarks[i].x for i in idxs) / n
    ys = sum(landmarks[i].y for i in idxs) / n
    return type("Pt", (), {"x": xs, "y": ys})()


def is_face_frontal(landmarks, max_ratio: float = 1.15) -> bool:
    """
    True when left-eye-centre → mouth-centre distance and
    right-eye-centre → mouth-centre distance agree within max_ratio.
    Large asymmetry indicates yaw (head turned) or rapid movement.
    """
    left_c = _landmark_center(landmarks, LEFT_EYE_EAR_IDX)
    right_c = _landmark_center(landmarks, RIGHT_EYE_EAR_IDX)
    mouth = type("Pt", (), {
        "x": (landmarks[MOUTH_UPPER_IDX].x + landmarks[MOUTH_LOWER_IDX].x) / 2.0,
        "y": (landmarks[MOUTH_UPPER_IDX].y + landmarks[MOUTH_LOWER_IDX].y) / 2.0,
    })()
    dL = _dist(left_c, mouth)
    dR = _dist(right_c, mouth)
    if min(dL, dR) < 1e-6:
        return False
    ratio = max(dL, dR) / min(dL, dR)
    return ratio <= max_ratio


def _enhance_low_light(bgr: np.ndarray, mean_thr: float) -> tuple[np.ndarray, bool]:
    """
    Apply CLAHE on the L channel of LAB only when the frame is dim.
    Returns (possibly enhanced frame, was_low_light).
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mean_br = float(np.mean(gray))
    if mean_br >= mean_thr:
        return bgr, False
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)
    return enhanced, True


def _glasses_edge_score(bgr: np.ndarray, landmarks) -> float:
    """
    Horizontal Sobel energy on a small ROI centred on the nose bridge.
    Glasses frames produce strong horizontal edges here; bare skin does not.
    """
    h, w = bgr.shape[:2]

    def px(i):
        p = landmarks[i]
        return int(p.x * w), int(p.y * h)

    le = px(133)   # left eye inner
    re = px(362)   # right eye inner
    eye_dist = max(abs(re[0] - le[0]), 1)
    mid_x = (le[0] + re[0]) // 2
    # Bridge sits slightly above the eye-inner line
    mid_y = (le[1] + re[1]) // 2 - max(4, int(0.04 * h))

    roi_w = max(12, int(eye_dist * 0.38))
    roi_h = max(8, int(eye_dist * 0.14))
    x1 = max(0, mid_x - roi_w // 2)
    y1 = max(0, mid_y - roi_h // 2)
    x2 = min(w, mid_x + roi_w // 2)
    y2 = min(h, mid_y + roi_h // 2)
    if x2 - x1 < 6 or y2 - y1 < 4:
        return 0.0

    roi = bgr[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # slight blur reduces noise before edge measure
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    return float(np.mean(np.abs(sobelx)))


class BlinkDetector:
    """
    Feed frames in, get blink counts out.

    Usage:
        det = BlinkDetector("models/face_landmarker.task")
        result = det.process_frame(bgr_frame, timestamp_ms)
    """

    STATE_OPEN = "OPEN"
    STATE_CLOSED = "CLOSED"

    def __init__(self, model_path: str, config: BlinkConfig | None = None):
        self.config = config or BlinkConfig()
        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            output_face_blendshapes=True,
            num_faces=1,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

        self._state = self.STATE_OPEN
        self._blink_count = 0
        self._closed_since_ms: float | None = None
        self._last_blink_ms: float = -1e12
        self._blink_times_ms: deque[float] = deque(maxlen=300)
        self._start_ms: float | None = None
        self._score_hist: deque[float] = deque(
            maxlen=self.config.baseline_window)
        self._ear_hist: deque[float] = deque(
            maxlen=self.config.baseline_window)
        # smoothed glasses decision
        self._glasses_votes: deque[float] = deque(
            maxlen=self.config.glasses_smooth_window)

    # ------------------------------------------------------------------ API

    def reset(self) -> None:
        self._state = self.STATE_OPEN
        self._blink_count = 0
        self._closed_since_ms = None
        self._last_blink_ms = -1e12
        self._blink_times_ms.clear()
        self._start_ms = None
        self._score_hist.clear()
        self._ear_hist.clear()
        self._glasses_votes.clear()

    def close(self) -> None:
        self._landmarker.close()

    def process_frame(self, bgr_frame, timestamp_ms: int) -> FrameResult:
        """Process one BGR frame (OpenCV format). timestamp_ms must be
        monotonically increasing (video position or wall clock)."""
        result = FrameResult(blink_count=self._blink_count)
        if self._start_ms is None:
            self._start_ms = timestamp_ms

        cfg = self.config

        # ---- low-light enhancement (only when needed) -----------------
        frame, was_low = _enhance_low_light(bgr_frame, cfg.low_light_mean)
        result.low_light = was_low

        rgb = frame[:, :, ::-1]  # BGR -> RGB
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                            data=rgb.copy())
        detection = self._landmarker.detect_for_video(mp_image,
                                                      int(timestamp_ms))

        if not detection.face_landmarks:
            # Face lost: keep state machine but do not count anything.
            result.face_found = False
            result.blinks_per_minute = self._bpm(timestamp_ms)
            return result

        landmarks = detection.face_landmarks[0]
        result.face_found = True

        # ---- frontal-face gate ----------------------------------------
        frontal = is_face_frontal(landmarks, cfg.face_turn_max_ratio)
        result.is_frontal = frontal

        # ---- glasses detection (smoothed) -----------------------------
        edge = _glasses_edge_score(bgr_frame, landmarks)  # use original frame
        self._glasses_votes.append(edge)
        avg_edge = sum(self._glasses_votes) / len(self._glasses_votes)
        has_glasses = avg_edge >= cfg.glasses_edge_threshold
        result.has_glasses = has_glasses

        # ---- Signal 1: EAR (geometric)
        result.ear_left = eye_aspect_ratio(landmarks, LEFT_EYE_EAR_IDX)
        result.ear_right = eye_aspect_ratio(landmarks, RIGHT_EYE_EAR_IDX)
        result.ear_avg = (result.ear_left + result.ear_right) / 2.0

        # ---- Signal 2: blendshapes (learned)
        have_blend = bool(detection.face_blendshapes)
        if have_blend:
            shapes = {c.category_name: c.score
                      for c in detection.face_blendshapes[0]}
            result.blend_left = shapes.get("eyeBlinkLeft", 0.0)
            result.blend_right = shapes.get("eyeBlinkRight", 0.0)
            # Both eyes must agree -> robust against winks/landmark jitter
            result.blink_score = min(result.blend_left, result.blend_right)

        # ---- Adaptive thresholds relative to this person's baseline
        # When glasses are present, lower the close threshold so that the
        # typically weaker signals still trigger a closure.
        close_delta = cfg.close_delta
        if has_glasses:
            close_delta = max(0.12, close_delta - cfg.glasses_close_delta_reduction)

        if have_blend:
            self._score_hist.append(result.blink_score)
            baseline = _percentile(self._score_hist, 25)
            close_thr = min(cfg.close_max,
                            max(cfg.close_min, baseline + close_delta))
            open_thr = max(cfg.open_min,
                           min(close_thr - 0.08, baseline + cfg.open_delta))
            is_closed_signal = result.blink_score >= close_thr
            is_open_signal = result.blink_score <= open_thr
        else:
            self._ear_hist.append(result.ear_avg)
            ear_base = min(0.45, max(0.18,
                                     _percentile(self._ear_hist, 75)))
            # also relax EAR ratios a little for glasses
            close_r = cfg.ear_close_ratio + (0.05 if has_glasses else 0.0)
            open_r = cfg.ear_open_ratio
            is_closed_signal = result.ear_avg <= ear_base * close_r
            is_open_signal = result.ear_avg >= ear_base * open_r

        # ---- Hysteresis state machine
        counted = False
        if self._state == self.STATE_OPEN:
            if is_closed_signal:
                self._state = self.STATE_CLOSED
                self._closed_since_ms = timestamp_ms
        else:  # CLOSED
            if is_open_signal:
                closure_ms = timestamp_ms - (self._closed_since_ms
                                             or timestamp_ms)
                since_last = timestamp_ms - self._last_blink_ms
                if (closure_ms >= cfg.min_blink_duration_s * 1000.0
                        and since_last >= cfg.refractory_s * 1000.0
                        and frontal):          # <-- discard if head turned
                    self._blink_count += 1
                    self._last_blink_ms = timestamp_ms
                    self._blink_times_ms.append(timestamp_ms)
                    counted = True
                self._state = self.STATE_OPEN
                self._closed_since_ms = None

        result.eyes_closed = self._state == self.STATE_CLOSED
        result.blink_count = self._blink_count
        result.blink_just_counted = counted
        result.blinks_per_minute = self._bpm(timestamp_ms)

        # Eye outlines for UI drawing (normalized coordinates)
        result.left_eye_points = [(landmarks[i].x, landmarks[i].y)
                                  for i in LEFT_EYE_OUTLINE_IDX]
        result.right_eye_points = [(landmarks[i].x, landmarks[i].y)
                                   for i in RIGHT_EYE_OUTLINE_IDX]
        # Full landmark set (already computed by the model - free to expose)
        result.all_points = [(p.x, p.y) for p in landmarks]
        return result

    # ------------------------------------------------------------ internals

    def _bpm(self, now_ms: float) -> float:
        """Blinks per minute over the last 60 s (or elapsed time if less)."""
        if self._start_ms is None:
            return 0.0
        window_ms = min(60_000.0, max(1_000.0, now_ms - self._start_ms))
        recent = [t for t in self._blink_times_ms if now_ms - t <= window_ms]
        return len(recent) * 60_000.0 / window_ms
