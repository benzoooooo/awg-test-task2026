"""Git adapter errors."""


class GitPulseError(Exception):
    """Base error for the gitpulse package."""


class GitNotARepositoryError(GitPulseError):
    """Path is not a git repository."""


class GitCommandError(GitPulseError):
    """git CLI returned a non-zero status or timed out."""


class UnknownRefError(GitPulseError):
    """Requested branch or ref does not exist."""


class UnknownAuthorError(GitPulseError):
    """Requested author has no commits on the analyzed branch."""


class InvalidRemoteUrlError(GitPulseError):
    """Remote URL failed validation (scheme, host, credentials, path)."""


class UnknownRepositoryError(GitPulseError):
    """Repository id is not registered."""


class RepositoryNotReadyError(GitPulseError):
    """Repository is still cloning or its clone failed."""


class RepositoryLimitError(GitPulseError):
    """Registry is full and nothing can be evicted."""
