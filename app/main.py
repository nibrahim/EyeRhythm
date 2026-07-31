"""
EyeRhythm - BlinkCounter (open-source edition)

Live blink counting using the built-in webcam. Displays only a compact
statistics panel — the camera feed is never shown.

Run from the project root:
    python -m app.main            (default camera 0)
    python -m app.main --camera 1

Keys:
  q = quit                b = beep on blink
  a = alert on low rate   t = always on top
(Screen time and daily average blink rate are tracked silently, survive
restarts and roll over to zero at midnight.)
"""

import argparse
import platform
import sys
import threading
import time
from pathlib import Path

import cv2

# ---------------------------------------------------------------------------
# Resource root – works both as a normal script and as a PyInstaller .exe
# ---------------------------------------------------------------------------
def _resource_root() -> Path:
    """Project root (script) or the PyInstaller extraction folder (frozen)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


ROOT = _resource_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blink_core import BlinkDetector  # noqa: E402
from blink_core.screentime import ScreenTimeTracker  # noqa: E402
from app.overlay import render_stats, render_startup  # noqa: E402
from app.beeper import Beeper  # noqa: E402

WINDOW = "EyeRhythm - BlinkCounter"
STARTUP_WINDOW = "EyeRhythm - Startup"

MODEL_PATH = str(ROOT / "models" / "face_landmarker.task")
FONT_DIR = ROOT / "assets" / "fonts"

# Low-rate alert: background thread polls every ALERT_POLL_S.
# Beeps while face is present AND instantaneous bpm < threshold.
# Stops beeping as soon as rate recovers to the safe zone.
# Thread is started when A is turned ON and stopped when A is turned OFF
# (or when the app exits).
ALERT_BPM_THRESHOLD = 10.0
ALERT_POLL_S = 0.5


class AlertMonitor:
    """
    Background thread that watches the live blink rate.

    Lifecycle
    ---------
    start()  – begin the monitoring loop (called when user presses A ON)
    stop()   – signal the loop to exit and join the thread (A OFF / quit)
    update(bpm, face_found) – called from the main loop every frame so the
                              worker always sees the latest values
    """

    def __init__(self, beeper: Beeper, threshold: float = ALERT_BPM_THRESHOLD,
                 poll_s: float = ALERT_POLL_S):
        self._beeper = beeper
        self._threshold = threshold
        self._poll_s = poll_s
        self._lock = threading.Lock()
        self._bpm = 0.0
        self._face_found = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---- main-loop API ------------------------------------------------

    def update(self, bpm: float, face_found: bool) -> None:
        with self._lock:
            self._bpm = bpm
            self._face_found = face_found

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="AlertMonitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- worker -------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                bpm = self._bpm
                face = self._face_found
            # Beep only while rate is in the danger zone
            if face and bpm < self._threshold:
                self._beeper.beep()
            # Wait up to poll interval, but wake early on stop
            self._stop.wait(self._poll_s)


def _reapply_topmost(states) -> None:
    """Set/unset the always-on-top flag on the (possibly new) window."""
    try:
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST,
                              1.0 if states["ontop"] else 0.0)
    except cv2.error:
        pass  # older OpenCV builds without TOPMOST support


def _frame_is_black(frame) -> bool:
    return frame is None or frame.mean() < 2.0


def open_camera(index: int) -> cv2.VideoCapture | None:
    """Open the webcam with the best backend for the current OS and
    verify it actually delivers non-black frames. Some Windows cameras
    return black frames with certain backend/resolution combinations,
    so we probe a few backends and never force a resolution."""
    system = platform.system()
    if system == "Windows":
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    elif system == "Darwin":  # macOS
        backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    else:
        backends = [cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            continue
        # warm up: some cameras need a few frames before exposure kicks in
        good = False
        for _ in range(15):
            ok, frame = cap.read()
            if ok and not _frame_is_black(frame):
                good = True
                break
            time.sleep(0.05)
        if good:
            return cap
        cap.release()
    return None


# ------------------------------------------------------------------ startup

def _check_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _show_startup(checks: list, footer: str = "") -> None:
    """Paint the startup panel and process one OpenCV event."""
    canvas = render_startup(checks, footer=footer)
    cv2.imshow(STARTUP_WINDOW, canvas)
    cv2.waitKey(1)


def run_startup_checks_gui(camera_index: int) -> bool:
    """
    Run the same sanity checks as before, but display them in a GUI window
    so the result is visible when the app is packaged as a standalone .exe
    (no console).

    Returns True if the user may proceed, False if they chose to exit.
    """
    checks: list[dict] = []
    failures: list[str] = []

    cv2.namedWindow(STARTUP_WINDOW, cv2.WINDOW_AUTOSIZE)

    def add(label: str, status: str, detail: str = "", fail_msg: str = ""):
        checks.append({"label": label, "status": status, "detail": detail})
        _show_startup(checks, footer="Checking…")
        if status == "FAIL" and fail_msg:
            failures.append(fail_msg)

    # 1. Python runtime
    py_ok = sys.version_info >= (3, 10)
    add("Python runtime  (3.10+ required)",
        "OK" if py_ok else "FAIL",
        fail_msg="Python version is too old. Please use Python 3.10 or newer.")

    # 2. Imaging / display stack
    imaging_ok = (_check_import("cv2") and _check_import("numpy")
                  and _check_import("PIL"))
    add("Imaging & display components",
        "OK" if imaging_ok else "FAIL",
        fail_msg="Core imaging components are missing.")

    # 3. Face analysis engine
    engine_ok = _check_import("mediapipe")
    add("Face analysis engine",
        "OK" if engine_ok else "FAIL",
        fail_msg="Face analysis engine is missing.")

    # 4. Model asset
    model_ok = Path(MODEL_PATH).is_file()
    add("Analysis model file",
        "OK" if model_ok else "FAIL",
        detail="" if model_ok else str(MODEL_PATH),
        fail_msg=f"Model file not found at:\n{MODEL_PATH}")

    # 5. Fonts (optional)
    font_ok = (FONT_DIR / "Inter-Regular.ttf").is_file()
    add("Typography assets",
        "OK" if font_ok else "WARN",
        detail="" if font_ok else "will fall back to system default font")

    # 6. Camera (show probing state first)
    checks.append({"label": "Camera access", "status": "..",
                   "detail": "probing…"})
    _show_startup(checks, footer="Checking…")
    cap = open_camera(camera_index)
    camera_ok = cap is not None
    if camera_ok:
        cap.release()
    checks[-1] = {
        "label": "Camera access",
        "status": "OK" if camera_ok else "FAIL",
        "detail": "" if camera_ok else f"camera {camera_index} not usable",
    }
    if not camera_ok:
        failures.append(
            f"Camera {camera_index} is not delivering usable frames.\n"
            "• Close other apps that may be using the webcam\n"
            "• Check OS camera privacy permissions\n"
            "• Try:  EyeRhythm.exe --camera 1")
    _show_startup(checks, footer="Checking…")

    # ---- result -------------------------------------------------------
    if not failures:
        _show_startup(checks, footer="All checks passed  ·  starting…")
        # brief pause so the user can see the green checklist
        t_end = time.monotonic() + 1.2
        while time.monotonic() < t_end:
            if cv2.waitKey(50) & 0xFF in (ord("q"), ord("Q"), 27):
                cv2.destroyWindow(STARTUP_WINDOW)
                return False
        cv2.destroyWindow(STARTUP_WINDOW)
        return True

    # failures – show troubleshooting and wait for Y / Q
    for msg in failures:
        checks.append({"label": msg.split("\n")[0][:60], "status": "FAIL",
                       "detail": ""})
    _show_startup(
        checks,
        footer="Y  continue anyway    ·    Q / Esc  quit")

    while True:
        key = cv2.waitKey(50) & 0xFF
        if key in (ord("y"), ord("Y")):
            cv2.destroyWindow(STARTUP_WINDOW)
            return True
        if key in (ord("q"), ord("Q"), 27):
            cv2.destroyWindow(STARTUP_WINDOW)
            return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EyeRhythm - BlinkCounter (open-source)")
    parser.add_argument("--camera", type=int, default=0,
                        help="webcam index (default 0)")
    parser.add_argument("--skip-checks", action="store_true",
                        help="skip startup checks (not recommended)")
    args = parser.parse_args()

    if not args.skip_checks:
        if not run_startup_checks_gui(args.camera):
            sys.exit(1)

    cap = open_camera(args.camera)
    if cap is None:
        # last-resort GUI message if camera died between checks and open
        checks = [{"label": f"Camera {args.camera} not usable",
                   "status": "FAIL",
                   "detail": "Close other apps or try --camera 1"}]
        cv2.namedWindow(STARTUP_WINDOW, cv2.WINDOW_AUTOSIZE)
        _show_startup(checks, footer="Q / Esc  quit")
        while True:
            if cv2.waitKey(50) & 0xFF in (ord("q"), ord("Q"), 27):
                break
        cv2.destroyAllWindows()
        sys.exit(1)

    detector = BlinkDetector(MODEL_PATH)
    screen_time = ScreenTimeTracker()
    beeper = Beeper()
    alert = AlertMonitor(beeper)
    states = {"beep": False, "alert": False, "ontop": False}
    apply_topmost = False
    t0 = time.monotonic()
    fps, frames = 0.0, 0
    fps_t = t0
    last_ts_ms = -1
    window_ready = False

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # MediaPipe requires STRICTLY increasing timestamps; two frames
            # can land in the same millisecond, so enforce +1 ms minimum.
            ts_ms = max(int((time.monotonic() - t0) * 1000), last_ts_ms + 1)
            last_ts_ms = ts_ms
            res = detector.process_frame(frame, ts_ms)
            screen_time.tick(res.face_found)

            if res.blink_just_counted:
                screen_time.add_blink()
                if states["beep"]:
                    beeper.beep()

            # Feed the latest rate to the alert worker (if running)
            alert.update(res.blinks_per_minute, res.face_found)

            frames += 1
            now = time.monotonic()
            if now - fps_t >= 1.0:
                fps = frames / (now - fps_t)
                frames, fps_t = 0, now

            # Always statistics-only view (camera feed is never shown).
            # Big number = daily total from JSON (survives restarts).
            canvas = render_stats(
                res, fps, screen_time.formatted(), states,
                avg_bpm=screen_time.avg_blinks_per_minute,
                total_blinks=screen_time.blinks_today)

            if not window_ready:
                # Clean floating-card window: fixed size, no status bar.
                # (True OS title-bar removal is not available in OpenCV;
                #  the rounded outer shell makes the UI look borderless.)
                flags = cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL
                try:
                    cv2.namedWindow(WINDOW, flags)
                except cv2.error:
                    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
                h, w = canvas.shape[:2]
                cv2.resizeWindow(WINDOW, w, h)
                window_ready = True

            cv2.imshow(WINDOW, canvas)

            if apply_topmost:
                _reapply_topmost(states)
                apply_topmost = False

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):  # q or Esc
                break
            elif key in (ord("b"), ord("B")):
                states["beep"] = not states["beep"]
            elif key in (ord("a"), ord("A")):
                states["alert"] = not states["alert"]
                if states["alert"]:
                    alert.start()          # start background monitor
                else:
                    alert.stop()           # stop thread immediately
            elif key in (ord("t"), ord("T")):
                states["ontop"] = not states["ontop"]
                apply_topmost = True
    finally:
        alert.stop()                       # ensure thread is gone on quit
        screen_time.save()
        detector.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
