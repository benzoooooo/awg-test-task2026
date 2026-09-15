import { useState, type KeyboardEvent } from 'react'
import type { TrendBucket } from '../api'
import { clamp, columnPath, niceTicks } from '../chart'
import { formatCount } from '../format'
import { useElementWidth } from '../hooks'

const HEIGHT = 240
const TOP = 12
const AXIS = 30
const LEFT = 48
const RIGHT = 8

type Props = {
  buckets: TrendBucket[]
  granularity: 'week' | 'month'
  authorName?: string | null
}

export function TrendChart({ buckets, granularity, authorName }: Props) {
  const [ref, width] = useElementWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const [showTable, setShowTable] = useState(false)
  const unit = granularity === 'week' ? 'week' : 'month'
  const hasAuthor = Boolean(authorName)

  if (!buckets.length) {
    return <p className="muted empty">No commits in this period.</p>
  }

  const count = buckets.length
  const plotWidth = Math.max(width - LEFT - RIGHT, 60)
  const plotHeight = HEIGHT - TOP - AXIS
  const peak = Math.max(...buckets.map((bucket) => bucket.commits), 1)
  const ticks = niceTicks(peak)
  const top = ticks[ticks.length - 1]
  const band = plotWidth / count
  const columnWidth = band >= 4 ? Math.min(24, band - 2) : Math.max(band - 0.5, 0.5)
  const baseline = TOP + plotHeight
  const y = (value: number) => baseline - (value / top) * plotHeight
  const heightOf = (value: number) => (value > 0 ? Math.max(baseline - y(value), 1) : 0)
  const labelIndexes = Array.from(new Set([0, Math.floor((count - 1) / 2), count - 1]))
  const current = active === null ? null : buckets[active]

  const onKey = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const delta = event.key === 'ArrowRight' ? 1 : -1
    setActive((prev) => clamp((prev ?? (delta > 0 ? -1 : count)) + delta, 0, count - 1))
  }

  return (
    <div className="chart" ref={ref}>
      <div className="chart-head">
        {hasAuthor ? (
          <ul className="legend">
            <li>
              <span className="key key-muted" aria-hidden="true" />
              All commits
            </li>
            <li>
              <span className="key key-accent" aria-hidden="true" />
              {authorName}
            </li>
          </ul>
        ) : (
          <p className="chart-sub">Non-merge commits per {unit}</p>
        )}
        <button
          type="button"
          className="link-button"
          aria-pressed={showTable}
          onClick={() => setShowTable((value) => !value)}
        >
          {showTable ? 'Chart view' : 'Table view'}
        </button>
      </div>

      {showTable ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">{granularity === 'week' ? 'Week' : 'Month'}</th>
                <th scope="col">Commits</th>
                {hasAuthor && <th scope="col">{authorName}</th>}
                <th scope="col">Active authors</th>
              </tr>
            </thead>
            <tbody>
              {[...buckets].reverse().map((bucket) => (
                <tr key={bucket.start}>
                  <th scope="row">{bucket.period}</th>
                  <td>{formatCount(bucket.commits)}</td>
                  {hasAuthor && <td>{formatCount(bucket.author_commits ?? 0)}</td>}
                  <td>{formatCount(bucket.active_authors)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="plot">
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            tabIndex={0}
            aria-label={`Commits per ${unit}: ${count} periods from ${buckets[0].period} to ${
              buckets[count - 1].period
            }, peak ${formatCount(peak)}. Use arrow keys to inspect periods.`}
            onKeyDown={onKey}
            onBlur={() => setActive(null)}
            onPointerLeave={() => setActive(null)}
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line
                  x1={LEFT}
                  x2={LEFT + plotWidth}
                  y1={y(tick)}
                  y2={y(tick)}
                  className={tick === 0 ? 'axis-line' : 'grid-line'}
                />
                <text x={LEFT - 8} y={y(tick)} className="tick" textAnchor="end" dominantBaseline="middle">
                  {formatCount(tick)}
                </text>
              </g>
            ))}
            {buckets.map((bucket, index) => {
              const x = LEFT + index * band + (band - columnWidth) / 2
              return (
                <g key={bucket.start}>
                  {active === index && (
                    <rect x={LEFT + index * band} y={TOP} width={band} height={plotHeight} className="hover-band" />
                  )}
                  <path
                    d={columnPath(x, y(bucket.commits), columnWidth, heightOf(bucket.commits))}
                    className={hasAuthor ? 'bar-muted' : 'bar-accent'}
                  />
                  {hasAuthor && bucket.author_commits ? (
                    <path
                      d={columnPath(
                        x,
                        baseline - heightOf(bucket.author_commits),
                        columnWidth,
                        heightOf(bucket.author_commits),
                      )}
                      className="bar-accent"
                    />
                  ) : null}
                  <rect
                    data-testid="trend-hit"
                    x={LEFT + index * band}
                    y={TOP}
                    width={band}
                    height={plotHeight}
                    fill="transparent"
                    onPointerEnter={() => setActive(index)}
                  />
                </g>
              )
            })}
            {labelIndexes.map((index) => {
              const anchor = index === 0 ? 'start' : index === count - 1 ? 'end' : 'middle'
              const x =
                index === 0 ? LEFT : index === count - 1 ? LEFT + plotWidth : LEFT + (index + 0.5) * band
              return (
                <text key={index} x={x} y={HEIGHT - 8} className="tick" textAnchor={anchor}>
                  {buckets[index].period}
                </text>
              )
            })}
          </svg>
          {current && active !== null && (
            <div
              className="tooltip"
              role="status"
              style={{ left: clamp(LEFT + (active + 0.5) * band, 90, width - 90) }}
            >
              <span className="tooltip-title">{current.period}</span>
              <span className="tooltip-row">
                <span className={`line-key ${hasAuthor ? 'key-muted' : 'key-accent'}`} aria-hidden="true" />
                <strong>{formatCount(current.commits)}</strong> commits
              </span>
              {hasAuthor && (
                <span className="tooltip-row">
                  <span className="line-key key-accent" aria-hidden="true" />
                  <strong>{formatCount(current.author_commits ?? 0)}</strong> {authorName}
                </span>
              )}
              <span className="tooltip-row muted">{formatCount(current.active_authors)} active authors</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
