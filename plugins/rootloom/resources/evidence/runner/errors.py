"""Stable failures for the personal engineering helper."""


class ChangeError(RuntimeError):
    """A controlled Evidence Mode failure."""


class DangerousDeletionError(ChangeError):
    """A sensitive deletion needs exact operator confirmation."""
