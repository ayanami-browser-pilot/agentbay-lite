"""Alibaba Cloud RPC transport for AgentBay cloud browser SDK."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .exceptions import (
    AuthenticationError,
    CloudBrowserError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    TimeoutError,
)

_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_DEFAULT_BACKOFF_BASE = 0.5
_DEFAULT_BACKOFF_MAX = 3.0
_API_VERSION = "2025-05-06"


def _raise_for_rpc_error(
    code: str,
    message: str,
    request_id: str | None,
    status_code: int | None = None,
) -> None:
    """Map RPC error codes to SDK exceptions."""
    code_upper = code.upper() if code else ""

    if "AUTH" in code_upper or "UNAUTHORIZED" in code_upper:
        raise AuthenticationError(message)
    if "NOTFOUND" in code_upper or "NOTEXIST" in code_upper:
        raise SessionNotFoundError(message)
    if "THROTTLING" in code_upper:
        raise QuotaExceededError(message)

    raise ProviderError(
        message, status_code=status_code, request_id=request_id
    )


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse Retry-After header value in seconds."""
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_rpc_response(response: httpx.Response) -> dict[str, Any]:
    """Parse an Alibaba Cloud RPC JSON response.

    Expected shape: {"body": {"Success": true, "Data": {...}, "RequestId": "..."}}
    Or flat: {"Success": true, "Data": {...}, "RequestId": "..."}
    """
    status = response.status_code

    # Map HTTP-level errors first
    if status in (401, 403):
        raise AuthenticationError(f"HTTP {status}: {response.text}")
    if status == 429:
        retry_after_val = _parse_retry_after(response)
        retry_after_int = int(retry_after_val) if retry_after_val is not None else None
        raise QuotaExceededError(f"HTTP {status}: {response.text}", retry_after=retry_after_int)
    if status >= 500:
        raise ProviderError(
            f"HTTP {status}: {response.text}",
            status_code=status,
            request_id=response.headers.get("x-acs-request-id"),
        )
    if status >= 400:
        # Try to parse RPC error from body
        try:
            body = response.json()
        except Exception:
            raise CloudBrowserError(f"HTTP {status}: {response.text}")

        wrapper = body.get("body", body)
        code = wrapper.get("Code", "")
        message = wrapper.get("Message", response.text)
        request_id = wrapper.get("RequestId")
        if code:
            _raise_for_rpc_error(code, message, request_id, status_code=status)
        raise CloudBrowserError(f"HTTP {status}: {message}")

    # Success path
    try:
        body = response.json()
    except Exception:
        return {}

    # Unwrap {"body": {...}} envelope if present
    wrapper = body.get("body", body)

    # Check for RPC-level errors in successful HTTP responses
    if not wrapper.get("Success", True) and wrapper.get("Code"):
        code = wrapper["Code"]
        message = wrapper.get("Message", "Unknown RPC error")
        request_id = wrapper.get("RequestId")
        _raise_for_rpc_error(code, message, request_id)

    return wrapper.get("Data", wrapper)


class SyncRpcClient:
    """Synchronous Alibaba Cloud RPC transport with retry logic."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        base_url = f"https://{endpoint}"
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._api_key = api_key
        self._max_retries = max_retries

    def rpc_call(self, action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute an RPC call with retry on transient errors."""
        form_body = dict(body) if body else {}
        form_body["Authorization"] = f"Bearer {self._api_key}"

        params = {
            "Action": action,
            "Version": _API_VERSION,
            "Format": "json",
        }

        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post("/", params=params, data=form_body)
            except httpx.TimeoutException as exc:
                last_exc = TimeoutError(str(exc))
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise last_exc from exc
            except httpx.ConnectError as exc:
                last_exc = NetworkError(str(exc))
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise last_exc from exc

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                wait = _parse_retry_after(response) or self._backoff_delay(attempt)
                time.sleep(wait)
                continue

            return _parse_rpc_response(response)

        if last_exc is not None:
            raise last_exc
        raise CloudBrowserError("Request failed after retries")

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        return min(_DEFAULT_BACKOFF_BASE * (2**attempt), _DEFAULT_BACKOFF_MAX)

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(min(_DEFAULT_BACKOFF_BASE * (2**attempt), _DEFAULT_BACKOFF_MAX))


class AsyncRpcClient:
    """Asynchronous Alibaba Cloud RPC transport with retry logic."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        base_url = f"https://{endpoint}"
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._api_key = api_key
        self._max_retries = max_retries

    async def rpc_call(self, action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute an async RPC call with retry on transient errors."""
        import asyncio

        form_body = dict(body) if body else {}
        form_body["Authorization"] = f"Bearer {self._api_key}"

        params = {
            "Action": action,
            "Version": _API_VERSION,
            "Format": "json",
        }

        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post("/", params=params, data=form_body)
            except httpx.TimeoutException as exc:
                last_exc = TimeoutError(str(exc))
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                raise last_exc from exc
            except httpx.ConnectError as exc:
                last_exc = NetworkError(str(exc))
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                raise last_exc from exc

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                wait = _parse_retry_after(response) or self._backoff_delay(attempt)
                await asyncio.sleep(wait)
                continue

            return _parse_rpc_response(response)

        if last_exc is not None:
            raise last_exc
        raise CloudBrowserError("Request failed after retries")

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        return min(_DEFAULT_BACKOFF_BASE * (2**attempt), _DEFAULT_BACKOFF_MAX)
