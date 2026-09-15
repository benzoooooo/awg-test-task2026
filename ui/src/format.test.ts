import { describe, expect, it } from 'vitest'
import { niceTicks, columnPath } from './chart'
import { commitUrl, formatBytes, formatCount, periodFromParam, sinceFor } from './format'

describe('format helpers', () => {
  it('computes since dates in UTC', () => {
    const today = new Date(Date.UTC(2026, 8, 15, 23, 30))
    expect(sinceFor('30d', today)).toBe('2026-08-16')
    expect(sinceFor('365d', today)).toBe('2025-09-15')
    expect(sinceFor('all', today)).toBeUndefined()
  })

  it('parses unknown periods as all time', () => {
    expect(periodFromParam('90d')).toBe('90d')
    expect(periodFromParam('7y')).toBe('all')
    expect(periodFromParam(null)).toBe('all')
  })

  it('formats counts and sizes', () => {
    expect(formatCount(1284)).toBe('1,284')
    expect(formatCount(12900)).toBe('12.9K')
    expect(formatBytes(2_560_000)).toBe('2.4 MB')
  })

  it('links commits only for known forges', () => {
    expect(commitUrl('https://github.com/a/b', 'abc')).toBe('https://github.com/a/b/commit/abc')
    expect(commitUrl('https://gitlab.com/a/b.git', 'abc')).toBe('https://gitlab.com/a/b/-/commit/abc')
    expect(commitUrl('https://git.example.com/a/b', 'abc')).toBeNull()
    expect(commitUrl(null, 'abc')).toBeNull()
  })
})

describe('chart helpers', () => {
  it('produces clean integer ticks', () => {
    expect(niceTicks(1)).toEqual([0, 1])
    expect(niceTicks(7)).toEqual([0, 2, 4, 6, 8])
    expect(niceTicks(930)).toEqual([0, 200, 400, 600, 800, 1000])
  })

  it('skips empty columns', () => {
    expect(columnPath(0, 0, 10, 0)).toBe('')
    expect(columnPath(0, 0, 10, 20)).toContain('Q')
  })
})
