import { formatCount } from '../format'

export function MetricsHelp({ maxCommits }: { maxCommits: number | null }) {
  return (
    <details className="card help" id="metrics">
      <summary>
        <h2>How these metrics are computed</h2>
      </summary>
      <dl className="help-list">
        <div>
          <dt>Commits</dt>
          <dd>
            Non-merge commits reachable from the selected branch tip, filtered by author date. Merge commits are
            excluded because they repeat work already counted in their parents.
          </dd>
        </div>
        <div>
          <dt>Contributors and the author filter</dt>
          <dd>
            Identities are resolved through the repository&apos;s <code>.mailmap</code> and grouped by e-mail.
            Without a mailmap, one person committing from several e-mails appears several times. Bots count like
            people.
          </dd>
        </div>
        <div>
          <dt>Share</dt>
          <dd>
            An author&apos;s commits divided by all commits in the period. It measures activity, not impact: a
            one-line fix and a large feature count the same. Line counts are not computed because repositories are
            cloned without file contents.
          </dd>
        </div>
        <div>
          <dt>Core contributors</dt>
          <dd>
            The smallest number of top authors whose commits add up to at least half of the period. Low values mean
            knowledge is concentrated in few people.
          </dd>
        </div>
        <div>
          <dt>Activity trend</dt>
          <dd>
            Commits per ISO week for spans up to 18 months, per month beyond, in UTC. Empty periods are shown as
            zero up to today. With an author filter, the author&apos;s commits are drawn over all commits on the
            same scale.
          </dd>
        </div>
        <div>
          <dt>Activity by hour</dt>
          <dd>
            Weekday and hour in each author&apos;s own time zone as recorded in the commit, so it shows working
            rhythm rather than server time.
          </dd>
        </div>
        <div>
          <dt>Freshness and limits</dt>
          <dd>
            Data reflects the last fetch shown in the header; stale repositories refresh in the background when
            opened. {maxCommits ? `At most ${formatCount(maxCommits)} newest commits per branch are scanned. ` : ''}
            Author dates can be wrong after rebases or with misconfigured clocks.
          </dd>
        </div>
      </dl>
    </details>
  )
}
