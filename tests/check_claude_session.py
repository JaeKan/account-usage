"""Run with Hermes Python, from the Hermes source directory."""
from unittest.mock import patch
import httpx
from agent import account_usage as usage

payload = {'five_hour': {'utilization': 0, 'resets_at': None},
           'seven_day': {'utilization': 0, 'resets_at': None},
           'seven_day_sonnet': {'utilization': 0, 'resets_at': None}}
response = httpx.Response(200, json=payload, request=httpx.Request('GET', 'https://api.anthropic.com/api/oauth/usage'))
with patch.object(usage, 'resolve_anthropic_token', return_value='test'), patch.object(usage, '_is_oauth_token', return_value=True), patch.object(usage, '_fetch_anthropic_plan', return_value=None), patch.object(httpx.Client, 'get', return_value=response):
    result = usage.fetch_account_usage('anthropic')
assert [(w.label, w.used_percent) for w in result.windows] == [('Session', 0), ('Weekly', 0)]
print('CLAUDE_ZERO_SESSION_OK')
