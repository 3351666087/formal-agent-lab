#!/usr/bin/env python3
"""Research-track local checks (phases 5–7) on scripts/check_runner.py. 5A registers group p5a; p5b–p7 are declared
but empty until their executors register checks, so the suite is complete only once every required group passes.

    make research-check ARGS="--group p5a"      # just the 5A foundation (selected_passed, never overall_complete)
    make research-check                          # every group; complete only when p5b–p7 are registered and pass
    uv run --frozen python scripts/check_runner.py --suite research --list

Status protocol: docs/execution/check-protocol.md. The report always carries both `selected_passed` (did the chosen
checks pass) and `overall_complete` (is the whole suite complete). Evidence → $FAL_EVIDENCE_DIR
(default docs/execution/evidence/research)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_runner import ROOT, Suite, main
from research_checks import RESEARCH_CHECKS, RESEARCH_GROUPS

EV = os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/research")

SUITE = Suite(
    name="research",
    groups=RESEARCH_GROUPS,
    checks=RESEARCH_CHECKS,
    out=ROOT / EV / "checks",
    # what the checks and the handoff write themselves — never part of what is being checked (no code lives here)
    outputs=("docs/execution/evidence/", "docs/handoff/", "research/results/", "out/"),
    required_groups=RESEARCH_GROUPS,
)

if __name__ == "__main__":
    sys.exit(main(["--suite", "research", *sys.argv[1:]]))
