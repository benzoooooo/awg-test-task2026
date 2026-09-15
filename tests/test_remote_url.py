"""Remote URL validation and clone hardening."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gitpulse.git.errors import GitCommandError, InvalidRemoteUrlError
from gitpulse.git.remote import (
    clone_argv,
    ensure_public_host,
    fetch_argv,
    parse_remote_url,
    run_bounded,
)


def test_accepts_public_https_url() -> None:
    remote = parse_remote_url('https://github.com/fastapi/fastapi')
    assert remote.url == 'https://github.com/fastapi/fastapi'
    assert remote.host == 'github.com'
    assert remote.display_name == 'github.com/fastapi/fastapi'
    assert len(remote.repo_id) == 16


def test_equivalent_urls_share_repo_id() -> None:
    first = parse_remote_url('https://github.com/fastapi/fastapi')
    second = parse_remote_url('  https://GitHub.com/FastAPI/fastapi.git/  ')
    assert first.repo_id == second.repo_id


@pytest.mark.parametrize(
    'raw',
    [
        '',
        'http://github.com/a/b',
        'ssh://git@github.com/a/b',
        'git@github.com:a/b.git',
        'ext::sh -c touch% /tmp/pwned',
        'file:///etc/passwd',
        '/srv/repos/private',
        '--upload-pack=touch /tmp/pwned',
        'https://user:secret@github.com/a/b',
        'https://token@github.com/a/b',
        'https://127.0.0.1/a/b',
        'https://[::1]/a/b',
        'https://localhost/a/b',
        'https://svc.localhost/a/b',
        'https://2130706433/a/b',
        'https://github.com:8443/a/b',
        'https://github.com/a/b?ref=main',
        'https://github.com/a/b#readme',
        'https://github.com/a/../b',
        'https://github.com',
        'https://github.com/a b',
        'https://github.com/a/%2e%2e',
    ],
)
def test_rejects_unsafe_urls(raw: str) -> None:
    with pytest.raises(InvalidRemoteUrlError):
        parse_remote_url(raw)


def test_allowlist_is_enforced() -> None:
    with pytest.raises(InvalidRemoteUrlError):
        parse_remote_url('https://github.com/a/b', allowed_hosts=frozenset({'gitlab.com'}))
    assert parse_remote_url('https://gitlab.com/a/b', allowed_hosts=frozenset({'gitlab.com'}))


@pytest.mark.parametrize('address', ['10.0.0.8', '127.0.0.1', '169.254.169.254', '::1', 'fd00::1'])
def test_private_resolution_is_rejected(address: str) -> None:
    with pytest.raises(InvalidRemoteUrlError):
        ensure_public_host('example.com', lambda _host: ['140.82.112.3', address])


def test_public_resolution_is_accepted() -> None:
    ensure_public_host('github.com', lambda _host: ['140.82.112.3', '2606:50c0:8000::153'])


def test_clone_argv_is_hardened(tmp_path: Path) -> None:
    remote = parse_remote_url('https://github.com/fastapi/fastapi')
    argv = clone_argv(remote, tmp_path / 'dest')
    assert argv[0] == 'git'
    for setting in (
        'protocol.allow=never',
        'protocol.https.allow=always',
        'core.hooksPath=/dev/null',
        'credential.helper=',
        'http.followRedirects=false',
    ):
        assert setting in argv
    assert '--bare' in argv
    assert '--filter=blob:none' in argv
    assert argv[argv.index('--') + 1] == remote.url
    assert not any(arg.startswith('--upload-pack') for arg in argv)
    assert 'protocol.allow=never' in fetch_argv(tmp_path / 'dest')


def test_run_bounded_enforces_size_limit(tmp_path: Path) -> None:
    watch = tmp_path / 'clone'
    script = (
        'import pathlib, time, sys; p = pathlib.Path(sys.argv[1]); p.mkdir(); '
        "(p / 'blob').write_bytes(b'x' * 3_000_000); time.sleep(30)"
    )
    with pytest.raises(GitCommandError, match='size limit'):
        run_bounded(
            [sys.executable, '-c', script, str(watch)],
            watch=watch,
            timeout=20,
            max_bytes=1_000_000,
        )


def test_run_bounded_enforces_timeout(tmp_path: Path) -> None:
    with pytest.raises(GitCommandError, match='timed out'):
        run_bounded(
            [sys.executable, '-c', 'import time; time.sleep(30)'],
            watch=tmp_path,
            timeout=0.5,
            max_bytes=1_000_000,
        )
