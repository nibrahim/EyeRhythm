"""Linux window checks: Qt environment and reasons to use the browser instead."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.linux_window import prepare_window


def _prepare(env: dict[str, str], *, has_gi: bool = False, has_xcb_cursor: bool = True):
    """Run ``prepare_window`` on Linux with exactly ``env``; return (result, env after)."""
    with (
        patch.dict(os.environ, env, clear=True),
        patch("app.linux_window.sys.platform", "linux"),
        patch(
            "app.linux_window.importlib.util.find_spec",
            return_value=object() if has_gi else None,
        ),
        patch(
            "app.linux_window.ctypes.util.find_library",
            return_value="libxcb-cursor.so.0" if has_xcb_cursor else None,
        ),
    ):
        result = prepare_window()
        return result, dict(os.environ)


class OpenCvPathTests(unittest.TestCase):
    def test_clears_paths_set_by_opencv(self) -> None:
        _, env = _prepare({
            "DISPLAY": ":0",
            "QT_QPA_PLATFORM_PLUGIN_PATH": "/venv/site-packages/cv2/qt/plugins",
            "QT_QPA_FONTDIR": "/venv/site-packages/cv2/qt/fonts",
        })
        self.assertNotIn("QT_QPA_PLATFORM_PLUGIN_PATH", env)
        self.assertNotIn("QT_QPA_FONTDIR", env)

    def test_keeps_a_path_the_user_chose(self) -> None:
        _, env = _prepare({"DISPLAY": ":0", "QT_QPA_PLATFORM_PLUGIN_PATH": "/opt/qt/plugins"})
        self.assertEqual(env["QT_QPA_PLATFORM_PLUGIN_PATH"], "/opt/qt/plugins")


class WindowProblemTests(unittest.TestCase):
    def test_wayland_does_not_need_xcb_cursor(self) -> None:
        result, _ = _prepare({"WAYLAND_DISPLAY": "wayland-0"}, has_xcb_cursor=False)
        self.assertIsNone(result)

    def test_wayland_session_type_alone_counts_as_wayland(self) -> None:
        result, _ = _prepare({"XDG_SESSION_TYPE": "wayland"}, has_xcb_cursor=False)
        self.assertIsNone(result)

    def test_x11_without_xcb_cursor_is_a_problem(self) -> None:
        result, _ = _prepare({"DISPLAY": ":0"}, has_xcb_cursor=False)
        self.assertIn("libxcb-cursor", result)

    def test_x11_with_xcb_cursor_is_fine(self) -> None:
        result, _ = _prepare({"DISPLAY": ":0"})
        self.assertIsNone(result)

    def test_forced_xcb_on_wayland_needs_xcb_cursor(self) -> None:
        result, _ = _prepare(
            {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0", "QT_QPA_PLATFORM": "xcb"},
            has_xcb_cursor=False,
        )
        self.assertIn("libxcb-cursor", result)

    def test_no_display_is_a_problem(self) -> None:
        result, _ = _prepare({})
        self.assertIn("no graphical session", result)


class BackendChoiceTests(unittest.TestCase):
    def test_without_gtk_uses_qt_directly(self) -> None:
        _, env = _prepare({"DISPLAY": ":0"})
        self.assertEqual(env["PYWEBVIEW_GUI"], "qt")

    def test_gtk_install_is_left_alone(self) -> None:
        result, env = _prepare({"DISPLAY": ":0"}, has_gi=True, has_xcb_cursor=False)
        self.assertIsNone(result)
        self.assertNotIn("PYWEBVIEW_GUI", env)

    def test_user_choice_of_gtk_is_respected(self) -> None:
        result, env = _prepare({"DISPLAY": ":0", "PYWEBVIEW_GUI": "gtk"}, has_xcb_cursor=False)
        self.assertIsNone(result)
        self.assertEqual(env["PYWEBVIEW_GUI"], "gtk")

    def test_kde_uses_qt_even_with_gtk_installed(self) -> None:
        result, _ = _prepare(
            {"DISPLAY": ":0", "KDE_FULL_SESSION": "true"}, has_gi=True, has_xcb_cursor=False
        )
        self.assertIn("libxcb-cursor", result)


class OtherPlatformTests(unittest.TestCase):
    def test_other_platforms_are_untouched(self) -> None:
        with (
            patch.dict(
                os.environ, {"QT_QPA_PLATFORM_PLUGIN_PATH": "/x/cv2/qt/plugins"}, clear=True
            ),
            patch("app.linux_window.sys.platform", "darwin"),
        ):
            self.assertIsNone(prepare_window())
            self.assertIn("QT_QPA_PLATFORM_PLUGIN_PATH", os.environ)


if __name__ == "__main__":
    unittest.main()
