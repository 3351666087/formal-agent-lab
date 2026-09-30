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
from formal_lab_domain_broker import HmacVerifier, KeyStore, ReceiptStore, RequestBinding, admit
from formal_lab_domain_broker.receipt import digest_params

from .admission import mal_ruleset
from .config import LabPolicy, TargetSecurity
from .frontend import attack_graph_of

DESCRIPTOR = PluginDescriptor(
    plugin_id="formal-lab.domain.mal.broker-gate", version="1.0.0", interface="EXECUTION_GATE",
    interface_version="2", semantic_profiles=["deterministic_finite_v1"],
    capabilities=[{"id": caps.GATE_PRE_EXECUTION}],
    config_schema={"type": "object", "additionalProperties": True, "properties": {
        "receipts_path": {"type": "string"}, "keystore_path": {"type": "string"},
        "role_allowed_actions": {"type": "array"}, "service_identity": {"type": "string"},
        "lab_policy": {"type": "object"}, "target_security": {"type": "object"}}},
    entrypoint="formal_lab_domain_mal.gate:create_mal_broker_gate",
    ui={"label": "MAL 准入 Broker", "category": "gate",
        "description": "admits a compromise action only against a valid VerificationReceipt bound to the current "
                       "state and the MAL domain rules; rejection has zero side effects"},
    license="Apache-2.0", source="formal-lab-domain-mal")


class MalBrokerGate:
    descriptor = DESCRIPTOR

    def __init__(self, *, store: ReceiptStore, verifier: HmacVerifier, id_to_full: dict[str, str],
                 lab_policy: LabPolicy, target_security: TargetSecurity, role_allowed_actions: list[str],
                 service_identity: str | None = None, ruleset_version: int = 1):
        self._store = store
        self._verifier = verifier
        self._rules = mal_ruleset(version=ruleset_version)
        self._id_to_full = id_to_full
        self._lab = lab_policy
        self._tgt = target_security
        self._roles = role_allowed_actions
        self._service = service_identity

    def paths(self, action):
        return []

    def decide(self, request):
        from formal_lab_contracts import ConditionCheck, GateResult

        receipt = self._store.get(request.request_digest)
        revision = request.values_revision if request.values_source == "FRESH" else request.based_on_revision
        binding = RequestBinding(
            run_id=request.run_id, step=request.step, actor_id=request.actor_id or "",
            operation_id=request.operation_id, action_type=request.action.action_type,
            action_params_digest=digest_params(request.action.params),
            current_revision=revision if revision is not None else -1, service_identity=self._service)
        ctx = {"lab_policy": self._lab, "target_security": self._tgt, "action_params": request.action.params,
               "id_to_full": self._id_to_full}
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
                         service_identity=cfg.get("service_identity"))
