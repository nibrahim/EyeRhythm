"""
Dodo Payments license activation
================================

Copies open without a purchase key, including packaged Mac/Windows
builds, so the app can be shared for free. Blink data still never
leaves the machine.

The Dodo Payments gate is off unless you turn it on::

    EYERHYTHM_REQUIRE_LICENSE=1   # force the gate (useful while developing)
    --require-license             # same, from the command line
    EYERHYTHM_SKIP_LICENSE=1      # skip even when the gate was forced
    EYERHYTHM_DODO_TEST=1         # talk to Dodo test mode, not live

Fill ``DODO_PRODUCT_MAC`` / ``DODO_PRODUCT_WINDOWS`` after the Dodo
products exist so a key bought for the other OS cannot unlock this copy.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.preferences import STORAGE_DIR

LICENSE_FILE = STORAGE_DIR / "license.json"
DODO_LIVE_API = "https://live.dodopayments.com"
DODO_TEST_API = "https://test.dodopayments.com"

# Paste product ids from Dodo → Products (pdt_…). Empty means “not
# configured yet” — the key is still checked with Dodo, but the app
# cannot confirm it belongs to this OS product.
DODO_PRODUCT_MAC = os.environ.get(
    "EYERHYTHM_DODO_PRODUCT_MAC", "pdt_0Nmc1Cv8LQYff3wqM6ULl"
).strip()
DODO_PRODUCT_WINDOWS = os.environ.get(
    "EYERHYTHM_DODO_PRODUCT_WINDOWS", "pdt_0Nmc1TZ9g5VKLY81Xi6pG"
).strip()

_ENFORCEMENT: bool | None = None


class LicenseError(Exception):
    """User-facing activation failure (bad key, wrong OS, network, …)."""


class LicenseNetworkError(LicenseError):
    """Dodo Payments could not be reached."""


def set_enforcement(required: bool | None) -> None:
    """Override whether a key is required (CLI flags). ``None`` = default."""
    global _ENFORCEMENT
    _ENFORCEMENT = required


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def is_required() -> bool:
    """True when this process must activate before the dashboard.

    Free by default, including PyInstaller freezes. Turn the gate on
    with ``--require-license`` or ``EYERHYTHM_REQUIRE_LICENSE=1``.
    """
    if _env_flag("EYERHYTHM_SKIP_LICENSE"):
        return False
    if _ENFORCEMENT is False:
        return False
    if _ENFORCEMENT is True:
        return True
    if _env_flag("EYERHYTHM_REQUIRE_LICENSE"):
        return True
    return False


def current_platform() -> str:
    """``mac``, ``windows``, or ``other`` (Linux / unknown)."""
    system = platform.system().lower()
    if system == "darwin":
        return "mac"
    if system == "windows":
        return "windows"
    return "other"


def dodo_api_base() -> str:
    override = os.environ.get("EYERHYTHM_DODO_API", "").strip()
    if override:
        return override.rstrip("/")
    if _env_flag("EYERHYTHM_DODO_TEST"):
        return DODO_TEST_API
    return DODO_LIVE_API


def expected_product_id() -> str:
    plat = current_platform()
    if plat == "mac":
        return DODO_PRODUCT_MAC
    if plat == "windows":
        return DODO_PRODUCT_WINDOWS
    return ""


def _license_path() -> Path:
    override = os.environ.get("EYERHYTHM_LICENSE_FILE", "").strip()
    return Path(override) if override else LICENSE_FILE


def normalize_key(raw: str) -> str:
    """Strip spaces; keep hyphens so Dodo sees the issued key."""
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
    """SHA-256 of the hardware id. This is what we send as the instance name."""
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


def _payload_message(payload: dict[str, Any]) -> str:
    for key in ("message", "error", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
            if isinstance(first, dict):
                nested = _payload_message(first)
                if nested:
                    return nested
    return ""


def _post_json(
    url: str, fields: dict[str, str], timeout: float = 20.0
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "EyesRhythm/2.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"error": "Unexpected response from checkout"}
            if not isinstance(parsed, dict):
                parsed = {"error": "Unexpected response from checkout"}
            return int(getattr(resp, "status", 200) or 200), parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        if not _payload_message(parsed) and raw.strip():
            parsed["error"] = raw.strip()
        return int(exc.code), parsed
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LicenseNetworkError(
            "Activation needs the internet. Connect and try again."
        ) from exc


def _dodo_call(action: str, fields: dict[str, str]) -> tuple[int, dict[str, Any]]:
    return _post_json(f"{dodo_api_base()}/licenses/{action}", fields)


def _product_id_from(payload: dict[str, Any]) -> str:
    product = payload.get("product")
    if isinstance(product, dict):
        return str(product.get("product_id") or "").strip()
    return str(payload.get("product_id") or "").strip()


def _reject_if_wrong_product(payload: dict[str, Any], key: str) -> None:
    product_id = _product_id_from(payload)
    expected = expected_product_id()
    if not expected or not product_id or product_id == expected:
        return
    instance_id = str(payload.get("id") or "").strip()
    if instance_id:
        try:
            _dodo_call(
                "deactivate",
                {
                    "license_key": key,
                    "license_key_instance_id": instance_id,
                },
            )
        except LicenseError:
            pass
    other = "Windows" if current_platform() == "mac" else "macOS"
    this = "macOS" if current_platform() == "mac" else "Windows"
    product = payload.get("product") if isinstance(payload.get("product"), dict) else {}
    hint = str((product or {}).get("name") or other)
    raise LicenseError(
        f"This key is for {hint}, not {this}. "
        "Each purchase is one operating system."
    )


def _friendly_dodo_error(status: int, payload: dict[str, Any]) -> str:
    err = _payload_message(payload)
    lowered = err.lower()
    if status == 404 or "not found" in lowered or "invalid" in lowered:
        return "That license key was not recognised. Check the email from checkout."
    if (
        status == 422
        or "activation limit" in lowered
        or "limit reached" in lowered
    ):
        return (
            "This key is already used on another computer. "
            "If you reinstalled, open the Dodo customer portal, "
            "deactivate the old machine, then try again."
        )
    if "expired" in lowered:
        return "This license key has expired."
    if status == 403 or "disabled" in lowered or "inactive" in lowered:
        return "This license key is no longer active."
    return err or "Checkout could not activate this key."


def activate(license_key: str) -> dict[str, Any]:
    """
    Call Dodo Payments, bind this machine, save locally.

    Subsequent launches read the local file and stay offline.
    """
    key = normalize_key(license_key)
    if not key:
        raise LicenseError("Paste the license key from your purchase email.")
    if len(key) < 8:
        raise LicenseError("That does not look like a license key.")

    fingerprint = machine_fingerprint()
    status_code, payload = _dodo_call(
        "activate",
        {"license_key": key, "name": fingerprint},
    )
    if status_code not in {200, 201} or not str(payload.get("id") or "").strip():
        raise LicenseError(_friendly_dodo_error(status_code, payload))

    _reject_if_wrong_product(payload, key)

    instance_id = str(payload.get("id") or "").strip()
    customer = (
        payload.get("customer")
        if isinstance(payload.get("customer"), dict)
        else {}
    )
    product = (
        payload.get("product")
        if isinstance(payload.get("product"), dict)
        else {}
    )

    record = {
        "license_key": key,
        "instance_id": instance_id,
        "instance_name": fingerprint,
        "platform": current_platform(),
        "customer_email": str((customer or {}).get("email") or ""),
        "product_name": str((product or {}).get("name") or ""),
        "product_id": _product_id_from(payload),
        "provider": "dodo",
        "activated_at": _utc_now(),
    }
    try:
        _save_local(record)
    except OSError as exc:
        raise LicenseError("Could not save the license on this computer.") from exc
    return status()
