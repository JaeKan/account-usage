"""Re-apply the account.usage backend after a Hermes update (idempotent).

Why this exists: the plugin calls `host.request('account.usage', {provider})`,
which needs (1) a handler in `tui_gateway/methods_session.py` + a
`_LONG_HANDLERS` entry in `tui_gateway/server.py`, and (2) the Cursor /
Antigravity fetchers wired into `agent/account_usage.py`. Hermes updates wipe
all three — that is how the chips broke after the 2026-09-11 restart. This
script is the single source of truth: re-run it after every Hermes update,
then restart Hermes.

Usage (Windows):
    python backend/reapply_account_usage.py [HERMES_AGENT_DIR]

Default HERMES_AGENT_DIR: %LOCALAPPDATA%\\hermes\\hermes-agent
(fallback ~/.hermes/hermes-agent).

Verify from the hermes-agent dir:
    python <plugin>/tests/check_backend_contract.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROVIDERS = ("openai-codex", "anthropic", "cursor", "antigravity", "openrouter")

HANDLER = '''# account-usage plugin RPC (source of truth: desktop-plugins/account-usage/backend/reapply_account_usage.py — do not hand-edit).
@method("account.usage")
def _(rid, params: dict) -> dict:
    from agent import account_usage as _account_usage
    provider = str((params or {}).get("provider") or "").strip().lower()
    if provider not in ("openai-codex", "anthropic", "cursor", "antigravity", "openrouter"):
        return _err(rid, -32602, f"unknown provider: {provider!r}")
    snapshot = _account_usage.fetch_account_usage(provider)
    if snapshot is None:
        card = {
            "provider": provider, "available": False, "plan": None,
            "windows": [], "unavailable_reason": "usage unavailable",
        }
    else:
        card = {
            "provider": snapshot.provider,
            "available": snapshot.available,
            "plan": snapshot.plan,
            "windows": [
                {
                    "label": w.label,
                    "used_percent": w.used_percent,
                    "reset_at": w.reset_at.isoformat() if w.reset_at else None,
                    "detail": w.detail,
                }
                for w in snapshot.windows
            ],
            "unavailable_reason": snapshot.unavailable_reason,
        }
    return _ok(rid, {"cards": [card]})


'''

ANCHOR_SESSION = '@_session_method("session.context_breakdown")'
ANCHOR_LONG = '"session.usage", "billing.step_up"'
LONG_REPLACEMENT = '"session.usage", "account.usage", "billing.step_up"'

# Fetcher sources of truth live beside this script; the agent/ copies are
# synced below. Marker = our unique docstring line; a foreign file at the
# same path is never overwritten.
_FETCHER_MARKERS = {
    "cursor_usage_fetcher.py": "Cursor's undocumented current-period usage endpoint.",
    "antigravity_usage_fetcher.py": "Antigravity quota via `agy -p /usage",
}

WIRING_ANCHOR = "_USAGE_FETCHERS: dict"
WIRING_DICT_ANCHOR = '"openrouter": _fetch_openrouter_account_usage,\n}'
WIRING_DICT_REPLACEMENT = (
    '"openrouter": _fetch_openrouter_account_usage,\n'
    '    "cursor": _fetch_cursor_account_usage, "antigravity": _fetch_antigravity_account_usage,\n}'
)

WIRING_FUNCTIONS = '''# account-usage plugin providers (source of truth: desktop-plugins/account-usage/backend/reapply_account_usage.py — do not hand-edit).
def _fetch_cursor_account_usage(
    base_url: Optional[str] = None, api_key: Optional[str] = None,
) -> Optional[AccountUsageSnapshot]:
    try:
        from agent.cursor_usage_fetcher import fetch_cursor_usage

        usage = fetch_cursor_usage()
        if usage is None:
            return None
        try:
            reset_at = _parse_dt(float(usage["billingCycleEnd"]) / 1000)
        except (KeyError, TypeError, ValueError, OverflowError):
            reset_at = None
        return AccountUsageSnapshot(
            provider="cursor",
            source="cursor_dashboard_api",
            fetched_at=_utc_now(),
            plan=usage.get("plan"),
            windows=tuple(
                AccountUsageWindow(label=label, used_percent=float(usage[key]), reset_at=reset_at)
                for key, label in (("autoPercentUsed", "Cursor Models"), ("apiPercentUsed", "Other Models"))
                if isinstance(usage.get(key), (int, float)) and not isinstance(usage[key], bool) and math.isfinite(usage[key])
            ),
        )
    except Exception:
        # Undocumented endpoint: never let it break account.usage.
        return None


def _fetch_antigravity_account_usage(
    base_url: Optional[str] = None, api_key: Optional[str] = None,
) -> Optional[AccountUsageSnapshot]:
    try:
        from agent.antigravity_usage_fetcher import fetch_antigravity_usage

        usage = fetch_antigravity_usage()
        rows = (usage or {}).get("windows") or []
        windows = [
            AccountUsageWindow(
                label=str(w.get("label") or "Usage"),
                used_percent=float(w["used_percent"]),
                reset_at=_parse_dt(w.get("reset_at")),
            )
            for w in rows
            if isinstance(w.get("used_percent"), (int, float))
        ]
        if not windows:
            return None
        return AccountUsageSnapshot(
            provider="antigravity",
            source="agy_cli",
            fetched_at=_utc_now(),
            plan="Google AI Pro",  # No plan/tier field anywhere in `agy` CLI — owner-confirmed value.
            windows=tuple(windows),
        )
    except Exception:
        # agy CLI missing/failing: fail open for connection-only display.
        return None


'''


def _hermes_agent_dir() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    local = os.environ.get("LOCALAPPDATA")
    if local and (Path(local) / "hermes" / "hermes-agent").is_dir():
        return Path(local) / "hermes" / "hermes-agent"
    return Path.home() / ".hermes" / "hermes-agent"


def _read(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main() -> int:
    root = _hermes_agent_dir()
    session_file = root / "tui_gateway" / "methods_session.py"
    server_file = root / "tui_gateway" / "server.py"
    usage_file = root / "agent" / "account_usage.py"
    for p in (session_file, server_file, usage_file):
        if not p.is_file():
            print(f"missing: {p} (hermes-agent dir: {root})")
            return 2

    changed = []
    backend_dir = Path(__file__).resolve().parent
    agent_dir = root / "agent"
    for name, marker in _FETCHER_MARKERS.items():
        dst = agent_dir / name
        if dst.is_file():
            existing = _read(dst)
            if existing == _read(backend_dir / name):
                print(f"{name}: already in sync, skip")
                continue
            if marker not in existing:
                print(f"{name}: foreign file present, NOT overwriting — resolve manually")
                continue
        _write(dst, _read(backend_dir / name))
        changed.append(name)

    text = _read(usage_file)
    if "_fetch_cursor_account_usage" in text and "_fetch_antigravity_account_usage" in text:
        print("account_usage.py: already wired, skip")
    elif WIRING_ANCHOR not in text or WIRING_DICT_ANCHOR not in text:
        print("account_usage.py: anchor not found, Hermes source moved — update the script")
        return 2
    else:
        text = text.replace(WIRING_ANCHOR, WIRING_FUNCTIONS + WIRING_ANCHOR, 1)
        _write(usage_file, text.replace(WIRING_DICT_ANCHOR, WIRING_DICT_REPLACEMENT, 1))
        changed.append("account_usage.py")

    text = _read(session_file)
    if '"account.usage"' in text:
        print("methods_session.py: already applied, skip")
    elif ANCHOR_SESSION not in text:
        print("methods_session.py: anchor not found, Hermes source moved — update the script")
        return 2
    else:
        _write(session_file, text.replace(ANCHOR_SESSION, HANDLER + ANCHOR_SESSION, 1))
        changed.append("methods_session.py")

    text = _read(server_file)
    if '"account.usage"' in text:
        print("server.py: already applied, skip")
    elif ANCHOR_LONG not in text:
        print("server.py: anchor not found, Hermes source moved — update the script")
        return 2
    else:
        _write(server_file, text.replace(ANCHOR_LONG, LONG_REPLACEMENT, 1))
        changed.append("server.py (_LONG_HANDLERS)")

    print(f"done: {', '.join(changed) if changed else 'nothing to do'} — restart Hermes, then run check_backend_contract.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
