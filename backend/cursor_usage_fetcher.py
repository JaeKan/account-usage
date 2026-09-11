"""Cursor's undocumented current-period usage endpoint."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

_URL = "https://api2.cursor.sh/aiserver.v1.DashboardService/GetCurrentPeriodUsage"


def find_cursor_access_token() -> str | None:
    for path in _legacy_cursor_auth_paths():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            token = data.get("accessToken")
            if isinstance(token, str) and token.strip():
                return token.strip()
        except (OSError, ValueError, TypeError):
            continue
    # Current Cursor builds keep auth in SQLite global storage, not the
    # legacy cursorAuth file (verified: cursorAuth/accessToken in state.vscdb).
    for db_path in _state_vscdb_paths():
        token = _read_state_vscdb_token(db_path)
        if token:
            return token
    return None


def _legacy_cursor_auth_paths() -> list[Path]:
    appdata = os.environ.get("APPDATA")
    return [
        p
        for p in (
            Path(appdata) / "Cursor/User/globalStorage/cursor.io.cursor/cursorAuth" if appdata else None,
            Path.home() / "AppData/Roaming/Cursor/User/globalStorage/cursor.io.cursor/cursorAuth",
            Path.home() / "Library/Application Support/Cursor/User/globalStorage/cursor.io.cursor/cursorAuth",
            Path.home() / ".config/Cursor/User/globalStorage/cursor.io.cursor/cursorAuth",
        )
        if p is not None
    ]


def _state_vscdb_paths() -> list[Path]:
    home = Path.home()
    appdata = os.environ.get("APPDATA")
    return [
        p
        for p in (
            Path(appdata) / "Cursor/User/globalStorage/state.vscdb" if appdata else None,
            home / "AppData/Roaming/Cursor/User/globalStorage/state.vscdb",
            home / "Library/Application Support/Cursor/User/globalStorage/state.vscdb",
            home / ".config/Cursor/User/globalStorage/state.vscdb",
        )
        if p is not None
    ]


def _read_state_vscdb_value(db_path: Path, key: str) -> str | None:
    try:
        import sqlite3

        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=2)
        try:
            row = conn.execute("SELECT value FROM ItemTable WHERE key=?", (key,)).fetchone()
        finally:
            conn.close()
        if not row or not isinstance(row[0], str):
            return None
        text = row[0].strip()
        if len(text) > 1 and text.startswith('"') and text.endswith('"'):
            try:
                text = json.loads(text)
            except ValueError:
                pass
        return text.strip() if isinstance(text, str) and text.strip() else None
    except Exception:
        return None


def _read_state_vscdb_token(db_path: Path) -> str | None:
    return _read_state_vscdb_value(db_path, "cursorAuth/accessToken")


def find_cursor_plan() -> str | None:
    """Membership tier from local Cursor storage (e.g. pro -> Pro)."""
    for db_path in _state_vscdb_paths():
        raw = _read_state_vscdb_value(db_path, "cursorAuth/stripeMembershipType")
        if raw:
            return {"pro": "Pro", "team": "Team", "business": "Business", "enterprise": "Enterprise"}.get(
                raw.strip().lower(), raw.strip().title()
            )
    return None


def fetch_cursor_usage() -> dict[str, Any] | None:
    try:
        token = find_cursor_access_token()
        if not token:
            return None
        response = requests.post(
            _URL,
            json={},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Connect-Protocol-Version": "1"},
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json() or {}
        plan_usage = payload.get("planUsage") or {}
        total = plan_usage.get("totalPercentUsed")
        if not isinstance(total, (int, float)):
            return None
        return {
            "totalPercentUsed": total,
            "autoPercentUsed": plan_usage.get("autoPercentUsed"),
            "apiPercentUsed": plan_usage.get("apiPercentUsed"),
            "billingCycleEnd": payload.get("billingCycleEnd"),
            "plan": find_cursor_plan(),
        }
    except Exception:
        return None
