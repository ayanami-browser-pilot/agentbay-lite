"""Tests for session CRUD resources — multi-step create + CRUD."""

from __future__ import annotations

import json
from typing import Any

import pytest

from agentbay_lite.exceptions import ProviderError, SessionNotFoundError
from agentbay_lite.models import (
    ContextAttach,
    FingerprintConfig,
    ManagedProxyConfig,
    ProxyConfig,
    RecordingConfig,
    ViewportConfig,
)
from agentbay_lite.sessions import SessionsResource, AsyncSessionsResource

from .conftest import (
    FakeAsyncRpc,
    FakeSyncRpc,
    SAMPLE_CDP_LINK_RESPONSE,
    SAMPLE_CREATE_RESPONSE,
    SAMPLE_INIT_BROWSER_RESPONSE,
    SAMPLE_LIST_RESPONSE,
    SAMPLE_SESSION_DETAIL_RESPONSE,
)


class TestCreateMultiStep:
    def test_create_calls_three_rpc_actions_in_order(self, sync_sessions, fake_sync_rpc):
        session = sync_sessions.create()

        actions = [call[0] for call in fake_sync_rpc.calls]
        assert actions == ["CreateMcpSession", "InitBrowser", "GetCdpLink"]

    def test_create_returns_session_id(self, sync_sessions):
        session = sync_sessions.create()
        assert session.session_id == "sess-abc123"

    def test_create_returns_cdp_url(self, sync_sessions):
        session = sync_sessions.create()
        assert session.cdp_url == SAMPLE_CDP_LINK_RESPONSE["Url"]

    def test_create_returns_active_status(self, sync_sessions):
        session = sync_sessions.create()
        assert session.status == "active"

    def test_create_passes_session_id_to_init_browser(self, sync_sessions, fake_sync_rpc):
        sync_sessions.create()
        init_call = fake_sync_rpc.calls[1]
        assert init_call[0] == "InitBrowser"
        assert init_call[1]["SessionId"] == "sess-abc123"

    def test_create_passes_session_id_to_get_cdp_link(self, sync_sessions, fake_sync_rpc):
        sync_sessions.create()
        cdp_call = fake_sync_rpc.calls[2]
        assert cdp_call[0] == "GetCdpLink"
        assert cdp_call[1]["SessionId"] == "sess-abc123"


class TestCreateCleanup:
    def test_cleanup_on_init_browser_failure(self):
        call_count = {"count": 0}

        def fail_on_init():
            raise ProviderError("init failed", status_code=500)

        rpc = FakeSyncRpc({
            "CreateMcpSession": dict(SAMPLE_CREATE_RESPONSE),
            "InitBrowser": fail_on_init,
            "DeleteSessionAsync": {"Success": True},
        })
        sessions = SessionsResource(rpc)

        with pytest.raises(ProviderError, match="init failed"):
            sessions.create()

        # Verify cleanup was called
        actions = [call[0] for call in rpc.calls]
        assert "DeleteSessionAsync" in actions
        delete_call = next(c for c in rpc.calls if c[0] == "DeleteSessionAsync")
        assert delete_call[1]["SessionId"] == "sess-abc123"

    def test_cleanup_on_get_cdp_link_failure(self):
        def fail_on_cdp():
            raise ProviderError("cdp failed", status_code=500)

        rpc = FakeSyncRpc({
            "CreateMcpSession": dict(SAMPLE_CREATE_RESPONSE),
            "InitBrowser": dict(SAMPLE_INIT_BROWSER_RESPONSE),
            "GetCdpLink": fail_on_cdp,
            "DeleteSessionAsync": {"Success": True},
        })
        sessions = SessionsResource(rpc)

        with pytest.raises(ProviderError, match="cdp failed"):
            sessions.create()

        actions = [call[0] for call in rpc.calls]
        assert "DeleteSessionAsync" in actions


