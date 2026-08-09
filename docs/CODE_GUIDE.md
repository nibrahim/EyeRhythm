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
│  - interblink_hours.py  research: IBI stats per screen hour │
└─────────────────────────────────────────────────────────────┘
```

| Path | Role |
|------|------|
| `app/main.py` | Start engine + HTTP + desktop window |
| `app/engine.py` | Camera, detector, stats, beeps/alerts |
| `app/frame_pacer.py` | Adaptive FPS: 30 face / post-blink sleep / 1 no-face |
| `app/server.py` | Local API for the UI |
| `app/regularity.py` | Inter-blink CV → score 0–100 |
| `app/beeper.py` | Sounds |
| `blink_core/detector.py` | Blink detection |
| `blink_core/screentime.py` | Daily totals |
| `blink_core/interblink_hours.py` | Per screen-hour inter-blink research JSON |
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

## Inter-blink research log (per screen-time hour)

Path: `~/.eyerhythm_blinkcounter/interblink_hours.json`

Each **hour of face-present screen time** (not wall-clock hour) gets one
entry with inter-blink interval stats. Example: **6 h 45 m** screen time →
**7 entries** for that date (6 complete hours + 1 partial).

```json
{
  "version": 1,
  "records": [
    {
      "date": "2026-04-05",
      "hour_index": 1,
      "start_time": "2026-04-05T09:15:22",
      "end_time": "2026-04-05T10:40:11",
      "screen_seconds": 3600.0,
      "blink_count": 420,
      "gap_count": 419,
      "min_s": 0.42,
      "max_s": 18.3,
      "mean_s": 3.15,
      "median_s": 2.88,
      "complete": true
    }
  ]
}
```

Gaps longer than 30 s (or under 0.15 s) are ignored as breaks/noise.
History is kept across days in the same file.

---

## Practice mode (full-screen coach)

1. User toggles **Practice** → engine enters `countdown` for **20 s**.
2. React opens a dark full-screen overlay with instructions + countdown.
3. Desktop shell may expand the window (`set_practice_fullscreen` bridge).
4. Countdown ends → `active` for **120 s**: beeps every **3 s** (at the *end*
   of each interval) and a ball+string animation that arrives on each beep.
5. Path cycle: center → top-left → bottom-left → bottom-right → top-right →
   spiral back to center (then repeat).
6. Esc or **End practice** stops early; natural end clears the toggle.

Tunables in `app/engine.py`: `PRACTICE_COUNTDOWN_S`, `PRACTICE_INTERVAL_S`,
`PRACTICE_DURATION_S`. Animation lives in `frontend/src/components/PracticeScreen.tsx`.

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
