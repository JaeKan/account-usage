"""Antigravity quota via `agy -p /usage --output-format json` (verified live 2026-09-07).

`agy status` does NOT exist as a CLI subcommand; quota comes from the
`/usage` slash command. JSON mode exposes structured `groups[].buckets[]`
(id, name, window, remaining_fraction, reset_time) -- richer than the TSV
text mode this module used to parse, and avoids re-deriving reset_time from
a locale-formatted string.

No plan/tier name is exposed anywhere in the CLI (`/credits`, `/config`,
`/help`, or this endpoint) -- observed strings are generic
("your individual tier", "supported paid plan"), not a product name. Do
not fabricate one; `plan` stays None until Google ships a real field.
"""
from __future__ import annotations

import json
import subprocess
import time
from typing import Any

# ponytail: process-global TTL cache, not per-instance -- this module has no
# instance boundary (fetch_account_usage is a bare function), and the whole
# point is to survive across independent polls from the same process.
_AGY_USAGE_CACHE: dict[str, Any] = {"value": None, "at": 0.0}
_AGY_USAGE_CACHE_TTL_SECONDS = 50


def _parse_agy_usage_json(output: str) -> list[dict[str, Any]]:
    """Parse `agy -p /usage --output-format json` into Session/Weekly windows.

    The Gemini scope drives the statusbar chip, so it always comes first with
    bare Session/Weekly labels (the plugin keys the chip off exact 'Session').
    Other scopes (e.g. Claude & GPT models) follow, session-then-weekly.
    """
    try:
        payload = json.loads(output)
    except (ValueError, TypeError):
        return []
    groups = ((payload.get("command") or {}).get("data") or {}).get("groups") or []
    rows: list[tuple[str, str, float, str | None]] = []
    for group in groups:
        scope = str(group.get("name") or "").strip()
        if not scope:
            continue
        for bucket in group.get("buckets") or []:
            if bucket.get("disabled"):
                continue  # e.g. Claude/GPT 5h window disabled while its weekly limit is hit
            fraction = bucket.get("remaining_fraction")
            window = str(bucket.get("window") or "")
            kind = "session" if window == "5h" else ("weekly" if window == "weekly" else None)
            if kind is None or not isinstance(fraction, (int, float)):
                continue
            used = max(0.0, min(100.0, 100.0 - float(fraction) * 100.0))
            rows.append((scope, kind, used, bucket.get("reset_time")))
    rows.sort(key=lambda r: (0 if "gemini" in r[0].lower() else 1, 0 if r[1] == "session" else 1))
    windows: list[dict[str, Any]] = []
    for scope, kind, used, reset in rows:
        lowered = scope.lower()
        if "gemini" in lowered:
            label = kind.title()
        elif "claude" in lowered:
            label = f"{kind.title()} · Claude & GPT"
        else:
            label = f"{kind.title()} · {scope}"
        windows.append({"label": label, "used_percent": used, "reset_at": reset or None})
    return windows


def fetch_antigravity_usage() -> dict[str, Any] | None:
    """Run `agy -p /usage --output-format json` and parse quota rows into usage windows.

    Cached briefly: the `agy` subprocess costs ~7s to start every call (Node
    CLI cold start, not quota freshness), so a bare subprocess-per-poll makes
    every 60s statusbar refresh pay that cost again. TTL just under the
    plugin's REFRESH_MS keeps quota fresh across the interval that matters
    while making every poll but the first cheap.
    """
    now = time.monotonic()
    cached = _AGY_USAGE_CACHE.get("value")
    if cached is not None and now - _AGY_USAGE_CACHE["at"] < _AGY_USAGE_CACHE_TTL_SECONDS:
        return cached
    try:
        result = subprocess.run(
            ["agy", "-p", "/usage", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        windows = _parse_agy_usage_json(result.stdout or "")
        value = {"windows": windows} if windows else None
        _AGY_USAGE_CACHE["value"] = value
        _AGY_USAGE_CACHE["at"] = now
        return value
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None
