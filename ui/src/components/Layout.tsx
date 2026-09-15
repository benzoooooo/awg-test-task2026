import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { RepoInfo } from '../api'

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="page">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true" />
          AWG GitPulse
        </Link>
        <span className="topbar-note">Contribution analytics for public git repositories</span>
      </header>
      <main className="shell">{children}</main>
    </div>
  )
}

const STATUS_TEXT: Record<RepoInfo['status'], string> = {
  pending: 'Queued',
  cloning: 'Cloning',
  ready: 'Ready',
  failed: 'Failed',
}

export function StatusBadge({ repo }: { repo: RepoInfo }) {
  const refreshing = repo.status === 'ready' && repo.refreshing
  const state = refreshing ? 'refreshing' : repo.status
  const label = refreshing ? 'Updating' : STATUS_TEXT[repo.status]
  return (
    <span className={`status status-${state}`}>
      <span className="status-icon" aria-hidden="true" />
      {label}
    </span>
  )
}
