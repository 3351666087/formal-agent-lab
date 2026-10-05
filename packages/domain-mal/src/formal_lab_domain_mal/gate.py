"""MAL admission gate (phase 3B, D2): the generic Broker wired with the MAL rule set and domain context.

The generic `BrokerGate` verifies a receipt's signature, bindings, state revision and expiry, and runs the released
rules. This gate adds the MAL domain context those rules need — the scenario's LabPolicy and TargetSecurity, the map
from IR step id back to the MAL full name, and the action's parameters — so `lab_policy` and `target_security` are
evaluated for the actual step. Registered as an `EXECUTION_GATE` plugin, so it runs on the coordinator's real send path
(local runner, Temporal, re-send, pure-data re-execution) and a DENY is never sent — rejection has zero side effects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from formal_lab_contracts import PluginDescriptor
from formal_lab_contracts import capabilities as caps
from formal_lab_domain_broker import (
    HmacVerifier,
    KeyStore,
    ReceiptStore,
    RequestBinding,
    admit,
    admit_execution,
)
from formal_lab_domain_broker.receipt import digest_params

from .admission import mal_ruleset, target_check_basis
from .config import LabPolicy, TargetSecurity
from .frontend import attack_graph_of

_POSITIVE = ("WITNESS", "OPTIMAL", "HOLDS")

DESCRIPTOR = PluginDescriptor(
    plugin_id="formal-lab.domain.mal.broker-gate", version="1.0.0", interface="EXECUTION_GATE",
    interface_version="2", semantic_profiles=["deterministic_finite_v1"],
    capabilities=[{"id": caps.GATE_PRE_EXECUTION}],
    config_schema={"type": "object", "additionalProperties": True, "properties": {
        "receipts_path": {"type": "string"}, "keystore_path": {"type": "string"},
        "role_allowed_actions": {"type": "array"}, "service_identity": {"type": "string"},
        "lab_policy": {"type": "object"}, "target_security": {"type": "object"},
        "governed_action_types": {"type": "array", "items": {"type": "string"}, "default": ["compromise"]}}},
    entrypoint="formal_lab_domain_mal.gate:create_mal_broker_gate",
    ui={"label": "MAL 准入 Broker", "category": "gate",
        "description": "admits a compromise action only against a valid VerificationReceipt bound to the current "
                       "state and the MAL domain rules; rejection has zero side effects"},
    license="Apache-2.0", source="formal-lab-domain-mal")


class MalBrokerGate:
    descriptor = DESCRIPTOR

    def __init__(self, *, store: ReceiptStore, verifier: HmacVerifier, id_to_full: dict[str, str],
                 lab_policy: LabPolicy, target_security: TargetSecurity, role_allowed_actions: list[str],
                 service_identity: str | None = None, ruleset_version: int = 1,
                 governed_action_types: list[str] | None = None):
        self._store = store
        self._verifier = verifier
        self._rules = mal_ruleset(version=ruleset_version)
        self._id_to_full = id_to_full
        self._lab = lab_policy
        self._tgt = target_security
        self._roles = role_allowed_actions
        self._service = service_identity
        self._governed = list(governed_action_types or ["compromise"])

    def paths(self, action):
        return []

    def decide(self, request):
        from formal_lab_contracts import ConditionCheck, GateResult

        if request.action.action_type not in self._governed:
            return _outside_scope(request.action.action_type, self._governed)
        receipt = self._store.get(request.request_digest)
        revision = request.values_revision if request.values_source == "FRESH" else request.based_on_revision
        binding = RequestBinding(
            run_id=request.run_id, step=request.step, actor_id=request.actor_id or "",
            operation_id=request.operation_id, action_type=request.action.action_type,
            action_params_digest=digest_params(request.action.params),
            current_revision=revision if revision is not None else -1, service_identity=self._service)
        ctx = {"lab_policy": self._lab, "target_security": self._tgt, "action_params": request.action.params,
               "id_to_full": self._id_to_full}
        if getattr(request, "execution", None) is not None:  # phase 4A: verify against the kernel's basis
            decision = admit_execution(receipt, request.execution, verifier=self._verifier, rules=self._rules,
                                       role_allowed_actions=self._roles, context=ctx)
        else:
            decision = admit(receipt, binding, verifier=self._verifier, rules=self._rules,
                             role_allowed_actions=self._roles, context=ctx)
        conditions = [ConditionCheck(name=r.kind, holds=r.holds, detail=r.detail[:200]) for r in decision.reasons]
        if decision.allowed:
            return GateResult(verdict="ALLOW", reason="receipt verified: bindings, state revision, expiry and MAL "
                              "domain rules (LabPolicy / precondition / role / TargetSecurity) all hold",
                              conditions=conditions)
        failed = "; ".join(r.detail for r in decision.reasons if r.holds is not True) or "receipt missing"
        return GateResult(verdict="DENY", reason=failed[:400], conditions=conditions)


def create_mal_broker_gate(config: dict[str, Any] | None, services: Any) -> MalBrokerGate:
    cfg = config or {}
    store = ReceiptStore(cfg.get("receipts_path"))
    keys = KeyStore()
    kp = cfg.get("keystore_path")
    if kp and Path(kp).exists():
        for kid, hexsecret in json.loads(Path(kp).read_text()).items():
            keys.add(kid, bytes.fromhex(hexsecret))
    pkg = services.pinned_model()
    id_map = attack_graph_of(pkg)["lowering"]["id_map"]
    id_to_full = {v: k for k, v in id_map.items()}
    lab = LabPolicy.from_dict(cfg.get("lab_policy", {}))
    tgt = TargetSecurity.from_dict(cfg["target_security"])
    return MalBrokerGate(store=store, verifier=HmacVerifier(keys), id_to_full=id_to_full, lab_policy=lab,
                         target_security=tgt, role_allowed_actions=cfg.get("role_allowed_actions", ["compromise"]),
                         service_identity=cfg.get("service_identity"),
                         governed_action_types=cfg.get("governed_action_types"))


def _outside_scope(action_type: str, governed: list[str]):
    """An action type this gate does not govern (phase 4B, B3) — e.g. the defender's `harden` in a red/blue game: the
    admission Broker governs side-effect steps against the target (`compromise`), not the defender's own configuration
    changes. The pass-through is explicit and recorded (condition GOVERNED_ACTION = false), never silent."""
    from formal_lab_contracts import ConditionCheck, GateResult

    return GateResult(verdict="ALLOW", reason=f"{action_type} is outside this gate's admission scope (governs "
                      f"{', '.join(governed)}); passed on unchanged",
                      conditions=[ConditionCheck(name="GOVERNED_ACTION", holds=False,
                                                 detail=f"{action_type} not in {governed}")])


# --------------------------------------------------------------------------- per-action issuer (phase 4B, B1)

ISSUER_DESCRIPTOR = PluginDescriptor(
    plugin_id="formal-lab.domain.mal.receipt-issuer", version="1.0.0", interface="EXECUTION_GATE",
    interface_version="2", semantic_profiles=["deterministic_finite_v1"],
    capabilities=[{"id": caps.GATE_PRE_EXECUTION}],
    config_schema={"type": "object", "additionalProperties": True, "required": ["keystore_path", "target_security"],
                   "properties": {"keystore_path": {"type": "string"}, "key_id": {"type": "string"},
                                  "receipts_path": {"type": "string"}, "target_security": {"type": "object"},
                                  "ttl_seconds": {"type": "integer"}, "bound": {"type": "object"},
                                  "governed_action_types": {"type": "array", "items": {"type": "string"},
                                                            "default": ["compromise"]}}},
    entrypoint="formal_lab_domain_mal.gate:create_mal_issuer",
    ui={"label": "MAL 凭据签发（逐动作检查）", "category": "gate",
        "description": "issues a receipt only after checking, at send time against the current state, that this "
                       "compromise step is applicable now, and that the target is reachable in the model (Z3); no "
                       "applicable action or no current revision → DENY, no receipt"},
    license="Apache-2.0", source="formal-lab-domain-mal")


class MalReceiptIssuer:
    """Issues a receipt only after a real check at send time (phase 4B, B1): the action's precondition is evaluated on
    the current state (the per-send, per-revision check a pre-signed path cannot give), and the target property is
    confirmed reachable in the model by the Z3 bounded verifier (checked once — a model property, constant across the
    run). No applicable action, no authoritative current revision, or an unreachable target ⇒ DENY and no receipt, so
    the broker gate that follows has nothing to admit and the side effect never happens."""

    descriptor = ISSUER_DESCRIPTOR

    def __init__(self, *, loaded: Any, package: Any, signer: Any, store: Any, target: TargetSecurity,
                 bound: dict[str, Any], id_to_full: dict[str, str], ttl_seconds: int = 300,
                 governed_action_types: list[str] | None = None):
        self.loaded = loaded
        self.governed = list(governed_action_types or ["compromise"])
        self.package = package
        self.signer = signer
        self.store = store
        self.target = target
        self.bound = bound
        self.id_to_full = id_to_full
        self.ttl = ttl_seconds
        self._initial = loaded.initial_state()
        self._state_paths = [p for p in loaded.state_paths() if p.startswith(("compromised[", "hardened["))]
        self._reach: str | None = None

    def paths(self, action: Any) -> list[str]:
        # the kernel reads these fresh before the send, so the precondition is checked against the current state
        return list(self._state_paths)

    def _target_reachable(self) -> str:
        if self._reach is None:
            from formal_lab_contracts import CheckQuery
            from formal_lab_solver_z3.verifier import Z3Verifier

            q = CheckQuery(kind="GOAL_REACHABILITY", property_id="target_reached", bound=self.bound)
            self._reach = Z3Verifier().check(self.package, q).verdict
        return self._reach

    def _name(self, action: Any) -> str:
        n = str(action.params.get("n"))
        return self.id_to_full.get(n, n)

    def decide(self, request: Any):
        from formal_lab_contracts import GateResult
        from formal_lab_domain_broker.receipt import issue_for_context

        if request.action.action_type not in self.governed:
            return _outside_scope(request.action.action_type, self.governed)
        execution = getattr(request, "execution", None)
        if execution is None or execution.current_revision is None:
            return GateResult(verdict="DENY", reason="cannot issue a receipt: no authoritative current revision "
                              f"({getattr(execution, 'revision_note', None)})")
        if request.action.action_type != "compromise":
            return GateResult(verdict="DENY", reason=f"not a compromise action: {request.action.action_type}")
        step = self._name(request.action)
        rev = execution.current_revision
        # the current state: the model's constants / initial state with the locations the kernel just read fresh
        state = {**self._initial, **request.values}
        pred = self.loaded.predict(state, request.action)
        if not pred.applicable:
            return GateResult(verdict="DENY", reason=f"ACTION_PRECONDITION_FAILED at revision {rev}: "
                              f"compromise({step}) is not applicable in the current state ({pred.reason}); no receipt")
        verdict = self._target_reachable()
        if verdict not in _POSITIVE:
            return GateResult(verdict="DENY", reason=f"the target {self.target.property_id} is not reachable in the "
                              f"model (Z3 {verdict}); no receipt")
        basis = target_check_basis(property_id=self.target.property_id, verdict=verdict, scope="MODEL_INTERNAL",
                                   backend="formal-lab.verifier.z3-bmc@1.1.0", bound=self.bound)
        receipt = issue_for_context(
            execution, check_basis=basis,
            guarantee_scope=f"bounded reachability of {self.target.property_id}; compromise({step}) verified "
                            f"applicable at revision {rev}",
            signer=self.signer, ttl_seconds=self.ttl)
        self.store.put(request.request_digest, receipt)
        return GateResult(verdict="ALLOW", reason=f"receipt {receipt.receipt_id}: compromise({step}) applicable at "
                          f"revision {rev}, target reachable (Z3 {verdict})")


def create_mal_issuer(config: dict[str, Any] | None, services: Any) -> MalReceiptIssuer:
    from formal_lab_domain_broker import HmacSigner, KeyStore, ReceiptStore

    cfg = config or {}
    secrets = json.loads(Path(cfg["keystore_path"]).read_text())
    keys = KeyStore({kid: bytes.fromhex(h) for kid, h in secrets.items()})
    key_id = cfg.get("key_id") or next(iter(secrets))
    pkg = services.pinned_model()
    id_to_full = {v: k for k, v in attack_graph_of(pkg)["lowering"]["id_map"].items()}
    return MalReceiptIssuer(loaded=services.loaded_model(), package=pkg, signer=HmacSigner(keys, key_id),
                            store=ReceiptStore(cfg.get("receipts_path")),
                            target=TargetSecurity.from_dict(cfg["target_security"]),
                            bound=cfg.get("bound", {"max_steps": 60, "timeout_ms": 30000}), id_to_full=id_to_full,
                            ttl_seconds=int(cfg.get("ttl_seconds", 300)),
                            governed_action_types=cfg.get("governed_action_types"))
