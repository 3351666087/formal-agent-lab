"""The admission Broker (phase 3B, D2).

The Broker decides whether a side-effect action may be sent. It admits an action only when a `VerificationReceipt`:
  * is authentic (signature verifies — provenance + integrity), and
  * binds to *this* request (run / step / actor / operation / action-parameter digest / session / service identity), and
  * was made against the *current* world (its `state_revision` equals the live revision — an old revision is refused), and
  * has not expired, and
  * carries a check basis that actually authorises the action, and
  * passes the RELEASED domain rules (LabPolicy, action preconditions, role rules, TargetSecurity), each explained on its own.

Any failure yields DENY. When the Broker runs as an `ExecutionGate` (below), a DENY means the coordinator never sends the
action — so rejection has **zero side effects** (that guarantee is G2's; the Broker rides on it). The Broker never grants
more than the receipt's `check_basis` / `guarantee_scope`: a signature over a weak or absent check does not become strong,
and a model's RELEASED label is not admission on its own — there must be a receipt bound to this request and state.

`admit()` is pure and unit-testable; `BrokerGate` is the platform adapter; `ReceiptStore` carries receipts from the
issuer (which ran the check) to the gate (which verifies), keyed by the coordinator's `request_digest`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .receipt import VerificationReceipt, Verifier, signature_ok
from .rules import Handling, RuleSet, condition, evaluate

# ------------------------------------------------------------------ generic conditions (domains add their own)


@condition("receipt_present")
def _receipt_present(ctx: dict[str, Any]) -> bool:
    return ctx.get("receipt") is not None


@condition("receipt_authorizes_action")
def _authorizes(ctx: dict[str, Any]) -> bool | None:
    """The receipt's check basis is a positive verdict for a query about this action / its target."""
    r = ctx.get("receipt")
    if r is None:
        return None
    return r.check_basis.verdict in ("WITNESS", "OPTIMAL", "HOLDS", "NO_WITNESS_WITHIN_BOUND") and \
        bool(r.guarantee_scope)


@condition("role_permits_action")
def _role_permits(ctx: dict[str, Any]) -> bool | None:
    allowed = ctx.get("role_allowed_actions")
    if allowed is None:
        return None
    return ctx.get("action_type") in allowed


@dataclass(frozen=True)
class Reason:
    kind: str  # provenance | binding | state_revision | expiry | lab_policy | action_precondition | role_rule | target_security
    holds: bool | None
    detail: str


@dataclass(frozen=True)
class BrokerDecision:
    verdict: str  # ALLOW | DENY
    reasons: list[Reason]
    zero_side_effect: bool = True  # a DENY is never sent; kept for the record / evidence

    @property
    def allowed(self) -> bool:
        return self.verdict == "ALLOW"

    def by_kind(self, kind: str) -> list[Reason]:
        return [r for r in self.reasons if r.kind == kind]


@dataclass(frozen=True)
class RequestBinding:
    """The live request the receipt is checked against."""

    run_id: str
    step: int
    actor_id: str
    operation_id: str
    action_type: str
    action_params_digest: str
    current_revision: int
    session_id: str | None = None
    service_identity: str | None = None


def _binding_reasons(receipt: VerificationReceipt, req: RequestBinding) -> list[Reason]:
    b = receipt.bindings
    checks = [
        ("run_id", b.run_id, req.run_id), ("step", b.step, req.step), ("actor_id", b.actor_id, req.actor_id),
        ("operation_id", b.operation_id, req.operation_id), ("action_type", b.action_type, req.action_type),
        ("action_params_digest", b.action_params_digest, req.action_params_digest),
    ]
    if req.session_id is not None:
        checks.append(("session_id", b.session_id, req.session_id))
    if req.service_identity is not None:
        checks.append(("service_identity", b.service_identity, req.service_identity))
    reasons = []
    for name, got, want in checks:
        ok = got == want
        reasons.append(Reason("binding", ok,
                              f"{name}: receipt={got!r} request={want!r} {'match' if ok else 'MISMATCH'}"))
    return reasons


