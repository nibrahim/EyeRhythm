# EyesRhythm on Linux

Everything Linux-related lives in this folder. EyesRhythm runs from source in a desktop window. The window's web engine (Qt, through PySide6) installs from `pip`, so the steps are the same on GNOME, KDE and other desktops.

```
for_linux/
├── README.md              ← this file
├── setup.sh               ← one-time: create venv + install deps
├── run.sh                 ← launch the app from source
├── install_autostart.sh   ← open EyesRhythm automatically at login
├── uninstall_autostart.sh ← turn that off
└── start_at_login.sh      ← used by the login entry (do not run by hand)
```

## Requirements

- **Python 3.10, 3.11 or 3.12.** If you only have a newer Python, install [uv](https://docs.astral.sh/uv/) and `setup.sh` will use it to fetch 3.12.
- **Node.js 18+**, to build the dashboard once.
- A webcam your user can open. If it fails, check you are in the `video` group.
- About 1.3 GB of disk for the virtual environment, mostly Qt.
- Audio through `pw-play`, `paplay` or `aplay` for practice and blink beeps.

## Run

```bash
./for_linux/setup.sh
./for_linux/run.sh
```

If the window cannot open, the app logs why and opens your browser instead. You can also choose another way to run it:

```bash
./for_linux/run.sh --browser
./for_linux/run.sh --headless
```

`--browser` opens the dashboard in your browser, and `--headless` prints live numbers to the terminal. To use your own GTK install for the window, set `PYWEBVIEW_GUI=gtk`.

## Start at login

```bash
./for_linux/install_autostart.sh
./for_linux/uninstall_autostart.sh
```

This adds an entry to `~/.config/autostart`, which GNOME, KDE and most desktops read. Window managers such as i3 may not read it, so run `for_linux/start_at_login.sh` from your window manager's startup config instead. Logs go to `~/.local/state/EyesRhythm/EyesRhythm.log`.

## Differences from the Mac and Windows apps

- There is no prebuilt installer, and the Dock or taskbar icon does not change for alerts.
- Tiling window managers such as i3 control window size, so they may ignore the app's resizing and "On top".
- With `--browser`, the app cannot resize itself or stay on top, and browsers can block the Sound alert until you click or press a key on the page.
- The Visual alert is drawn in the window, so you will not see it while the window is hidden.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Window does not open and the browser does | Run from a terminal and read the log. Qt may need a system library such as `libxcb-cursor0` |
| Status says `reconnecting…` | Open the camera shutter if your laptop has one, and close other apps using the camera |
| Numpy fails to install | You are on Python 3.13 or newer. Delete `EyeRhythm/` and rerun `setup.sh` with Python 3.12 or uv installed |
| Port 8742 is in use | Another copy is running. `run.sh` stops it, or pass `--port` |
