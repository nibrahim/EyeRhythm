"""
EyeRhythm main entry
====================

Starts:
1. The processing engine (camera + blink detection + daily stats)
2. A local HTTP/WebSocket API for the React UI
3. A desktop window (pywebview) loading the UI — or the system browser
   if ``--browser`` is passed / pywebview is unavailable

Restores last session preferences (avatar, window size, Beep/Alert/On top).
"""

from __future__ import annotations

import argparse
import platform
import socket
import sys
import time
import webbrowser
from pathlib import Path

# Make sure Python can find the rest of this project (`app/`, `blink_core/`)
# even when this file is launched in unusual ways (packaged .app / .exe).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import preferences  # noqa: E402
from app.engine import EyeRhythmEngine, MODEL_PATH  # noqa: E402
from app.server import run_server, UI_DIST  # noqa: E402

# The dashboard talks to this machine only (never the internet).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8742
WINDOW_TITLE = "EyeRhythm"
DEFAULT_WIDTH = preferences.DEFAULT_WIDTH
DEFAULT_HEIGHT = preferences.DEFAULT_HEIGHT
MIN_WIDTH = preferences.MIN_WIDTH
MIN_HEIGHT = preferences.MIN_HEIGHT


class _WindowApi:
    """
    JS bridge methods exposed to the React UI via ``window.pywebview.api``.
    """

    def __init__(self) -> None:
        # The real desktop window is attached later, after pywebview creates it.
        self._window = None
        self._practice_fullscreen = False
        # Remember whether we used true fullscreen vs. “maximize”, so Exit
        # can undo the same action (toggle_fullscreen vs. just resizing).
        self._used_native_fullscreen = False
        # Window size before Practice, so we can restore it afterwards.
        self._pre_practice_geometry: tuple[int, int] | None = None
        # Splash may grow a compact window; do not persist that size.
        self._splash_active = False
        self._pre_splash_geometry: tuple[int, int] | None = None

    def bind(self, window) -> None:
        """Remember the live window object so later JS calls can resize it."""
        self._window = window

    def set_camera_layout(self, expanded: bool) -> None:
        # No-op: Lens avatar replaces the expandable camera panel.
        return None

    def set_compact_layout(self, compact: bool, height=None) -> None:
        """
        Grow / shrink the desktop window for More / Less.

        Compact keeps the last expanded height in preferences so expanding
        restores the user's dashboard size instead of a stubby window.
        ``height`` is the measured outer window size from the UI (optional).
        """
        window = self._window
        want = bool(compact)
        try:
            preferences.set_compact(want)
        except Exception:
            pass
        if window is None:
            return
        try:
            w = int(getattr(window, "width", 0) or 0)
            h = int(getattr(window, "height", 0) or 0)
        except Exception:
            w, h = 0, 0
        if w < preferences.MIN_WIDTH:
            w = preferences.DEFAULT_WIDTH
        # Optional measured height from the UI (hugs the compact content).
        fit_h = None
        if height is not None:
            try:
                fit_h = int(round(float(height)))
            except (TypeError, ValueError):
                fit_h = None
        try:
            if want:
                # Shrinking: remember today’s tall size so “More” can restore it.
                if h >= preferences.MIN_EXPANDED_HEIGHT:
                    preferences.set_window_size(w, h)
                target = (
                    fit_h
                    if fit_h is not None and fit_h >= preferences.MIN_HEIGHT
                    else preferences.COMPACT_HEIGHT
                )
                window.resize(w, target)
            else:
                # Growing: use the last saved dashboard height.
                _, stored_h = preferences.get_window_size()
                if stored_h < preferences.MIN_EXPANDED_HEIGHT:
                    stored_h = preferences.DEFAULT_HEIGHT
                window.resize(w, stored_h)
        except Exception as exc:
            _log(f"compact layout toggle failed: {exc}")

    def set_splash_layout(self, enabled: bool) -> None:
        """
        Grow a compact companion window so the launch splash is readable.

        Does not change the compact preference. ``on_resized`` skips saving
        while the splash is up so a taller splash is not stored as the
        dashboard size.
        """
        window = self._window
        want = bool(enabled)
        self._splash_active = want
        if window is None:
            return
        try:
            w = int(getattr(window, "width", 0) or 0)
            h = int(getattr(window, "height", 0) or 0)
        except Exception:
            w, h = 0, 0
        if w < preferences.MIN_WIDTH:
            w = preferences.DEFAULT_WIDTH
        try:
            if want:
                self._pre_splash_geometry = (w, h)
                target_h = max(h, preferences.MIN_EXPANDED_HEIGHT)
                window.resize(w, target_h)
            else:
                geom = self._pre_splash_geometry
                self._pre_splash_geometry = None
                if geom is not None:
                    window.resize(geom[0], geom[1])
        except Exception as exc:
            _log(f"splash layout failed: {exc}")

    def set_practice_fullscreen(self, enabled: bool) -> None:
        """
        Expand the desktop window for Practice mode; restore on exit.

        Prefer native fullscreen when available; otherwise maximize.
        Idempotent — safe to call repeatedly from the React overlay.
        """
        window = self._window
        if window is None:
            return
        want = bool(enabled)
        if want == self._practice_fullscreen:
            return
        try:
            if want:
                # Remember the current size so leaving Practice can restore it.
                try:
                    w = int(getattr(window, "width", 0) or 0)
                    h = int(getattr(window, "height", 0) or 0)
                    if w > 0 and h > 0:
                        self._pre_practice_geometry = (w, h)
                except Exception:
                    self._pre_practice_geometry = None
                self._used_native_fullscreen = False
                try:
                    window.toggle_fullscreen()
                    self._used_native_fullscreen = True
                except Exception:
                    # Some platforms have no true fullscreen — fill the screen.
                    try:
                        window.maximize()
                    except Exception:
                        pass
                self._practice_fullscreen = True
            else:
                if self._used_native_fullscreen:
                    try:
                        window.toggle_fullscreen()
                    except Exception:
                        pass
                geom = self._pre_practice_geometry
                if geom is not None:
                    try:
                        window.resize(geom[0], geom[1])
                    except Exception:
                        pass
                self._pre_practice_geometry = None
                self._used_native_fullscreen = False
                self._practice_fullscreen = False
        except Exception as exc:
            _log(f"practice fullscreen toggle failed: {exc}")


