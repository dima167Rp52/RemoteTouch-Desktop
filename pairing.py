"""Local pairing and session management for RemoteTouch Desktop.

Only device identifiers and display names are persisted. Session tokens are
short-lived, random, and kept in memory. This module never stores the pairing
PIN or session tokens on disk.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import uuid
from pathlib import Path


SESSION_TTL = 12 * 60 * 60
REQUEST_TTL = 3 * 60
MAX_PENDING = 20


def _data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        path = Path(root) / "RemoteTouch"
    else:
        path = Path.home() / ".remotetouch"
    path.mkdir(parents=True, exist_ok=True)
    return path


class PairingManager:
    """Thread-safe pairing queue, trusted-device store, and session registry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._trusted_path = _data_dir() / "trusted_devices.json"
        self._settings_path = _data_dir() / "settings.json"
        self._trusted = self._load_trusted()
        self._pending: dict[str, dict] = {}
        self._sessions: dict[str, dict] = {}
        self._auto_allow_trusted = self._load_auto_allow()

    def _load_trusted(self) -> dict[str, dict]:
        try:
            data = json.loads(self._trusted_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_trusted(self) -> None:
        self._trusted_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._trusted_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._trusted, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self._trusted_path)

    def _load_auto_allow(self) -> bool:
        try:
            data = json.loads(self._settings_path.read_text(encoding="utf-8"))
            return bool(data.get("auto_allow_trusted", False))
        except (OSError, json.JSONDecodeError, AttributeError):
            return False

    def _save_settings(self) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._settings_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"auto_allow_trusted": self._auto_allow_trusted},
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self._settings_path)

    @staticmethod
    def _clean_name(value: object) -> str:
        name = " ".join(str(value or "Устройство").split())
        return name[:48] or "Устройство"

    @staticmethod
    def _clean_device_id(value: object) -> str:
        raw = str(value or "")
        try:
            return str(uuid.UUID(raw))
        except (ValueError, TypeError, AttributeError):
            return ""

    def set_auto_allow_trusted(self, enabled: bool) -> None:
        with self._lock:
            self._auto_allow_trusted = bool(enabled)
            self._save_settings()

    def auto_allow_trusted(self) -> bool:
        with self._lock:
            return self._auto_allow_trusted

    def request_pairing(self, device_id: object, device_name: object) -> dict:
        device_id = self._clean_device_id(device_id)
        if not device_id:
            raise ValueError("Некорректный идентификатор устройства")

        name = self._clean_name(device_name)
        now = time.time()

        with self._lock:
            self._expire_locked(now)

            for request_id, request in self._pending.items():
                if request["device_id"] == device_id:
                    request["device_name"] = name
                    return {"request_id": request_id, "status": "pending"}

            if len(self._pending) >= MAX_PENDING:
                raise RuntimeError("Слишком много запросов на подключение")

            if device_id in self._trusted and self._auto_allow_trusted:
                token = self._new_session_locked(device_id, name, now)
                return {"status": "approved", "session_token": token}

            request_id = secrets.token_urlsafe(18)
            self._pending[request_id] = {
                "request_id": request_id,
                "device_id": device_id,
                "device_name": name,
                "created_at": now,
                "status": "pending",
                "session_token": "",
            }
            return {"request_id": request_id, "status": "pending"}

    def pending_requests(self) -> list[dict]:
        with self._lock:
            self._expire_locked(time.time())
            return [
                {
                    "request_id": item["request_id"],
                    "device_id": item["device_id"],
                    "device_name": item["device_name"],
                    "created_at": item["created_at"],
                }
                for item in self._pending.values()
                if item["status"] == "pending"
            ]

    def approve(self, request_id: str, trust_device: bool = False) -> bool:
        with self._lock:
            self._expire_locked(time.time())
            request = self._pending.get(str(request_id))
            if not request or request["status"] != "pending":
                return False

            now = time.time()
            request["session_token"] = self._new_session_locked(
                request["device_id"], request["device_name"], now
            )
            request["status"] = "approved"

            if trust_device:
                self._trusted[request["device_id"]] = {
                    "name": request["device_name"],
                    "added_at": int(now),
                }
                self._save_trusted()
            return True

    def deny(self, request_id: str) -> bool:
        with self._lock:
            request = self._pending.get(str(request_id))
            if not request or request["status"] != "pending":
                return False
            request["status"] = "denied"
            return True

    def pairing_status(self, request_id: str) -> dict:
        with self._lock:
            self._expire_locked(time.time())
            request = self._pending.get(str(request_id))
            if not request:
                return {"status": "expired"}
            if request["status"] == "approved":
                token = request["session_token"]
                request["status"] = "delivered"
                request["session_token"] = ""
                return {"status": "approved", "session_token": token}
            return {"status": request["status"]}

    def _new_session_locked(self, device_id: str, name: str, now: float) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = {
            "device_id": device_id,
            "device_name": name,
            "created_at": now,
            "expires_at": now + SESSION_TTL,
        }
        return token

    def authenticate(self, token: str) -> bool:
        if not token or len(token) > 256:
            return False
        with self._lock:
            session = self._sessions.get(token)
            if not session:
                return False
            if session["expires_at"] < time.time():
                self._sessions.pop(token, None)
                return False
            return True

    def revoke_device(self, device_id: str) -> bool:
        device_id = self._clean_device_id(device_id)
        if not device_id:
            return False
        with self._lock:
            existed = self._trusted.pop(device_id, None) is not None
            for token, session in list(self._sessions.items()):
                if session["device_id"] == device_id:
                    self._sessions.pop(token, None)
            if existed:
                self._save_trusted()
            return existed

    def trusted_devices(self) -> list[dict]:
        with self._lock:
            return [
                {"device_id": key, **value}
                for key, value in self._trusted.items()
            ]

    def _expire_locked(self, now: float) -> None:
        for request_id, request in list(self._pending.items()):
            if now - request["created_at"] > REQUEST_TTL:
                self._pending.pop(request_id, None)
        for token, session in list(self._sessions.items()):
            if session["expires_at"] < now:
                self._sessions.pop(token, None)
