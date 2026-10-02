"""A3 evidence: the reusable model decision path through the real strategy factories and the local runner.

Default (`p4-a3-decision`): the loopback protocol test service (NOT a model), a closed port and the stub —
  follows_answer   scripted different legal answers → different decisions, labelled LLM_PROTOCOL_TEST;
  invalid          out-of-range answers → asked again, then a RULE fallback with the failed call ids; with
                   on_model_failure=fail the run fails with the classified reason;
  unreachable      a closed port → TRANSPORT_ERROR records with attempts, no usable answer, never a model decision;
  stub             the deterministic stand-in stays LLM_STUB;
  resume           stopped after step 4 and resumed from JSON in fresh components → no committed call repeated;
  budget           max_model_calls=3 → exactly 3 requests reach the service; max_model_attempts=4 with failing
                   answers → at most 4 requests;
  reuse            the scheduling task planner (generator=model) through the same decision: plan steps cite the call
                   ids that generated the plan (INHERITED_PLAN), far fewer calls than steps.
`--real` (`p4-a3-real-endpoint`): the configured provider (FAL_LLM_* from the environment or the git-ignored .env) on
the ordinary scheduling scenario with the task planner and on the order case with the LLM planner under a small call
budget; BLOCKED when no endpoint is configured or it cannot be reached. Credentials are never written.

Writes $FAL_EVIDENCE_DIR/a3-model-decision.json (or a3-real-endpoint.json) and reports through check_result.py.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
for _k in ("NO_PROXY", "no_proxy"):  # loopback never through a proxy from the environment
    os.environ[_k] = ",".join(x for x in (os.environ.get(_k), "127.0.0.1,localhost,::1") if x)

from formal_lab_example_scheduling.scenarios import model_package, scenario  # noqa: E402
from formal_lab_runtime import default_registry, make_manifest, resume_local, run_local  # noqa: E402
from formal_lab_strategies.protocol_server import MODEL, ProtocolTestServer  # noqa: E402

LLM = {"plugin_id": "formal-lab.planner.llm", "version": "1.1.0"}
TASK = {"plugin_id": "formal-lab.example.scheduling.task-planner", "version": "1.0.0"}
KEYS = ("FAL_LLM_BASE_URL", "FAL_LLM_API_KEY", "FAL_LLM_MODEL")


class Endpoint:
    """Point the settings at an endpoint for the duration of a block (os.environ wins over .env)."""

    def __init__(self, url: str, key: str = "protocol-test-only", model: str = MODEL):
        self.values = {"FAL_LLM_BASE_URL": url, "FAL_LLM_API_KEY": key, "FAL_LLM_MODEL": model}

    def __enter__(self):
        self.before = {k: os.environ.get(k) for k in KEYS}
        os.environ.update(self.values)

    def __exit__(self, *exc):
        for k, v in self.before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run(strategy: dict[str, Any], *, budget: dict[str, Any] | None = None, stop_after: int | None = None,
        key: str = "normal", seed: int = 1):
    pkg, reg = model_package(), default_registry()
    sc = scenario(key, pkg, seed=seed, strategy=strategy)
    m = make_manifest(run_id=f"run_a3_{uuid.uuid4().hex[:8]}", project_id="a3", scenario=sc, package=pkg,
                      registry=reg, budget=budget)
    return run_local(m, pkg, reg, stop_after=stop_after), pkg, reg


def sources(result) -> list[tuple[str, str | None]]:
    return [(str(s.proposal.source.kind), s.proposal.source.decided_by) for s in result.steps if s.proposal]


def llm(config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"plugin": LLM, "config": {"client": "openai_compatible", "max_attempts": 2, "timeout_s": 10,
                                      **(config or {})}}


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def protocol_sections() -> dict[str, Any]:
    out: dict[str, Any] = {}
    # follows_answer: the same scenario, two scripted different legal first answers
    firsts = []
    for pick in ("pick:0", "pick:1"):
        with ProtocolTestServer(script=[pick]) as srv, Endpoint(srv.base_url):
            res, _, _ = run(llm(), budget={"max_steps": 3})
        step1 = res.steps[0].proposal
        firsts.append({"script": pick, "action": step1.action.model_dump(mode="json"),
                       "source": [str(step1.source.kind), step1.source.decided_by],
                       "call_ids": step1.source.model_call_ids, "answered": [f"ptest_{i:05d}" for i in
                                                                             range(1, len(srv.requests) + 1)]})
    out["follows_answer"] = firsts
    # invalid answers: re-asked, then fallback / fail
    with ProtocolTestServer(script=["out_of_range", "out_of_range"]) as srv, Endpoint(srv.base_url):
        res, _, _ = run(llm({"fallback_preference": ["assign"]}), budget={"max_steps": 2})
    p = res.steps[0].proposal
    out["invalid_fallback"] = {"source": [str(p.source.kind), p.source.decided_by], "call_ids": p.source.model_call_ids,
                               "outcomes": [c.get("business") for c in res.model_calls if c.get("step") == 1],
                               "rationale": p.rationale}
    with ProtocolTestServer(script=["out_of_range", "out_of_range"]) as srv, Endpoint(srv.base_url):
        res, _, _ = run(llm({"on_model_failure": "fail"}), budget={"max_steps": 2})
    out["invalid_fail"] = {"status": str(res.status.value), "reason": (res.reason or "")[:300]}
    # unreachable endpoint
    with Endpoint(f"http://127.0.0.1:{closed_port()}/v1"):
        res, _, _ = run(llm(), budget={"max_steps": 3})
    out["unreachable"] = {"status": str(res.status.value), "sources": sorted(set(map(tuple, sources(res)))),
                          "records": [{k: c.get(k) for k in ("outcome", "attempts", "error", "input_tokens",
                                                              "usage_reported")} for c in res.model_calls][:3],
                          "usage": res.usage.model_dump()}
    # stub
    res, _, _ = run({"plugin": LLM, "config": {"client": "stub"}}, budget={"max_steps": 4})
    out["stub"] = {"sources": sorted(set(map(tuple, sources(res)))),
                   "endpoint_kinds": sorted({c.get("endpoint_kind") for c in res.model_calls})}
    # stop and resume (fresh components from JSON): no committed call is repeated
    with ProtocolTestServer() as srv, Endpoint(srv.base_url):
        state, pkg, reg = run(llm(), budget={"max_steps": 12}, stop_after=4)
        at_stop = len(srv.requests)
        res = resume_local(json.loads(json.dumps(state.to_json())), pkg, reg)
        ids = [cid for s in res.steps if s.proposal for cid in s.proposal.source.model_call_ids]
        out["resume"] = {"requests_before_stop": at_stop, "requests_total": len(srv.requests),
                         "committed_call_ids": len(ids), "unique": len(set(ids)), "steps": len(res.steps),
                         "status": str(res.status.value)}
    # budget: calls, then attempts
    with ProtocolTestServer() as srv, Endpoint(srv.base_url):
        res, _, _ = run(llm(), budget={"max_steps": 30, "max_model_calls": 3})
        out["budget_calls"] = {"requests": len(srv.requests), "status": str(res.status.value),
                               "reason": res.reason, "model_calls": res.usage.model_calls}
    with ProtocolTestServer(script=["500"] * 50) as srv, Endpoint(srv.base_url):
        res, _, _ = run(llm({"max_attempts": 3}), budget={"max_steps": 30, "max_model_attempts": 4})
        out["budget_attempts"] = {"requests": len(srv.requests), "status": str(res.status.value),
                                  "reason": res.reason, "attempts": res.usage.model_attempts,
                                  "budget_records": sum(1 for c in res.model_calls
                                                        if c.get("outcome") == "BUDGET_EXHAUSTED")}
    # reuse: the scheduling task planner through the same decision
    with ProtocolTestServer() as srv, Endpoint(srv.base_url):
        res, _, _ = run({"plugin": TASK, "config": {"generator": "model"}})
        props = [s.proposal for s in res.steps if s.proposal]
        out["reuse_task_planner"] = {
            "status": str(res.status.value), "steps": len(props), "requests": len(srv.requests),
            "decided_by": sorted({p.source.decided_by for p in props}),
            "kinds": sorted({str(p.source.kind) for p in props}),
            "inherited_cite_generating_calls": all(p.source.model_call_ids for p in props
                                                   if p.source.decided_by == "INHERITED_PLAN"),
            "cited_ids_answered": {cid for p in props for cid in p.source.model_call_ids}
            <= {f"ptest_{i:05d}" for i in range(1, len(srv.requests) + 1)}}
    return out


def main_protocol() -> int:
    r = CheckResult("p4-a3-decision")
    out = protocol_sections()
    c = r.check
    fa = out["follows_answer"]
    c("decision_follows_answer", fa[0]["action"] != fa[1]["action"]
      and all(f["source"] == ["LLM_PROTOCOL_TEST", "MODEL_RESPONSE"] for f in fa)
      and all(set(f["call_ids"]) <= set(f["answered"]) for f in fa),
      f"{fa[0]['script']} → {fa[0]['action']}; {fa[1]['script']} → {fa[1]['action']}")
    inv = out["invalid_fallback"]
    c("invalid_answer_fallback", inv["source"] == ["RULE", "RULE_FALLBACK"] and len(inv["call_ids"]) == 2,
      f"{inv['source']} with failed calls {inv['call_ids']}")
    c("invalid_answer_fail", out["invalid_fail"]["status"] == "FAILED"
      and "BUSINESS_INVALID" in out["invalid_fail"]["reason"], out["invalid_fail"]["reason"][:160])
    un = out["unreachable"]
    c("unreachable_is_recorded_failure", un["sources"] == [("RULE", "RULE_FALLBACK")] and un["records"]
      and all(x["outcome"] == "TRANSPORT_ERROR" and x["attempts"] >= 1 and x["input_tokens"] is None
              for x in un["records"]) and un["usage"]["model_calls"] == 0 and un["usage"]["model_attempts"] > 0,
      f"{un['records'][0] if un['records'] else None}")
    c("stub_stays_stub", out["stub"]["sources"] == [("LLM_STUB", "MODEL_RESPONSE")]
      and out["stub"]["endpoint_kinds"] == ["STUB"], str(out["stub"]))
    rs = out["resume"]
    c("resume_never_repeats_committed_calls", rs["requests_total"] == rs["committed_call_ids"] == rs["unique"]
      and rs["requests_before_stop"] > 0, str(rs))
    bc, ba = out["budget_calls"], out["budget_attempts"]
    c("budget_stops_calls", bc["requests"] == 3 and bc["status"] == "BUDGET_EXHAUSTED", str(bc))
    c("budget_stops_attempts", ba["requests"] <= 4 and ba["status"] == "BUDGET_EXHAUSTED", str(ba))
    ru = out["reuse_task_planner"]
    c("reusable_by_task_planner", ru["status"] == "SUCCEEDED" and "INHERITED_PLAN" in ru["decided_by"]
      and ru["kinds"] == ["LLM_PROTOCOL_TEST"] and ru["inherited_cite_generating_calls"] and ru["cited_ids_answered"]
      and ru["requests"] < ru["steps"], f"{ru['steps']} steps from {ru['requests']} request(s): {ru['decided_by']}")
    EV.mkdir(parents=True, exist_ok=True)
    path = EV / "a3-model-decision.json"
    out["reuse_task_planner"]["cited_ids_answered"] = bool(ru["cited_ids_answered"])
    path.write_text(json.dumps({"deliverable": "phase4A-A3", "endpoint": "protocol test service (loopback; NOT a model)"
                                " / closed port / stub", "sections": out,
                                "conclusion": {a["id"]: a["holds"] for a in r.assertions}},
                               indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(path)
    return r.finish()


def main_real() -> int:
    from formal_lab_runtime.settings import get_setting

    r = CheckResult("p4-a3-real-endpoint")
    base, model = get_setting("FAL_LLM_BASE_URL"), get_setting("FAL_LLM_MODEL")
    if not get_setting("FAL_LLM_API_KEY") or not base:
        return r.blocked("no model endpoint configured (FAL_LLM_BASE_URL / FAL_LLM_API_KEY): the real-provider check "
                         "is not run; the protocol test service does not stand in for it")
    from formal_lab_strategies.model_clients import public_endpoint

    task, _, _ = run({"plugin": TASK, "config": {"generator": "model"}})
    calls = task.model_calls
    if calls and all(c.get("outcome") == "TRANSPORT_ERROR" for c in calls):
        return r.blocked(f"the configured endpoint {public_endpoint(base)} cannot be reached: "
                         f"{calls[0].get('error', '')[:200]}")
    props = [s.proposal for s in task.steps if s.proposal]
    orders = _order_case()
    oprops = [s.proposal for s in orders.steps if s.proposal]
    ocalls = orders.model_calls
    out = {"endpoint": public_endpoint(base), "model_configured": model,
           "task_planner_scheduling": {
               "status": str(task.status.value), "steps": len(props),
               "requests": sum(c.get("attempts", 0) for c in calls),
               "calls": [{k: c.get(k) for k in ("call_id", "outcome", "endpoint_kind", "model_requested",
                                                 "model_returned", "model_switched", "attempts", "usage_reported",
                                                 "input_tokens", "output_tokens", "latency_ms", "business",
                                                 "prompt_digest", "config_digest")} for c in calls],
               "kinds": sorted({str(p.source.kind) for p in props}),
               "decided_by": sorted({str(p.source.decided_by) for p in props}),
               "metrics": {m.metric_id: m.value for m in task.metrics}},
           "llm_planner_orders": {
               "status": str(orders.status.value), "reason": orders.reason, "steps": len(oprops),
               "kinds": sorted({str(p.source.kind) for p in oprops}),
               "calls": len(ocalls), "ok": sum(1 for c in ocalls if c.get("outcome") == "OK"),
               "outcomes": [{k: c.get(k) for k in ("step", "outcome", "business", "attempts", "http_status",
                                                    "model_returned", "usage_reported")} | {
                   "error": (c.get("error") or "")[:160]} for c in ocalls],
               "endpoint_kinds": sorted({str(c.get("endpoint_kind")) for c in ocalls}),
               "first_rationales": [p.rationale for p in oprops[:2]]}}
    c = r.check
    model_calls = [x for x in out["task_planner_scheduling"]["calls"] if x["outcome"] == "OK"]
    c("real_provider_answered", bool(model_calls) and all(x["endpoint_kind"] == "PROVIDER" for x in model_calls),
      f"{len(model_calls)} answered call(s) from {out['endpoint']} model {model_calls[0]['model_returned'] if model_calls else None}")
    c("task_planner_real_run", out["task_planner_scheduling"]["status"] == "SUCCEEDED"
      and "LLM" in out["task_planner_scheduling"]["kinds"], str(out["task_planner_scheduling"]["kinds"]))
    c("llm_planner_real_steps", out["llm_planner_orders"]["ok"] > 0 and "LLM" in out["llm_planner_orders"]["kinds"],
      f"{out['llm_planner_orders']['ok']} answered call(s), status {out['llm_planner_orders']['status']}")
    EV.mkdir(parents=True, exist_ok=True)
    path = EV / "a3-real-endpoint.json"
    path.write_text(json.dumps({"deliverable": "phase4A-A3 real provider", **out,
                                "conclusion": {a["id"]: a["holds"] for a in r.assertions}},
                               indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(path)
    return r.finish()


def _order_case():
    """The ordinary order case with the LLM planner under a small model-call budget (local-lite service)."""
    import tempfile

    from formal_lab_contracts import ScenarioManifest
    from formal_lab_example_orders.lifecycle import ServiceManager
    from formal_lab_example_orders.model import model_package as orders_package
    from formal_lab_example_orders.scenarios import scenario as order_scenario

    work = Path(tempfile.mkdtemp(prefix="a3-orders-"))
    svc = ServiceManager(work, project="a3-real").start()
    svc.ready()
    try:
        pkg, reg = orders_package(), default_registry()
        base = order_scenario("normal", endpoint=svc.endpoint, tenant="a3-real",
                              strategy={"plugin": LLM, "config": {"client": "openai_compatible", "max_attempts": 3}})
        sc = ScenarioManifest.model_validate({**base.model_dump(mode="json"),
                                              "budget": {"max_steps": 40, "max_model_calls": 6,
                                                         "max_wall_seconds": 600}})
        m = make_manifest(run_id=f"run_a3_orders_{uuid.uuid4().hex[:6]}", project_id="a3", scenario=sc, package=pkg,
                          registry=reg, config={"initial_check_horizon": 0})
        return run_local(m, pkg, reg)
    finally:
        svc.close()


if __name__ == "__main__":
    sys.exit(main_real() if "--real" in sys.argv[1:] else main_protocol())