class TestCreateOptions:
    def test_stealth_mode(self, sync_sessions, fake_sync_rpc):
        sync_sessions.create(browser_mode="stealth")

        init_call = fake_sync_rpc.calls[1]
        browser_option = json.loads(init_call[1]["BrowserOption"])
        assert browser_option["useStealth"] is True

    def test_custom_proxy(self, sync_sessions, fake_sync_rpc):
        sync_sessions.create(proxy=ProxyConfig(server="http://p:8080"))

        init_call = fake_sync_rpc.calls[1]
        browser_option = json.loads(init_call[1]["BrowserOption"])
        assert browser_option["proxies"][0]["type"] == "custom"
        assert browser_option["proxies"][0]["server"] == "http://p:8080"

    def test_managed_proxy(self, sync_sessions, fake_sync_rpc):
        sync_sessions.create(proxy=ManagedProxyConfig(country="US"))

        init_call = fake_sync_rpc.calls[1]
        browser_option = json.loads(init_call[1]["BrowserOption"])
        assert browser_option["proxies"][0]["type"] == "wuying"
        assert browser_option["proxies"][0]["strategy"] == "restricted"

    def test_fingerprint(self, sync_sessions, fake_sync_rpc):
        fp = FingerprintConfig(
            user_agent="TestBot/1.0",
            viewport=ViewportConfig(width=1280, height=720),
        )
        sync_sessions.create(fingerprint=fp)

        init_call = fake_sync_rpc.calls[1]
        browser_option = json.loads(init_call[1]["BrowserOption"])
        assert browser_option["userAgent"] == "TestBot/1.0"
        assert browser_option["viewport"] == {"width": 1280, "height": 720}

    def test_recording_disabled(self, sync_sessions, fake_sync_rpc):
        sync_sessions.create(recording=RecordingConfig(enabled=False))

        create_call = fake_sync_rpc.calls[0]
        assert create_call[1]["EnableRecord"] is False

    def test_vendor_params(self, sync_sessions, fake_sync_rpc):
        sync_sessions.create(
            image_id="img-1",
            labels={"env": "test"},
            idle_release_timeout=300,
        )

        create_call = fake_sync_rpc.calls[0]
        body = create_call[1]
        assert body["ImageId"] == "img-1"
        assert json.loads(body["Labels"]) == {"env": "test"}
        assert body["Timeout"] == 300

    def test_context_persistence(self):
        rpc = FakeSyncRpc({
            "CreateMcpSession": dict(SAMPLE_CREATE_RESPONSE),
            "InitBrowser": dict(SAMPLE_INIT_BROWSER_RESPONSE),
            "GetCdpLink": dict(SAMPLE_CDP_LINK_RESPONSE),
            "GetSessionDetail": {
                "SessionId": "sess-abc123",
                "Status": "RUNNING",
                "ContextStatusData": [
                    {"ContextId": "ctx-001", "Status": "Success"},
                ],
            },
            "DeleteSessionAsync": {"Success": True},
        })
        sessions = SessionsResource(rpc)

        ctx = ContextAttach(context_id="ctx-001")
        session = sessions.create(context=ctx)

        create_call = rpc.calls[0]
        persistence = json.loads(create_call[1]["PersistenceDataList"])
        assert len(persistence) == 1
        assert persistence[0]["context_id"] == "ctx-001"
        assert session.session_id == "sess-abc123"


class TestCreateContextManager:
    def test_context_manager_auto_delete(self, sync_sessions, fake_sync_rpc):
        with sync_sessions.create() as session:
            assert session.session_id == "sess-abc123"

        # After exit, delete should be called
        actions = [call[0] for call in fake_sync_rpc.calls]
        assert actions.count("DeleteSessionAsync") == 1


class TestGet:
    def test_get_returns_session_info(self, sync_sessions):
        info = sync_sessions.get("sess-abc123")
        assert info.session_id == "sess-abc123"
        assert info.status == "active"

    def test_get_maps_status(self):
        rpc = FakeSyncRpc({
            "GetSessionDetail": {"SessionId": "s1", "Status": "PAUSED"},
        })
        sessions = SessionsResource(rpc)
        info = sessions.get("s1")
        assert info.status == "closed"


