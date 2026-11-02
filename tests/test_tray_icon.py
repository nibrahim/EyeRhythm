"""Dock / taskbar icon frames: orange Alert flash and blink lid."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from app.tray_icon import (
    VARIANTS,
    TrayIconAnimator,
    alert_flash_on,
    icon_variant,
    render_frames,
)


class TrayIconLogicTests(unittest.TestCase):
    def test_variant_names(self) -> None:
        self.assertEqual(
            icon_variant(alert_flash=False, eyes_closed=False), "blue_open"
        )
        self.assertEqual(
            icon_variant(alert_flash=False, eyes_closed=True), "blue_closed"
        )
        self.assertEqual(
            icon_variant(alert_flash=True, eyes_closed=False), "orange_open"
        )
        self.assertEqual(
            icon_variant(alert_flash=True, eyes_closed=True), "orange_closed"
        )

    def test_alert_flash_alternates(self) -> None:
        self.assertFalse(alert_flash_on(0.0, period_s=0.5))
        self.assertTrue(alert_flash_on(0.5, period_s=0.5))
        self.assertFalse(alert_flash_on(1.0, period_s=0.5))
        self.assertTrue(alert_flash_on(1.5, period_s=0.5))


class TrayIconAnimatorTests(unittest.TestCase):
    def _animator(self) -> tuple[TrayIconAnimator, list[str]]:
        anim = TrayIconAnimator(window=None)
        anim._ready = True
        applied: list[str] = []
        anim._apply = applied.append  # type: ignore[method-assign]
        return anim, applied

    def test_blink_closes_the_eye(self) -> None:
        anim, applied = self._animator()
        anim.pulse_blink()
        anim._tick()
        self.assertEqual(applied[-1], "blue_closed")

    def test_alert_uses_orange_on_flash_phase(self) -> None:
        anim, applied = self._animator()
        anim.set_alert(True)
        with patch("app.tray_icon.alert_flash_on", return_value=True):
            anim._tick()
        self.assertEqual(applied[-1], "orange_open")

    def test_alert_and_blink_can_combine(self) -> None:
        anim, applied = self._animator()
        anim.set_alert(True)
        anim.pulse_blink()
        with patch("app.tray_icon.alert_flash_on", return_value=True):
            anim._tick()
        self.assertEqual(applied[-1], "orange_closed")


class TrayIconRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frames = render_frames(256)

    def test_four_frames(self) -> None:
        self.assertEqual(set(self.frames), set(VARIANTS))
        for name, img in self.frames.items():
            self.assertEqual(img.shape, (256, 256, 4), name)
            self.assertEqual(img.dtype, np.uint8)

    def test_open_eye_has_dark_pupil(self) -> None:
        pupil = self.frames["blue_open"][128, 128, :3].astype(np.int16)
        self.assertLess(int(pupil.mean()), 90)

    def test_closed_eye_is_bright_slit(self) -> None:
        lid = self.frames["blue_closed"][128, 128, :3].astype(np.int16)
        self.assertGreater(int(lid.mean()), 180)

    def test_orange_mark_is_warmer_than_blue(self) -> None:
        # Sample the square, not the eye (a bit above the lid).
        blue = self.frames["blue_open"][48, 128, :3].astype(np.int16)
        orange = self.frames["orange_open"][48, 128, :3].astype(np.int16)
        # OpenCV BGR: orange has more red (index 2), blue has more blue (index 0).
        self.assertGreater(int(orange[2]), int(blue[2]))
        self.assertGreater(int(blue[0]), int(orange[0]))

    def test_closed_and_open_differ(self) -> None:
        delta = np.abs(
            self.frames["blue_open"].astype(np.int16)
            - self.frames["blue_closed"].astype(np.int16)
        )
        self.assertGreater(int(delta.mean()), 2)


if __name__ == "__main__":
    unittest.main()
