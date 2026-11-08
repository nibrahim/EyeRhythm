# EyesRhythm on Linux

Everything Linux-related lives in this folder. EyesRhythm runs from source and shows its dashboard in your browser, so it needs no desktop-specific packages.

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

## Run

```bash
./for_linux/setup.sh
./for_linux/run.sh
```

To skip the dashboard and print live numbers in the terminal instead:

```bash
EyeRhythm/bin/python -m app.main --headless
```

## Start at login

```bash
./for_linux/install_autostart.sh
./for_linux/uninstall_autostart.sh
```

This adds an entry to `~/.config/autostart`, which GNOME, KDE and most desktops read. Window managers such as i3 may not read it, so run `for_linux/start_at_login.sh` from your window manager's startup config instead. Logs go to `~/.local/state/EyesRhythm/EyesRhythm.log`.

## Differences from the Mac and Windows apps

- There is no native window, so the app cannot resize itself, stay on top, or change a Dock or taskbar icon.
- Browsers can block sound until you click or press a key on the page, so the Sound alert may stay silent in a freshly opened tab.
- The Visual alert is drawn in the page, so you will not see it while the tab is hidden.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Status says `reconnecting…` | Open the camera shutter if your laptop has one, and close other apps using the camera |
| Numpy fails to install | You are on Python 3.13 or newer. Delete `EyeRhythm/` and rerun `setup.sh` with Python 3.12 or uv installed |
| Port 8742 is in use | Another copy is running. `run.sh` stops it, or pass `--port` |
