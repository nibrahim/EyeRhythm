"""
app — desktop shell + local API for EyeRhythm
=============================================

Modules
-------
* ``main``         – process entry: engine + HTTP server + window
* ``engine``       – camera loop, blink pipeline, beeps/alerts (business logic)
* ``server``       – FastAPI REST + WebSocket API for the React UI
* ``preferences``  – last avatar, window size, Beep/Alert/On top
* ``regularity``   – inter-blink CV → regularity score 0–100
* ``beeper``       – short OS-native sounds

The React UI lives in ``frontend/`` and is served from ``frontend/dist`` after build.
Blink science stays in ``blink_core`` (unchanged).
"""
