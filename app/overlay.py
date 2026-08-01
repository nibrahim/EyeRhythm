"""
EyeRhythm - BlinkCounter overlay (open-source edition).

Rendered with PIL + the bundled Inter typeface (SIL OFL license) for
crisp, modern typography. Brand theme: blue / green / brown.

This edition shows only the statistics card — no video feed is ever
displayed. The info card and help bar are re-rendered only when a
displayed value changes; otherwise cached bitmaps are pasted.

Visual style matches the polished floating-card mockup:
  - smaller chip logo
  - large rounded outer shell
  - filled status pill
  - side-by-side screen-time / avg row
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _resource_root():
    import sys
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


FONT_DIR = _resource_root() / "assets" / "fonts"

# ------------------------------------------------------- brand palette (RGB)
BLUE = (86, 148, 217, 255)       # primary brand
GREEN = (86, 204, 145, 255)      # healthy / eyes open
BROWN = (176, 138, 102, 255)     # warm secondary text
DARK_BROWN = (52, 38, 28, 255)
BG = (28, 32, 40, 255)           # main card fill
BG_SOFT = (36, 40, 48, 230)      # logo chip / help bar
FG = (243, 240, 235, 255)        # primary text (warm white)
WARN = (245, 158, 66, 255)       # amber - low blink rate
DANGER = (239, 83, 80, 255)      # red - eyes closed
OUTER_BG = (12, 14, 18)          # canvas outside the floating card
PILL_FG = (18, 22, 28, 255)      # text on filled green pill

HEALTHY_MIN, HEALTHY_MAX = 15, 20


class _Fonts:
    _cache: dict = {}

    @classmethod
    def get(cls, size: int, weight: str = "Regular"):
        key = (size, weight)
        if key not in cls._cache:
            try:
                cls._cache[key] = ImageFont.truetype(
                    str(FONT_DIR / f"Inter-{weight}.ttf"), size,
                    layout_engine=ImageFont.Layout.BASIC)
            except OSError:
                cls._cache[key] = ImageFont.load_default(size)
        return cls._cache[key]


def _paste_rgba(canvas: np.ndarray, rgba: Image.Image, x: int, y: int) -> None:
    """Alpha-composite a small RGBA image onto a BGR canvas region."""
    h, w = canvas.shape[:2]
    pw, ph = rgba.size
    x, y = max(0, x), max(0, y)
    pw, ph = min(pw, w - x), min(ph, h - y)
    if pw <= 0 or ph <= 0:
        return
    region = canvas[y:y + ph, x:x + pw]
    fg = np.asarray(rgba, dtype=np.float32)[:ph, :pw]
    alpha = (fg[:, :, 3:4]) / 255.0
    fg_bgr = fg[:, :, [2, 1, 0]]
    region[:] = (fg_bgr * alpha
                 + region.astype(np.float32) * (1.0 - alpha)).astype(np.uint8)


def _rate_color(bpm: float, face_found: bool = True):
    if not face_found and bpm <= 0:
        return BROWN
    if bpm >= HEALTHY_MIN:
        return GREEN
    if bpm >= 8:
        return WARN
    return DANGER


# ================================================================= renderers

def _render_logo(S) -> Image.Image:
    """Compact chip logo: rounded plate + stylised eye + EyeRhythm wordmark."""
    f_logo = _Fonts.get(S(15), "Bold")
    meas = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tw_eye = meas.textlength("Eye", font=f_logo)
    tw_rhythm = meas.textlength("Rhythm", font=f_logo)

    icon = S(28)
    pad_x = S(12)
    gap = S(8)
    w = int(pad_x + icon + gap + tw_eye + tw_rhythm + pad_x)
    h = S(40)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=S(12), fill=BG_SOFT)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=S(12),
                        outline=(60, 68, 80, 180), width=1)

    cy = h // 2
    ex0 = pad_x
    ex1 = pad_x + icon
    d.ellipse([ex0, cy - S(8), ex1, cy + S(8)], outline=BROWN, width=S(2))
    cxi = (ex0 + ex1) // 2
    d.ellipse([cxi - S(6), cy - S(6), cxi + S(6), cy + S(6)], fill=BLUE)
    d.ellipse([cxi - S(2), cy - S(2), cxi + S(2), cy + S(2)],
              fill=DARK_BROWN)
    d.ellipse([cxi + S(1), cy - S(4), cxi + S(3), cy - S(1)],
              fill=(255, 255, 255, 220))
    d.arc([cxi - S(7), cy - S(7), cxi + S(7), cy + S(7)],
          start=300, end=60, fill=GREEN, width=S(2))

    ty = cy - S(9)
    tx = ex1 + gap
    d.text((tx, ty), "Eye", font=f_logo, fill=BLUE)
    d.text((tx + tw_eye, ty), "Rhythm", font=f_logo, fill=GREEN)
    return img


def _render_card(res, fps_txt, screen_time, avg_bpm, total_blinks, S) -> Image.Image:
    f_count = _Fonts.get(S(56), "Bold")
    f_label = _Fonts.get(S(13), "Regular")
    f_state = _Fonts.get(S(13), "SemiBold")
    f_note = _Fonts.get(S(12), "Regular")
    f_row = _Fonts.get(S(13), "Regular")

    pad = S(20)
    note_txt = (f"Healthy: {HEALTHY_MIN}-{HEALTHY_MAX} blinks/min "
                "- blink more on screens")
    meas = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    card_w = max(S(340), int(meas.textlength(note_txt, font=f_note)) + 2 * pad)
    card_h = S(210)

    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)

    d.rounded_rectangle([0, 0, card_w - 1, card_h - 1],
                        radius=S(18), fill=BG)
    d.rounded_rectangle([0, 0, S(5), card_h - 1], radius=S(2), fill=BLUE)

    cx, cy = pad, S(16)

    count_val = total_blinks if total_blinks is not None else res.blink_count
    d.text((cx, cy), str(count_val), font=f_count, fill=FG)
    d.text((cx + S(4), cy + S(58)), "blinks today",
           font=f_label, fill=BROWN)

    if res.face_found:
        pill_txt = "EYES CLOSED" if res.eyes_closed else "EYES OPEN"
        pill_bg = DANGER if res.eyes_closed else GREEN
        pill_fg = FG if res.eyes_closed else PILL_FG
    else:
        pill_txt, pill_bg, pill_fg = "NO FACE", BROWN, FG

    pw = d.textlength(pill_txt, font=f_state) + S(28)
    px = card_w - pad - pw
    py = cy + S(14)
    d.rounded_rectangle([px, py, px + pw, py + S(28)],
                        radius=S(14), fill=pill_bg)
    d.ellipse([px + S(10), py + S(9), px + S(18), py + S(17)], fill=pill_fg)
    d.text((px + S(22), py + S(5)), pill_txt, font=f_state, fill=pill_fg)

    cy += S(82)

    bpm = res.blinks_per_minute
    bpm_col = _rate_color(bpm, res.face_found)
    d.ellipse([cx, cy + S(4), cx + S(10), cy + S(14)], fill=bpm_col)
    rate_txt = f"{bpm:.0f} blinks/min"
    d.text((cx + S(16), cy), rate_txt, font=f_state, fill=FG)
    rate_w = d.textlength(rate_txt, font=f_state)
    if fps_txt is not None:
        d.ellipse([cx + S(28) + rate_w, cy + S(5),
                   cx + S(36) + rate_w, cy + S(13)], fill=BROWN)
        d.text((cx + S(40) + rate_w, cy), f"{fps_txt} fps",
               font=f_label, fill=BROWN)
    cy += S(28)

    d.text((cx, cy), note_txt, font=f_note, fill=BROWN)
    cy += S(26)

    if screen_time is not None:
        d.text((cx, cy), "Screen time today", font=f_note, fill=BROWN)
        d.text((cx, cy + S(16)), screen_time, font=f_row, fill=FG)

    mid = card_w // 2 + S(10)
    avg = avg_bpm if avg_bpm is not None else 0.0
    avg_col = _rate_color(avg)
    d.ellipse([mid, cy + S(18), mid + S(10), cy + S(28)], fill=avg_col)
    d.text((mid, cy), "Avg today", font=f_note, fill=BROWN)
    d.text((mid + S(16), cy + S(16)), f"{avg:.0f} blinks/min",
           font=f_row, fill=FG)

    return card


def _render_help(states, S) -> Image.Image:
    f_key = _Fonts.get(S(12), "Bold")
    f_txt = _Fonts.get(S(12), "Regular")
    items = [
        ("Q", "quit", None),
        ("B", "beep", states.get("beep", False)),
        ("A", "alert", states.get("alert", False)),
        ("T", "on-top", states.get("ontop", False)),
    ]
    meas = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    gap = S(14)
    w = S(12)
    for key, label, state in items:
        w += meas.textlength(key, font=f_key) + S(4)
        w += meas.textlength(label, font=f_txt)
        if state is not None:
            w += S(5) + meas.textlength("OFF", font=f_key)
        w += gap
    w = int(w - gap + S(12))
    h = S(28)

    bar = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(bar)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=S(14), fill=BG_SOFT)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=S(14),
                        outline=(60, 68, 80, 160), width=1)

    x = S(12)
    ty = S(6)
    for key, label, state in items:
        d.text((x, ty), key, font=f_key, fill=BLUE)
        x += meas.textlength(key, font=f_key) + S(4)
        d.text((x, ty), label, font=f_txt, fill=FG)
        x += meas.textlength(label, font=f_txt)
        if state is not None:
            st = "ON" if state else "OFF"
            d.text((x + S(5), ty), st, font=f_key,
                   fill=GREEN if state else BROWN)
            x += S(5) + meas.textlength("OFF", font=f_key)
        x += gap
    return bar


def render_startup(checks: list, footer: str = "",
                   title: str = "Startup checks") -> "np.ndarray":
    scale = 1.0

    def S(v: float) -> int:
        return int(v * scale)

    f_title = _Fonts.get(S(18), "SemiBold")
    f_row = _Fonts.get(S(15), "Regular")
    f_stat = _Fonts.get(S(14), "Bold")
    f_detail = _Fonts.get(S(12), "Regular")
    f_foot = _Fonts.get(S(13), "Regular")

    pad = S(22)
    row_h = S(28)
    detail_h = S(18)
    h = S(56) + S(10)
    for c in checks:
        h += row_h
        if c.get("detail"):
            h += detail_h
    h += S(36) + 2 * pad
    w = S(440)

    canvas_img = Image.new("RGBA", (w, h), (*OUTER_BG, 255))
    d = ImageDraw.Draw(canvas_img)

    d.rounded_rectangle([S(8), S(8), w - S(8) - 1, h - S(8) - 1],
                        radius=S(16), fill=BG)
    d.rounded_rectangle([S(8), S(8), S(8) + S(5), h - S(8) - 1],
                        radius=S(2), fill=BLUE)

    cy = S(20)
    d.text((pad, cy), "EyeRhythm", font=f_title, fill=BLUE)
    tw = d.textlength("EyeRhythm", font=f_title)
    d.text((pad + tw, cy), f"  ·  {title}", font=f_title, fill=BROWN)
    cy += S(36)

    status_col = {
        "OK": GREEN, "FAIL": DANGER, "WARN": WARN, "..": BROWN,
    }
    for c in checks:
        st = c.get("status", "..")
        col = status_col.get(st, BROWN)
        badge = f"[{st}]"
        d.text((pad, cy), badge, font=f_stat, fill=col)
        bw = d.textlength("[FAIL]", font=f_stat)
        d.text((pad + bw + S(10), cy), c.get("label", ""), font=f_row, fill=FG)
        cy += row_h
        if c.get("detail"):
            d.text((pad + bw + S(10), cy - S(4)), c["detail"],
                   font=f_detail, fill=BROWN)
            cy += detail_h

    if footer:
        cy = h - S(32)
        d.text((pad, cy), footer, font=f_foot, fill=BROWN)

    arr = np.asarray(canvas_img)
    return arr[:, :, [2, 1, 0]].copy()


_CARD_CACHE: dict = {"key": None, "img": None}
_HELP_CACHE: dict = {"key": None, "img": None}
_LOGO_CACHE: dict = {"key": None, "img": None}
_DEFAULT_STATES = {"beep": False, "alert": False, "ontop": False}


def render_stats(res, fps: float | None = None,
                 screen_time: str | None = None,
                 states: dict | None = None,
                 avg_bpm: float | None = None,
                 total_blinks: int | None = None) -> "np.ndarray":
    """Render the statistics-only window as a floating rounded card."""
    states = states if states is not None else _DEFAULT_STATES
    scale = 1.0

    def S(v: float) -> int:
        return int(v * scale)

    fps_txt = f"{fps:.0f}" if fps is not None else None
    avg_key = None if avg_bpm is None else round(avg_bpm)
    key = ("stats", total_blinks, res.face_found, res.eyes_closed,
           round(res.blinks_per_minute), fps_txt, screen_time, avg_key)
    if _CARD_CACHE["key"] != key:
        _CARD_CACHE["img"] = _render_card(
            res, fps_txt, screen_time, avg_bpm, total_blinks, S)
        _CARD_CACHE["key"] = key
    card = _CARD_CACHE["img"]

    if _LOGO_CACHE["key"] != "logo":
        _LOGO_CACHE["img"] = _render_logo(S)
        _LOGO_CACHE["key"] = "logo"
    logo = _LOGO_CACHE["img"]

    hkey = ("stats-help", tuple(sorted(states.items())))
    if _HELP_CACHE["key"] != hkey:
        _HELP_CACHE["img"] = _render_help(states, S)
        _HELP_CACHE["key"] = hkey
    bar = _HELP_CACHE["img"]

    m = S(16)
    gap = S(10)
    content_w = max(card.size[0], bar.size[0], logo.size[0])
    shell_w = content_w + 2 * m
    shell_h = (logo.size[1] + gap + card.size[1] + gap +
               bar.size[1] + 2 * m)

    outer_pad = S(6)
    w = shell_w + 2 * outer_pad
    h = shell_h + 2 * outer_pad

    canvas = np.full((h, w, 3), OUTER_BG, dtype=np.uint8)

    shell = Image.new("RGBA", (shell_w, shell_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shell)
    sd.rounded_rectangle([0, 0, shell_w - 1, shell_h - 1],
                         radius=S(22), fill=(18, 20, 26, 255))
    sd.rounded_rectangle([0, 0, shell_w - 1, shell_h - 1],
                         radius=S(22), outline=(48, 54, 64, 200), width=1)

    shell_arr = np.asarray(shell)
    shell_bgr = shell_arr[:, :, [2, 1, 0]].copy()
    canvas[outer_pad:outer_pad + shell_h,
           outer_pad:outer_pad + shell_w] = shell_bgr

    ox, oy = outer_pad + m, outer_pad + m
    _paste_rgba(canvas, logo, ox + (content_w - logo.size[0]) // 2, oy)
    oy2 = oy + logo.size[1] + gap
    _paste_rgba(canvas, card, ox + (content_w - card.size[0]) // 2, oy2)
    oy3 = oy2 + card.size[1] + gap
    _paste_rgba(canvas, bar, ox + (content_w - bar.size[0]) // 2, oy3)

    return canvas


# ===== camera / landmark overlay =====
# Subset of MediaPipe Face Mesh contour edges (oval, eyes, brows, lips, nose).
# Used when --show_landmarks is on so the mesh stays readable.
_FACE_CONNECTIONS: list[tuple[int, int]] = [
    # Face oval
    (10, 338), (338, 297), (297, 332), (332, 284), (284, 251), (251, 389),
    (389, 356), (356, 454), (454, 323), (323, 361), (361, 288), (288, 397),
    (397, 365), (365, 379), (379, 378), (378, 400), (400, 377), (377, 152),
    (152, 148), (148, 176), (176, 149), (149, 150), (150, 136), (136, 172),
    (172, 58), (58, 132), (132, 93), (93, 234), (234, 127), (127, 162),
    (162, 21), (21, 54), (54, 103), (103, 67), (67, 109), (109, 10),
    # Left eye
    (33, 7), (7, 163), (163, 144), (144, 145), (145, 153), (153, 154),
    (154, 155), (155, 133), (33, 246), (246, 161), (161, 160), (160, 159),
    (159, 158), (158, 157), (157, 173), (173, 133),
    # Right eye
    (263, 249), (249, 390), (390, 373), (373, 374), (374, 380), (380, 381),
    (381, 382), (382, 362), (263, 466), (466, 388), (388, 387), (387, 386),
    (386, 385), (385, 384), (384, 398), (398, 362),
    # Lips (outer)
    (61, 146), (146, 91), (91, 181), (181, 84), (84, 17), (17, 314),
    (314, 405), (405, 321), (321, 375), (375, 291), (61, 185), (185, 40),
    (40, 39), (39, 37), (37, 0), (0, 267), (267, 269), (269, 270),
    (270, 409), (409, 291),
    # Nose
    (168, 6), (6, 197), (197, 195), (195, 5), (5, 4), (4, 1), (1, 19),
    (19, 94), (94, 2), (98, 97), (97, 2), (2, 326), (326, 327),
]


def _eye_center(points: list) -> tuple[float, float] | None:
    """Average of normalized eye outline points → (x, y) or None."""
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def draw_camera_overlay(
    frame_bgr,
    res,
    show_landmarks: bool = False,
) -> "np.ndarray":
    """
    Draw debug overlays on a live camera frame (BGR).

    - Always (when face found): eye-centre dots
        green = eyes open, red = eyes closed
    - If show_landmarks: all 478 landmarks as small blue dots,
      connected with thin light-blue contour lines
    """
    out = frame_bgr.copy()
    if not res.face_found:
        return out

    h, w = out.shape[:2]

    # ---- full face mesh (optional) ------------------------------------
    if show_landmarks and res.all_points:
        pts = res.all_points
        light_blue = (255, 200, 120)   # BGR light blue
        blue_dot = (255, 140, 40)     # BGR stronger blue for dots

        # contour lines first (under the dots)
        for i, j in _FACE_CONNECTIONS:
            if i < len(pts) and j < len(pts):
                p1 = (int(pts[i][0] * w), int(pts[i][1] * h))
                p2 = (int(pts[j][0] * w), int(pts[j][1] * h))
                cv2.line(out, p1, p2, light_blue, 1, cv2.LINE_AA)

        # all landmark dots
        for x_n, y_n in pts:
            cx, cy = int(x_n * w), int(y_n * h)
            cv2.circle(out, (cx, cy), 1, blue_dot, -1, cv2.LINE_AA)

    # ---- eye centres (always when camera is shown) --------------------
    colour = (0, 0, 255) if res.eyes_closed else (0, 220, 0)  # BGR red / green
    for pts in (res.left_eye_points, res.right_eye_points):
        centre = _eye_center(pts)
        if centre is None:
            continue
        cx, cy = int(centre[0] * w), int(centre[1] * h)
        cv2.circle(out, (cx, cy), 2, colour, -1, cv2.LINE_AA)
        cv2.circle(out, (cx, cy), 3, (255, 255, 255), 1, cv2.LINE_AA)

    return out


def composite_camera_and_stats(
    frame_bgr,
    res,
    fps: float | None = None,
    screen_time: str | None = None,
    states: dict | None = None,
    avg_bpm: float | None = None,
    total_blinks: int | None = None,
    show_landmarks: bool = False,
) -> "np.ndarray":
    """
    Live camera (with overlays) + stats card pasted in the top-right corner.
    """
    view = draw_camera_overlay(frame_bgr, res, show_landmarks=show_landmarks)
    card = render_stats(
        res, fps, screen_time, states,
        avg_bpm=avg_bpm, total_blinks=total_blinks)

    # scale card to ~40% of frame width if the frame is large
    fh, fw = view.shape[:2]
    ch, cw = card.shape[:2]
    max_card_w = max(180, int(fw * 0.38))
    if cw > max_card_w:
        scale = max_card_w / cw
        card = cv2.resize(card, (max_card_w, int(ch * scale)),
                          interpolation=cv2.INTER_AREA)
        ch, cw = card.shape[:2]

    margin = 12
    x1 = max(0, fw - cw - margin)
    y1 = margin
    x2, y2 = x1 + cw, y1 + ch
    if x2 <= fw and y2 <= fh:
        # soft dark backing so the card stays readable on bright frames
        roi = view[y1:y2, x1:x2]
        # card is already opaque BGR from render_stats
        view[y1:y2, x1:x2] = card
    return view

