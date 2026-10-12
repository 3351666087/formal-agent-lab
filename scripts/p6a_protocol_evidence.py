#!/usr/bin/env python3
"""P6A acceptance against the loopback protocol test service (not a model): every planned unit of study p6a-protocol
gets a scripted provider behaviour, so the whole runner — research calls, raw-first records, the two result axes,
scoring, the two-track report — is exercised on: a legal answer, a visible refusal and a content filter inside HTTP
success, empty content, truncation, invalid JSON / schema / type, a model change and an unnamed model, 401, 429,
5xx, 404-model, a malformed body, a lost response, a thinking summary; then budget, cancellation, resume (answered
units reused, unanswered ones called again as new samples, spent budget not regained), rescoring without calls, and
that the credential never reaches a file. Writes docs/execution/evidence/research/p6a/protocol.json.

    uv run --frozen python scripts/p6a_protocol_evidence.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from pathlib import Path

from check_result import CheckResult
from evidence_io import write

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "studies" / "p6a-protocol"
RESULTS = ROOT / "research" / "results" / "p6a-protocol"
SCRATCH = ROOT / "var" / "p6a"
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))
KEY = "fal-ptest-key-6a-UNIQUE-7319"

ORDERS_OK = '{"constant": "slow", "station": "p2", "value": true}'
LAMP_OK = '{"reachable": true, "plan": ["toggle", "toggle", "toggle"]}'
SHORT_OK = '{"reachable": true, "plan": ["express"]}'
# unit → (scripted behaviours in request order, expected call outcome, expected behaviour label)
SCRIPT = {
    "orders-deviation.ptest-openai.S.r0": ([f"answer:{ORDERS_OK}"], "ANSWERED", "CORRECT"),
    "orders-deviation.ptest-openai.S.r1": (['answer:{"constant": "slow", "station": "p1", "value": true}'],
                                           "ANSWERED", "INCORRECT"),
    "orders-deviation.ptest-anthropic.S.r0": (["refusal"], "CONTENT_REFUSAL", "REFUSED"),
    "orders-deviation.ptest-anthropic.S.r1": (["429", f"answer:{ORDERS_OK}"], "ANSWERED", "CORRECT"),
    "orders-deviation.ptest-openai.A.r0": ([f"answer:```json\n{ORDERS_OK}\n```"], "ANSWERED", "CORRECT"),
    "orders-deviation.ptest-openai.A.r1": (["answer:I think station p2 is the slow one."], "ANSWERED",
                                           "INVALID_FORMAT"),
    "orders-deviation.ptest-anthropic.A.r0": (["drop", f"answer:{ORDERS_OK}"], "ANSWERED", "CORRECT"),
    "orders-deviation.ptest-anthropic.A.r1": (["500", "500", "500"], "PROVIDER_ERROR", "NO_MODEL_ANSWER"),
    "lamp-ir-json.ptest-openai.S.r0": ([f"answer:{LAMP_OK}"], "ANSWERED", "CORRECT"),
    "lamp-ir-json.ptest-openai.S.r1": (['answer:{"reachable": true, "plan": ["toggle", "reset", "toggle", "toggle", '
                                        '"toggle"]}'], "ANSWERED", "PARTIAL"),
    "lamp-ir-json.ptest-anthropic.S.r0": (["empty"], "EMPTY_CONTENT", "EMPTY"),
    "lamp-ir-json.ptest-anthropic.S.r1": (['truncate:{"reachable": true, "plan": ["tog'], "TRUNCATED",
                                          "INVALID_FORMAT"),
    "lamp-prose.ptest-openai.S.r0": ([f"answer:{LAMP_OK}"], "ANSWERED", "CORRECT"),
    "lamp-prose.ptest-openai.S.r1": (["other_model"], "ANSWERED", "INVALID_FORMAT"),
    "lamp-prose.ptest-anthropic.S.r0": (["401"], "AUTH_ERROR", "NO_MODEL_ANSWER"),
    "lamp-prose.ptest-anthropic.S.r1": (['answer:{"reachable": false, "plan": []}'], "ANSWERED", "INCORRECT"),
    "shortcut-ir-json.ptest-openai.S.r0": ([f"answer:{SHORT_OK}"], "ANSWERED", "CORRECT"),
    "shortcut-ir-json.ptest-openai.S.r1": (['answer:{"reachable": "yes", "plan": ["express"]}'], "ANSWERED",
                                           "INVALID_FORMAT"),
    "shortcut-ir-json.ptest-anthropic.S.r0": (["no_model"], "ANSWERED", "INVALID_FORMAT"),
    "shortcut-ir-json.ptest-anthropic.S.r1": (["404_model"], "MODEL_UNAVAILABLE", "NO_MODEL_ANSWER"),
    "shortcut-prose.ptest-openai.S.r0": (["content_filter"], "CONTENT_REFUSAL", "REFUSED"),
    "shortcut-prose.ptest-openai.S.r1": (['answer:{"reachable": true, "plan": ["teleport"]}'], "ANSWERED",
                                         "INCORRECT"),
    "shortcut-prose.ptest-anthropic.S.r0": (["malformed"], "MALFORMED_RESPONSE", "NO_MODEL_ANSWER"),
    "shortcut-prose.ptest-anthropic.S.r1": ([f"thinking:{SHORT_OK}"], "ANSWERED", "CORRECT"),
}


def correct_for(unit_id: str) -> str:
    return "answer:" + (ORDERS_OK if unit_id.startswith("orders") else LAMP_OK if unit_id.startswith("lamp")
                        else SHORT_OK)


def copy_study(name: str, **limits: int) -> Path:
    d = SCRATCH / name
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(STUDY, d)
    doc = json.loads((d / "study.json").read_text())
    doc["study_id"] = f"p6a-protocol-{name}"
    doc["limits"].update(limits)
    (d / "study.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return d


def files_contain(root: Path, needle: str) -> list[str]:
    return [str(p.relative_to(ROOT)) for p in root.rglob("*") if p.is_file() and needle in p.read_text(errors="ignore")]


def main() -> int:
    from formal_lab_eval.research import Ledger, build_report, load_study, plan_units, run_study, score_study
    from formal_lab_strategies.protocol_server import ProtocolTestServer

    r = CheckResult("p6a-protocol")
    quiet = lambda *_a, **_k: None  # noqa: E731
    shutil.rmtree(RESULTS, ignore_errors=True)
    shutil.rmtree(SCRATCH, ignore_errors=True)
    os.environ["FAL_PTEST_API_KEY"] = KEY
    units, not_run = plan_units(load_study(STUDY))
    r.check("every_unit_scripted", {u.unit_id for u in units} == set(SCRIPT), f"{len(units)} planned units")
    ev: dict = {"study": "p6a-protocol", "planned_units": len(units), "not_run": not_run}

    with ProtocolTestServer() as srv:
        os.environ["FAL_PTEST_BASE_URL"] = srv.base_url
        for u in units:
            srv.script.extend(SCRIPT[u.unit_id][0])
        run_study(STUDY, RESULTS, log=quiet)
        main_requests = len(srv.requests)
        ledger = Ledger(RESULTS)
        latest = ledger.latest_responses()
        responses = {u: json.loads((RESULTS / e["path"]).read_text()) for u, e in latest.items()}
        evals = {u: json.loads((RESULTS / "evaluations" / f"{u}--{e['sampling_index']}.json").read_text())
                 for u, e in latest.items()}
        r.check("no_silent_drop", set(latest) == set(SCRIPT) and len(evals) == len(SCRIPT),
                f"{len(latest)} response record(s), {len(evals)} evaluation(s) for {len(SCRIPT)} planned units")
        wrong = {u: (responses[u]["status"]["outcome"], evals[u]["behavior_label"]) for u in SCRIPT
                 if (responses[u]["status"]["outcome"], evals[u]["behavior_label"]) != SCRIPT[u][1:]}
        r.check("outcomes_and_labels_as_scripted", not wrong, f"mismatches: {wrong}")
        order = [(e["event"], e["unit_id"]) for e in ledger.events()]
        r.check("raw_saved_before_scoring",
                all(order.index(("response", u)) < order.index(("evaluation", u)) for u in SCRIPT),
                "every response event precedes its evaluation event in the ledger")
        trunc = "lamp-ir-json.ptest-anthropic.S.r1"
        r.check("two_axes_apart", responses[trunc]["status"]["outcome"] == "TRUNCATED"
                and evals[trunc]["answer_status"] == "INVALID_JSON",
                f"{trunc}: call {responses[trunc]['status']['outcome']}, answer {evals[trunc]['answer_status']}")
        refused = responses["orders-deviation.ptest-anthropic.S.r0"]
        r.check("refusal_not_retried", refused["cost"]["http_attempts"] == 1 and refused["raw"]["refusal"],
                f"attempts {refused['cost']['http_attempts']}, refusal {refused['raw']['refusal']!r}")
        r.check("content_filter_is_a_refusal", evals["shortcut-prose.ptest-openai.S.r0"]["refusal_status"]
                == "CONTENT_FILTER", "finish_reason content_filter → CONTENT_REFUSAL / CONTENT_FILTER")
        auth = responses["lamp-prose.ptest-anthropic.S.r0"]["status"]
        r.check("auth_error_is_not_a_refusal", auth["outcome"] == "AUTH_ERROR" and auth["http_status"] == 401,
                f"{auth['outcome']} / {auth['http_status']}")
        lost = responses["orders-deviation.ptest-anthropic.A.r0"]
        r.check("lost_response_possibly_billed", lost["cost"]["possibly_billed_unconfirmed"] == 1
                and lost["status"]["outcome"] == "ANSWERED", "a dropped attempt, then an answer on a new attempt")
        sw = responses["lamp-prose.ptest-openai.S.r1"]["call"]
        unk = responses["shortcut-ir-json.ptest-anthropic.S.r0"]["call"]
        r.check("model_identity_recorded", sw["model_switched"] and unk["model_identity"] == "UNKNOWN",
                f"switched {sw['model_returned']}; unnamed → {unk['model_identity']}")
        th = responses["shortcut-prose.ptest-anthropic.S.r1"]["raw"]
        r.check("reasoning_never_raw", th["reasoning"] == "SUMMARY_ONLY", "a thinking block is a summary only")
        good, bad = evals["orders-deviation.ptest-openai.S.r0"], evals["orders-deviation.ptest-openai.S.r1"]
        r.check("program_grounded_scoring", good["program_correspondence"] == "CORRESPONDS"
                and bad["program_correspondence"] == "DEVIATES",
                "slow[p2] corresponds with the recorded run; slow[p1] deviates")
        syn = [e for u, e in evals.items() if not u.startswith("orders")]
        r.check("synthetic_program_not_applicable",
                all(e["program_correspondence"] == "NOT_APPLICABLE" and next(
                    m for m in e["metrics"] if m["metric_id"] == "program_corresponds")["status"] == "NOT_APPLICABLE"
                    for e in syn), "never filled in as a pass")
        failed = [evals[u] for u in SCRIPT if evals[u]["behavior_label"] == "NO_MODEL_ANSWER"]
        r.check("no_answer_is_missing_not_zero", failed and all(
            next(m for m in e["metrics"] if m["metric_id"] == "correct")["status"] == "MISSING" for e in failed),
            f"{len(failed)} unit(s) without a model answer: correct = MISSING")
        report = json.loads((RESULTS / "report.json").read_text())
        r.check("tracks_never_pooled", set(report["tracks"]) == {"implementation_conformance",
                                                                 "synthetic_representation"}
                and "correct" not in report, f"tracks {sorted(report['tracks'])}")
        r.check("unimplemented_mode_not_run", len(report["not_run"]) == 4,
                f"{len(report['not_run'])} (task, ASSISTED) conditions listed NOT_RUN")
        cmps = {c["vary"] for t in report["tracks"].values() for c in t["comparisons"]}
        r.check("paired_comparisons", {"provider", "representation", "assistance"} <= cmps, f"{sorted(cmps)}")
        ev["main"] = {"requests": main_requests, "outcomes": {u: responses[u]["status"]["outcome"] for u in SCRIPT},
                      "behaviours": {u: evals[u]["behavior_label"] for u in SCRIPT},
                      "answer_status": {u: evals[u]["answer_status"] for u in SCRIPT}}

        # rescoring reuses saved responses and makes no call
        before = len(srv.requests)
        n_eval = sum(1 for e in ledger.events() if e["event"] == "evaluation")
        score_study(STUDY, RESULTS, log=quiet)
        reused = sum(1 for e in ledger.events() if e["event"] == "evaluation") == n_eval
        score_study(STUDY, RESULTS, force=True, log=quiet)
        build_report(STUDY, RESULTS)
        r.check("rescoring_makes_no_call", len(srv.requests) == before and reused,
                "score without --force reuses every evaluation; --force recomputes; no HTTP request either way")

        # budget: a 3-call limit, then a resume that must not regain it
        b = copy_study("budget", max_calls=3)
        for u in units[:3]:
            srv.script.append(correct_for(u.unit_id))
        n0 = len(srv.requests)
        run_study(b, SCRATCH / "budget-results", log=quiet)
        n1 = len(srv.requests)
        run_study(b, SCRATCH / "budget-results", log=quiet)
        bl = Ledger(SCRATCH / "budget-results").latest_responses()
        exhausted = sum(1 for e in bl.values() if e["outcome"] == "BUDGET_EXHAUSTED")
        r.check("budget_checked_before_sending", n1 - n0 == 3 and exhausted == len(units) - 3,
                f"{n1 - n0} request(s) sent, {exhausted} unit(s) BUDGET_EXHAUSTED")
        r.check("budget_not_regained_on_resume", len(srv.requests) == n1,
                "the resumed study rebuilt its counters from the ledger and sent nothing")

        # cancel after four units (two of which fail), then resume
        c = copy_study("cancel")
        srv.script.extend([correct_for(units[0].unit_id), "500", "500", "500", "401", correct_for(units[3].unit_id)])
        stop = threading.Event()
        seen = []

        def after(unit, _res):
            seen.append(unit.unit_id)
            if len(seen) == 4:
                stop.set()

        n2 = len(srv.requests)
        run_study(c, SCRATCH / "cancel-results", cancel=stop, after_unit=after, log=quiet)
        n3 = len(srv.requests)
        cl = Ledger(SCRATCH / "cancel-results").latest_responses()
        cancelled = [u for u, e in cl.items() if e["outcome"] == "CANCELLED"]
        r.check("cancel_checked_before_sending", n3 - n2 == 6 and len(cancelled) == len(units) - 4,
                f"{n3 - n2} request(s) for 4 units (one 500×3, one 401), {len(cancelled)} unit(s) CANCELLED unsent")
        for u in units[1:3] + [u for u in units if u.unit_id in cancelled]:
            srv.script.append(correct_for(u.unit_id))
        summary = run_study(c, SCRATCH / "cancel-results", log=quiet)
        cl2 = Ledger(SCRATCH / "cancel-results").latest_responses()
        r.check("resume_reuses_answers", summary["tally"].get("reused") == 2 and len(srv.requests) - n3 ==
                len(units) - 2 and all(cl2[u.unit_id]["sampling_index"] == 1 for u in units[1:3]),
                f"reused {summary['tally'].get('reused')}, sent {len(srv.requests) - n3}; the two failed units "
                "were called again as new samples")
        ev["resume"] = {"reused": summary["tally"].get("reused"), "new": summary["tally"].get("new")}

    leaks = files_contain(RESULTS, KEY) + files_contain(SCRATCH, KEY)
    r.check("credential_never_written", not leaks, f"files containing the test key: {leaks}")
    out = ROOT / EV / "p6a" / "protocol.json"
    write(out, {**ev, "conclusion": {"all_classes_recorded": not wrong, "tracks_apart": True,
                                     "credential_never_written": not leaks}})
    r.evidence(out)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
