import type { AuthorContribution } from '../api'
import { formatCount, formatPercent } from '../format'

type Props = {
  rows: AuthorContribution[]
  otherAuthors: number
  otherCommits: number
  otherShare: number
  selected?: string
  onSelect: (email: string | undefined) => void
}

export function ContributionBars({ rows, otherAuthors, otherCommits, otherShare, selected, onSelect }: Props) {
  if (!rows.length) return <p className="muted empty">No commits in this period.</p>
  const peak = Math.max(...rows.map((row) => row.share_percent), otherShare, 0.01)
  const selectedKey = selected ? selected.toLowerCase() : undefined
  const width = (share: number) => `${Math.max((share / peak) * 100, 0.8)}%`

  return (
    <ol className="share-list">
      {rows.map((row) => {
        const isSelected = selectedKey !== undefined && selectedKey === row.email.toLowerCase()
        const dimmed = selectedKey !== undefined && !isSelected
        if (!row.email) {
          return (
            <li key={`name:${row.name}`}>
              <div className="share-row is-static" title="No e-mail recorded in commits; cannot filter by this author">
                <span className="share-name">{row.name}</span>
                <span className="share-track" aria-hidden="true">
                  <span className={`share-fill${dimmed ? ' is-dim' : ''}`} style={{ width: width(row.share_percent) }} />
                </span>
                <span className="share-value">
                  <strong>{formatPercent(row.share_percent)}</strong>
                  <span className="muted">{formatCount(row.commits)}</span>
                </span>
              </div>
            </li>
          )
        }
        return (
          <li key={row.email || row.name}>
            <button
              type="button"
              className={`share-row${isSelected ? ' is-selected' : ''}`}
              aria-pressed={isSelected}
              title={isSelected ? 'Clear author filter' : `Filter by ${row.name}`}
              onClick={() => onSelect(isSelected ? undefined : row.email)}
            >
              <span className="share-name">{row.name}</span>
              <span className="share-track" aria-hidden="true">
                <span className={`share-fill${dimmed ? ' is-dim' : ''}`} style={{ width: width(row.share_percent) }} />
              </span>
              <span className="share-value">
                <strong>{formatPercent(row.share_percent)}</strong>
                <span className="muted">{formatCount(row.commits)}</span>
              </span>
            </button>
          </li>
        )
      })}
      {otherAuthors > 0 && (
        <li>
          <div className="share-row is-static">
            <span className="share-name muted">
              {formatCount(otherAuthors)} other {otherAuthors === 1 ? 'author' : 'authors'}
            </span>
            <span className="share-track" aria-hidden="true">
              <span className="share-fill is-dim" style={{ width: width(otherShare) }} />
            </span>
            <span className="share-value">
              <strong>{formatPercent(otherShare)}</strong>
              <span className="muted">{formatCount(otherCommits)}</span>
            </span>
          </div>
        </li>
      )}
    </ol>
  )
}
