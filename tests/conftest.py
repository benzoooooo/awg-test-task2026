"""Pytest fixtures."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gitpulse.fastapi_app import create_app


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args],
        check=True,
        capture_output=True,
        env={**os.environ, **(env or {})},
    )


def commit_as(repo: Path, name: str, email: str, when: str, message: str) -> None:
    """Commit a unique file change with fixed author/committer identity and date."""

    marker = repo / 'log.txt'
    with marker.open('a', encoding='utf-8') as handle:
        handle.write(f'{when} {message}\n')
    _git(repo, 'add', '-A')
    _git(
        repo,
        'commit',
        '-m',
        message,
        env={
            'GIT_AUTHOR_NAME': name,
            'GIT_AUTHOR_EMAIL': email,
            'GIT_AUTHOR_DATE': when,
            'GIT_COMMITTER_NAME': name,
            'GIT_COMMITTER_EMAIL': email,
            'GIT_COMMITTER_DATE': when,
        },
    )


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / 'repo'
    repo.mkdir()
    _git(repo, 'init', '-b', 'main')
    _git(repo, 'config', 'user.name', 'Ada Lovelace')
    _git(repo, 'config', 'user.email', 'ada@example.com')
    (repo / 'README.md').write_text('one\n', encoding='utf-8')
    _git(repo, 'add', 'README.md')
    _git(repo, 'commit', '-m', 'feat: initial')
    _git(repo, 'config', 'user.name', 'Ada L.')
    _git(repo, 'config', 'user.email', 'ada@example.org')
    (repo / 'README.md').write_text('one\ntwo\n', encoding='utf-8')
    _git(repo, 'add', 'README.md')
    _git(repo, 'commit', '-m', 'docs: expand readme')
    (repo / '.mailmap').write_text(
        'Ada Lovelace <ada@example.com> Ada L. <ada@example.org>\n',
        encoding='utf-8',
    )
    _git(repo, 'checkout', '-b', 'feat/sample')
    (repo / 'note.txt').write_text('note\n', encoding='utf-8')
    _git(repo, 'add', 'note.txt')
    _git(repo, 'commit', '-m', 'feat: note')
    _git(repo, 'checkout', 'main')
    return repo


@pytest.fixture()
def client(sample_repo: Path) -> TestClient:
    app = create_app(mount_path='/git', repo_path=sample_repo, mount_ui=False)
    return TestClient(app)


@pytest.fixture()
def history_repo(tmp_path: Path) -> Path:
    """Dated history: Ada x4 (one via mailmap alias), Bob x2 (one on a merged branch)."""

    repo = tmp_path / 'history'
    repo.mkdir()
    _git(repo, 'init', '-b', 'main')
    (repo / '.mailmap').write_text(
        'Ada Lovelace <ada@example.com> Ada L. <ada@example.org>\n',
        encoding='utf-8',
    )
    commit_as(repo, 'Ada Lovelace', 'ada@example.com', '2026-01-05T10:00:00+03:00', 'feat: a1')
    commit_as(repo, 'Ada Lovelace', 'ada@example.com', '2026-01-06T11:00:00+03:00', 'feat: a2')
    commit_as(repo, 'Bob Builder', 'bob@example.com', '2026-01-07T23:30:00-05:00', 'fix: b1')
    commit_as(repo, 'Ada L.', 'ada@example.org', '2026-02-10T12:00:00+00:00', 'docs: a3')
    _git(repo, 'checkout', '-b', 'feat/bob')
    commit_as(repo, 'Bob Builder', 'bob@example.com', '2026-02-20T08:00:00+00:00', 'feat: b2')
    _git(repo, 'checkout', 'main')
    _git(
        repo,
        'merge',
        '--no-ff',
        '-m',
        'merge: feat/bob',
        'feat/bob',
        env={
            'GIT_AUTHOR_NAME': 'Ada Lovelace',
            'GIT_AUTHOR_EMAIL': 'ada@example.com',
            'GIT_AUTHOR_DATE': '2026-02-21T09:00:00+00:00',
            'GIT_COMMITTER_NAME': 'Ada Lovelace',
            'GIT_COMMITTER_EMAIL': 'ada@example.com',
            'GIT_COMMITTER_DATE': '2026-02-21T09:00:00+00:00',
        },
    )
    commit_as(repo, 'Ada Lovelace', 'ada@example.com', '2026-03-02T09:00:00+00:00', 'feat: a4')
    return repo
