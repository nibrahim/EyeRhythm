#!/bin/bash
# Launch EyeRhythm on macOS / Linux (creates venv named "EyeRhythm" on first run)
cd "$(dirname "$0")"
if [ ! -d EyeRhythm ]; then
    echo "Creating virtual environment 'EyeRhythm'..."
    python3 -m venv EyeRhythm
    source EyeRhythm/bin/activate
    pip install -r requirements.txt
else
    source EyeRhythm/bin/activate
fi
python3 -m app.main "$@"
