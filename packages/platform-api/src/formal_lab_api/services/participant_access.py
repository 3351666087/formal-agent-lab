"""Participant access (phase 4A, A2): a participant's read channel is bound to a server-issued identity.

The operator (the local single-user API) issues a token for one run and one actor; the participant endpoints take
the identity from that token, never from a request parameter — an `actor` parameter only narrows within the token's
scope and is refused when it names another actor. Tokens are HMAC-SHA256 signed with a key that lives only on the
server side (`FAL_PARTICIPANT_TOKEN_KEY`, else a 0600 key file next to the artifact store). They grant reading the
participant's projected replay bundle and nothing else: environment write credentials are never part of this channel.
Multi-user sign-in (SSO) stays in the later deployment scope.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from ..settings import get_settings


class AccessDenied(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


def _key() -> bytes:
    env = os.environ.get("FAL_PARTICIPANT_TOKEN_KEY")
    if env:
        return env.encode()
    path = Path(get_settings().artifact_root).resolve().parent / "participant-access.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(os.urandom(32))
        path.chmod(0o600)
    return path.read_bytes()


def _sign(body: bytes) -> str:
    return hmac.new(_key(), body, hashlib.sha256).hexdigest()


def issue(run_id: str, actor_id: str, ttl_s: int = 3600) -> dict[str, str]:
    exp = int(time.time()) + int(ttl_s)
    body = f"{run_id}\n{actor_id}\n{exp}".encode()
    token = base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + _sign(body)
    return {"token": token, "run_id": run_id, "actor_id": actor_id,
            "expires_at": datetime.fromtimestamp(exp, UTC).isoformat(), "scope": "participant:read"}


def resolve(authorization: str | None) -> tuple[str, str]:
    """(run_id, actor_id) of a valid participant token in an `Authorization: Bearer …` header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AccessDenied(401, "PARTICIPANT_TOKEN_REQUIRED: send Authorization: Bearer <participant token>")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        encoded, sig = token.split(".", 1)
        body = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        run_id, actor_id, exp = body.decode().split("\n")
    except (ValueError, UnicodeDecodeError) as exc:
        raise AccessDenied(401, "PARTICIPANT_TOKEN_MALFORMED") from exc
    if not hmac.compare_digest(sig, _sign(body)):
        raise AccessDenied(401, "PARTICIPANT_TOKEN_INVALID: signature does not verify")
    if int(exp) < time.time():
        raise AccessDenied(401, "PARTICIPANT_TOKEN_EXPIRED")
    return run_id, actor_id
