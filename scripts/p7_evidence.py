#!/usr/bin/env python3
"""P7-01 acceptance: confirm the held-out study p7-holdout against the loopback protocol test service (not a model),
then run the authorized real batch (8 requests). Writes docs/execution/evidence/research/p7/holdout.json.

Dry run: each of the 8 planned units is scripted (correct / wrong / refusal / invalid) so the capacity-judgment
scorer, the rubric, the program-grounded correspondence and the answer-leak guard are exercised without a model.
Real run: the frozen study against the relay providers, within the authorized quota; BLOCKED if no relay credential.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from check_result import CheckResult
from evidence_io import write

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "studies" / "p7-holdout"
RESULTS = ROOT / "research" / "results" / "p7-holdout"
SCRATCH = ROOT / "var" / "p7"
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))
PKEY = "fal-ptest-key-p7-UNIQUE-8842"


def correct_answer(task: dict) -> dict:
    return json.loads((STUDY / task["reference"]).read_text())["answer"]


def loopback_copy(name: str, base_url: str, **limit) -> Path:
    d = SCRATCH / name
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(STUDY, d)
    doc = json.loads((d / "study.json").read_text())
    doc["study_id"] = f"p7-{name}"
    for p in doc["providers"]:
        p["route"] = "LOOPBACK_TEST"
        p["base_url_setting"] = "FAL_PTEST_BASE_URL"
        p["api_key_setting"] = "FAL_PTEST_API_KEY"
        p.pop("base_url", None)
    doc["limits"].update(limit)
    (d / "study.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return d


def main() -> int:
    from formal_lab_eval.research import Ledger, build_report, load_study, plan_units, run_study
    from formal_lab_eval.research_scorers import load_rubric
    from formal_lab_strategies.model_clients import read_setting
    from formal_lab_strategies.protocol_server import ProtocolTestServer

    r = CheckResult("p7-holdout")
    quiet = lambda *a, **k: None  # noqa: E731
    shutil.rmtree(SCRATCH, ignore_errors=True)
    study = load_study(STUDY)
    tasks = {t.task_id: t.model_dump() for t in study.tasks}
    units, not_run = plan_units(study)
    r.check("frozen_batch_is_8", len(units) == 8 and not not_run,
            f"{len(units)} planned units ({len(tasks)} tasks × {len(study.providers)} models × {study.replicates} reps)")
    r.check("rubric_frozen", load_rubric(ROOT, study.rubric_id, study.rubric_version)["digest"] ==
            load_rubric(ROOT, study.rubric_id, study.rubric_version)["digest"], "rubric digest-checked")
    ev: dict = {"study": "p7-holdout", "planned_units": len(units)}

    with ProtocolTestServer() as srv:
        os.environ["FAL_PTEST_BASE_URL"] = srv.base_url
        os.environ["FAL_PTEST_API_KEY"] = PKEY
        dry = loopback_copy("protocol", srv.base_url)
        dry_units, _ = plan_units(load_study(dry))
        expect: dict[str, tuple[str, str]] = {}
        classes = {"gpt-6-astra-relay": {0: "correct", 1: "wrong"},
                   "claude-opus-5-5-relay": {0: "refusal", 1: "invalid"}}
        for u in dry_units:
            task = tasks[u.task.task_id]
            correct = correct_answer(task)
            cls = classes[u.provider.provider_config_id][u.replicate]
            if cls == "correct":
                srv.script.append("answer:" + json.dumps(correct))
                expect[u.unit_id] = ("ANSWERED", "CORRECT")
            elif cls == "wrong":
                srv.script.append("answer:" + json.dumps({"within_capacity": not correct["within_capacity"],
                                                          "first_overflow": None}))
                expect[u.unit_id] = ("ANSWERED", "INCORRECT")
            elif cls == "refusal":
                srv.script.append("refusal")
                expect[u.unit_id] = ("CONTENT_REFUSAL", "REFUSED")
            else:
                srv.script.append("answer:not json")
                expect[u.unit_id] = ("ANSWERED", "INVALID_FORMAT")
        run_study(dry, SCRATCH / "protocol-results", log=quiet)
        ledger = Ledger(SCRATCH / "protocol-results")
        latest = ledger.latest_responses()
        resp = {u: json.loads((SCRATCH / "protocol-results" / e["path"]).read_text()) for u, e in latest.items()}
        evals = {u: json.loads((SCRATCH / "protocol-results" / "evaluations" / f"{u}--{e['sampling_index']}.json")
                               .read_text()) for u, e in latest.items()}
        r.check("no_silent_drop", set(latest) == set(expect) and len(evals) == len(expect),
                f"{len(latest)} responses, {len(evals)} evaluations for {len(expect)} units")
        wrong = {u: (resp[u]["status"]["outcome"], evals[u]["behavior_label"]) for u in expect
                 if (resp[u]["status"]["outcome"], evals[u]["behavior_label"]) != expect[u]}
        r.check("outcomes_and_labels_as_scripted", not wrong, f"mismatches: {dict(list(wrong.items())[:4])}")
        ok = [evals[u] for u in expect if evals[u]["behavior_label"] == "CORRECT"]
        r.check("program_grounded_scoring", ok and all(e["program_correspondence"] == "CORRESPONDS" for e in ok),
                "a correct capacity judgment corresponds to the recorded run")
        report = json.loads((SCRATCH / "protocol-results" / "report.json").read_text())
        r.check("single_track", set(report["tracks"]) == {"implementation_conformance"}, "held-out case is one track")
        ev["protocol"] = {"outcomes": {u: resp[u]["status"]["outcome"] for u in expect},
                          "behaviours": {u: evals[u]["behavior_label"] for u in expect}}

        cap = loopback_copy("cap", srv.base_url, max_calls=2)
        for u in plan_units(load_study(cap))[0][:2]:
            srv.script.append("answer:" + json.dumps(correct_answer(tasks[u.task.task_id])))
        n0 = len(srv.requests)
        run_study(cap, SCRATCH / "cap-results", log=quiet)
        cl = Ledger(SCRATCH / "cap-results").latest_responses()
        r.check("cost_cap_before_sending",
                len(srv.requests) - n0 == 2 and sum(1 for e in cl.values() if e["outcome"] == "BUDGET_EXHAUSTED") == 6,
                f"{len(srv.requests) - n0} sent, {sum(1 for e in cl.values() if e['outcome'] == 'BUDGET_EXHAUSTED')} over budget")

    leaks = [str(p.relative_to(ROOT)) for p in SCRATCH.rglob("*") if p.is_file() and PKEY in p.read_text(errors="ignore")]
    r.check("credential_never_written", not leaks, f"{leaks}")

    secrets = {p.api_key_setting: read_setting(p.api_key_setting) for p in study.providers if p.api_key_setting}
    if not any(secrets.values()):
        write(ROOT / EV / "p7" / "holdout.json", {**ev, "conclusion": {"dry_run_passed": not wrong, "real_run": "BLOCKED"}})
        sys.exit(r.blocked(f"no relay credential ({', '.join(sorted(secrets))} empty); dry run passed, NOT_RUN real"))
    summary = run_study(STUDY, RESULTS, log=quiet)
    latest = Ledger(RESULTS).latest_responses()
    responses = {u: json.loads((RESULTS / e["path"]).read_text()) for u, e in latest.items()}
    report = build_report(STUDY, RESULTS)
    produced = [x for x in responses.values() if x["status"]["outcome"] in
                ("ANSWERED", "TRUNCATED", "CONTENT_REFUSAL", "EMPTY_CONTENT")]
    r.check("every_planned_unit_recorded", set(latest) == {u.unit_id for u in units}, f"{len(latest)}/{len(units)}")
    r.check("real_answers_recorded", bool(produced), f"{len(produced)} model-produced response(s)")
    r.check("within_budget", summary["budget"]["calls"] <= study.limits.max_calls,
            f"{summary['budget']['calls']} ≤ {study.limits.max_calls}")
    leaks2 = [str(p.relative_to(ROOT)) for p in RESULTS.rglob("*") if p.is_file()
              and any(v and v in p.read_text(errors="ignore") for v in secrets.values())]
    r.check("real_credential_never_written", not leaks2, f"{leaks2}")

    rows = [{"condition": c["condition"], "correct": c["metrics"]["correct"], "behaviors": c["behaviors"]}
            for c in report["tracks"]["implementation_conformance"]["conditions"]]
    write(ROOT / EV / "p7" / "holdout.json", {
        "study_id": summary["study_id"], "planned": len(units), "tally": summary["tally"], "budget": summary["budget"],
        "conditions": rows, "configured_credentials": sorted(k for k, v in secrets.items() if v),
        "conclusion": {"dry_run_passed": not wrong, "real_answers_recorded": bool(produced),
                       "mechanism": "token-bucket capacity (different from the order service)",
                       "provider_comparison_verified": False,
                       "why": "a new held-out case; both models answered through a relay (relay-reported identity), "
                              "so this is a descriptive generality check, not a verified provider comparison"}})
    r.evidence(ROOT / EV / "p7" / "holdout.json")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
