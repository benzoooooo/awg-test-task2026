export type Author = {
  name: string
  email: string
  commits: number
}

export type BranchRef = {
  name: string
  tip_sha: string
  tip_date: string | null
  tip_author: string | null
}

export type Commit = {
  sha: string
  short_sha: string
  author_name: string
  author_email: string
  authored_at: string
  subject: string
}

export type RepoSummary = {
  path: string
  head: string | null
  default_branch: string | null
  commit_count: number
  first_commit_at: string | null
  last_commit_at: string | null
  branch_count: number
  author_count: number
}

export type AuthorContribution = {
  name: string
  email: string
  commits: number
  insertions: number
  deletions: number
  share_percent: number
}

export type ActivityBucket = {
  period: string
  commits: number
}

export type RepoStatus = 'pending' | 'cloning' | 'ready' | 'failed'

export type RepoInfo = {
  id: string
  name: string
  url: string | null
  source: 'local' | 'remote'
  status: RepoStatus
  error: string | null
  refreshing: boolean
  pinned: boolean
  created_at: string
  updated_at: string
  fetched_at: string | null
  size_bytes: number | null
}

export type TrendBucket = {
  period: string
  start: string
  commits: number
  author_commits: number | null
  active_authors: number
}

export type AuthorProfile = {
  name: string
  email: string
  commits: number
  share_percent: number
  rank: number | null
  first_commit_at: string | null
  last_commit_at: string | null
  active_periods: number
  total_periods: number
}

export type Dashboard = {
  branch: string
  tip_sha: string
  since: string | null
  author: string | null
  total_commits: number
  author_count: number
  first_commit_at: string | null
  last_commit_at: string | null
  core_authors: number
  scanned_commits: number
  truncated: boolean
  contributors: AuthorContribution[]
  other_authors: number
  other_commits: number
  other_share_percent: number
  trend: { granularity: 'week' | 'month'; buckets: TrendBucket[] }
  punchcard: number[][]
  selected_author: AuthorProfile | null
}

export type ServiceConfig = {
  version: string
  remote_enabled: boolean
  allowed_hosts: string[]
  max_repos: number
  max_repo_size_mb: number
  max_commits_scan: number
}

export type Filters = {
  branch?: string
  since?: string
  author?: string
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function apiBase(): string {
  const mount = window.__GITPULSE_MOUNT__ ?? '/git'
  return `${mount.replace(/\/$/, '')}/api/v1`
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, init)
  if (!response.ok) {
    let message = `request failed: ${response.status}`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) message = body.detail[0].msg
    } catch {
      // keep the generic message
    }
    throw new ApiError(response.status, message)
  }
  return response.json() as Promise<T>
}

const repoPath = (id: string) => `/repos/${encodeURIComponent(id)}`

export const api = {
  config: () => request<ServiceConfig>('/config'),
  repos: () => request<RepoInfo[]>('/repos'),
  repo: (id: string) => request<RepoInfo>(repoPath(id)),
  connect: (url: string) =>
    request<RepoInfo>('/repos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }),
  refresh: (id: string) => request<RepoInfo>(`${repoPath(id)}/refresh`, { method: 'POST' }),
  summary: (id: string) => request<RepoSummary>(`${repoPath(id)}/summary`),
  branches: (id: string) => request<BranchRef[]>(`${repoPath(id)}/branches`),
  authors: (id: string, filters: Filters) =>
    request<Author[]>(
      `${repoPath(id)}/authors${query({ branch: filters.branch, since: filters.since })}`,
    ),
  dashboard: (id: string, filters: Filters) =>
    request<Dashboard>(`${repoPath(id)}/dashboard${query({ ...filters })}`),
  commits: (id: string, filters: Filters & { branch: string; skip?: number; limit?: number }) =>
    request<Commit[]>(`${repoPath(id)}/commits${query({ ...filters })}`),
}
