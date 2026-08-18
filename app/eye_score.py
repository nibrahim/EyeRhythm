"""
Ocular Rhythm Index (ORI)
=========================

Composite 0–100 score blending blink rate (70 %) and inter-blink regularity
(30 %). Both inputs are already on comparable scales after rate normalization.

Rate normalization uses a trapezoid aligned with EyeRhythm alert targets:
  * 0 BPM        → unavailable (None)
  * 0–10 BPM     → 0–50   (alert zone)
  * 10–20 BPM    → 50–100 (healthy screen-use band)
  * ≥ 20 BPM     → 100

When regularity is still warming up (< 2 gaps), ORI falls back to the rate
component alone so the card is usable immediately.
"""

from __future__ import annotations

RATE_WEIGHT = 0.70
REGULARITY_WEIGHT = 0.30

ALERT_BPM = 10.0
HEALTHY_BPM_MAX = 20.0


def rate_score(bpm: float) -> float | None:
    """Map continuous BPM to 0–100. None when BPM ≤ 0 (no usable signal)."""
    if bpm <= 0.0:
        return None
    if bpm < ALERT_BPM:
        return 50.0 * (bpm / ALERT_BPM)
    if bpm <= HEALTHY_BPM_MAX:
        span = HEALTHY_BPM_MAX - ALERT_BPM
        return 50.0 + 50.0 * ((bpm - ALERT_BPM) / span)
    return 100.0


def ocular_rhythm_index(
    bpm: float,
    regularity: float | None,
) -> float | None:
    """
    Ocular Rhythm Index (ORI): weighted blend of rate and regularity.

    Returns None when blink rate is unavailable (BPM ≤ 0).
    """
    rs = rate_score(bpm)
    if rs is None:
        return None
    if regularity is None:
        return round(rs, 1)
    combined = (RATE_WEIGHT * rs) + (REGULARITY_WEIGHT * regularity)
    return round(min(100.0, max(0.0, combined)), 1)
