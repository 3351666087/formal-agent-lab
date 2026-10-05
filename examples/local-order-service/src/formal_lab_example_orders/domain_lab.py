"""Security-domain layer on the running order service (phase 3B, D4).

The order service is an ordinary business service. This module adds a *security experiment* that runs beside the normal
business, without changing the business code:

  * `SecurityProbe.sample` reads the service independently (its state / metrics / health / operating conditions) and
    records what a defender watches — access, configuration, service state, business success rate, cost and recovery.
    It reads from the service itself, never from the attacker's view.
  * `gated_condition_change` performs the one *domain-privileged* action (changing operating conditions — reconfiguring
    the target) only through the D2 admission Broker: without a valid receipt bound to the current revision the Broker
    denies it and the service is never called, so a rejected privileged action has zero side effect on the service.

`orders_admission_ruleset` is the released rule set for this domain; `check_property_vs_model` compares the service's
observed admission of the privileged action with the model's prediction on a comparable state, recording whether they
are consistent, a model deviation, or undecidable (a service state the model does not represent).
"""

from __future__ import annotations

from typing import Any

import httpx
from formal_lab_domain_broker import RequestBinding, Rule, RuleSet, RuleStatus, admit, digest_params
from formal_lab_domain_broker.receipt import VerificationReceipt, Verifier

from .net import trust_env


def _get(endpoint: str, path: str) -> Any:
    url = f"{endpoint}{path}"
    return httpx.get(url, trust_env=trust_env(url), timeout=10).json()


def _post(endpoint: str, path: str, body: dict[str, Any]) -> httpx.Response:
    url = f"{endpoint}{path}"
    return httpx.post(url, json=body, trust_env=trust_env(url), timeout=15)


def orders_admission_ruleset(*, version: int = 1) -> RuleSet:
    """A privileged configuration change needs a receipt whose check basis authorises it, and the acting role must be
    permitted. Reviewed rules, released and frozen for execution."""
    rules = [
        Rule(rule_id="orders.receipt", on="side_effect_action", when=["receipt_present", "receipt_authorizes_action"],
             then="REQUIRE_RECEIPT", kind="action_precondition", status=RuleStatus.REVIEWED,
             source="领域动作合同：更改运行条件这类特权动作必须有验证凭据。",
             detail="a privileged configuration change needs an authorising receipt"),
        Rule(rule_id="orders.role", on="side_effect_action", when=["role_permits_action"], then="ADMIT",
             kind="role_rule", status=RuleStatus.REVIEWED, source="角色规则：只有运维角色可以更改运行条件。",
             detail="only the operator role may change operating conditions"),
    ]
    return RuleSet(ruleset_id="orders-admission", version=version, rules=rules, status=RuleStatus.DRAFT,
                   note="订单服务领域准入").released()


class SecurityProbe:
    """Independent business/security observation, taken from the service itself (P2-064 style)."""

    def __init__(self, endpoint: str, tenant: str):
        self.endpoint = endpoint
        self.tenant = tenant
        self._baseline_revision: int | None = None

    def sample(self, *, stats: dict[str, Any] | None = None, window: int = 6) -> dict[str, Any]:
        health = _get(self.endpoint, f"/t/{self.tenant}/health")
        state = _get(self.endpoint, f"/t/{self.tenant}/state")
        metrics = _get(self.endpoint, f"/t/{self.tenant}/metrics?window={window}")
        revision = state.get("revision", 0)
        if self._baseline_revision is None:
            self._baseline_revision = revision
        props = state.get("properties", {})
        done = sum(1 for k, v in props.items() if k.startswith("done[") and v)
        total = sum(1 for k in props if k.startswith("done["))
        return {
            "access": {"operations": state.get("operations", 0), "endpoint": self.endpoint, "tenant": self.tenant},
            "config": _get(self.endpoint, f"/t/{self.tenant}/admin/conditions"),  # read-only, from the service
            "metrics": metrics,  # the service's own business metrics over the last `window` ticks
            "service_state": {"health": health.get("status"), "revision": revision, "clock": state.get("clock")},
            "success_rate": round(done / total, 3) if total else None,
            "cost": stats or {},
            "recovery": {"baseline_revision": self._baseline_revision, "current_revision": revision,
                         "reset_to_baseline": revision == self._baseline_revision},
        }


def gated_condition_change(endpoint: str, tenant: str, conditions: dict[str, Any], *,
                          receipt: VerificationReceipt | None, verifier: Verifier, ruleset: RuleSet,
                          current_revision: int, role_allowed_actions: list[str], actor_id: str = "operator",
                          operation_id: str = "cfg", step: int = 0) -> dict[str, Any]:
    """Change operating conditions only if the Broker admits it. A DENY never reaches the service."""
    params = {"conditions": conditions}
    binding = RequestBinding(run_id=tenant, step=step, actor_id=actor_id, operation_id=operation_id,
                             action_type="set_conditions", action_params_digest=digest_params(params),
                             current_revision=current_revision, service_identity="order-service")
    decision = admit(receipt, binding, verifier=verifier, rules=ruleset,
                     role_allowed_actions=role_allowed_actions)
    if not decision.allowed:
        return {"admitted": False, "applied": False, "verdict": decision.verdict,
                "reasons": [f"{r.kind}={r.holds}" for r in decision.reasons],
                "failed": [r.detail for r in decision.reasons if r.holds is not True]}
    resp = _post(endpoint, f"/t/{tenant}/admin/conditions", conditions)
    return {"admitted": True, "applied": resp.status_code == 200, "verdict": "ALLOW",
            "service_conditions": resp.json() if resp.status_code == 200 else None}


def check_property_vs_model(*, service_denied_without_receipt: bool, model_blocks_unauthorized: bool,
                            comparable: bool) -> dict[str, Any]:
    """Compare the security property on the service with the model's prediction on a comparable state."""
    if not comparable:
        return {"result": "UNDECIDABLE", "detail": "the service state has no comparable model state (out of scope)"}
    if service_denied_without_receipt == model_blocks_unauthorized:
        return {"result": "CONSISTENT", "service": service_denied_without_receipt,
                "model": model_blocks_unauthorized,
                "detail": "the service and the model agree the unauthorized action is prevented"}
    return {"result": "MODEL_DEVIATION", "service": service_denied_without_receipt,
            "model": model_blocks_unauthorized, "detail": "the service and the model disagree on a comparable state"}
