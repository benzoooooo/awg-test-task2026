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

function apiBase(): string {
  const mount = window.__GITPULSE_MOUNT__ ?? '/git'
  return `${mount.replace(/\/$/, '')}/api/v1`
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`)
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  summary: () => getJson<RepoSummary>('/summary'),
  branches: () => getJson<BranchRef[]>('/branches'),
  commits: (branch: string) =>
    getJson<Commit[]>(`/commits?branch=${encodeURIComponent(branch)}`),
  authors: () => getJson<Author[]>('/authors'),
  contributions: () => getJson<AuthorContribution[]>('/contributions'),
  activity: () => getJson<ActivityBucket[]>('/activity'),
}
