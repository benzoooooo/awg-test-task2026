# Agent instructions

The product brand is **AWG GitPulse**. Use `gitpulse` for the Python package,
modules, and filesystem paths. The distribution name is `awg-gitpulse-test`.

## Cursor bridge

Before planning or editing, read and apply every applicable rule in
`.cursor/rules/*.mdc`. `.cursor/` is the source of truth for this repository.

## Project orientation

- Product code and packaging are developed from `dev`.
- Domain documentation is canonical on the orphan `docs/vault` branch.
- Use a separate worktree for vault changes; never copy the vault into `dev`.
- Read the vault root map and ADRs before architecture work.
- Pull requests target `dev`.
- `main` receives only release merges.

## Agent responsibilities

- Implement against acceptance criteria in `docs/vault`.
- Keep the public API stable: `create_router`, `create_app`, `mount_static_ui`.
- Run `make ci-check` before opening or updating a PR.
- Record timestamps in `TIMELOG.md`:
  - `build_started` when implementation begins
  - `dod_submitted` when Definition of Done is met
- Do not expand scope without an explicit request.
- Do not force-push, rewrite shared history, or bypass hooks.
- Use Conventional Commits and single quotes where the formatter allows.
- Imports stay at file top — never inside functions or conditionals.

## Human responsibilities (do not silently take over)

- Product priorities and trade-offs
- Final acceptance of UX and DoD
- Hosting credentials and production deploy decisions
- Publishing release tags when acting as maintainer of record

## Privacy

This is a public repository. Disclose only the git-analytics domain. Mentions of
internal projects, products, infrastructure, or customers are forbidden.
