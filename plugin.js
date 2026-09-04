/**
 * Account Usage -- one statusbar chip + popover per provider (Codex / Anthropic /
 * OpenRouter) showing subscription quota via the account.usage gateway RPC
 * (tui_gateway/methods_session.py), which wraps the same
 * agent.account_usage.fetch_account_usage the /usage slash command uses.
 * Hover shows the full breakdown popover; click opens the provider usage page.
 */

import {
  cn,
  haptic,
  host,
  Popover,
  PopoverContent,
  PopoverTrigger,
  useQuery
} from '@hermes/plugin-sdk'
import { useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'account-usage'
// account.usage is a _LONG_HANDLER (serial HTTP round-trips per provider) --
// poll well under the "never faster than a few seconds" floor.
const REFRESH_MS = 60_000

const PROVIDERS = ['openai-codex', 'anthropic', 'openrouter']

const PROVIDER_LABEL = {
  'openai-codex': 'Codex',
  anthropic: 'Claude',
  openrouter: 'OpenRouter'
}

// Each provider's own usage page (fixed constants, no user input):
// Codex analytics (jdhodges guide), Claude settings usage (already
// referenced in agent/conversation_loop.py), OpenRouter Activity tab.
const PROVIDER_USAGE_URL = {
  'openai-codex': 'https://chatgpt.com/codex/cloud/settings/analytics',
  anthropic: 'https://claude.ai/settings/usage',
  openrouter: 'https://openrouter.ai/activity'
}

// Assigned in register(ctx) -- the sanctioned external-open door
// (ctx.os.openExternal, attributed to this plugin, never throws).
// Null until register runs (e.g. under node --test); openUsage guards it.
let openExternalFn = null

function openUsage(provider) {
  const url = PROVIDER_USAGE_URL[provider]
  if (!url) return
  if (openExternalFn) { void openExternalFn(url); return }
  const bridge = typeof window !== 'undefined' ? window.hermesDesktop : null
  if (bridge?.openExternal) { void bridge.openExternal(url); return }
  if (typeof window !== 'undefined') window.open(url, '_blank', 'noopener,noreferrer')
}
// VS Code Codicons ships official OpenAI and Claude marks. OpenRouter uses
// the exact user-supplied SVG (assets/openrouter.svg) as an inline path so it
// inherits the active theme color. Fixed 12px boxes align every mark to text.
const PROVIDER_CODICON = {
  'openai-codex': 'openai',
  anthropic: 'claude'
}

// Codicon brand marks have denser artwork than the supplied OpenRouter mark.
// Render them slightly smaller while retaining the same centered 12px box.
const PROVIDER_CODICON_SIZE = '10px'

// Pixel measurement from the statusbar capture: Codicon glyph artwork sits
// higher in its em box than the numeral glyphs; the supplied OpenRouter SVG
// is only half a pixel high. Offset only the paint, not flex layout.
const ICON_OPTICAL_OFFSET_Y = {
  'openai-codex': 1,
  anthropic: 1,
  openrouter: 0.5
}

const OPENROUTER_PATH = 'M18.654 3.87a5.087 5.087 0 110 10.174L23.7 19.09c.64.641.187 1.737-.72 1.737H8.48a8.479 8.479 0 010-16.958h10.175zM8.479 7.26a5.087 5.087 0 100 10.176 5.087 5.087 0 000-10.175z'

const ICON_BOX_STYLE = {
  alignItems: 'center',
  display: 'inline-flex',
  flex: '0 0 12px',
  height: 12,
  justifyContent: 'center',
  lineHeight: 1,
  verticalAlign: 'middle',
  width: 12
}

function pctColor(pct) {
  if (pct == null) return 'var(--ui-text-tertiary)'
  if (pct >= 90) return 'var(--ui-danger, #e5484d)'
  if (pct >= 70) return 'var(--ui-warning, #f5a524)'
  return 'var(--ui-accent)'
}

function ProviderIcon({ provider }) {
  const glyph = provider === 'openrouter'
    ? jsx('svg', {
        fill: 'currentColor',
        focusable: 'false',
        height: 12,
        style: { display: 'block' },
        viewBox: '0 0 24 24',
        width: 12,
        children: jsx('path', { d: OPENROUTER_PATH, fillRule: 'evenodd' })
      })
    : jsx('span', {
        className: `codicon codicon-${PROVIDER_CODICON[provider] ?? 'circle'}`,
        style: { display: 'block', fontSize: PROVIDER_CODICON_SIZE, lineHeight: 1 }
      })

  return jsx('span', {
    'aria-hidden': true,
    style: { ...ICON_BOX_STYLE, transform: `translateY(${ICON_OPTICAL_OFFSET_Y[provider] ?? 0}px)` },
    children: glyph
  })
}

function formatResetAt(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    })
  } catch {
    return null
  }
}

