#!/usr/bin/env python3
"""P6B acceptance: first confirm the fields, scoring and cost caps of the frozen study `p6b-eval` against the loopback
protocol test service (not a model), then run the authorized real batch.

Dry run (loopback): every planned unit is scripted — correct and wrong answers on both tracks, a refusal, a
truncation, an invalid format and an empty answer — so the isolation-judgment and shortest-plan scorers, the rubric
digest and signals, the two-track report, the answer-leak guard and the cost cap are all exercised without a model.
Real run: the frozen study against the relay providers, within the authorized quota. Writes
docs/execution/evidence/research/p6b/{protocol.json,eval.json}.

    uv run --frozen python scripts/p6b_evidence.py
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
STUDY = ROOT / "research" / "studies" / "p6b-eval"
RESULTS = ROOT / "research" / "results" / "p6b-eval"
SCRATCH = ROOT / "var" / "p6b"
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))
PKEY = "fal-ptest-key-6b-UNIQUE-5521"


def correct_answer(task: dict) -> dict:
    return json.loads((STUDY / task["reference"]).read_text())["answer"]


def files_with(root: Path, needle: str) -> list[str]:
    return [str(p.relative_to(ROOT)) for p in root.rglob("*") if p.is_file() and needle in p.read_text(errors="ignore")]


def loopback_copy(name: str, base_url: str, **limit) -> Path:
    d = SCRATCH / name
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(STUDY, d)
    doc = json.loads((d / "study.json").read_text())
    doc["study_id"] = f"p6b-{name}"
    for p in doc["providers"]:
        p["route"] = "LOOPBACK_TEST"
        p["base_url_setting"] = "FAL_PTEST_BASE_URL"
        p["api_key_setting"] = "FAL_PTEST_API_KEY"
        p.pop("base_url", None)
    for c in doc["comparisons"]:
        if c["vary"] == "provider":
            c["a"], c["b"] = "gpt-6-astra-relay", "claude-opus-5-5-relay"
    doc["limits"].update(limit)
    (d / "study.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return d


def main() -> int:
    from formal_lab_eval.research import Ledger, build_report, load_study, plan_units, run_study
    from formal_lab_eval.research_scorers import load_rubric, rubric_digest
    from formal_lab_strategies.protocol_server import ProtocolTestServer

    r = CheckResult("p6b")
    quiet = lambda *a, **k: None  # noqa: E731
    shutil.rmtree(SCRATCH, ignore_errors=True)
    study = load_study(STUDY)
    tasks = {t.task_id: t.model_dump() for t in study.tasks}
    units, not_run = plan_units(study)
    r.check("frozen_batch_is_24", len(units) == 24 and not not_run,
            f"{len(units)} planned units ({len(tasks)} tasks × {len(study.providers)} models × {study.replicates} reps)")

    # the frozen rubric: version + self-digest, and recorded in the report
    rubric = load_rubric(ROOT, study.rubric_id, study.rubric_version)
    r.check("rubric_frozen", rubric["digest"] == rubric_digest(rubric) and len(rubric["dimensions"]) == 6,
            f"rubric {study.rubric_id}@{study.rubric_version} digest {rubric['digest'][:12]}, "
            f"{len(rubric['dimensions'])} dimensions")

    # answer-leak guard: the real study is clean; a copy with the answer pasted into an input is rejected
    leak = SCRATCH / "leak"
    shutil.copytree(STUDY, leak)
    ans = json.loads((leak / "reference" / "isolation-defect.json").read_text())["answer"]
    (leak / "inputs" / "isolation-defect.md").write_text((leak / "inputs" / "isolation-defect.md").read_text()
                                                         + "\n" + json.dumps(ans))
    from formal_lab_contracts.errors import InvalidInput
    try:
        load_study(leak)
        leaked_rejected = False
    except InvalidInput as exc:
        leaked_rejected = "ANSWER_LEAK" in exc.message
    r.check("answer_leak_rejected", leaked_rejected, "load_study rejects a reference answer pasted into a task input")

    ev: dict = {"study": "p6b-eval", "planned_units": len(units), "rubric_digest": rubric["digest"]}

    with ProtocolTestServer() as srv:
        os.environ["FAL_PTEST_BASE_URL"] = srv.base_url
        os.environ["FAL_PTEST_API_KEY"] = PKEY
        dry = loopback_copy("protocol", srv.base_url)
        dry_units, _ = plan_units(load_study(dry))
        # rep0 → the correct answer; rep1 → a varied class so every outcome/behaviour appears
        classes = ["wrong", "refusal", "truncate", "empty", "invalid", "wrong"]
        expect: dict[str, tuple[str, str]] = {}
        for u in dry_units:
            task = tasks[u.task.task_id]
            correct = correct_answer(task)
            if u.unit_id.endswith(".r0"):
                srv.script.append("answer:" + json.dumps(correct))
                expect[u.unit_id] = ("ANSWERED", "CORRECT")
            else:
                cls = classes[sorted(tasks).index(u.task.task_id) % len(classes)]
                if cls == "refusal":
                    srv.script.append("refusal")
                    expect[u.unit_id] = ("CONTENT_REFUSAL", "REFUSED")
                elif cls == "truncate":
                    srv.script.append("truncate:" + json.dumps(correct)[:12])
                    expect[u.unit_id] = ("TRUNCATED", "INVALID_FORMAT")
                elif cls == "empty":
                    srv.script.append("empty")
                    expect[u.unit_id] = ("EMPTY_CONTENT", "EMPTY")
                elif cls == "invalid":
                    srv.script.append("answer:not json at all")
                    expect[u.unit_id] = ("ANSWERED", "INVALID_FORMAT")
                elif "isolation_holds" in correct:
                    srv.script.append("answer:" + json.dumps({"isolation_holds": not correct["isolation_holds"],
                                                              "violations": []}))
                    expect[u.unit_id] = ("ANSWERED", "INCORRECT")
                else:  # a valid but longer-than-shortest plan for this base → PARTIAL
                    sample = json.loads((STUDY / task["reference"]).read_text())["sample"]
                    longer = ["toggle", "reset", "toggle", "toggle", "toggle"] if sample == "lamp" \
                        else ["walk", "walk", "walk"]
                    srv.script.append("answer:" + json.dumps({"reachable": True, "plan": longer}))
                    expect[u.unit_id] = ("ANSWERED", "PARTIAL")
        run_study(dry, SCRATCH / "protocol-results", log=quiet)
        ledger = Ledger(SCRATCH / "protocol-results")
        latest = ledger.latest_responses()
        resp = {u: json.loads((SCRATCH / "protocol-results" / e["path"]).read_text()) for u, e in latest.items()}
        evals = {u: json.loads((SCRATCH / "protocol-results" / "evaluations" / f"{u}--{e['sampling_index']}.json")
                               .read_text()) for u, e in latest.items()}
        r.check("no_silent_drop", set(latest) == set(expect) and len(evals) == len(expect),
                f"{len(latest)} responses, {len(evals)} evaluations for {len(expect)} planned units")
        wrong = {u: (resp[u]["status"]["outcome"], evals[u]["behavior_label"]) for u in expect
                 if (resp[u]["status"]["outcome"], evals[u]["behavior_label"]) != expect[u]}
        r.check("outcomes_and_labels_as_scripted", not wrong, f"mismatches: {dict(list(wrong.items())[:4])}")
        order = [(e["event"], e["unit_id"]) for e in ledger.events()]
        r.check("raw_saved_before_scoring",
                all(order.index(("response", u)) < order.index(("evaluation", u)) for u in expect), "ledger order")
        iso_ok = [evals[u] for u in expect if u.startswith("isolation-") and u.endswith(".r0")]
        r.check("isolation_program_grounded",
                iso_ok and all(e["program_correspondence"] == "CORRESPONDS" and e["model_internal"] == "CORRECT"
                               for e in iso_ok), "correct isolation answers correspond to the recorded run")
        iso_signals = [e for e in iso_ok if e["rubric_signals"]]
        r.check("rubric_signals_recorded", iso_signals and all(
            "states_scope" in e["rubric_signals"] and "names_isolation_risk" in e["rubric_signals"] for e in iso_signals),
            "heuristic rubric signals recorded on isolation units (recorded-only, not a pass)")
        syn = [evals[u] for u in expect if not u.startswith("isolation-")]
        r.check("synthetic_program_not_applicable",
                all(e["program_correspondence"] == "NOT_APPLICABLE" for e in syn), "synthetic tasks N/A, not a pass")
        report = json.loads((SCRATCH / "protocol-results" / "report.json").read_text())
        r.check("tracks_apart_with_rubric_digest",
                set(report["tracks"]) == {"implementation_conformance", "synthetic_representation"}
                and report["rubric_digest"] == rubric["digest"] and "correct" not in report, "two tracks, never pooled")
        cmps = {(c["vary"], c["a"], c["b"]) for t in report["tracks"].values() for c in t["comparisons"]}
        r.check("comparisons_present",
                {("provider", "gpt-6-astra-relay", "claude-opus-5-5-relay"), ("representation", "garage", "library"),
                 ("representation", "courier", "approval")} <= cmps, f"{sorted(cmps)}")
        ev["protocol"] = {"outcomes": {u: resp[u]["status"]["outcome"] for u in expect},
                          "behaviours": {u: evals[u]["behavior_label"] for u in expect}}

        # cost cap: a 3-call copy exhausts the budget before sending the rest
        cap = loopback_copy("cap", srv.base_url, max_calls=3)
        for u in plan_units(load_study(cap))[0][:3]:
            srv.script.append("answer:" + json.dumps(correct_answer(tasks[u.task.task_id])))
        n0 = len(srv.requests)
        run_study(cap, SCRATCH / "cap-results", log=quiet)
        cl = Ledger(SCRATCH / "cap-results").latest_responses()
        exhausted = sum(1 for e in cl.values() if e["outcome"] == "BUDGET_EXHAUSTED")
        r.check("cost_cap_before_sending", len(srv.requests) - n0 == 3 and exhausted == len(dry_units) - 3,
                f"{len(srv.requests) - n0} sent, {exhausted} BUDGET_EXHAUSTED of {len(dry_units)}")

    leaks = files_with(SCRATCH, PKEY)
    r.check("credential_never_written", not leaks, f"files with the test key: {leaks}")

    # real batch (within the authorized quota); BLOCKED if no relay credential
    from formal_lab_strategies.model_clients import read_setting
    secrets = {p.api_key_setting: read_setting(p.api_key_setting) for p in study.providers if p.api_key_setting}
    if not any(secrets.values()):
        write(ROOT / EV / "p6b" / "protocol.json", {**ev, "conclusion": {"dry_run_passed": not wrong}})
        sys.exit(r.blocked(f"no relay credential configured ({', '.join(sorted(secrets))} all empty); dry run passed"))
    summary = run_study(STUDY, RESULTS, log=quiet)
    latest = Ledger(RESULTS).latest_responses()
    responses = {u: json.loads((RESULTS / e["path"]).read_text()) for u, e in latest.items()}
    report = build_report(STUDY, RESULTS)
    produced = [x for x in responses.values() if x["status"]["outcome"] in
                ("ANSWERED", "TRUNCATED", "CONTENT_REFUSAL", "EMPTY_CONTENT")]
    r.check("every_planned_unit_recorded", set(latest) == {u.unit_id for u in units},
            f"{len(latest)}/{len(units)} units recorded")
    r.check("real_answers_recorded", bool(produced) and all(
        x["raw"]["body"] is not None for x in produced if x["status"]["outcome"] != "EMPTY_CONTENT"),
            f"{len(produced)} model-produced response(s); raw bodies kept")
    r.check("within_budget", summary["budget"]["calls"] <= study.limits.max_calls,
            f"{summary['budget']['calls']} calls ≤ {study.limits.max_calls}")
    r.check("two_tracks_reported_apart", set(report["tracks"]) == {"implementation_conformance",
                                                                   "synthetic_representation"}, "")
    leaks2 = [str(p.relative_to(ROOT)) for p in RESULTS.rglob("*") if p.is_file()
              and any(v and v in p.read_text(errors="ignore") for v in secrets.values())]
    r.check("real_credential_never_written", not leaks2, f"{leaks2}")

    tracks = {name: {"outcomes": t["outcomes"], "conditions": [{"condition": c["condition"],
              "correct": c["metrics"]["correct"], "behaviors": c["behaviors"]} for c in t["conditions"]],
              "comparisons": [{k: c.get(k) for k in ("vary", "a", "b", "n_pairs", "mean_diff_b_minus_a", "reading_note")}
                              for c in t["comparisons"]]} for name, t in report["tracks"].items()}
    write(ROOT / EV / "p6b" / "protocol.json", {**ev, "conclusion": {"dry_run_passed": not wrong}})
    write(ROOT / EV / "p6b" / "eval.json", {
        "study_id": summary["study_id"], "planned": len(units), "tally": summary["tally"],
        "budget": summary["budget"], "rubric_digest": rubric["digest"], "tracks": tracks,
        "configured_credentials": sorted(k for k, v in secrets.items() if v),
        "conclusion": {"real_answers_recorded": bool(produced), "tracks_apart": True,
                       "provider_comparison_verified": False,
                       "why": "both real models answered through a relay (relay-reported identity); the official "
                              "routes are not configured, so no verified provider comparison is drawn"}})
    r.evidence(ROOT / EV / "p6b" / "eval.json")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
