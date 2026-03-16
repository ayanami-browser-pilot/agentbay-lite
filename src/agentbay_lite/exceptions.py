"""Unified exception hierarchy for cloud browser SDK."""

from __future__ import annotations


class CloudBrowserError(Exception):
    """Base exception for all cloud browser SDK errors."""


class AuthenticationError(CloudBrowserError):
    """Authentication failed (401/403). API key invalid or expired."""


class QuotaExceededError(CloudBrowserError):
    """Quota exceeded (429). Concurrent or monthly usage limit reached.

    Attributes:
        retry_after: Suggested wait time in seconds, if provided by the server.
    """

    def __init__(self, message: str = "", *, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class SessionNotFoundError(CloudBrowserError):
    """Session not found (404). Already deleted or never created."""


class ProviderError(CloudBrowserError):
    """Provider internal error (5xx).

    Attributes:
        status_code: HTTP status code.
        request_id: Request tracking ID for reporting to provider.
    """

    def __init__(
        self,
        message: str = "",
        *,
        status_code: int | None = None,
        request_id: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


class TimeoutError(CloudBrowserError):
    """Operation timed out."""


class NetworkError(CloudBrowserError):
    """Network connection failure."""
