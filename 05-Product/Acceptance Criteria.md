---
title: Acceptance Criteria
type: product
status: active
---

# Acceptance Criteria — remote analytics

| ID | Criterion | Decided in | Verified by |
|----|-----------|------------|-------------|
| AC-1 | A visitor pastes a public `https://` git URL; the service clones it in the background and shows status (pending, cloning, ready, failed with reason). | [[07-ADR/0003-remote-clone-isolation]] | `tests/test_registry_api.py` |
| AC-2 | Unsafe URLs (non-https, credentials, `ext::`, IP/localhost hosts, private DNS, ports, queries) are rejected before any git process starts. | [[07-ADR/0003-remote-clone-isolation]] | `tests/test_remote_url.py` |
| AC-3 | Clones are bounded by time and size, isolated per repository, and reads never fetch from the network. | [[07-ADR/0003-remote-clone-isolation]] | `tests/test_remote_url.py`, `tests/test_registry_api.py` |
| AC-4 | Commits, trend, activity by hour, and the commit list can be filtered by one author (mailmap-canonical e-mail); the filter survives reloads through the URL. | [[07-ADR/0004-commit-index-and-metrics]] | `tests/test_analytics.py`, `ui/src/pages/Workspace.test.tsx` |
| AC-5 | The dashboard shows per-author share, core contributors, a continuous trend, and activity by hour for a selectable period and branch, with an explanation of every metric. | [[07-ADR/0004-commit-index-and-metrics]] | `tests/test_analytics.py`, UI |
| AC-6 | Analytics for a branch tip are computed once and reused until the tip changes. | [[07-ADR/0002-cache-and-mailmap]], [[07-ADR/0004-commit-index-and-metrics]] | `tests/test_analytics.py` |
| AC-7 | The package still mounts under a host prefix through `create_router` / `create_app` / `mount_static_ui`; remote cloning is opt-in. | [[07-ADR/0001-module-boundaries]] | `tests/test_registry_api.py`, `make package-verify` |
