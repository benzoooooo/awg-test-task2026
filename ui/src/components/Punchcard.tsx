import { useState } from 'react'
import { formatCount } from '../format'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const LEVELS = 6
const pad = (hour: number) => String(hour).padStart(2, '0')

export function Punchcard({ grid }: { grid: number[][] }) {
  const [active, setActive] = useState<{ day: number; hour: number } | null>(null)
  const values = grid.flat()
  const peak = Math.max(0, ...values)
  const total = values.reduce((sum, value) => sum + value, 0)
  if (!total) return <p className="muted empty">No commits in this period.</p>
  const level = (value: number) => (value === 0 ? 0 : Math.min(LEVELS, Math.ceil((value / peak) * LEVELS)))

  return (
    <div className="punchcard">
      <div className="punch-grid" onPointerLeave={() => setActive(null)}>
        {grid.map((row, day) => (
          <div className="punch-row" key={DAYS[day]}>
            <span className="punch-day">{DAYS[day]}</span>
            {row.map((value, hour) => (
              <span
                key={hour}
                role="img"
                data-testid="punch-cell"
                tabIndex={-1}
                className={`punch-cell level-${level(value)}${
                  active?.day === day && active.hour === hour ? ' is-active' : ''
                }`}
                aria-label={`${DAYS[day]} ${pad(hour)}:00, ${value} commits`}
                onPointerEnter={() => setActive({ day, hour })}
              />
            ))}
          </div>
        ))}
        <div className="punch-row punch-hours" aria-hidden="true">
          <span className="punch-day" />
          {Array.from({ length: 24 }, (_, hour) => (
            <span key={hour} className="punch-hour">
              {hour % 6 === 0 ? pad(hour) : ''}
            </span>
          ))}
        </div>
      </div>
      <div className="punch-foot">
        <span className="readout" role="status">
          {active ? (
            <>
              <strong>{formatCount(grid[active.day][active.hour])}</strong> commits · {DAYS[active.day]}{' '}
              {pad(active.hour)}:00–{pad(active.hour)}:59
            </>
          ) : (
            <span className="muted">Hover a cell · author local time</span>
          )}
        </span>
        <span className="scale" aria-hidden="true">
          Fewer
          {Array.from({ length: LEVELS }, (_, index) => (
            <span key={index} className={`punch-cell level-${index + 1}`} />
          ))}
          More
        </span>
      </div>
    </div>
  )
}
