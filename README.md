# EyeRhythm — BlinkCounter (Open-Source Edition)

Reliable real-time eye blink detection with a live counter, using only the
built-in laptop webcam. **Statistics-only interface** — the camera feed is
never displayed. 100% open-source stack, identical business logic on
Windows, macOS and Linux.

## Eye-health features

- **Blink-rate guidance** — the UI shows your live blinks/min with a
  colour indicator against the healthy spontaneous rate of ~15–20
  blinks/min reported in medical research; blink rate can drop by half
  or more during screen use (computer vision syndrome), so the app
  reminds you to blink more.
- **Daily average blink rate** — total blinks counted today divided by
  screen-time minutes, shown under “Screen time today” with the same
  green / amber / red indicator. Survives the `R` reset and app restarts;
  rolls over at midnight with screen time.
- **Daily screen-time tracking** — the app silently accumulates how long
  a face is in front of the screen. It is stored in
  `~/.eyerhythm_blinkcounter/screentime.json`, survives the `R` reset key
  and app restarts, and automatically resets to zero at midnight.
- **Modern UI** — rendered with the bundled open-source
  [Inter](https://rsms.me/inter/) typeface (SIL OFL license) in
  `assets/fonts/`. Brand theme: blue / green / brown; the EyeRhythm logo
  (drawn programmatically) sits top-right of the stats panel.
- **Blink beep (B)** — optional audio cue on every counted blink, using
  only what ships with the OS (winsound on Windows, afplay on macOS).
  Off by default.
- **Low-rate alert (A)** — optional continuous beep for 30 seconds when
  the instantaneous rate drops below 10 blinks/min. Off by default;
  toggle with `A`.
- **Always on top (T)** — keep the counter visible above all other
  application windows.
- **Startup self-check** — on launch the app verifies the runtime,
  required components, model assets and camera availability, then
  offers a clear exit path with short troubleshooting advice if
  anything is missing.

## Keys

| Key | Action                                   |
|-----|------------------------------------------|
| Q / Esc | quit                                 |
| R   | reset blink counter                      |
| B   | beep on blink ON/OFF (default OFF)       |
| A   | alert on low rate ON/OFF (default OFF)   |
| T   | always-on-top ON/OFF                     |

All toggles and their current state are shown in the in-app help bar.

## How it works

```
webcam frame (never shown)
   ├─> optional CLAHE low-light enhancement (only when dim)
   └─> MediaPipe Face Landmarker (478 landmarks + 52 blendshapes, CPU real-time)
         ├─> eyeBlinkLeft/Right blendshape scores  (primary signal)
         ├─> Eye Aspect Ratio from eye landmarks   (fallback signal)
         ├─> frontal-face gate (eye-to-mouth distance symmetry)
         ├─> lightweight glasses detector (nose-bridge edge energy)
         └─> adaptive per-person threshold + hysteresis state machine
               └─> blink events -> live counter + blinks/min
```

Key reliability features:

- **Adaptive thresholds** — the detector learns each person's open-eye
  baseline (rolling percentile over ~10 s) and sets the blink threshold
  relative to it. No fixed magic numbers, robust across eye shapes and
  eyeglasses.
- **Hysteresis + refractory period** — a blink is only counted on a full
  close→open cycle; one blink can never be counted twice.
- **Both eyes must agree** — winks and single-eye landmark jitter are
  not counted as blinks.
- **EAR fallback** — if blendshapes are unavailable the geometric Eye
  Aspect Ratio (Soukupová & Čech 2016) takes over automatically.
- **Frontal-face gate (anti false-positive)** — distances from the left
  and right eye centres to the mouth centre must agree within ~15 %.
  When the head is turned or moving (large asymmetry) a candidate blink
  is discarded.
- **Low-light enhancement (anti false-negative)** — when mean luminance
  is low, CLAHE is applied to the L channel of LAB before landmark
  detection, improving signal quality under dim lighting.
- **Glasses compensation (anti false-negative)** — a lightweight
  nose-bridge horizontal-edge detector flags eyeglasses; the close
  threshold is then relaxed so weaker blendshape / EAR signals still
  register.

## Install (Windows)

1. Install Python 3.10–3.12 (or newer) from https://python.org
   — during setup tick **"Add python.exe to PATH"**.
2. Open Command Prompt in this folder and run:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Start the app (or double-click `run_windows.bat`):

   ```bat
   python -m app.main
   ```

## Install (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m app.main
```

macOS will ask for camera permission the first time — allow it
(System Settings → Privacy & Security → Camera → Terminal/IDE).

## Usage

- A compact window opens showing only the statistics panel (no video).
- Panel contents: total **BLINKS**, eye state, **blinks/min**, FPS,
  medical guidance note and daily screen-time.
- Keys: `q` quit · `r` reset counter · `b` beep · `a` alert · `t` always-on-top.
- Wrong camera? `python -m app.main --camera 1`
- Skip the startup checks (not recommended): `--skip-checks`

## Project layout

```
blink_core/          platform-independent business logic
  detector.py        BlinkDetector: landmarks -> signals -> blink events
  screentime.py      daily screen-time tracker (persists across restarts)
app/
  main.py            live app (statistics-only UI)
  overlay.py         stats card + logo + help bar rendering
  beeper.py          cross-platform beep
models/
  face_landmarker.task   MediaPipe model (Apache 2.0, bundled)
assets/fonts/        Inter typeface (SIL OFL)
tools/               signal analysis helpers (optional)
```

## Licenses (all open source)

- MediaPipe + face_landmarker model: Apache 2.0
- OpenCV: Apache 2.0 · NumPy: BSD · Pillow: HPND
- Inter font: SIL Open Font License 1.1
- Test clip (if present): public domain

## Design notes (this edition)

- Video preview, landmark mesh overlay and the related key toggles
  (V / M) have been removed entirely. The camera is used only for
  analysis; the UI is a fixed-size statistics card.
- Startup performs a quiet checklist of runtime, imaging stack, face
  engine, model file, fonts and camera without naming individual
  library packages. On failure the user is given a short troubleshooting
  list and the choice to exit or continue.
- Branding renamed from EyeCare to **EyeRhythm**. Logo uses the same
  blue / green / brown palette.
- Blink-detection reliability improvements (frontal-face gate, adaptive
  low-light CLAHE, glasses-aware threshold) live entirely inside
  `blink_core/detector.py` and require no UI or API changes.
