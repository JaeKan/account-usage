import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
const source = readFileSync(new URL('../plugin.js', import.meta.url), 'utf8')
test('Cursor opens spending; Antigravity never opens an external page', () => {
  const links = source.match(/const PROVIDER_USAGE_URL = (\{[\s\S]*?\n\})/)[1]
  const fn = source.slice(source.indexOf('function openUsage('), source.indexOf('// VS Code Codicons'))
  const opened = []
  const context = vm.createContext({ opened })
  vm.runInContext(`const PROVIDER_USAGE_URL = ${links}; const openExternalFn = url => opened.push(url); ${fn}; openUsage('cursor'); openUsage('antigravity');`, context)
  assert.deepEqual(opened, ['https://cursor.com/dashboard/spending'])
})
