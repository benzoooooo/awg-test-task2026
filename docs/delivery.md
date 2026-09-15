# Delivery notes — v0.2.0

What was built on top of the reference satellite library, how the metrics are
defined, and where the limits are. Decisions are recorded on the `docs/vault`
branch: `07-ADR/0003-remote-clone-isolation.md`,
`07-ADR/0004-commit-index-and-metrics.md`, `05-Product/Acceptance Criteria.md`.

## Requirements map

| Requirement | Implementation |
|-------------|----------------|
| Own repository, satellite-library shape | Fork. Public API unchanged: `create_router`, `create_app`, `mount_static_ui` (new optional `settings`). Import-linter contracts still hold. |
| Accept any public git URL, clone safely | `gitpulse.git.remote` (validation, hardened clone/fetch, size/time watchdog) and `gitpulse.git.registry` (background clone pool, LRU, restore from disk). |
| Filter actions by user | `author` (mailmap-canonical e-mail) on `/dashboard`, `/commits`, `/activity`. UI: author combobox, click a contributor or commit author; the filter lives in the URL. |
| Activity / contribution dashboard | `GET /repos/{id}/dashboard` + React workspace: tiles, trend, contribution share, activity by hour, commit list, metric explanations. |
| Public deploy with a large repository | `Dockerfile`, `docker-compose.yml`, `deploy/host/app.py`; `GITPULSE_PRELOAD_URLS` pins the demo repository. |
| TIMELOG | `build_started` / `dod_submitted` rows in `TIMELOG.md`. |

## Metrics

All metrics use non-merge commits reachable from the selected branch tip, bucketed by
author date. They are computed from one streaming `git log` pass per branch tip and
cached until the tip changes.

- **Commits** — non-merge commits in the period.
- **Contributors** — distinct identities after `.mailmap`, grouped by e-mail.
- **Share** — author commits / all commits in the period. Activity, not impact.
- **Core contributors** — the smallest number of top authors covering ≥ 50% of commits.
- **Activity trend** — continuous weekly buckets (monthly for spans over 18 months),
  zero-filled to today; with an author filter the author's series is overlaid.
- **Activity by hour** — weekday × hour in each author's own time zone.

## Safety model

- `https://` only; rejects credentials, `ext::`, scp syntax, IP or localhost hosts,
  ports, queries, fragments, dot segments; optional host allowlist.
- Every resolved address must be public (SSRF), checked before clone and fetch.
- git runs argv-only with `protocol.allow=never` + `protocol.https.allow=always`,
  hooks/credential helpers/askpass/templates/redirects disabled, no system or global
  config, URL after `--`.
- Bare, blobless, tagless clones in per-repository directories, renamed atomically;
  killed on timeout or when the directory exceeds the size limit.
- Analytics read clones with `GIT_NO_LAZY_FETCH=1`: no network on the read path.

## HTTP API (under `/git/api/v1`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/config` | Limits and whether remote repositories are enabled |
| GET / POST | `/repos` | List / connect `{"url": "https://…"}` (202, idempotent) |
| GET | `/repos/{id}` | Clone status (`pending`, `cloning`, `ready`, `failed`) |
| POST | `/repos/{id}/refresh` | Fetch updates or retry a failed clone |
| GET | `/repos/{id}/dashboard` | `branch`, `since`, `author`, `granularity`, `top` |
| GET | `/repos/{id}/commits` | `branch`, `author`, `since`, `limit`, `skip` |
| GET | `/repos/{id}/authors` | Authors of a branch / period |
| GET | `/repos/{id}/summary`, `/branches`, `/contributions`, `/activity` | Reference endpoints, per repository |

The reference flat routes (`/summary`, `/commits`, …) still serve `repo_path` when a
host passes one; that repository is also listed as `local`.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `GITPULSE_REMOTE_ENABLED` | `false` | Enable cloning public URLs (Docker image: `true`) |
| `GITPULSE_DATA_DIR` | `.gitpulse-data` | Clone storage (Docker: `/data` volume) |
| `GITPULSE_PRELOAD_URLS` | — | Comma-separated URLs cloned at start and never evicted |
| `GITPULSE_ALLOWED_HOSTS` | — | Comma-separated host allowlist; empty = any public host |
| `GITPULSE_BLOCK_PRIVATE_NETWORKS` | `true` | SSRF guard; disable only for local development behind fake-IP DNS/VPN |
| `GITPULSE_MAX_REPOS` | `20` | Remote clones kept; least recently used unpinned one is evicted |
| `GITPULSE_MAX_REPO_SIZE_MB` | `1536` | Size limit per clone |
| `GITPULSE_CLONE_TIMEOUT_SEC` / `GITPULSE_FETCH_TIMEOUT_SEC` | `900` / `300` | Network time limits |
| `GITPULSE_MAX_PARALLEL_CLONES` | `2` | Worker pool size |
| `GITPULSE_REFRESH_INTERVAL_SEC` | `900` | Background fetch when an opened clone is older (0 disables) |
| `GITPULSE_MAX_COMMITS_SCAN` | `400000` | Newest commits indexed per branch |
| `GITPULSE_INDEX_CACHE_SIZE` | `6` | Branch indexes kept in memory |
| `GITPULSE_LOG_TIMEOUT_SEC` | `180` | Timeout for history scans |

## Run

```bash
make install
make ci-check
poetry run uvicorn fixtures.host.app:app --reload
# http://127.0.0.1:8000/git/ — fixture host enables remote repositories and lists this repo as "local"
```

If your resolver returns private addresses for public hosts (VPN or proxy with
fake-IP DNS), start with `GITPULSE_BLOCK_PRIVATE_NETWORKS=false`. Never do this on a
public server.

### Production (Docker + HTTPS)

`docker-compose.yml` runs GitPulse on an internal network behind Caddy, which obtains
and renews a Let's Encrypt certificate automatically. Only Caddy publishes ports.

1. Point a hostname at the server: an `A` record with the public IPv4 (for example a
   free No-IP hostname; remove any stale `AAAA` record). Check with `dig +short <host>`.
2. Open inbound TCP 80 and 443 (and UDP 443 for HTTP/3) in the firewall or security group.
   Port 80 must stay open: the ACME challenge and HTTP→HTTPS redirect use it.
3. Configure and start:

   ```bash
   git clone https://github.com/<owner>/awg-test-task2026.git && cd awg-test-task2026
   cp .env.example .env   # set GITPULSE_DOMAIN and ACME_EMAIL
   docker compose up -d --build
   docker compose logs -f caddy   # "certificate obtained successfully"
   ```

4. Open `https://<host>/git/`. The pinned repository from `GITPULSE_PRELOAD_URLS` clones
   in the background; its status is visible on the home page.

Troubleshooting: ACME failures are almost always DNS not yet pointing to the server or
port 80 blocked. Let's Encrypt rate-limits repeated failures, so fix DNS/ports before
retrying (`docker compose restart caddy`). Certificates persist in the `caddy-data`
volume; do not delete it between deploys. Free No-IP hostnames must be confirmed every
30 days or they stop resolving.

## Known limits

- Share counts commits, not lines or review work; bots count like people.
- Without a `.mailmap`, one person with several e-mails appears several times.
- Hosts that answer with HTTP redirects (renamed repositories) are rejected — use the canonical URL.
- DNS rebinding between the address check and git's own resolution is a residual risk;
  add an egress firewall in production.
- No authentication: any visitor can add repositories up to `GITPULSE_MAX_REPOS`.
- Registry and caches are per process: run a single worker per data directory.
