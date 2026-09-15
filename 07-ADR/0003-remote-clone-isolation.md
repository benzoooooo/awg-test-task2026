---
title: ADR 0003 Remote clone isolation
type: adr
status: accepted
---

# ADR 0003 — Remote clone isolation

## Context

Candidates must accept any public git URL. Cloning user-supplied URLs on a public
server exposes command injection, SSRF, credential leakage, disk exhaustion, and
malicious repository content (hooks, templates, lazy object fetches).

## Decision

- Only `https://` URLs with a public hostname are accepted. Rejected: other schemes,
  scp-style `git@host:path`, `ext::` / `::` transport syntax, userinfo (credentials),
  IP-literal hosts, `localhost`, custom ports, query strings, fragments, `.` / `..`
  path segments. Optional host allowlist via `GITPULSE_ALLOWED_HOSTS`.
- Before every clone and fetch the host is resolved and every address must be global
  (`GITPULSE_BLOCK_PRIVATE_NETWORKS`, default on).
- git runs argv-only with `protocol.allow=never`, `protocol.https.allow=always`,
  `core.hooksPath=/dev/null`, empty `credential.helper` / `core.askPass` /
  `init.templateDir`, `http.followRedirects=false`, `GIT_TERMINAL_PROMPT=0`, and no
  system or global config. The URL is passed after `--`.
- Clones are `--bare --filter=blob:none --no-tags` into `data_dir/tmp/<id>-<nonce>.git`
  and renamed atomically to `data_dir/repos/<id>.git`, where `<id>` is a SHA-256 prefix
  of the normalized host and path. Only the `.mailmap` blob is materialized.
- A watchdog kills git on `clone_timeout_sec` / `fetch_timeout_sec` or when the
  directory exceeds `max_repo_size_mb`. A bounded worker pool limits parallel clones.
- Reads of clones run with `GIT_NO_LAZY_FETCH=1`, so analytics never touch the network.
- The registry holds at most `max_repos` remote clones and evicts the least recently
  used unpinned one. `preload_urls` are pinned. Stale clones are fetched in the
  background after `refresh_interval_sec`.

## Consequences

- No file contents on disk: line-based statistics are out of scope (see ADR 0004).
- Renamed repositories that answer with an HTTP redirect fail with a clear error;
  users paste the canonical URL.
- DNS rebinding between the check and git's own resolution remains a residual risk;
  production should add an egress firewall.
- Without authentication any visitor can fill the registry up to `max_repos`.
