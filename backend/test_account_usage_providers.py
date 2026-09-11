"""Tight checks for cursor/antigravity/codex usage wiring (no network)."""

import json

from agent.antigravity_usage_fetcher import _parse_agy_usage_json


def test_agy_usage_json_parses_remaining_fraction_into_used():
    payload = json.dumps({
        "command": {"data": {"groups": [
            {"name": "Gemini Models", "buckets": [
                {"window": "weekly", "remaining_fraction": 0.83, "reset_time": "2026-09-11T00:21:15Z"},
                {"window": "5h", "remaining_fraction": 0.97, "reset_time": "2026-09-04T13:14:20Z"},
            ]},
            {"name": "Claude and GPT models", "buckets": [
                {"window": "weekly", "remaining_fraction": 0.0, "reset_time": "2026-09-07T02:55:30Z"},
                {"window": "5h", "disabled": True},
            ]},
        ]}}
    })
    windows = _parse_agy_usage_json(payload)
    assert [w["label"] for w in windows] == ["Session", "Weekly", "Weekly · Claude & GPT"]
    assert windows[0]["used_percent"] == 3.0
    assert windows[1]["used_percent"] == 17.0
    assert windows[2]["used_percent"] == 100.0


def test_codex_cooldown_with_no_prior_snapshot_returns_none(monkeypatch):
    from agent import account_usage as au

    def _limited(*args, **kwargs):
        raise au.CodexQuotaCooldown(300)

    monkeypatch.setattr(au, "_resolve_codex_usage_credentials", _limited)
    monkeypatch.setattr(au, "_LAST_CODEX_SNAPSHOT", None)
    assert au.fetch_account_usage("openai-codex") is None


def test_codex_cooldown_reshows_previous_popover_unchanged(monkeypatch):
    from agent.account_usage import (
        AccountUsageSnapshot,
        AccountUsageWindow,
        _utc_now,
        fetch_account_usage,
    )
    import agent.account_usage as au

    prev = AccountUsageSnapshot(
        provider="openai-codex",
        source="usage_api",
        fetched_at=_utc_now(),
        plan="Plus",
        windows=(
            AccountUsageWindow(label="Session", used_percent=42.0),
            AccountUsageWindow(label="Weekly", used_percent=10.0),
        ),
    )

    def _limited(*args, **kwargs):
        raise au.CodexQuotaCooldown(300)

    monkeypatch.setattr(au, "_resolve_codex_usage_credentials", _limited)
    monkeypatch.setattr(au, "_LAST_CODEX_SNAPSHOT", prev)
    # Popover must be byte-identical to the last real fetch -- no synthetic
    # 100%/"rate limited" text injected over it.
    assert fetch_account_usage("openai-codex") is prev
