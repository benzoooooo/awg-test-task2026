---
title: ADR 0004 Commit index and metric definitions
type: adr
status: accepted
---

# ADR 0004 — Commit index and metric definitions

Refines [[07-ADR/0002-cache-and-mailmap]].

## Context

The reference computed contributions from different windows (all of `HEAD` without a
branch, the newest 500 commits with a branch) and scanned history once per request.
Large repositories need one bounded pass and metrics that agree with each other.

## Decision

- One streaming `git log --use-mailmap --no-merges` pass per (repository, branch, tip
  SHA) builds a columnar index: sha, author timestamp, author UTC offset, author id.
  The pass stops at `max_commits_scan` newest commits and marks the index `truncated`.
- Indexes live in an in-process LRU (`index_cache_size`). A new tip replaces older
  entries for that branch; clones warm the index for the default branch when ready.
- Author identity is the mailmap-canonical e-mail (case-insensitive), falling back
  to name when e-mail is empty. The author filter takes that e-mail.
- Metrics over the selected window (`since`, author date, UTC):
  - commits — non-merge commits reachable from the branch tip;
  - share — author commits / window commits (activity, not value or lines);
  - core contributors — smallest number of top authors covering at least 50% of commits;
  - trend — continuous weekly buckets for spans up to 18 months, monthly beyond,
    zero-filled until today; with an author filter, the author's series is overlaid;
  - activity by hour — weekday x hour in each author's local time.
- The author filter scopes focus metrics (trend overlay, punchcard, commit list,
  author profile); contributor shares keep the whole window for context.
- Legacy `/contributions` and `/activity` use the same index and apply
  `limit_commits` consistently to the newest commits.

## Consequences

- Line counts (`insertions`, `deletions`) stay zero; blobless clones make them
  prohibitively expensive.
- One person committing under several e-mails without a `.mailmap` counts as several
  contributors; the UI states this.
- Memory is bounded by `index_cache_size x max_commits_scan` rows.