function WindowRow({ w, provider }) {
  const resetLabel = formatResetAt(w.reset_at)
  const openRouterHeadline = provider === 'openrouter' ? openRouterText(w) : null
  const headline = openRouterHeadline ?? (w.used_percent != null ? `${w.used_percent.toFixed(1)}%` : (w.detail ?? '\u2014'))
  // Detail line is only useful when it adds info beyond the headline (i.e.
  // headline is a computed used/left summary, not just the raw detail text).
  const showDetail = w.detail && headline !== w.detail

  return jsxs('div', {
    className: 'flex flex-col gap-0.5',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('span', { className: 'text-(--ui-text-secondary)', children: w.label }),
          jsx('span', {
            className: 'tabular-nums text-foreground',
            style: w.used_percent != null ? { color: pctColor(w.used_percent) } : undefined,
            children: headline
          })
        ]
      }),
      w.used_percent != null
        ? jsx('div', {
            className: 'h-1 w-full overflow-hidden rounded-full bg-(--ui-stroke-secondary)',
            children: jsx('div', {
              className: 'h-full rounded-full transition-[width]',
              style: {
                width: `${Math.max(0, Math.min(100, w.used_percent))}%`,
                background: pctColor(w.used_percent)
              }
            })
          })
        : null,
      showDetail ? jsx('div', { className: 'text-(--ui-text-tertiary)', children: w.detail }) : null,
      resetLabel ? jsx('div', { className: 'text-(--ui-text-tertiary)', children: `resets ${resetLabel}` }) : null
    ]
  })
}


// OpenRouter has no subscription window -- it bills against purchased/
// allotted dollars instead. `detail` already carries both figures as
// "$<remaining> of $<total> ... remaining"; parse them so the UI can show
// the pair a user actually wants at a glance: spent vs. left.
function parseOpenRouterAmounts(w) {
  const match = typeof w.detail === 'string' ? w.detail.match(/\$([\d.]+)\s+of\s+\$([\d.]+)/) : null
  if (match) {
    const remaining = parseFloat(match[1])
    const total = parseFloat(match[2])
    if (Number.isFinite(remaining) && Number.isFinite(total)) {
      return { used: Math.max(0, total - remaining), remaining }
    }
  }
  return w.amount_usd != null ? { used: null, remaining: w.amount_usd } : null
}

function openRouterText(w) {
  const amounts = parseOpenRouterAmounts(w)
  if (!amounts) return null
  return amounts.used != null
    ? `$${amounts.used.toFixed(2)} used · $${amounts.remaining.toFixed(2)} left`
    : `$${amounts.remaining.toFixed(2)} left`
}

// The chip always tracks the Session window (backend label "Session", the
// five_hour/primary_window rate limit) -- that is the number a user checks
// before their next message, not a longer rolling week. Fall back to the
// highest used_percent only when no Session window is present (e.g. an
// unlimited/legacy account) so the chip never goes blank.
function sessionWindow(windows) {
  return windows.find(w => w.label === 'Session') ?? null
}

// Per-provider chip/tooltip headline:
//   - percent-based providers (Codex, Claude) show the Session window's
//     used_percent (see sessionWindow above).
//   - OpenRouter shows spent/left dollars (never a percent -- see
//     openRouterText above) for whichever window is the tighter constraint
//     (credits balance vs per-key quota, lowest remaining wins).
function chipEntryFor(card) {
  if (!card.available) return { provider: card.provider, available: false, text: null }

  const windows = card.windows ?? []

  if (card.provider === 'openrouter') {
    const withAmounts = windows.map(w => ({ w, amounts: parseOpenRouterAmounts(w) })).filter(x => x.amounts)
    if (withAmounts.length) {
      const tightest = withAmounts.reduce((min, x) => (x.amounts.remaining < min.amounts.remaining ? x : min))
      const text = openRouterText(tightest.w)
      if (text) return { provider: card.provider, available: true, text }
    }
  }

  const session = sessionWindow(windows)
  const pct = session?.used_percent ?? windows
    .map(w => w.used_percent)
    .filter(p => p != null)
    .reduce((max, p) => (max == null ? p : Math.max(max, p)), null)

  return { provider: card.provider, available: true, text: pct != null ? `${Math.round(pct)}%` : null }
}

