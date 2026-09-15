"""In-memory commit index built from one streaming `git log` pass, cached by branch tip."""

from __future__ import annotations

import threading
from array import array
from collections import OrderedDict
from dataclasses import dataclass, field

from gitpulse.git.errors import UnknownAuthorError
from gitpulse.git.repository import GitRepository

DEFAULT_MAX_COMMITS = 400_000
DEFAULT_CACHE_ENTRIES = 6


def author_key(name: str, email: str) -> str:
    """Canonical author identity after mailmap: e-mail, or name when e-mail is empty."""

    return email.strip().lower() or f'name:{name.strip().lower()}'


@dataclass
class CommitIndex:
    """Columnar, newest-first commit metadata for one branch tip (merges excluded)."""

    branch: str
    tip_sha: str
    shas: list[str] = field(default_factory=list)
    timestamps: array[int] = field(default_factory=lambda: array('q'))
    offsets: array[int] = field(default_factory=lambda: array('h'))
    author_ids: array[int] = field(default_factory=lambda: array('I'))
    author_names: list[str] = field(default_factory=list)
    author_emails: list[str] = field(default_factory=list)
    truncated: bool = False
    _ids: dict[str, int] = field(default_factory=dict, repr=False)

    def __len__(self) -> int:
        return len(self.shas)

    def add(self, sha: str, timestamp: int, offset: int, name: str, email: str) -> None:
        key = author_key(name, email)
        author_id = self._ids.get(key)
        if author_id is None:
            author_id = len(self.author_names)
            self._ids[key] = author_id
            self.author_names.append(name)
            self.author_emails.append(email)
        self.shas.append(sha)
        self.timestamps.append(timestamp)
        self.offsets.append(max(-32768, min(32767, offset)))
        self.author_ids.append(author_id)

    def find_author(self, value: str) -> int:
        """Resolve an author filter (e-mail, case-insensitive) to an author id."""

        text = value.strip().lower()
        author_id = self._ids.get(text)
        if author_id is None:
            author_id = self._ids.get(f'name:{text}')
        if author_id is None:
            raise UnknownAuthorError(f'unknown author on {self.branch}: {value[:120]}')
        return author_id


def build_index(
    repo: GitRepository,
    branch: str,
    tip_sha: str,
    *,
    max_commits: int = DEFAULT_MAX_COMMITS,
) -> CommitIndex:
    index = CommitIndex(branch=branch, tip_sha=tip_sha)
    records = repo.iter_log_records(tip_sha)
    try:
        for record in records:
            if len(index) >= max_commits:
                index.truncated = True
                break
            index.add(
                record.sha,
                record.timestamp,
                record.offset_minutes,
                record.author_name,
                record.author_email,
            )
    finally:
        records.close()
    return index


class IndexCache:
    """LRU of commit indexes keyed by (repository path, branch, tip SHA).

    A new tip replaces older entries for the same branch, so a fetch invalidates
    analytics without explicit bookkeeping. Concurrent requests for the same key
    share one build.
    """

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_CACHE_ENTRIES,
        max_commits: int = DEFAULT_MAX_COMMITS,
    ) -> None:
        self._max_entries = max_entries
        self._max_commits = max_commits
        self._lock = threading.Lock()
        self._entries: OrderedDict[tuple[str, str, str], CommitIndex] = OrderedDict()
        self._building: dict[tuple[str, str, str], threading.Lock] = {}

    def get(self, repo: GitRepository, branch: str) -> CommitIndex:
        tip = repo.branch_tip(branch)
        key = (str(repo.path), branch, tip)
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None:
                self._entries.move_to_end(key)
                return hit
            build_lock = self._building.setdefault(key, threading.Lock())

        with build_lock:
            with self._lock:
                hit = self._entries.get(key)
                if hit is not None:
                    return hit
            try:
                index = build_index(repo, branch, tip, max_commits=self._max_commits)
            finally:
                with self._lock:
                    self._building.pop(key, None)
            with self._lock:
                for stale in [k for k in self._entries if k[:2] == key[:2]]:
                    del self._entries[stale]
                self._entries[key] = index
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
        return index
