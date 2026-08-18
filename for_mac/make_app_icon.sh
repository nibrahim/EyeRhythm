#!/bin/bash
# =============================================================================
# Build a transparent-background app icon from the square brand mark
# (assets/logo.svg geometry) → PNG + .icns + .ico
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PNG="$ROOT/assets/app_icon.png"
ICNS="$ROOT/assets/EyeRhythm.icns"
ICO="$ROOT/assets/EyeRhythm.ico"

PYTHON=""
if [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/EyeRhythm/bin/python" ]; then
    PYTHON="$ROOT/EyeRhythm/bin/python"
else
    PYTHON="$(command -v python3)"
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

"$PYTHON" - "$PNG" "$ICO" "$TMP/EyeRhythm.iconset" <<'PY'
"""Rasterize the EyeRhythm mark with a real alpha channel (no white plate)."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

png_path = Path(sys.argv[1])
ico_path = Path(sys.argv[2])
iconset = Path(sys.argv[3])
iconset.mkdir(parents=True, exist_ok=True)


def render(size: int) -> Image.Image:
    # Draw at 2× then downscale so the rounded corners stay smooth.
    hi = max(size * 2, 256)
    f = hi / 128.0
    im = Image.new("RGBA", (hi, hi), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle(
        [4 * f, 4 * f, 124 * f, 124 * f],
        radius=36 * f,
        fill=(91, 159, 224, 255),
    )
    cx, cy, rx, ry = 64 * f, 64 * f, 40 * f, 25 * f
    d.ellipse(
        [cx - rx, cy - ry, cx + rx, cy + ry],
        fill=(255, 255, 255, 36),
    )
    d.ellipse(
        [cx - rx, cy - ry, cx + rx, cy + ry],
        outline=(255, 255, 255, 255),
        width=max(1, round(5 * f)),
    )
    r = 14.5 * f
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(232, 242, 250, 255))
    r2 = 6.2 * f
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=(26, 42, 56, 255))
    hx, hy, hr = 68.5 * f, 59.5 * f, 3 * f
    d.ellipse(
        [hx - hr, hy - hr, hx + hr, hy + hr],
        fill=(255, 255, 255, 230),
    )
    if hi != size:
        im = im.resize((size, size), Image.Resampling.LANCZOS)
    return im


master = render(1024)
master.save(png_path)

sizes = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}
for name, px in sizes.items():
    render(px).save(iconset / name)

master.save(
    ico_path,
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print(f"Wrote {png_path}")
print(f"Wrote {ico_path}")
PY

iconutil -c icns "$TMP/EyeRhythm.iconset" -o "$ICNS"
echo "Wrote $ICNS"
