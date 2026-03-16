"""Tests for data models and AgentBay-specific helpers."""

import json

from agentbay_lite.models import (
    ContextAttach,
    FingerprintConfig,
    ManagedProxyConfig,
    ProxyConfig,
    RecordingConfig,
    SessionInfo,
    ViewportConfig,
    _build_browser_option,
    _build_create_body,
    map_status,
)


class TestStatusMapping:
    def test_running_maps_to_active(self):
        assert map_status("RUNNING") == "active"

    def test_pausing_maps_to_active(self):
        assert map_status("PAUSING") == "active"

    def test_resuming_maps_to_active(self):
        assert map_status("RESUMING") == "active"

    def test_paused_maps_to_closed(self):
        assert map_status("PAUSED") == "closed"

    def test_deleting_maps_to_closed(self):
        assert map_status("DELETING") == "closed"

    def test_deleted_maps_to_closed(self):
        assert map_status("DELETED") == "closed"

    def test_unknown_passes_through(self):
        assert map_status("WEIRD") == "WEIRD"


class TestBuildBrowserOption:
    def test_normal_mode_empty(self):
        result = _build_browser_option("normal", None, None, {})
        assert result == {}

    def test_stealth_mode(self):
        result = _build_browser_option("stealth", None, None, {})
        assert result == {"useStealth": True}

    def test_fingerprint_user_agent(self):
        fp = FingerprintConfig(user_agent="MyBot/1.0")
        result = _build_browser_option("normal", fp, None, {})
        assert result == {"userAgent": "MyBot/1.0"}

    def test_fingerprint_viewport(self):
        fp = FingerprintConfig(viewport=ViewportConfig(width=1280, height=720))
        result = _build_browser_option("normal", fp, None, {})
        assert result == {"viewport": {"width": 1280, "height": 720}}

    def test_custom_proxy(self):
        proxy = ProxyConfig(server="http://proxy:8080", username="u", password="p")
        result = _build_browser_option("normal", None, proxy, {})
        assert result == {
            "proxies": [
                {"type": "custom", "server": "http://proxy:8080", "username": "u", "password": "p"}
            ]
        }

    def test_managed_proxy(self):
        proxy = ManagedProxyConfig(country="US")
        result = _build_browser_option("normal", None, proxy, {})
        assert result == {
            "proxies": [{"type": "wuying", "strategy": "restricted"}]
        }

    def test_vendor_params_browser_option_override(self):
        override = {"useStealth": True, "custom": "value"}
        result = _build_browser_option("normal", None, None, {"browser_option": override})
        assert result == override

    def test_stealth_with_proxy_combined(self):
        proxy = ProxyConfig(server="http://proxy:8080")
        result = _build_browser_option("stealth", None, proxy, {})
        assert result["useStealth"] is True
        assert len(result["proxies"]) == 1


class TestBuildCreateBody:
    def test_empty_params(self):
        result = _build_create_body(None, None, {})
        assert result == {}

    def test_image_id(self):
        result = _build_create_body(None, None, {"image_id": "img-123"})
        assert result["ImageId"] == "img-123"

    def test_labels(self):
        result = _build_create_body(None, None, {"labels": {"env": "test"}})
        assert json.loads(result["Labels"]) == {"env": "test"}

    def test_idle_release_timeout(self):
        result = _build_create_body(None, None, {"idle_release_timeout": 300})
        assert result["Timeout"] == 300

    def test_policy_id(self):
        result = _build_create_body(None, None, {"policy_id": "pol-abc"})
        assert result["McpPolicyId"] == "pol-abc"

    def test_recording_enabled_by_default(self):
        result = _build_create_body(RecordingConfig(enabled=True), None, {})
        assert "EnableRecord" not in result

    def test_recording_disabled(self):
        result = _build_create_body(RecordingConfig(enabled=False), None, {})
        assert result["EnableRecord"] is False

    def test_context_attach(self):
        ctx = ContextAttach(context_id="ctx-123")
        result = _build_create_body(None, ctx, {})
        persistence = json.loads(result["PersistenceDataList"])
        assert len(persistence) == 1
        assert persistence[0]["context_id"] == "ctx-123"

    def test_vendor_browser_context(self):
        bc = {"context_id": "bc-456", "path": "/custom"}
        result = _build_create_body(None, None, {"browser_context": bc})
        persistence = json.loads(result["PersistenceDataList"])
        assert len(persistence) == 1
        assert persistence[0]["context_id"] == "bc-456"


class TestSessionInfo:
    def test_defaults(self):
        info = SessionInfo(session_id="s1")
        assert info.session_id == "s1"
        assert info.cdp_url is None
        assert info.status == "active"
        assert info.metadata == {}

    def test_context_manager(self):
        deleted = []
        info = SessionInfo(session_id="s1")
        info.set_delete_fn(lambda: deleted.append(True))

        with info as s:
            assert s.session_id == "s1"

        assert deleted == [True]

    def test_context_manager_no_delete_fn(self):
        info = SessionInfo(session_id="s1")
        with info:
            pass  # Should not raise
