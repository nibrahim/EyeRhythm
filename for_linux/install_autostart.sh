#!/bin/bash
# =============================================================================
# EyesRhythm — start automatically when you log in to this desktop
# =============================================================================
#
# Installs an XDG autostart entry, which GNOME, KDE and most desktops read.
#
#   ./for_linux/install_autostart.sh
#   ./for_linux/uninstall_autostart.sh
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
ENTRY="${AUTOSTART_DIR}/eyesrhythm.desktop"

if [ ! -d "$ROOT/.venv" ] && [ ! -d "$ROOT/EyeRhythm" ]; then
    echo "ERROR: No virtual environment found (.venv/ or EyeRhythm/)."
    echo "Run setup first:  ./for_linux/setup.sh"
    exit 1
fi

if [ ! -f "$ROOT/frontend/dist/index.html" ]; then
    echo "ERROR: The React UI is not built. Run setup first:  ./for_linux/setup.sh"
    exit 1
fi

mkdir -p "$AUTOSTART_DIR"

cat >"$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=EyesRhythm
Comment=Blink companion
Exec="${SCRIPT_DIR}/start_at_login.sh"
Icon=${ROOT}/assets/app_icon.png
Terminal=false
EOF

echo
echo "=============================================="
echo "  EyesRhythm will now open when you log in."
echo
echo "  Entry:  ${ENTRY}"
echo "  Logs:   ${XDG_STATE_HOME:-$HOME/.local/state}/EyesRhythm/EyesRhythm.log"
echo
echo "  Window managers such as i3 may not read this"
echo "  folder. Add the start_at_login.sh script to"
echo "  your window manager's startup config instead."
echo
echo "  Stop auto-start:  ./for_linux/uninstall_autostart.sh"
echo "=============================================="
