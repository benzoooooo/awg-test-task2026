"""Tests for the git adapter and analytics."""

from __future__ import annotations

from pathlib import Path

from gitpulse.analytics import author_contributions
from gitpulse.git.repository import GitRepository


def test_list_branches_and_commits(sample_repo: Path) -> None:
    repo = GitRepository(sample_repo)
    names = {b.name for b in repo.list_branches()}
    assert 'main' in names
    assert 'feat/sample' in names
    commits = repo.list_commits('main')
    assert len(commits) >= 2
    assert commits[0].subject


def test_mailmap_collapses_authors(sample_repo: Path) -> None:
    repo = GitRepository(sample_repo)
    authors = repo.list_authors()
    assert len(authors) == 1
    assert authors[0].name == 'Ada Lovelace'
    assert authors[0].commits == 2


def test_summary(sample_repo: Path) -> None:
    summary = GitRepository(sample_repo).summary()
    assert summary.commit_count == 2
    assert summary.branch_count == 2
    assert summary.author_count == 1


def test_contributions_share(sample_repo: Path) -> None:
    repo = GitRepository(sample_repo)
    rows = author_contributions(repo)
    assert rows
    assert abs(sum(r.share_percent for r in rows) - 100.0) < 0.1
