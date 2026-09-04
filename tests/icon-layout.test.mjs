import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../plugin.js', import.meta.url), 'utf8')

test('statusbar provider glyphs use the measured optical vertical offsets', () => {
  assert.match(
    source,
    /const ICON_OPTICAL_OFFSET_Y = \{\s*'openai-codex': 1,\s*anthropic: 1,\s*openrouter: 0\.5,\s*antigravity: 0\.5,\s*cursor: 0\.5\s*\}/
  )
  assert.doesNotMatch(source, /\.svg\?raw/)
  assert.match(source, /transform: `translateY\(\$\{ICON_OPTICAL_OFFSET_Y\[provider\] \?\? 0}px\)`/)
})

test('registers one independent statusbar chip for each usage provider', () => {
  for (const provider of ['openai-codex', 'anthropic', 'openrouter']) {
    assert.match(source, new RegExp(`id: '${provider}-usage'`))
    assert.match(source, new RegExp(`jsx\\(ProviderUsageChip, \\{ provider: '${provider}' \\}\\)`))
  }

  assert.doesNotMatch(source, /function UsageChip\(/)
})

test('registers chips in the requested statusbar order', () => {
  const ids = ['openai-codex-usage', 'anthropic-usage', 'cursor-usage', 'antigravity-usage', 'openrouter-usage']
  const positions = ids.map(id => source.indexOf(`id: '${id}'`))
  assert.ok(positions.every(position => position >= 0))
  assert.deepEqual(positions, [...positions].sort((a, b) => a - b))
})

test('uses web-sourced mono SVG paths for Cursor and Antigravity', () => {
  assert.match(source, /thesvg \(MIT\)/)
  assert.match(source, /M11\.503\.131 1\.891 5\.678/)
  assert.match(source, /M21\.751 22\.607c1\.34 1\.005/)
})

test('shows a visible loading placeholder before the first account RPC resolves', () => {
  assert.match(source, /function UsageChipPlaceholder\(\{ provider, isError \}\)/)
  assert.match(source, /if \(!card\) return jsx\(UsageChipPlaceholder, \{ provider, isError \}\)/)
  assert.match(source, /usage loading/)
})

test('hover shows the full breakdown popover', () => {
  assert.match(source, /function providerTooltip\(card\)/)
  assert.match(source, /children: providerTooltip\(card\)/)
  assert.match(source, /jsx\(Popover,/)
})

test('openrouter tooltip never calls toFixed on a null used amount', () => {
  assert.match(source, /const hasUsed = amounts\.used != null/)
  assert.doesNotMatch(source, /children: `\$\$\{amounts\.used\.toFixed\(2\)\} used` \}\),\n            jsx\('span', \{ className: 'tabular-nums text-foreground', children: `\$\$\{amounts\.remaining\.toFixed\(2\)\} left` \}\)\n          \]\n        \}\),\n        jsx\('div', \{\n          className: 'h-1 w-full overflow-hidden rounded-full/)
})

test('chip click opens the provider usage page in a new window', () => {
  assert.match(source, /openExternalFn = ctx\.os\.openExternal/)
  assert.match(source, /openUsage\(provider\)/)
})

test('hover shows the popover, click opens the usage page', () => {
  assert.match(source, /onMouseEnter: \(\) => markHover\(true\)/)
  assert.match(source, /onMouseLeave: \(\) => markHover\(false\)/)
  assert.match(source, /onOpenChange: next =>/)
  assert.match(source, /setTimeout\(\(\) => setOpen\(false\), 150\)/)
  assert.match(source, /onCloseAutoFocus: e => e\.preventDefault\(\)/)
})

test('each chip is individually show/hide-toggleable in the statusbar menu', () => {
  assert.match(source, /data: \{ toggleLabel: 'Codex usage' \}/)
  assert.match(source, /data: \{ toggleLabel: 'Claude usage' \}/)
  assert.match(source, /data: \{ toggleLabel: 'OpenRouter usage' \}/)
})