// OpenRouter hover, Linear Monitor vocabulary: hairline-separated sections,
// muted key left / tabular value right, remaining bars for dollar windows.
// The backend packs multi-value windows into one " • "-joined detail string
// (shared with /usage text rendering), so the split lives here — presentation
// is the plugin's job, not the fetcher's.
function detailRows(detail) {
  return typeof detail === 'string' ? detail.split(' • ').map(s => s.trim()).filter(Boolean) : []
}

function KeyValueRow({ label, value }) {
  return jsxs('div', {
    className: 'flex items-center justify-between gap-2',
    children: [
      jsx('span', { className: 'text-(--ui-text-tertiary)', children: label }),
      jsx('span', { className: 'tabular-nums text-foreground', children: value })
    ]
  })
}

function OpenRouterTooltip({ windows, plan }) {
  const usage = windows.find(w => w.label === 'API key usage') ?? null
  const limits = windows.filter(w => w !== usage && parseOpenRouterAmounts(w))
  const usageRows = usage ? detailRows(usage.detail) : []
  const [keyCaption, ...usedRows] = usageRows

  const sections = []
  if (usageRows.length) {
    sections.push(jsxs('div', {
      className: 'flex flex-col gap-0.5',
      children: [
        keyCaption ? jsx('div', { className: 'font-medium text-foreground', children: keyCaption.replace(/^Key: /, '') }) : null,
        ...usedRows.map((row, i) => {
          const sep = row.indexOf(': ')
          return sep < 0
            ? jsx('div', { className: 'text-(--ui-text-tertiary)', children: row, key: i })
            : jsx(KeyValueRow, { label: row.slice(0, sep), value: row.slice(sep + 2), key: i })
        })
      ]
    }))
  }
  for (const w of limits) {
    const amounts = parseOpenRouterAmounts(w)
    const total = amounts.used + amounts.remaining
    const frac = total > 0 ? Math.max(0, Math.min(1, amounts.remaining / total)) : 0
    sections.push(jsxs('div', {
      className: 'flex flex-col gap-0.5 border-t border-(--ui-stroke-secondary) pt-1',
      children: [
        jsx('div', { className: 'text-(--ui-text-tertiary)', children: w.label }),
        jsxs('div', {
          className: 'flex items-center justify-between gap-2',
          children: [
            jsx('span', { className: 'tabular-nums text-foreground', children: `$${amounts.used.toFixed(2)} used` }),
            jsx('span', { className: 'tabular-nums text-foreground', children: `$${amounts.remaining.toFixed(2)} left` })
          ]
        }),
        jsx('div', {
          className: 'h-1 w-full overflow-hidden rounded-full bg-(--ui-stroke-secondary)',
          children: jsx('div', {
            className: 'h-full rounded-full bg-(--ui-accent) transition-[width]',
            style: { width: `${frac * 100}%` }
          })
        })
      ]
    }))
  }
  return jsxs('div', {
    className: 'flex min-w-52 flex-col gap-1.5',
    children: [
      jsx('div', { className: 'font-medium text-foreground', children: 'OpenRouter' }),
      plan ? jsx('div', { className: 'text-(--ui-text-tertiary)', children: `Plan: ${plan}` }) : null,
      ...sections
    ]
  })
}

// Detailed, multi-line popover content for one provider's chip: every window
// row with progress bar, so hover shows the full breakdown.
function providerTooltip(card) {
  const label = PROVIDER_LABEL[card.provider] ?? card.provider
  if (!card.available) {
    return jsx('div', { children: `${label}: ${card.unavailable_reason || 'not connected'}` })
  }

  const windows = card.windows ?? []
  if (card.provider === 'openrouter') return jsx(OpenRouterTooltip, { windows, plan: card.plan })
  return jsxs('div', {
    className: 'flex flex-col gap-1',
    children: [
      jsx('div', { className: 'font-medium text-foreground', children: label }),
      card.plan ? jsx('div', { className: 'text-(--ui-text-tertiary)', children: `Plan: ${card.plan}` }) : null,
      ...windows.map((w, i) => jsx(WindowRow, { w, provider: card.provider, key: i }))
    ]
  })
}

