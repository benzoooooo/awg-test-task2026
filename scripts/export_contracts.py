"""Export OpenAPI golden contract from the fixture app."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gitpulse.fastapi_app import create_app
from gitpulse.settings import GitPulseSettings


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / 'contracts' / 'openapi.json'
    repo = root
    os.environ.setdefault('GITPULSE_REPO_PATH', str(repo))
    app = create_app(
        mount_path='/git',
        repo_path=repo,
        mount_ui=False,
        settings=GitPulseSettings(remote_enabled=False),
    )
    schema = app.openapi()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
