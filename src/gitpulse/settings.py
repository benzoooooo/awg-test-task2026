"""Runtime settings for AWG GitPulse (environment prefix `GITPULSE_`)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitPulseSettings(BaseSettings):
    """Limits and switches for remote repository analysis.

    Remote cloning is opt-in so that embedding the package never starts network
    access or disk writes unless the host asks for it.
    """

    model_config = SettingsConfigDict(env_prefix='GITPULSE_', extra='ignore')

    remote_enabled: bool = False
    data_dir: Path = Path('.gitpulse-data')
    allowed_hosts: str = Field(
        default='',
        description='Comma-separated host allowlist; empty means any public host.',
    )
    block_private_networks: bool = Field(
        default=True,
        description='Reject hosts that resolve to loopback, private, or reserved addresses.',
    )
    clone_timeout_sec: float = Field(default=900.0, gt=0)
    fetch_timeout_sec: float = Field(default=300.0, gt=0)
    max_repo_size_mb: int = Field(default=1536, gt=0)
    max_repos: int = Field(default=20, gt=0)
    max_parallel_clones: int = Field(default=2, gt=0)
    refresh_interval_sec: int = Field(default=900, ge=0)
    max_commits_scan: int = Field(default=400_000, gt=0)
    index_cache_size: int = Field(default=6, gt=0)
    log_timeout_sec: float = Field(default=180.0, gt=0)
    preload_urls: str = Field(
        default='',
        description='Comma-separated public URLs cloned at startup and never evicted.',
    )

    @property
    def allowed_host_set(self) -> frozenset[str]:
        return frozenset(_split_csv(self.allowed_hosts, lower=True))

    @property
    def preload_url_list(self) -> list[str]:
        return _split_csv(self.preload_urls)

    @property
    def max_repo_size_bytes(self) -> int:
        return self.max_repo_size_mb * 1024 * 1024


def _split_csv(value: str, *, lower: bool = False) -> list[str]:
    items = [item.strip() for item in value.split(',')]
    return [item.lower() if lower else item for item in items if item]
