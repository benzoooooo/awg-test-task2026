# Adoption notes

- Mount path defaults to `/git`.
- Pass `repo_path` into `create_router` / `create_app`.
- Build UI with `make ui-package` before `make package`.
- Prefer vendoring the wheel into the host repository for reproducible deploys.
