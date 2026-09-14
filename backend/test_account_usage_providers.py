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
