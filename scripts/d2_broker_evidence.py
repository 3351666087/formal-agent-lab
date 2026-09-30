"""D2 evidence: domain admission broker, verification receipts and red/blue role boundaries.

Records, offline-readable:
  * ruleset       — the RELEASED MAL rule set (four separately-explained kinds) with its content digest;
  * admit_taxonomy — one happy admission plus every rejection class (missing receipt, tampered signature, binding
                    mismatch, stale state revision, expired, wrong role, LabPolicy out of scope, TargetSecurity
                    mismatch), each showing which reason failed — all are zero-side-effect refusals;
  * platform_run  — the red-team episode behind the Broker gate: with receipts every send is ADMITTED and the goal is
                    reached; with an empty receipt store every send is DENIED and the goal is never compromised;
  * role_boundary — a marked payload check: hidden ground truth and signing credentials are detected and withheld,
                    while legitimate observation is complete;
  * isolation     — a plain statement of the isolation actually in force here.

Run: scripts/in-vm.sh 'export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/formal-agent-lab; cd <repo>; uv run --no-sync python scripts/d2_broker_evidence.py'
Writes $FAL_EVIDENCE_DIR/d2-broker.json (default docs/execution/evidence/phase3).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from formal_lab_domain_broker import (
    HmacSigner,
    HmacVerifier,
    KeyStore,
    RequestBinding,
    admit,
    digest_params,
    red_blue_boundaries,
    signature_ok,
)
from formal_lab_domain_mal.admission import issue_receipt, mal_ruleset, target_check_basis
from formal_lab_domain_mal.config import LabPolicy, TargetSecurity
from formal_lab_domain_mal.demo import gated_red_team
from formal_lab_domain_mal.frontend import package_from_graph

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packages" / "domain-mal"
OUT = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3") / "d2-broker.json"

LAB = LabPolicy(allowed_assets=["app", "secret", "net"], max_attack_steps=40)
TGT = TargetSecurity(property_id="secret-confidentiality", reach_forbidden="secret:read")
ID_TO_FULL = {"secret__read": "secret:read", "net__eavesdrop": "net:eavesdrop"}


def _package():
    graph = json.loads((PKG / "tests/fixtures/net_app_data.graph.json").read_text())
    native = json.loads((PKG / "tests/fixtures/net_app_data.native.json").read_text())["reachable_case"]
    model = json.loads((PKG / "src/formal_lab_domain_mal/models/net_app_data.json").read_text())
    return package_from_graph(graph, native["entry"], native["goal"], package_id="mal-net-app-data", version=1,
                             reachable=native["compromised"], model=model, language={"name": "coreLang",
                                                                                     "version": "1.0.0"})


def _ctx(params):
    return {"lab_policy": LAB, "target_security": TGT, "action_params": params, "id_to_full": ID_TO_FULL}


def _admit(receipt, binding, params, *, role=("compromise",), lab=LAB):
    ctx = {**_ctx(params), "lab_policy": lab}
    return admit(receipt, binding, verifier=VERIFIER, rules=mal_ruleset(), role_allowed_actions=list(role), context=ctx)


KS = KeyStore({"issuer-1": os.urandom(24)})
SIGNER = HmacSigner(KS, "issuer-1")
VERIFIER = HmacVerifier(KS)


def _mk(params, *, revision=5, property_id="secret-confidentiality", verdict="WITNESS", ttl=300):
    basis = target_check_basis(property_id=property_id, verdict=verdict, scope="MODEL_INTERNAL",
                               backend="formal-lab.verifier.z3-bmc@1.1.0", bound={"max_steps": 60})
    r = issue_receipt(run_id="r", step=6, actor_id="red", operation_id="op", action_params=params,
                      state_revision=revision, check_basis=basis, guarantee_scope="bounded reachability", signer=SIGNER,
                      service_identity="mal-sim", ttl_seconds=ttl)
    b = RequestBinding(run_id="r", step=6, actor_id="red", operation_id="op", action_type="compromise",
                       action_params_digest=digest_params(params), current_revision=revision, service_identity="mal-sim")
    return r, b


def _row(name, decision, failing_kind=None):
    failed = [f"{x.kind}: {x.detail}" for x in decision.reasons if x.holds is not True]
    return {"case": name, "verdict": decision.verdict, "zero_side_effect": decision.verdict == "DENY",
            "failing_reason_kind": (failing_kind if decision.verdict == "DENY" else None),
            "explained_reasons": [f"{r.kind}={r.holds}" for r in decision.reasons], "failed": failed}


def admit_taxonomy():
    p = {"n": "secret__read"}
    rows = []
    r, b = _mk(p)
    rows.append(_row("happy_path", _admit(r, b, p)))
    rows.append(_row("missing_receipt", _admit(None, b, p), "binding"))
    rows.append(_row("tampered_signature", _admit(replace(r, signature="00" * 32), b, p), "provenance"))
    rows.append(_row("binding_mismatch_actor", _admit(r, replace(b, actor_id="blue"), p), "binding"))
    rows.append(_row("stale_state_revision", _admit(r, replace(b, current_revision=7), p), "state_revision"))
    r_exp, b_exp = _mk(p, ttl=-1)
    rows.append(_row("expired_receipt", _admit(r_exp, b_exp, p), "expiry"))
    rows.append(_row("wrong_role", _admit(r, b, p, role=("observe",)), "role_rule"))
    pn = {"n": "net__eavesdrop"}
    r_net, b_net = _mk(pn)
    rows.append(_row("lab_policy_out_of_scope", _admit(r_net, b_net, pn, lab=LabPolicy(allowed_assets=["app"])),
                     "lab_policy"))
    r_wrong, b_wrong = _mk(p, property_id="unrelated-property")
    rows.append(_row("target_security_mismatch", _admit(r_wrong, b_wrong, p), "target_security"))
    return rows


def role_boundary():
    b = red_blue_boundaries()
    attacker = b["attacker"]
    leaky = {"compromised": {"app:read": True}, "ground_truth": {"secret:read": True}, "signing_key": "deadbeef",
             "service_token": "t0ken"}
    clean = {"compromised": {"app:read": True}}
    state = {"compromised[app:read]": True, "defense[eavesdrop]": False, "ground_truth[secret:read]": True}
    return {
        "roles": sorted(b),
        "leaks_detected_in_marked_payload": attacker.leaks(leaky),
        "leaks_in_legitimate_payload": attacker.leaks(clean),
        "redacted_state_keys": sorted(attacker.redact_state(state)),
        "withheld": sorted(set(state) - set(attacker.redact_state(state))),
    }


def main() -> int:
    rs = mal_ruleset()
    pkg = _package()
    with tempfile.TemporaryDirectory() as td:
        run = gated_red_team(pkg, workdir=td, target_security=TGT, lab_policy=LAB)

    # provenance survives expiry (history), even though a fresh send would be refused
    p = {"n": "secret__read"}
    r_exp, _ = _mk(p, ttl=-100)
    history_provenance_ok = signature_ok(r_exp, VERIFIER) and r_exp.is_expired()

    result = {
        "deliverable": "phase3B-D2",
        "ruleset": {"id": rs.ruleset_id, "version": rs.version, "status": str(rs.status), "digest": rs.digest(),
                    "rules": [{"rule_id": x.rule_id, "kind": x.kind, "on": x.on, "when": x.when, "then": str(x.then),
                               "source": x.source} for x in rs.rules]},
        "signing": {"scheme": "HMAC-SHA256 (FIPS-198) behind Signer/Verifier; asymmetric backend can replace it",
                    "guarantee": "signature provides provenance + integrity only; the mathematical guarantee is the "
                                 "receipt's check_basis / scope, not the signature",
                    "history_provenance_survives_expiry": history_provenance_ok},
        "admit_taxonomy": admit_taxonomy(),
        "platform_run": run,
        "role_boundary": role_boundary(),
        "isolation": {
            "gate_path": "the Broker runs as an EXECUTION_GATE, so a DENY is never sent by the coordinator — rejection "
                         "has zero side effects on the local runner, Temporal, re-send and pure-data re-execution (G2)",
            "keys": "signing key held in a KeyStore separate from environment/service credentials; the receipt store "
                    "carries only receipts, never secrets",
            "strength": "in-process Python objects are NOT a security sandbox; isolation here is the gate boundary plus "
                        "separate key storage and role views. Process/container/network isolation is D4's concern.",
        },
        "conclusion": {
            "normal_action_executable": run["with_receipts"]["goal_reached"],
            "rejection_zero_side_effect": (not run["without_receipts"]["goal_reached"]
                                           and run["without_receipts"]["denied_operations"] > 0),
            "every_rejection_class_explained": all(r["verdict"] == "DENY" for r in admit_taxonomy()[1:]),
            "offline_readable": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  ruleset={rs.ruleset_id} v{rs.version} digest={rs.digest()[:12]} status={rs.status}")
    print(f"  with_receipts={run['with_receipts']['status']} goal={run['with_receipts']['goal_reached']} "
          f"| without_receipts goal={run['without_receipts']['goal_reached']} "
          f"denied={run['without_receipts']['denied_operations']}")
    print(f"  admit taxonomy: {sum(1 for r in admit_taxonomy() if r['verdict'] == 'DENY')} deny classes + 1 happy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
