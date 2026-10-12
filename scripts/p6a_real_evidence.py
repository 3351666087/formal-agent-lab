#!/usr/bin/env python3
"""P6A real-endpoint verification: study p6a-real (the minimal ordinary-business task) against the configured,
authorized endpoints only. BLOCKED when none is configured — the protocol test service never stands in for a
provider. Resume semantics apply: a persisted real answer is reused, so re-running this check does not buy the same
sample again. Writes docs/execution/evidence/research/p6a/real-endpoint.json.

    uv run --frozen python scripts/p6a_real_evidence.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from check_result import CheckResult
from evidence_io import write

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "studies" / "p6a-real"
RESULTS = ROOT / "research" / "results" / "p6a-real"
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))


def main() -> int:
    from formal_lab_contracts.research import MODEL_PRODUCED
    from formal_lab_eval.research import Ledger, load_study, plan_units, run_study
    from formal_lab_strategies.model_clients import read_setting

    r = CheckResult("p6a-real")
    study = load_study(STUDY)
    secrets = {p.api_key_setting: read_setting(p.api_key_setting) for p in study.providers if p.api_key_setting}
    configured = sorted(k for k, v in secrets.items() if v)
    if not configured:
        sys.exit(r.blocked(f"no authorized endpoint configured ({', '.join(sorted(secrets))} all empty); the protocol "
                           "test service does not stand in for a provider"))
    summary = run_study(STUDY, RESULTS, log=lambda *a, **k: None)
    units, _ = plan_units(study)
    latest = Ledger(RESULTS).latest_responses()
    responses = {u: json.loads((RESULTS / e["path"]).read_text()) for u, e in latest.items()}
    r.check("every_unit_recorded", set(latest) == {u.unit_id for u in units}, f"{len(latest)}/{len(units)} units")
    per_provider: dict[str, dict] = {}
    for p in study.providers:
        mine = [responses[u.unit_id] for u in units if u.provider.provider_config_id == p.provider_config_id
                and u.unit_id in responses]
        per_provider[p.provider_config_id] = {
            "route": str(p.route), "model_requested": p.model, "credential_setting": p.api_key_setting,
            "configured": p.api_key_setting in configured,
            "outcomes": [x["status"]["outcome"] for x in mine],
            "model_returned": sorted({str(x["call"]["model_returned"]) for x in mine}),
            "model_identity": sorted({x["call"]["model_identity"] for x in mine}),
            "usage": [{k: x["cost"][k] for k in ("usage_known", "input_tokens", "output_tokens", "reasoning_tokens",
                                                 "http_attempts", "possibly_billed_unconfirmed", "latency_ms")}
                      for x in mine],
            "notes": [x["status"]["note"] for x in mine if x["status"]["note"]]}
    real = [x for x in responses.values() if x["call"]["route"] in ("COMPATIBLE_RELAY", "OFFICIAL_NATIVE")
            and x["status"]["outcome"] in MODEL_PRODUCED]
    r.check("real_model_answer_recorded", bool(real),
            f"{len(real)} model-produced response(s) from a real route: "
            f"{sorted({(x['call']['route'], x['call']['model_returned']) for x in real})}")
    r.check("raw_body_persisted", all(x["raw"]["body"] is not None for x in real), "the provider body as returned")
    r.check("identity_recorded", all(x["call"]["model_identity"] in ("RELAY_REPORTED", "CONFIRMED_BY_PROVIDER",
                                                                       "UNKNOWN") for x in real),
            "each real answer names its identity status")
    r.check("relay_never_recorded_as_official",
            all(x["call"]["route"] == "COMPATIBLE_RELAY" for x in responses.values()
                if "relay" in x["call"]["provider_config_id"]), "a relay route stays COMPATIBLE_RELAY")
    r.check("within_budget", summary["budget"]["calls"] <= study.limits.max_calls,
            f"{summary['budget']['calls']} call(s) ≤ {study.limits.max_calls}")
    leaks = [str(p.relative_to(ROOT)) for p in RESULTS.rglob("*") if p.is_file()
             and any(v and v in p.read_text(errors="ignore") for v in secrets.values())]
    r.check("credential_never_written", not leaks, f"files containing a configured credential: {leaks}")
    answered = {x["call"]["provider_config_id"] for x in real}
    supported = len(answered) == len(study.providers) and all(x["call"]["route"] == "OFFICIAL_NATIVE" for x in real)
    for pid, st in per_provider.items():
        if not st["configured"]:
            r.note(f"{pid}: BLOCKED — {st['credential_setting']} is not configured; {st['outcomes']}")
    out = ROOT / EV / "p6a" / "real-endpoint.json"
    write(out, {"study": study.study_id, "configured_credentials": configured, "providers": per_provider,
                "tally": summary["tally"], "budget": summary["budget"],
                "conclusion": {"real_answer_recorded": bool(real),
                               "routes": sorted({x["call"]["route"] for x in real}),
                               "provider_comparison_supported": supported,
                               "why": "a provider conclusion needs every compared provider answering on a route "
                                      "whose identity is verifiable (OFFICIAL_NATIVE)"}})
    r.evidence(out)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
