"""Frame pacer: single-camera adaptive rate vs uncapped hybrid."""

from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from app.frame_pacer import FACE_INTERVAL_S, FramePacer, NO_FACE_INTERVAL_S


class FramePacerTests(unittest.TestCase):
    def test_single_camera_drops_to_no_face_after_grace(self) -> None:
        pacer = FramePacer()
        for _ in range(5):
            pacer.observe(face_found=False, blink_just_counted=False)
        self.assertEqual(pacer.interval_s, NO_FACE_INTERVAL_S)

    def test_hybrid_uncapped_never_sleeps_or_slows(self) -> None:
        pacer = FramePacer(post_blink_sleep=True, uncapped=True)
        pacer.observe(face_found=True, blink_just_counted=True)
        pacer.note_no_signal()
        for _ in range(10):
            pacer.observe(face_found=False, blink_just_counted=False)
        self.assertEqual(pacer.interval_s, 0.0)
        with patch("app.frame_pacer.time.sleep") as slept:
            pacer.sleep_for_frame(time.monotonic())
        slept.assert_not_called()

    def test_single_camera_face_rate(self) -> None:
        pacer = FramePacer()
        pacer.observe(face_found=True, blink_just_counted=False)
        self.assertEqual(pacer.interval_s, FACE_INTERVAL_S)


if __name__ == "__main__":
    unittest.main()
