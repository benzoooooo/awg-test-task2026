import { useEffect, useState } from 'react'
import type { Author } from '../api'
import { formatCount } from '../format'

type Props = {
  authors: Author[]
  value: string
  onChange: (email: string | undefined) => void
}

export function AuthorFilter({ authors, value, onChange }: Props) {
  const [text, setText] = useState(value)
  const [hint, setHint] = useState<string | null>(null)

  useEffect(() => {
    setText(value)
    setHint(null)
  }, [value])

  const find = (raw: string) => {
    const query = raw.trim().toLowerCase()
    return (
      authors.find((author) => author.email.toLowerCase() === query) ??
      authors.find((author) => author.name.toLowerCase() === query)
    )
  }

  const apply = (raw: string) => {
    if (!raw.trim()) {
      setHint(null)
      if (value) onChange(undefined)
      return
    }
    if (!authors.length) return
    const match = find(raw)
    if (!match) {
      setHint('No author with this e-mail or name on the branch')
      return
    }
    setHint(null)
    setText(match.email)
    if (match.email.toLowerCase() !== value.toLowerCase()) onChange(match.email)
  }

  // Some histories contain commits without an e-mail; an empty filter must not match them.
  const selected = value ? authors.find((author) => author.email.toLowerCase() === value.toLowerCase()) : undefined

  return (
    <div className="field field-author">
      <label htmlFor="author-filter" className="field-label">
        Author
      </label>
      <div className="combo">
        <input
          id="author-filter"
          list="author-options"
          value={text}
          autoComplete="off"
          spellCheck={false}
          placeholder={authors.length ? `All ${formatCount(authors.length)} authors` : 'All authors'}
          onChange={(event) => {
            setText(event.target.value)
            const query = event.target.value.trim().toLowerCase()
            const exact = query ? authors.find((author) => author.email.toLowerCase() === query) : undefined
            if (exact) apply(exact.email)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') apply(text)
            if (event.key === 'Escape') {
              setText('')
              onChange(undefined)
            }
          }}
          onBlur={() => apply(text)}
        />
        {value && (
          <button
            type="button"
            className="combo-clear"
            aria-label="Clear author filter"
            onClick={() => {
              setText('')
              onChange(undefined)
            }}
          >
            ×
          </button>
        )}
        <datalist id="author-options">
          {authors.slice(0, 3000).map((author) => (
            <option key={author.email || author.name} value={author.email}>
              {`${author.name} · ${author.commits}`}
            </option>
          ))}
        </datalist>
      </div>
      {hint ? (
        <span className="field-note is-error">{hint}</span>
      ) : selected ? (
        <span className="field-note">{selected.name}</span>
      ) : null}
    </div>
  )
}
