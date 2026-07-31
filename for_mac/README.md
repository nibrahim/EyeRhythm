# EyeRhythm on macOS / Linux

Everything you need to run EyeRhythm from source is in the parent folder.  
This `for_mac/` directory only holds the helper scripts and a short guide.

## 1. Install Python

You need **Python 3.10, 3.11 or 3.12**.

- Download the official installer: https://www.python.org/downloads/  
  (or with Homebrew: `brew install python@3.11`)

Verify:

```bash
python3 --version
# should print something like Python 3.11.x
```

## 2. One-time setup

Open Terminal, go to the **project root** (the folder that contains `app/`, `requirements.txt`, etc.):

```bash
cd /path/to/EyeRhythm

# Create the virtual environment named exactly “EyeRhythm”
python3 -m venv EyeRhythm
source EyeRhythm/bin/activate

# Install the four open-source libraries
pip install -r requirements.txt
```

Or simply run the helper:

```bash
./for_mac/setup.sh
```

## 3. Run the app

```bash
source EyeRhythm/bin/activate   # if not already active
python -m app.main
```

or the convenience script from the project root:

```bash
./run_mac.sh
```

or from this folder:

```bash
./for_mac/run.sh
```

### Camera permission

The first time you launch, macOS will ask for camera access.  
**Allow** it. You can later manage the permission under:

**System Settings → Privacy & Security → Camera**

Allow both **Terminal** (or your IDE) and, if you later build an `.app`, **EyeRhythm**.

### Wrong camera?

```bash
python -m app.main --camera 1
```

### Skip the startup self-check (not recommended)

```bash
python -m app.main --skip-checks
```

## 4. Keys while the app is running

| Key | Action |
|-----|--------|
| Q / Esc | Quit |
| B | Beep on every blink ON/OFF |
| A | Low-rate alert ON/OFF |
| T | Always-on-top ON/OFF |

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| “No module named mediapipe” | Make sure the `EyeRhythm` venv is activated and `pip install -r requirements.txt` succeeded |
| Black / no camera | Close Zoom, Teams, browser tabs that use the webcam; check System Settings → Camera |
| “Model file not found” | Confirm `models/face_landmarker.task` exists (≈ 3.7 MB) |
| App starts then immediately exits | Look for a crash log at `~/Library/Logs/EyeRhythm_crash.log` |

## Building a standalone .app (optional)

If you want a double-clickable Mac application (no Terminal needed):

```bash
source EyeRhythm/bin/activate
pip install pyinstaller
./build_mac.sh
```

The result appears under `dist/`.  
(Advanced signing / notarization is outside the scope of this open-source edition.)

---

That’s everything required to run EyeRhythm on a Mac or Linux machine.
