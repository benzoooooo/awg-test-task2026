"""Validated public remote URLs and hardened clone / fetch into isolated bare repos."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import socket
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from gitpulse.git import ISOLATED_ENV, MAX_STDERR_BYTES, git_env
from gitpulse.git.errors import GitCommandError, InvalidRemoteUrlError

MAX_URL_LENGTH = 2048
SIZE_CHECK_INTERVAL_SEC = 2.0
POLL_INTERVAL_SEC = 0.25
MAILMAP_TIMEOUT_SEC = 60.0

_HOST_RE = re.compile(
    r'^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$'
)
_SEGMENT_RE = re.compile(r'^[A-Za-z0-9._~-]+$')
_FORBIDDEN_HOSTS = frozenset({'localhost', 'localhost.localdomain'})

# Applied to every networked git call. Only https is allowed; hooks, credential
# helpers, prompts, redirects to other hosts, and templates are all disabled.
HARDENED_CONFIG: tuple[str, ...] = (
    '-c',
    'core.hooksPath=/dev/null',
    '-c',
    'protocol.allow=never',
    '-c',
    'protocol.https.allow=always',
    '-c',
    'credential.helper=',
    '-c',
    'core.askPass=',
    '-c',
    'http.followRedirects=false',
    '-c',
    'init.templateDir=',
)
REMOTE_ENV: dict[str, str] = {
    **ISOLATED_ENV,
    'GIT_ALLOW_PROTOCOL': 'https',
    'GIT_PROTOCOL_FROM_USER': '0',
}

Resolver = Callable[[str], Iterable[str]]


@dataclass(frozen=True)
class RemoteUrl:
    """A remote URL that passed validation. `url` is the canonical https form."""

    url: str
    host: str
    path: str

    @property
    def repo_id(self) -> str:
        key = f'{self.host}{_strip_git_suffix(self.path).lower()}'
        return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]

    @property
    def display_name(self) -> str:
        return f'{self.host}{_strip_git_suffix(self.path)}'


def _strip_git_suffix(path: str) -> str:
    return path[: -len('.git')] if path.lower().endswith('.git') else path


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def parse_remote_url(raw: str, *, allowed_hosts: frozenset[str] = frozenset()) -> RemoteUrl:
    """Validate a user-supplied repository URL without touching the network."""

    text = raw.strip()
    if not text:
        raise InvalidRemoteUrlError('repository URL is empty')
    if len(text) > MAX_URL_LENGTH:
        raise InvalidRemoteUrlError('repository URL is too long')
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
        raise InvalidRemoteUrlError('repository URL must not contain whitespace or control chars')
    if '::' in text:
        raise InvalidRemoteUrlError('transport helper syntax such as ext:: is not allowed')
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError as exc:
        raise InvalidRemoteUrlError('malformed repository URL') from exc
    if parts.scheme.lower() != 'https':
        raise InvalidRemoteUrlError('only https:// repository URLs are supported')
    if '@' in parts.netloc:
        raise InvalidRemoteUrlError('credentials in repository URLs are not allowed')
    if parts.query or parts.fragment:
        raise InvalidRemoteUrlError('query strings and fragments are not allowed')
    if port not in (None, 443):
        raise InvalidRemoteUrlError('custom ports are not allowed')

    host = (parts.hostname or '').rstrip('.').lower()
    if not host:
        raise InvalidRemoteUrlError('repository URL has no host')
    if _is_ip_literal(host):
        raise InvalidRemoteUrlError('IP address hosts are not allowed; use a public hostname')
    if host in _FORBIDDEN_HOSTS or host.endswith('.localhost') or not _HOST_RE.match(host):
        raise InvalidRemoteUrlError(f'invalid host: {host}')
    if allowed_hosts and host not in allowed_hosts:
        raise InvalidRemoteUrlError(f'host is not allowed: {host}')

    segments = parts.path.strip('/').split('/') if parts.path.strip('/') else []
    if not segments:
        raise InvalidRemoteUrlError('repository URL must include a repository path')
    for segment in segments:
        if segment in {'.', '..'} or not _SEGMENT_RE.match(segment):
            raise InvalidRemoteUrlError('repository path contains forbidden characters')
    path = '/' + '/'.join(segments)
    return RemoteUrl(url=f'https://{host}{path}', host=host, path=path)


def system_resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise InvalidRemoteUrlError(f'cannot resolve host: {host}') from exc
    return [str(info[4][0]) for info in infos]


def ensure_public_host(host: str, resolver: Resolver = system_resolve) -> None:
    """Reject hosts resolving to loopback, private, link-local, or reserved ranges (SSRF)."""

    addresses = {address.split('%', 1)[0] for address in resolver(host)}
    if not addresses:
        raise InvalidRemoteUrlError(f'cannot resolve host: {host}')
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise InvalidRemoteUrlError(f'host resolves to a non-public address: {host}')


def clone_argv(remote: RemoteUrl, dest: Path) -> list[str]:
    """Bare, blobless, tagless clone. `--` stops option injection through the URL."""

    return [
        'git',
        *HARDENED_CONFIG,
        'clone',
        '--bare',
        '--filter=blob:none',
        '--no-tags',
        '--quiet',
        '--',
        remote.url,
        str(dest),
    ]


def fetch_argv(repo: Path) -> list[str]:
    return [
        'git',
        *HARDENED_CONFIG,
        '-C',
        str(repo),
        'fetch',
        '--prune',
        '--no-tags',
        '--quiet',
        '--filter=blob:none',
        'origin',
        '+refs/heads/*:refs/heads/*',
    ]


def directory_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda _err: None):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue
    return total


def run_bounded(argv: list[str], *, watch: Path, timeout: float, max_bytes: int) -> None:
    """Run a networked git command, killing it on timeout or when `watch` outgrows `max_bytes`."""

    with tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
            env=git_env(REMOTE_ENV),
            shell=False,
        )
        started = time.monotonic()
        next_size_check = started + SIZE_CHECK_INTERVAL_SEC
        try:
            while True:
                try:
                    returncode = proc.wait(timeout=POLL_INTERVAL_SEC)
                    break
                except subprocess.TimeoutExpired:
                    pass
                now = time.monotonic()
                if now - started > timeout:
                    raise GitCommandError(f'git timed out after {int(timeout)}s')
                if now >= next_size_check:
                    next_size_check = now + SIZE_CHECK_INTERVAL_SEC
                    if directory_size(watch) > max_bytes:
                        raise GitCommandError(
                            f'repository exceeds the size limit of {max_bytes // (1024 * 1024)} MB'
                        )
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

        if returncode != 0:
            stderr.seek(0)
            message = stderr.read(MAX_STDERR_BYTES).decode('utf-8', errors='replace').strip()
            raise GitCommandError(message or f'git exited with status {returncode}')
    if directory_size(watch) > max_bytes:
        raise GitCommandError(
            f'repository exceeds the size limit of {max_bytes // (1024 * 1024)} MB'
        )


def materialize_mailmap(repo: Path) -> None:
    """Fetch the single `.mailmap` blob so later offline reads resolve identities."""

    try:
        subprocess.run(
            ['git', *HARDENED_CONFIG, '-C', str(repo), 'cat-file', 'blob', 'HEAD:.mailmap'],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=MAILMAP_TIMEOUT_SEC,
            env=git_env(REMOTE_ENV),
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return


class GitRemoteTransport:
    """Default clone/fetch implementation used by the repository registry."""

    def __init__(
        self,
        *,
        clone_timeout: float,
        fetch_timeout: float,
        max_bytes: int,
        block_private_networks: bool = True,
        resolver: Resolver = system_resolve,
    ) -> None:
        self._clone_timeout = clone_timeout
        self._fetch_timeout = fetch_timeout
        self._max_bytes = max_bytes
        self._block_private_networks = block_private_networks
        self._resolver = resolver

    def _check_host(self, remote: RemoteUrl) -> None:
        if self._block_private_networks:
            ensure_public_host(remote.host, self._resolver)

    def clone(self, remote: RemoteUrl, dest: Path) -> None:
        self._check_host(remote)
        run_bounded(
            clone_argv(remote, dest),
            watch=dest,
            timeout=self._clone_timeout,
            max_bytes=self._max_bytes,
        )
        materialize_mailmap(dest)

    def fetch(self, remote: RemoteUrl, repo: Path) -> None:
        self._check_host(remote)
        run_bounded(
            fetch_argv(repo),
            watch=repo,
            timeout=self._fetch_timeout,
            max_bytes=self._max_bytes,
        )
        materialize_mailmap(repo)
