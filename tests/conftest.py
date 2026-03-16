"""Shared test fixtures for agentbay-lite."""

from __future__ import annotations

from typing import Any

import pytest

from agentbay_lite.sessions import AsyncSessionsResource, SessionsResource


# ---------------------------------------------------------------------------
# Canned RPC responses
# ---------------------------------------------------------------------------

SAMPLE_CREATE_RESPONSE = {
    "SessionId": "sess-abc123",
    "Success": True,
}

SAMPLE_INIT_BROWSER_RESPONSE = {
    "Port": 9222,
}

SAMPLE_CDP_LINK_RESPONSE = {
    "Url": "wss://wuyingai.cn-shanghai.aliyuncs.com/devtools/browser/sess-abc123",
}

SAMPLE_SESSION_DETAIL_RESPONSE = {
    "SessionId": "sess-abc123",
    "Status": "RUNNING",
    "CreateTime": "2026-01-15T10:00:00Z",
    "Url": "wss://wuyingai.cn-shanghai.aliyuncs.com/devtools/browser/sess-abc123",
}

SAMPLE_LIST_RESPONSE = {
    "Sessions": [
        {"SessionId": "sess-001", "Status": "RUNNING"},
        {"SessionId": "sess-002", "Status": "PAUSED"},
    ],
}

SAMPLE_DELETE_RESPONSE = {
    "Success": True,
}


# ---------------------------------------------------------------------------
# Fake RPC clients
# ---------------------------------------------------------------------------


class FakeSyncRpc:
    """Fake sync RPC client that returns canned responses per action."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses: dict[str, Any] = responses or {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def rpc_call(self, action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((action, body))
        response = self.responses.get(action, {})
        if callable(response):
            return response()
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        pass


class FakeAsyncRpc:
    """Fake async RPC client that returns canned responses per action."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses: dict[str, Any] = responses or {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def rpc_call(self, action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((action, body))
        response = self.responses.get(action, {})
        if callable(response):
            return response()
        if isinstance(response, Exception):
            raise response
        return response

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _default_sync_responses() -> dict[str, Any]:
    return {
        "CreateMcpSession": dict(SAMPLE_CREATE_RESPONSE),
        "InitBrowser": dict(SAMPLE_INIT_BROWSER_RESPONSE),
        "GetCdpLink": dict(SAMPLE_CDP_LINK_RESPONSE),
        "GetSessionDetail": dict(SAMPLE_SESSION_DETAIL_RESPONSE),
        "ListSession": dict(SAMPLE_LIST_RESPONSE),
        "DeleteSessionAsync": dict(SAMPLE_DELETE_RESPONSE),
    }


@pytest.fixture
def fake_sync_rpc() -> FakeSyncRpc:
    return FakeSyncRpc(_default_sync_responses())


@pytest.fixture
def fake_async_rpc() -> FakeAsyncRpc:
    return FakeAsyncRpc(_default_sync_responses())


@pytest.fixture
def sync_sessions(fake_sync_rpc: FakeSyncRpc) -> SessionsResource:
    return SessionsResource(fake_sync_rpc)


@pytest.fixture
def async_sessions(fake_async_rpc: FakeAsyncRpc) -> AsyncSessionsResource:
    return AsyncSessionsResource(fake_async_rpc)
