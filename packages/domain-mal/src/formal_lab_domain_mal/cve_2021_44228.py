"""A formal attack/defence model of a real vulnerability in a large, well-known project: Log4Shell —
CVE-2021-44228 in Apache Log4j 2 (github.com/apache/logging-log4j2). It models the published attack chain as
techniques over abstract security state, and the real fix / mitigations as constants that gate those techniques, so
the Z3 verifier decides whether remote code execution (the goal) is reachable in a given version and configuration.
It is an abstract model for defensive analysis — the states are named conditions, not an exploit.

The chain (CVE-2021-44228, as published by the Apache Log4j security page and the CVE record):
  attacker-controlled data is logged → if message-lookup substitution is on, a `${jndi:…}` string triggers a JNDI
  lookup → if JNDI is enabled and the app can reach the attacker endpoint, a malicious reference is returned → a
  remote class is loaded (via an LDAP reference when the JVM trusts a remote codebase, or via a deserialisation
  gadget on the classpath) → the class executes ⇒ RCE.

Versions (affected 2.0-beta9 … 2.14.1): 2.15.0 disabled message lookups by default (incomplete — CVE-2021-45046);
2.16.0 removed message-lookup patterns and disabled JNDI by default (the fix for the RCE); 2.17.x added further
hardening. Mitigations without upgrading: remove the JndiLookup class, set log4j2.formatMsgNoLookups=true, block
outbound LDAP/RMI, validate input.
"""

from __future__ import annotations

from typing import Any

from formal_lab_model.samples import ap, assign, c, v

from .attack_model import AttackModel

REPO = "github.com/apache/logging-log4j2"
CVE = "CVE-2021-44228"

# per-version defaults for the three Log4j-internal controls (message lookups / JNDI enabled / JndiLookup present)
VERSIONS: dict[str, dict[str, bool]] = {
    "2.14.1": {"message_lookups": True, "jndi_enabled": True, "jndi_class_present": True},   # vulnerable
    "2.15.0": {"message_lookups": False, "jndi_enabled": True, "jndi_class_present": True},  # partial (CVE-2021-45046)
    "2.16.0": {"message_lookups": False, "jndi_enabled": False, "jndi_class_present": True},  # RCE fixed
    "2.17.1": {"message_lookups": False, "jndi_enabled": False, "jndi_class_present": True},  # fixed + hardening
}
# operator mitigations that can be layered on top of any version, and the control each one flips
MITIGATIONS: dict[str, tuple[str, bool]] = {
    "formatMsgNoLookups": ("message_lookups", False),
    "disable_jndi": ("jndi_enabled", False),
    "remove_jndi_class": ("jndi_class_present", False),
    "block_egress": ("egress_allowed", False),
    "input_validation": ("input_sanitized", True),
    "remove_gadget": ("gadget_present", False),
    "trust_url_codebase_false": ("trust_url_codebase", False),
}


def log4shell_model(*, version: str = "2.14.1", mitigations: frozenset[str] = frozenset(),
                    egress_allowed: bool = True, input_sanitized: bool = False, trust_url_codebase: bool = False,
                    gadget_present: bool = True, name: str = "cve-2021-44228-log4shell") -> AttackModel:
    """Build the model for a Log4j `version` with optional operator `mitigations`. The environment defaults model a
    typical exposed service: it can reach the internet (egress), no input validation, a deserialisation gadget on the
    classpath (so RCE does not depend on the JVM trusting a remote codebase)."""
    if version not in VERSIONS:
        raise ValueError(f"unknown version {version!r}; known: {sorted(VERSIONS)}")
    env = {**VERSIONS[version], "egress_allowed": egress_allowed, "input_sanitized": input_sanitized,
           "trust_url_codebase": trust_url_codebase, "gadget_present": gadget_present}
    for mit in mitigations:
        if mit not in MITIGATIONS:
            raise ValueError(f"unknown mitigation {mit!r}; known: {sorted(MITIGATIONS)}")
        key, val = MITIGATIONS[mit]
        env[key] = val

    constants = [{"name": k, "type": {"kind": "bool"}, "value": {"default": bool(v_)}} for k, v_ in env.items()]
    steps = ["attacker_input_logged", "jndi_lookup_triggered", "attacker_endpoint_contacted",
             "malicious_reference_returned", "remote_class_loaded", "rce_achieved"]
    state = [{"name": s, "type": {"kind": "bool"}, "initial": {"default": False}, "label": s} for s in steps]

    actions: list[dict[str, Any]] = []
    tech: list[str] = []

    def act(nm: str, pre: dict[str, Any], *sets: str) -> None:
        actions.append({"name": nm, "cost": 1, "precondition": pre,
                        "effects": [assign(s, c(True)) for s in sets]})
        tech.append(nm)

    # 1. attacker gets a JNDI string into a logged field (header / username / user-agent), unless input is validated
    act("inject_jndi_string", ap("not", v("input_sanitized")), "attacker_input_logged")
    # 2. Log4j substitutes the lookup — needs message lookups on AND the JndiLookup class present
    act("trigger_jndi_lookup", ap("and", v("attacker_input_logged"), v("message_lookups"), v("jndi_class_present")),
        "jndi_lookup_triggered")
    # 3. the lookup resolves to the attacker endpoint — needs JNDI enabled AND the app can reach the endpoint
    act("resolve_to_attacker", ap("and", v("jndi_lookup_triggered"), v("jndi_enabled"), v("egress_allowed")),
        "attacker_endpoint_contacted")
    # 4. the attacker endpoint returns a malicious naming reference
    act("return_malicious_reference", v("attacker_endpoint_contacted"), "malicious_reference_returned")
    # 5a. load the remote class via an LDAP reference — only when the JVM trusts a remote codebase
    act("load_class_via_reference", ap("and", v("malicious_reference_returned"), v("trust_url_codebase")),
        "remote_class_loaded")
    # 5b. or via a deserialisation gadget already on the classpath (worked even with trustURLCodebase=false)
    act("load_class_via_gadget", ap("and", v("malicious_reference_returned"), v("gadget_present")),
        "remote_class_loaded")
    # 6. the loaded class executes
    act("execute_payload", v("remote_class_loaded"), "rce_achieved")

    ir_dict = {
        "name": name,
        "description": f"Formal attack/defence model of {CVE} (Log4Shell) in Apache Log4j 2 ({REPO}), version "
                       f"{version}. The goal rce_achieved is reachable only when the configuration leaves the chain "
                       "open; the fix / mitigations flip the constants that gate it.",
        "constants": constants, "state": state, "actions": actions,
        "properties": [{"id": "rce_achieved", "kind": "goal", "expr": v("rce_achieved"),
                        "label": "攻击者达成远程代码执行（RCE）"},
                       {"id": "no_rce", "kind": "invariant", "expr": ap("not", v("rce_achieved")),
                        "label": "不发生 RCE"}],
        "objectives": [{"id": "attack_cost", "label": "攻击步数", "unit": "steps",
                        "terms": [{"kind": "action_cost"}]}],
    }
    am = AttackModel(name=name, hosts=[], creds=[], defenses=mitigations, ir_dict=ir_dict, techniques=tech)
    am.version = version  # type: ignore[attr-defined]
    am.env = env  # type: ignore[attr-defined]
    return am
