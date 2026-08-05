"""
Developer tool: dump per-frame eye-closure signals to a CSV file
================================================================

Plain-language goal
-------------------
When tuning blink thresholds, it helps to plot the raw signals over time:

* blendshape left / right
* fused blink score
* EAR average
* whether a face was found

This script runs the same ``BlinkDetector`` used by the app on a **video
file** (or camera index), and writes one CSV row per frame.

Usage
-----
From the project root::

    python tools/analyze_signals.py input.mp4 output.csv

Then open ``output.csv`` in a spreadsheet or plot it with Python.

This file is **not** part of the normal user experience; it is for
developers and researchers only.
"""

import sys
from pathlib import Path

import cv2

# Allow `from blink_core import ...` when running this file as a script
# (project root may not already be on PYTHONPATH).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blink_core import BlinkDetector

# Bundled MediaPipe model used by the real app.
MODEL = str(Path(__file__).resolve().parents[1] / "models" / "face_landmarker.task")

# Command-line: input video path, output CSV path.
src, dst = sys.argv[1], sys.argv[2]

# Open the video (or webcam if src is "0", etc. — OpenCV accepts both).
cap = cv2.VideoCapture(src)

# Frames per second of the source; default 30 if the file does not report it.
# We use fps to invent monotonically increasing timestamps in milliseconds.
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

# Same detector the live app uses.
det = BlinkDetector(MODEL)

# CSV header row (column names for the spreadsheet).
rows = ["t_s,blend_left,blend_right,blink_score,ear_avg,face"]

i = 0  # frame index
while True:
    ok, frame = cap.read()
    if not ok:
        # End of file (or camera failure) — stop the loop.
        break

    # Synthetic timestamp: frame_index / fps → seconds → milliseconds.
    # Must increase every frame for MediaPipe VIDEO mode.
    ts = int(i * 1000.0 / fps)

    # Run blink analysis on this frame.
    r = det.process_frame(frame, ts)

    # One CSV line: time and the main signals we care about for tuning.
    rows.append(
        f"{ts/1000:.3f},{r.blend_left:.3f},{r.blend_right:.3f},"
        f"{r.blink_score:.3f},{r.ear_avg:.3f},{int(r.face_found)}"
    )
    i += 1

# Free camera/model resources.
det.close()
cap.release()

# Write the whole CSV in one go.
Path(dst).write_text("\n".join(rows))
print(f"wrote {i} rows to {dst}")
