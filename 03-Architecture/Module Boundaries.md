---
title: Module Boundaries
type: architecture
status: accepted
---

# Module Boundaries

- `gitpulse.core` — pure domain models
- `gitpulse.settings` — environment-driven limits (`GITPULSE_*`)
- `gitpulse.git` — CLI adapter: local reads, `remote` (URL validation, hardened clone/fetch), `registry` (clone lifecycle)
- `gitpulse.analytics` — `index` (commit index + tip-SHA cache) and `metrics` (pure aggregations)
- `gitpulse.fastapi_app` — HTTP + static UI mount

Remote cloning: [[07-ADR/0003-remote-clone-isolation]]. Metrics: [[07-ADR/0004-commit-index-and-metrics]].

Public host API: `create_router`, `create_app`, `mount_static_ui`.
