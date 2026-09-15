import { useEffect, useState } from 'react'
import {
  ActivityBucket,
  Author,
  AuthorContribution,
  BranchRef,
  Commit,
  RepoSummary,
  api,
} from './api'

export function App() {
  const [summary, setSummary] = useState<RepoSummary | null>(null)
  const [branches, setBranches] = useState<BranchRef[]>([])
  const [branch, setBranch] = useState('')
  const [commits, setCommits] = useState<Commit[]>([])
  const [authors, setAuthors] = useState<Author[]>([])
  const [contributions, setContributions] = useState<AuthorContribution[]>([])
  const [activity, setActivity] = useState<ActivityBucket[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [s, b, a, c, act] = await Promise.all([
          api.summary(),
          api.branches(),
          api.authors(),
          api.contributions(),
          api.activity(),
        ])
        if (cancelled) return
        setSummary(s)
        setBranches(b)
        setAuthors(a)
        setContributions(c)
        setActivity(act)
        const initial = s.head || b[0]?.name || ''
        setBranch(initial)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'failed to load')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!branch) return
    let cancelled = false
    ;(async () => {
      try {
        const rows = await api.commits(branch)
        if (!cancelled) setCommits(rows)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'failed to load commits')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [branch])

  if (loading) {
    return (
      <div className="shell">
        <p className="muted">Loading repository…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="shell">
        <p className="error">{error}</p>
      </div>
    )
  }

  return (
    <div className="shell">
      <header className="hero">
        <p className="brand">AWG GitPulse</p>
        <h1>Repository pulse</h1>
        <p className="lede">
          Local git metadata for <code>{summary?.path}</code>
        </p>
      </header>

      <section className="panel">
        <h2>Overview</h2>
        <dl className="stats">
          <div>
            <dt>Commits</dt>
            <dd>{summary?.commit_count ?? 0}</dd>
          </div>
          <div>
            <dt>Branches</dt>
            <dd>{summary?.branch_count ?? 0}</dd>
          </div>
          <div>
            <dt>Authors</dt>
            <dd>{summary?.author_count ?? 0}</dd>
          </div>
          <div>
            <dt>HEAD</dt>
            <dd>{summary?.head ?? '—'}</dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <div className="row">
          <h2>Commits</h2>
          <label className="branch-select">
            Branch
            <select value={branch} onChange={(e) => setBranch(e.target.value)}>
              {branches.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <ol className="timeline">
          {commits.map((commit) => (
            <li key={commit.sha}>
              <code>{commit.short_sha}</code>
              <strong>{commit.subject}</strong>
              <span className="muted">
                {commit.author_name} · {new Date(commit.authored_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel split">
        <div>
          <h2>Authors</h2>
          <ul className="list">
            {authors.map((author) => (
              <li key={`${author.name}:${author.email}`}>
                <strong>{author.name}</strong>
                <span className="muted">
                  {author.email} · {author.commits} commits
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2>Contribution share</h2>
          <ul className="list">
            {contributions.map((row) => (
              <li key={`${row.name}:${row.email}`}>
                <div className="bar-row">
                  <strong>{row.name}</strong>
                  <span>{row.share_percent}%</span>
                </div>
                <div className="bar">
                  <span style={{ width: `${Math.min(row.share_percent, 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="panel">
        <h2>Activity by week</h2>
        <ul className="activity">
          {activity.map((bucket) => (
            <li key={bucket.period}>
              <span>{bucket.period}</span>
              <strong>{bucket.commits}</strong>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
