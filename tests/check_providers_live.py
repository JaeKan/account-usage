import importlib.util

_spec = importlib.util.spec_from_file_location(
    "_account_usage_provider_tests", "tests/agent/test_account_usage_providers.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_mod.test_agy_usage_json_parses_remaining_fraction_into_used()

from agent.account_usage import fetch_account_usage
c = fetch_account_usage('cursor')
print('cursor:', [(w.label, round(w.used_percent, 1)) for w in c.windows], c.plan)
a = fetch_account_usage('antigravity')
print('antigravity:', a.plan, [(w.label, round(w.used_percent, 1)) for w in a.windows])
print('PROVIDER_TESTS_OK')
