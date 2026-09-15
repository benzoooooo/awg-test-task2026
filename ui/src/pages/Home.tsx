import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type RepoInfo, type ServiceConfig } from '../api'
import { Shell, StatusBadge } from '../components/Layout'
import { formatBytes, formatRelative, messageOf } from '../format'

const EXAMPLES = [
  'https://github.com/django/django',
  'https://github.com/fastapi/fastapi',
  'https://github.com/pallets/click',
]

const busy = (repo: RepoInfo) => repo.status === 'pending' || repo.status === 'cloning' || repo.refreshing

export function Home() {
  const navigate = useNavigate()
  const [config, setConfig] = useState<ServiceConfig | null>(null)
  const [repos, setRepos] = useState<RepoInfo[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [url, setUrl] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const loadRepos = useCallback(async () => {
    try {
      setRepos(await api.repos())
      setLoadError(null)
    } catch (error) {
      setLoadError(messageOf(error))
    }
  }, [])

  useEffect(() => {
    api.config().then(setConfig).catch(() => undefined)
    void loadRepos()
  }, [loadRepos])

  const polling = repos?.some(busy) ?? false
  useEffect(() => {
    if (!polling) return
    const timer = window.setInterval(() => void loadRepos(), 2000)
    return () => window.clearInterval(timer)
  }, [polling, loadRepos])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const value = url.trim()
    if (!/^https:\/\/[^\s/]+\/\S+/i.test(value)) {
      setFormError('Paste a public https:// repository URL, for example https://github.com/owner/repo')
      return
    }
    setSubmitting(true)
    setFormError(null)
    try {
      const repo = await api.connect(value)
      setUrl('')
      if (repo.status === 'ready') {
        navigate(`/r/${repo.id}`)
        return
      }
      setRepos((current) => [repo, ...(current ?? []).filter((item) => item.id !== repo.id)])
    } catch (error) {
      setFormError(messageOf(error))
    } finally {
      setSubmitting(false)
    }
  }

  const retry = async (repo: RepoInfo) => {
    try {
      const info = await api.refresh(repo.id)
      setRepos((current) => (current ?? []).map((item) => (item.id === info.id ? info : item)))
    } catch (error) {
      setLoadError(messageOf(error))
    }
  }

  const remoteEnabled = config?.remote_enabled ?? true

  return (
    <Shell>
      <section className="hero">
        <h1>Who builds this repository, and how is activity changing?</h1>
        <p className="lede">
          Paste any public git URL. GitPulse clones commit history without file contents, then shows each
          author&apos;s share, activity trends, and working hours — filterable by author.
        </p>
      </section>

      {remoteEnabled ? (
        <section className="card connect" aria-labelledby="connect-title">
          <h2 id="connect-title">Connect a repository</h2>
          <form className="connect-form" onSubmit={submit} noValidate>
            <label htmlFor="repo-url" className="sr-only">
              Repository URL
            </label>
            <input
              id="repo-url"
              type="url"
              inputMode="url"
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              aria-invalid={Boolean(formError)}
              aria-describedby="connect-help"
              autoComplete="off"
              spellCheck={false}
            />
            <button type="submit" className="button-primary" disabled={submitting}>
              {submitting ? 'Connecting…' : 'Analyze'}
            </button>
          </form>
          {formError && (
            <p className="field-note is-error" role="alert">
              {formError}
            </p>
          )}
          <p id="connect-help" className="connect-help">
            Try{' '}
            {EXAMPLES.map((example, index) => (
              <span key={example}>
                <button type="button" className="link-button" onClick={() => setUrl(example)}>
                  {example.replace('https://github.com/', '')}
                </button>
                {index < EXAMPLES.length - 1 ? ', ' : ''}
              </span>
            ))}
            .{' '}
            {config && (
              <span className="muted">
                https only · up to {config.max_repo_size_mb} MB of history
                {config.allowed_hosts.length ? ` · hosts: ${config.allowed_hosts.join(', ')}` : ''}
              </span>
            )}
          </p>
        </section>
      ) : (
        <p className="notice">Remote repositories are disabled on this server; the local repository is shown below.</p>
      )}

      <section aria-labelledby="repos-title">
        <div className="section-head">
          <h2 id="repos-title">Repositories</h2>
          {config && remoteEnabled && (
            <span className="muted">
              {repos?.filter((repo) => repo.source === 'remote').length ?? 0} of {config.max_repos} slots used ·
              least recently used are replaced
            </span>
          )}
        </div>
        {loadError && (
          <p className="notice is-error" role="alert">
            {loadError}
          </p>
        )}
        {repos === null && !loadError && <p className="muted">Loading repositories…</p>}
        {repos?.length === 0 && <p className="muted empty">No repositories yet — connect one above.</p>}
        <ul className="repo-grid">
          {repos?.map((repo) => (
            <li key={repo.id} className="card repo-card">
              <div className="repo-card-head">
                {repo.status === 'ready' ? (
                  <Link to={`/r/${repo.id}`} className="repo-name">
                    {repo.name}
                  </Link>
                ) : (
                  <span className="repo-name">{repo.name}</span>
                )}
                <StatusBadge repo={repo} />
              </div>
              {repo.status === 'failed' && repo.error && <p className="field-note is-error">{repo.error}</p>}
              {(repo.status === 'pending' || repo.status === 'cloning') && (
                <p className="muted small">Cloning commit history… large repositories take a few minutes.</p>
              )}
              <p className="repo-meta muted small">
                {repo.source === 'local' ? 'Local repository' : formatBytes(repo.size_bytes)}
                {repo.fetched_at ? ` · fetched ${formatRelative(repo.fetched_at)}` : ''}
                {repo.pinned && repo.source === 'remote' ? ' · pinned' : ''}
              </p>
              <div className="repo-actions">
                {repo.status === 'ready' && (
                  <Link to={`/r/${repo.id}`} className="button-secondary">
                    Open dashboard
                  </Link>
                )}
                {repo.status === 'failed' && (
                  <button type="button" className="button-secondary" onClick={() => void retry(repo)}>
                    Retry
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </Shell>
  )
}
