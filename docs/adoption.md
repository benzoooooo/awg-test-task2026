# Adoption notes

- Mount path defaults to `/git`.
- Pass `repo_path` into `create_router` / `create_app` to expose one local repository.
- Pass `settings=GitPulseSettings(remote_enabled=True, data_dir=...)` (or set
  `GITPULSE_REMOTE_ENABLED=true`) to let users connect public repositories. Remote
  cloning is off by default so embedding never starts network access by surprise.
- Run a single worker per data directory: the registry and caches are in-process.
- Build UI with `make ui-package` before `make package`.
- Prefer vendoring the wheel into the host repository for reproducible deploys.
- See `docs/delivery.md` for configuration, API, and limits.
