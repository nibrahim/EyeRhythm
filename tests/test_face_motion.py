"""Poise: three face angles, a lasting grid, and a one-way direction histogram."""

from __future__ import annotations

import base64
import json
import math
import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np

from blink_core.face_motion import (
    BIN_COUNT,
    CENTER,
    CHIN,
    FOREHEAD,
    LEFT_CHEEK,
    LEFT_EYE,
    POINT_COUNT,
    RIGHT_CHEEK,
    RIGHT_EYE,
    FaceMotionTracker,
    direction_bin,
)


def _base_face() -> np.ndarray:
    """A frontal cloud. 33 is the subject's right eye (image-left)."""
    rng = np.random.default_rng(7)
    pts = np.zeros((POINT_COUNT, 3), dtype=np.float64)
    pts[:, 0] = rng.normal(0.5, 0.04, POINT_COUNT)
    pts[:, 1] = rng.normal(0.55, 0.06, POINT_COUNT)
    pts[:, 2] = rng.normal(0.0, 0.01, POINT_COUNT)
    pts[CENTER] = (0.50, 0.48, 0.00)
    pts[RIGHT_EYE] = (0.42, 0.46, -0.01)
    pts[LEFT_EYE] = (0.58, 0.46, -0.01)
    pts[FOREHEAD] = (0.50, 0.30, 0.02)
    pts[CHIN] = (0.50, 0.78, 0.03)
    pts[1] = (0.50, 0.56, -0.05)
    for i in LEFT_CHEEK:
        pts[i] = (0.66, 0.58, 0.01)
    for i in RIGHT_CHEEK:
        pts[i] = (0.34, 0.58, 0.01)
    return pts


def _yaw_image(pts: np.ndarray, deg: float) -> np.ndarray:
    """Rotate around image-down. Positive deg points the nose image-left."""
    ang = math.radians(deg)
    c, s = math.cos(ang), math.sin(ang)
    out = pts.copy()
    rel = out - out[CENTER]
    x = rel[:, 0].copy()
    z = rel[:, 2].copy()
    rel[:, 0] = c * x + s * z
    rel[:, 2] = -s * x + c * z
    return rel + out[CENTER]


def _pitch_z(pts: np.ndarray, lift: float) -> np.ndarray:
    """Bring the chin closer and the forehead farther. Positive lift looks up."""
    out = pts.copy()
    out[FOREHEAD, 2] += lift
    out[CHIN, 2] -= lift
    return out


def _tracker() -> FaceMotionTracker:
    return FaceMotionTracker(persist=False)


def _feed(tracker: FaceMotionTracker, face: np.ndarray, t: float, seconds: float) -> float:
    steps = max(1, int(round(seconds / 0.05)))
    for _ in range(steps):
        tracker.observe(face, t, frontal=True)
        t += 0.05
    return t


def _mesh(pub: dict) -> np.ndarray:
    raw = base64.b64decode(pub["mesh"])
    return np.frombuffer(raw, dtype="<f4").reshape(POINT_COUNT, 3).copy()


def _bins(pub: dict) -> np.ndarray:
    raw = base64.b64decode(pub["dots"])
    values = np.frombuffer(raw, dtype="<u2").astype(np.float64)
    if values.shape != (BIN_COUNT,):
        raise AssertionError(f"expected {BIN_COUNT} bins, got {values.shape}")
    return values


