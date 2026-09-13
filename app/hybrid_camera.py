"""
Hybrid multi-camera capture
===========================

Desk webcams (built-in + USB, never a phone) can run together. OpenCV cannot
genlock USB cameras, but grabbing every device *first* and only then
retrieving the pixels samples them at the same loop tick so one physical
blink is not counted twice.

Each tick every desk camera is grabbed at the same instant. MediaPipe
runs on the sticky front-facing camera so FPS stays near a single-camera
loop; extras are decoded only while hunting a better view.
"""

from __future__ import annotations

from collections import deque
from typing import Any

CAMERA_MODE_SINGLE = "single"
CAMERA_MODE_HYBRID = "hybrid"

# After one camera counts a blink, ignore the same event from the other
# streams. Wider than the per-camera 80 ms refractory so a delayed OPEN
# on a second angle cannot double-count after post-blink sleep.
HYBRID_FUSE_REFRACTORY_S = 0.25

# A live extra camera that produces no frames this long is treated as dead
# (~1 s at face fps) so hybrid can reopen the full set. Do not drop when
# every camera is silent — that path already reopens everything.
HYBRID_SILENT_DROP_FRAMES = 24
# First retry for a camera that failed to join the hybrid set.
HYBRID_FILL_MIN_S = 5.0
HYBRID_FILL_MAX_S = 30.0


def missing_camera_indices(
    wanted: list[int],
    open_idxs: list[int],
) -> list[int]:
    """Wanted desk-camera indices that are not in the open set."""
    have = {int(i) for i in open_idxs}
    return [int(i) for i in wanted if int(i) not in have]


def should_drop_silent_hybrid_camera(
    miss_frames: int,
    *,
    others_live: bool,
    threshold: int = HYBRID_SILENT_DROP_FRAMES,
) -> bool:
    """
    True when one hybrid camera is mute while another is still delivering
    frames. Hot-opening the mute device while the live one holds AVFoundation
    usually fails on macOS — drop it so a full-set reopen can recover it.
    """
    return bool(others_live) and int(miss_frames) >= int(threshold)


def next_hybrid_fill_wait(attempt: int) -> float:
    """Backoff between hybrid full-set recovery tries (5s, 10s, 20s, 30s…)."""
    n = max(0, int(attempt))
    return float(min(HYBRID_FILL_MAX_S, HYBRID_FILL_MIN_S * (2 ** n)))


def grab_all(
    caps: dict[int, Any],
    *,
    drain: int = 0,
) -> dict[int, Any]:
    """
    Hardware-sample every camera at one instant (no decode yet).

    Returns ``index → capture`` for cameras whose ``grab()`` succeeded.
    Call ``retrieve_frame`` only for cameras you will actually process so
    unused streams do not pay JPEG decode every tick.
    """
    items = [(int(idx), cap) for idx, cap in caps.items() if cap is not None]
    if not items:
        return {}
    try:
        for _ in range(max(0, int(drain))):
            for _idx, cap in items:
                cap.grab()
        ready: dict[int, Any] = {}
        for idx, cap in items:
            if cap.grab():
                ready[idx] = cap
        return ready
    except Exception:
        return {}


def retrieve_frame(cap: Any) -> Any | None:
    """Decode the frame that ``grab_all`` already sampled. None on failure."""
    try:
        ok, frame = cap.retrieve()
    except Exception:
        return None
    if not ok or frame is None:
        return None
    return frame


def read_frames_synced(
    caps: dict[int, Any],
    *,
    drain: int = 0,
) -> dict[int, Any]:
    """
    Sample every open camera at one instant, then decode all of them.

    The live loop uses ``grab_all`` + ``retrieve_frame`` so hybrid can skip
    decoding cameras that will not run MediaPipe this tick.
    """
    ready = grab_all(caps, drain=drain)
    out: dict[int, Any] = {}
    for idx, cap in ready.items():
        frame = retrieve_frame(cap)
        if frame is not None:
            out[idx] = frame
    return out


def camera_try_order(sticky: int | None, available: list[int]) -> list[int]:
    """Sticky camera first, then the rest (stable order)."""
    avail = [int(i) for i in available]
    if sticky is None or int(sticky) not in avail:
        return avail
    s = int(sticky)
    return [s] + [i for i in avail if i != s]


def hybrid_decode_indices(
    ready: list[int],
    sticky: int | None,
    *,
    hunt: bool,
) -> list[int]:
    """
    Which grabbed cameras to decode and run MediaPipe on this tick.

    Hybrid keeps FPS near a single camera by detecting only the sticky
    front-facing view. Decode every camera only while hunting (no sticky
    face yet, or the sticky view is no longer front-facing).
    """
    avail = [int(i) for i in ready]
    if not avail:
        return []
    if hunt:
        return camera_try_order(sticky, avail)
    if sticky is not None and int(sticky) in avail:
        return [int(sticky)]
    return [avail[0]]


