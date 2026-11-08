"""Terminal reporter: status formatting and engine event lines."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.terminal import TerminalReporter, format_status


def _snapshot(**overrides) -> SimpleNamespace:
    values = {
        "camera_ok": True,
        "camera_message": "live",
        "continuous_bpm": 12.0,
        "average_bpm": 14.5,
        "ocular_rhythm_index": 72.4,
        "regularity": 65.0,
        "blinks_today": 40,
        "screen_time": "3m",
        "fps": 14.7,
        "face_found": True,
        "face_direction": "straight",
        "off_screen": False,
        "low_light": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FakeEngine:
    def __init__(self) -> None:
        self.blink_listeners = []
        self.alert_listeners = []

    def on_blink_pulse(self, callback) -> None:
        self.blink_listeners.append(callback)

    def on_alert_active_change(self, callback) -> None:
        self.alert_listeners.append(callback)

    def snapshot(self) -> SimpleNamespace:
        return _snapshot()


class FormatStatusTests(unittest.TestCase):
    def test_live_numbers(self) -> None:
        line = format_status(_snapshot())
        for part in (
            "rate 12.0/min",
            "avg 14.5/min",
            "ORI 72",
            "regularity 65",
            "today 40",
            "screen 3m",
            "fps 14.7",
            "face straight",
        ):
            self.assertIn(part, line)

    def test_scores_not_ready_yet(self) -> None:
        line = format_status(_snapshot(ocular_rhythm_index=None, regularity=None))
        self.assertIn("ORI --", line)
        self.assertIn("regularity --", line)

    def test_camera_problem_replaces_numbers(self) -> None:
        line = format_status(
            _snapshot(camera_ok=False, camera_message="reconnecting…")
        )
        self.assertEqual(line, "camera: reconnecting…")

    def test_no_face(self) -> None:
        line = format_status(_snapshot(face_found=False, face_direction=None))
        self.assertIn("face no face", line)

    def test_off_screen_and_low_light_are_flagged(self) -> None:
        line = format_status(
            _snapshot(face_direction="bottom", off_screen=True, low_light=True)
        )
        self.assertIn("face bottom (off-screen)", line)
        self.assertIn("low light", line)


class TerminalReporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _FakeEngine()
        self.lines: list[str] = []
        self.reporter = TerminalReporter(self.engine, write=self.lines.append)
        self.reporter.bind()

    def test_blinks_are_numbered(self) -> None:
        self.engine.blink_listeners[0]()
        self.engine.blink_listeners[0]()
        self.assertTrue(self.lines[0].endswith("blink 1"))
        self.assertTrue(self.lines[1].endswith("blink 2"))

    def test_alert_on_and_off(self) -> None:
        self.engine.alert_listeners[0](True)
        self.engine.alert_listeners[0](False)
        self.assertTrue(self.lines[0].endswith("ALERT: blink rhythm is low"))
        self.assertTrue(self.lines[1].endswith("alert cleared"))

    def test_status_line_reads_the_snapshot(self) -> None:
        self.reporter.report_status()
        self.assertIn("rate 12.0/min", self.lines[0])


if __name__ == "__main__":
    unittest.main()
