import types

def _mp():
    class MP:
        def __init__(self):
            self.saved = []
        def setattr(self, obj, name, value):
            self.saved.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)
    return MP()

from tests.agent.test_account_usage_providers import (
    test_agy_usage_json_parses_remaining_fraction_into_used,
    test_codex_cooldown_with_no_prior_snapshot_returns_none,
    test_codex_cooldown_reshows_previous_popover_unchanged,
)
test_agy_usage_json_parses_remaining_fraction_into_used()
test_codex_cooldown_with_no_prior_snapshot_returns_none(_mp())
test_codex_cooldown_reshows_previous_popover_unchanged(_mp())

from agent.account_usage import fetch_account_usage
c = fetch_account_usage('cursor')
print('cursor:', [(w.label, round(w.used_percent, 1)) for w in c.windows], c.plan)
a = fetch_account_usage('antigravity')
print('antigravity:', a.plan, [(w.label, round(w.used_percent, 1)) for w in a.windows])
print('PROVIDER_TESTS_OK')
