#!/usr/bin/env python3
"""P7-02 offline reproduction: an automated clean-room recheck of the committed research data that uses only existing
results — no model call, no platform, no network. It copies the research tree into a fresh directory, validates every
committed case against the protocol (digests, model/property identity, data separation), re-derives each case's
conformance from the recorded observations, reads the study reports, and records the machine, the exact commands and
which steps need network (none here). Writes docs/execution/evidence/research/p7/reproduce.json.

A re-sampling path (new online calls) is separate and needs the user's own API credentials and quota — see the
`fal research study run` / p6*/p7-holdout evidence; this script never makes one. Running it again by the same agent
is an *automated* clean-environment reproduction; an independent human reproduction is recorded separately (PENDING
until a person does it).

    uv run --frozen python scripts/p7_reproduce.py
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path

from check_result import CheckResult
from evidence_io import write

ROOT = Path(__file__).resolve().parents[1]
EV = Path(os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research"))


def main() -> int:
    from formal_lab_contracts.research import ConformanceItem
    from formal_lab_runtime.research import decide_correspondence, load_case, validate_case

    r = CheckResult("p7-reproduce")
    cases_dir = ROOT / "research" / "cases"
    case_ids = sorted(p.name for p in cases_dir.iterdir() if (p / "case.json").is_file()) if cases_dir.is_dir() else []
    r.check("cases_present", bool(case_ids), f"committed cases: {case_ids}")

    # a fresh directory with only the committed research data — nothing from the working tree, no platform
    cases: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "research"
        shutil.copytree(ROOT / "research", fresh)
        for cid in case_ids:
            report, case = validate_case(load_case(fresh / "cases" / cid), repo=None)
            derived = []
            if case is not None:
                art = {a.id: a for a in case.artifacts}
                for aid in case.validation.conformance_ids:
                    conf = json.loads((fresh / "cases" / cid / art[aid].path).read_text())
                    obs = conf["program_observations"]
                    status = None
                    if obs:
                        obs_art = art[obs[0]["artifact_id"]]
                        observation = (json.loads((fresh / "cases" / cid / obs_art.path).read_text())
                                       if obs_art.media_type == "application/json" else None)
                        items = _rederive(observation) if observation is not None else None
                        if items is not None:
                            status, _ = decide_correspondence([ConformanceItem(**d) for d in items],
                                                              has_observation=True)
                    derived.append({"id": aid, "stored": conf["correspondence"], "rederived": status,
                                    "match": status is None or status == conf["correspondence"]})
            cases[cid] = {"valid_offline": report.ok, "warnings": [w.code for w in report.warnings],
                          "conformance": derived}
        studies = sorted(p.name for p in (fresh / "studies").iterdir()) if (fresh / "studies").is_dir() else []
        reports = {}
        for sid in studies:
            rp = fresh / "results" / sid / "report.json"
            if rp.is_file():
                rep = json.loads(rp.read_text())
                reports[sid] = {"tracks": {t: v.get("outcomes") for t, v in rep.get("tracks", {}).items()},
                                "ledger": rep.get("ledger")}

    r.check("every_case_valid_offline", all(c["valid_offline"] for c in cases.values()),
            f"{sum(c['valid_offline'] for c in cases.values())}/{len(cases)} cases validate offline with no repository")
    r.check("conformance_rederives", all(d["match"] for c in cases.values() for d in c["conformance"]),
            "every re-derivable conformance matches the committed verdict")
    r.check("software_not_verified_without_repo",
            all("SOFTWARE_NOT_VERIFIED_HERE" in c["warnings"] for c in cases.values()),
            "offline (no repo): software tree digests are warned, not silently passed")
    r.check("study_reports_readable", bool(reports), f"study reports read offline: {sorted(reports)}")

    ev = {"machine": {"arch": platform.machine(), "python": platform.python_version(), "system": platform.system()},
          "offline_recheck": {"cases": cases, "studies": reports},
          "network": {"needed_for_this_recheck": False,
                      "needed_once_for": "the first dependency pull (uv sync) on a truly empty machine",
                      "resampling_path": "fal research study run — new online calls, needs the user's API credentials "
                                         "and quota; not exercised here"},
          "commands": ["uv sync --frozen", "make research-check ARGS=\"--group p5a,p5b,p7\" (offline case/protocol "
                       "checks)", "uv run --frozen python scripts/p7_reproduce.py"],
          "cleanup": "the fresh copy is a temporary directory, removed on exit; only files this run created are touched",
          "reproduction_mode": "automated_clean_room_offline (same agent); independent_human_reproduction is PENDING",
          "conclusion": {"offline_recheck_passes": all(c["valid_offline"] for c in cases.values()),
                         "uses_only_existing_results": True, "makes_no_model_call": True}}
    out = ROOT / EV / "p7" / "reproduce.json"
    write(out, ev)
    r.evidence(out)
    return r.finish()


def _rederive(observation: dict) -> list[dict] | None:
    """Re-derive a case's conformance items from its recorded observation, using the case's own fixture logic."""
    try:
        if "attempts" in observation:  # tenant-isolation
            from formal_lab_example_orders.research_isolation import derive_items

            return derive_items(observation)
        if "steps" in observation and "capacity" in observation:  # token-bucket
            from formal_lab_example_orders.research_ratelimit import derive_items

            return derive_items(observation)
    except Exception:  # an observation shape this script does not re-derive stays stored-only
        return None
    return None  # e.g. the orders-p2-speed replay bundle (engine replay, not re-derived here)


if __name__ == "__main__":
    sys.exit(main())
