"""Git adapter errors."""


class GitPulseError(Exception):
    """Base error for the gitpulse package."""


class GitNotARepositoryError(GitPulseError):
    """Path is not a git repository."""


class GitCommandError(GitPulseError):
    """git CLI returned a non-zero status or timed out."""


class UnknownRefError(GitPulseError):
    """Requested branch or ref does not exist."""
