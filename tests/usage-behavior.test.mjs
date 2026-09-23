import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
const source = readFileSync(new URL('../plugin.js', import.meta.url), 'utf8')
const executable = source.replace(/import[\s\S]*?from '[^']+'\s*/g, '').replace('export default {', 'const plugin = {')
const render = (type, props) => ({ type, ...props })
const ctx = vm.createContext({ jsx: render, jsxs: render, useState: () => [false, () => {}], useRef: () => ({}), cn: (...x) => x.join(' '), useQuery: () => ({ data: { cards: [] } }), host: {}, setTimeout, clearTimeout })
vm.runInContext(executable, ctx)
test('Claude null reset shows no reset line; valid reset is rendered', () => {
  assert.doesNotMatch(JSON.stringify(vm.runInContext("WindowRow({provider:'anthropic',w:{label:'Session',used_percent:0}})", ctx)), /resets/)
  assert.doesNotMatch(JSON.stringify(vm.runInContext("WindowRow({provider:'anthropic',w:{label:'Session',used_percent:5,reset_at:'2026-09-10T10:00:00Z'}})", ctx)), /not provided/)
})
test('Antigravity label and owner-confirmed Codex plan', () => {
  assert.match(JSON.stringify(vm.runInContext("providerTooltip({provider:'antigravity',available:true,plan:'AI Pro',windows:[{label:'Session'}]})", ctx)), /Antigravity/)
  assert.match(JSON.stringify(vm.runInContext("providerTooltip({provider:'openai-codex',available:true,plan:'Team',windows:[]})", ctx)), /Business Standard/)
})
test('provider queries are independent and placeholders mount immediately', () => {
  let options
  ctx.useQuery = value => { options = value; return {} }
  const result = vm.runInContext("ProviderUsageChip({provider:'cursor'})", ctx)
  assert.equal(result.provider, 'cursor')
  assert.equal(options.queryKey[1], 'cursor')
  ctx.host.request = (method, args) => { assert.equal(args.provider, 'cursor'); return method }
  assert.equal(options.queryFn(), 'account.usage')
})
test('upstream shapes: Claude chip = Current session (not week), OpenRouter details panel', () => {
  const chip = vm.runInContext("chipEntryFor({provider:'anthropic',available:true,windows:[{label:'Current session',used_percent:5},{label:'Current week',used_percent:22}]})", ctx)
  assert.equal(chip.text, '5%')
  const tip = JSON.stringify(vm.runInContext("const t = providerTooltip({provider:'openrouter',available:true,windows:[{label:'API key quota',used_percent:22.8,detail:'$23.15 of $30.00 remaining • resets monthly'}],details:['Credits balance: $13.60','API key usage: $35.40 total • $0.33 today • $6.85 this month']}); OpenRouterTooltip(t)", ctx))
  for (const t of ['Credits balance', '$13.60', 'Used (all time)', '$35.40', 'Used today', 'Used this month', '$6.85 used', '$23.15 left']) assert.ok(tip.includes(t), t)
})
test('OpenRouter chip = lower of credits balance and key quota', () => {
  const chip = vm.runInContext("chipEntryFor({provider:'openrouter',available:true,windows:[{label:'API key quota',detail:'$23.15 of $30.00 remaining'}],details:['Credits balance: $13.60']})", ctx)
  assert.equal(chip.text, '$13.60 left')
})
