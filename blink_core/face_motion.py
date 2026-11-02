"""
Poise angles and the pairing field
===================================

Each frame with a face yields three degrees, measured from the nose
bridge:

* left / right — yaw, positive when the face points to the person's right
* up — pitch above the camera, otherwise 0
* down — pitch below the camera, otherwise 0

The live wireframe is that same centered mesh, so the grid on the left
is the face plotted around its own center. It stays on screen after the
face leaves. Reset is the only clear.

The right-hand field is a top-down dial of eight sectors, 45° each.
Up is the top of the dial and down is the bottom. A sector fills from
the center toward the rim. That span is five hours, so one minute adds
one three-hundredth of it. Looking straight ahead adds nothing. Looking
somewhere else never shortens a sector.
"""

from __future__ import annotations

import base64
import json
import math
import threading
from pathlib import Path
from typing import Any

import numpy as np

# Full face mesh. Iris landmarks 468–477 are not part of the tessellation.
POINT_COUNT = 468

# Nose bridge. This vertex is the origin of the wireframe.
CENTER = 168
RIGHT_EYE = 33
LEFT_EYE = 263
FOREHEAD = 10
CHIN = 152

LEFT_CHEEK = (345, 352, 376, 411, 425, 280, 330, 266, 423, 426, 427, 436, 432, 422, 424)
RIGHT_CHEEK = (116, 123, 147, 187, 205, 50, 101, 36, 203, 206, 207, 216, 212, 202, 204)

# Dial layout. The same numbers are repeated in poiseField.ts.
# Eight sectors of 45°. Sector 0 is centered on the person's right.
# Looking up is the top of the dial. Looking down is the bottom.
BIN_COUNT = 8
# Inside this fraction of the circle the face is still "straight ahead"
# and no sector grows. 0.30 is about 15° of yaw or 12° of pitch.
DEAD_REACH = 0.30
# How many old 15° bins version 5 and 6 stored.
_LEGACY_BINS = 24

# Edge of a full turn, in degrees. Past this, the direction stays on the rim.
_YAW_EDGE = 50.0
_PITCH_EDGE = 40.0
# The span from the inner ring to the outer ring. One minute is 1/300 of it.
_FULL_S = 5.0 * 60.0 * 60.0
_SMOOTH_TAU = 0.07
# 8 is eight sectors with up at the top. 7 was six sectors with up at the bottom.
_STORE_VERSION = 8

_DEFAULT_STORE = Path.home() / ".eyerhythm_blinkcounter" / "poise_field.json"


def aim_vector(lr: float, up: float, down: float) -> tuple[float, float, float]:
    """
    Where the face is pointing inside the unit circle.

    +x is the person's right. +y is the top of the circle. Pitch is
    mirrored, so looking up aims at the bottom and looking down aims at
    the top. The third value is the reach, already clamped to 1.
    """
    nx = max(-1.0, min(1.0, lr / _YAW_EDGE))
    ny = max(-1.0, min(1.0, (down - up) / _PITCH_EDGE))
    reach = math.hypot(nx, ny)
    if reach > 1.0:
        nx /= reach
        ny /= reach
        reach = 1.0
    return nx, ny, reach


def _sector_index(angle: float) -> int:
    """Sector containing this dial angle. Matches the drawer in poiseField.ts.

    ``angle`` uses the picture's frame: 0 is the person's right, positive
    is up (the top of the dial). Each sector is 45° and is centered on a
    spoke, so looking straight up or right sits in the middle of a sector.
    """
    width = 2.0 * math.pi / BIN_COUNT
    return int(math.floor((angle + width * 0.5) / width)) % BIN_COUNT


def direction_bin(lr: float, up: float, down: float) -> int | None:
    """
    Sector for this aim, or None while the face stays inside the dead zone.

    Eight sectors of 45°. Looking up fills the top sector and looking down
    fills the bottom one. The person's right and left land in opposite
    sectors.
    """
    nx, ny, reach = aim_vector(lr, up, down)
    if reach < DEAD_REACH:
        return None
    # aim_vector's +y is looking down. The dial draws up at the top.
    return _sector_index(math.atan2(-ny, nx))


def _mirror_pitch(exposure: np.ndarray) -> np.ndarray:
    """Swap the up and down sides of a 24-bin field. Left and right stay put."""
    out = np.empty_like(exposure)
    count = int(exposure.shape[0])
    for i in range(count):
        out[(-i) % count] = exposure[i]
    return out


