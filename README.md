# AWG GitPulse — test task (2026)

Hiring exercise for an AI-engineering teammate. The repository ships a **reference
satellite library**: a Python package that mounts into a FastAPI host, ships its
own React UI, and surfaces local git metadata through a clean module boundary.

You will fork this pattern into your own project, connect arbitrary public
repositories, and extend analytics. The reference is intentionally incomplete —
it demonstrates packaging, mounting, and process, not the full product.

## What you get

- Python package `awg-gitpulse-test` (import name `gitpulse`)
- Public host API: `create_router`, `create_app`, `mount_static_ui`
- React + TypeScript + Vite UI packaged into the wheel
- Local git adapter (argv-only, timeouts, mailmap, no hooks)
- Branches: `dev` (integration), `main` (release), `docs/vault` (DDD vault)
- Cursor rules, PR template, `AGENTS.md`, `TIMELOG.md`

## What you must build

1. Move into your own repository (keep the satellite-library shape).
2. Accept any public git URL, clone it safely, and analyze it.
3. Add an action filter by user.
4. Ship an activity / contribution dashboard (share per author, trends).
5. Deploy somewhere public and connect a large real repository.
6. Track time in `TIMELOG.md` (`build_started`, `dod_submitted`).

If you have hosting — use it. If not — write [@mazazyrikbeats](https://t.me/mazazyrikbeats).

## Definition of Done

- Service is reachable on the public internet
- A large public repository is connected and visible in the UI
- User filter works
- Contribution / activity metrics are visible and explained
- PRs followed gitflow into `dev`, vault decisions recorded where needed
- `TIMELOG.md` contains start and DoD timestamps

## Evaluation criteria

| Area | What we look for |
|------|------------------|
| Packaging | Wheel installs; host mounts the module under a prefix |
| Process | Conventional Commits, PR → `dev`, vault/ADR discipline |
| Git engineering | Safety (no shell, timeouts, hook disable), mailmap, caching |
| Product sense | Clear UX, honest metrics, documented limits |
| Agent harness | Useful `AGENTS.md` / rules; human vs agent split respected |
| Delivery | Live URL + large repo demo |

## Human vs agent

Read both:

- **This README** — assignment, DoD, evaluation, local runbook (human)
- **[AGENTS.md](AGENTS.md)** — implementation constraints for coding agents

Decisions a human must own and defend: module boundaries, cache strategy, ADR
updates, prioritization, and final acceptance of the deployed result.

## Local quickstart (reference)

```bash
# Node 20+ and pnpm via corepack; Poetry 2.x
export PATH="$HOME/.local/bin:$PATH"
make install
make ci-check
poetry run uvicorn fixtures.host.app:app --reload
# UI  http://127.0.0.1:8000/git/
# API http://127.0.0.1:8000/git/api/v1/health
```

Package release:

```bash
make package
# dist/*.whl + SHA256SUMS
# see examples/host-vendor for vendoring the wheel into a host app
```

## Gitflow

- Feature branches from `origin/dev`
- Pull requests target `dev`
- `docs/vault` is an orphan branch edited only from its worktree — never merge it
- `main` receives release merges and version tags (`v0.1.0`, …)

## TIMELOG

Agents must append ISO-8601 UTC rows when a build starts and when DoD is submitted:

```bash
make timelog-start
make timelog-dod
```
