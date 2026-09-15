"""Pytest fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gitpulse.fastapi_app import create_app


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args],
        check=True,
        capture_output=True,
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