def _log(msg: str) -> None:
    """Print a short diagnostic line. Never crash if the terminal is gone."""
    try:
        print(f"[EyeRhythm] {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass


def _port_free(host: str, port: int) -> bool:
    """True if nothing else is already using this local address + port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _find_port(host: str, preferred: int) -> int:
    """
    Use the preferred port if free; otherwise try the next few numbers.

    Two EyeRhythm windows (or another app) may already own 8742 — we still
    want to launch instead of failing.
    """
    if _port_free(host, preferred):
        return preferred
    for p in range(preferred + 1, preferred + 40):
        if _port_free(host, p):
            return p
    raise RuntimeError("No free localhost port for EyeRhythm UI server")


def _wait_for_server(host: str, port: int, timeout: float = 15.0) -> bool:
    """Keep poking the local API until it answers, or we give up."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _startup_console_checks(camera_index: int) -> list[str]:
    """Lightweight checks printed to stderr (no OpenCV window)."""
    issues: list[str] = []
    if sys.version_info < (3, 10):
        issues.append("Python 3.10+ is required")
    for mod in ("cv2", "numpy", "mediapipe", "fastapi", "uvicorn"):
        try:
            __import__(mod)
        except Exception:
            issues.append(f"Missing dependency: {mod}")
    if not Path(MODEL_PATH).is_file():
        issues.append(f"Model not found: {MODEL_PATH}")
    if not (UI_DIST / "index.html").is_file():
        issues.append(
            "React UI not built. Run:  cd frontend && npm install && npm run build"
        )
    return issues


def _window_size_from_prefs() -> tuple[int, int]:
    """Last-session window size, or a safe compact default if prefs fail."""
    try:
        return preferences.launch_window_geometry()
    except Exception:
        return DEFAULT_WIDTH, preferences.COMPACT_HEIGHT


def _save_window_size(window) -> None:
    """Best-effort persist of current window dimensions."""
    try:
        w = int(getattr(window, "width", 0) or 0)
        h = int(getattr(window, "height", 0) or 0)
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            return
        # Compact height is fixed — do not overwrite the expanded size.
        if preferences.get_compact():
            preferences.save(window_width=w)
            _log(f"saved compact window width {w}")
            return
        preferences.set_window_size(w, h)
        _log(f"saved window size {w}x{h}")
    except Exception as exc:
        _log(f"could not save window size: {exc}")


def _app_icon_path() -> Path | None:
    """Brand mark used as the Dock / taskbar icon when running from source."""
    for name in ("app_icon.png", "EyeRhythm.icns", "EyeRhythm.ico", "logo.svg"):
        path = ROOT / "assets" / name
        if path.is_file():
            return path
    return None


def _apply_app_icon() -> None:
    """
    Running from source is a Python process, so macOS shows the Python icon
    in the Dock unless we set the application image ourselves. The packaged
    .app already has this icon in Info.plist.
    """
    icon = _app_icon_path()
    if icon is None:
        return
    if platform.system() != "Darwin":
        return
    try:
        from AppKit import NSApplication, NSImage  # type: ignore

        image = NSImage.alloc().initWithContentsOfFile_(str(icon))
        if image is None:
            return
        NSApplication.sharedApplication().setApplicationIconImage_(image)
    except Exception as exc:
        _log(f"could not set app icon: {exc}")


def _open_webview(url: str, engine: EyeRhythmEngine) -> None:
    """Native desktop window via pywebview (macOS + Windows + Linux)."""
    import webview

    _apply_app_icon()

    width, height = _window_size_from_prefs()
    prefs = preferences.load()
    ontop = bool(prefs.get("ontop", False))
    _log(f"restoring window {width}x{height} ontop={ontop}")

    # js_api lets the React UI call back into Python (resize / fullscreen).
    api = _WindowApi()
    window = webview.create_window(
        WINDOW_TITLE,
        url,
        width=width,
        height=height,
        min_size=(MIN_WIDTH, MIN_HEIGHT),
        resizable=True,
        confirm_close=False,
        background_color="#E8F0F8",
        js_api=api,
        on_top=ontop,
    )
    api.bind(window)

    def apply_ontop(flag: bool) -> None:
        """Keep the window above others when the user turns On top on."""
        try:
            window.on_top = flag
        except Exception:
            pass

    engine.on_ontop_change(apply_ontop)

    def on_resized():
        if api._splash_active:
            return
        _save_window_size(window)

    def on_closing():
        # Remember size and switches so the next launch looks the same.
        _save_window_size(window)
        # Keep toggles in sync with engine (already auto-saved on change).
        try:
            preferences.set_toggles(**engine.get_toggles())
        except Exception:
            pass

    # pywebview event hooks (versions differ slightly — guard each).
    try:
        window.events.resized += on_resized
    except Exception:
        pass
    try:
        window.events.closing += on_closing
    except Exception:
        try:
            window.events.closed += on_closing
        except Exception:
            pass

    # Block until the window is closed.
    webview.start(debug=False)
    # Final save after start() returns (window gone).
    _save_window_size(window)


def main() -> None:
    """
    Boot sequence (plain English):

    1. Check Python, libraries, the face model, and the built dashboard.
    2. Pick a free localhost port.
    3. Start the camera/blink engine in the background.
    4. Start the tiny local web server the dashboard talks to.
    5. Open a desktop window (or the browser) pointing at that server.
    6. On quit: stop the camera loop and save today’s stats.
    """
    parser = argparse.ArgumentParser(
        description="EyeRhythm — blink rhythm companion (React UI)")
    parser.add_argument("--camera", type=int, default=0,
                        help="webcam index (default 0)")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="local API host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"local API port (default {DEFAULT_PORT})")
    parser.add_argument("--browser", action="store_true",
                        help="open system browser instead of desktop window")
    parser.add_argument("--skip-checks", action="store_true",
                        help="skip dependency / build checks")
    parser.add_argument("--no-engine", action="store_true",
                        help="UI only (dev; no camera) — not for normal use")
    args = parser.parse_args()

    if not args.skip_checks:
        issues = _startup_console_checks(args.camera)
        for msg in issues:
            _log(f"CHECK: {msg}")
        hard = [m for m in issues if m.startswith("Python")
                or m.startswith("Model") or m.startswith("React")]
        if hard:
            for m in hard:
                print(m, file=sys.stderr)
            sys.exit(1)

    port = args.port
    try:
        if not _port_free(args.host, port):
            port = _find_port(args.host, port)
            _log(f"port {args.port} busy — using {port}")
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    # The engine owns the webcam and all blink numbers. --no-engine is a
    # developer shortcut: show the dashboard without opening the camera.
    engine = EyeRhythmEngine(camera_index=args.camera)
    if not args.no_engine:
        engine.start()

    # Local HTTP + WebSocket for the React UI (same machine only).
    run_server(engine, host=args.host, port=port)
    url = f"http://{args.host}:{port}/"
    _log(f"UI at {url}")
    _log(f"OS={platform.system()}  model={MODEL_PATH}")
    _log(f"prefs: {preferences.load()}")

    if not _wait_for_server(args.host, port):
        _log("server failed to start in time")
        engine.stop()
        sys.exit(1)

    use_browser = args.browser
    if not use_browser:
        try:
            import webview  # noqa: F401
        except ImportError:
            _log("pywebview not installed — falling back to browser")
            use_browser = True

    try:
        if use_browser:
            # Developer / fallback path: the OS browser, not a native window.
            webbrowser.open(url)
            _log("running in browser mode — press Ctrl+C to quit")
            while True:
                time.sleep(0.5)
        else:
            # Normal path: a compact desktop window wrapping the same UI.
            _open_webview(url, engine)
    except KeyboardInterrupt:
        _log("interrupted")
    finally:
        # Always stop the camera loop, even if the window closed abruptly.
        engine.stop()
        _log("shutdown complete")


if __name__ == "__main__":
    main()
