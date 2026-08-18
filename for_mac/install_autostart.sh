#!/bin/bash
# =============================================================================
# EyeRhythm — start automatically when you log in to this Mac
# =============================================================================
#
# Installs a per-user Launch Agent that opens the EyeRhythm window at login.
# No Terminal window is shown.
#
#   ./for_mac/install_autostart.sh
#   ./for_mac/uninstall_autostart.sh
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LABEL="com.eyerhythm.app"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST="${AGENTS_DIR}/${LABEL}.plist"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}/${LABEL}"

if [ ! -x "$SCRIPT_DIR/run.sh" ]; then
    echo "ERROR: $SCRIPT_DIR/run.sh is missing or not executable."
    exit 1
fi

if [ ! -d "$ROOT/.venv" ] && [ ! -d "$ROOT/EyeRhythm" ]; then
    echo "ERROR: No virtual environment found (.venv/ or EyeRhythm/)."
    echo "Run setup first:  ./for_mac/setup.sh"
    exit 1
fi

if [ ! -f "$ROOT/frontend/dist/index.html" ]; then
    echo "WARNING: frontend/dist is missing. Building it once so login start can succeed…"
    if ! command -v npm >/dev/null 2>&1; then
        echo "ERROR: npm is not installed. Install Node.js, then:  cd frontend && npm install && npm run build"
        exit 1
    fi
    (cd "$ROOT/frontend" && npm install && npm run build)
fi

chmod +x "$SCRIPT_DIR/start_at_login.sh" "$SCRIPT_DIR/run.sh"
mkdir -p "$AGENTS_DIR" "${HOME}/Library/Logs"

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/start_at_login.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/EyeRhythm.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/EyeRhythm.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>LANG</key>
        <string>en_US.UTF-8</string>
    </dict>
</dict>
</plist>
EOF

# Replace any previous agent, then load the new one (macOS 13+ API, with fallback).
if launchctl print "$DOMAIN" >/dev/null 2>&1; then
    launchctl bootout "gui/${UID_NUM}" "$PLIST" >/dev/null 2>&1 || \
        launchctl bootout "$DOMAIN" >/dev/null 2>&1 || true
fi
if ! launchctl bootstrap "gui/${UID_NUM}" "$PLIST" 2>/dev/null; then
    launchctl unload "$PLIST" >/dev/null 2>&1 || true
    launchctl load "$PLIST"
fi

echo
echo "=============================================="
echo "  EyeRhythm will now open when you log in."
echo
echo "  Agent:  ${PLIST}"
echo "  Logs:   ~/Library/Logs/EyeRhythm.log"
echo
echo "  If macOS asks to allow EyeRhythm in the"
echo "  background, choose Allow."
echo "  (System Settings → General → Login Items)"
echo
echo "  First camera prompt: Allow, then it is remembered."
echo
echo "  Stop auto-start:  ./for_mac/uninstall_autostart.sh"
echo "=============================================="
echo
echo "Opening EyeRhythm now so you can confirm it works…"
# RunAtLoad starts the agent on bootstrap. Do not kickstart -k — that would
# kill the first launch and start a second one.