class FaceMotionTests(unittest.TestCase):
    def test_every_thirty_degrees_is_its_own_sector(self) -> None:
        self.assertEqual(BIN_COUNT, 12)
        seen = []
        for k in range(BIN_COUNT):
            ang = math.radians(k * 30.0)
            # Dial +y is up, so a positive sine is an upward look.
            lr = 40.0 * math.cos(ang)
            pitch = 32.0 * math.sin(ang)
            seen.append(direction_bin(lr, max(pitch, 0.0), max(-pitch, 0.0)))
        self.assertEqual(seen, list(range(BIN_COUNT)))

    def test_cardinal_directions_land_on_opposite_bars(self) -> None:
        right = direction_bin(30.0, 0.0, 0.0)
        left = direction_bin(-30.0, 0.0, 0.0)
        up = direction_bin(0.0, 30.0, 0.0)
        down = direction_bin(0.0, 0.0, 30.0)
        self.assertIsNotNone(right)
        self.assertEqual(left, (right + BIN_COUNT // 2) % BIN_COUNT)
        self.assertEqual(down, (up + BIN_COUNT // 2) % BIN_COUNT)
        self.assertNotEqual(right, up)
        # A small lean while looking right stays in the same sector.
        self.assertEqual(direction_bin(30.0, 0.0, 4.0), right)
        self.assertIsNone(direction_bin(0.0, 0.0, 0.0))
        self.assertIsNone(direction_bin(10.0, 0.0, 0.0))
        self.assertIsNone(direction_bin(0.0, 8.0, 0.0))

    def test_straight_face_is_centered_and_reports_three_small_degrees(self) -> None:
        tr = _tracker()
        _feed(tr, _base_face(), 0.0, 0.4)
        pub = tr.to_public()
        self.assertTrue(pub["ready"])
        mesh = _mesh(pub)
        self.assertTrue(np.allclose(mesh[CENTER], 0.0, atol=1e-5))
        self.assertGreater(float(mesh[1, 2]), 0.05)
        self.assertLess(float(mesh[LEFT_CHEEK[0], 0]), -0.2)
        self.assertGreater(float(mesh[RIGHT_CHEEK[0], 0]), 0.2)
        self.assertLess(abs(pub["lr"]), 8.0)
        self.assertLess(pub["up"], 8.0)
        self.assertLess(pub["down"], 8.0)
        self.assertEqual(min(pub["up"], pub["down"]), 0.0)

    def test_right_up_and_down_are_separate_degrees(self) -> None:
        right = _tracker()
        _feed(right, _yaw_image(_base_face(), 28.0), 0.0, 0.6)
        pub = right.to_public()
        self.assertGreater(pub["lr"], 18.0)
        self.assertLess(pub["up"], 8.0)
        self.assertLess(pub["down"], 8.0)
        turned = _mesh(pub)
        self.assertGreater(float(turned[1, 0]), 0.1)
        self.assertTrue(np.allclose(turned[CENTER], 0.0, atol=1e-5))

        up = _tracker()
        _feed(up, _pitch_z(_base_face(), 0.12), 0.0, 2.0)
        risen = up.to_public()
        self.assertGreater(risen["up"], 8.0)
        self.assertEqual(risen["down"], 0.0)

        down = _tracker()
        _feed(down, _pitch_z(_base_face(), -0.12), 0.0, 2.0)
        dropped = down.to_public()
        self.assertGreater(dropped["down"], 8.0)
        self.assertEqual(dropped["up"], 0.0)
        self.assertLess(abs(dropped["lr"]), 8.0)

        # Looking up and looking down grow opposite sectors.
        up_bin = direction_bin(risen["lr"], risen["up"], risen["down"])
        down_bin = direction_bin(dropped["lr"], dropped["up"], dropped["down"])
        self.assertEqual(down_bin, (up_bin + BIN_COUNT // 2) % BIN_COUNT)
        up_vals = _bins(risen)
        down_vals = _bins(dropped)
        self.assertGreater(float(up_vals[up_bin]), 0.0)
        self.assertEqual(int(up_vals.sum()), int(up_vals[up_bin]))
        self.assertGreater(float(down_vals[down_bin]), 0.0)
        self.assertEqual(int(down_vals.sum()), int(down_vals[down_bin]))

    def test_shift_and_scale_do_not_move_the_centered_grid(self) -> None:
        tr = _tracker()
        face = _base_face()
        t = _feed(tr, face, 0.0, 0.5)
        before = _mesh(tr.to_public())
        shifted = face + np.array([0.3, -0.2, 0.05])
        shifted = (shifted - shifted[CENTER]) * 1.8 + shifted[CENTER]
        _feed(tr, shifted, t, 0.6)
        after = _mesh(tr.to_public())
        self.assertTrue(np.allclose(after, before, atol=0.03))
        self.assertTrue(np.allclose(after[CENTER], 0.0, atol=1e-5))

    def test_straight_ahead_grows_nothing_and_a_turn_never_shrinks(self) -> None:
        tr = _tracker()
        tr._paint(0.0, 0.0, 0.0, 6.0 * 3600.0)
        tr._paint(10.0, 8.0, 0.0, 6.0 * 3600.0)
        tr._publish_unlocked()
        self.assertTrue(np.all(_bins(tr.to_public()) == 0))

        right = direction_bin(30.0, 0.0, 0.0)
        left = direction_bin(-30.0, 0.0, 0.0)
        tr._paint(30.0, 0.0, 0.0, 2.0)
        tr._publish_unlocked()
        values = _bins(tr.to_public())
        # Two seconds is a short stub. The outer ring is five hours.
        peak = float(values.max()) / 65535.0
        self.assertGreater(peak, 0.0)
        self.assertLess(peak, 0.01)
        self.assertEqual(int(values.sum()), int(values[right]))
        held = values.copy()
        tr._paint(-30.0, 0.0, 0.0, 30.0)
        tr._publish_unlocked()
        later = _bins(tr.to_public())
        self.assertTrue(np.all(later + 1e-6 >= held))
        self.assertGreater(float(later[left]), float(held[left]))

    def test_one_minute_is_one_three_hundredth_and_five_hours_fills(self) -> None:
        tr = _tracker()
        sector = direction_bin(30.0, 0.0, 0.0)
        # A lean that stays in this sector adds to the same wedge.
        self.assertEqual(direction_bin(28.0, 0.0, 4.0), sector)
        tr._paint(30.0, 0.0, 0.0, 60.0)
        tr._publish_unlocked()
        minute = float(_bins(tr.to_public())[sector]) / 65535.0
        self.assertAlmostEqual(minute, 1.0 / 300.0, delta=0.001)
        tr._paint(28.0, 0.0, 4.0, 2.5 * 3600.0)
        tr._publish_unlocked()
        half = float(_bins(tr.to_public())[sector]) / 65535.0
        self.assertGreater(half, 0.45)
        self.assertLess(half, 0.55)
        tr._paint(30.0, 0.0, 0.0, 2.5 * 3600.0)
        tr._publish_unlocked()
        full = _bins(tr.to_public()) / 65535.0
        self.assertGreater(float(full[sector]), 0.99)
        self.assertEqual(int(np.count_nonzero(full)), 1)

    def test_a_missing_face_keeps_the_grid_and_the_bars(self) -> None:
        tr = _tracker()
        t = _feed(tr, _yaw_image(_base_face(), 32.0), 0.0, 1.0)
        hot = tr.to_public()
        for _ in range(5):
            tr.observe(None, t, frontal=False)
            t += 4.0
        frozen = tr.to_public()
        self.assertEqual(frozen["mesh"], hot["mesh"])
        self.assertEqual(frozen["dots"], hot["dots"])
        self.assertGreater(float(_bins(frozen).max()), 0.0)
        self.assertTrue(frozen["ready"])

    def test_reset_clears_grid_and_dots_including_the_store(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "poise_field.json"
            tr = FaceMotionTracker(persist=True, store=path)
            _feed(tr, _base_face(), 0.0, 0.4)
            tr._write_store()
            self.assertTrue(path.is_file())
            first = tr.to_public()

            again = FaceMotionTracker(persist=True, store=path)
            loaded = again.to_public()
            self.assertEqual(loaded["mesh"], first["mesh"])
            self.assertEqual(loaded["dots"], first["dots"])
            self.assertTrue(loaded["ready"])

            again.reset()
            cleared = again.to_public()
            self.assertFalse(path.exists())
            self.assertFalse(cleared["ready"])
            self.assertEqual(cleared["mesh"], "")
            self.assertEqual(cleared["samples"], 0)
            self.assertTrue(np.all(_bins(cleared) == 0))

    def test_a_new_day_starts_with_empty_sectors_and_keeps_the_grid(self) -> None:
        day = [date(2026, 11, 2)]
        tr = FaceMotionTracker(persist=False, today=lambda: day[0])
        t = _feed(tr, _yaw_image(_base_face(), 32.0), 0.0, 1.0)
        before = tr.to_public()
        self.assertGreater(float(_bins(before).max()), 0.0)

        day[0] = date(2026, 11, 3)
        morning = tr.to_public()
        self.assertTrue(np.all(_bins(morning) == 0))
        self.assertEqual(morning["mesh"], before["mesh"])

        _feed(tr, _yaw_image(_base_face(), 32.0), t, 1.0)
        self.assertGreater(float(_bins(tr.to_public()).max()), 0.0)

    def test_saved_sectors_load_only_on_the_same_day(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "poise_field.json"
            tr = FaceMotionTracker(persist=True, store=path, today=lambda: date(2026, 11, 2))
            _feed(tr, _yaw_image(_base_face(), 32.0), 0.0, 1.0)
            tr._write_store()
            saved = tr.to_public()

            same = FaceMotionTracker(persist=True, store=path, today=lambda: date(2026, 11, 2))
            self.assertEqual(same.to_public()["dots"], saved["dots"])

            later = FaceMotionTracker(persist=True, store=path, today=lambda: date(2026, 11, 3))
            fresh = later.to_public()
            self.assertTrue(np.all(_bins(fresh) == 0))
            self.assertEqual(fresh["mesh"], saved["mesh"])
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual((stored["v"], stored["day"]), (10, "2026-11-03"))

    def test_version_nine_from_today_swaps_up_and_down(self) -> None:
        up = direction_bin(0.0, 30.0, 0.0)
        down = direction_bin(0.0, 0.0, 30.0)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "poise_field.json"
            old = np.zeros(BIN_COUNT, dtype="<f4")
            old[up] = np.float32(600.0)
            payload = {
                "v": 9,
                "exposure": base64.b64encode(np.ascontiguousarray(old).tobytes()).decode("ascii"),
                "mesh": "",
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            tr = FaceMotionTracker(persist=True, store=path)
            values = _bins(tr.to_public())
            self.assertGreater(float(values[down]), 0.0)
            self.assertEqual(float(values[up]), 0.0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["v"], 10)


if __name__ == "__main__":
    unittest.main()
