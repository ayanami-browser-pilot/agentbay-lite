# agentbay-lite

[![PyPI version](https://img.shields.io/pypi/v/agentbay-lite.svg)](https://pypi.org/project/agentbay-lite/)
[![Python](https://img.shields.io/pypi/pyversions/agentbay-lite.svg)](https://pypi.org/project/agentbay-lite/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Minimal cloud browser SDK for [AgentBay](https://help.aliyun.com/zh/wuying-agentbay/) (Alibaba Cloud Wuying) — session lifecycle management via CDP.

- **Lightweight**: only `httpx` + `pydantic`, no Alibaba Cloud SDK dependency
- **Sync & Async**: `AgentBayCloud` and `AsyncAgentBayCloud` clients
- **Context manager**: sessions auto-delete on exit
- **Unified interface**: same API shape as [browser-use-lite](https://pypi.org/project/browser-use-lite/), [skyvern-lite](https://pypi.org/project/skyvern-lite/), [airtop-lite](https://pypi.org/project/airtop-lite/)

## Install

```bash
pip install agentbay-lite
```

## Quick Start

```python
from agentbay_lite import AgentBayCloud

client = AgentBayCloud(api_key="...")  # or set AGENTBAY_API_KEY env var

# Create a cloud browser session (3-step RPC: CreateMcpSession -> InitBrowser -> GetCdpLink)
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
client.close()
```

## Context Manager

```python
with AgentBayCloud(api_key="...") as client:
    with client.sessions.create() as session:
        ...  # session auto-deleted on exit
```

## Async

```python
import asyncio
from agentbay_lite import AsyncAgentBayCloud

async def main():
    async with AsyncAgentBayCloud(api_key="...") as client:
        session = await client.sessions.create()
        print(session.cdp_url)
        await client.sessions.delete(session.session_id)

asyncio.run(main())
```

## Features

| Feature | Usage |
|---------|-------|
| Stealth mode | `create(browser_mode="stealth")` |
| Custom proxy | `create(proxy=ProxyConfig(server="http://..."))` |
| Managed proxy | `create(proxy=ManagedProxyConfig(country="US"))` |
| Fingerprint | `create(fingerprint=FingerprintConfig(user_agent="..."))` |
| Context persistence | `create(context=ContextAttach(context_id="..."))` |
| Recording control | `create(recording=RecordingConfig(enabled=False))` |
| Custom image | `create(image_id="img-xxx")` |
| Session labels | `create(labels={"env": "prod"})` |
| Idle timeout | `create(idle_release_timeout=300)` |

## Session CRUD

```python
# Create
session = client.sessions.create()

# Get
info = client.sessions.get(session.session_id)

# List
sessions = client.sessions.list(status="RUNNING")

# Delete (idempotent)
client.sessions.delete(session.session_id)
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `AGENTBAY_API_KEY` | API key (required if not passed explicitly) | — |
| `AGENTBAY_ENDPOINT` | API endpoint hostname | `wuyingai.cn-shanghai.aliyuncs.com` |

## Exception Hierarchy

```
CloudBrowserError          # Base exception
├── AuthenticationError    # 401/403 — invalid or expired API key
├── QuotaExceededError     # 429 — rate limit (has .retry_after attribute)
├── SessionNotFoundError   # 404 — session doesn't exist
├── ProviderError          # 5xx — server error (has .status_code, .request_id)
├── TimeoutError           # Operation timed out
└── NetworkError           # Connection failure
```

## License

MIT
