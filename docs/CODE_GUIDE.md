# EyeRhythm — Code Guide

How the project fits together after the React UI rewrite.

---

## What the product does

1. Opens the **webcam** in the background  
2. Detects **face + blinks** (MediaPipe)  
3. Shows a **React dashboard** in a compact desktop window  
4. Optionally **beeps** on blinks or very low rate  
5. Saves **today’s** blink count and face-time to a local JSON file  

Nothing is uploaded. Privacy is by design. Camera preview is collapsed by default.

---

## Big picture

```
┌─────────────────────────────────────────────────────────────┐
│  frontend/          React (Vite + TypeScript)               │
│  - dashboard, cards, camera panel, toggles                  │
│  - talks to local API over WebSocket / HTTP                 │
└──────────────────────────────┬──────────────────────────────┘
                               │  ws://127.0.0.1:8742
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  app/               “shell + hands”                         │
│  - main.py      process entry, pywebview window             │
│  - server.py    FastAPI REST + WebSocket                    │
│  - engine.py    camera loop, toggles, snapshot              │
│  - regularity.py  CV-based regularity score                 │
│  - beeper.py    OS-native short sounds                      │
└──────────────────────────────┬──────────────────────────────┘
                               │ uses
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  blink_core/        “brain” (unchanged science)             │
│  - detector.py      blink state machine                     │
│  - screentime.py    daily diary on disk                     │
└─────────────────────────────────────────────────────────────┘
```

| Path | Role |
|------|------|
| `app/main.py` | Start engine + HTTP + desktop window |
| `app/engine.py` | Camera, detector, stats, beeps/alerts |
| `app/server.py` | Local API for the UI |
| `app/regularity.py` | Inter-blink CV → score 0–100 |
| `app/beeper.py` | Sounds |
| `blink_core/detector.py` | Blink detection |
| `blink_core/screentime.py` | Daily totals |
| `frontend/` | React source |
| `frontend/dist/` | Built UI (served in production) |
| `run_app.py` | Packaging entry + crash log |

---

## Life of one frame

```
Webcam frame
    → EyeRhythmEngine (background thread)
    → BlinkDetector.process_frame()
    → ScreenTimeTracker + RegularityTracker
    → EngineSnapshot (thread-safe)
    → WebSocket /api clients (~10 Hz)
    → React re-renders metric cards
```

Optional camera panel: engine encodes low-res JPEG only while the panel is open.

---

## Regularity score

```
CV = stdev(inter-blink gaps) / mean(gaps)
Score = max(0, 100 − 100 × CV)
```

Needs a few recent blinks before the UI shows a number.

---

## Daily stats file

Path: `~/.eyerhythm_blinkcounter/screentime.json`

```json
{ "date": "2026-08-01", "seconds": 3600.0, "blinks": 420 }
```

Resets at local midnight.

---

## UI shortcuts

| Key | Effect |
|-----|--------|
| B | Toggle beep on each counted blink |
| A | Toggle low-rate alert |
| T | Toggle always-on-top (desktop window) |
| C | Expand / collapse camera panel |

---

## How to run (developers)

```bash
# Python
./for_mac/setup.sh          # or venv + pip install -r requirements.txt
./for_mac/run.sh

# UI only (hot reload) — terminal 1:
python -m app.main --browser
# terminal 2:
cd frontend && npm install && npm run dev
```

Useful flags:

* `--camera 1` — second webcam  
* `--browser` — system browser instead of pywebview  
* `--port 8742` — local API port  
* `--skip-checks` — skip startup dependency checks  

---

## What stayed the same

* `blink_core` detection math and thresholds  
* Daily screen-time / blink persistence  
* Beep + low-rate alert behaviour  
* Camera reconnect after sleep/wake  
* Offline-only design  

## What changed

* OpenCV/Pillow stats card **removed**  
* UI is React; window is pywebview (browser fallback)  
* Live metrics stream over WebSocket  

---

*EyeRhythm is free and open source. Take care of your eyes.*
