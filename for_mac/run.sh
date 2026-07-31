#!/bin/bash
# Run EyeRhythm from source (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [ ! -d EyeRhythm ]; then
    echo "No 'EyeRhythm' virtual environment found."
    echo "Run setup first:  ./for_mac/setup.sh"
    exit 1
fi

# shellcheck disable=SC1091
source EyeRhythm/bin/activate

echo "EyeRhythm  ·  $(pwd)"
echo "Keys: Q quit  ·  B beep  ·  A alert  ·  T on-top"
echo

exec python -m app.main "$@"
