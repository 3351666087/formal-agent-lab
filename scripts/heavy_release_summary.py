"""Collect the disk-heavy release checks (phase-2 local-release, phase-3 g6 extensions) into one phase-4 record.

These checks stayed BLOCKED by host disk through phase 4A's acceptance; they are run one at a time on the shared
engine (`scripts/check_runner.py --suite <s> --only <id> --out out/heavy/<s>-<id>`, evidence under
docs/execution/evidence/phase4/regression/<suite>/), and this script copies each check's record — every attempt,
the earlier runs in `history`, evidence digests — into docs/execution/evidence/phase4/heavy-release.json.

    uv run --frozen python scripts/heavy_release_summary.py
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "out" / "heavy"
OUT = ROOT / "docs" / "execution" / "evidence" / "phase4" / "heavy-release.json"
HEAVY = [("phase2", "offline-install"), ("phase2", "kind-install-upgrade"), ("phase2", "compose-smoke"),
         ("phase2", "release-manifest"), ("phase2", "orders-compose"),
         ("phase3", "p3-offline-bundle"), ("phase3", "p3-release-images")]
KEEP = ("result", "reason", "checked_commit", "worktree_clean", "started_at", "finished_at", "duration_s", "heavy_gib",
        "evidence_files", "first_failure", "flaky", "history")


def record(suite: str, check_id: str) -> dict:
    path = RUNS / f"{suite}-{check_id}" / "results.json"
    if not path.exists():
        return {"suite": suite, "id": check_id, "result": "NOT_RUN", "reason": f"no report at {path.relative_to(ROOT)}"}
    doc = json.loads(path.read_text())
    c = next(c for c in doc["checks"] if c["id"] == check_id)
    return {"suite": suite, "id": check_id, **{k: c.get(k) for k in KEEP},
            "attempts": [{k: a.get(k) for k in ("result", "duration_s", "reason")} for a in c.get("attempts") or []],
            "report": str(path.relative_to(ROOT)), "nonce": doc["run"].get("nonce")}


def main() -> int:
    checks = [record(s, i) for s, i in HEAVY]
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    doc = {"format": "heavy-release@1", "generated_at": datetime.now(UTC).isoformat(), "head": rev,
           "checked_commits": sorted({c.get("checked_commit") for c in checks if c.get("checked_commit")}),
           "summary": dict(Counter(c["result"] for c in checks)),
           "all_passed": all(c["result"] == "PASS" for c in checks), "checks": checks,
           "rule": "one check at a time on the shared engine; host keeps heavy_gib + 15 GiB free, the VM's Docker disk "
                   "heavy_gib + 2 GiB; earlier runs of a check stay in its history (first failures stay visible)"}
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"heavy release checks: {doc['summary']} → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
