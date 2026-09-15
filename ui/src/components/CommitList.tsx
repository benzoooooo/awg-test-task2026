import type { Commit } from '../api'
import { commitUrl, formatDate } from '../format'

type Props = {
  commits: Commit[]
  loading: boolean
  exhausted: boolean
  error: string | null
  repoUrl: string | null
  selectedAuthor: string
  onMore: () => void
  onAuthor: (email: string) => void
}

export function CommitList({ commits, loading, exhausted, error, repoUrl, selectedAuthor, onMore, onAuthor }: Props) {
  if (error) return <p className="notice is-error">{error}</p>
  if (!commits.length && !loading) return <p className="muted empty">No commits match these filters.</p>
  return (
    <>
      <ol className="commit-list">
        {commits.map((commit) => {
          const href = commitUrl(repoUrl, commit.sha)
          const isSelected = selectedAuthor.toLowerCase() === commit.author_email.toLowerCase()
          return (
            <li key={commit.sha}>
              {href ? (
                <a className="sha" href={href} target="_blank" rel="noreferrer noopener">
                  {commit.short_sha}
                </a>
              ) : (
                <code className="sha">{commit.short_sha}</code>
              )}
              <span className="commit-subject">{commit.subject}</span>
              <span className="commit-meta">
                {isSelected ? (
                  <span>{commit.author_name}</span>
                ) : (
                  <button type="button" className="link-button" onClick={() => onAuthor(commit.author_email)}>
                    {commit.author_name}
                  </button>
                )}
                <span className="muted"> · {formatDate(commit.authored_at)}</span>
              </span>
            </li>
          )
        })}
      </ol>
      {!exhausted && (
        <button type="button" className="button-secondary load-more" onClick={onMore} disabled={loading}>
          {loading ? 'Loading…' : 'Load more'}
        </button>
      )}
    </>
  )
}
