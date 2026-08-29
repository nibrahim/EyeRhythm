"""The Windows freeze must unblock downloaded DLLs before pythonnet loads."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowsUnblockHookTests(unittest.TestCase):
    def test_runtime_hook_is_wired_into_the_spec(self) -> None:
        spec = (ROOT / "EyeRhythm.spec").read_text(encoding="utf-8")
        self.assertIn("rthook_unblock_dlls.py", spec)

    def test_hook_file_exists_and_is_self_contained(self) -> None:
        hook = ROOT / "for_windows" / "rthook_unblock_dlls.py"
        self.assertTrue(hook.is_file())
        text = hook.read_text(encoding="utf-8")
        self.assertIn("Zone.Identifier", text)
        self.assertNotIn("from app.", text)


if __name__ == "__main__":
    unittest.main()
