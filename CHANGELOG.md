# Changelog

All notable changes to this project are documented in this file.

## [0.2.1] — 2026-09-15

### Fixed

- UI: authors whose commits have no e-mail looked selected without an author filter
  and could not be filtered; they are now shown as non-filterable rows

### Documentation

- Live deployment link and `dod_submitted` in `TIMELOG.md`

## [0.2.0] — 2026-09-15

### Added

- Connect any public `https://` repository: validated URLs, SSRF check, hardened bare
  blobless clones with size and time limits, background clone pool, LRU eviction,
  pinned preload URLs, background refresh, restore from disk
- Multi-repository API under `/repos/{id}` and `/config`
- Contribution dashboard endpoint: shares, core contributors, continuous trend,
  weekday x hour activity, author profile
- `author` and `since` filters on commits, activity, and authors
- React workspace: repository list, clone status, period/branch/author filters kept in
  the URL, trend chart with table view, contribution share, activity by hour, commit list,
  metric explanations
- `GitPulseSettings` (`GITPULSE_*` environment), Dockerfile, deploy host
- Production compose stack with Caddy reverse proxy and automatic Let's Encrypt HTTPS
- GitHub Actions: `make ci-check`, Docker image smoke test, compose/Caddy config validation
- Vault ADR 0003 (remote clone isolation) and ADR 0004 (commit index and metrics)

### Changed

- Analytics use one cached commit index per branch tip; `/contributions` and `/activity`
  apply `limit_commits` consistently to the newest commits
- Read-only git calls set `GIT_OPTIONAL_LOCKS=0` and pass refs after `--end-of-options`
- `list_authors` uses `git shortlog`; summary is cached by HEAD

### Fixed

- Index cache kept a stale build lock after a failed history scan
- `first_commit_at` returned the newest commit (`git log --reverse -n1` limits before reversing)

## [0.1.0] — 2026-09-15

### Added

- Embeddable `gitpulse` package with `create_router`, `create_app`, `mount_static_ui`
- Local git adapter with mailmap, timeouts, and hook disable
- React UI for branches, commits, authors, contribution share, and weekly activity
- Fixture host, vendor-host example, contracts export, and privacy gate
- Orphan `docs/vault` DDD map and ADRs
