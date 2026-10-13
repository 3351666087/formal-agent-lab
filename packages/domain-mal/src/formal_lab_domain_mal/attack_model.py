"""A real attack model (not a flat attack graph): the state is the actual security posture an attacker changes —
footholds on hosts, local admin, stolen credentials, network reach, and finally data exfiltration — and the actions
are attack techniques with real preconditions and effects (you need a credential to authenticate, admin on the domain
controller to read the DB admin's secret, an un-patched host to exploit it, and so on). Defences — patching, MFA,
network segmentation — are model constants that gate techniques. The attacker's objective (`exfiltrated`) is reached
by a *plan* the Z3 verifier finds; there is no pre-computed "compromised[step]" / "hardened[step]" graph.

This is the model the platform runs (a red-team plan) and the model the LLM study reasons about; its ground truth
(shortest attack plan, reachability under a defence set, the minimum defences that stop exfiltration) is computed by
the Z3 verifier on the model itself. Defensive security modelling; the techniques are abstract named steps, not
operational instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from formal_lab_model.samples import ap, assign, c, v

# the enterprise topology: tiers of hosts, the credentials each yields, and the defences that gate them. Everything
# here is an abstract label in a formal model.
TIERS: list[dict[str, Any]] = [
    {"tier": "dmz", "hosts": ["web", "proxy", "vpn"], "exploitable": True},
    {"tier": "client", "hosts": ["workstation", "laptop"], "phishable": True},
    {"tier": "app", "hosts": ["appserver", "apiserver", "ciserver"], "needs_cred": "user"},
    {"tier": "domain", "hosts": ["dc", "adfs"], "needs_cred": "admin", "yields_cred": "dbadmin"},
    {"tier": "data", "hosts": ["db", "fileserver", "backup"], "needs_cred": "dbadmin", "crown": True},
]
CREDS = ["user", "admin", "dbadmin"]


@dataclass
class AttackModel:
    name: str
    hosts: list[str]
    creds: list[str]
    defenses: frozenset[str]
    ir_dict: dict[str, Any]
    techniques: list[str] = field(default_factory=list)

    def ir(self) -> Any:
        from formal_lab_contracts import ModelIR

        return ModelIR.model_validate(self.ir_dict)

    def package(self, version: int = 1) -> Any:
        from formal_lab_contracts import ModelSource
        from formal_lab_model import build_package

        ir = self.ir()
        return build_package(ir, package_id=self.name, version=version,
                             source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(),
                                                origin="formal_lab_domain_mal.attack_model"))


def enterprise_attack_model(*, scale: int = 1, defenses: frozenset[str] = frozenset(),
                            name: str = "enterprise-attack") -> AttackModel:
    """Build the attack model. `scale` adds hosts per tier (more attack surface); `defenses` is the set of deployed
    controls, each `patched:<host>`, `mfa:<cred>` or `segmented`, applied as model constants that block techniques."""
    hosts: list[str] = []
    tier_hosts: dict[str, list[str]] = {}
    for t in TIERS:
        picks = t["hosts"][: max(1, min(len(t["hosts"]), scale + (1 if t.get("crown") or t["tier"] == "dmz" else 0)))]
        tier_hosts[t["tier"]] = picks
        hosts += picks

    state = [{"name": "reach_dmz", "type": {"kind": "bool"}, "initial": {"default": True}, "label": "可达 DMZ"},
             {"name": "reach_internal", "type": {"kind": "bool"}, "initial": {"default": False}, "label": "可达内网"},
             {"name": "exfiltrated", "type": {"kind": "bool"}, "initial": {"default": False}, "label": "数据已外泄"}]
    for h in hosts:
        state.append({"name": f"foothold_{h}", "type": {"kind": "bool"}, "initial": {"default": False},
                      "label": f"{h} 立足点"})
        state.append({"name": f"admin_{h}", "type": {"kind": "bool"}, "initial": {"default": False},
                      "label": f"{h} 管理员"})
    for cr in CREDS:
        state.append({"name": f"stolen_{cr}", "type": {"kind": "bool"}, "initial": {"default": False},
                      "label": f"已窃取 {cr} 凭据"})

    def const_bool(nm: str, on: bool) -> dict[str, Any]:
        return {"name": nm, "type": {"kind": "bool"}, "value": {"default": on}}

    constants = [const_bool("segmented", "segmented" in defenses)]
    for h in hosts:
        constants.append(const_bool(f"patched_{h}", f"patched:{h}" in defenses))
    for cr in CREDS:
        constants.append(const_bool(f"mfa_{cr}", f"mfa:{cr}" in defenses))

    actions: list[dict[str, Any]] = []
    tech: list[str] = []

    def act(nm: str, pre: dict[str, Any] | None, *sets: str) -> None:
        a = {"name": nm, "cost": 1, "effects": [assign(s, c(True)) for s in sets]}
        if pre is not None:
            a["precondition"] = pre
        actions.append(a)
        tech.append(nm)

    # perimeter → footholds: exploit an un-patched DMZ host, or phish a client
    for h in tier_hosts["dmz"]:
        act(f"exploit_{h}", ap("and", v("reach_dmz"), ap("not", v(f"patched_{h}"))), f"foothold_{h}")
    for h in tier_hosts.get("client", []):
        act(f"phish_{h}", None, f"foothold_{h}", "stolen_user")
        # a local privilege escalation on a phished client — admin here lets the attacker pivot even past segmentation
        act(f"escalate_{h}", ap("and", v(f"foothold_{h}"), ap("not", v(f"patched_{h}"))), f"admin_{h}")

    # steal the user credential from any held foothold
    any_foothold = _any(hosts, "foothold_")
    act("steal_user_cred", any_foothold, "stolen_user")
    # reach the internal network: need admin on a client/app host, unless the network is flat (not segmented)
    internal_pivot = ap("or", ap("not", v("segmented")), _any(tier_hosts.get("app", []) + tier_hosts.get("client", []),
                                                               "admin_"))
    act("pivot_internal", ap("and", any_foothold, internal_pivot), "reach_internal")

    # authenticate to app hosts with the user credential (blocked by MFA unless also phished)
    for h in tier_hosts.get("app", []):
        act(f"auth_{h}", ap("and", v("reach_internal"), v("stolen_user"),
                            ap("or", ap("not", v("mfa_user")), _any(tier_hosts.get("client", []), "foothold_"))),
            f"foothold_{h}")
        act(f"escalate_{h}", ap("and", v(f"foothold_{h}"), ap("or", v("stolen_admin"), ap("not", v(f"patched_{h}")))),
            f"admin_{h}")
        # a CI/deploy host leaks the DB-admin credential in its pipeline secrets — a second path that does not go
        # through the domain controller, so the domain MFA alone no longer cuts every route to the data
        if h == "ciserver":
            act(f"leak_secrets_{h}", v(f"admin_{h}"), "stolen_dbadmin")

    # the domain controller yields the admin and then the DB-admin credential
    for h in tier_hosts.get("domain", []):
        act(f"auth_{h}", ap("and", v("reach_internal"), v("stolen_admin"), ap("not", v("mfa_admin"))),
            f"foothold_{h}")
        act(f"kerberoast_{h}", ap("and", v("reach_internal"), _any(tier_hosts.get("app", []), "foothold_")),
            "stolen_admin")
        act(f"escalate_{h}", ap("and", v(f"foothold_{h}"), v("stolen_admin")), f"admin_{h}")
        act(f"dump_dbadmin_{h}", v(f"admin_{h}"), "stolen_dbadmin")

    # the crown-jewel data tier: authenticate with the DB-admin credential, get admin, exfiltrate
    domain_admin = _any(tier_hosts.get("domain", []), "admin_")
    for h in tier_hosts["data"]:
        act(f"auth_{h}", ap("and", v("reach_internal"), v("stolen_dbadmin"),
                            ap("or", ap("not", v("mfa_dbadmin")), domain_admin)), f"foothold_{h}")
        # admin on the data host comes from domain admin OR from the stolen DB-admin credential (the CI-leak path)
        act(f"escalate_{h}", ap("and", v(f"foothold_{h}"), ap("or", domain_admin, v("stolen_dbadmin"))), f"admin_{h}")
        act(f"exfiltrate_{h}", v(f"admin_{h}"), "exfiltrated")

    ir_dict = {
        "name": name, "description": "Enterprise breach attack model: techniques over real security posture; the "
        "attacker plans a path to data exfiltration. Defences (patching/MFA/segmentation) are constants that gate "
        "techniques.", "constants": constants, "state": state, "actions": actions,
        "properties": [{"id": "data_exfiltrated", "kind": "goal", "expr": v("exfiltrated"),
                        "label": "攻击者外泄了王冠数据"},
                       {"id": "data_safe", "kind": "invariant", "expr": ap("not", v("exfiltrated")),
                        "label": "数据未被外泄"}],
        "objectives": [{"id": "attack_cost", "label": "攻击步数", "unit": "techniques",
                        "terms": [{"kind": "action_cost"}]}],
    }
    return AttackModel(name=name, hosts=hosts, creds=CREDS, defenses=defenses, ir_dict=ir_dict, techniques=tech)


def _any(names: list[str], prefix: str) -> dict[str, Any]:
    """An OR over `prefix<name>` state vars (… any foothold / any admin …)."""
    refs = [v(f"{prefix}{n}") for n in names]
    if not refs:
        return c(False)
    out = refs[0]
    for r_ in refs[1:]:
        out = ap("or", out, r_)
    return out
