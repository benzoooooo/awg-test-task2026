"""API route tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get('/git/api/v1/health')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert body['version']


def test_summary_and_branches(client: TestClient) -> None:
    summary = client.get('/git/api/v1/summary')
    assert summary.status_code == 200
    assert summary.json()['commit_count'] == 2
    branches = client.get('/git/api/v1/branches')
    assert branches.status_code == 200
    names = {row['name'] for row in branches.json()}
    assert 'main' in names


def test_commits_and_authors(client: TestClient) -> None:
    commits = client.get('/git/api/v1/branches/main/commits')
    assert commits.status_code == 200
    assert len(commits.json()) >= 2
    authors = client.get('/git/api/v1/authors')
    assert authors.status_code == 200
    assert authors.json()[0]['name'] == 'Ada Lovelace'


def test_unknown_branch(client: TestClient) -> None:
    response = client.get('/git/api/v1/branches/does-not-exist/commits')
    assert response.status_code == 404
