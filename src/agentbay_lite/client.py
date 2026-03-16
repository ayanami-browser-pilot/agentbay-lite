"""Cloud browser SDK clients for AgentBay."""

from __future__ import annotations

import os
from typing import Any

from ._http import AsyncRpcClient, SyncRpcClient
from .sessions import AsyncSessionsResource, SessionsResource

_DEFAULT_ENDPOINT = "wuyingai.cn-shanghai.aliyuncs.com"
_ENV_API_KEY = "AGENTBAY_API_KEY"
_ENV_ENDPOINT = "AGENTBAY_ENDPOINT"


class AgentBayCloud:
    """Synchronous AgentBay cloud browser client.

    Usage::

        client = AgentBayCloud(api_key="...")
        session = client.sessions.create()
        print(session.cdp_url)
        client.sessions.delete(session.session_id)
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        endpoint: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        resolved_key = api_key or os.environ.get(_ENV_API_KEY)
        if not resolved_key:
            raise ValueError(
                f"api_key must be provided or set {_ENV_API_KEY} environment variable"
            )
        resolved_endpoint = endpoint or os.environ.get(_ENV_ENDPOINT) or _DEFAULT_ENDPOINT
        self._rpc = SyncRpcClient(
            endpoint=resolved_endpoint,
            api_key=resolved_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._sessions = SessionsResource(self._rpc)

    @property
    def sessions(self) -> SessionsResource:
        """Session lifecycle management."""
        return self._sessions

    @property
    def contexts(self) -> None:
        """Context managed via create() vendor_params."""
        return None

    @property
    def capabilities(self) -> list[str]:
        """Declare supported enhanced capabilities."""
        return ["context_persistence", "fingerprint", "proxy", "recording"]

    def close(self) -> None:
        """Close the underlying RPC client."""
        self._rpc.close()

    def __enter__(self) -> "AgentBayCloud":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncAgentBayCloud:
    """Asynchronous AgentBay cloud browser client.

    Usage::

        async with AsyncAgentBayCloud(api_key="...") as client:
            session = await client.sessions.create()
            print(session.cdp_url)
            await client.sessions.delete(session.session_id)
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        endpoint: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        resolved_key = api_key or os.environ.get(_ENV_API_KEY)
        if not resolved_key:
            raise ValueError(
                f"api_key must be provided or set {_ENV_API_KEY} environment variable"
            )
        resolved_endpoint = endpoint or os.environ.get(_ENV_ENDPOINT) or _DEFAULT_ENDPOINT
        self._rpc = AsyncRpcClient(
            endpoint=resolved_endpoint,
            api_key=resolved_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._sessions = AsyncSessionsResource(self._rpc)

    @property
    def sessions(self) -> AsyncSessionsResource:
        """Session lifecycle management (async)."""
        return self._sessions

    @property
    def contexts(self) -> None:
        """Context managed via create() vendor_params."""
        return None

    @property
    def capabilities(self) -> list[str]:
        """Declare supported enhanced capabilities."""
        return ["context_persistence", "fingerprint", "proxy", "recording"]

    async def close(self) -> None:
        """Close the underlying RPC client."""
        await self._rpc.close()

    async def __aenter__(self) -> "AsyncAgentBayCloud":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
