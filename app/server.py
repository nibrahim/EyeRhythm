"""
Local HTTP + WebSocket API for the React UI
===========================================

Serves:
* Built static frontend (production) or is used with Vite dev proxy
* GET  /api/health
* GET  /api/state          — one-shot engine snapshot
* POST /api/toggles/{name} — beep | alert | ontop | practice  body: {"value": bool?}
* GET  /api/preview        — latest JPEG bytes (when camera panel open)
* WS   /ws/stats           — live JSON snapshots (~10 Hz)
* WS   /ws/preview         — live JPEG frames as binary (when client asks)

Everything is localhost-only. No cloud. No analytics.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import audit
from app import preferences

if TYPE_CHECKING:
    from app.engine import EyeRhythmEngine


def _project_root() -> Path:
    """
    Folder that holds `frontend/`, `quotes.json`, and the face model.

    When packaged (PyInstaller), files live in a temporary extract folder
    (`sys._MEIPASS`) instead of next to this source file.
    """
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def _ui_dist() -> Path:
    """
    Built React app (vite → dist).

    Works for source checkouts and PyInstaller freezes (``sys._MEIPASS``).
    """
    return _project_root() / "frontend" / "dist"


# Built dashboard folder (index.html + JS/CSS). Empty until `npm run build`.
UI_DIST = _ui_dist()
QUOTES_PATH = _project_root() / "quotes.json"
# Quotes are tiny and never change at runtime — load once, reuse forever.
_QUOTES_CACHE: list[dict[str, str]] | None = None


def _load_quotes() -> list[dict[str, str]]:
    """
    Load famous quotes as ``{"text": str, "author": str}``.

    Supports the v2 schema (objects with text+author) and falls back for
    legacy plain-string lists.
    """
    global _QUOTES_CACHE
    if _QUOTES_CACHE is not None:
        return _QUOTES_CACHE
    out: list[dict[str, str]] = []
    try:
        data = json.loads(QUOTES_PATH.read_text(encoding="utf-8"))
        raw = data.get("quotes") if isinstance(data, dict) else data
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                    author = str(item.get("author", "Unknown")).strip() or "Unknown"
                    if text:
                        out.append({"text": text, "author": author})
                elif isinstance(item, str) and item.strip():
                    out.append({"text": item.strip(), "author": "Unknown"})
    except (OSError, ValueError, TypeError):
        out = []
    _QUOTES_CACHE = out
    return _QUOTES_CACHE



class ToggleBody(BaseModel):
    """JSON body for POST /api/toggles/{name}. Missing value = flip it."""
    value: bool | None = Field(
        default=None,
        description="If omitted, the toggle is flipped.",
    )


class PreferencesPatch(BaseModel):
    """Any subset of saved settings the dashboard may send back."""
    avatar: str | None = None
    compact: bool | None = None
    window_width: int | None = None
    window_height: int | None = None
    beep: bool | None = None
    alert: bool | None = None
    ontop: bool | None = None
    eye_comfort: str | None = None
    dock: bool | None = None
    ori_threshold: float | None = None
    writing_angle_deg: float | None = None
    turn_angle_deg: float | None = None
    close_delta: float | None = None
    # practice is accepted by toggle API but never stored in preferences


class SettingsPatch(BaseModel):
    """Live Settings-dock knobs. Any subset is applied immediately."""
    ori_threshold: float | None = None
    writing_angle_deg: float | None = None
    turn_angle_deg: float | None = None
    close_delta: float | None = None


def create_app(engine: "EyeRhythmEngine") -> FastAPI:
    """
    Build the tiny local website the dashboard uses.

    Think of it as a receptionist: the React UI asks “what’s my blink rate?”
    or “please turn Beep on”, and this file forwards that to the engine.
    """
    # Hide the auto-generated API docs — this is a private localhost app.
    app = FastAPI(title="EyeRhythm", version="2.0.0", docs_url=None, redoc_url=None)

    # Vite dev server may call from another port during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.engine = engine

    @app.get("/api/health")
    def health():
        """“Is the local server alive?” — used by the UI / installers."""
        return {"ok": True, "service": "EyeRhythm"}

    @app.get("/api/state")
    def state():
        """One-shot snapshot of every live number (blink rate, toggles, …)."""
        return engine.snapshot().to_dict()

    @app.get("/api/toggles")
    def get_toggles():
        """Current Beep / Alert / On top / Practice flags."""
        return engine.get_toggles()

    @app.post("/api/toggles/{name}")
    def set_toggle(name: str, body: ToggleBody | None = None):
        """Turn a named switch on or off (or flip it if no value is sent)."""
        name = name.lower().strip()
        if name not in ("beep", "alert", "ontop", "practice"):
            raise HTTPException(status_code=400, detail="unknown toggle")
        value = None if body is None else body.value
        try:
            return engine.set_toggle(name, value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/preferences")
    def get_preferences():
        """Last session UI state (avatar, window size, toggles)."""
        prefs = preferences.load()
        # Live toggles win if they differ mid-session.
        toggles = engine.get_toggles()
        prefs["beep"] = toggles["beep"]
        prefs["alert"] = toggles["alert"]
        prefs["ontop"] = toggles["ontop"]
        prefs.update(engine.get_settings())
        return prefs

    @app.put("/api/preferences")
    def put_preferences(body: PreferencesPatch):
        """Merge and persist any subset of preferences."""
        patch = body.model_dump(exclude_none=True)
        if not patch:
            return preferences.load()
        # Toggles go through the engine so side-car threads / ontop callbacks run.
        # Practice is intentionally not part of durable preferences.
        toggle_keys = {
            k: patch.pop(k)
            for k in ("beep", "alert", "ontop")
            if k in patch
        }
        for name, val in toggle_keys.items():
            engine.set_toggle(name, bool(val))
        # Detection knobs go through the engine so Alert / Trace / detector
        # update live and the change is audited.
        setting_keys = {
            k: patch.pop(k)
            for k in (
                "ori_threshold",
                "writing_angle_deg",
                "turn_angle_deg",
                "close_delta",
            )
            if k in patch
        }
        if setting_keys:
            engine.apply_settings(setting_keys)
        if patch:
            preferences.save(patch)
        prefs = preferences.load()
        toggles = engine.get_toggles()
        prefs.update({k: toggles[k] for k in ("beep", "alert", "ontop")})
        prefs.update(engine.get_settings())
        return prefs

    @app.get("/api/settings")
    def get_settings():
        """Current live Settings-dock values."""
        return engine.get_settings()

    @app.put("/api/settings")
    def put_settings(body: SettingsPatch):
        """Apply ORI threshold / writing angle / blink sensitivity immediately."""
        patch = body.model_dump(exclude_none=True)
        try:
            return engine.apply_settings(patch)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/audit")
    def get_audit(limit: int = 40):
        """Newest-first settings change log (local JSON)."""
        return {"entries": audit.list_entries(limit)}

    @app.get("/api/reports")
    def get_reports(
        kind: str = "daily",
        date: str | None = None,
        year: int | None = None,
        month: int | None = None,
    ):
        """
        Daily (5-min bins), weekly (1 bar/day), or monthly (1 point/day).

        ``date`` is YYYY-MM-DD (daily/weekly). Monthly uses ``year`` + ``month``.
        """
        kind = (kind or "daily").lower().strip()
        if kind == "index":
            return engine.reports_index()
        if kind == "daily":
            if not date:
                raise HTTPException(status_code=400, detail="date required")
            return engine.report_daily(date)
        if kind == "weekly":
            if not date:
                raise HTTPException(status_code=400, detail="date required")
            return engine.report_weekly(date)
        if kind == "monthly":
            if year is None or month is None:
                raise HTTPException(status_code=400, detail="year and month required")
            return engine.report_monthly(int(year), int(month))
        raise HTTPException(status_code=400, detail="kind must be daily|weekly|monthly|index")

    @app.get("/api/quotes")
    def get_quotes():
        """Motivating short quotes used during Practice mode."""
        quotes = _load_quotes()
        return {
            "count": len(quotes),
            "interval_seconds": 30,
            "practice_duration_seconds": 120,
            "quotes": quotes,
        }

    @app.post("/api/preview/enable")
    def preview_enable():
        """Ask the engine to start encoding camera JPEGs (Lens avatar)."""
        engine.set_preview_wanted(True)
        return {"preview": True}

    @app.post("/api/preview/disable")
    def preview_disable():
        """Stop encoding preview frames — saves CPU when Lens is hidden."""
        engine.set_preview_wanted(False)
        return {"preview": False}

    @app.get("/api/preview")
    def preview():
        """Latest camera still as a JPEG, or 204 if none is ready yet."""
        data = engine.latest_preview_jpeg()
        if not data:
            return Response(status_code=204)
        return Response(content=data, media_type="image/jpeg")

    @app.websocket("/ws/stats")
    async def ws_stats(ws: WebSocket):
        """Live feed of metrics (~10 times a second) for the dashboard cards."""
        await ws.accept()
        try:
            while True:
                snap = engine.snapshot().to_dict()
                await ws.send_text(json.dumps(snap))
                await asyncio.sleep(0.1)  # 10 Hz is plenty for the dashboard
        except WebSocketDisconnect:
            pass
        except Exception:
            try:
                await ws.close()
            except Exception:
                pass

    @app.websocket("/ws/preview")
    async def ws_preview(ws: WebSocket):
        """Stream camera JPEGs while a client is connected (optional path)."""
        await ws.accept()
        engine.set_preview_wanted(True)
        last: bytes | None = None
        try:
            while True:
                # Client may send {"enable": false} to pause encoding.
                try:
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=0.05)
                    try:
                        payload = json.loads(msg)
                        if "enable" in payload:
                            engine.set_preview_wanted(bool(payload["enable"]))
                    except json.JSONDecodeError:
                        pass
                except asyncio.TimeoutError:
                    pass

                data = engine.latest_preview_jpeg()
                if data and data is not last:
                    await ws.send_bytes(data)
                    last = data
                await asyncio.sleep(0.08)
        except WebSocketDisconnect:
            pass
        except Exception:
            try:
                await ws.close()
            except Exception:
                pass
        finally:
            engine.set_preview_wanted(False)

    # ---- static React build -------------------------------------------
    # After `npm run build`, serve the dashboard files so the desktop
    # window can load http://127.0.0.1:8742/ without Vite.
    if UI_DIST.is_dir() and (UI_DIST / "index.html").is_file():
        assets = UI_DIST / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/")
        def index():
            """The dashboard’s first page."""
            return FileResponse(UI_DIST / "index.html")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            """Serve a real file if it exists; otherwise the same HTML page."""
            # Do not swallow API / WS.
            if full_path.startswith("api") or full_path.startswith("ws"):
                raise HTTPException(status_code=404)
            candidate = UI_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(UI_DIST / "index.html")

    return app


def run_server(engine: "EyeRhythmEngine", host: str = "127.0.0.1",
               port: int = 8742) -> threading.Thread:
    """
    Start uvicorn in a daemon thread. Returns the thread.
    """
    import uvicorn

    app = create_app(engine)

    def _serve() -> None:
        # Running off the main thread: skip signal handlers (uvicorn handles this
        # on recent versions; Config + Server is explicit and quieter in logs).
        # Pin protocols so a PyInstaller freeze does not depend on uvicorn's
        # "auto" importer finding httptools / uvloop at runtime.
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            loop="asyncio",
            http="h11",
            ws="websockets",
            lifespan="on",
            ws_ping_interval=20,
            ws_ping_timeout=20,
        )
        server = uvicorn.Server(config)
        try:
            server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
        except Exception:
            pass
        try:
            server.run()
        except Exception:
            import traceback
            traceback.print_exc()

    t = threading.Thread(target=_serve, name="EyeRhythmHTTP", daemon=True)
    t.start()
    return t
