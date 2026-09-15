"""Git CLI adapter: argv-only subprocess with timeouts and limits."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from gitpulse.git.errors import GitCommandError, GitNotARepositoryError

DEFAULT_TIMEOUT_SEC = 30
DEFAULT_MAX_OUTPUT_BYTES = 8 * 1024 * 1024


def resolve_repo(path: Path) -> Path:
    """Resolve and validate that path is a git work tree or bare repo."""

    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise GitNotARepositoryError(f'path does not exist: {resolved}')
    git_dir = resolved / '.git'
    if not git_dir.exists() and not (resolved / 'HEAD').exists():
        raise GitNotARepositoryError(f'not a git repository: {resolved}')
    return resolved


def run_git(
    repo: Path,
    args: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    max_output: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> str:
    """Run `git -C <repo> ...` with hooks disabled and UTF-8 replacement decoding."""

    cmd = [
        'git',
        '-c',
        'core.hooksPath=/dev/null',
        '-C',
        str(repo),
        *args,
    ]
    env = {
        **os.environ,
        'GIT_OPTIONAL_LOCKS': '1',
        'LC_ALL': 'C.UTF-8',
        'LANG': 'C.UTF-8',
    }
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            timeout=timeout,
            env=env,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(f'git timed out after {timeout}s: {" ".join(args)}') from exc

    if completed.returncode != 0:
        err = completed.stderr.decode('utf-8', errors='replace').strip()
        raise GitCommandError(err or f'git failed ({completed.returncode}): {" ".join(args)}')

    raw = completed.stdout
    if len(raw) > max_output:
        raise GitCommandError(f'git output exceeded {max_output} bytes')
    return raw.decode('utf-8', errors='replace')
