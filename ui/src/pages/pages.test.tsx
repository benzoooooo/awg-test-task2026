import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import type { Dashboard, RepoInfo } from '../api'
import { mockFetch } from '../test/mockFetch'
import { Home } from './Home'
import { Workspace } from './Workspace'

const REPO_ID = '0123456789abcdef'

const repo: RepoInfo = {
  id: REPO_ID,
  name: 'github.com/team/history',
  url: 'https://github.com/team/history',
  source: 'remote',
  status: 'ready',
  error: null,
  refreshing: false,
  pinned: false,
  created_at: '2026-09-15T10:00:00Z',
  updated_at: '2026-09-15T10:00:00Z',
  fetched_at: '2026-09-15T10:00:00Z',
  size_bytes: 2_500_000,
}

const config = {
  version: '0.2.0',
  remote_enabled: true,
  allowed_hosts: [],
  max_repos: 20,
  max_repo_size_mb: 1536,
  max_commits_scan: 400000,
}

const dashboard = (author: string | null): Dashboard => ({
  branch: 'main',
  tip_sha: 'a'.repeat(40),
  since: null,
  author,
  total_commits: 6,
  author_count: 2,
  first_commit_at: '2026-01-05T07:00:00Z',
  last_commit_at: '2026-03-02T09:00:00Z',
  core_authors: 1,
  scanned_commits: 6,
  truncated: false,
  contributors: [
    { name: 'Ada Lovelace', email: 'ada@example.com', commits: 4, insertions: 0, deletions: 0, share_percent: 66.67 },
    { name: 'Bob Builder', email: 'bob@example.com', commits: 2, insertions: 0, deletions: 0, share_percent: 33.33 },
  ],
  other_authors: 0,
  other_commits: 0,
  other_share_percent: 0,
  trend: {
    granularity: 'week',
    buckets: [
      { period: '2026-W02', start: '2026-01-05', commits: 3, author_commits: author ? 1 : null, active_authors: 2 },
    ],
  },
  punchcard: Array.from({ length: 7 }, () => Array.from({ length: 24 }, () => 0)).map((row, day) =>
    day === 0 ? row.map((value, hour) => (hour === 10 ? 1 : value)) : row,
  ),
  selected_author: author
    ? {
        name: 'Bob Builder',
        email: 'bob@example.com',
        commits: 2,
        share_percent: 33.33,
        rank: 2,
        first_commit_at: '2026-01-08T04:30:00Z',
        last_commit_at: '2026-02-20T08:00:00Z',
        active_periods: 2,
        total_periods: 10,
      }
    : null,
})

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.search}</output>
}

afterEach(() => cleanup())

describe('Home', () => {
  it('lists repositories and validates URLs before connecting', async () => {
    const fetchMock = mockFetch({ '/config': config, '/repos': [repo] })
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    )
    expect(await screen.findByText('github.com/team/history')).toBeTruthy()
    expect(screen.getByText('Ready')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Repository URL'), { target: { value: 'git@github.com:a/b.git' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze' }))
    expect((await screen.findByRole('alert')).textContent).toContain('https://')
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })
})

describe('Workspace', () => {
  it('renders the dashboard and filters by author through the URL', async () => {
    const fetchMock = mockFetch({
      '/config': config,
      [`/repos/${REPO_ID}`]: repo,
      [`/repos/${REPO_ID}/branches`]: [{ name: 'main', tip_sha: 'a'.repeat(40), tip_date: null, tip_author: null }],
      [`/repos/${REPO_ID}/authors`]: [
        { name: 'Ada Lovelace', email: 'ada@example.com', commits: 4 },
        { name: 'Bob Builder', email: 'bob@example.com', commits: 2 },
      ],
      [`/repos/${REPO_ID}/dashboard`]: (url: URL) => dashboard(url.searchParams.get('author')),
      [`/repos/${REPO_ID}/commits`]: [],
    })
    render(
      <MemoryRouter initialEntries={[`/r/${REPO_ID}`]}>
        <Routes>
          <Route
            path="/r/:repoId"
            element={
              <>
                <Workspace />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByRole('region', { name: 'Key metrics' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Ada Lovelace/ })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Bob Builder/ }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('author=bob%40example.com'))
    expect(await screen.findByText('Filtered by author')).toBeTruthy()
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) => String(input).includes('/dashboard?') && String(input).includes('author=bob')),
      ).toBe(true),
    )

    fireEvent.click(screen.getByRole('button', { name: '90 days' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('period=90d'))
  })
})
