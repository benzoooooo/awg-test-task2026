const whole = new Intl.NumberFormat('en')
const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })

export function formatCount(value: number): string {
  return Math.abs(value) >= 10_000 ? compact.format(value) : whole.format(value)
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatRelative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '—'
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000)
  if (seconds < 45) return 'just now'
  const steps: [number, string][] = [
    [60, 'min'],
    [24, 'h'],
    [30, 'd'],
    [12, 'mo'],
  ]
  let value = seconds / 60
  let unit = 'min'
  for (const [size, label] of steps) {
    unit = label
    if (Math.abs(value) < size) break
    value /= size
    unit = label === 'mo' ? 'y' : unit
  }
  if (unit === 'mo' && Math.abs(value) >= 12) unit = 'y'
  const rounded = Math.max(1, Math.round(value))
  return seconds >= 0 ? `${rounded} ${unit} ago` : `in ${rounded} ${unit}`
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}

export type PeriodKey = 'all' | '365d' | '90d' | '30d'

export const PERIODS: { key: PeriodKey; label: string; days: number | null }[] = [
  { key: 'all', label: 'All time', days: null },
  { key: '365d', label: '12 months', days: 365 },
  { key: '90d', label: '90 days', days: 90 },
  { key: '30d', label: '30 days', days: 30 },
]

export function periodFromParam(value: string | null): PeriodKey {
  return PERIODS.find((period) => period.key === value)?.key ?? 'all'
}

export function periodLabel(key: PeriodKey): string {
  return PERIODS.find((period) => period.key === key)?.label ?? 'All time'
}

export function sinceFor(key: PeriodKey, today: Date = new Date()): string | undefined {
  const days = PERIODS.find((period) => period.key === key)?.days
  if (!days) return undefined
  const start = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()))
  start.setUTCDate(start.getUTCDate() - days)
  return start.toISOString().slice(0, 10)
}

export function commitUrl(repoUrl: string | null, sha: string): string | null {
  if (!repoUrl) return null
  try {
    const host = new URL(repoUrl).host
    const base = repoUrl.replace(/\.git$/, '')
    if (host === 'github.com' || host === 'codeberg.org') return `${base}/commit/${sha}`
    if (host === 'gitlab.com') return `${base}/-/commit/${sha}`
  } catch {
    return null
  }
  return null
}

export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}
