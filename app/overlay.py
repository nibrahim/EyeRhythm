"""
EyeRhythm - BlinkCounter overlay (open-source edition).

Rendered with PIL + the bundled Inter typeface (SIL OFL license) for
crisp, modern typography. Brand theme: blue / green / brown.

This edition shows only the statistics card — no video feed is ever
displayed. The info card and help bar are re-rendered only when a
displayed value changes; otherwise cached bitmaps are pasted.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

def _resource_root():
    import sys
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


FONT_DIR = _resource_root() / "assets" / "fonts"

# ------------------------------------------------------- brand palette (RGB)
BLUE = (86, 148, 217, 255)      # primary brand
GREEN = (86, 204, 145, 255)     # healthy / eyes open
BROWN = (176, 138, 102, 255)    # warm secondary text
DARK_BROWN = (52, 38, 28, 255)
BG = (22, 19, 15, 218)          # warm dark panel background (RGBA)
BG_SOFT = (22, 19, 15, 160)
FG = (243, 240, 235, 255)       # primary text (warm white)
WARN = (245, 158, 66, 255)      # amber - low blink rate
DANGER = (239, 83, 80, 255)     # red - eyes closed

# Medical guidance shown in the UI: healthy spontaneous blink rate is
# ~15-20 blinks/min (American Academy of Ophthalmology); it can drop by
# half or more when staring at screens.
HEALTHY_MIN, HEALTHY_MAX = 15, 20


class _Fonts:
    _cache: dict = {}

    @classmethod
    def get(cls, size: int, weight: str = "Regular"):
        key = (size, weight)
        if key not in cls._cache:
            try:
                # BASIC layout engine: much faster than complex shaping,
                # identical output for the plain ASCII strings we draw.
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
    """Same colour rules used for both instant and daily-average rates."""
    if not face_found and bpm <= 0:
        return BROWN
    if bpm >= HEALTHY_MIN:
        return GREEN
    if bpm >= 8:
        return WARN
    return DANGER


# ================================================================= renderers

def _render_logo(S) -> Image.Image:
    """EyeRhythm logo chip: brown almond eye, blue iris, green accent."""
    f_logo = _Fonts.get(S(17), "Bold")
    meas = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tw_eye = meas.textlength("Eye", font=f_logo)
    tw_rhythm = meas.textlength("Rhythm", font=f_logo)
    icon_w = S(34)
    pad = S(10)
    w = int(pad + icon_w + S(8) + tw_eye + tw_rhythm + pad)
    h = S(36)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=S(10), fill=BG_SOFT)

    # eye icon
    cy = h // 2
    ex0, ex1 = pad, pad + icon_w
    # almond shape
    d.ellipse([ex0, cy - S(9), ex1, cy + S(9)], outline=BROWN, width=S(2))
    # iris + pupil + glint
    cxi = (ex0 + ex1) // 2
    d.ellipse([cxi - S(7), cy - S(7), cxi + S(7), cy + S(7)], fill=BLUE)
    d.ellipse([cxi - S(3), cy - S(3), cxi + S(3), cy + S(3)],
              fill=DARK_BROWN)
    d.ellipse([cxi + S(1), cy - S(5), cxi + S(4), cy - S(2)],
              fill=(255, 255, 255, 230))

    # wordmark: Eye (blue) + Rhythm (green)
    ty = cy - S(11)
    d.text((ex1 + S(8), ty), "Eye", font=f_logo, fill=BLUE)
    d.text((ex1 + S(8) + tw_eye, ty), "Rhythm", font=f_logo, fill=GREEN)
    return img


def _render_card(res, fps_txt, screen_time, avg_bpm, total_blinks, S) -> Image.Image:
    f_brand = _Fonts.get(S(15), "SemiBold")
    f_count = _Fonts.get(S(54), "Bold")
    f_label = _Fonts.get(S(14), "Regular")
    f_state = _Fonts.get(S(14), "SemiBold")
    f_note = _Fonts.get(S(13), "Regular")

    pad = S(18)
    note_txt = (f"Healthy: {HEALTHY_MIN}-{HEALTHY_MAX} blinks/min "
                "- blink more on screens")
    meas = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    card_w = max(S(320), int(meas.textlength(note_txt, font=f_note))
                 + 2 * pad)
    # Extra row for daily average rate under screen time
    card_h = S(230)
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, card_w - 1, card_h - 1],
                        radius=S(14), fill=BG)
    # brand accent stripe down the left edge
    d.rounded_rectangle([0, 0, S(5), card_h - 1], radius=S(2), fill=BLUE)

    cx, cy = pad, S(14)

    # brand
    d.text((cx, cy), "EyeRhythm", font=f_brand, fill=BLUE)
    brand_w = d.textlength("EyeRhythm", font=f_brand)
    d.text((cx + brand_w, cy), "  ·  BlinkCounter", font=f_brand, fill=BROWN)
    cy += S(30)

    # daily blink total (persisted; survives restarts, rolls over at midnight)
    count_val = total_blinks if total_blinks is not None else res.blink_count
    d.text((cx, cy), str(count_val), font=f_count, fill=FG)
    count_w = max(d.textlength(str(count_val), font=f_count), S(46))
    d.text((cx + count_w + S(10), cy + S(34)), "blinks today",
           font=f_label, fill=BROWN)

    if res.face_found:
        pill_txt = "EYES CLOSED" if res.eyes_closed else "EYES OPEN"
        pill_col = DANGER if res.eyes_closed else GREEN
    else:
        pill_txt, pill_col = "NO FACE", BROWN
    pw = d.textlength(pill_txt, font=f_state) + S(24)
    px = card_w - pad - pw
    py = cy + S(10)
    d.rounded_rectangle([px, py, px + pw, py + S(26)], radius=S(13),
                        outline=pill_col, width=2)
    d.text((px + S(12), py + S(4)), pill_txt, font=f_state, fill=pill_col)
    cy += S(66)

    # instantaneous blink rate row with health colour
    bpm = res.blinks_per_minute
    bpm_col = _rate_color(bpm, res.face_found)
    d.ellipse([cx, cy + S(5), cx + S(10), cy + S(15)], fill=bpm_col)
    rate_txt = f"{bpm:.0f} blinks/min"
    d.text((cx + S(18), cy), rate_txt, font=f_state, fill=FG)
    rate_w = d.textlength(rate_txt, font=f_state)
    if fps_txt is not None:
        d.text((cx + S(26) + rate_w, cy), f"{fps_txt} fps",
               font=f_label, fill=BROWN)
    cy += S(26)

    # medical guidance note
    d.text((cx, cy), note_txt, font=f_note, fill=BROWN)
    cy += S(24)

    # screen time (persists across resets, rolls over at midnight)
    if screen_time is not None:
        d.text((cx, cy), f"Screen time today   {screen_time}",
               font=f_note, fill=BROWN)
        cy += S(22)

    # daily average blink rate (total blinks / screen-time minutes)
    avg = avg_bpm if avg_bpm is not None else 0.0
    avg_col = _rate_color(avg)
    d.ellipse([cx, cy + S(4), cx + S(10), cy + S(14)], fill=avg_col)
    avg_txt = f"Avg today   {avg:.0f} blinks/min"
    d.text((cx + S(18), cy), avg_txt, font=f_note, fill=FG)

    return card


def _render_help(states, S) -> Image.Image:
    """Key help bar with live ON/OFF state of each toggle."""
    f_key = _Fonts.get(S(14), "Bold")
    f_txt = _Fonts.get(S(14), "Regular")
    items = [
        ("Q", "quit", None),
        ("B", "beep", states.get("beep", False)),
        ("A", "alert", states.get("alert", False)),
        ("T", "on-top", states.get("ontop", False)),
    ]
    meas = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    gap = S(16)
    w = S(14)
    for key, label, state in items:
        w += meas.textlength(key, font=f_key) + S(5)
        w += meas.textlength(label, font=f_txt)
        if state is not None:
            w += S(6) + meas.textlength("OFF", font=f_key)
        w += gap
    w = int(w - gap + S(14))
    h = S(30)

    bar = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(bar)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=S(9), fill=BG_SOFT)
    x = S(14)
    ty = S(6)
    for key, label, state in items:
        d.text((x, ty), key, font=f_key, fill=BLUE)
        x += meas.textlength(key, font=f_key) + S(5)
        d.text((x, ty), label, font=f_txt, fill=FG)
        x += meas.textlength(label, font=f_txt)
        if state is not None:
            st = "ON" if state else "OFF"
            d.text((x + S(6), ty), st, font=f_key,
                   fill=GREEN if state else BROWN)
            x += S(6) + meas.textlength("OFF", font=f_key)
        x += gap
    return bar


# ============================================================ startup panel

def render_startup(checks: list, footer: str = "",
                   title: str = "Startup checks") -> "np.ndarray":
    """
    Render the startup sanity-check panel shown before the main UI.

    checks: list of dicts with keys:
        label  – e.g. "Python runtime"
        status – "OK" | "FAIL" | "WARN" | ".."
        detail – optional secondary line
    footer: instruction line at the bottom (e.g. "Y continue  ·  Q quit")
    """
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
    # estimate height
    h = S(56) + S(10)  # title
    for c in checks:
        h += row_h
        if c.get("detail"):
            h += detail_h
    h += S(36) + 2 * pad  # footer strip
    w = S(440)

    canvas_img = Image.new("RGBA", (w, h), (15, 19, 22, 255))
    d = ImageDraw.Draw(canvas_img)

    # card background
    d.rounded_rectangle([S(8), S(8), w - S(8) - 1, h - S(8) - 1],
                        radius=S(14), fill=BG)
    d.rounded_rectangle([S(8), S(8), S(8) + S(5), h - S(8) - 1],
                        radius=S(2), fill=BLUE)

    cy = S(20)
    d.text((pad, cy), "EyeRhythm", font=f_title, fill=BLUE)
    tw = d.textlength("EyeRhythm", font=f_title)
    d.text((pad + tw, cy), f"  ·  {title}", font=f_title, fill=BROWN)
    cy += S(36)

    status_col = {
        "OK": GREEN,
        "FAIL": DANGER,
        "WARN": WARN,
        "..": BROWN,
    }
    for c in checks:
        st = c.get("status", "..")
        col = status_col.get(st, BROWN)
        # status badge
        badge = f"[{st}]"
        d.text((pad, cy), badge, font=f_stat, fill=col)
        bw = d.textlength("[FAIL]", font=f_stat)  # fixed width for alignment
        d.text((pad + bw + S(10), cy), c.get("label", ""), font=f_row, fill=FG)
        cy += row_h
        if c.get("detail"):
            d.text((pad + bw + S(10), cy - S(4)), c["detail"],
                   font=f_detail, fill=BROWN)
            cy += detail_h

    # footer
    if footer:
        cy = h - S(32)
        d.text((pad, cy), footer, font=f_foot, fill=BROWN)

    # convert RGBA → BGR for OpenCV
    arr = np.asarray(canvas_img)
    bgr = arr[:, :, [2, 1, 0]].copy()
    return bgr


# ================================================================ public API

_CARD_CACHE: dict = {"key": None, "img": None}
_HELP_CACHE: dict = {"key": None, "img": None}
_LOGO_CACHE: dict = {"key": None, "img": None}

_DEFAULT_STATES = {"beep": False, "alert": False, "ontop": False}


def render_stats(res, fps: float | None = None,
                 screen_time: str | None = None,
                 states: dict | None = None,
                 avg_bpm: float | None = None,
                 total_blinks: int | None = None) -> "np.ndarray":
    """Render the statistics-only window (no video feed)."""
    states = states if states is not None else _DEFAULT_STATES
    scale = 1.0

    def S(v: float) -> int:
        return int(v * scale)

    fps_txt = f"{fps:.0f}" if fps is not None else None
    avg_key = None if avg_bpm is None else round(avg_bpm)
    # total_blinks is the persisted daily count shown as the big number
    key = ("stats", total_blinks, res.face_found, res.eyes_closed,
           round(res.blinks_per_minute), fps_txt, screen_time, avg_key)
    if _CARD_CACHE["key"] != key:
        _CARD_CACHE["img"] = _render_card(
            res, fps_txt, screen_time, avg_bpm, total_blinks, S)
        _CARD_CACHE["key"] = key
    card = _CARD_CACHE["img"]

    # logo is static for fixed scale
    if _LOGO_CACHE["key"] != "logo":
        _LOGO_CACHE["img"] = _render_logo(S)
        _LOGO_CACHE["key"] = "logo"
    logo = _LOGO_CACHE["img"]

    hkey = ("stats-help", tuple(sorted(states.items())))
    if _HELP_CACHE["key"] != hkey:
        _HELP_CACHE["img"] = _render_help(states, S)
        _HELP_CACHE["key"] = hkey
    bar = _HELP_CACHE["img"]

    m = S(14)
    # layout: logo row (top) → stats card → help bar (bottom)
    content_w = max(card.size[0], bar.size[0], logo.size[0])
    w = content_w + 2 * m
    logo_h = logo.size[1]
    h = logo_h + card.size[1] + bar.size[1] + 4 * m
    canvas = np.full((h, w, 3), (15, 19, 22), dtype=np.uint8)  # warm dark
    # centre the logo horizontally in the top strip
    _paste_rgba(canvas, logo, (w - logo.size[0]) // 2, m)
    _paste_rgba(canvas, card, m, logo_h + 2 * m)
    _paste_rgba(canvas, bar, m, logo_h + card.size[1] + 3 * m)
    return canvas
