"""Repository registry lifecycle and the multi-repository HTTP API."""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gitpulse.fastapi_app import create_app
from gitpulse.fastapi_app.routes import build_api_router
from gitpulse.git.errors import GitCommandError
from gitpulse.git.registry import RepoRegistry
from gitpulse.git.remote import RemoteUrl
from gitpulse.settings import GitPulseSettings

REPO_URL = 'https://example.com/team/history'
OTHER_URL = 'https://example.com/team/other'


class LocalTransport:
    """Test double: serves registered https URLs from local repositories."""

    def __init__(self, sources: dict[str, Path]) -> None:
        self.sources = sources
        self.gate = threading.Event()
        self.gate.set()
        self.clones = 0

    def clone(self, remote: RemoteUrl, dest: Path) -> None:
        self.gate.wait(timeout=10)
        source = self.sources.get(remote.url)
        if source is None:
            raise GitCommandError('repository not found')
        self.clones += 1
        subprocess.run(
            ['git', 'clone', '--bare', '--no-local', '--quiet', str(source), str(dest)],
            check=True,
            capture_output=True,
        )

    def fetch(self, remote: RemoteUrl, repo: Path) -> None:
        subprocess.run(
            [
                'git',
                '-C',
                str(repo),
                'fetch',
                '--quiet',
                str(self.sources[remote.url]),
                '+refs/heads/*:refs/heads/*',
            ],
            check=True,
            capture_output=True,
        )


def _settings(tmp_path: Path, **overrides: object) -> GitPulseSettings:
    values: dict[str, object] = {
        'remote_enabled': True,
        'data_dir': tmp_path / 'data',
        'refresh_interval_sec': 0,
        'max_repos': 5,
    }
    values.update(overrides)
    return GitPulseSettings(**values)  # type: ignore[arg-type]


def _client(registry: RepoRegistry, settings: GitPulseSettings) -> TestClient:
    app = FastAPI()
    app.include_router(build_api_router(registry=registry, settings=settings), prefix='/git')
    return TestClient(app)


def _wait_status(client: TestClient, repo_id: str, expected: str) -> dict[str, object]:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        body: dict[str, object] = client.get(f'/git/api/v1/repos/{repo_id}').json()
        if body['status'] == expected:
            return body
        time.sleep(0.05)
    raise AssertionError(f'repository {repo_id} never became {expected}')


@pytest.fixture()
def transport(history_repo: Path, sample_repo: Path) -> LocalTransport:
    return LocalTransport({REPO_URL: history_repo, OTHER_URL: sample_repo})


@pytest.fixture()
def registry(tmp_path: Path, transport: LocalTransport) -> Iterator[RepoRegistry]:
    registry = RepoRegistry(_settings(tmp_path), transport=transport)
    yield registry
    registry.close()


def test_connect_clone_and_dashboard(tmp_path: Path, registry: RepoRegistry) -> None:
    client = _client(registry, _settings(tmp_path))
    created = client.post('/git/api/v1/repos', json={'url': REPO_URL})
    assert created.status_code == 202
    repo_id = created.json()['id']
    ready = _wait_status(client, repo_id, 'ready')
    assert ready['url'] == REPO_URL
    assert ready['size_bytes']

    base = f'/git/api/v1/repos/{repo_id}'
    board = client.get(f'{base}/dashboard').json()
    assert board['branch'] == 'main'
    assert board['total_commits'] == 6
    assert [row['name'] for row in board['contributors']] == ['Ada Lovelace', 'Bob Builder']

    filtered = client.get(f'{base}/dashboard', params={'author': 'bob@example.com'}).json()
    assert filtered['selected_author']['commits'] == 2

    commits = client.get(
        f'{base}/commits', params={'branch': 'main', 'author': 'bob@example.com'}
    ).json()
    assert {row['author_name'] for row in commits} == {'Bob Builder'}
    assert len(commits) == 2

    authors = client.get(f'{base}/authors', params={'branch': 'main'}).json()
    assert [row['email'] for row in authors] == ['ada@example.com', 'bob@example.com']
    summary = client.get(f'{base}/summary').json()
    assert summary['path'] == REPO_URL
    assert client.get(f'{base}/branches').status_code == 200


def test_connect_is_idempotent(
    tmp_path: Path, registry: RepoRegistry, transport: LocalTransport
) -> None:
    client = _client(registry, _settings(tmp_path))
    first = client.post('/git/api/v1/repos', json={'url': REPO_URL}).json()
    _wait_status(client, first['id'], 'ready')
    second = client.post('/git/api/v1/repos', json={'url': REPO_URL + '.git/'}).json()
    assert second['id'] == first['id']
    assert transport.clones == 1
    listed = client.get('/git/api/v1/repos').json()
    assert [row['id'] for row in listed] == [first['id']]


@pytest.mark.parametrize(
    'url',
    ['http://example.com/a/b', 'ext::sh -c id', 'https://127.0.0.1/a/b', 'git@github.com:a/b'],
)
def test_invalid_urls_are_rejected(tmp_path: Path, registry: RepoRegistry, url: str) -> None:
    client = _client(registry, _settings(tmp_path))
    response = client.post('/git/api/v1/repos', json={'url': url})
    assert response.status_code == 422


