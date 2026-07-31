"""Dump per-frame eye-closure signals to CSV for threshold tuning."""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blink_core import BlinkDetector

MODEL = str(Path(__file__).resolve().parents[1] / "models" / "face_landmarker.task")

src, dst = sys.argv[1], sys.argv[2]
cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
det = BlinkDetector(MODEL)
rows = ["t_s,blend_left,blend_right,blink_score,ear_avg,face"]
i = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    ts = int(i * 1000.0 / fps)
    r = det.process_frame(frame, ts)
    rows.append(f"{ts/1000:.3f},{r.blend_left:.3f},{r.blend_right:.3f},"
                f"{r.blink_score:.3f},{r.ear_avg:.3f},{int(r.face_found)}")
    i += 1
det.close()
Path(dst).write_text("\n".join(rows))
print(f"wrote {i} rows to {dst}")
