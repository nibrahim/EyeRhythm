"""Beeper: Linux player selection, generated tone, and silent fallbacks."""

from __future__ import annotations

import wave
from unittest import TestCase, main
from unittest.mock import patch

from app.beeper import Beeper, _LINUX_TONE_RATE, _LINUX_TONE_S, _write_tone_wav


def _linux_beeper() -> Beeper:
    with patch("app.beeper.platform.system", return_value="Linux"):
        return Beeper()


class LinuxPlayTests(TestCase):
    def test_prefers_first_available_player(self) -> None:
        available = {"paplay": "/usr/bin/paplay", "aplay": "/usr/bin/aplay"}
        beeper = _linux_beeper()
        with (
            patch("app.beeper.shutil.which", side_effect=available.get),
            patch("app.beeper.subprocess.Popen") as popen,
        ):
            beeper._play()
        command = popen.call_args.args[0]
        self.assertEqual(command[0], "paplay")
        self.assertTrue(command[1].endswith(".wav"))

    def test_player_is_found_once(self) -> None:
        beeper = _linux_beeper()
        with (
            patch("app.beeper.shutil.which", return_value="/usr/bin/pw-play") as which,
            patch("app.beeper.subprocess.Popen") as popen,
        ):
            beeper._play()
            beeper._play()
        self.assertEqual(which.call_count, 1)
        self.assertEqual(popen.call_count, 2)
        self.assertEqual(popen.call_args_list[0].args, popen.call_args_list[1].args)

    def test_no_player_rings_the_bell(self) -> None:
        beeper = _linux_beeper()
        with (
            patch("app.beeper.shutil.which", return_value=None),
            patch("app.beeper.subprocess.Popen") as popen,
            patch("app.beeper.sys.stdout") as stdout,
        ):
            beeper._play()
        popen.assert_not_called()
        stdout.write.assert_called_once_with("\a")

    def test_player_failure_does_not_raise(self) -> None:
        beeper = _linux_beeper()
        with (
            patch("app.beeper.shutil.which", return_value="/usr/bin/pw-play"),
            patch("app.beeper.subprocess.Popen", side_effect=OSError("no device")),
        ):
            beeper._play()


class ToneTests(TestCase):
    def test_tone_is_a_short_valid_wav(self) -> None:
        with wave.open(_write_tone_wav(), "rb") as tone:
            self.assertEqual(tone.getnchannels(), 1)
            self.assertEqual(tone.getsampwidth(), 2)
            self.assertEqual(tone.getframerate(), _LINUX_TONE_RATE)
            self.assertEqual(tone.getnframes(), int(_LINUX_TONE_RATE * _LINUX_TONE_S))
            self.assertGreater(max(tone.readframes(tone.getnframes())), 0)


if __name__ == "__main__":
    main()