function ProviderUsageChip({ provider }) {
  const { data } = useQuery({
    queryKey: ['account-usage'],
    queryFn: () => host.request('account.usage', {}),
    refetchInterval: REFRESH_MS,
    staleTime: REFRESH_MS
  })

  // Hooks stay above the early return: `card` is null on first load, and a
  // return before useState/useRef changes the hook count (-> React #310 crash
  // on restart, see desktop.log error-boundary contrib:account-usage).
  const [open, setOpen] = useState(false)
  // Hover bridge grace: the content portals to document.body, so moving the
  // cursor from chip to popover crosses a few px of dead space. Closing
  // immediately on mouseleave wins the race and the popover dies on arrival.
  // A 150ms grace lets the content's mouseenter cancel the pending close.
  const closeTimer = useRef(null)
  const cancelClose = () => {
    if (closeTimer.current) { clearTimeout(closeTimer.current); closeTimer.current = null }
  }
  const showNow = () => { cancelClose(); setOpen(true) }
  const scheduleClose = () => {
    cancelClose()
    closeTimer.current = setTimeout(() => setOpen(false), 150)
  }
  // Hover owns visibility, click owns navigation: every close path always
  // applies, so nothing can pin the popover open.
  const markHover = v => { if (v) showNow(); else scheduleClose() }

  const card = (data?.cards ?? []).find(c => c.provider === provider)
  if (!card) return null

  const entry = chipEntryFor(card)

  return jsx(Popover, {
    open,
    onOpenChange: next => { cancelClose(); setOpen(next) },
    children: [
      jsx(PopoverTrigger, {
        asChild: true,
        children: jsx('button', {
          className: cn(
            'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] transition-colors',
            'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
          ),
          type: 'button',
          onClick: () => { haptic('tap'); openUsage(provider) },
          onFocus: () => showNow(),
          onBlur: () => scheduleClose(),
          onMouseEnter: () => markHover(true),
          onMouseLeave: () => markHover(false),
          onMouseDown: e => e.preventDefault(),
          children: jsxs('span', {
            className: 'inline-flex items-center gap-1',
            children: [
              jsx(ProviderIcon, { provider: entry.provider }),
              jsx('span', {
                className: 'tabular-nums',
                style: entry.available && entry.text && entry.text.endsWith('%') ? { color: pctColor(parseFloat(entry.text)) } : undefined,
                children: entry.available && entry.text != null ? entry.text : '—'
              })
            ]
          })
        })
      }),
      jsx(PopoverContent, {
        align: 'start',
        side: 'top',
        className: '[--popover-surface:var(--ui-bg-elevated)]',
        // Break the focus-reopen loop: Radix refocuses the trigger on close,
        // and our onFocus would reopen instantly, pinning the popover open.
        onCloseAutoFocus: e => e.preventDefault(),
        onMouseEnter: () => markHover(true),
        onMouseLeave: () => markHover(false),
        children: providerTooltip(card)
      })
    ]
  })
}

export default {
  id: ID,
  name: 'Account Usage',
  register(ctx) {
    openExternalFn = ctx.os.openExternal
    ctx.i18n.register({
      en: {
        title: 'Account Usage',
        loading: 'Loading\u2026',
        error: 'Could not load usage'
      }
    })

    ctx.register({
      id: 'openai-codex-usage',
      area: 'statusBar.left',
      order: 140,
      data: { toggleLabel: 'Codex usage' },
      render: () => jsx(ProviderUsageChip, { provider: 'openai-codex' })
    })
    ctx.register({
      id: 'anthropic-usage',
      area: 'statusBar.left',
      order: 141,
      data: { toggleLabel: 'Claude usage' },
      render: () => jsx(ProviderUsageChip, { provider: 'anthropic' })
    })
    ctx.register({
      id: 'openrouter-usage',
      area: 'statusBar.left',
      order: 142,
      data: { toggleLabel: 'OpenRouter usage' },
      render: () => jsx(ProviderUsageChip, { provider: 'openrouter' })
    })
  }
}
