"""The MAL admission closed loop (phase 3B, D2), reused by the test and the evidence script.

`gated_red_team` runs the red-team episode three ways on one package and returns a structured, offline-readable record:

  * plan          — the deterministic attack plan (from a plain run), used to pre-issue receipts;
  * with_receipts — the same run behind the MAL Broker gate, receipts issued for the plan → every send ADMITTED, goal reached;
  * without_receipts — the same run with an empty receipt store → every send DENIED, **zero side effects** (the goal step is never compromised).

Because ir-world and the Z3 planner are deterministic, the plan learned in the first pass matches the gated passes, so a
receipt issued for step k at revision k−1 binds exactly to that send's run_id / operation_id / parameter digest / revision.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .admission import target_check_basis
from .config import LabPolicy, TargetSecurity
from .frontend import attack_graph_of
from .run import red_team_scenario, run_red_team

GATE = {"plugin_id": "formal-lab.domain.mal.broker-gate", "version": "1.0.0"}
ISSUER = {"plugin_id": "formal-lab.broker.receipt-issuer", "version": "1.0.0"}


def _request_digest(actor: str, action: dict[str, Any]) -> str:
    body = {"kind": "apply", "actor_id": actor, "action": action}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _run_summary(result: Any, goal_id: str) -> dict[str, Any]:
    decided = [s for s in result.steps if s.operation and s.operation.decisions]
    verdicts = [d.verdict for s in decided for d in s.operation.decisions]
    failed = sum(1 for s in result.steps if s.operation and s.operation.state == "FAILED")
    return {"status": str(result.status), "reason": result.reason, "steps": len(result.steps),
            "goal_reached": bool(result.final_state.get(f"compromised[{goal_id}]")),
            "gate_verdicts": verdicts, "denied_operations": failed}


def gated_red_team(package: Any, *, workdir: str | Path, target_security: TargetSecurity, lab_policy: LabPolicy,
                   service_identity: str = "mal-sim", ttl_seconds: int = 3600) -> dict[str, Any]:
    from formal_lab_runtime import default_registry, make_manifest, run_local

    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    reg = default_registry()
    goal_id = attack_graph_of(package)["lowering"]["goal_id"]

    plan_result = run_red_team(package)
    plan = [{"actor": st.proposal.actor_id, "action": st.proposal.action.model_dump(mode="json"),
             "revision": st.proposal.based_on_revision, "step": st.step} for st in plan_result.steps]

    # receipts are issued at send time, bound to the kernel's authoritative ExecutionContext (phase 4A): an issuer
    # gate signs for the verified basis, the MAL broker gate then admits only against that same context
    secret = os.urandom(24)
    ks_path = work / "keys.json"
    ks_path.write_text(json.dumps({"issuer-1": secret.hex()}))
    rc_path = work / "receipts.json"
    basis = target_check_basis(property_id=target_security.property_id, verdict="WITNESS", scope="MODEL_INTERNAL",
                               backend="formal-lab.verifier.z3-bmc@1.1.0", bound={"max_steps": 60})
    issuer = {"plugin": ISSUER, "config": {
        "keystore_path": str(ks_path), "key_id": "issuer-1", "receipts_path": str(rc_path), "ttl_seconds": ttl_seconds,
        "basis": {"query_kind": basis.query_kind, "property_id": basis.property_id, "verdict": basis.verdict,
                  "scope": basis.scope, "backend": basis.backend, "bound": basis.bound},
        "guarantee_scope": f"bounded reachability of {target_security.property_id}"}}
    run_id = "run_mal_d2_admit"

    base_cfg = {"keystore_path": str(ks_path), "service_identity": service_identity,
                "target_security": target_security.to_dict(), "lab_policy": lab_policy.to_dict(),
                "role_allowed_actions": ["compromise"]}

    def run_with(receipts_path: str, run_id_used: str | None = None, *, issue: bool = False) -> Any:
        from formal_lab_runtime import new_run_id

        cfg = {**base_cfg, "receipts_path": receipts_path}
        gates = ([issuer] if issue else []) + [{"plugin": GATE, "config": cfg}]
        scn = red_team_scenario(package, execution_gates=gates)
        manifest = make_manifest(run_id=run_id_used or new_run_id(), project_id="phase3b-d2", scenario=scn,
                                 package=package, registry=reg)
        return run_local(manifest, package, reg)

    with_receipts = run_with(str(rc_path), run_id, issue=True)
    empty_path = str(work / "empty.json")
    without_receipts = run_with(empty_path)

    return {
        "plan": [{"step": x["step"], "revision": x["revision"], "action_type": x["action"]["action_type"],
                  "params": x["action"]["params"]} for x in plan],
        "receipts_issued": len(plan),
        "with_receipts": _run_summary(with_receipts, goal_id),
        "without_receipts": _run_summary(without_receipts, goal_id),
    }