def view_quality(
    *,
    face_found: bool,
    off_screen: bool,
    is_frontal: bool,
    face_angle_deg: float | None,
) -> float:
    """Higher is a better camera to show and to treat as the face pose."""
    if not face_found:
        return -1e9
    score = 1000.0
    if not off_screen:
        score += 200.0
    if is_frontal:
        score += 100.0
    angle = 90.0 if face_angle_deg is None else float(face_angle_deg)
    return score - angle


def is_front_facing(
    *,
    face_found: bool,
    off_screen: bool,
    is_frontal: bool,
) -> bool:
    """True when this view is a face looking toward that camera."""
    return bool(face_found) and bool(is_frontal) and not bool(off_screen)


def pick_front_facing_index(
    views: list[tuple[int, bool, bool, bool, float | None]],
    sticky: int | None = None,
) -> int | None:
    """
    Choose the camera to run blink detection on for this tick.

    Prefers a front-facing, on-screen face. If the sticky camera is still
    in that set, keep it so pose noise does not hop views mid-blink. If
    none are front-facing, falls back to the most frontal-ish face that
    was processed. ``views`` entries are
    ``(index, face_found, off_screen, is_frontal, face_angle_deg)``.
    """
    frontal = [
        v
        for v in views
        if is_front_facing(face_found=v[1], off_screen=v[2], is_frontal=v[3])
    ]
    if sticky is not None and frontal:
        sticky_i = int(sticky)
        if any(v[0] == sticky_i for v in frontal):
            return sticky_i
    return pick_best_index(frontal if frontal else views)


def any_on_screen_face(views: list[tuple[bool, bool]]) -> bool:
    """True when any view has a face that is not looking off-screen."""
    return any(bool(face) and not bool(off) for face, off in views)


def hybrid_should_count_blink(
    *,
    counting: bool,
    chosen_counted: bool,
    chosen_off_screen: bool,
    extra_counts: list[tuple[bool, bool]],
) -> bool:
    """
    One physical blink may finish on a non-chosen camera this tick.

    Count it if the chosen view completed an on-screen blink, or any extra
    view did. ``extra_counts`` entries are ``(blink_just_counted, off_screen)``.
    """
    if not counting:
        return False
    if chosen_counted and not chosen_off_screen:
        return True
    return any(counted and not off for counted, off in extra_counts)


def pick_best_index(
    views: list[tuple[int, bool, bool, bool, float | None]],
) -> int | None:
    """
    Pick the best camera among ``(index, face_found, off_screen, is_frontal,
    face_angle_deg)``. Prefer a face, then on-screen, then frontal, then
    the smallest look angle. Returns ``None`` if ``views`` is empty.
    """
    if not views:
        return None
    best_i, best_q = views[0][0], -1e12
    for index, face_found, off_screen, is_frontal, angle in views:
        q = view_quality(
            face_found=face_found,
            off_screen=off_screen,
            is_frontal=is_frontal,
            face_angle_deg=angle,
        )
        if q > best_q:
            best_q = q
            best_i = index
    return best_i


class FusedBlinkRate:
    """60-second blink rate shared across hybrid cameras (one count per blink)."""

    def __init__(self) -> None:
        self._times_ms: deque[float] = deque(maxlen=300)
        self.count = 0
        self._last_count_mono = -1e12

    def reset(self) -> None:
        self._times_ms.clear()
        self.count = 0
        self._last_count_mono = -1e12

    def allow(self, now_mono: float, refractory_s: float = HYBRID_FUSE_REFRACTORY_S) -> bool:
        """True if a new fused blink may be accepted at this wall-clock time."""
        return (float(now_mono) - self._last_count_mono) >= float(refractory_s)

    def on_blink(self, timestamp_ms: float, now_mono: float) -> None:
        self._times_ms.append(float(timestamp_ms))
        self.count += 1
        self._last_count_mono = float(now_mono)

    def bpm(self, timestamp_ms: float) -> float:
        now = float(timestamp_ms)
        cutoff = now - 60_000.0
        n = sum(1 for t in self._times_ms if t >= cutoff)
        return float(n)

    def hold_rate_across_gap(self, gap_ms: float) -> None:
        try:
            shift = float(gap_ms)
        except (TypeError, ValueError):
            return
        if shift != shift or shift <= 0.0:  # NaN or non-positive
            return
        shifted: deque[float] = deque(maxlen=self._times_ms.maxlen)
        for t in self._times_ms:
            shifted.append(float(t) + shift)
        self._times_ms = shifted
