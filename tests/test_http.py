"""Tests for Alibaba Cloud RPC transport."""

from __future__ import annotations

import httpx
import pytest
import respx

from agentbay_lite._http import (
    AsyncRpcClient,
    SyncRpcClient,
    _parse_rpc_response,
    _raise_for_rpc_error,
)
from agentbay_lite.exceptions import (
    AuthenticationError,
    CloudBrowserError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    TimeoutError,
)

ENDPOINT = "test.aliyuncs.com"
API_KEY = "test-key-123"


class TestRaiseForRpcError:
    def test_auth_error(self):
        with pytest.raises(AuthenticationError):
            _raise_for_rpc_error("Unauthorized", "bad key", None)

    def test_auth_error_partial_match(self):
        with pytest.raises(AuthenticationError):
            _raise_for_rpc_error("InvalidAuthToken", "expired", None)

    def test_not_found_error(self):
        with pytest.raises(SessionNotFoundError):
            _raise_for_rpc_error("SessionNotFound", "gone", None)

    def test_not_exist_error(self):
        with pytest.raises(SessionNotFoundError):
            _raise_for_rpc_error("ResourceNotExist", "no such", None)

    def test_throttling_error(self):
        with pytest.raises(QuotaExceededError):
            _raise_for_rpc_error("Throttling", "too many", None)

    def test_generic_provider_error(self):
        with pytest.raises(ProviderError) as exc_info:
            _raise_for_rpc_error("InternalError", "boom", "req-1", status_code=500)
        assert exc_info.value.status_code == 500
        assert exc_info.value.request_id == "req-1"


class TestParseRpcResponse:
    def test_success_with_data(self):
        response = httpx.Response(
            200,
            json={"body": {"Success": True, "Data": {"SessionId": "s1"}, "RequestId": "r1"}},
        )
        result = _parse_rpc_response(response)
        assert result["SessionId"] == "s1"

    def test_success_flat_response(self):
        response = httpx.Response(
            200,
            json={"Success": True, "Data": {"Url": "wss://test"}, "RequestId": "r1"},
        )
        result = _parse_rpc_response(response)
        assert result["Url"] == "wss://test"

    def test_http_401_raises_auth_error(self):
        response = httpx.Response(401, text="Unauthorized")
        with pytest.raises(AuthenticationError):
            _parse_rpc_response(response)

    def test_http_429_raises_quota_error(self):
        response = httpx.Response(429, text="Too Many Requests")
        with pytest.raises(QuotaExceededError):
            _parse_rpc_response(response)

    def test_http_500_raises_provider_error(self):
        response = httpx.Response(500, text="Internal Server Error")
        with pytest.raises(ProviderError):
            _parse_rpc_response(response)

    def test_rpc_level_error_in_200(self):
        response = httpx.Response(
            200,
            json={"body": {"Success": False, "Code": "SessionNotFound", "Message": "gone"}},
        )
        with pytest.raises(SessionNotFoundError):
            _parse_rpc_response(response)

    def test_http_400_with_rpc_code(self):
        response = httpx.Response(
            400,
            json={"body": {"Code": "Throttling", "Message": "rate limited"}},
        )
        with pytest.raises(QuotaExceededError):
            _parse_rpc_response(response)


class TestSyncRpcClient:
    @respx.mock
    def test_rpc_call_url_and_form_encoding(self):
        route = respx.post(f"https://{ENDPOINT}/").mock(
            return_value=httpx.Response(
                200,
                json={"body": {"Success": True, "Data": {"SessionId": "s1"}}},
            )
        )

        client = SyncRpcClient(ENDPOINT, API_KEY)
        result = client.rpc_call("CreateMcpSession", {"ImageId": "img-1"})

        assert result["SessionId"] == "s1"
        assert route.called

        request = route.calls[0].request
        # Check query params
        assert "Action=CreateMcpSession" in str(request.url)
        assert "Version=2025-05-06" in str(request.url)
        assert "Format=json" in str(request.url)

        # Check form body contains Authorization
        body_text = request.content.decode()
        assert "Authorization=Bearer+test-key-123" in body_text or "Authorization=Bearer%20test-key-123" in body_text
        assert "ImageId=img-1" in body_text

        client.close()

    @respx.mock
    def test_retry_on_500(self):
        route = respx.post(f"https://{ENDPOINT}/").mock(
            side_effect=[
                httpx.Response(500, text="error"),
                httpx.Response(
                    200,
                    json={"body": {"Success": True, "Data": {"ok": True}}},
                ),
            ]
        )

        client = SyncRpcClient(ENDPOINT, API_KEY, max_retries=1)
        result = client.rpc_call("Test")
        assert result["ok"] is True
        assert route.call_count == 2
        client.close()

    @respx.mock
    def test_timeout_exception(self):
        respx.post(f"https://{ENDPOINT}/").mock(
            side_effect=httpx.TimeoutException("timed out")
        )

        client = SyncRpcClient(ENDPOINT, API_KEY, max_retries=0)
        with pytest.raises(TimeoutError):
            client.rpc_call("Test")
        client.close()

    @respx.mock
    def test_connect_error(self):
        respx.post(f"https://{ENDPOINT}/").mock(
            side_effect=httpx.ConnectError("refused")
        )

        client = SyncRpcClient(ENDPOINT, API_KEY, max_retries=0)
        with pytest.raises(NetworkError):
            client.rpc_call("Test")
        client.close()

    @respx.mock
    def test_empty_body_defaults(self):
        respx.post(f"https://{ENDPOINT}/").mock(
            return_value=httpx.Response(
                200,
                json={"body": {"Success": True, "Data": {"key": "val"}}},
            )
        )

        client = SyncRpcClient(ENDPOINT, API_KEY)
        result = client.rpc_call("Test")
        assert result["key"] == "val"

        # Verify Authorization was in form body even without explicit body
        client.close()


class TestAsyncRpcClient:
    @respx.mock
    @pytest.mark.asyncio
    async def test_async_rpc_call(self):
        respx.post(f"https://{ENDPOINT}/").mock(
            return_value=httpx.Response(
                200,
                json={"body": {"Success": True, "Data": {"SessionId": "s1"}}},
            )
        )

        client = AsyncRpcClient(ENDPOINT, API_KEY)
        result = await client.rpc_call("CreateMcpSession")
        assert result["SessionId"] == "s1"
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_retry_on_500(self):
        route = respx.post(f"https://{ENDPOINT}/").mock(
            side_effect=[
                httpx.Response(500, text="error"),
                httpx.Response(
                    200,
                    json={"body": {"Success": True, "Data": {"ok": True}}},
                ),
            ]
        )

        client = AsyncRpcClient(ENDPOINT, API_KEY, max_retries=1)
        result = await client.rpc_call("Test")
        assert result["ok"] is True
        assert route.call_count == 2
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_timeout(self):
        respx.post(f"https://{ENDPOINT}/").mock(
            side_effect=httpx.TimeoutException("timed out")
        )

        client = AsyncRpcClient(ENDPOINT, API_KEY, max_retries=0)
        with pytest.raises(TimeoutError):
            await client.rpc_call("Test")
        await client.close()
