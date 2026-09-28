"""HTTP to the order service: loopback traffic never goes through a proxy from the environment.

A system-wide HTTP_PROXY without NO_PROXY (Lima, for one, copies the host's proxy into the VM's /etc/environment)
would send requests for 127.0.0.1 to a proxy that cannot reach this machine's loopback: it answers 502 or the
connection times out, which the adapter would have to treat as a lost answer.
"""

from __future__ import annotations

import httpx


def is_loopback(url: str) -> bool:
    host = httpx.URL(url).host
    return host in ("localhost", "::1") or host.startswith("127.")


def trust_env(url: str) -> bool:
    """httpx `trust_env`: environment proxies only for non-loopback endpoints."""
    return not is_loopback(url)
