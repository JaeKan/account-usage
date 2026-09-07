import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
const source = readFileSync(new URL('../plugin.js', import.meta.url), 'utf8')
const executable = source.replace(/import[\s\S]*?from '[^']+'\s*/g, '').replace('export default {', 'const plugin = {')
const render = (type, props) => ({ type, ...props })
const ctx = vm.createContext({ jsx: render, jsxs: render, useState: () => [false, () => {}], useRef: () => ({}), cn: (...x) => x.join(' '), useQuery: () => ({ data: { cards: [] } }), host: {}, setTimeout, clearTimeout })
vm.runInContext(executable, ctx)
test('Claude null reset is explicit and valid reset is rendered', () => {
  assert.match(JSON.stringify(vm.runInContext("WindowRow({provider:'anthropic',w:{label:'Session',used_percent:0}})", ctx)), /not provided by API/)
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
