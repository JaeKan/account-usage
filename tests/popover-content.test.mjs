import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
import test from 'node:test'
const source = readFileSync(new URL('../plugin.js', import.meta.url), 'utf8')
const context = vm.createContext({ jsx: (type, props) => typeof type === 'function' ? type(props) : props, jsxs: (type, props) => typeof type === 'function' ? type(props) : props })
vm.runInContext(source.replace(/import[\s\S]*?from ['"][^'"]+['"]/g, '').replace('export default', 'const plugin ='), context)
const render = card => { context.card = card; return JSON.stringify(vm.runInContext('providerTooltip(card)', context)) }
test('Cursor always lists both buckets without inventing missing usage', () => {
  const out = render({ provider: 'cursor', available: true, plan: 'Pro', windows: [{ label: 'Cursor Models', used_percent: 8 }, { label: 'Other Models', used_percent: 65 }] })
  assert.ok(out.includes('Other Models') && out.includes('65.0%'))
  assert.ok(render({ provider: 'cursor', available: true, windows: [] }).includes('Usage unavailable'))
})
test('Codex retains plan and windows but summarizes resets', () => {
  const out = render({ provider: 'openai-codex', available: true, plan: 'Plus', windows: [{label: 'Session', used_percent: 100}, {label: 'Weekly', used_percent: 20}, {label: 'Limit resets', detail: '3 available · 1 applicable now'}, {label: 'Bonus', detail: 'Granted: yesterday · Expires: tomorrow'}] })
  for (const text of ['Plan: Plus', 'Session', 'Weekly', '3 available']) assert.ok(out.includes(text))
  for (const text of ['Granted:', 'Expires:', 'applicable now']) assert.ok(!out.includes(text))
})
test('navigation uses spending URL and has no Antigravity target', () => {
  assert.equal(vm.runInContext('PROVIDER_USAGE_URL.cursor', context), 'https://cursor.com/dashboard/spending')
  assert.equal(vm.runInContext('PROVIDER_USAGE_URL.antigravity', context), undefined)
})
