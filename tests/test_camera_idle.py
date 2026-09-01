"""Camera idle policy: 1 min absent → off, peek every 2 min, 30 s confirm."""

from __future__ import annotations

import unittest

from app.camera_idle import (
    ABSENT_BEFORE_SLEEP_S,
    CONFIRM_FACE_S,
    CONFIRM_GRACE_S,
    PEEK_NO_FACE_S,
    CameraIdlePolicy,
)


class CameraIdlePolicyTests(unittest.TestCase):
    def test_stays_live_until_one_minute_without_face(self) -> None:
        p = CameraIdlePolicy()
        t0 = 1_000.0
        self.assertEqual(p.note_face(False, t0), "live")
        self.assertEqual(p.note_face(False, t0 + ABSENT_BEFORE_SLEEP_S - 0.01), "live")
        self.assertEqual(p.note_face(False, t0 + ABSENT_BEFORE_SLEEP_S), "sleep")
        self.assertEqual(p.phase, "sleep")

    def test_any_face_resets_the_one_minute_timer(self) -> None:
        p = CameraIdlePolicy()
        t0 = 0.0
        p.note_face(False, t0)
        p.note_face(True, t0 + 40)
        self.assertEqual(p.note_face(False, t0 + 41), "live")
        self.assertEqual(p.note_face(False, t0 + 41 + 59), "live")
        self.assertEqual(p.note_face(False, t0 + 41 + 60), "sleep")

    def test_peek_without_face_gives_up(self) -> None:
        p = CameraIdlePolicy()
        p.begin_peek(0.0)
        self.assertEqual(p.note_face(False, 1.0), "peek")
        self.assertEqual(p.note_face(False, PEEK_NO_FACE_S), "sleep")

    def test_peek_needs_thirty_seconds_of_face(self) -> None:
        p = CameraIdlePolicy()
        p.begin_peek(0.0)
        self.assertEqual(p.note_face(True, 0.0), "peek")
        self.assertEqual(p.note_face(True, CONFIRM_FACE_S - 0.01), "peek")
        self.assertEqual(p.note_face(True, CONFIRM_FACE_S), "live")
        self.assertEqual(p.phase, "live")

    def test_lost_face_during_confirm_returns_to_sleep(self) -> None:
        p = CameraIdlePolicy()
        p.begin_peek(0.0)
        p.note_face(True, 0.0)
        p.note_face(True, 10.0)
        self.assertEqual(p.note_face(False, 10.5), "peek")
        self.assertEqual(
            p.note_face(False, 10.5 + CONFIRM_GRACE_S), "sleep"
        )

    def test_reset_to_live_clears_sleep(self) -> None:
        p = CameraIdlePolicy()
        p.begin_sleep()
        p.reset_to_live()
        self.assertEqual(p.note_face(False, 0.0), "live")


if __name__ == "__main__":
    unittest.main()