class TestList:
    def test_list_returns_sessions(self, sync_sessions):
        result = sync_sessions.list()
        assert len(result) == 2
        assert result[0].session_id == "sess-001"
        assert result[0].status == "active"
        assert result[1].session_id == "sess-002"
        assert result[1].status == "closed"

    def test_list_with_filters(self, fake_sync_rpc):
        sessions = SessionsResource(fake_sync_rpc)
        sessions.list(status="RUNNING", max_results=10)

        list_call = fake_sync_rpc.calls[0]
        assert list_call[1]["Status"] == "RUNNING"
        assert list_call[1]["MaxResults"] == 10


class TestDelete:
    def test_delete_calls_rpc(self, sync_sessions, fake_sync_rpc):
        sync_sessions.delete("sess-abc123")

        assert len(fake_sync_rpc.calls) == 1
        assert fake_sync_rpc.calls[0] == ("DeleteSessionAsync", {"SessionId": "sess-abc123"})

    def test_delete_idempotent(self):
        rpc = FakeSyncRpc({
            "DeleteSessionAsync": SessionNotFoundError("not found"),
        })
        sessions = SessionsResource(rpc)
        sessions.delete("gone")  # Should not raise


class TestStatusMapping:
    def test_running(self):
        rpc = FakeSyncRpc({
            "GetSessionDetail": {"SessionId": "s1", "Status": "RUNNING"},
        })
        info = SessionsResource(rpc).get("s1")
        assert info.status == "active"

    def test_pausing(self):
        rpc = FakeSyncRpc({
            "GetSessionDetail": {"SessionId": "s1", "Status": "PAUSING"},
        })
        info = SessionsResource(rpc).get("s1")
        assert info.status == "active"

    def test_deleted(self):
        rpc = FakeSyncRpc({
            "GetSessionDetail": {"SessionId": "s1", "Status": "DELETED"},
        })
        info = SessionsResource(rpc).get("s1")
        assert info.status == "closed"


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncCreate:
    @pytest.mark.asyncio
    async def test_async_create_three_steps(self, async_sessions, fake_async_rpc):
        session = await async_sessions.create()

        actions = [call[0] for call in fake_async_rpc.calls]
        assert actions == ["CreateMcpSession", "InitBrowser", "GetCdpLink"]
        assert session.session_id == "sess-abc123"
        assert session.cdp_url == SAMPLE_CDP_LINK_RESPONSE["Url"]

    @pytest.mark.asyncio
    async def test_async_cleanup_on_failure(self):
        def fail_on_init():
            raise ProviderError("fail", status_code=500)

        rpc = FakeAsyncRpc({
            "CreateMcpSession": dict(SAMPLE_CREATE_RESPONSE),
            "InitBrowser": fail_on_init,
            "DeleteSessionAsync": {"Success": True},
        })
        sessions = AsyncSessionsResource(rpc)

        with pytest.raises(ProviderError):
            await sessions.create()

        actions = [call[0] for call in rpc.calls]
        assert "DeleteSessionAsync" in actions


class TestAsyncGet:
    @pytest.mark.asyncio
    async def test_async_get(self, async_sessions):
        info = await async_sessions.get("sess-abc123")
        assert info.session_id == "sess-abc123"
        assert info.status == "active"


class TestAsyncList:
    @pytest.mark.asyncio
    async def test_async_list(self, async_sessions):
        result = await async_sessions.list()
        assert len(result) == 2


class TestAsyncDelete:
    @pytest.mark.asyncio
    async def test_async_delete_idempotent(self):
        rpc = FakeAsyncRpc({
            "DeleteSessionAsync": SessionNotFoundError("not found"),
        })
        sessions = AsyncSessionsResource(rpc)
        await sessions.delete("gone")  # Should not raise
