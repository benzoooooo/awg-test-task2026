---
title: ADR 0001 Module boundaries
type: adr
status: accepted
---

# ADR 0001 — Module boundaries

## Decision

Keep domain models free of FastAPI and subprocess I/O. Hosts integrate only through `create_router` / `create_app` / `mount_static_ui`.

## Consequences

Import-linter enforces the layering. UI ships as prebuilt static assets inside the wheel.