def admit(receipt: VerificationReceipt | None, req: RequestBinding, *, verifier: Verifier, rules: RuleSet,
          role_allowed_actions: list[str] | None = None, context: dict[str, Any] | None = None,
          now: datetime | None = None) -> BrokerDecision:
    """Decide admission. Pure: no I/O, no side effects. Returns a DENY with every failed reason, or ALLOW.
    `context` carries domain facts (e.g. a LabPolicy, the action parameters) that domain rule conditions read."""
    now = now or datetime.now(UTC)
    reasons: list[Reason] = []

    if receipt is None:
        reasons.append(Reason("binding", False, "no receipt bound to this request"))
        return BrokerDecision("DENY", reasons)

    # 1. provenance + integrity
    sig_ok = signature_ok(receipt, verifier)
    reasons.append(Reason("provenance", sig_ok,
                          f"signature by {receipt.issuer!r} {'verified' if sig_ok else 'INVALID'}"))

    # 2. bindings
    binding_reasons = _binding_reasons(receipt, req)
    reasons.extend(binding_reasons)

    # 3. freshness (current state revision)
    fresh = receipt.bindings.state_revision == req.current_revision
    reasons.append(Reason("state_revision", fresh,
                          f"receipt at revision {receipt.bindings.state_revision}, current {req.current_revision}"
                          f"{'' if fresh else ' (stale — re-check against current state)'}"))

    # 4. expiry
    live = not receipt.is_expired(now=now)
    reasons.append(Reason("expiry", live, f"expires_at {receipt.expires_at}" + ("" if live else " (EXPIRED)")))

    # 5. domain rules (LabPolicy / precondition / role / TargetSecurity), each explained on its own
    ctx = {"receipt": receipt, "action_type": req.action_type, "role_allowed_actions": role_allowed_actions,
           **(context or {})}
    for fired in evaluate(rules, "side_effect_action", ctx):
        detail = fired.detail
        if fired.unknown_conditions:
            detail += f" (undetermined: {', '.join(fired.unknown_conditions)})"
        # Keep the three-valued outcome so an undetermined check (None) is distinguishable from a failed one (False):
        # both deny, but only None means "re-observe / re-plan". A DENY rule passes when its condition is definitely
        # False; every other handling is a positive requirement that passes when its condition is True.
        if fired.holds is None:
            holds: bool | None = None
        elif fired.handling == Handling.DENY:
            holds = fired.holds is False
        else:
            holds = fired.holds is True
        reasons.append(Reason(fired.kind, holds, f"[{fired.handling}] {detail}"))

    hard_ok = sig_ok and all(r.holds for r in binding_reasons) and fresh and live
    rule_ok = all(r.holds is True for r in reasons if r.kind in
                  ("lab_policy", "action_precondition", "role_rule", "target_security"))
    verdict = "ALLOW" if (hard_ok and rule_ok) else "DENY"
    return BrokerDecision(verdict, reasons)


# ------------------------------------------------------------------ receipt store (issuer → gate)


class ReceiptStore:
    """Carries receipts from the issuer (which ran the check) to the Broker gate, keyed by the coordinator's
    request_digest. In-memory by default; back it with a JSON file to cross process boundaries (local runner /
    Temporal worker / a separate issuer)."""

    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path else None
        self._mem: dict[str, dict[str, Any]] = {}
        if self._path and self._path.exists():
            self._mem = json.loads(self._path.read_text())

    def put(self, request_digest: str, receipt: VerificationReceipt) -> None:
        self._mem[request_digest] = receipt.to_dict()
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._mem, ensure_ascii=False, indent=1))

    def get(self, request_digest: str) -> VerificationReceipt | None:
        if self._path and self._path.exists():  # a separate issuer may have written since construction
            self._mem = json.loads(self._path.read_text())
        d = self._mem.get(request_digest)
        return VerificationReceipt.from_dict(d) if d else None


# ------------------------------------------------------------------ ExecutionGate adapter
# Imported lazily inside the class body's module use; declared here so the gate is discoverable as a plugin.


