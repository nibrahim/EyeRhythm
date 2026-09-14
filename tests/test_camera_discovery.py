"""Camera discovery: OS order and names, desk webcams only."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from app.engine import (
    _clear_camera_cache,
    _describe_from_os_devices,
    _frame_is_black,
    _frame_is_usable,
    _is_desk_camera,
    _is_mobile_camera_model,
    _is_mobile_camera_name,
    _opencv_avfoundation_order,
    describe_cameras,
    open_cameras,
    resolve_startup_camera,
)


class CameraDiscoveryTests(unittest.TestCase):
    def test_usable_requires_mean_and_variance(self) -> None:
        live = np.random.randint(80, 160, (480, 640, 3), dtype=np.uint8)
        self.assertTrue(_frame_is_usable(live))

        dark_static = np.full((480, 640, 3), 10, dtype=np.uint8)
        self.assertFalse(_frame_is_usable(dark_static))

        black = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertTrue(_frame_is_black(black))
        self.assertFalse(_frame_is_usable(black))

    def test_mobile_names_and_models_are_rejected(self) -> None:
        self.assertTrue(_is_mobile_camera_name("iPhone12Mini Camera"))
        self.assertTrue(_is_mobile_camera_name("Pranay's iPhone"))
        self.assertTrue(_is_mobile_camera_model("iPhone13,1"))
        self.assertFalse(_is_mobile_camera_name("FaceTime HD Camera (Built-in)"))

    def test_desk_camera_allowlist_on_macos(self) -> None:
        self.assertTrue(_is_desk_camera(
            "FaceTime HD Camera (Built-in)",
            "UVC Camera VendorID_1452 ProductID_34068",
        ))
        self.assertTrue(_is_desk_camera(
            "Brio 100",
            "UVC Camera VendorID_1133 ProductID_2380",
        ))
        self.assertTrue(_is_desk_camera("Brio 100", ""))
        self.assertFalse(_is_desk_camera(
            "iPhone12Mini Camera",
            "iPhone13,1",
        ))

    def test_desk_cameras_listed_when_probe_fails(self) -> None:
        """Settings still shows Brio + FaceTime if the first frame is black."""
        devices = [
            {
                "name": "FaceTime HD Camera (Built-in)",
                "model_id": "UVC Camera VendorID_1452 ProductID_34068",
                "unique_id": "0x8020000005ac8514",
            },
            {
                "name": "Brio 100",
                "model_id": "UVC Camera VendorID_1133 ProductID_2380",
                "unique_id": "0x14130000046d094c",
            },
            {
                "name": "iPhone12Mini Camera",
                "model_id": "iPhone13,1",
                "unique_id": "67A0AFDB-0410-4AE1-B838-268500000001",
            },
        ]
        with patch(
            "app.engine._probe_camera_index",
            return_value=(False, 0, 0, 0.0, 0.0),
        ):
            matched = _describe_from_os_devices(
                devices, max_index=6, backend=0,
            )

        self.assertEqual(
            [(m["name"], m["index"], m["label"]) for m in matched],
            [("Brio 100", 0, "Brio 100"),
             ("FaceTime HD Camera (Built-in)", 1,
              "FaceTime HD Camera (Built-in)")],
        )

    def test_os_index_matches_opencv_index(self) -> None:
        """Without unique IDs, list slot i still maps to OpenCV index i."""
        devices = [
            {
                "name": "FaceTime HD Camera (Built-in)",
                "model_id": "UVC Camera VendorID_1452 ProductID_34068",
            },
            {
                "name": "Brio 100",
                "model_id": "UVC Camera VendorID_1133 ProductID_2380",
            },
            {
                "name": "iPhone12Mini Camera",
                "model_id": "iPhone13,1",
            },
        ]

        def probe(index: int, _backend: int):
            if index == 0:
                return True, 1920, 1080, 0.0, 0.0
            if index == 1:
                return True, 1280, 720, 0.0, 0.0
            return False, 0, 0, 0.0, 0.0

        with patch("app.engine._probe_camera_index", side_effect=probe):
            matched = _describe_from_os_devices(
                devices, max_index=6, backend=0,
            )

        by_name = {str(m["name"]): int(m["index"]) for m in matched}
        self.assertEqual(by_name["FaceTime HD Camera (Built-in)"], 0)
        self.assertEqual(by_name["Brio 100"], 1)
        self.assertNotIn("iPhone12Mini Camera", by_name)

    def test_unique_id_sort_matches_opencv_not_listing_order(self) -> None:
        """OpenCV sorts by uniqueID, so FaceTime listed first is not index 0."""
        devices = [
            {
                "name": "FaceTime HD Camera (Built-in)",
                "model_id": "UVC Camera VendorID_1452 ProductID_34068",
                "unique_id": "ffff-facetime",
            },
            {
                "name": "Brio 100",
                "model_id": "UVC Camera VendorID_1133 ProductID_2380",
                "unique_id": "aaaa-brio",
            },
        ]
        ordered = _opencv_avfoundation_order(devices)
        self.assertEqual(
            [d["name"] for d in ordered],
            ["Brio 100", "FaceTime HD Camera (Built-in)"],
        )

        def probe(index: int, _backend: int):
            if index in (0, 1):
                return True, 1280, 720, 0.0, 0.0
            return False, 0, 0, 0.0, 0.0

        with patch("app.engine._probe_camera_index", side_effect=probe):
            matched = _describe_from_os_devices(
                devices, max_index=6, backend=0,
            )

        by_name = {str(m["name"]): int(m["index"]) for m in matched}
        self.assertEqual(by_name["Brio 100"], 0)
        self.assertEqual(by_name["FaceTime HD Camera (Built-in)"], 1)

    def test_real_macos_unique_ids_put_usb_before_facetime(self) -> None:
        """Typical Mac uniqueIDs: USB 0x14… sorts before built-in 0x80…."""
        devices = [
            {
                "name": "FaceTime HD Camera (Built-in)",
                "model_id": "UVC Camera VendorID_1452 ProductID_34068",
                "unique_id": "0x8020000005ac8514",
            },
            {
                "name": "Brio 100",
                "model_id": "UVC Camera VendorID_1133 ProductID_2380",
                "unique_id": "0x14130000046d094c",
            },
            {
                "name": "iPhone12Mini Camera",
                "model_id": "iPhone13,1",
                "unique_id": "67A0AFDB-0410-4AE1-B838-268500000001",
            },
        ]
        ordered = [d["name"] for d in _opencv_avfoundation_order(devices)]
        self.assertEqual(
            ordered,
            [
                "Brio 100",
                "FaceTime HD Camera (Built-in)",
                "iPhone12Mini Camera",
            ],
        )

        def probe(index: int, _backend: int):
            if index in (0, 1):
                return True, 1280, 720, 0.0, 0.0
            return False, 0, 0, 0.0, 0.0

        with patch("app.engine._probe_camera_index", side_effect=probe):
            matched = _describe_from_os_devices(
                devices, max_index=6, backend=0,
            )

        by_name = {str(m["name"]): int(m["index"]) for m in matched}
        self.assertEqual(by_name["Brio 100"], 0)
        self.assertEqual(by_name["FaceTime HD Camera (Built-in)"], 1)
        self.assertNotIn("iPhone12Mini Camera", by_name)

    def test_saved_camera_skips_splash_picker(self) -> None:
        """Two webcams + a remembered index → do not ask again at login."""
        index, pick, hybrid = resolve_startup_camera([0, 1], saved=0, cli=None)
        self.assertEqual(index, 0)
        self.assertFalse(pick)
        self.assertFalse(hybrid)

        index, pick, hybrid = resolve_startup_camera([0, 1], saved=1, cli=None)
        self.assertEqual(index, 1)
        self.assertFalse(pick)
        self.assertFalse(hybrid)

    def test_unknown_saved_camera_asks_when_several(self) -> None:
        index, pick, hybrid = resolve_startup_camera([0, 1], saved=-1, cli=None)
        self.assertEqual(index, 0)
        self.assertTrue(pick)
        self.assertFalse(hybrid)

    def test_cli_and_single_camera_never_ask(self) -> None:
        index, pick, hybrid = resolve_startup_camera([0, 1], saved=-1, cli=1)
        self.assertEqual(index, 1)
        self.assertFalse(pick)
        self.assertFalse(hybrid)
        index, pick, hybrid = resolve_startup_camera([2], saved=-1, cli=None)
        self.assertEqual(index, 2)
        self.assertFalse(pick)
        self.assertFalse(hybrid)

    def test_saved_hybrid_uses_all_desk_cameras(self) -> None:
        index, pick, hybrid = resolve_startup_camera(
            [0, 1], saved=-1, cli=None, saved_mode="hybrid",
        )
        self.assertFalse(pick)
        self.assertTrue(hybrid)
        self.assertEqual(index, 0)

    def test_saved_hybrid_falls_back_when_only_one_camera(self) -> None:
        index, pick, hybrid = resolve_startup_camera(
            [2], saved=-1, cli=None, saved_mode="hybrid",
        )
        self.assertEqual(index, 2)
        self.assertFalse(pick)
        self.assertFalse(hybrid)

    def test_cli_overrides_saved_hybrid(self) -> None:
        index, pick, hybrid = resolve_startup_camera(
            [0, 1], saved=0, cli=1, saved_mode="hybrid",
        )
        self.assertEqual(index, 1)
        self.assertFalse(pick)
        self.assertFalse(hybrid)

    def test_describe_cameras_reuses_cache(self) -> None:
        """Splash / Settings must not re-open cameras after the first probe."""
        _clear_camera_cache()
        fake = [
            {
                "index": 0,
                "label": "FaceTime (1280×720)",
                "name": "FaceTime",
                "width": 1280,
                "height": 720,
            }
        ]
        try:
            with patch("app.engine._camera_devices", return_value=[]), patch(
                "app.engine._describe_from_os_devices", return_value=fake
            ) as desc:
                first = describe_cameras()
                second = describe_cameras()
                self.assertEqual(desc.call_count, 1)
                self.assertEqual(first, second)
                describe_cameras(refresh=True)
                self.assertEqual(desc.call_count, 2)
        finally:
            _clear_camera_cache()

    def test_open_cameras_retries_partial_failure_by_reopening_all(self) -> None:
        """If the built-in fails while USB is already open, retry the full set."""

        class _Cap:
            def release(self) -> None:
                return None

        opened: list[int] = []
        caps = {0: _Cap(), 1: _Cap()}

        def fake_open(idx, quiet=False, width_hint=None):
            opened.append(int(idx))
            # First pass: USB (1) works, built-in (0) fails.
            if len(opened) <= 2:
                return caps[idx] if idx == 1 else None
            return caps[idx]

        with patch("app.engine.open_camera", side_effect=fake_open), patch(
            "app.engine.time.sleep"
        ):
            out = open_cameras([0, 1], quiet=True)
        self.assertEqual(set(out), {0, 1})
        self.assertGreaterEqual(len(opened), 4)


if __name__ == "__main__":
    unittest.main()
