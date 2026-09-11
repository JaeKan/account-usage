"""Re-apply the account-usage backend after a Hermes update (idempotent).

Why this exists: the plugin calls `host.request('account.usage', {provider})`,
which needs backend code inside the Hermes source tree. Hermes updates wipe
hand-edits there — that is how the chips broke after the 2026-09-11 restart.
This script is the single source of truth and covers everything:

1. New files synced into the tree (content-compared, never clobber foreign):
   - agent/cursor_usage_fetcher.py (Cursor dashboard API + local token discovery)
   - agent/antigravity_usage_fetcher.py (`agy -p /usage --output-format json`)
   - tests/agent/test_account_usage_providers.py (Hermes-side provider tests)
2. backend/hermes-customs.patch via `git apply` for tracked-file customs:
   account.usage RPC, _LONG_HANDLERS, codex/claude/openrouter fetchers,
   panes.tsx chip toggles. Already-applied is detected (skip); context drift
   fails LOUD so a silent half-patch is impossible.

Usage (Windows):
    python backend/reapply_account_usage.py [HERMES_AGENT_DIR]

Default HERMES_AGENT_DIR: %LOCALAPPDATA%\\hermes\\hermes-agent
(fallback ~/.hermes/hermes-agent). Then restart Hermes and verify from the
hermes-agent dir:
    python <plugin>/tests/check_backend_contract.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PATCH_NAME = "hermes-customs.patch"

# tree path -> backend/ source of truth
NEW_FILES = {
    "agent/cursor_usage_fetcher.py": "cursor_usage_fetcher.py",
    "agent/antigravity_usage_fetcher.py": "antigravity_usage_fetcher.py",
    "tests/agent/test_account_usage_providers.py": "test_account_usage_providers.py",
}

# Unique docstring line per file: a foreign file at the same path is never overwritten.
MARKERS = {
    "cursor_usage_fetcher.py": "Cursor's undocumented current-period usage endpoint.",
    "antigravity_usage_fetcher.py": "Antigravity quota via `agy -p /usage",
    "test_account_usage_providers.py": "account_usage",
}


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _git(root: Path, *args: str):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def main() -> int:
    root = _hermes_agent_dir()
    backend_dir = Path(__file__).resolve().parent
    if not (root / ".git").is_dir():
        print(f"not a git checkout: {root}")
        return 2

    changed = []
    for tree_rel, src_name in NEW_FILES.items():
        src, dst = backend_dir / src_name, root / tree_rel
        if not src.is_file():
            print(f"missing source of truth: {src}")
            return 2
        if dst.is_file():
            existing = _read(dst)
            if existing == _read(src):
                print(f"{tree_rel}: already in sync, skip")
                continue
            if MARKERS[src_name] not in existing:
                print(f"{tree_rel}: foreign file present, NOT overwriting — resolve manually")
                continue
        _write(dst, _read(src))
        changed.append(tree_rel)

    patch = backend_dir / PATCH_NAME
    if _git(root, "apply", "-R", "--check", str(patch)).returncode == 0:
        print(f"{PATCH_NAME}: already applied, skip")
    else:
        check = _git(root, "apply", "--check", str(patch))
        if check.returncode != 0:
            print(f"{PATCH_NAME}: does NOT apply cleanly — Hermes source moved. Output:\n{check.stderr.strip()}")
            return 2
        applied = _git(root, "apply", str(patch))
        if applied.returncode != 0:
            print(f"{PATCH_NAME}: apply failed:\n{applied.stderr.strip()}")
            return 2
        changed.append(PATCH_NAME)

    print(f"done: {', '.join(changed) if changed else 'nothing to do'} — restart Hermes, then run check_backend_contract.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
