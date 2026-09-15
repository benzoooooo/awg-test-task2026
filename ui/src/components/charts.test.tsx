import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { TrendBucket } from '../api'
import { AuthorFilter } from './AuthorFilter'
import { ContributionBars } from './ContributionBars'
import { Punchcard } from './Punchcard'
import { TrendChart } from './TrendChart'

const buckets: TrendBucket[] = [
  { period: '2026-W01', start: '2025-12-29', commits: 4, author_commits: 1, active_authors: 2 },
  { period: '2026-W02', start: '2026-01-05', commits: 0, author_commits: 0, active_authors: 0 },
  { period: '2026-W03', start: '2026-01-12', commits: 9, author_commits: 3, active_authors: 3 },
]

describe('TrendChart', () => {
  it('renders one hit target per period and a tooltip on hover', () => {
    render(<TrendChart buckets={buckets} granularity="week" authorName="Ada" />)
    const hits = screen.getAllByTestId('trend-hit')
    expect(hits).toHaveLength(3)
    fireEvent.pointerEnter(hits[2])
    const tooltip = screen.getByRole('status')
    expect(tooltip.textContent).toContain('2026-W03')
    expect(tooltip.textContent).toContain('9')
    expect(tooltip.textContent).toContain('Ada')
  })

  it('offers a table view', () => {
    render(<TrendChart buckets={buckets} granularity="week" />)
    fireEvent.click(screen.getByRole('button', { name: 'Table view' }))
    expect(screen.getAllByRole('row')).toHaveLength(4)
  })

  it('shows an empty state', () => {
    render(<TrendChart buckets={[]} granularity="month" />)
    expect(screen.getByText(/No commits/)).toBeTruthy()
  })
})

describe('Punchcard', () => {
  it('renders a 7x24 grid', () => {
    const grid = Array.from({ length: 7 }, (_, day) => Array.from({ length: 24 }, (_, hour) => day + hour))
    render(<Punchcard grid={grid} />)
    expect(screen.getAllByTestId('punch-cell')).toHaveLength(168)
  })
})

describe('ContributionBars', () => {
  it('toggles the author filter', () => {
    const onSelect = vi.fn()
    const rows = [
      { name: 'Ada', email: 'ada@example.com', commits: 4, insertions: 0, deletions: 0, share_percent: 66.67 },
      { name: 'Bob', email: 'bob@example.com', commits: 2, insertions: 0, deletions: 0, share_percent: 33.33 },
    ]
    const { rerender } = render(
      <ContributionBars rows={rows} otherAuthors={0} otherCommits={0} otherShare={0} onSelect={onSelect} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Bob/ }))
    expect(onSelect).toHaveBeenLastCalledWith('bob@example.com')
    rerender(
      <ContributionBars
        rows={rows}
        otherAuthors={0}
        otherCommits={0}
        otherShare={0}
        selected="BOB@example.com"
        onSelect={onSelect}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Bob/ }))
    expect(onSelect).toHaveBeenLastCalledWith(undefined)
  })
})

describe('authors without e-mail', () => {
  const rows = [
    { name: 'Ada', email: 'ada@example.com', commits: 4, insertions: 0, deletions: 0, share_percent: 66.67 },
    { name: 'No Mail', email: '', commits: 2, insertions: 0, deletions: 0, share_percent: 33.33 },
  ]

  it('are not shown as selected without a filter and are not clickable', () => {
    const onSelect = vi.fn()
    render(<ContributionBars rows={rows} otherAuthors={0} otherCommits={0} otherShare={0} selected="" onSelect={onSelect} />)
    expect(screen.getAllByRole('button')).toHaveLength(1)
    expect(screen.getByRole('button', { name: /Ada/ }).getAttribute('aria-pressed')).toBe('false')
    expect(screen.getByText('No Mail')).toBeTruthy()
  })

  it('do not appear as the selected author in the filter', () => {
    render(
      <AuthorFilter
        authors={[
          { name: 'No Mail', email: '', commits: 2 },
          { name: 'Ada', email: 'ada@example.com', commits: 4 },
        ]}
        value=""
        onChange={vi.fn()}
      />,
    )
    expect(screen.queryByText('No Mail')).toBeNull()
  })
})
