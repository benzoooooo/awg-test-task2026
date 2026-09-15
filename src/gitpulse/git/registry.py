"""Registry of analyzable repositories: an optional local path plus isolated remote clones."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from gitpulse.core.models import RepoInfo, RepoSource, RepoStatus
from gitpulse.git import OFFLINE_CLONE_ENV
from gitpulse.git.errors import (
    GitPulseError,
    RepositoryLimitError,
    RepositoryNotReadyError,
    UnknownRepositoryError,
)
from gitpulse.git.remote import GitRemoteTransport, RemoteUrl, directory_size, parse_remote_url
from gitpulse.git.repository import GitRepository
from gitpulse.settings import GitPulseSettings

LOCAL_REPO_ID = 'local'
MAX_ERROR_LENGTH = 500

logger = logging.getLogger(__name__)


class RemoteTransport(Protocol):
    def clone(self, remote: RemoteUrl, dest: Path) -> None: ...

    def fetch(self, remote: RemoteUrl, repo: Path) -> None: ...


ReadyListener = Callable[[str, GitRepository], None]


@dataclass
class _Entry:
    info: RepoInfo
    remote: RemoteUrl | None = None
    repository: GitRepository | None = None
    last_access: float = 0.0


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _short_error(exc: BaseException) -> str:
    return (str(exc) or exc.__class__.__name__)[:MAX_ERROR_LENGTH]


class RepoRegistry:
    """Thread-safe registry. Clones and fetches run on a bounded worker pool.

    Layout under `data_dir`: `repos/<id>.git` (bare, blobless clone), `repos/<id>.json`
    (metadata), `tmp/` (in-progress clones, renamed into place atomically).
    """

    def __init__(
        self,
        settings: GitPulseSettings,
        *,
        transport: RemoteTransport | None = None,
    ) -> None:
        self._settings = settings
        self._root = settings.data_dir.expanduser().resolve()
        self._repos_dir = self._root / 'repos'
        self._tmp_dir = self._root / 'tmp'
        for directory in (self._root, self._repos_dir, self._tmp_dir):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        for leftover in self._tmp_dir.iterdir():
            shutil.rmtree(leftover, ignore_errors=True)
        self._transport: RemoteTransport = transport or GitRemoteTransport(
            clone_timeout=settings.clone_timeout_sec,
            fetch_timeout=settings.fetch_timeout_sec,
            max_bytes=settings.max_repo_size_bytes,
            block_private_networks=settings.block_private_networks,
        )
        self._lock = threading.RLock()
        self._entries: dict[str, _Entry] = {}
        self._listeners: list[ReadyListener] = []
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_parallel_clones,
            thread_name_prefix='gitpulse-git',
        )
        self._load_existing()

    # ------------------------------------------------------------------ queries

    def list_repos(self) -> list[RepoInfo]:
        with self._lock:
            infos = [entry.info for entry in self._entries.values()]
        return sorted(
            infos,
            key=lambda info: (
                info.source is not RepoSource.LOCAL,
                not info.pinned,
                -info.created_at.timestamp(),
            ),
        )

    def get(self, repo_id: str) -> RepoInfo:
        with self._lock:
            return self._entry(repo_id).info

    def open(self, repo_id: str) -> GitRepository:
        """Return a ready repository, scheduling a background refresh when it is stale."""

        with self._lock:
            entry = self._entry(repo_id)
            entry.last_access = time.monotonic()
            if entry.info.status is not RepoStatus.READY or entry.repository is None:
                if entry.info.status is RepoStatus.FAILED:
                    raise RepositoryNotReadyError(entry.info.error or 'clone failed')
                raise RepositoryNotReadyError(f'repository is {entry.info.status.value}')
            if self._is_stale(entry):
                self._schedule_refresh(entry)
            return entry.repository

    # ---------------------------------------------------------------- commands

    def add_ready_listener(self, listener: ReadyListener) -> None:
        self._listeners.append(listener)

    def add_local(self, repository: GitRepository) -> RepoInfo:
        now = _now()
        info = RepoInfo(
            id=LOCAL_REPO_ID,
            name=repository.path.name,
            source=RepoSource.LOCAL,
            status=RepoStatus.READY,
            pinned=True,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._entries[LOCAL_REPO_ID] = _Entry(info=info, repository=repository)
        return info

    def connect(self, raw_url: str, *, pinned: bool = False) -> RepoInfo:
        """Register a public repository URL and clone it in the background (idempotent)."""

        remote = parse_remote_url(raw_url, allowed_hosts=self._settings.allowed_host_set)
        with self._lock:
            entry = self._entries.get(remote.repo_id)
            if entry is not None:
                entry.last_access = time.monotonic()
                if pinned and not entry.info.pinned:
                    self._update(entry, pinned=True)
                if entry.info.status is RepoStatus.FAILED:
                    self._schedule_clone(entry)
                return entry.info
            self._make_room()
            now = _now()
            entry = _Entry(
                info=RepoInfo(
                    id=remote.repo_id,
                    name=remote.display_name,
                    url=remote.url,
                    source=RepoSource.REMOTE,
                    status=RepoStatus.PENDING,
                    pinned=pinned,
                    created_at=now,
                    updated_at=now,
                ),
                remote=remote,
                last_access=time.monotonic(),
            )
            self._entries[remote.repo_id] = entry
            self._schedule_clone(entry)
            return entry.info

    def refresh(self, repo_id: str) -> RepoInfo:
        with self._lock:
            entry = self._entry(repo_id)
            if entry.remote is None:
                return entry.info
            if entry.info.status is RepoStatus.FAILED:
                self._schedule_clone(entry)
            elif entry.info.status is RepoStatus.READY:
                self._schedule_refresh(entry)
            return entry.info

    def preload(self, urls: list[str]) -> None:
        for url in urls:
            try:
                self.connect(url, pinned=True)
            except GitPulseError as exc:
                logger.warning('gitpulse: cannot preload %s: %s', url, exc)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ---------------------------------------------------------------- internals

    def _entry(self, repo_id: str) -> _Entry:
        entry = self._entries.get(repo_id)
        if entry is None:
            raise UnknownRepositoryError(f'unknown repository: {repo_id[:40]}')
        return entry

    def _update(self, entry: _Entry, **changes: Any) -> None:
        entry.info = entry.info.model_copy(update={**changes, 'updated_at': _now()})

    def _is_stale(self, entry: _Entry) -> bool:
        interval = self._settings.refresh_interval_sec
        fetched = entry.info.fetched_at
        if entry.remote is None or interval <= 0 or fetched is None or entry.info.refreshing:
            return False
        return (_now() - fetched).total_seconds() > interval

    def _make_room(self) -> None:
        remotes = [e for e in self._entries.values() if e.remote is not None]
        if len(remotes) < self._settings.max_repos:
            return
        evictable = sorted(
            (
                e
                for e in remotes
                if not e.info.pinned
                and not e.info.refreshing
                and e.info.status in (RepoStatus.READY, RepoStatus.FAILED)
            ),
            key=lambda e: e.last_access,
        )
        if not evictable:
            raise RepositoryLimitError('repository limit reached; try again later')
        victim = evictable[0]
        del self._entries[victim.info.id]
        self._delete_files(victim.info.id)

    def _repo_dir(self, repo_id: str) -> Path:
        return self._repos_dir / f'{repo_id}.git'

    def _meta_path(self, repo_id: str) -> Path:
        return self._repos_dir / f'{repo_id}.json'

    def _delete_files(self, repo_id: str) -> None:
        repo_dir = self._repo_dir(repo_id)
        if repo_dir.exists():
            trash = self._tmp_dir / f'evicted-{uuid.uuid4().hex}'
            try:
                os.replace(repo_dir, trash)
            except OSError:
                trash = repo_dir
            shutil.rmtree(trash, ignore_errors=True)
        self._meta_path(repo_id).unlink(missing_ok=True)

    def _write_meta(self, entry: _Entry) -> None:
        if entry.remote is None:
            return
        payload = {
            'url': entry.remote.url,
            'created_at': entry.info.created_at.isoformat(),
            'fetched_at': entry.info.fetched_at.isoformat() if entry.info.fetched_at else None,
        }
        target = self._meta_path(entry.info.id)
        scratch = target.with_suffix(f'.{uuid.uuid4().hex}.tmp')
        scratch.write_text(json.dumps(payload), encoding='utf-8')
        os.replace(scratch, target)

    def _open_clone(self, repo_id: str, remote: RemoteUrl) -> GitRepository:
        return GitRepository(
            self._repo_dir(repo_id),
            label=remote.url,
            env=OFFLINE_CLONE_ENV,
            log_timeout=self._settings.log_timeout_sec,
        )

    def _load_existing(self) -> None:
        for meta in sorted(self._repos_dir.glob('*.json')):
            try:
                payload = json.loads(meta.read_text(encoding='utf-8'))
                remote = parse_remote_url(
                    str(payload['url']), allowed_hosts=self._settings.allowed_host_set
                )
                if remote.repo_id != meta.stem or not self._repo_dir(remote.repo_id).is_dir():
                    raise GitPulseError('stale metadata')
                created = datetime.fromisoformat(payload['created_at'])
                fetched_raw = payload.get('fetched_at')
                fetched = datetime.fromisoformat(fetched_raw) if fetched_raw else None
                repository = self._open_clone(remote.repo_id, remote)
            except (GitPulseError, OSError, ValueError, KeyError, TypeError) as exc:
                logger.warning('gitpulse: skipping stored repository %s: %s', meta.name, exc)
                continue
            self._entries[remote.repo_id] = _Entry(
                info=RepoInfo(
                    id=remote.repo_id,
                    name=remote.display_name,
                    url=remote.url,
                    source=RepoSource.REMOTE,
                    status=RepoStatus.READY,
                    created_at=created,
                    updated_at=fetched or created,
                    fetched_at=fetched,
                    size_bytes=directory_size(repository.path),
                ),
                remote=remote,
                repository=repository,
            )

    def _schedule_clone(self, entry: _Entry) -> None:
        self._update(entry, status=RepoStatus.PENDING, error=None)
        self._executor.submit(self._clone_job, entry.info.id)

    def _schedule_refresh(self, entry: _Entry) -> None:
        if entry.info.refreshing:
            return
        self._update(entry, refreshing=True)
        self._executor.submit(self._refresh_job, entry.info.id)

    def _clone_job(self, repo_id: str) -> None:
        with self._lock:
            entry = self._entries.get(repo_id)
            if entry is None or entry.remote is None:
                return
            remote = entry.remote
            self._update(entry, status=RepoStatus.CLONING)
        work = self._tmp_dir / f'{repo_id}-{uuid.uuid4().hex}.git'
        dest = self._repo_dir(repo_id)
        try:
            self._transport.clone(remote, work)
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            os.replace(work, dest)
            repository = self._open_clone(repo_id, remote)
            size = directory_size(dest)
        except Exception as exc:
            shutil.rmtree(work, ignore_errors=True)
            logger.warning('gitpulse: clone failed for %s: %s', remote.url, exc)
            with self._lock:
                if self._entries.get(repo_id) is entry:
                    self._update(entry, status=RepoStatus.FAILED, error=_short_error(exc))
            return
        with self._lock:
            if self._entries.get(repo_id) is not entry:
                return
            entry.repository = repository
            self._update(
                entry,
                status=RepoStatus.READY,
                error=None,
                fetched_at=_now(),
                size_bytes=size,
            )
            self._write_meta(entry)
        self._notify_ready(repo_id, repository)

    def _refresh_job(self, repo_id: str) -> None:
        with self._lock:
            entry = self._entries.get(repo_id)
            if entry is None or entry.remote is None or entry.repository is None:
                return
            remote, repository = entry.remote, entry.repository
        try:
            self._transport.fetch(remote, repository.path)
            size = directory_size(repository.path)
        except Exception as exc:
            logger.warning('gitpulse: refresh failed for %s: %s', remote.url, exc)
            with self._lock:
                self._update(entry, refreshing=False, error=f'refresh failed: {_short_error(exc)}')
            return
        with self._lock:
            self._update(entry, refreshing=False, error=None, fetched_at=_now(), size_bytes=size)
            self._write_meta(entry)
        self._notify_ready(repo_id, repository)

    def _notify_ready(self, repo_id: str, repository: GitRepository) -> None:
        for listener in list(self._listeners):
            try:
                listener(repo_id, repository)
            except Exception:
                logger.exception('gitpulse: ready listener failed for %s', repo_id)
