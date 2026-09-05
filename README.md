# EyesRhythm — Blink companion

**Your eyes work hard for you. EyesRhythm helps them work longer.**

Every day millions of knowledge workers, students and creators spend hours staring at screens. Research from the American Academy of Ophthalmology shows that the spontaneous blink rate drops by **half or more** during computer use. Fewer blinks → dry eyes, fatigue, blurred vision, and the classic symptoms of Computer Vision Syndrome.

EyesRhythm is a lightweight, **on-device** companion that quietly watches your blink rate through the built-in webcam and gently nudges you back toward a healthy rhythm (~15–20 blinks per minute). No accounts, no cloud, no analytics, no video ever leaves your machine.

Official **macOS and Windows** copies are sold as a one-time license at [eyesrhythm.com](https://eyesrhythm.com). After payment, Dodo Payments emails a unique key. Packaged builds ask for that key on first launch (internet once). After that the app stays offline.

The source in this tree is MIT-licensed: you may use, modify, and share it under `LICENSE`, provided you keep the copyright notice and the third-party notices in `THIRD_PARTY_NOTICES.md`. Selling a packaged copy does not re-license MediaPipe, OpenCV, FFmpeg, or the other libraries listed there.

> **Privacy first.** After activation, EyesRhythm runs offline. Camera frames are not uploaded. Local JSON under `~/.eyerhythm_blinkcounter/` holds today’s blink count and screen-time minutes (resets at midnight), plus an optional research log of inter-blink interval stats per screen-time hour. The license file in that same folder is the only record of activation.

---

## What you see

A compact **React dashboard** (not full-screen by default):

| Element | Meaning |
|--------|---------|
| **Live blink rate** | Continuous blinks/min over the recent window |
| **Average rate** | Daily average = total blinks ÷ face-time minutes |
| **Screen time** | How long a face has been in front of the screen today |
| **FPS** | Camera pipeline throughput |
| **Regularity** | How steady your inter-blink gaps are (0–100) |
| **Reserved cards** | Placeholders for future metrics |
| **Camera panel** | Collapsed by default; expand when you want a preview |

Regularity is computed as:

```text
CV = (std of inter-blink gaps) ÷ (mean gap)
Score = max(0, 100 − 100 × CV)
```

---

## Quick start

### Prerequisites

* **Python 3.10–3.12** (3.11 recommended)  
* **Node.js 18+** (to build the UI once)  
* Webcam + OS camera permission  

### macOS / Linux

```bash
./for_mac/setup.sh                 # venv + Python deps + React build
./for_mac/run.sh                   # launches the desktop window
./for_mac/install_autostart.sh     # optional: open at every login
```

First launch: allow **Camera** permission  
(System Settings → Privacy & Security → Camera).

To stop opening at login: `./for_mac/uninstall_autostart.sh`.

### Windows

Share **`EyesRhythm-Windows.zip`** (built by GitHub Actions or `for_windows/for_developers/build_exe.bat`). Recipients unzip and double-click `EyesRhythm.exe` — no Python or Node.

All Windows helpers live under **[`for_windows/`](for_windows/)**.

* **Share / use the app** → unzip `EyesRhythm-Windows.zip` and run `EyesRhythm.exe`. Details in [`for_windows/`](for_windows/).
* **From source** → [`for_windows/just_use_for_nondevelopers/`](for_windows/just_use_for_nondevelopers/) (needs Python once).
* **Rebuild the zip / installer** → [`for_windows/for_developers/`](for_windows/for_developers/) or **Actions → Build Windows app**.

### Developer (UI hot reload)

```bash
# Terminal 1 — engine + API
source EyeRhythm/bin/activate   # or your venv
python -m app.main --browser

# Terminal 2 — Vite
cd frontend && npm install && npm run dev
```

Open the Vite URL (proxies `/api` and `/ws` to the Python server).

---

## Keyboard shortcuts (dashboard focused)

| Key | Action |
|-----|--------|
| **B** | Toggle beep on every counted blink |
| **A** | Toggle alert (beeps after ORI is below 50 for 3 min in the last 5 min) |
| **D** | More / Less (compact companion vs full dashboard) |
| **W** | Settings / Hide settings (Reports beside the companion) |
| **C** | Switch Lens camera preview |

Close the window to quit (or Ctrl+C in browser mode).

---

## Architecture

* **`blink_core/`** — blink detection + daily stats (platform-independent)  
* **`app/`** — camera engine, local FastAPI server, desktop window  
* **`frontend/`** — React + TypeScript + Vite UI  

The default window is small and resizable. Maximising scales typography and layout with the viewport. Works on **macOS and Windows** (Linux supported via browser or pywebview).

---

## Libraries and licenses

All runtime libraries used here allow commercial distribution of a packaged
app. None of them require EyesRhythm’s own source to be published.

See **[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)** (also in
Settings → About, and inside every freeze). Full texts live in `licenses/`.

| Component | License | In the sold app |
|-----------|---------|-----------------|
| EyesRhythm source | MIT | Yes |
| MediaPipe + Face Landmarker model | Apache 2.0 | Yes |
| OpenCV | Apache 2.0 | Yes |
| FFmpeg (inside the OpenCV wheel) | LGPLv2.1 | Yes — replaceable library, notice required |
| NumPy | BSD-3-Clause | Yes |
| FastAPI, Pydantic, React, Vite | MIT | Yes |
| Uvicorn, pywebview | BSD-3-Clause | Yes |
| Inter font | SIL OFL 1.1 | Bundled with the app, not sold alone |
| PyInstaller | GPL-2.0 with freeze exception | Build tool only |

Packaged copies include `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `licenses/`.
FFmpeg remains a separate shared library (typically
`opencv_videoio_ffmpeg*.dll` on Windows) so it can be substituted, as LGPL
asks.

The alert tone (`alert.wav`) and Practice lines (`quotes.json`) are original
EyesRhythm work.

---

## Project layout

```
EyeRhythm/
├── app/                 # engine + local API + window
├── blink_core/          # blink detection & screen-time
├── frontend/            # React UI (source + dist/)
├── models/              # MediaPipe face landmarker
├── assets/              # logo + brand assets + Inter (OFL)
├── licenses/            # Apache 2.0, LGPLv2.1, SIL OFL texts
├── THIRD_PARTY_NOTICES.md
├── docs/CODE_GUIDE.md   # map of the codebase
├── for_mac/             # setup / run / login-start helpers
├── for_windows/         # launchers + packaging
├── requirements.txt
└── run_app.py           # packaging entry-point
```

### Contributors

Start with **[`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md)**, then `app/engine.py` and `blink_core/detector.py`.

---

## Feedback & sharing

If the counter feels off for you, or you have ideas for the reserved metric cards, please write to [hello@eyesrhythm.com](mailto:hello@eyesrhythm.com). If EyesRhythm is useful, share it — a regular blink habit is one of the easiest gifts we can give our eyes.

EyesRhythm is a wellness companion, not a medical device. It is not intended to diagnose, treat, cure, or prevent disease.

Official copies: [eyesrhythm.com](https://eyesrhythm.com). Source terms: [`LICENSE`](LICENSE). Third-party terms: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
