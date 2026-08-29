"""Unit tests for Lemon Squeezy license activation (no network)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import license as app_license


def _activate_payload(
    *,
    activated: bool = True,
    error: str | None = None,
    store_id: int = 11,
    variant_id: int = 22,
    variant_name: str = "macOS",
    instance_id: str = "inst-1",
) -> dict:
    return {
        "activated": activated,
        "error": error,
        "instance": {"id": instance_id, "name": "abc"},
        "meta": {
            "store_id": store_id,
            "variant_id": variant_id,
            "variant_name": variant_name,
            "product_name": "EyesRhythm",
            "customer_email": "buyer@example.com",
        },
    }


class LicenseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._path = Path(self._tmp.name) / "license.json"
        self._env = patch.dict(
            "os.environ",
            {
                "EYERHYTHM_LICENSE_FILE": str(self._path),
                "EYERHYTHM_SKIP_LICENSE": "",
                "EYERHYTHM_REQUIRE_LICENSE": "1",
            },
            clear=False,
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        app_license.set_enforcement(True)
        self.addCleanup(lambda: app_license.set_enforcement(None))

    def test_normalize_key_strips_spaces(self) -> None:
        self.assertEqual(
            app_license.normalize_key("  ER-AB 12  CD  "),
            "ER-AB12CD",
        )

    def test_fingerprint_is_stable(self) -> None:
        with patch.object(app_license, "_raw_machine_id", return_value="machine-a"):
            a = app_license.machine_fingerprint()
            b = app_license.machine_fingerprint()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 32)

    def test_missing_file_is_not_activated_when_required(self) -> None:
        self.assertFalse(app_license.is_activated())

    def test_skip_env_disables_gate(self) -> None:
        with patch.dict("os.environ", {"EYERHYTHM_SKIP_LICENSE": "1"}):
            app_license.set_enforcement(None)
            self.assertFalse(app_license.is_required())
            self.assertTrue(app_license.is_activated())

    def test_activate_saves_local_file(self) -> None:
        payload = _activate_payload()
        with (
            patch.object(app_license, "_ls_call", return_value=payload),
            patch.object(app_license, "machine_fingerprint", return_value="fp-1"),
            patch.object(app_license, "LS_STORE_ID", 11),
            patch.object(app_license, "expected_variant_id", return_value=22),
        ):
            status = app_license.activate("ER-TEST-KEY")
            self.assertTrue(status["activated"])
            self.assertTrue(app_license.is_activated())
        saved = json.loads(self._path.read_text(encoding="utf-8"))
        self.assertEqual(saved["license_key"], "ER-TEST-KEY")
        self.assertEqual(saved["instance_id"], "inst-1")
        self.assertEqual(saved["instance_name"], "fp-1")
        self.assertEqual(saved["customer_email"], "buyer@example.com")

    def test_copied_license_from_other_machine_is_rejected(self) -> None:
        self._path.write_text(
            json.dumps(
                {
                    "license_key": "ER-TEST-KEY",
                    "instance_id": "inst-1",
                    "instance_name": "other-machine",
                }
            ),
            encoding="utf-8",
        )
        with patch.object(app_license, "machine_fingerprint", return_value="this-machine"):
            self.assertFalse(app_license.is_activated())

    def test_wrong_variant_is_rejected(self) -> None:
        payload = _activate_payload(variant_id=99, variant_name="Windows")
        with (
            patch.object(app_license, "_ls_call", return_value=payload),
            patch.object(app_license, "current_platform", return_value="mac"),
            patch.object(app_license, "LS_STORE_ID", 11),
            patch.object(app_license, "LS_VARIANT_MAC", 22),
            patch.object(app_license, "expected_variant_id", return_value=22),
        ):
            with self.assertRaises(app_license.LicenseError) as ctx:
                app_license.activate("ER-WIN-KEY")
        self.assertIn("not macOS", str(ctx.exception))
        self.assertFalse(self._path.exists())

    def test_unknown_key(self) -> None:
        payload = _activate_payload(activated=False, error="license_key not found")
        with patch.object(app_license, "_ls_call", return_value=payload):
            with self.assertRaises(app_license.LicenseError) as ctx:
                app_license.activate("not-a-real-key")
        self.assertIn("not recognised", str(ctx.exception))

    def test_empty_key(self) -> None:
        with self.assertRaises(app_license.LicenseError):
            app_license.activate("   ")

    def test_activation_limit_message(self) -> None:
        payload = _activate_payload(
            activated=False,
            error="This license key has reached the activation limit.",
        )
        with patch.object(app_license, "_ls_call", return_value=payload):
            with self.assertRaises(app_license.LicenseError) as ctx:
                app_license.activate("ER-USED-ALREADY")
        self.assertIn("already used", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
