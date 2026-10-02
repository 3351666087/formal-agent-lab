"""Structured check results (phase 4A, A1): what an evidence script reports back to the check engine.

The engine (scripts/check_runner.py) does not trust an exit code alone. A check declared with `protocol=True` must
write one result document, `fal-check-result@1`, to the path the engine passes in `FAL_CHECK_RESULT`, echoing the
attempt's `FAL_CHECK_NONCE` (a result without the current nonce is stale and fails). Stdlib only, so every script —
inside or outside the platform venv — can use it:

    from check_result import CheckResult           # scripts/ is on sys.path when run as `python scripts/x.py`

    r = CheckResult("a2-binding")
    if not service_reachable:
        sys.exit(r.blocked("order service not reachable on 127.0.0.1:8765"))
    r.check("stale_version_rejected", writes == 0, f"service writes = {writes}")   # a required assertion
    r.check("note_only", latency < 50, "p50 latency", required=False)               # recorded, never decisive
    r.evidence("docs/execution/evidence/phase4/a2-binding.json")
    sys.exit(r.finish())

Status rules (the engine re-derives them; the script's own status is advisory and may only make things worse):
  * BLOCKED / NOT_RUN — a declared environment prerequisite is missing; nothing was verified;
  * FAIL — a required assertion is False or undetermined (None), or the script raised;
  * PASS — every required assertion is True and at least one exists.
Exit codes: PASS 0, FAIL 1, BLOCKED / NOT_RUN 3 — so a manual run is honest too.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROTOCOL = "fal-check-result@1"
ROOT = Path(__file__).resolve().parents[1]
EXIT = {"PASS": 0, "FAIL": 1, "BLOCKED": 3, "NOT_RUN": 3}


def _commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except Exception:
        return None


class CheckResult:
    def __init__(self, check_id: str | None = None):
        self.check_id = os.environ.get("FAL_CHECK_ID") or check_id or Path(sys.argv[0]).stem
        self.nonce = os.environ.get("FAL_CHECK_NONCE")
        self.attempt = os.environ.get("FAL_CHECK_ATTEMPT")
        self.path = Path(os.environ.get("FAL_CHECK_RESULT") or ROOT / "out" / "check-results" / f"{self.check_id}.json")
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.assertions: list[dict[str, Any]] = []
        self.evidence_files: list[str] = []
        self.notes: list[str] = []
        self._status: str | None = None
        self._reason: str | None = None

    # ------------------------------------------------------------------ recording
    def check(self, assertion_id: str, holds: bool | None, detail: str = "", *, required: bool = True) -> bool:
        """Record one assertion. `holds` None means undetermined — a required undetermined assertion fails."""
        value = None if holds is None else bool(holds)
        self.assertions.append({"id": assertion_id, "required": required, "holds": value, "detail": str(detail)[:500]})
        return bool(value)

    def evidence(self, path: str | Path) -> None:
        p = Path(path)
        self.evidence_files.append(str(p.relative_to(ROOT)) if p.is_absolute() and p.is_relative_to(ROOT) else str(p))

    def note(self, text: str) -> None:
        self.notes.append(str(text)[:500])

    def blocked(self, reason: str) -> int:
        """A declared prerequisite is missing: record BLOCKED and return the exit code (nothing was verified)."""
        self._status, self._reason = "BLOCKED", reason
        return self.finish()

    def not_run(self, reason: str) -> int:
        self._status, self._reason = "NOT_RUN", reason
        return self.finish()

    # ------------------------------------------------------------------ outcome
    def status(self) -> tuple[str, str]:
        if self._status in ("BLOCKED", "NOT_RUN"):
            return self._status, self._reason or self._status.lower()
        required = [a for a in self.assertions if a["required"]]
        failed = [a for a in required if a["holds"] is not True]
        if failed:
            first = failed[0]
            return "FAIL", f"required assertion {first['id']} = {first['holds']}: {first['detail']}"
        if not required:
            return "FAIL", "no required assertion was recorded (nothing verified)"
        return "PASS", f"{len(required)} required assertion(s) hold"

    def finish(self) -> int:
        status, reason = self.status()
        doc = {"protocol": PROTOCOL, "check": self.check_id, "nonce": self.nonce, "attempt": self.attempt,
               "commit": _commit(), "started_at": self.started_at,
               "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "status": status, "reason": reason, "assertions": self.assertions,
               "evidence": self.evidence_files, "notes": self.notes}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(f"[{self.check_id}] {status}: {reason}")
        return EXIT[status]
