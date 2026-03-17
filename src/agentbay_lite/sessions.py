"""Session CRUD resources for AgentBay cloud browser SDK.

AgentBay's session creation requires 3 sequential RPC calls:
1. CreateMcpSession → get SessionId
2. InitBrowser → start browser with BrowserOption
3. GetCdpLink → get CDP WebSocket URL
"""

from __future__ import annotations

import json
import time
from typing import Any

from .exceptions import SessionNotFoundError, TimeoutError
from .models import (
    ContextAttach,
    FingerprintConfig,
    ManagedProxyConfig,
    ProxyConfig,
    RecordingConfig,
    SessionInfo,
    _BROWSER_DATA_PATH,
    _build_browser_option,
    _build_create_body,
    map_status,
)

_CONTEXT_SYNC_POLL_INITIAL = 0.5
_CONTEXT_SYNC_POLL_MAX = 5.0
_CONTEXT_SYNC_TIMEOUT = 30.0


def _to_session_info(
    data: dict[str, Any],
    session_id: str | None = None,
    cdp_url: str | None = None,
    delete_fn: Any = None,
) -> SessionInfo:
    """Map AgentBay API response data to SessionInfo."""
    info = SessionInfo(
        session_id=session_id or data.get("SessionId", ""),
        cdp_url=cdp_url or data.get("Url"),
        status=map_status(data.get("Status", "RUNNING")),
        created_at=data.get("CreateTime"),
        metadata={
            k: v
            for k, v in data.items()
            if k not in {"SessionId", "Url", "Status", "CreateTime"}
        },
    )
    if delete_fn is not None:
        info.set_delete_fn(delete_fn)
    return info


class SessionsResource:
    """Synchronous session CRUD operations via AgentBay RPC."""

    def __init__(self, rpc: Any) -> None:
        self._rpc = rpc

    def create(
        self,
        *,
        browser_mode: str = "normal",
        proxy: ProxyConfig | ManagedProxyConfig | None = None,
        recording: RecordingConfig | None = None,
        fingerprint: FingerprintConfig | str | None = None,
        context: ContextAttach | None = None,
        **vendor_params: Any,
    ) -> SessionInfo:
        """Create a browser session via 3-step RPC flow.

        Steps:
            1. CreateMcpSession → SessionId
            2. InitBrowser → start browser
            3. GetCdpLink → CDP WebSocket URL

        On failure at any step, cleanup via DeleteSessionAsync.
        """
        create_body = _build_create_body(recording, context, vendor_params)
        session_id: str | None = None

        try:
            # Step 1: CreateMcpSession
            create_data = self._rpc.rpc_call("CreateMcpSession", create_body)
            session_id = create_data.get("SessionId", "")
            if not session_id:
                raise ValueError("SessionId not found in CreateMcpSession response")

            # Step 1.5: Wait for context sync if context was provided
            needs_context_sync = bool(create_body.get("PersistenceDataList"))
            if needs_context_sync:
                self._wait_for_context_sync(session_id)

            # Step 2: InitBrowser
            browser_option = _build_browser_option(
                browser_mode, fingerprint, proxy, vendor_params
            )
            init_body: dict[str, Any] = {
                "SessionId": session_id,
                "PersistentPath": _BROWSER_DATA_PATH,
                "BrowserOption": json.dumps(browser_option),
            }
            self._rpc.rpc_call("InitBrowser", init_body)

            # Step 3: GetCdpLink
            cdp_data = self._rpc.rpc_call("GetCdpLink", {"SessionId": session_id})
            cdp_url = cdp_data.get("Url", "")

            def _delete() -> None:
                self.delete(session_id)  # type: ignore[arg-type]

            return _to_session_info(
                create_data, session_id=session_id, cdp_url=cdp_url, delete_fn=_delete
            )

        except Exception:
            if session_id:
                self._cleanup_session(session_id)
            raise

    def get(self, session_id: str) -> SessionInfo:
        """Get session info by ID."""
        data = self._rpc.rpc_call("GetSessionDetail", {"SessionId": session_id})
        return _to_session_info(data, session_id=session_id)

    def list(self, **filters: Any) -> list[SessionInfo]:
        """List sessions, optionally filtered.

        Note: ListSession returns session IDs with minimal info.
        Use get() for full session details.
        """
        body: dict[str, Any] = {}
        if "labels" in filters:
            body["Labels"] = json.dumps(filters["labels"])
        if "status" in filters:
            body["Status"] = filters["status"]
        if "max_results" in filters:
            body["MaxResults"] = filters["max_results"]
        if "next_token" in filters:
            body["NextToken"] = filters["next_token"]

        data = self._rpc.rpc_call("ListSession", body if body else None)

        # ListSession may return a list directly or {"Sessions": [...]}
        if isinstance(data, list):
            sessions = data
        else:
            sessions = data.get("Sessions") or data.get("sessions") or []
        return [
            SessionInfo(
                session_id=s.get("SessionId", ""),
                status=map_status(s.get("Status", "RUNNING")),
            )
            for s in sessions
        ]

    def delete(self, session_id: str) -> None:
        """Delete (close) a session. Idempotent — ignores not-found errors."""
        try:
            self._rpc.rpc_call("DeleteSessionAsync", {"SessionId": session_id})
        except SessionNotFoundError:
            pass

    def _wait_for_context_sync(self, session_id: str) -> None:
        """Poll GetSessionDetail until context sync completes."""
        deadline = time.monotonic() + _CONTEXT_SYNC_TIMEOUT
        interval = _CONTEXT_SYNC_POLL_INITIAL

        while True:
            data = self._rpc.rpc_call("GetSessionDetail", {"SessionId": session_id})
            # Check context status from response
            context_data = data.get("ContextStatusData") or data.get("PersistenceDataStatus") or []
            if context_data:
                all_done = all(
                    item.get("Status") in ("Success", "Failed")
                    for item in context_data
                )
                if all_done:
                    return

            if time.monotonic() + interval > deadline:
                raise TimeoutError(
                    f"Context sync not complete after {_CONTEXT_SYNC_TIMEOUT}s "
                    f"for session {session_id}"
                )

            time.sleep(interval)
            interval = min(interval * 2, _CONTEXT_SYNC_POLL_MAX)

    def _cleanup_session(self, session_id: str) -> None:
        """Best-effort session cleanup — swallow all exceptions."""
        try:
            self._rpc.rpc_call("DeleteSessionAsync", {"SessionId": session_id})
        except Exception:
            pass


