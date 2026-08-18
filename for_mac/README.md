# EyeRhythm on macOS / Linux

Everything Mac/Linux-related lives in this folder.

```
for_mac/
├── README.md              ← this file
├── setup.sh               ← one-time: create venv + install deps
├── run.sh                 ← launch the app from source
├── install_autostart.sh   ← open EyeRhythm automatically at login
├── uninstall_autostart.sh ← turn that off
├── start_at_login.sh      ← used by the login item (do not run by hand)
└── build_mac.sh           ← optional: build a standalone .app
```

---

## 1. Install Python

You need **Python 3.10, 3.11 or 3.12**.

- Official installer: https://www.python.org/downloads/  
- or Homebrew: `brew install python@3.11`

```bash
python3 --version
# should print something like Python 3.11.x
```

---

## 2. One-time setup

Open Terminal and go to the **project root** (the folder that contains `app/`, `requirements.txt`, `run_app.py`, etc.):

```bash
cd /path/to/EyeRhythm
./for_mac/setup.sh
```

This creates a virtual environment named exactly **`EyeRhythm`** and installs the required libraries.

(You can also do it manually: `python3 -m venv EyeRhythm && source EyeRhythm/bin/activate && pip install -r requirements.txt`.)

---

## 3. Run the app

```bash
./for_mac/run.sh
```

or:

```bash
source EyeRhythm/bin/activate
python -m app.main
```

### Camera permission

The first time you launch, macOS will ask for camera access → **Allow**.  
You can manage it later under:

**System Settings → Privacy & Security → Camera**

### Start automatically when you turn the Mac on

```bash
./for_mac/install_autostart.sh
```

This registers a per-user Launch Agent. After you log in (or restart), the EyeRhythm window opens on its own — no Terminal needed. macOS may ask once to allow EyeRhythm in the background; choose **Allow** (System Settings → General → Login Items).

Turn it off with:

```bash
./for_mac/uninstall_autostart.sh
```

If you move the project folder, run `install_autostart.sh` again so the login item points at the new path.

Logs land in `~/Library/Logs/EyeRhythm.log`.

### Useful flags

```bash
python -m app.main --camera 1          # try a different webcam
python -m app.main --skip-checks       # skip the startup self-check
```

---

## 4. Keyboard shortcuts

| Key       | Action                          |
|-----------|---------------------------------|
| Q / Esc   | Quit                            |
| B         | Beep on every blink ON/OFF      |
| A         | Low-rate alert ON/OFF           |
| T         | Always-on-top ON/OFF            |
| D         | More / Less (compact window)    |

---

## 5. Build a standalone .app (optional)

If you want a double-clickable Mac application (no Terminal needed):

```bash
./for_mac/build_mac.sh
```

The script builds the app icon from `assets/logo.svg`, stamps the camera permission key, and writes `dist/EyeRhythm.app`.

### After you change the code

You must rebuild. Editing Python / React files does **not** update an already-built `.app`.

1. Save your code changes.
2. If you changed the React UI (`frontend/src/…`), rebuild it first:

   ```bash
   cd frontend && npm run build && cd ..
   ```

   (`build_mac.sh` also does this if `frontend/dist` is missing, but not if it is merely stale.)
3. Rebuild the app (this replaces `dist/EyeRhythm.app`):

   ```bash
   ./for_mac/build_mac.sh
   ```
4. Double-click `dist/EyeRhythm.app` and confirm it works.
5. Right-click `EyeRhythm.app` → **Compress**, and send only that zip.

Do not send the project folder, `build/`, or `.venv`.

(Advanced code-signing / notarization is outside the scope of this open-source edition.)

---

## Troubleshooting

| Symptom                         | What to try |
|---------------------------------|-------------|
| “No module named mediapipe”     | Make sure the `EyeRhythm` venv is activated and `pip install -r requirements.txt` succeeded |
| Black / no camera               | Close Zoom, Teams, browser tabs that use the webcam; check System Settings → Camera |
| “Model file not found”          | Confirm `models/face_landmarker.task` exists (≈ 3.7 MB) |
| App starts then immediately exits | Look for a crash log at `~/Library/Logs/EyeRhythm_crash.log` |
| Double-click `.app` shows Retry / Ignore / Report | The bundle was missing `NSCameraUsageDescription`. Rebuild with `./for_mac/build_mac.sh` (the script now stamps the camera privacy key). |

That’s everything required to run EyeRhythm on a Mac or Linux machine.
