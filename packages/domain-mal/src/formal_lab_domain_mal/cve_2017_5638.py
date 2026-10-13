"""A complex, multi-stage attack/defence model grounded in a real CVE and a real breach: Apache Struts
CVE-2017-5638 (Jakarta Multipart parser OGNL injection → RCE, CVSS 10.0, no auth; github.com/apache/struts, fixed in
2.3.32 / 2.5.10.1) as the initial access of the 2017 Equifax breach, and the published post-exploitation chain that
followed — internal reconnaissance, credential access, lateral movement, database access and exfiltration of ~143M
records, undetected for weeks.

Each stage has alternative techniques (branches); each technique is blocked by one or more defensive controls (the
real Equifax failures, as controls: patch Struts, a WAF, credential vaulting, network segmentation, egress
inspection, …). This is both:
  * a formal attack/defence model — the Z3 verifier decides whether exfiltration is reachable under a deployed set of
    controls, and the minimum controls that stop it (`equifax_model`), and
  * the board for a live red-blue game (`GAME_SPEC`) in which two models plan attacker vs defender in real time.

Abstract defensive modelling: the techniques are named stages, not operational instructions.
"""

from __future__ import annotations

from typing import Any

from formal_lab_model.samples import ap, assign, c, v

from .attack_model import AttackModel

REPO = "github.com/apache/struts"
CVE = "CVE-2017-5638"

# ordered breach stages. Each: (stage_var, requires_prev_var_or_None, [(technique, frozenset(blocking_controls)), …]).
# A stage is crossed when any one of its techniques runs; a technique runs only if none of its blockers is deployed.
GAME_SPEC: list[tuple[str, str | None, list[tuple[str, frozenset[str]]]]] = [
    ("foothold", None, [
        ("exploit_struts_cve_2017_5638", frozenset({"patch_struts", "waf"})),
        ("spearphish_employee", frozenset({"email_filtering", "security_awareness"})),
    ]),
    ("recon", "foothold", [
        ("internal_reconnaissance", frozenset()),  # passive discovery — not blockable
    ]),
    ("creds", "recon", [
        ("steal_config_credentials", frozenset({"credential_vaulting"})),
        ("dump_process_memory", frozenset({"edr"})),
    ]),
    ("lateral", "creds", [
        ("smb_lateral_movement", frozenset({"network_segmentation"})),
        ("vpn_pivot", frozenset({"vpn_mfa"})),
    ]),
    ("db_access", "lateral", [
        ("query_pii_database", frozenset({"db_access_control"})),
        ("read_database_replica", frozenset({"replica_isolation"})),
    ]),
    ("exfiltrated", "db_access", [
        ("exfiltrate_over_dns", frozenset({"dns_monitoring"})),
        ("exfiltrate_over_https", frozenset({"proxy_tls_inspection"})),
    ]),
]
GOAL = "exfiltrated"
STAGE_VARS = [s for s, _, _ in GAME_SPEC]


def all_controls() -> list[str]:
    return sorted({ctrl for _, _, branches in GAME_SPEC for _, blockers in branches for ctrl in blockers})


def all_techniques() -> list[tuple[str, str, frozenset[str]]]:
    """(technique, stage_var, blockers) for every branch."""
    return [(t, stage, blk) for stage, _, branches in GAME_SPEC for t, blk in branches]


def equifax_model(*, deployed: frozenset[str] = frozenset(), name: str = CVE.lower() + "-equifax") -> AttackModel:
    """The Z3 model for a fixed set of deployed controls: is exfiltration reachable? Defences are constants."""
    bad = deployed - set(all_controls())
    if bad:
        raise ValueError(f"unknown controls {sorted(bad)}; known: {all_controls()}")
    constants = [{"name": ctl, "type": {"kind": "bool"}, "value": {"default": ctl in deployed}}
                 for ctl in all_controls()]
    state = [{"name": s, "type": {"kind": "bool"}, "initial": {"default": False}, "label": s} for s in STAGE_VARS]

    actions: list[dict[str, Any]] = []
    tech: list[str] = []
    for stage, prev, branches in GAME_SPEC:
        for t, blockers in branches:
            pre_terms = [] if prev is None else [v(prev)]
            pre_terms += [ap("not", v(b)) for b in sorted(blockers)]
            pre = pre_terms[0] if len(pre_terms) == 1 else ap("and", *pre_terms) if pre_terms else c(True)
            a: dict[str, Any] = {"name": t, "cost": 1, "effects": [assign(stage, c(True))]}
            if pre_terms:
                a["precondition"] = pre
            actions.append(a)
            tech.append(t)

    ir_dict = {
        "name": name,
        "description": f"Multi-stage attack/defence model grounded in {CVE} (Apache Struts, {REPO}) and the 2017 "
                       "Equifax breach: Struts RCE → recon → credential access → lateral movement → database access → "
                       "exfiltration. Controls block techniques; the goal is exfiltration of the customer database.",
        "constants": constants, "state": state, "actions": actions,
        "properties": [{"id": "data_exfiltrated", "kind": "goal", "expr": v(GOAL),
                        "label": "客户数据库被外泄（≈1.43 亿条）"},
                       {"id": "breach_prevented", "kind": "invariant", "expr": ap("not", v(GOAL)),
                        "label": "泄露被阻止"}],
        "objectives": [{"id": "attack_cost", "label": "攻击步数", "unit": "stages",
                        "terms": [{"kind": "action_cost"}]}],
    }
    am = AttackModel(name=name, hosts=[], creds=[], defenses=deployed, ir_dict=ir_dict, techniques=tech)
    am.env = {"deployed": sorted(deployed)}  # type: ignore[attr-defined]
    return am
