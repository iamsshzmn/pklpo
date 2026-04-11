"""OKX API credentials — lazy-loaded, masked repr, fail-fast on missing env."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OKXCredentials:
    """Immutable OKX API credentials with masked repr.

    Use ``OKXCredentials.from_env()`` to load from environment.
    Missing env vars raise ``KeyError`` immediately (fail-fast).
    """

    api_key: str
    api_secret: str
    passphrase: str

    def __repr__(self) -> str:
        return (
            f"OKXCredentials("
            f"api_key='{self.api_key[:4]}...', "
            f"secret=***, "
            f"passphrase=***)"
        )

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_env(cls) -> OKXCredentials:
        """Load credentials from environment variables.

        Raises:
            KeyError: If any required env var is missing.
        """
        return cls(
            api_key=os.environ["OKX_API_KEY"],
            api_secret=os.environ["OKX_API_SECRET"],
            passphrase=os.environ["OKX_API_PASSPHRASE"],
        )


# Lazy singleton — initialized on first access, not on import.
_instance: OKXCredentials | None = None


def get_credentials() -> OKXCredentials:
    """Return cached credentials, loading from env on first call."""
    global _instance
    if _instance is None:
        _instance = OKXCredentials.from_env()
    return _instance
