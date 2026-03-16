"""Tests for client initialization and capabilities."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from agentbay_lite.client import AgentBayCloud, AsyncAgentBayCloud


class TestAgentBayCloudInit:
    def test_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="api_key"):
                AgentBayCloud()

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"AGENTBAY_API_KEY": "test-key"}):
            client = AgentBayCloud()
            assert client._rpc._api_key == "test-key"
            client.close()

    def test_api_key_explicit(self):
        client = AgentBayCloud(api_key="explicit-key")
        assert client._rpc._api_key == "explicit-key"
        client.close()

    def test_explicit_key_overrides_env(self):
        with patch.dict(os.environ, {"AGENTBAY_API_KEY": "env-key"}):
            client = AgentBayCloud(api_key="explicit-key")
            assert client._rpc._api_key == "explicit-key"
            client.close()

    def test_endpoint_from_env(self):
        with patch.dict(os.environ, {"AGENTBAY_ENDPOINT": "custom.endpoint.com"}):
            client = AgentBayCloud(api_key="key")
            assert "custom.endpoint.com" in str(client._rpc._client.base_url)
            client.close()

    def test_default_endpoint(self):
        client = AgentBayCloud(api_key="key")
        assert "wuyingai.cn-shanghai.aliyuncs.com" in str(client._rpc._client.base_url)
        client.close()

    def test_custom_endpoint(self):
        client = AgentBayCloud(api_key="key", endpoint="my.endpoint.com")
        assert "my.endpoint.com" in str(client._rpc._client.base_url)
        client.close()


class TestClientProperties:
    def test_sessions_property(self):
        client = AgentBayCloud(api_key="key")
        assert client.sessions is not None
        client.close()

    def test_contexts_is_none(self):
        client = AgentBayCloud(api_key="key")
        assert client.contexts is None
        client.close()

    def test_capabilities(self):
        client = AgentBayCloud(api_key="key")
        caps = client.capabilities
        assert "context_persistence" in caps
        assert "fingerprint" in caps
        assert "proxy" in caps
        assert "recording" in caps
        client.close()


class TestClientContextManager:
    def test_sync_context_manager(self):
        with AgentBayCloud(api_key="key") as client:
            assert client.sessions is not None
        # Should not raise after exit

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncAgentBayCloud(api_key="key") as client:
            assert client.sessions is not None


class TestAsyncAgentBayCloudInit:
    def test_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="api_key"):
                AsyncAgentBayCloud()

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"AGENTBAY_API_KEY": "test-key"}):
            client = AsyncAgentBayCloud()
            assert client._rpc._api_key == "test-key"

    @pytest.mark.asyncio
    async def test_async_capabilities(self):
        async with AsyncAgentBayCloud(api_key="key") as client:
            assert client.capabilities == ["context_persistence", "fingerprint", "proxy", "recording"]
