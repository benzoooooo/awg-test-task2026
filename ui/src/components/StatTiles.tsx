import type { AuthorProfile, Dashboard } from '../api'
import { formatCount, formatDate, formatPercent, formatRelative } from '../format'

export function StatTiles({ board, periodText }: { board: Dashboard; periodText: string }) {
  const tiles = [
    {
      label: 'Commits',
      value: formatCount(board.total_commits),
      note: `Non-merge · ${periodText.toLowerCase()}`,
    },
    {
      label: 'Contributors',
      value: formatCount(board.author_count),
      note: 'Distinct identities after mailmap',
    },
    {
      label: 'Core contributors',
      value: formatCount(board.core_authors),
      note: board.total_commits ? 'Top authors covering 50% of commits' : 'No commits in period',
    },
    {
      label: 'Last commit',
      value: formatRelative(board.last_commit_at),
      note: formatDate(board.last_commit_at),
    },
  ]
  return (
    <section className="tiles" aria-label="Key metrics">
      {tiles.map((tile) => (
        <div className="tile" key={tile.label}>
          <span className="tile-label">{tile.label}</span>
          <span className="tile-value">{tile.value}</span>
          <span className="tile-note">{tile.note}</span>
        </div>
      ))}
    </section>
  )
}

type PanelProps = {
  profile: AuthorProfile
  authorCount: number
  granularity: 'week' | 'month'
  onClear: () => void
}

export function AuthorPanel({ profile, authorCount, granularity, onClear }: PanelProps) {
  return (
    <section className="card author-panel" aria-label="Selected author">
      <div className="author-id">
        <span className="eyebrow">Filtered by author</span>
        <h2>{profile.name}</h2>
        <span className="muted">{profile.email}</span>
      </div>
      <dl className="author-stats">
        <div>
          <dt>Commits</dt>
          <dd>{formatCount(profile.commits)}</dd>
        </div>
        <div>
          <dt>Share</dt>
          <dd>{formatPercent(profile.share_percent)}</dd>
        </div>
        <div>
          <dt>Rank</dt>
          <dd>
            {profile.rank ? `#${profile.rank}` : '—'} <small>of {formatCount(authorCount)}</small>
          </dd>
        </div>
        <div>
          <dt>Active {granularity}s</dt>
          <dd>
            {profile.active_periods} <small>of {profile.total_periods}</small>
          </dd>
        </div>
        <div>
          <dt>First – last commit</dt>
          <dd className="dd-small">
            {formatDate(profile.first_commit_at)} – {formatDate(profile.last_commit_at)}
          </dd>
        </div>
      </dl>
      <button type="button" className="button-secondary" onClick={onClear}>
        Clear filter
      </button>
    </section>
  )
}
