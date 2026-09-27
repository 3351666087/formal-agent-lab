#!/usr/bin/env python3
"""Backup / restore verified with a real experiment (P2-108).

Uses its own database (fal_backup_check) next to the development one: migrate + seed, run one experiment through the
platform's execution activities (the same functions the Temporal worker calls), export its replay bundle, then
`scripts/local_data.py backup` → `reset` (database and artifacts emptied) → `restore`, and check that the run, its
events, operations and artifacts are back and the re-exported bundle is byte-identical.

Evidence: docs/execution/evidence/phase2/backup-restore.json. Needs the fal-dev PostgreSQL container
(`make services-up`).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = "fal_backup_check"
WORK = Path(tempfile.mkdtemp(prefix="fal-backup-"))
os.environ["FAL_DATABASE_URL"] = f"postgresql+psycopg://fal:fal@127.0.0.1:5432/{DB}"
os.environ["FAL_ARTIFACT_ROOT"] = str(WORK / "artifacts")
OUT = ROOT / "docs/execution/evidence/phase2/backup-restore.json"


def sh(*args: str) -> dict:
    t0 = time.perf_counter()
    res = subprocess.run([sys.executable, str(ROOT / "scripts" / "local_data.py"), *args, "--database", DB],
                         capture_output=True, text=True, env=os.environ)
    if res.returncode != 0:
        raise SystemExit(f"local_data {args}: {res.stderr or res.stdout}")
    return {"command": f"scripts/local_data.py {' '.join(args)} --database {DB}", "exit": res.returncode,
            "seconds": round(time.perf_counter() - t0, 2), "result": json.loads(res.stdout)}


def main() -> int:
    import psycopg

    with psycopg.connect("postgresql://fal:fal@127.0.0.1:5432/fal", autocommit=True) as conn:
        conn.execute(f"drop database if exists {DB}")
        conn.execute(f"create database {DB}")
    subprocess.run([sys.executable, "-m", "formal_lab_api.migrate", "upgrade"], cwd=ROOT, check=True, env=os.environ)
    subprocess.run([sys.executable, "-m", "formal_lab_api.seed"], cwd=ROOT, check=True, env=os.environ,
                   capture_output=True)
    from formal_lab_api.db import Project, Scenario, session_scope
    from formal_lab_api.services import bundles, execution, runs
    from formal_lab_api.services.runs import mark_queued
    from sqlalchemy import select

    with session_scope() as s:
        pid = s.scalar(select(Project.id).where(Project.name == "生产调度示例"))
        sid = s.scalar(select(Scenario.id).where(Scenario.project_id == pid, Scenario.name == "资源不足"))
        run, _ = runs.create_run(s, pid, {"scenario_id": sid, "seed": 3})
        run_id = run.id
        mark_queued(s, run_id)
    res = execution.prepare_run(run_id)
    step = res["next_step"]
    while True:
        res = execution.run_step(run_id, step)
        if res.get("terminal"):
            break
        step = res["next_step"]
    execution.finalize_run(run_id, res["status"], res.get("reason"))
    with session_scope() as s:
        before_bundle, _ = bundles.export_run(s, run_id)
    before = hashlib.sha256(before_bundle).hexdigest()
    steps = [sh("status"), sh("backup", "--out", str(WORK / "backup"))]
    steps.append(sh("reset", "--yes"))
    emptied = steps[-1]["result"]["rows"]
    steps.append(sh("restore", "--from", str(WORK / "backup"), "--yes"))
    restored = steps[-1]["result"]
    with session_scope() as s:
        after_bundle, _ = bundles.export_run(s, run_id)
        run_status = s.get(runs.Run, run_id).status
    after = hashlib.sha256(after_bundle).hexdigest()
    ok = restored["matches_backup"] and before == after and emptied["runs"] == 0
    OUT.write_text(json.dumps({
        "database": DB, "run_id": run_id, "run_status": run_status, "steps": steps,
        "after_reset_rows": emptied, "bundle_sha256_before": before, "bundle_sha256_after_restore": after,
        "bundle_identical": before == after, "ok": ok,
        "backup_files": steps[1]["result"]["files"]}, indent=2, ensure_ascii=False) + "\n")
    with psycopg.connect("postgresql://fal:fal@127.0.0.1:5432/fal", autocommit=True) as conn:
        conn.execute(f"drop database if exists {DB}")
    print(json.dumps({"ok": ok, "run": run_id, "status": run_status, "bundle_identical": before == after,
                      "rows_after_reset": emptied["runs"], "restored_rows": restored["now"]}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
