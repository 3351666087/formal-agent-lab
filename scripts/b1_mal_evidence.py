"""B1 evidence (phase 4B): the MAL security-lab closed loop with the runtime check path, a live-model red, a dynamic
blue, and model revision. Offline — the committed coreLang fixture, the ir-world simulator and the Z3 verifier; the
model endpoint is the loopback protocol-test service (a real HTTP round-trip, not a provider). `--real` uses the
configured provider from the environment / .env instead (`p4-b1-real-endpoint`); unavailable ⇒ BLOCKED, never faked.

The attack steps are abstract boolean nodes of a lowered coreLang attack graph in a simulator; nothing runs a real
system. In order (each result computed here, nothing asserted from source code):
  1. per-action admission loop — the MAL issuer checks each compromise step's precondition at the current revision and
     the target's reachability (Z3) before signing; the broker admits only against that receipt; the goal is reached
     and every send was checked at its own revision;
  2. live-model red — the hybrid red, through the protocol-test service (or the real provider), adopts at least one
     decision traceable to a model response (LLM_PROTOCOL_TEST / LLM with call ids); the stub is labelled LLM_STUB; an
     unreachable endpoint falls back to the rule (RULE, failed call kept) — never a bare LLM label without an answer;
  3. dynamic red/blue — red compromises and the reactive blue hardens from its observation (rule and live-model red);
     the environment state is the referee; two controlled cases show blue's choice follows the observation;
  4. zero side effect on rejection — with no issuer (no receipts) every send is DENIED and the target is never
     compromised; the issuer DENIES a step whose precondition does not hold at the current revision;
  5. model revision — a true deviation on a comparable state yields a regression case the old model fails and the
     revised model passes; a stale difference is classified STALE and never enters the regression library.
Writes $FAL_EVIDENCE_DIR/b1-mal.json (or b1-real-endpoint.json); reports through check_result.py.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
FIX = ROOT / "packages/domain-mal/tests/fixtures"
MODELS = ROOT / "packages/domain-mal/src/formal_lab_domain_mal/models"
KEYS = ("FAL_LLM_BASE_URL", "FAL_LLM_API_KEY", "FAL_LLM_MODEL")
TGT = {"property_id": "secret-confidentiality", "reach_forbidden": "secret:read"}


class Endpoint:
    """Point the LLM settings at an endpoint for a block (os.environ wins over .env)."""

    def __init__(self, url: str, key: str = "protocol-test-only", model: str = "protocol-test-v1"):
        self.values = {"FAL_LLM_BASE_URL": url, "FAL_LLM_API_KEY": key, "FAL_LLM_MODEL": model}

    def __enter__(self):
        self.before = {k: os.environ.get(k) for k in KEYS}
        os.environ.update(self.values)

    def __exit__(self, *exc):
        for k, v in self.before.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _package(*, defense: bool = False):
    from formal_lab_domain_mal.frontend import package_from_graph

    graph = json.loads((FIX / "net_app_data.graph.json").read_text())
    native = json.loads((FIX / "net_app_data.native.json").read_text())["reachable_case"]
    model = json.loads((MODELS / "net_app_data.json").read_text())
    pkg = package_from_graph(graph, native["entry"], native["goal"], package_id="mal-b1", version=1,
                             reachable=native["compromised"], model=model,
                             language={"name": "coreLang", "version": "1.0.0"}, include_defense=defense)
    return pkg, graph, native


def _lab_tgt():
    from formal_lab_domain_mal.config import LabPolicy, TargetSecurity

    return (LabPolicy(allowed_assets=["app", "secret", "net"], max_attack_steps=40),
            TargetSecurity(property_id=TGT["property_id"], reach_forbidden=TGT["reach_forbidden"]))


def _ctx(pkg, candidates, actor="red", facts=None):
    from formal_lab_contracts import BudgetUsage, CandidateAction, Observation, PlanningContext

    cands = [CandidateAction(action=a, belief_applicability="APPLICABLE") for a in candidates]
    obs = Observation(run_id="r", actor_id=actor, step=1, state_revision=0, facts=facts or [])
    return PlanningContext(run_id="r", step=1, step_id="r:s1", actor_id=actor, observation=obs, action_specs=[],
                           candidates=cands, model=pkg.ref(), budget={"max_steps": 120}, usage=BudgetUsage(), seed=0)


def _common(r: CheckResult, *, label: str, base_url: str | None) -> dict:
    from formal_lab_contracts import GroundAction
    from formal_lab_domain_mal.demo import gated_red_team, per_action_gated_red_team
    from formal_lab_domain_mal.frontend import attack_graph_of
    from formal_lab_domain_mal.gate import MalReceiptIssuer
    from formal_lab_domain_mal.revision import model_revision_cases
    from formal_lab_domain_mal.run import red_blue_scenario
    from formal_lab_domain_mal.strategies import MalBlueDefender, MalRedHybrid
    from formal_lab_model.driver import IRFiniteDriver
    from formal_lab_runtime import default_registry, make_manifest, run_local
    from formal_lab_strategies.model_clients import OpenAICompatibleClient, StubModelClient

    work = ROOT / "var" / f"b1-{uuid.uuid4().hex[:8]}"
    pkg, graph, native = _package()
    pkg_def, _, _ = _package(defense=True)
    lab, tgt = _lab_tgt()
    reg = default_registry()
    out: dict = {"endpoint": label}

    # 1. per-action admission loop (symbolic red)
    loop = per_action_gated_red_team(pkg, workdir=work / "loop", target_security=tgt, lab_policy=lab,
                                     strategy="symbolic")
    out["admission_loop"] = loop
    r.check("per_action_loop_reaches_goal", loop["run"]["goal_reached"] and loop["run"]["status"] == "SUCCEEDED",
            str(loop["run"]))
    r.check("every_send_checked_at_its_revision", loop["every_send_checked_at_its_revision"]
            and len(loop["issuer_decisions"]) >= 3, f"{len(loop['issuer_decisions'])} issuer checks at their revisions")

    # 2. live-model red: the hybrid through the configured endpoint, plus stub and unreachable
    hybrid = per_action_gated_red_team(pkg, workdir=work / "hybrid", target_security=tgt, lab_policy=lab,
                                       strategy="hybrid", max_model_calls=20,
                                       red_config={"client": "openai_compatible"} if base_url else None)
    model_sends = [s for s in hybrid["red_sources"] if s["decided_by"] == "MODEL_RESPONSE" and s["model_call_ids"]]
    ids = list(attack_graph_of(pkg)["lowering"]["id_map"].values())[:3]
    cands = [GroundAction(action_type="compromise", params={"n": i}) for i in ids]
    stub = MalRedHybrid(pkg, StubModelClient()).propose(_ctx(pkg, cands))
    bad = MalRedHybrid(pkg, OpenAICompatibleClient(base_url="http://127.0.0.1:9", api_key="x", model="m",
                                                   backoff_s=0.01, timeout_s=1, max_attempts=1))
    bad_p = bad.propose(_ctx(pkg, cands))
    out["live_model_red"] = {"endpoint": label, "red_sources": hybrid["red_sources"],
                             "adopted_from_model": len(model_sends),
                             "adopted_kind": model_sends[0]["kind"] if model_sends else None,
                             "stub_kind": str(stub.source.kind), "fallback_kind": str(bad_p.source.kind),
                             "fallback_failure": bad.last_decision.failure}
    r.check("red_adopts_a_model_decision", len(model_sends) >= 1
            and out["live_model_red"]["adopted_kind"] in ("LLM_PROTOCOL_TEST", "LLM"),
            f"{len(model_sends)} adopted {out['live_model_red']['adopted_kind']} send(s) with call ids")
    r.check("stub_labelled_and_unreachable_falls_back", str(stub.source.kind) == "LLM_STUB"
            and str(bad_p.source.kind) == "RULE" and bad.last_decision.failure,
            f"stub={stub.source.kind}, unreachable={bad_p.source.kind} ({bad.last_decision.failure})")

    # 3. dynamic red/blue — both act, env state is referee
    rb = {}
    for strat in (["rule", "hybrid"] if base_url else ["rule"]):
        rc = {"client": "openai_compatible"} if (strat == "hybrid" and base_url) else None
        scn = red_blue_scenario(pkg_def, strategy=strat, horizon=120, seed=0, red_config=rc, max_model_calls=40)
        res = run_local(make_manifest(run_id=f"rb_{strat}_{uuid.uuid4().hex[:6]}", project_id="b1", scenario=scn,
                                      package=pkg_def, registry=reg), pkg_def, reg)
        by: dict[str, list[str]] = {}
        for st in res.steps:
            if st.proposal:
                by.setdefault(st.actor_id, []).append(st.proposal.action.action_type)
        gid = attack_graph_of(pkg_def)["lowering"]["goal_id"]
        rb[strat] = {"status": str(res.status), "termination": str(res.termination_reason),
                     "red_actions": len(by.get("red", [])), "blue_actions": len(by.get("blue", [])),
                     "goal_reached": bool(res.final_state.get(f"compromised[{gid}]")),
                     "red_all_compromise": bool(by.get("red")) and all(a == "compromise" for a in by["red"]),
                     "blue_all_harden": bool(by.get("blue")) and all(a == "harden" for a in by["blue"])}
    out["red_blue"] = rb
    r.check("red_and_blue_both_act", all(v["red_all_compromise"] and v["blue_all_harden"] for v in rb.values()),
            str({k: (v["red_actions"], v["blue_actions"], v["goal_reached"]) for k, v in rb.items()}))

    # controlled cases: same initial config, different observation → different harden target
    blue = MalBlueDefender(pkg_def)
    gids = attack_graph_of(pkg_def)["lowering"]["id_map"]
    inv = {v: k for k, v in gids.items()}
    entry = {gids[e] for e in native["entry"] if e in gids}

    def blue_ctx(compromised):
        hc = [GroundAction(action_type="harden", params={"n": i}) for i in gids.values() if i not in compromised]
        facts = [{"path": f"compromised[{i}]", "value": i in compromised, "observed_at_step": 1}
                 for i in gids.values()]
        return _ctx(pkg_def, [h.model_dump() for h in hc], actor="blue", facts=facts)

    a = blue.propose(blue_ctx(set(entry)))
    b = blue.propose(blue_ctx(set(entry) | ({gids["app:attemptRead"]} if "app:attemptRead" in gids else set())))
    out["blue_controlled_cases"] = {"case_a_harden": inv.get(str(a.action.params.get("n"))),
                                    "case_b_harden": inv.get(str(b.action.params.get("n"))),
                                    "decision_varies": a.action.params != b.action.params}
    r.check("blue_decision_varies_with_observation", a.action.params != b.action.params,
            str(out["blue_controlled_cases"]))

    # 3b. real data-path projection: a participant's download of a gated red/blue run is projected — the gate
    # credential / receipt paths, the environment config and the other participant's config are not in it

    from formal_lab_contracts.bundle import read_bundle
    from formal_lab_runtime.bundles import bundle_from_local
    from formal_lab_runtime.participants import participant_bundle

    work.mkdir(parents=True, exist_ok=True)
    ks = work / "proj-keys.json"
    ks.write_text(json.dumps({"issuer-1": "00" * 24}))
    rcp = str((work / "proj-receipts.json").resolve())
    gates = [{"plugin": {"plugin_id": "formal-lab.domain.mal.receipt-issuer", "version": "1.0.0"},
              "config": {"keystore_path": str(ks.resolve()), "key_id": "issuer-1", "receipts_path": rcp,
                         "target_security": {"property_id": tgt.property_id, "reach_forbidden": tgt.reach_forbidden}}},
             {"plugin": {"plugin_id": "formal-lab.domain.mal.broker-gate", "version": "1.0.0"},
              "config": {"keystore_path": str(ks.resolve()), "receipts_path": rcp, "service_identity": "mal-sim",
                         "target_security": {"property_id": tgt.property_id, "reach_forbidden": tgt.reach_forbidden},
                         "lab_policy": lab.to_dict(), "role_allowed_actions": ["compromise"]}}]
    pscn = red_blue_scenario(pkg_def, strategy="rule", horizon=60, seed=0, execution_gates=gates)
    pres = run_local(make_manifest(run_id=f"proj_{uuid.uuid4().hex[:6]}", project_id="b1", scenario=pscn,
                                   package=pkg_def, registry=reg), pkg_def, reg)
    full = read_bundle(bundle_from_local(pres, pkg_def))
    red_dl = participant_bundle(full, "red")
    red_text = json.dumps([e.model_dump(mode="json") for e in red_dl.events], ensure_ascii=False) \
        + json.dumps(red_dl.manifest.model_dump(mode="json"), ensure_ascii=False)
    leaks = [s for s in (rcp, str(ks.resolve()), "proj-keys", "00000000") if s in red_text]
    out["participant_projection"] = {"actor": "red", "events": len(red_dl.events),
                                     "credential_paths_in_download": leaks,
                                     "blue_config_removed": all(p.strategy.config == {} for p in red_dl.manifest.participants
                                                                if p.actor_id != "red")}
    r.check("participant_download_is_a_projection", not leaks and out["participant_projection"]["blue_config_removed"]
            and len(red_dl.events) > 0, f"leaks={leaks}; blue config removed="
            f"{out['participant_projection']['blue_config_removed']}")

    # 4. zero side effect on rejection
    presigned = gated_red_team(pkg, workdir=work / "presigned", target_security=tgt, lab_policy=lab)
    inv_full = {v: k for k, v in attack_graph_of(pkg)["lowering"]["id_map"].items()}
    issuer = MalReceiptIssuer(loaded=IRFiniteDriver().load(pkg), package=pkg, signer=None, store=None, target=tgt,
                              bound={"max_steps": 60, "timeout_ms": 30000}, id_to_full=inv_full, ttl_seconds=300)
    goal_id = attack_graph_of(pkg)["lowering"]["goal_id"]
    deny = issuer.decide(SimpleNamespace(action=GroundAction(action_type="compromise", params={"n": goal_id}),
                                         execution=SimpleNamespace(current_revision=0, revision_note="t"),
                                         values={}, request_digest="d"))
    out["zero_side_effect"] = {"without_receipts": presigned["without_receipts"],
                               "issuer_precondition_deny": {"verdict": deny.verdict, "reason": deny.reason[:160]}}
    wr = presigned["without_receipts"]
    r.check("no_receipt_no_side_effect", wr["goal_reached"] is False and wr["denied_operations"] > 0
            and all(v == "DENY" for v in wr["gate_verdicts"]), str(wr))
    r.check("issuer_denies_unmet_precondition", deny.verdict == "DENY" and "ACTION_PRECONDITION_FAILED" in deny.reason,
            deny.reason[:120])

    # 5. model revision
    rev = model_revision_cases(graph, native["entry"], native["goal"], native["compromised"])
    td = rev["true_deviation"]
    out["model_revision"] = {"is_model_error": td["is_model_error"], "old_v1_rejected": td["old_model_v1_rejected"],
                             "revised_v2_passes": td["revised_model_v2_passes_case"],
                             "stale": rev["stale_difference"]["classification"],
                             "regression_library_clean": rev["regression_library_clean"]}
    r.check("true_deviation_regression_and_revision", td["is_model_error"] and td["old_model_v1_rejected"]
            and td["revised_model_v2_passes_case"], str(out["model_revision"]))
    r.check("stale_difference_not_in_library", rev["stale_difference"]["classification"] == "STALE"
            and rev["regression_library_clean"], rev["stale_difference"]["classification"])
    return out


def main_protocol() -> int:
    from formal_lab_strategies.protocol_server import ProtocolTestServer

    r = CheckResult("p4-b1-mal-loop")
    server = ProtocolTestServer().start()
    try:
        with Endpoint(server.base_url):
            out = _common(r, label=f"protocol-test service ({server.base_url})", base_url=server.base_url)
    finally:
        server.stop()
    EV.mkdir(parents=True, exist_ok=True)
    path = EV / "b1-mal.json"
    path.write_text(json.dumps({"deliverable": "phase4B-B1", **out,
                                "conclusion": {a["id"]: a["holds"] for a in r.assertions}},
                               indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(path)
    return r.finish()


def main_real() -> int:
    from formal_lab_runtime.settings import get_setting

    r = CheckResult("p4-b1-real-endpoint")
    base, model = get_setting("FAL_LLM_BASE_URL"), get_setting("FAL_LLM_MODEL")
    if not get_setting("FAL_LLM_API_KEY") or not base:
        return r.blocked("no model endpoint configured (FAL_LLM_BASE_URL / FAL_LLM_API_KEY): the real-provider "
                         "hybrid red is not run; the protocol-test service does not stand in for a real model")
    out = _common(r, label=f"real provider ({base}, model {model})", base_url=base)
    EV.mkdir(parents=True, exist_ok=True)
    path = EV / "b1-real-endpoint.json"
    path.write_text(json.dumps({"deliverable": "phase4B-B1 (real endpoint)", **out,
                                "conclusion": {a["id"]: a["holds"] for a in r.assertions}},
                               indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(path)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main_real() if "--real" in sys.argv[1:] else main_protocol())
