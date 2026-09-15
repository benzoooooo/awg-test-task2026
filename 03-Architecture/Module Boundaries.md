---
title: Module Boundaries
type: architecture
status: accepted
---

# Module Boundaries

- `gitpulse.core` — pure domain models
- `gitpulse.git` — local CLI adapter
- `gitpulse.analytics` — aggregations over adapter results
- `gitpulse.fastapi_app` — HTTP + static UI mount

Public host API: `create_router`, `create_app`, `mount_static_ui`.