def test_unknown_and_malformed_ids(tmp_path: Path, registry: RepoRegistry) -> None:
    client = _client(registry, _settings(tmp_path))
    assert client.get('/git/api/v1/repos/0123456789abcdef/summary').status_code == 404
    assert client.get('/git/api/v1/repos/../../etc/summary').status_code == 404
    assert client.get('/git/api/v1/repos/ZZZ/summary').status_code == 422


def test_not_ready_then_ready(
    tmp_path: Path, registry: RepoRegistry, transport: LocalTransport
) -> None:
    client = _client(registry, _settings(tmp_path))
    transport.gate.clear()
    repo_id = client.post('/git/api/v1/repos', json={'url': REPO_URL}).json()['id']
    response = client.get(f'/git/api/v1/repos/{repo_id}/dashboard')
    assert response.status_code == 409
    transport.gate.set()
    _wait_status(client, repo_id, 'ready')
    assert client.get(f'/git/api/v1/repos/{repo_id}/dashboard').status_code == 200


def test_failed_clone_reports_error(tmp_path: Path, registry: RepoRegistry) -> None:
    client = _client(registry, _settings(tmp_path))
    url = 'https://example.com/team/missing'
    repo_id = client.post('/git/api/v1/repos', json={'url': url}).json()['id']
    failed = _wait_status(client, repo_id, 'failed')
    assert 'not found' in str(failed['error'])
    response = client.get(f'/git/api/v1/repos/{repo_id}/summary')
    assert response.status_code == 409
    assert not list((tmp_path / 'data' / 'tmp').iterdir())


def test_refresh_picks_up_new_commits(
    tmp_path: Path, registry: RepoRegistry, history_repo: Path
) -> None:
    from tests.conftest import commit_as

    client = _client(registry, _settings(tmp_path))
    repo_id = client.post('/git/api/v1/repos', json={'url': REPO_URL}).json()['id']
    _wait_status(client, repo_id, 'ready')
    base = f'/git/api/v1/repos/{repo_id}'
    assert client.get(f'{base}/dashboard').json()['total_commits'] == 6
    commit_as(history_repo, 'Cy', 'cy@example.com', '2026-03-03T10:00:00+00:00', 'feat: c1')
    assert client.post(f'{base}/refresh').status_code == 202
    deadline = time.monotonic() + 15
    total = 6
    while time.monotonic() < deadline and total != 7:
        info = client.get(base).json()
        if not info['refreshing']:
            total = client.get(f'{base}/dashboard').json()['total_commits']
        time.sleep(0.05)
    assert total == 7


def test_lru_eviction_and_limit(tmp_path: Path, transport: LocalTransport) -> None:
    settings = _settings(tmp_path, max_repos=1)
    registry = RepoRegistry(settings, transport=transport)
    try:
        client = _client(registry, settings)
        first = client.post('/git/api/v1/repos', json={'url': REPO_URL}).json()['id']
        _wait_status(client, first, 'ready')
        second = client.post('/git/api/v1/repos', json={'url': OTHER_URL}).json()['id']
        assert client.get(f'/git/api/v1/repos/{first}').status_code == 404
        assert not (tmp_path / 'data' / 'repos' / f'{first}.git').exists()

        transport.gate.clear()
        _wait_status(client, second, 'ready')
        client.post('/git/api/v1/repos/' + second + '/refresh')
        third = client.post('/git/api/v1/repos', json={'url': REPO_URL})
        assert third.status_code in (202, 429)
    finally:
        transport.gate.set()
        registry.close()


def test_limit_when_everything_is_busy(tmp_path: Path, transport: LocalTransport) -> None:
    settings = _settings(tmp_path, max_repos=1)
    registry = RepoRegistry(settings, transport=transport)
    try:
        client = _client(registry, settings)
        transport.gate.clear()
        client.post('/git/api/v1/repos', json={'url': REPO_URL})
        response = client.post('/git/api/v1/repos', json={'url': OTHER_URL})
        assert response.status_code == 429
    finally:
        transport.gate.set()
        registry.close()


def test_registry_restores_clones_from_disk(tmp_path: Path, transport: LocalTransport) -> None:
    settings = _settings(tmp_path)
    registry = RepoRegistry(settings, transport=transport)
    repo_id = registry.connect(REPO_URL).id
    deadline = time.monotonic() + 15
    while registry.get(repo_id).status != 'ready' and time.monotonic() < deadline:
        time.sleep(0.05)
    registry.close()

    restored = RepoRegistry(settings, transport=transport)
    try:
        info = restored.get(repo_id)
        assert info.status == 'ready'
        assert info.url == REPO_URL
        assert restored.open(repo_id).summary().commit_count == 7
    finally:
        restored.close()


def test_remote_disabled_exposes_local_repo(sample_repo: Path) -> None:
    app = create_app(
        repo_path=sample_repo,
        mount_ui=False,
        settings=GitPulseSettings(remote_enabled=False),
    )
    client = TestClient(app)
    assert client.get('/git/api/v1/config').json()['remote_enabled'] is False
    assert [row['id'] for row in client.get('/git/api/v1/repos').json()] == ['local']
    assert client.post('/git/api/v1/repos', json={'url': REPO_URL}).status_code == 403
    assert client.get('/git/api/v1/repos/local/summary').json()['commit_count'] == 2
    board = client.get('/git/api/v1/repos/local/dashboard').json()
    assert board['total_commits'] == 2


def test_create_router_requires_a_source() -> None:
    with pytest.raises(ValueError):
        create_app(mount_ui=False, settings=GitPulseSettings(remote_enabled=False))
