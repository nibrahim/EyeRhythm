"""
Lemon Squeezy license activation
================================

Paid Mac/Windows builds ask for the key from the purchase email on first
launch. The desktop app talks to Lemon Squeezy (unique keys, payment,
activation store). Blink data still never leaves the machine.

Running from source does not require a key, so contributors can keep
working. Packaged copies (PyInstaller) do. Override with::

    EYERHYTHM_REQUIRE_LICENSE=1   # force the gate (useful while developing)
    EYERHYTHM_SKIP_LICENSE=1      # skip even in a packaged build

Fill ``LS_STORE_ID`` / ``LS_VARIANT_*`` after the Lemon Squeezy products
exist so a key from some other store cannot unlock EyesRhythm.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.preferences import STORAGE_DIR

LICENSE_FILE = STORAGE_DIR / "license.json"
LS_LICENSE_API = "https://api.lemonsqueezy.com/v1/licenses"

# Paste numeric IDs from Lemon Squeezy → Products (or set env vars).
# 0 means “not configured yet” — the key is still checked with Lemon Squeezy,
# but the app cannot confirm it belongs to this store / OS variant.
LS_STORE_ID = int(os.environ.get("EYERHYTHM_LS_STORE_ID", "0") or "0")
LS_VARIANT_MAC = int(os.environ.get("EYERHYTHM_LS_VARIANT_MAC", "0") or "0")
LS_VARIANT_WINDOWS = int(
    os.environ.get("EYERHYTHM_LS_VARIANT_WINDOWS", "0") or "0"
)

_ENFORCEMENT: bool | None = None


class LicenseError(Exception):
    """User-facing activation failure (bad key, wrong OS, network, …)."""


class LicenseNetworkError(LicenseError):
    """Lemon Squeezy could not be reached."""


def set_enforcement(required: bool | None) -> None:
    """Override whether a key is required (CLI flags). ``None`` = default."""
    global _ENFORCEMENT
    _ENFORCEMENT = required


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def is_required() -> bool:
    """True when this process must activate before the dashboard."""
    if _env_flag("EYERHYTHM_SKIP_LICENSE"):
        return False
    if _ENFORCEMENT is False:
        return False
    if _ENFORCEMENT is True:
        return True
    if _env_flag("EYERHYTHM_REQUIRE_LICENSE"):
        return True
    return bool(getattr(sys, "frozen", False))


def current_platform() -> str:
    """``mac``, ``windows``, or ``other`` (Linux / unknown)."""
    system = platform.system().lower()
    if system == "darwin":
        return "mac"
    if system == "windows":
        return "windows"
    return "other"


def expected_variant_id() -> int:
    plat = current_platform()
    if plat == "mac":
        return LS_VARIANT_MAC
    if plat == "windows":
        return LS_VARIANT_WINDOWS
    return 0


def _license_path() -> Path:
    override = os.environ.get("EYERHYTHM_LICENSE_FILE", "").strip()
    return Path(override) if override else LICENSE_FILE


def normalize_key(raw: str) -> str:
    """Strip spaces; keep hyphens so Lemon Squeezy sees the issued key."""
    return "".join(str(raw or "").split()).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _raw_machine_id() -> str:
    """Stable OS identifier. Hashed before it is stored or sent."""
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                text=True,
                timeout=5,
            )
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    parts = line.split('"')
                    if len(parts) >= 2:
                        return parts[-2].strip()
        elif system == "Windows":
            import winreg  # type: ignore[import-not-found]

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            try:
                val, _ = winreg.QueryValueEx(key, "MachineGuid")
                return str(val).strip()
            finally:
                winreg.CloseKey(key)
        else:
            for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
                if path.is_file():
                    return path.read_text(encoding="utf-8").strip()
    except (OSError, subprocess.SubprocessError, ValueError, ImportError):
        pass
    return f"fallback:{platform.node()}:{sys.platform}"


def machine_fingerprint() -> str:
    """SHA-256 of the hardware id. This is what we send as instance_name."""
    payload = f"eyesrhythm:{current_platform()}:{_raw_machine_id()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def load_local() -> dict[str, Any] | None:
    """Return the saved activation, or None if missing/corrupt."""
    path = _license_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    key = str(raw.get("license_key") or "").strip()
    instance = str(raw.get("instance_id") or "").strip()
    if not key or not instance:
        return None
    return raw


def is_activated() -> bool:
    if not is_required():
        return True
    record = load_local()
    if record is None:
        return False
    # Same computer: fingerprint must still match (copied license file
    # from another machine should not skip activation).
    stored = str(record.get("instance_name") or "")
    return stored == machine_fingerprint()


def _save_local(record: dict[str, Any]) -> None:
    path = _license_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def status() -> dict[str, Any]:
    """JSON for GET /api/license."""
    required = is_required()
    activated = is_activated()
    record = load_local() if required else None
    plat = current_platform()
    return {
        "required": required,
        "activated": activated,
        "platform": plat,
        "platform_label": {
            "mac": "macOS",
            "windows": "Windows",
            "other": platform.system() or "this computer",
        }.get(plat, plat),
        "email": (record or {}).get("customer_email") or "",
    }


def _post_form(url: str, fields: dict[str, str], timeout: float = 20.0) -> tuple[int, dict[str, Any]]:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "EyesRhythm/2.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"error": "Unexpected response from Lemon Squeezy"}
            if not isinstance(parsed, dict):
                parsed = {"error": "Unexpected response from Lemon Squeezy"}
            return int(getattr(resp, "status", 200) or 200), parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        if not parsed.get("error"):
            parsed["error"] = raw.strip() or str(exc.reason or exc)
        return int(exc.code), parsed
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LicenseNetworkError(
            "Activation needs the internet. Connect and try again."
        ) from exc


def _ls_call(action: str, fields: dict[str, str]) -> dict[str, Any]:
    _status, payload = _post_form(f"{LS_LICENSE_API}/{action}", fields)
    return payload


def _reject_if_wrong_product(meta: dict[str, Any]) -> None:
    try:
        store_id = int(meta.get("store_id") or 0)
        variant_id = int(meta.get("variant_id") or 0)
    except (TypeError, ValueError):
        store_id = 0
        variant_id = 0
    variant_name = str(meta.get("variant_name") or "")
    if LS_STORE_ID and store_id and store_id != LS_STORE_ID:
        raise LicenseError("This key is not an EyesRhythm license.")
    expected = expected_variant_id()
    if expected and variant_id and variant_id != expected:
        other = "Windows" if current_platform() == "mac" else "macOS"
        this = "macOS" if current_platform() == "mac" else "Windows"
        hint = variant_name or other
        raise LicenseError(
            f"This key is for {hint}, not {this}. "
            "Each purchase is one operating system."
        )


def _friendly_ls_error(payload: dict[str, Any]) -> str:
    err = str(payload.get("error") or "").strip()
    lowered = err.lower()
    if "not found" in lowered or "invalid" in lowered:
        return "That license key was not recognised. Check the email from checkout."
    if "activation limit" in lowered or "limit" in lowered:
        return (
            "This key is already used on another computer. "
            "If you reinstalled, open Lemon Squeezy → Licenses, "
            "deactivate the old machine, then try again."
        )
    if "expired" in lowered:
        return "This license key has expired."
    if "disabled" in lowered or "inactive" in lowered:
        return "This license key is no longer active."
    return err or "Lemon Squeezy could not activate this key."


def activate(license_key: str) -> dict[str, Any]:
    """
    Call Lemon Squeezy, bind this machine, save locally.

    Subsequent launches read the local file and stay offline.
    """
    key = normalize_key(license_key)
    if not key:
        raise LicenseError("Paste the license key from your purchase email.")
    if len(key) < 8:
        raise LicenseError("That does not look like a license key.")

    fingerprint = machine_fingerprint()
    payload = _ls_call(
        "activate",
        {"license_key": key, "instance_name": fingerprint},
    )
    if not payload.get("activated"):
        raise LicenseError(_friendly_ls_error(payload))

    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    instance = payload.get("instance") if isinstance(payload.get("instance"), dict) else {}
    instance_id = str(instance.get("id") or "").strip()
    if not instance_id:
        raise LicenseError("Lemon Squeezy did not return an activation id.")

    _reject_if_wrong_product(meta)

    record = {
        "license_key": key,
        "instance_id": instance_id,
        "instance_name": fingerprint,
        "platform": current_platform(),
        "customer_email": str(meta.get("customer_email") or ""),
        "product_name": str(meta.get("product_name") or ""),
        "variant_name": str(meta.get("variant_name") or ""),
        "activated_at": _utc_now(),
    }
    try:
        _save_local(record)
    except OSError as exc:
        raise LicenseError("Could not save the license on this computer.") from exc
    return status()
