"""VerificationReceipt: a signed, canonically-serialised attestation that a specific action was checked (phase 3B, D2).

A receipt binds one intended side-effect action to *what was actually verified about it* and to the exact world it was
verified against: run / step / turn / actor, environment / session, `operation_id`, the digest of the action's
parameters, the state revision, the model / adapter / rules / projection versions, the check basis (which query and
verdict, at what scope), the guarantee scope, and an expiry. The Broker (see `broker.py`) admits an action only when a
receipt's bindings match the live request and current state.

The signature provides **provenance and integrity only** — it proves the receipt came from the issuer and was not
altered. The *mathematical* guarantee is exactly the `check_basis` / `scope` the receipt records; a signature over a
weak check does not make it strong, and a model's RELEASED label is not a substitute for a receipt (see the Broker).

Signing uses HMAC-SHA256 (stdlib `hmac`, a FIPS-198 keyed MAC) behind the `Signer` / `Verifier` protocols, so an
asymmetric backend (e.g. Ed25519) can replace it without touching callers. The signing key lives in a `KeyStore` that
is deliberately separate from any environment / service credentials (D2: 签发与环境凭据独立存储).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

RECEIPT_FORMAT = "formal-lab/verification-receipt@1"


def digest_params(params: dict[str, Any]) -> str:
    """Canonical sha256 of an action's parameters — delegates to the one contract definition (phase 4A) so issuer,
    broker and kernel can never disagree on it."""
    from formal_lab_contracts import params_digest

    return params_digest(params)


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


@dataclass(frozen=True)
class CheckBasis:
    """What was actually verified — the receipt's guarantee is exactly this, no more."""

    query_kind: str  # GOAL_REACHABILITY / INVARIANT_VIOLATION / ACTION_PRECONDITION / ...
    property_id: str | None
    verdict: str  # WITNESS / NO_WITNESS_WITHIN_BOUND / OPTIMAL / UNKNOWN / ...
    scope: str  # e.g. MODEL_INTERNAL
    backend: str  # verifier plugin id@version
    bound: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReceiptBindings:
    """The world the check was made against; the Broker checks every field against the live request / state."""

    run_id: str
    step: int
    actor_id: str
    operation_id: str
    action_type: str
    action_params_digest: str
    state_revision: int
    session_id: str | None = None
    environment: str | None = None
    turn: int | None = None
    service_identity: str | None = None
    versions: dict[str, str] = field(default_factory=dict)  # model / adapter / rules / projection
    # phase 4A: the kernel's canonical execution binding (formal_lab_contracts.execution_binding) and its digest —
    # issued from the authoritative ExecutionContext and verified against the live one with the same definition
    binding: dict[str, Any] | None = None
    binding_digest: str | None = None


def bindings_from_context(context: Any) -> ReceiptBindings:
    """The bindings of a receipt for one send, from the kernel's ExecutionContext (never from strategy strings)."""
    from formal_lab_contracts import execution_binding, execution_binding_digest

    b = execution_binding(context)
    return ReceiptBindings(
        run_id=b["run_id"], step=b["step"], actor_id=b["actor_id"], operation_id=b["operation_id"],
        action_type=b["action_type"], action_params_digest=b["action_params_digest"],
        state_revision=b["current_revision"] if b["current_revision"] is not None else -1,
        session_id=b["session_id"], environment=b["environment"], turn=(b["turn"] or {}).get("global_step"),
        service_identity=b["service_identity"], versions=b["versions"], binding=b,
        binding_digest=execution_binding_digest(context))


@dataclass(frozen=True)
class VerificationReceipt:
    receipt_id: str
    bindings: ReceiptBindings
    check_basis: CheckBasis
    guarantee_scope: str
    issued_at: str  # ISO-8601 UTC
    expires_at: str  # ISO-8601 UTC
    issuer: str  # key id
    signature: str = ""  # hex HMAC over the canonical body (everything but this field)
    format: str = RECEIPT_FORMAT

    def body(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("signature", None)
        return d

    def canonical(self) -> str:
        return _canon(self.body())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VerificationReceipt:
        return cls(bindings=ReceiptBindings(**d["bindings"]), check_basis=CheckBasis(**d["check_basis"]),
                   **{k: v for k, v in d.items() if k not in ("bindings", "check_basis")})

    def is_expired(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return now > datetime.fromisoformat(self.expires_at)


@runtime_checkable
class Signer(Protocol):
    key_id: str

    def sign(self, payload: str) -> str: ...


@runtime_checkable
class Verifier(Protocol):
    def verify(self, payload: str, signature: str, *, key_id: str) -> bool: ...


class KeyStore:
    """Signing keys, kept separate from environment / service credentials. In a real deployment the issuer holds the
    key and the Broker holds only what it needs to verify; with a shared-secret MAC that is the same secret, so this
    store is the single source and the two never read environment credentials from it."""

    def __init__(self, keys: dict[str, bytes] | None = None):
        self._keys = dict(keys or {})

    def add(self, key_id: str, secret: bytes) -> None:
        self._keys[key_id] = secret

    def secret(self, key_id: str) -> bytes:
        if key_id not in self._keys:
            raise KeyError(f"no signing key {key_id!r}")
        return self._keys[key_id]

    def has(self, key_id: str) -> bool:
        return key_id in self._keys


class HmacSigner:
    """HMAC-SHA256 signer (FIPS-198). Provenance + integrity only."""

    def __init__(self, store: KeyStore, key_id: str):
        self.key_id = key_id
        self._store = store

    def sign(self, payload: str) -> str:
        return hmac.new(self._store.secret(self.key_id), payload.encode(), hashlib.sha256).hexdigest()


class HmacVerifier:
    def __init__(self, store: KeyStore):
        self._store = store

    def verify(self, payload: str, signature: str, *, key_id: str) -> bool:
        if not self._store.has(key_id):
            return False
        expected = hmac.new(self._store.secret(key_id), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)  # constant-time


def sign_receipt(receipt: VerificationReceipt, signer: Signer) -> VerificationReceipt:
    from dataclasses import replace

    return replace(receipt, issuer=signer.key_id, signature=signer.sign(receipt.canonical()))


def signature_ok(receipt: VerificationReceipt, verifier: Verifier) -> bool:
    return bool(receipt.signature) and verifier.verify(receipt.canonical(), receipt.signature, key_id=receipt.issuer)


def issue_for_context(context: Any, *, check_basis: CheckBasis, guarantee_scope: str, signer: Signer,
                      ttl_seconds: int = 300, receipt_id: str | None = None,
                      now: datetime | None = None) -> VerificationReceipt:
    """Issue and sign a receipt bound to one send's authoritative ExecutionContext (phase 4A)."""
    import uuid
    from datetime import timedelta

    if context.current_revision is None:
        raise ValueError("cannot issue a receipt: the execution context has no current revision")
    now = now or datetime.now(UTC)
    receipt = VerificationReceipt(
        receipt_id=receipt_id or f"rcpt_{uuid.uuid4().hex[:16]}", bindings=bindings_from_context(context),
        check_basis=check_basis, guarantee_scope=guarantee_scope, issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(), issuer=signer.key_id)
    return sign_receipt(receipt, signer)
