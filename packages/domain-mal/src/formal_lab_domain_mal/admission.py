"""MAL domain admission (phase 3B, D2): the released rule set, the receipt issuer, and the LabPolicy / TargetSecurity
conditions that the generic Broker (formal_lab_domain_broker) evaluates for a coreLang attack step.

The Broker does the domain-independent work — signature, bindings, state revision, expiry. This module adds the MAL
domain's four separately-explained checks as typed rules over the Broker's context:

  * lab_policy        — the target step is inside the experiment's LabPolicy (allowed assets/steps, not forbidden);
  * action_precondition — a receipt is present and its check basis authorises the step;
  * role_rule         — the acting role may perform `compromise`;
  * target_security   — the receipt's check basis is about this scenario's TargetSecurity property with a real verdict.

The issuer runs the Z3 bounded check for the target and signs a receipt bound to one intended `compromise` action, its
parameters, and the state revision it was checked against. Reusing the platform's Z3 verifier keeps the guarantee equal
to what was actually checked (D2: 数学保证来自实际检查范围).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from formal_lab_domain_broker import (
    CheckBasis,
    ReceiptBindings,
    Rule,
    RuleSet,
    RuleStatus,
    VerificationReceipt,
    condition,
    digest_params,
    sign_receipt,
)
from formal_lab_domain_broker.receipt import Signer

from .config import BusinessSLO, LabPolicy, TargetSecurity  # noqa: F401  (re-exported context types)

_POSITIVE = ("WITNESS", "OPTIMAL", "HOLDS")


@condition("lab_policy_permits")
def _lab_policy_permits(ctx: dict[str, Any]) -> bool | None:
    lab: LabPolicy | None = ctx.get("lab_policy")
    params = ctx.get("action_params")
    if lab is None or params is None:
        return None
    full = ctx.get("id_to_full", {}).get(params.get("n"), params.get("n"))
    if not isinstance(full, str):
        return None
    return lab.permits(full, full.split(":")[0])


@condition("target_security_covered")
def _target_security_covered(ctx: dict[str, Any]) -> bool | None:
    receipt: VerificationReceipt | None = ctx.get("receipt")
    tgt: TargetSecurity | None = ctx.get("target_security")
    if receipt is None or tgt is None:
        return None
    basis = receipt.check_basis
    return basis.property_id == tgt.property_id and basis.verdict in _POSITIVE


def mal_ruleset(*, version: int = 1) -> RuleSet:
    """The MAL domain rule set. Written REVIEWED (each rule keeps the natural-language requirement it came from) and
    returned RELEASED, frozen with a content digest — only a released set is consulted at execution time."""
    rules = [
        Rule(rule_id="mal.lab-policy", on="side_effect_action", when=["lab_policy_permits"], then="ADMIT",
             kind="lab_policy", status=RuleStatus.REVIEWED,
             source="实验边界：红方只能触碰 LabPolicy 允许的资产/步骤，未被禁止，且在预算内。",
             detail="target step is within the experiment's LabPolicy"),
        Rule(rule_id="mal.receipt", on="side_effect_action", when=["receipt_present", "receipt_authorizes_action"],
             then="REQUIRE_RECEIPT", kind="action_precondition", status=RuleStatus.REVIEWED,
             source="动作前提：每个副作用动作都要有一份检查基础可授权该动作的验证凭据。",
             detail="a receipt whose check basis authorises this action must be present"),
        Rule(rule_id="mal.role", on="side_effect_action", when=["role_permits_action"], then="ADMIT",
             kind="role_rule", status=RuleStatus.REVIEWED,
             source="角色规则：只有攻击者角色可以执行 compromise 动作。",
             detail="the acting role may perform compromise"),
        Rule(rule_id="mal.target-security", on="side_effect_action", when=["target_security_covered"], then="ADMIT",
             kind="target_security", status=RuleStatus.REVIEWED,
             source="目标性质：凭据的检查基础必须针对本场景的 TargetSecurity 性质并给出真实判定。",
             detail="the receipt's check basis is about this scenario's TargetSecurity property"),
    ]
    return RuleSet(ruleset_id="mal-admission", version=version, rules=rules, status=RuleStatus.DRAFT,
                   note="coreLang 攻击步骤准入").released()


def target_check_basis(*, property_id: str, verdict: str, scope: str, backend: str, bound: dict[str, Any]) -> CheckBasis:
    return CheckBasis(query_kind="GOAL_REACHABILITY", property_id=property_id, verdict=verdict, scope=scope,
                      backend=backend, bound=bound)


def issue_receipt(*, run_id: str, step: int, actor_id: str, operation_id: str, action_params: dict[str, Any],
                  state_revision: int, check_basis: CheckBasis, guarantee_scope: str, signer: Signer,
                  session_id: str | None = None, environment: str | None = None, service_identity: str | None = None,
                  versions: dict[str, str] | None = None, ttl_seconds: int = 300,
                  now: datetime | None = None) -> VerificationReceipt:
    """Issue and sign a receipt for one intended `compromise` action."""
    now = now or datetime.now(UTC)
    receipt = VerificationReceipt(
        receipt_id=f"rcpt_{uuid.uuid4().hex[:16]}",
        bindings=ReceiptBindings(
            run_id=run_id, step=step, actor_id=actor_id, operation_id=operation_id, action_type="compromise",
            action_params_digest=digest_params(action_params), state_revision=state_revision, session_id=session_id,
            environment=environment, service_identity=service_identity, versions=versions or {}),
        check_basis=check_basis, guarantee_scope=guarantee_scope,
        issued_at=now.isoformat(), expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
        issuer=signer.key_id)
    return sign_receipt(receipt, signer)
