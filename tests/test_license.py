"""Unit tests for Dodo Payments license activation (no network)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import license as app_license


def _activate_payload(
    *,
    instance_id: str = "lki_1",
    product_id: str = "pdt_mac",
    product_name: str = "EyesRhythm for macOS",
    email: str = "buyer@example.com",
) -> dict:
    return {
        "id": instance_id,
        "business_id": "biz_1",
        "name": "fp-1",
        "license_key_id": "lic_1",
        "created_at": "2026-01-01T00:00:00Z",
        "product": {"product_id": product_id, "name": product_name},
        "customer": {
            "customer_id": "cus_1",
            "name": "Buyer",
            "email": email,
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

    def test_packaged_copy_is_free_unless_gate_is_forced(self) -> None:
        with patch.dict(
            "os.environ",
            {"EYERHYTHM_SKIP_LICENSE": "", "EYERHYTHM_REQUIRE_LICENSE": ""},
        ):
            app_license.set_enforcement(None)
            with patch.object(app_license.sys, "frozen", True, create=True):
                self.assertFalse(app_license.is_required())
                self.assertTrue(app_license.is_activated())

    def test_activate_saves_local_file(self) -> None:
        payload = _activate_payload()
        with (
            patch.object(
                app_license, "_dodo_call", return_value=(201, payload)
            ),
            patch.object(app_license, "machine_fingerprint", return_value="fp-1"),
            patch.object(app_license, "DODO_PRODUCT_MAC", "pdt_mac"),
            patch.object(app_license, "expected_product_id", return_value="pdt_mac"),
        ):
            status = app_license.activate("ER-TEST-KEY")
            self.assertTrue(status["activated"])
            self.assertTrue(app_license.is_activated())
        saved = json.loads(self._path.read_text(encoding="utf-8"))
        self.assertEqual(saved["license_key"], "ER-TEST-KEY")
        self.assertEqual(saved["instance_id"], "lki_1")
        self.assertEqual(saved["instance_name"], "fp-1")
        self.assertEqual(saved["customer_email"], "buyer@example.com")
        self.assertEqual(saved["provider"], "dodo")

    def test_copied_license_from_other_machine_is_rejected(self) -> None:
        self._path.write_text(
            json.dumps(
                {
                    "license_key": "ER-TEST-KEY",
                    "instance_id": "lki_1",
                    "instance_name": "other-machine",
                }
            ),
            encoding="utf-8",
        )
        with patch.object(app_license, "machine_fingerprint", return_value="this-machine"):
            self.assertFalse(app_license.is_activated())

    def test_wrong_product_is_rejected_and_deactivated(self) -> None:
        payload = _activate_payload(
            product_id="pdt_win",
            product_name="EyesRhythm for Windows",
        )
        calls: list[tuple[str, dict]] = []

        def fake_call(action: str, fields: dict) -> tuple[int, dict]:
            calls.append((action, fields))
            if action == "activate":
                return 201, payload
            return 200, {}

        with (
            patch.object(app_license, "_dodo_call", side_effect=fake_call),
            patch.object(app_license, "current_platform", return_value="mac"),
            patch.object(app_license, "DODO_PRODUCT_MAC", "pdt_mac"),
            patch.object(app_license, "expected_product_id", return_value="pdt_mac"),
        ):
            with self.assertRaises(app_license.LicenseError) as ctx:
                app_license.activate("ER-WIN-KEY")
        self.assertIn("not macOS", str(ctx.exception))
        self.assertFalse(self._path.exists())
        self.assertEqual(calls[1][0], "deactivate")
        self.assertEqual(calls[1][1]["license_key_instance_id"], "lki_1")

    def test_unknown_key(self) -> None:
        with patch.object(
            app_license, "_dodo_call", return_value=(404, {"message": "not found"})
        ):
            with self.assertRaises(app_license.LicenseError) as ctx:
                app_license.activate("not-a-real-key")
        self.assertIn("not recognised", str(ctx.exception))

    def test_empty_key(self) -> None:
        with self.assertRaises(app_license.LicenseError):
            app_license.activate("   ")

    def test_activation_limit_message(self) -> None:
        with patch.object(
            app_license,
            "_dodo_call",
            return_value=(
                422,
                {"message": "This license key has reached the activation limit."},
            ),
        ):
            with self.assertRaises(app_license.LicenseError) as ctx:
                app_license.activate("ER-USED-ALREADY")
        self.assertIn("already used", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