class AsyncSessionsResource:
    """Asynchronous session CRUD operations via AgentBay RPC."""

    def __init__(self, rpc: Any) -> None:
        self._rpc = rpc

    async def create(
        self,
        *,
        browser_mode: str = "normal",
        proxy: ProxyConfig | ManagedProxyConfig | None = None,
        recording: RecordingConfig | None = None,
        fingerprint: FingerprintConfig | str | None = None,
        context: ContextAttach | None = None,
        **vendor_params: Any,
    ) -> SessionInfo:
        """Create a browser session via 3-step RPC flow (async)."""
        create_body = _build_create_body(recording, context, vendor_params)
        session_id: str | None = None

        try:
            # Step 1: CreateMcpSession
            create_data = await self._rpc.rpc_call("CreateMcpSession", create_body)
            session_id = create_data.get("SessionId", "")
            if not session_id:
                raise ValueError("SessionId not found in CreateMcpSession response")

            # Step 1.5: Wait for context sync if context was provided
            needs_context_sync = bool(create_body.get("PersistenceDataList"))
            if needs_context_sync:
                await self._wait_for_context_sync(session_id)

            # Step 2: InitBrowser
            browser_option = _build_browser_option(
                browser_mode, fingerprint, proxy, vendor_params
            )
            init_body: dict[str, Any] = {
                "SessionId": session_id,
                "PersistentPath": _BROWSER_DATA_PATH,
                "BrowserOption": json.dumps(browser_option),
            }
            await self._rpc.rpc_call("InitBrowser", init_body)

            # Step 3: GetCdpLink
            cdp_data = await self._rpc.rpc_call("GetCdpLink", {"SessionId": session_id})
            cdp_url = cdp_data.get("Url", "")

            def _delete() -> None:
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    loop.create_task(self.delete(session_id))  # type: ignore[arg-type]
                else:
                    asyncio.run(self.delete(session_id))  # type: ignore[arg-type]

            return _to_session_info(
                create_data, session_id=session_id, cdp_url=cdp_url, delete_fn=_delete
            )

        except Exception:
            if session_id:
                await self._cleanup_session(session_id)
            raise

    async def get(self, session_id: str) -> SessionInfo:
        """Get session info by ID (async)."""
        data = await self._rpc.rpc_call("GetSessionDetail", {"SessionId": session_id})
        return _to_session_info(data, session_id=session_id)

    async def list(self, **filters: Any) -> list[SessionInfo]:
        """List sessions (async), optionally filtered."""
        body: dict[str, Any] = {}
        if "labels" in filters:
            body["Labels"] = json.dumps(filters["labels"])
        if "status" in filters:
            body["Status"] = filters["status"]
        if "max_results" in filters:
            body["MaxResults"] = filters["max_results"]
        if "next_token" in filters:
            body["NextToken"] = filters["next_token"]

        data = await self._rpc.rpc_call("ListSession", body if body else None)

        if isinstance(data, list):
            sessions = data
        else:
            sessions = data.get("Sessions") or data.get("sessions") or []
        return [
            SessionInfo(
                session_id=s.get("SessionId", ""),
                status=map_status(s.get("Status", "RUNNING")),
            )
            for s in sessions
        ]

    async def delete(self, session_id: str) -> None:
        """Delete (close) a session (async). Idempotent."""
        try:
            await self._rpc.rpc_call("DeleteSessionAsync", {"SessionId": session_id})
        except SessionNotFoundError:
            pass

    async def _wait_for_context_sync(self, session_id: str) -> None:
        """Poll GetSessionDetail until context sync completes (async)."""
        import asyncio

        deadline = time.monotonic() + _CONTEXT_SYNC_TIMEOUT
        interval = _CONTEXT_SYNC_POLL_INITIAL

        while True:
            data = await self._rpc.rpc_call(
                "GetSessionDetail", {"SessionId": session_id}
            )
            context_data = data.get("ContextStatusData") or data.get("PersistenceDataStatus") or []
            if context_data:
                all_done = all(
                    item.get("Status") in ("Success", "Failed")
                    for item in context_data
                )
                if all_done:
                    return

            if time.monotonic() + interval > deadline:
                raise TimeoutError(
                    f"Context sync not complete after {_CONTEXT_SYNC_TIMEOUT}s "
                    f"for session {session_id}"
                )

            await asyncio.sleep(interval)
            interval = min(interval * 2, _CONTEXT_SYNC_POLL_MAX)

    async def _cleanup_session(self, session_id: str) -> None:
        """Best-effort session cleanup — swallow all exceptions."""
        try:
            await self._rpc.rpc_call("DeleteSessionAsync", {"SessionId": session_id})
        except Exception:
            pass
