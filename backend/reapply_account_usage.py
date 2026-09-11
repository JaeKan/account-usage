"""Re-apply the account.usage gateway RPC after a Hermes update (idempotent).

Why this exists: the plugin calls `host.request('account.usage', {provider})`,
which needs a handler inside the Hermes source tree
(`tui_gateway/methods_session.py` + a `_LONG_HANDLERS` entry in
`tui_gateway/server.py`). Hermes updates wipe hand-edits there — that is
exactly how the chips broke after the 2026-09-11 restart. This script is the
single source of truth for that handler: re-run it after every Hermes update,
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
    for p in (session_file, server_file):
        if not p.is_file():
            print(f"missing: {p} (hermes-agent dir: {root})")
            return 2

    changed = []
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
