"""Run from Hermes source with its Python: read-only backend contract checks."""
import ast
from pathlib import Path
from unittest.mock import patch
import httpx
from agent import account_usage as usage

# Execute the real RPC handler without starting a gateway.
tree = ast.parse(Path('tui_gateway/methods_session.py').read_text(encoding='utf-8'))
handler = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and any(isinstance(d, ast.Call) and d.args and isinstance(d.args[0], ast.Constant) and d.args[0].value == 'account.usage' for d in n.decorator_list))
handler.decorator_list = []
scope = {'_ok': lambda rid, value: value, '_err': lambda *args: {'error': args}}
exec(compile(ast.Module(body=[handler], type_ignores=[]), '<account.usage>', 'exec'), scope)
with patch.object(usage, 'fetch_account_usage', return_value=None) as fetch:
    assert scope['_'](1, {'provider': 'cursor'})['cards'][0]['provider'] == 'cursor'
    assert fetch.call_args_list[0].args == ('cursor',)
    assert fetch.call_count == 1
    assert 'error' in scope['_'](1, {'provider': '../invalid'})
    assert fetch.call_count == 1

payload = {'rate_limit': {}, 'rate_limit_reset_credits': {'available_count': 2, 'applicable_available_count': 0}}
def get(client, url, **kwargs):
    return httpx.Response(200, json=payload, request=httpx.Request('GET', url))
with patch.object(usage, '_resolve_codex_usage_credentials', return_value=('test', '', None)), patch.object(httpx.Client, 'get', get):
    result = usage.fetch_account_usage('openai-codex')
# Banked resets surface as a details line.
assert any('2 resets banked' in d for d in result.details)
# Cursor + Antigravity wiring must survive Hermes updates (wiped 2026-09-11).
assert {"cursor", "antigravity"} <= set(usage._USAGE_FETCHERS)
# A pool entry in chat-call cooldown must still be used (force-refreshed) for
# the read-only /usage probe, never trusted-stale (cached 429 can be wrong —
# real quota refills before the reported ETA; observed 2026-09-14).
class _FakeCooldownEntry:
    runtime_api_key = 'cooldown-token'
    runtime_base_url = ''
    last_status = 'exhausted'
class _FakePool:
    def select(self):
        return None
    def _find(self, predicate):
        return _FakeCooldownEntry() if predicate(_FakeCooldownEntry()) else None
    def _refresh_entry(self, entry, force):
        return entry
with patch('agent.credential_pool.load_pool', return_value=_FakePool()), \
     patch.object(usage, 'resolve_codex_runtime_credentials', side_effect=usage.AuthError('no creds', code='codex_auth_missing')):
    token, _, _ = usage._resolve_codex_usage_credentials(None, None)
assert token == 'cooldown-token'
print('RPC_ISOLATION_AND_RESET_CREDITS_OK')
