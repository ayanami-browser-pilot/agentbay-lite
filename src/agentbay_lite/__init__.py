"""AgentBay Cloud Browser SDK — minimal interface for browser session lifecycle.

Quick Start
-----------
::

    from agentbay_lite import AgentBayCloud

    client = AgentBayCloud(api_key="...")  # or set AGENTBAY_API_KEY env var

    # Create a cloud browser session
    session = client.sessions.create()
    print(session.cdp_url)   # wss://...
    print(session.session_id)

    # Use with Playwright (or any CDP client)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(session.cdp_url)
        page = browser.contexts[0].new_page()
        page.goto("https://example.com")

    # Cleanup
    client.sessions.delete(session.session_id)

    # Or use context manager for auto-cleanup:
    with client.sessions.create() as session:
        ...  # session auto-deleted on exit

API Reference
-------------

Client Classes
~~~~~~~~~~~~~~
- ``AgentBayCloud(api_key, *, endpoint, timeout, max_retries)``  — Sync client
- ``AsyncAgentBayCloud(api_key, *, endpoint, timeout, max_retries)`` — Async client
- ``AgentBay`` / ``AsyncAgentBay`` — Backward-compatible aliases

Client Properties
~~~~~~~~~~~~~~~~~
- ``client.sessions``     — SessionsResource for CRUD operations
- ``client.contexts``     — Always None (context managed via create() params)
- ``client.capabilities`` — Returns ``["context_persistence", "fingerprint", "proxy", "recording"]``

Session CRUD (``client.sessions``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- ``create(*, browser_mode, proxy, recording, fingerprint, context, **vendor_params) -> SessionInfo``
- ``get(session_id) -> SessionInfo``
- ``list(**filters) -> list[SessionInfo]``
- ``delete(session_id) -> None``  (idempotent, safe to call multiple times)

Vendor Parameters (pass via ``**vendor_params`` in ``create()``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- ``image_id: str``             — Custom image ID for the session
- ``labels: dict``              — Session labels (JSON-serialized)
- ``idle_release_timeout: int`` — Idle release timeout in seconds
- ``policy_id: str``            — MCP policy ID
- ``browser_context: dict``     — Browser context persistence config
- ``browser_option: dict``      — Raw BrowserOption override (advanced)

Create Flow
~~~~~~~~~~~
Session creation orchestrates 3 sequential RPC calls:
1. ``CreateMcpSession`` → get SessionId
2. ``InitBrowser`` → start browser with BrowserOption
3. ``GetCdpLink`` → get CDP WebSocket URL

On failure at any step, cleanup via ``DeleteSessionAsync``.

Exception Hierarchy
~~~~~~~~~~~~~~~~~~~
::

    CloudBrowserError          # Base exception
    ├── AuthenticationError    # 401/403 — invalid or expired API key
    ├── QuotaExceededError     # 429 — rate limit (has .retry_after attribute)
    ├── SessionNotFoundError   # 404 — session doesn't exist
    ├── ProviderError          # 5xx — server error (has .status_code, .request_id)
    ├── TimeoutError           # Operation timed out
    └── NetworkError           # Connection failure
"""

from .client import AgentBayCloud, AsyncAgentBayCloud
from .exceptions import (
    AuthenticationError,
    CloudBrowserError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    TimeoutError,
)
from .models import (
    ContextAttach,
    FingerprintConfig,
    ManagedProxyConfig,
    ProxyConfig,
    RecordingConfig,
    SessionInfo,
    ViewportConfig,
)

# Backward compatibility aliases
AgentBay = AgentBayCloud
AsyncAgentBay = AsyncAgentBayCloud

__all__ = [
    # Clients
    "AgentBayCloud",
    "AsyncAgentBayCloud",
    "AgentBay",
    "AsyncAgentBay",
    # Models
    "SessionInfo",
    "ContextAttach",
    "FingerprintConfig",
    "ViewportConfig",
    "ProxyConfig",
    "ManagedProxyConfig",
    "RecordingConfig",
    # Exceptions
    "CloudBrowserError",
    "AuthenticationError",
    "QuotaExceededError",
    "SessionNotFoundError",
    "ProviderError",
    "TimeoutError",
    "NetworkError",
]
