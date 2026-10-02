"""Phase-4 domain checks (B1–B3) — the registration point for the 04B executor.

scripts/phase4_check.py imports `DOMAIN_CHECKS` from here and appends them to the phase-4 suite. Until something is
registered, the groups `b1`, `b2`, `b3` report `NO_CHECKS`, which keeps `complete` false: finishing 4A can never look
like a finished Phase 4.

How to register (see docs/execution/check-protocol.md):

    from check_runner import Check
    PY = "uv run --frozen python"
    DOMAIN_CHECKS = [
        Check("p4-b1-mal-loop", "b1", "MAL 闭环 …", f"{PY} scripts/b1_mal_evidence.py", ["P4B-B1"],
              protocol=True, produces=[f"{EV}/b1-mal.json"]),
    ]

Rules: only groups b1 / b2 / b3; `protocol=True` for evidence scripts (they report through scripts/check_result.py:
required assertions, BLOCKED with the missing prerequisite); a real-endpoint or optional backend item is
`kind="conditional"` with a `trigger` probe fixed here, never decided at run time.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_runner import Check

EV = os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
DOMAIN_GROUPS = ("b1", "b2", "b3")

DOMAIN_CHECKS: list[Check] = []
