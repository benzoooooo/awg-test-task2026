"""Git CLI adapter: argv-only subprocess with timeouts and limits."""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from collections.abc import Iterator, Mapping
from pathlib import Path

from gitpulse.git.errors import GitCommandError, GitNotARepositoryError

DEFAULT_TIMEOUT_SEC = 30
DEFAULT_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_STDERR_BYTES = 4096

# Ignore system/global git config (e.g. `url.insteadOf`, credential helpers) for clones we own.
ISOLATED_ENV: Mapping[str, str] = {
    'GIT_CONFIG_NOSYSTEM': '1',
    'GIT_CONFIG_GLOBAL': os.devnull,
}
# Read path for partial clones: never fetch missing objects implicitly.
OFFLINE_CLONE_ENV: Mapping[str, str] = {**ISOLATED_ENV, 'GIT_NO_LAZY_FETCH': '1'}


def resolve_repo(path: Path) -> Path:
    """Resolve and validate that path is a git work tree or bare repo."""

    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise GitNotARepositoryError(f'path does not exist: {resolved}')
    git_dir = resolved / '.git'
    if not git_dir.exists() and not (resolved / 'HEAD').exists():
        raise GitNotARepositoryError(f'not a git repository: {resolved}')
    return resolved


def git_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Environment for every git call: no prompts, no optional locks, stable locale."""

    env = {
        **os.environ,
        'GIT_OPTIONAL_LOCKS': '0',
        'GIT_TERMINAL_PROMPT': '0',
        'LC_ALL': 'C.UTF-8',
        'LANG': 'C.UTF-8',
    }
    if extra:
        env.update(extra)
    return env


def _git_argv(repo: Path, args: list[str]) -> list[str]:
    return ['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args]


def _decode_stderr(raw: bytes) -> str:
    return raw[:MAX_STDERR_BYTES].decode('utf-8', errors='replace').strip()


def run_git(
    repo: Path,
    args: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    max_output: int = DEFAULT_MAX_OUTPUT_BYTES,
    env: Mapping[str, str] | None = None,
) -> str:
    """Run `git -C <repo> ...` with hooks disabled and UTF-8 replacement decoding."""

    try:
        completed = subprocess.run(
            _git_argv(repo, args),
            check=False,
            capture_output=True,
            timeout=timeout,
            env=git_env(env),
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(f'git timed out after {timeout}s: {" ".join(args)}') from exc

    if completed.returncode != 0:
        err = _decode_stderr(completed.stderr)
        raise GitCommandError(err or f'git failed ({completed.returncode}): {" ".join(args)}')

    raw = completed.stdout
    if len(raw) > max_output:
        raise GitCommandError(f'git output exceeded {max_output} bytes')
    return raw.decode('utf-8', errors='replace')


def stream_git(
    repo: Path,
    args: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    env: Mapping[str, str] | None = None,
) -> Iterator[str]:
    """Yield stdout lines of a long-running git command.

    The process is killed when the timeout elapses or when the consumer stops
    iterating early, so callers can bound work by line count without buffering.
    """

    timed_out = threading.Event()
    with tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(
            _git_argv(repo, args),
            stdout=subprocess.PIPE,
            stderr=stderr,
            env=git_env(env),
            shell=False,
        )

        def _kill() -> None:
            timed_out.set()
            proc.kill()

        timer = threading.Timer(timeout, _kill)
        timer.daemon = True
        timer.start()
        try:
            if proc.stdout is None:
                raise GitCommandError('git stdout pipe is unavailable')
            for raw in proc.stdout:
                yield raw.decode('utf-8', errors='replace').rstrip('\n')
            returncode = proc.wait()
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if proc.stdout is not None:
                proc.stdout.close()

        if timed_out.is_set():
            raise GitCommandError(f'git timed out after {timeout}s: {" ".join(args)}')
        if returncode != 0:
            stderr.seek(0)
            err = _decode_stderr(stderr.read(MAX_STDERR_BYTES))
            raise GitCommandError(err or f'git failed ({returncode}): {" ".join(args)}')
