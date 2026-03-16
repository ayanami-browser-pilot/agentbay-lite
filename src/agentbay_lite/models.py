"""Data models for AgentBay cloud browser SDK."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Status mapping: AgentBay → spec
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[str, str] = {
    "RUNNING": "active",
    "PAUSING": "active",
    "PAUSED": "closed",
    "RESUMING": "active",
    "DELETING": "closed",
    "DELETED": "closed",
}


def map_status(agentbay_status: str) -> str:
    """Map an AgentBay status string to the unified spec status."""
    return _STATUS_MAP.get(agentbay_status, agentbay_status)


# ---------------------------------------------------------------------------
# Configuration models (shared with other lite SDKs)
# ---------------------------------------------------------------------------


class ManagedProxyConfig(BaseModel):
    """Managed proxy configuration — provider handles the proxy.

    For AgentBay, maps to wuying proxy with restricted strategy.
    """

    country: str
    city: str | None = None


class ProxyConfig(BaseModel):
    """Custom proxy configuration (server + credentials)."""

    server: str
    username: str | None = None
    password: str | None = None


class RecordingConfig(BaseModel):
    """Recording configuration."""

    enabled: bool = True


class ViewportConfig(BaseModel):
    """Viewport dimensions."""

    width: int = 1920
    height: int = 1080
    device_scale_factor: float = 1.0
    is_mobile: bool = False


class FingerprintConfig(BaseModel):
    """Browser fingerprint configuration. All fields optional."""

    user_agent: str | None = None
    viewport: ViewportConfig | None = None
    locale: str | None = None
    timezone: str | None = None
    webgl_vendor: str | None = None
    webgl_renderer: str | None = None
    platform: str | None = None


class ContextAttach(BaseModel):
    """Context attachment for session creation."""

    context_id: str
    mode: str = "read_write"


# ---------------------------------------------------------------------------
# SessionInfo
# ---------------------------------------------------------------------------


class SessionInfo(BaseModel):
    """Browser session information returned by create/get/list."""

    session_id: str
    cdp_url: str | None = None
    status: str = "active"
    created_at: datetime | None = None
    inspect_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Internal: deletion callback for context manager support.
    # Excluded from serialization.
    _delete_fn: Callable[[], None] | None = None

    model_config = {"arbitrary_types_allowed": True}

    def set_delete_fn(self, fn: Callable[[], None]) -> None:
        """Attach a deletion callback for context manager support."""
        object.__setattr__(self, "_delete_fn", fn)

    # --- Context manager protocol ---

    def __enter__(self) -> "SessionInfo":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        fn = getattr(self, "_delete_fn", None)
        if fn is not None:
            fn()


# ---------------------------------------------------------------------------
# AgentBay-specific helpers
# ---------------------------------------------------------------------------

_BROWSER_DATA_PATH = "/tmp/agentbay_browser"


def _build_browser_option(
    browser_mode: str,
    fingerprint: FingerprintConfig | str | None,
    proxy: ProxyConfig | ManagedProxyConfig | None,
    vendor_params: dict[str, Any],
) -> dict[str, Any]:
    """Convert spec params to AgentBay's BrowserOption dict."""
    # Allow raw override via vendor_params
    if "browser_option" in vendor_params:
        return dict(vendor_params["browser_option"])

    option: dict[str, Any] = {}

    # Stealth mode
    if browser_mode == "stealth":
        option["useStealth"] = True

    # Fingerprint
    if isinstance(fingerprint, FingerprintConfig):
        if fingerprint.user_agent:
            option["userAgent"] = fingerprint.user_agent
        if fingerprint.viewport:
            option["viewport"] = {
                "width": fingerprint.viewport.width,
                "height": fingerprint.viewport.height,
            }

    # Proxy
    if isinstance(proxy, ProxyConfig):
        proxy_entry: dict[str, Any] = {"type": "custom", "server": proxy.server}
        if proxy.username:
            proxy_entry["username"] = proxy.username
        if proxy.password:
            proxy_entry["password"] = proxy.password
        option["proxies"] = [proxy_entry]
    elif isinstance(proxy, ManagedProxyConfig):
        option["proxies"] = [{"type": "wuying", "strategy": "restricted"}]

    return option


def _build_create_body(
    recording: RecordingConfig | None,
    context: ContextAttach | None,
    vendor_params: dict[str, Any],
) -> dict[str, Any]:
    """Build form fields for CreateMcpSession RPC call."""
    body: dict[str, Any] = {}

    # ImageId
    if "image_id" in vendor_params:
        body["ImageId"] = vendor_params["image_id"]

    # Labels
    if "labels" in vendor_params:
        body["Labels"] = json.dumps(vendor_params["labels"])

    # Timeout (idle release timeout in seconds)
    if "idle_release_timeout" in vendor_params:
        body["Timeout"] = vendor_params["idle_release_timeout"]

    # McpPolicyId
    if "policy_id" in vendor_params:
        body["McpPolicyId"] = vendor_params["policy_id"]

    # Recording
    if recording is not None and not recording.enabled:
        body["EnableRecord"] = False

    # Context persistence
    persistence_list = []
    if context is not None:
        persistence_list.append(
            {"context_id": context.context_id, "path": _BROWSER_DATA_PATH}
        )
    if "browser_context" in vendor_params:
        bc = vendor_params["browser_context"]
        if isinstance(bc, dict):
            persistence_list.append(bc)
        elif hasattr(bc, "context_id"):
            persistence_list.append(
                {"context_id": bc.context_id, "path": _BROWSER_DATA_PATH}
            )
    if persistence_list:
        body["PersistenceDataList"] = json.dumps(persistence_list)

    return body
