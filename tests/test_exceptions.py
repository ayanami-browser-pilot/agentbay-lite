"""Tests for exception hierarchy."""

from agentbay_lite.exceptions import (
    AuthenticationError,
    CloudBrowserError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    TimeoutError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_base(self):
        for exc_cls in (
            AuthenticationError,
            QuotaExceededError,
            SessionNotFoundError,
            ProviderError,
            TimeoutError,
            NetworkError,
        ):
            assert issubclass(exc_cls, CloudBrowserError)

    def test_quota_exceeded_retry_after(self):
        exc = QuotaExceededError("rate limited", retry_after=30)
        assert exc.retry_after == 30
        assert "rate limited" in str(exc)

    def test_quota_exceeded_no_retry_after(self):
        exc = QuotaExceededError("rate limited")
        assert exc.retry_after is None

    def test_provider_error_attributes(self):
        exc = ProviderError("server error", status_code=500, request_id="req-123")
        assert exc.status_code == 500
        assert exc.request_id == "req-123"
        assert "server error" in str(exc)

    def test_provider_error_defaults(self):
        exc = ProviderError("oops")
        assert exc.status_code is None
        assert exc.request_id is None

    def test_catch_base_catches_all(self):
        for exc_cls in (
            AuthenticationError,
            QuotaExceededError,
            SessionNotFoundError,
            ProviderError,
            TimeoutError,
            NetworkError,
        ):
            try:
                raise exc_cls("test")
            except CloudBrowserError:
                pass  # Expected
