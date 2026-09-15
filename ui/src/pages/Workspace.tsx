import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  api,
  type Author,
  type BranchRef,
  type Commit,
  type Dashboard,
  type RepoInfo,
  type ServiceConfig,
} from '../api'
import { AuthorFilter } from '../components/AuthorFilter'
import { CommitList } from '../components/CommitList'
import { ContributionBars } from '../components/ContributionBars'
import { Shell, StatusBadge } from '../components/Layout'
import { MetricsHelp } from '../components/MetricsHelp'
import { Punchcard } from '../components/Punchcard'
import { AuthorPanel, StatTiles } from '../components/StatTiles'
import { TrendChart } from '../components/TrendChart'
import {
  PERIODS,
  formatBytes,
  formatRelative,
  messageOf,
  periodFromParam,
  periodLabel,
  sinceFor,
} from '../format'

const PAGE_SIZE = 30

type FilterKey = 'branch' | 'period' | 'author'

export function Workspace() {
  const { repoId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const period = periodFromParam(params.get('period'))
  const author = params.get('author') ?? ''
  const branchParam = params.get('branch') ?? ''
  const since = useMemo(() => sinceFor(period), [period])

  const [repo, setRepo] = useState<RepoInfo | null>(null)
  const [repoError, setRepoError] = useState<string | null>(null)
  const [pollToken, setPollToken] = useState(0)
  const [config, setConfig] = useState<ServiceConfig | null>(null)
  const [branches, setBranches] = useState<BranchRef[]>([])
  const [authors, setAuthors] = useState<Author[]>([])
  const [board, setBoard] = useState<Dashboard | null>(null)
  const [boardError, setBoardError] = useState<string | null>(null)
  const [boardLoading, setBoardLoading] = useState(false)
  const [commits, setCommits] = useState<Commit[]>([])
  const [commitsExhausted, setCommitsExhausted] = useState(false)
  const [commitsLoading, setCommitsLoading] = useState(false)
  const [commitsError, setCommitsError] = useState<string | null>(null)

  const setFilter = useCallback(
    (key: FilterKey, value: string | undefined) => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          if (value) next.set(key, value)
          else next.delete(key)
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  useEffect(() => {
    api.config().then(setConfig).catch(() => undefined)
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer: number | undefined
    const load = async () => {
      try {
        const info = await api.repo(repoId)
        if (cancelled) return
        setRepo(info)
        setRepoError(null)
        if (info.status === 'pending' || info.status === 'cloning' || info.refreshing) {
          timer = window.setTimeout(load, 2000)
        }
      } catch (error) {
        if (!cancelled) setRepoError(messageOf(error))
      }
    }
    void load()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [repoId, pollToken])

  const ready = repo?.status === 'ready'
  const dataVersion = repo?.fetched_at ?? ''
  const branch = branchParam || board?.branch || ''
  const authorFilter = author || undefined

  useEffect(() => {
    if (!ready) return
    let cancelled = false
    api
      .branches(repoId)
      .then((rows) => {
        if (!cancelled) setBranches(rows)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [repoId, ready, dataVersion])

  useEffect(() => {
    if (!ready) return
    let cancelled = false
    setBoardLoading(true)
    api
      .dashboard(repoId, { branch: branchParam || undefined, since, author: authorFilter })
      .then((data) => {
        if (cancelled) return
        setBoard(data)
        setBoardError(null)
      })
      .catch((error) => {
        if (!cancelled) setBoardError(messageOf(error))
      })
      .finally(() => {
        if (!cancelled) setBoardLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [repoId, ready, dataVersion, branchParam, since, authorFilter])

  useEffect(() => {
    if (!ready || !branch) return
    let cancelled = false
    api
      .authors(repoId, { branch, since })
      .then((rows) => {
        if (!cancelled) setAuthors(rows)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [repoId, ready, dataVersion, branch, since])

  useEffect(() => {
    if (!ready || !branch) return
    let cancelled = false
    setCommitsLoading(true)
    api
      .commits(repoId, { branch, since, author: authorFilter, limit: PAGE_SIZE })
      .then((rows) => {
        if (cancelled) return
        setCommits(rows)
        setCommitsExhausted(rows.length < PAGE_SIZE)
        setCommitsError(null)
      })
      .catch((error) => {
        if (!cancelled) setCommitsError(messageOf(error))
      })
      .finally(() => {
        if (!cancelled) setCommitsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [repoId, ready, dataVersion, branch, since, authorFilter])

  const loadMore = async () => {
    setCommitsLoading(true)
    try {
      const rows = await api.commits(repoId, {
        branch,
        since,
        author: authorFilter,
        limit: PAGE_SIZE,
        skip: commits.length,
      })
      setCommits((previous) => [...previous, ...rows])
      setCommitsExhausted(rows.length < PAGE_SIZE)
    } catch (error) {
      setCommitsError(messageOf(error))
    } finally {
      setCommitsLoading(false)
    }
  }

  const refresh = async () => {
    try {
      setRepo(await api.refresh(repoId))
      setPollToken((token) => token + 1)
    } catch (error) {
      setRepoError(messageOf(error))
    }
  }

  if (!repo) {
    return (
      <Shell>
        <Link to="/" className="back-link">
          ← All repositories
        </Link>
        {repoError ? (
          <p className="notice is-error" role="alert">
            {repoError}
          </p>
        ) : (
          <p className="muted">Loading repository…</p>
        )}
      </Shell>
    )
  }

  const selected = board?.selected_author ?? null

  return (
    <Shell>
      <Link to="/" className="back-link">
        ← All repositories
      </Link>
      <header className="repo-head">
        <div>
          <h1>{repo.name}</h1>
          <p className="muted small">
            {repo.url ? (
              <a href={repo.url} target="_blank" rel="noreferrer noopener">
                {repo.url}
              </a>
            ) : (
              'Local repository'
            )}
            {repo.fetched_at ? ` · fetched ${formatRelative(repo.fetched_at)}` : ''}
            {repo.size_bytes ? ` · ${formatBytes(repo.size_bytes)} of history` : ''}
          </p>
        </div>
        <div className="repo-head-actions">
          <StatusBadge repo={repo} />
          {repo.source === 'remote' && (
            <button
              type="button"
              className="button-secondary"
              onClick={() => void refresh()}
              disabled={repo.refreshing || repo.status === 'cloning' || repo.status === 'pending'}
            >
              {repo.status === 'failed' ? 'Retry clone' : 'Fetch updates'}
            </button>
          )}
        </div>
      </header>

      {repo.status !== 'ready' ? (
        <section className="card status-panel" aria-live="polite">
          {repo.status === 'failed' ? (
            <>
              <h2>Clone failed</h2>
              <p className="field-note is-error">{repo.error}</p>
            </>
          ) : (
            <>
              <h2>Cloning commit history…</h2>
              <p className="muted">
                Only commits and trees are downloaded, never file contents. Large repositories take a few minutes;
                this page updates automatically.
              </p>
            </>
          )}
        </section>
      ) : (
        <>
          {repo.error && <p className="notice">{repo.error}</p>}
          <div className="filters" role="toolbar" aria-label="Dashboard filters">
            <div className="field">
              <span className="field-label" id="period-label">
                Period
              </span>
              <div className="segmented" role="group" aria-labelledby="period-label">
                {PERIODS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    aria-pressed={period === item.key}
                    onClick={() => setFilter('period', item.key === 'all' ? undefined : item.key)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="field">
              <label className="field-label" htmlFor="branch-filter">
                Branch
              </label>
              <select
                id="branch-filter"
                value={branch}
                onChange={(event) => setFilter('branch', event.target.value)}
              >
                {!branches.some((item) => item.name === branch) && branch && <option value={branch}>{branch}</option>}
                {branches.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
            <AuthorFilter authors={authors} value={author} onChange={(email) => setFilter('author', email)} />
          </div>

          {boardError && (
            <div className="notice is-error" role="alert">
              {boardError}
              {author && (
                <button type="button" className="link-button" onClick={() => setFilter('author', undefined)}>
                  Clear author filter
                </button>
              )}
            </div>
          )}

          {board ? (
            <div className={`board${boardLoading ? ' is-loading' : ''}`} aria-busy={boardLoading}>
              {board.truncated && (
                <p className="notice">
                  History is larger than the scan limit: metrics cover the newest{' '}
                  {board.scanned_commits.toLocaleString('en')} commits of {board.branch}.
                </p>
              )}
              <StatTiles board={board} periodText={periodLabel(period)} />
              {selected && (
                <AuthorPanel
                  profile={selected}
                  authorCount={board.author_count}
                  granularity={board.trend.granularity}
                  onClear={() => setFilter('author', undefined)}
                />
              )}
              <section className="card" aria-labelledby="trend-title">
                <h2 id="trend-title">Activity trend</h2>
                <TrendChart
                  buckets={board.trend.buckets}
                  granularity={board.trend.granularity}
                  authorName={selected?.name}
                />
              </section>
              <div className="grid-2">
                <section className="card" aria-labelledby="share-title">
                  <div className="section-head">
                    <h2 id="share-title">Contribution share</h2>
                    <span className="muted small">Click an author to filter</span>
                  </div>
                  <ContributionBars
                    rows={board.contributors}
                    otherAuthors={board.other_authors}
                    otherCommits={board.other_commits}
                    otherShare={board.other_share_percent}
                    selected={author}
                    onSelect={(email) => setFilter('author', email)}
                  />
                </section>
                <section className="card" aria-labelledby="punch-title">
                  <div className="section-head">
                    <h2 id="punch-title">Activity by hour</h2>
                    <span className="muted small">{selected ? selected.name : 'All authors'}</span>
                  </div>
                  <Punchcard grid={board.punchcard} />
                </section>
              </div>
              <section className="card" aria-labelledby="commits-title">
                <div className="section-head">
                  <h2 id="commits-title">Commits</h2>
                  <span className="muted small">
                    {selected ? `by ${selected.name}` : 'All authors'} · {board.branch}
                  </span>
                </div>
                <CommitList
                  commits={commits}
                  loading={commitsLoading}
                  exhausted={commitsExhausted}
                  error={commitsError}
                  repoUrl={repo.url}
                  selectedAuthor={author}
                  onMore={() => void loadMore()}
                  onAuthor={(email) => setFilter('author', email)}
                />
              </section>
              <MetricsHelp maxCommits={config?.max_commits_scan ?? null} />
            </div>
          ) : (
            !boardError && (
              <p className="muted">Building the commit index… the first load of a large repository takes a moment.</p>
            )
          )}
        </>
      )}
    </Shell>
  )
}
