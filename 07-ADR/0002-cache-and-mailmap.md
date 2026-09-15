---
title: ADR 0002 Cache and mailmap
type: adr
status: accepted
---

# ADR 0002 — Cache and mailmap

## Decision

Author identity uses git mailmap (`--use-mailmap`). Heavy aggregations must be bounded (commit window) and may be cached by repository tip SHA.

## Consequences

Contribution percentages without mailmap are considered incorrect. Full `--numstat` scans are an extension point for candidates, not the reference default.