def _fold_legacy(exposure: np.ndarray) -> np.ndarray:
    """Add the old 15° bins into the eight sectors.

    Version 6 angles put looking-up at -90° (the bottom of that circle).
    The dial now puts up at the top, so the angle is negated.
    """
    out = np.zeros(BIN_COUNT, dtype=np.float64)
    step = 2.0 * math.pi / _LEGACY_BINS
    for i in range(_LEGACY_BINS):
        angle = i * step
        if angle > math.pi:
            angle -= 2.0 * math.pi
        out[_sector_index(-angle)] += float(exposure[i])
    np.minimum(out, _FULL_S, out=out)
    return out


def _fold_six(exposure: np.ndarray) -> np.ndarray:
    """Spread each old 60° sector across the 45° sectors it overlaps.

    Version 7 angles use the same bottom-is-up frame as version 6.
    """
    out = np.zeros(BIN_COUNT, dtype=np.float64)
    old_width = math.pi / 3.0
    samples = 12
    for i in range(6):
        start = -2.0 * math.pi / 3.0 + i * old_width
        share = float(exposure[i]) / samples
        if share <= 0.0:
            continue
        for step in range(samples):
            old = start + (step + 0.5) * old_width / samples
            out[_sector_index(-old)] += share
    np.minimum(out, _FULL_S, out=out)
    return out


def empty_face_map() -> dict[str, Any]:
    """JSON shape the dashboard reads before any face has been seen."""
    return {
        "ready": False,
        "samples": 0,
        "lr": 0.0,
        "up": 0.0,
        "down": 0.0,
        "mesh": "",
        "dots": _pack_exposure(np.zeros(BIN_COUNT, dtype=np.float64)),
    }


def _b64_f32(arr: np.ndarray) -> str:
    raw = np.ascontiguousarray(arr, dtype="<f4").tobytes()
    return base64.b64encode(raw).decode("ascii")


def _pack_exposure(seconds: np.ndarray) -> str:
    """Seconds in each direction → uint16. 0 is an empty bar, 65535 meets the ring."""
    scaled = np.clip(np.asarray(seconds, dtype=np.float64) / _FULL_S, 0.0, 1.0)
    raw = np.rint(scaled * 65535.0).astype("<u2").tobytes()
    return base64.b64encode(raw).decode("ascii")


def _display(norm: np.ndarray) -> np.ndarray:
    """Mirror into the view the UI draws. Nose bridge stays at the origin."""
    out = np.empty_like(norm)
    out[:, 0] = -norm[:, 0]
    out[:, 1] = -norm[:, 1]
    out[:, 2] = -norm[:, 2]
    out[CENTER] = 0.0
    return out


def _yaw_pitch_deg(norm: np.ndarray) -> tuple[float, float]:
    """
    Yaw and pitch of the centered face, in the mirrored view.

    Positive yaw is the person's right. Positive pitch is looking up.
    """
    shown = _display(norm)
    right = shown[RIGHT_EYE] - shown[LEFT_EYE]
    down = shown[CHIN] - shown[FOREHEAD]
    fx = down[1] * right[2] - down[2] * right[1]
    fy = down[2] * right[0] - down[0] * right[2]
    fz = down[0] * right[1] - down[1] * right[0]
    span = math.sqrt(fx * fx + fy * fy + fz * fz)
    if span < 1e-8:
        return 0.0, 0.0
    if fz < 0.0:
        fx, fy, fz = -fx, -fy, -fz
    yaw = math.degrees(math.atan2(fx, fz))
    # Forehead closer to the camera than the chin is a look upward.
    pitch = -math.degrees(math.atan2(fy, fz))
    return yaw, pitch


def _split_degrees(yaw: float, pitch: float) -> tuple[float, float, float]:
    """Left/right, up, and down. Up and down are never both positive."""
    return yaw, max(pitch, 0.0), max(-pitch, 0.0)


