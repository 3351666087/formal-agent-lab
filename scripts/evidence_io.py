"""Evidence files of the domain scripts (phase 4B, B3): what a conclusion may claim, and how it is read back.

The phase-3 domain checks (D1–D6) take their assertions from the evidence file's `conclusion`, so a constant there
would be a claim, not a result. This module gives the scripts two things instead:

  * `write(out, ev)` — records the revision the evidence was produced at, writes the file, reads it back from disk
    alone and sets `conclusion.offline_readable` from that round trip (then writes the final file);
  * `assess(path)` — tells, separately, whether an evidence file is present, whether it passed (every boolean of its
    conclusion is true and it is not BLOCKED / NOT_RUN), and whether it was produced at the current clean revision.

Stdlib only; used by scripts/d1_mal_evidence.py … scripts/d6_domain_acceptance_evidence.py.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
# evidence and scratch output never make the source revision dirty
_IGNORED = (":!docs/execution/evidence", ":!var", ":!out")


def revision() -> dict[str, Any]:
    """The source revision: HEAD and whether tracked source files differ from it (evidence / var / out excluded)."""
    def git(*args: str) -> str | None:
        try:
            res = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20)
            return res.stdout if res.returncode == 0 else None
        except Exception:
            return None

    commit = (git("rev-parse", "HEAD") or "").strip() or None
    status = git("status", "--porcelain", "--untracked-files=no", "--", ".", *_IGNORED)
    return {"commit": commit, "dirty": None if status is None else bool(status.strip())}


def write(out: Path, ev: dict[str, Any]) -> bool:
    """Write `ev` to `out` with its production revision; `conclusion.offline_readable` is the read-back result.
    Evidence without a conclusion (BLOCKED / NOT_RUN) gets none: a lone read-back flag must never look like a pass."""
    ev["produced_at"] = revision()
    conclusion = ev.get("conclusion")
    if conclusion is not None:
        conclusion["offline_readable"] = False
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(ev, indent=2, ensure_ascii=False)
    out.write_text(text)
    try:
        ok = json.loads(out.read_text()) == json.loads(text)
    except (OSError, json.JSONDecodeError):
        ok = False
    if conclusion is not None:
        conclusion["offline_readable"] = ok
        out.write_text(json.dumps(ev, indent=2, ensure_ascii=False))
    return ok


def assess(path: Path, current: dict[str, Any] | None = None) -> dict[str, Any]:
    """Present / passed / produced at the current clean revision — three separate verdicts for one evidence file."""
    if not path.exists():
        return {"present": False, "passed": False, "current_revision": False, "failed": [], "produced_at": None}
    try:
        ev = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {"present": True, "passed": False, "current_revision": False, "failed": [f"unreadable: {exc}"],
                "produced_at": None}
    bools = {k: v for k, v in (ev.get("conclusion") or {}).items() if isinstance(v, bool)}
    failed = [k for k, v in bools.items() if not v]
    passed = str(ev.get("status", "OK")).upper() not in ("BLOCKED", "NOT_RUN", "FAIL") and bool(bools) and not failed
    cur = current or revision()
    prod = ev.get("produced_at") or {}
    same = bool(prod.get("commit")) and prod.get("commit") == cur.get("commit") and prod.get("dirty") is False \
        and cur.get("dirty") is False
    return {"present": True, "passed": passed, "current_revision": same, "failed": failed, "produced_at": prod}
