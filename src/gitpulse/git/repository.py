"""Read-only queries against a local git repository."""

from __future__ import annotations

import re
import threading
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from gitpulse.core.models import Author, BranchRef, Commit, RepoSummary
from gitpulse.git import resolve_repo, run_git, stream_git
from gitpulse.git.errors import GitCommandError, UnknownRefError

DEFAULT_LOG_TIMEOUT_SEC = 180.0
MAX_SHOW_COMMITS = 200
COMMIT_FORMAT = '%H%x09%h%x09%aN%x09%aE%x09%aI%x09%s'
LOG_RECORD_FORMAT = '%H%x09%at%x09%ai%x09%aN%x09%aE'
_SHA_RE = re.compile(r'^[0-9a-f]{40}(?:[0-9a-f]{24})?$')
_SHORTLOG_RE = re.compile(r'^\s*(\d+)\t(.*) <(.*)>$')


def _parse_iso(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    return datetime.fromisoformat(text)


def _parse_offset_minutes(value: str) -> int:
    """Parse the trailing `+HHMM` / `-HHMM` of `%ai` into minutes east of UTC."""

    tz = value.strip()[-5:]
    if len(tz) != 5 or tz[0] not in '+-' or not tz[1:].isdigit():
        return 0
    minutes = int(tz[1:3]) * 60 + int(tz[3:5])
    return -minutes if tz[0] == '-' else minutes


def _require_sha(value: str) -> str:
    if not _SHA_RE.match(value):
        raise UnknownRefError(f'invalid commit id: {value[:80]}')
    return value


@dataclass(frozen=True, slots=True)
class LogRecord:
    """Compact per-commit metadata used to build analytics indexes."""

    sha: str
    timestamp: int
    offset_minutes: int
    author_name: str
    author_email: str


class GitRepository:
    """Facade over local git metadata used by the FastAPI layer."""

    def __init__(
        self,
        path: Path | str,
        *,
        label: str | None = None,
        env: Mapping[str, str] | None = None,
        log_timeout: float = DEFAULT_LOG_TIMEOUT_SEC,
    ) -> None:
        self.path = resolve_repo(Path(path))
        self.label = label or str(self.path)
        self._env = dict(env) if env else None
        self._log_timeout = log_timeout
        self._summary_lock = threading.Lock()
        self._summary_cache: tuple[str, RepoSummary] | None = None

    def _run(self, args: list[str], *, timeout: float = 30) -> str:
        return run_git(self.path, args, timeout=timeout, env=self._env)

    def list_branches(self) -> list[BranchRef]:
        fmt = '%(refname:short)\t%(objectname)\t%(committerdate:iso-strict)\t%(authorname)'
        out = self._run(['for-each-ref', f'--format={fmt}', 'refs/heads/'])
        branches: list[BranchRef] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            name, tip = parts[0], parts[1]
            tip_date = _parse_iso(parts[2]) if len(parts) > 2 else None
            tip_author = parts[3] if len(parts) > 3 and parts[3] else None
            branches.append(
                BranchRef(name=name, tip_sha=tip, tip_date=tip_date, tip_author=tip_author)
            )
        return sorted(branches, key=lambda b: b.name)

    def ensure_branch(self, name: str) -> str:
        """Return the verified branch name or raise."""

        for branch in self.list_branches():
            if branch.name == name:
                return branch.name
        raise UnknownRefError(f'unknown branch: {name}')

    def branch_tip(self, name: str) -> str:
        """Return the tip SHA of a verified branch or raise."""

        for branch in self.list_branches():
            if branch.name == name:
                return branch.tip_sha
        raise UnknownRefError(f'unknown branch: {name}')

    def head_branch(self) -> str:
        """Branch HEAD points to, falling back to the first branch for detached HEADs."""

        try:
            head = self._run(['symbolic-ref', '--quiet', '--short', 'HEAD']).strip()
        except GitCommandError:
            head = ''
        names = [branch.name for branch in self.list_branches()]
        if head in names:
            return head
        if not names:
            raise UnknownRefError('repository has no branches')
        return names[0]

    def list_commits(
        self,
        branch: str,
        *,
        limit: int = 50,
        skip: int = 0,
    ) -> list[Commit]:
        ref = self.ensure_branch(branch)
        limit = max(1, min(limit, MAX_SHOW_COMMITS))
        skip = max(0, skip)
        out = self._run(
            [
                'log',
                '--use-mailmap',
                '--no-merges',
                f'--pretty=format:{COMMIT_FORMAT}',
                f'-n{limit}',
                f'--skip={skip}',
                '--end-of-options',
                f'refs/heads/{ref}',
            ],
            timeout=self._log_timeout,
        )
        return _parse_commits(out)

    def show_commits(self, shas: list[str]) -> list[Commit]:
        """Metadata for specific commits, in the given order (no patches)."""

        if not shas:
            return []
        verified = [_require_sha(sha) for sha in shas[:MAX_SHOW_COMMITS]]
        out = self._run(
            [
                'log',
                '--no-walk=unsorted',
                '--use-mailmap',
                f'--pretty=format:{COMMIT_FORMAT}',
                '--end-of-options',
                *verified,
            ]
        )
        return _parse_commits(out)

    def iter_log_records(self, tip_sha: str) -> Generator[LogRecord, None, None]:
        """Stream mailmap-resolved, non-merge commit metadata reachable from `tip_sha`."""

        lines = stream_git(
            self.path,
            [
                'log',
                '--use-mailmap',
                '--no-merges',
                f'--pretty=format:{LOG_RECORD_FORMAT}',
                '--end-of-options',
                _require_sha(tip_sha),
            ],
            timeout=self._log_timeout,
            env=self._env,
        )
        try:
            for line in lines:
                parts = line.split('\t', 4)
                if len(parts) != 5:
                    continue
                try:
                    timestamp = int(parts[1])
                except ValueError:
                    continue
                yield LogRecord(
                    sha=parts[0],
                    timestamp=timestamp,
                    offset_minutes=_parse_offset_minutes(parts[2]),
                    author_name=parts[3],
                    author_email=parts[4],
                )
        finally:
            close = getattr(lines, 'close', None)
            if close is not None:
                close()

    def list_authors(self) -> list[Author]:
        out = self._run(
            ['shortlog', '--summary', '--email', '--no-merges', 'HEAD'],
            timeout=self._log_timeout,
        )
        authors: list[Author] = []
        for line in out.splitlines():
            match = _SHORTLOG_RE.match(line)
            if match is None:
                continue
            authors.append(
                Author(name=match.group(2), email=match.group(3), commits=int(match.group(1)))
            )
        return sorted(authors, key=lambda a: (-a.commits, a.name.lower()))

    def summary(self) -> RepoSummary:
        """Repository header, cached by the HEAD commit id."""

        head_sha = self._run(['rev-parse', '--verify', 'HEAD^{commit}']).strip()
        with self._summary_lock:
            if self._summary_cache is not None and self._summary_cache[0] == head_sha:
                return self._summary_cache[1]

        head = self._run(['rev-parse', '--abbrev-ref', 'HEAD']).strip() or None
        count_raw = self._run(['rev-list', '--count', head_sha], timeout=self._log_timeout)
        commit_count = int(count_raw.strip()) if count_raw.strip().isdigit() else 0
        first_at = None
        last_at = None
        if commit_count:
            # `git log --reverse -n1` limits before reversing, so it would return the newest
            # commit; root commits give the real start of history.
            roots_raw = self._run(
                ['log', '--max-parents=0', '--pretty=format:%aI', head_sha],
                timeout=self._log_timeout,
            )
            roots = [value for value in map(_parse_iso, roots_raw.splitlines()) if value]
            first_at = min(roots) if roots else None
            last_at = _parse_iso(self._run(['log', '--pretty=format:%aI', '-n1', head_sha]))
        result = RepoSummary(
            path=self.label,
            head=head,
            default_branch=head,
            commit_count=commit_count,
            first_commit_at=first_at,
            last_commit_at=last_at,
            branch_count=len(self.list_branches()),
            author_count=len(self.list_authors()),
        )
        with self._summary_lock:
            self._summary_cache = (head_sha, result)
        return result


def _parse_commits(out: str) -> list[Commit]:
    commits: list[Commit] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t', 5)
        if len(parts) < 6:
            continue
        authored = _parse_iso(parts[4])
        if authored is None:
            continue
        commits.append(
            Commit(
                sha=parts[0],
                short_sha=parts[1],
                author_name=parts[2],
                author_email=parts[3],
                authored_at=authored,
                subject=parts[5],
            )
        )
    return commits


@lru_cache(maxsize=32)
def get_repository(path: str) -> GitRepository:
    """Cached repository facade keyed by resolved path string."""

    return GitRepository(path)
