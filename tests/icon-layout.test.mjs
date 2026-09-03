import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../plugin.js', import.meta.url), 'utf8')

test('statusbar provider glyphs use the measured optical vertical offsets', () => {
  assert.match(
    source,
    /const ICON_OPTICAL_OFFSET_Y = \{\s*'openai-codex': 1,\s*anthropic: 1,\s*openrouter: 0\.5\s*\}/
  )
  assert.match(source, /transform: `translateY\(\$\{ICON_OPTICAL_OFFSET_Y\[provider\] \?\? 0}px\)`/)
})

test('registers one independent statusbar chip for each usage provider', () => {
  for (const provider of ['openai-codex', 'anthropic', 'openrouter']) {
    assert.match(source, new RegExp(`id: '${provider}-usage'`))
    assert.match(source, new RegExp(`jsx\\(ProviderUsageChip, \\{ provider: '${provider}' \\}\\)`))
  }

  assert.doesNotMatch(source, /function UsageChip\(/)
})

test('hover shows the full breakdown popover', () => {
  assert.match(source, /function providerTooltip\(card\)/)
  assert.match(source, /children: providerTooltip\(card\)/)
  assert.match(source, /jsx\(Popover,/)
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
