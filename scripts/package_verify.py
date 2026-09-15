"""Verify a built wheel installs and exposes the public API."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=Path, required=True)
    args = parser.parse_args()
    wheels = sorted(args.dist.glob('*.whl'))
    if not wheels:
        print('no wheel in dist/', file=sys.stderr)
        return 1
    wheel = wheels[-1]
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'site'
        target.mkdir()
        subprocess.check_call(
            [
                sys.executable,
                '-m',
                'pip',
                'install',
                '--target',
                str(target),
                str(wheel),
            ]
        )
        env_python = (
            'import sys; '
            f'sys.path.insert(0, {str(target)!r}); '
            'from gitpulse.fastapi_app import create_router, create_app, mount_static_ui; '
            'import gitpulse; print(gitpulse.__version__)'
        )
        subprocess.check_call([sys.executable, '-c', env_python])
    print(f'verified {wheel.name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