class FaceMotionTracker:
    """
    Three face angles, one lasting wireframe, and a one-way direction histogram.

    Call ``observe`` on the camera thread. ``to_public`` is safe from the
    WebSocket thread. ``persist=False`` is for tests, so they do not read
    or write the real field file.
    """

    def __init__(self, *, persist: bool = True, store: Path | None = None) -> None:
        self._persist = bool(persist)
        self._store = store or _DEFAULT_STORE
        self._lock = threading.Lock()
        self._reset_unlocked()
        if self._persist:
            self._load()

    def reset(self) -> None:
        """Drop the wireframe and clear every direction bar."""
        with self._lock:
            self._reset_unlocked()
            self._delete_store()

    def observe(
        self,
        xyz: np.ndarray | None,
        now: float,
        *,
        frontal: bool = True,
    ) -> None:
        """
        Ingest one frame.

        ``xyz`` is (468, 3) in MediaPipe image space, or None when the face
        is missing. None keeps the wireframe and the bars. ``frontal``
        is accepted so the engine can keep its keyword; a turned face still
        counts.
        """
        del frontal
        with self._lock:
            if xyz is None:
                self._last_t = None
                return
            pts = np.asarray(xyz, dtype=np.float64)
            if pts.shape != (POINT_COUNT, 3) or not np.isfinite(pts).all():
                return
            norm = self._normalize(pts)
            if norm is None:
                return
            now_f = float(now)
            if self._smooth is None or self._last_t is None:
                self._smooth = norm.copy()
                dt = 0.0
            else:
                dt = min(0.25, max(0.0, now_f - self._last_t))
                alpha = 1.0 - math.exp(-dt / _SMOOTH_TAU) if dt > 0.0 else 1.0
                self._smooth = self._smooth + alpha * (norm - self._smooth)
            self._smooth = self._smooth - self._smooth[CENTER]
            self._last_t = now_f
            yaw, pitch = _yaw_pitch_deg(self._smooth)
            lr, up, down = _split_degrees(yaw, pitch)
            if dt > 0.0:
                self._paint(lr, up, down, dt)
            self._lr = lr
            self._up = up
            self._down = down
            self._mesh_b64 = _b64_f32(_display(self._smooth))
            self._samples += 1
            self._publish_unlocked()
            self._maybe_save(now_f)

    def to_public(self) -> dict[str, Any]:
        """Shallow copy of the latest JSON-ready map."""
        with self._lock:
            return dict(self._public)

    # ---------------------------------------------------------------- internals

    def _reset_unlocked(self) -> None:
        self._smooth: np.ndarray | None = None
        self._last_t: float | None = None
        self._lr = 0.0
        self._up = 0.0
        self._down = 0.0
        self._samples = 0
        self._mesh_b64 = ""
        self._exposure = np.zeros(BIN_COUNT, dtype=np.float64)
        self._last_save = 0.0
        self._public = empty_face_map()

    def _normalize(self, pts: np.ndarray) -> np.ndarray | None:
        """Center on the nose bridge and scale so the eyes are one unit apart."""
        iod = float(np.linalg.norm(pts[LEFT_EYE] - pts[RIGHT_EYE]))
        if iod < 1e-4:
            return None
        return (pts - pts[CENTER]) / iod

    def _paint(self, lr: float, up: float, down: float, dt: float) -> None:
        idx = direction_bin(lr, up, down)
        if idx is None or dt <= 0.0:
            return
        self._exposure[idx] = min(_FULL_S, float(self._exposure[idx]) + dt)

    def _publish_unlocked(self) -> None:
        self._public = {
            "ready": bool(self._mesh_b64),
            "samples": int(self._samples),
            "lr": round(self._lr, 2),
            "up": round(self._up, 2),
            "down": round(self._down, 2),
            "mesh": self._mesh_b64,
            "dots": _pack_exposure(self._exposure),
        }

    def _maybe_save(self, now: float) -> None:
        if not self._persist:
            return
        if now - self._last_save < 15.0:
            return
        self._last_save = now
        self._write_store()

    def _write_store(self) -> None:
        """Caller holds ``_lock`` or is the only user of this tracker."""
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "v": _STORE_VERSION,
                "exposure": base64.b64encode(
                    np.ascontiguousarray(self._exposure, dtype="<f4").tobytes()
                ).decode("ascii"),
                "mesh": self._mesh_b64,
            }
            tmp = self._store.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._store)
        except OSError:
            return

    def _load(self) -> None:
        try:
            raw = json.loads(self._store.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            return
        version = raw.get("v") if isinstance(raw, dict) else None
        if version not in (_STORE_VERSION, 7, 6, 5):
            return
        try:
            exposure = np.frombuffer(base64.b64decode(raw.get("exposure", "")), dtype="<f4")
        except (ValueError, TypeError):
            return
        if version in (5, 6):
            if exposure.shape != (_LEGACY_BINS,):
                return
            values = np.maximum(exposure.astype(np.float64), 0.0)
            # Version 5 stored looking-up on the top. Version 6 already swapped it.
            if version == 5:
                values = _mirror_pitch(values)
            values = _fold_legacy(values)
        elif version == 7:
            if exposure.shape != (6,):
                return
            values = _fold_six(np.maximum(exposure.astype(np.float64), 0.0))
        elif exposure.shape != (BIN_COUNT,):
            return
        else:
            values = np.clip(exposure.astype(np.float64), 0.0, _FULL_S)
        self._exposure = values
        mesh = raw.get("mesh", "")
        if isinstance(mesh, str) and mesh:
            self._mesh_b64 = mesh
            self._samples = 1
        self._publish_unlocked()
        if version != _STORE_VERSION:
            self._write_store()

    def _delete_store(self) -> None:
        if not self._persist:
            return
        try:
            self._store.unlink(missing_ok=True)
        except OSError:
            return