def _descriptor():
    from formal_lab_contracts import PluginDescriptor
    from formal_lab_contracts import capabilities as caps

    return PluginDescriptor(
        plugin_id="formal-lab.broker.receipt-gate", version="1.0.0", interface="EXECUTION_GATE",
        interface_version="2", semantic_profiles=["deterministic_finite_v1"],
        capabilities=[{"id": caps.GATE_PRE_EXECUTION}],
        config_schema={"type": "object", "additionalProperties": True, "properties": {
            "receipts_path": {"type": "string"}, "role_allowed_actions": {"type": "array"},
            "service_identity": {"type": "string"}}},
        entrypoint="formal_lab_domain_broker.broker:create_gate",
        ui={"label": "准入 Broker（验证凭据）", "category": "gate",
            "description": "admits a side-effect action only against a valid VerificationReceipt bound to the current "
                           "state; rejection has zero side effects"},
        license="Apache-2.0", source="formal-lab-domain-broker")


DESCRIPTOR = _descriptor()


class BrokerGate:
    """ExecutionGate that runs the Broker before every send (covers local runner, Temporal, re-send and pure-data
    re-execution — G2's real send extension point)."""

    descriptor = DESCRIPTOR

    def __init__(self, *, store: ReceiptStore, verifier: Verifier, rules: RuleSet,
                 role_allowed_actions: list[str] | None = None, service_identity: str | None = None):
        self.store = store
        self.verifier = verifier
        self.rules = rules
        self.role_allowed_actions = role_allowed_actions
        self.service_identity = service_identity

    def paths(self, action):  # the revision the Broker needs is carried on the request, so no state read is required
        return []

    def decide(self, request):
        from formal_lab_contracts import GateResult

        receipt = self.store.get(request.request_digest)
        revision = request.values_revision if request.values_source == "FRESH" else request.based_on_revision
        binding = RequestBinding(
            run_id=request.run_id, step=request.step, actor_id=request.actor_id or "",
            operation_id=request.operation_id, action_type=request.action.action_type,
            action_params_digest=_params_digest(request), current_revision=revision if revision is not None else -1,
            service_identity=self.service_identity)
        decision = admit(receipt, binding, verifier=self.verifier, rules=self.rules,
                         role_allowed_actions=self.role_allowed_actions)
        verdict = "ALLOW" if decision.allowed else "DENY"
        conditions = _conditions(decision)
        reason = "; ".join(r.detail for r in decision.reasons if r.holds is not True) or "receipt verified"
        return GateResult(verdict=verdict, reason=(reason if verdict == "DENY" else "receipt verified: bindings, "
                          "state revision, expiry and domain rules all hold"), conditions=conditions)


def _params_digest(request) -> str:
    from .receipt import digest_params

    return digest_params(request.action.params)


def _conditions(decision: BrokerDecision):
    from formal_lab_contracts import ConditionCheck

    return [ConditionCheck(name=r.kind, holds=r.holds, detail=r.detail) for r in decision.reasons]


def create_gate(config: dict[str, Any] | None, services: Any) -> BrokerGate:
    """Factory. Config: receipts_path, role_allowed_actions, service_identity, key material via the platform's
    secret store is out of scope for the local runner — the shared-secret keystore is provided by the domain wiring
    (see domain-mal). Here we read a keystore file path if given, else an empty verifier that fails closed."""
    from .receipt import HmacVerifier, KeyStore

    cfg = config or {}
    store = ReceiptStore(cfg.get("receipts_path"))
    keys = KeyStore()
    key_path = cfg.get("keystore_path")
    if key_path and Path(key_path).exists():
        for kid, hex_secret in json.loads(Path(key_path).read_text()).items():
            keys.add(kid, bytes.fromhex(hex_secret))
    rules = services.broker_rules() if hasattr(services, "broker_rules") else _empty_rules()
    return BrokerGate(store=store, verifier=HmacVerifier(keys), rules=rules,
                      role_allowed_actions=cfg.get("role_allowed_actions"),
                      service_identity=cfg.get("service_identity"))


def _empty_rules() -> RuleSet:
    return RuleSet(ruleset_id="empty", version=1, rules=[]).released()
