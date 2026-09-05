"""License files travel with the freeze; Practice lines stay original."""

from __future__ import annotations

import json
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoticeTests(unittest.TestCase):
    def test_notice_files_exist(self) -> None:
        for rel in (
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
            "licenses/Apache-2.0.txt",
            "licenses/LGPLv2.1.txt",
            "licenses/SIL-OFL-1.1.txt",
            "alert.wav",
        ):
            path = ROOT / rel
            self.assertTrue(path.is_file(), f"missing {rel}")
            self.assertGreater(path.stat().st_size, 32)

    def test_apache_and_lgpl_headers(self) -> None:
        apache = (ROOT / "licenses" / "Apache-2.0.txt").read_text(encoding="utf-8")
        lgpl = (ROOT / "licenses" / "LGPLv2.1.txt").read_text(encoding="utf-8")
        self.assertIn("Apache License", apache)
        self.assertIn("Version 2.0", apache)
        self.assertIn("GNU LESSER GENERAL PUBLIC LICENSE", lgpl)
        self.assertIn("Version 2.1", lgpl)

    def test_spec_bundles_notices_and_original_alert(self) -> None:
        spec = (ROOT / "EyeRhythm.spec").read_text(encoding="utf-8")
        for needle in (
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
            "licenses",
            "alert.wav",
        ):
            self.assertIn(needle, spec)
        self.assertNotIn("alert.mp3", spec)

    def test_alert_wav_is_pcm_wave(self) -> None:
        path = ROOT / "alert.wav"
        with wave.open(str(path), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertGreaterEqual(wav.getframerate(), 22050)
            self.assertGreater(wav.getnframes(), 1000)

    def test_practice_lines_are_original(self) -> None:
        data = json.loads((ROOT / "quotes.json").read_text(encoding="utf-8"))
        quotes = data["quotes"]
        self.assertEqual(len(quotes), data["count"])
        self.assertGreaterEqual(len(quotes), 20)
        for item in quotes:
            self.assertTrue(str(item["text"]).strip())
            self.assertEqual(item["author"], "EyesRhythm")

    def test_readme_does_not_call_the_product_free_open_source(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("free and open-source", text.lower())
        self.assertIn("THIRD_PARTY_NOTICES.md", text)
        self.assertIn("LGPLv2.1", text)


if __name__ == "__main__":
    unittest.main()
