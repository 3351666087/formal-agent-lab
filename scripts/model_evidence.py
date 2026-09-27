#!/usr/bin/env python3
"""Evidence for model-assisted strategies against the configured endpoint (P2-039 / P2-045 / P2-046).

Uses the existing configuration (FAL_LLM_* from the environment or the git-ignored .env). Without a key every check
is reported NOT_RUN with that reason — nothing is simulated in its place.

What is claimed for a real model is only what can be reproduced: the *request* a strategy sends for given inputs,
and the completeness of the evidence (every call recorded with the configured model label, the model the provider
says answered, the request configuration, attempts, outcome and usage as reported). Answers and the trajectories
that follow them are reported, not claimed to repeat.

Checks
  requests       task-model on state-delay seed 1, twice: the first request (built before any answer) is identical.
  resume         the same run stopped after step 4 and continued in a fresh process: the planner checkpoint at the
                 boundary is restored exactly (digest), events continue without gaps, every call has its evidence.
  per_step       the per-step model planner on normal seed 1: call records keep configured vs returned model,
                 usage reported or flagged unreported, attempts and outcome kinds.
  mixed          two dispatchers — model planner + Z3 planner — on the platform kernel (P2-039).

Writes docs/execution/evidence/phase2/model/evidence.json and summary.md; never writes the key.

    scripts/in-vm.sh 'uv run --frozen python scripts/model_evidence.py'
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from formal_lab_contracts import digest_of
from formal_lab_example_scheduling.__main__ import EVALUATORS
from formal_lab_example_scheduling.scenarios import STRATEGIES, model_package, scenario, two_dispatchers
from formal_lab_runtime import default_registry, make_manifest, run_local
from formal_lab_runtime.local_runner import LocalRunState
from formal_lab_runtime.settings import get_setting

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/execution/evidence/phase2/model"


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def call_view(c: dict) -> dict:
    return {"call_id": c.get("call_id"), "outcome": c.get("outcome"), "attempts": c.get("attempts"),
            "model_requested": c.get("model_requested"), "model_returned": c.get("model_returned"),
            "usage_reported": c.get("usage_reported"), "input_tokens": c.get("input_tokens"),
            "output_tokens": c.get("output_tokens"), "unconfirmed": c.get("unconfirmed"),
            "latency_ms": round(c.get("latency_ms") or 0, 1), "request_digest": sha(c.get("request")),
            "response_digest": sha(c.get("response")) if c.get("response") is not None else None,
            "error": (c.get("error") or "")[:200] or None}


def complete(c: dict) -> bool:
    ok = c.get("outcome") in ("OK", "FORMAT_ERROR", "TRANSPORT_ERROR") and c.get("model_requested") \
        and c.get("request") and c.get("attempts", 0) >= 1
    if c.get("outcome") == "OK":
        ok = ok and c.get("model_returned") is not None and c.get("response") is not None
    return bool(ok)


def run(reg, pkg, sc, run_id: str, **kw):
    m = make_manifest(run_id=run_id, project_id="evidence", scenario=sc, package=pkg, registry=reg, seed=sc.seed,
                      evaluators=EVALUATORS)
    return run_local(m, pkg, reg, **kw)


def summary_of(res) -> dict:
    return {"status": res.status.value, "termination_reason": res.termination_reason.value
            if res.termination_reason else None, "steps": res.usage.steps, "model_calls": res.usage.model_calls,
            "tokens": res.usage.input_tokens + res.usage.output_tokens,
            "trajectory_digest": sha([(e.logical_step, e.payload["outcome"]["action"], e.payload["outcome"]["status"])
                                      for e in res.events if str(e.event_type) == "ACTION_OUTCOME"]),
            "metrics": {m.metric_id: m.value for m in res.metrics if m.metric_id in ("orders_completed", "delay_cost")},
            "calls": [call_view(c) for c in res.model_calls]}


RESUME = """
import json, sys
from formal_lab_example_scheduling.scenarios import model_package
from formal_lab_runtime import resume_local
res = resume_local(json.load(open(sys.argv[1])), model_package())
print(json.dumps({"status": res.status.value, "steps": res.usage.steps,
                  "seqs": [e.seq for e in res.events],
                  "kinds": [str(e.event_type) for e in res.events],
                  "checkpoints": [e.payload["digest"] for e in res.events if str(e.event_type) == "PLANNER_CHECKPOINT"],
                  "calls": res.model_calls}))
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    key = get_setting("FAL_LLM_API_KEY") or ""
    config = {"base_url_set": bool(get_setting("FAL_LLM_BASE_URL")), "model_label": get_setting("FAL_LLM_MODEL"),
              "provider": get_setting("FAL_LLM_PROVIDER")}
    report: dict = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "config": config, "checks": {}}
    if not key:
        for name in ("requests", "resume", "per_step", "mixed"):
            report["checks"][name] = {"status": "NOT_RUN", "reason": "FAL_LLM_API_KEY not configured"}
        (OUT / "evidence.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(report["checks"]))
        return 0
    reg = default_registry()
    pkg = model_package()
    checks = report["checks"]

    # requests: the same inputs produce the same first request
    sc = scenario("state-delay", pkg, seed=1, strategy=STRATEGIES["task-model"])
    a, b = run(reg, pkg, sc, "run_ev_a"), run(reg, pkg, sc, "run_ev_b")
    first_a = a.model_calls[0]["request"] if a.model_calls else None
    first_b = b.model_calls[0]["request"] if b.model_calls else None
    checks["requests"] = {
        "status": "PASS" if first_a is not None and first_a == first_b else "FAIL",
        "claim": "the first request (before any model answer) is identical for the same model, scenario and seed",
        "first_request_digest": [sha(first_a), sha(first_b)],
        "runs": [summary_of(a), summary_of(b)],
        "answers_identical": [c["response"] for c in a.model_calls] == [c["response"] for c in b.model_calls],
        "trajectories_identical": summary_of(a)["trajectory_digest"] == summary_of(b)["trajectory_digest"],
        "note": "answers and trajectories are reported, not claimed: a real model need not answer the same twice",
    }

    # resume: fresh process continues from the checkpoint, evidence complete
    part = run(reg, pkg, sc, "run_ev_resume", stop_after=4)
    assert isinstance(part, LocalRunState)
    boundary = part.carry.checkpoints.get("dispatcher") or {}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(part.to_json()))
        out = subprocess.run([sys.executable, "-c", RESUME, str(path)], capture_output=True, text=True, check=True,
                             cwd=ROOT).stdout.strip().splitlines()[-1]
    resumed = json.loads(out)
    calls = resumed["calls"]  # the resumed result carries the calls made before the stop as well
    boundary_digest = digest_of(boundary).value if boundary else None
    pre_stop = [e.payload["digest"] for e in part.drafts if str(e.event_type) == "PLANNER_CHECKPOINT"]
    contiguous = resumed["seqs"] == list(range(1, len(resumed["seqs"]) + 1))
    restored = bool(pre_stop) and pre_stop[-1] == boundary_digest and resumed["checkpoints"][:len(pre_stop)] == pre_stop
    checks["resume"] = {
        "status": "PASS" if restored and contiguous and "RECOVERY" in resumed["kinds"] and calls
        and all(complete(c) for c in calls) else "FAIL",
        "claim": "a fresh process restores the planner checkpoint at the boundary and every call keeps its evidence",
        "boundary_checkpoint_digest": boundary_digest, "boundary_is_last_recorded_checkpoint": restored,
        "resumed_status": resumed["status"], "resumed_steps": resumed["steps"],
        "events_contiguous": contiguous,
        "calls_before_stop": len(part.model_calls), "calls_total": len(resumed["calls"]),
        "calls_complete": all(complete(c) for c in calls),
        "calls": [call_view(c) for c in resumed["calls"]],
    }

    # per_step: the per-step model planner's call records
    ps = run(reg, pkg, scenario("normal", pkg, seed=1, strategy=STRATEGIES["llm"]), "run_ev_llm")
    returned = sorted({c.get("model_returned") or "-" for c in ps.model_calls})
    checks["per_step"] = {
        "status": "PASS" if ps.model_calls and all(complete(c) for c in ps.model_calls) else "FAIL",
        "claim": "every call records the configured label, the model the provider returned, request config, "
                 "attempts, outcome and usage as reported",
        "model_label": config["model_label"], "models_returned": returned,
        "label_differs_from_returned": any(r != config["model_label"] for r in returned),
        "outcomes": {k: sum(1 for c in ps.model_calls if c.get("outcome") == k)
                     for k in ("OK", "FORMAT_ERROR", "TRANSPORT_ERROR")},
        "usage_unreported_calls": ps.usage.unreported_calls, "unconfirmed_calls": ps.usage.unconfirmed_calls,
        "run": summary_of(ps),
    }

    # mixed: model planner + symbolic planner sharing the line (P2-039)
    mx = run(reg, pkg, two_dispatchers(pkg, seed=1, strategies=("llm", "z3")), "run_ev_mixed")
    checks["mixed"] = {
        "status": "PASS" if mx.status.value in ("SUCCEEDED", "BUDGET_EXHAUSTED", "FAILED") and mx.model_calls
        else "FAIL",
        "claim": "a real-model participant and a Z3 participant take turns on one run; per-actor usage is kept apart",
        "run": summary_of(mx), "actor_usage": mx.actor_usage,
    }

    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if key in text:
        raise SystemExit("refusing to write evidence that contains the API key")
    (OUT / "evidence.json").write_text(text)
    lines = ["# Model-assisted strategies: evidence against the configured endpoint", "",
             f"Generated {report['generated_at']} by `scripts/model_evidence.py`; model label "
             f"`{config['model_label']}`. Real-model reruns claim only request and evidence reproducibility.", "",
             "| check | status | claim |", "|---|---|---|"]
    lines += [f"| {k} | {v['status']} | {v.get('claim', v.get('reason', ''))} |" for k, v in checks.items()]
    lines += ["", "Details (digests, per-call records, run summaries) are in `evidence.json`."]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: v["status"] for k, v in checks.items()}))
    return 0 if all(v["status"] == "PASS" for v in checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
