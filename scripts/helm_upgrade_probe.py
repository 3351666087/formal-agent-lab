#!/usr/bin/env python3
"""One phase of scripts/helm-upgrade-check.sh: probe the deployed platform through the public SDK and append a JSON
line to the state file (previous → upgraded → rolled-back)."""

from __future__ import annotations

import json
import sys
import time

from formal_lab_contracts.errors import FormalLabError
from formal_lab_sdk import Client


def main() -> int:
    phase, api, state = sys.argv[1:4]
    with open(state) as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    first = next((r for r in rows if r["phase"] == "previous"), None)
    c = Client(api, timeout=60)
    row: dict = {"phase": phase, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for _ in range(60):
        try:
            row["ready"] = bool(c.get("/health/ready")["ready"])
            break
        except FormalLabError:
            time.sleep(2)
    meta = c.meta()
    row["platform_version"] = meta.get("platform_version") or meta.get("version")
    pid = c.find_project("生产调度示例")["id"]
    scs = {s["name"]: s["id"] for s in c.scenarios(pid)}
    sts = {s["name"]: s["id"] for s in c.strategies(pid)}
    if first is not None:  # the run made before the upgrade must stay readable in every later version
        try:
            old = c.run(first["run_id"])
            row["old_run_readable"] = old["status"] == first["run_status"]
            row["old_run_contract"] = old.get("stored_contract_version", "(field not reported)")
        except FormalLabError as exc:
            row["old_run_readable"] = False
            row["old_run_error"] = exc.message[:300]
    try:
        row["runs_listed"] = len(c.runs(pid))
    except FormalLabError as exc:
        row["runs_listed"] = None
        row["runs_list_error"] = exc.message[:300]
    scenario = "两名调度员（轮流）" if phase == "upgraded" and "两名调度员（轮流）" in scs else "状态延迟"
    run = c.start_run(pid, scs[scenario], None if scenario.startswith("两名") else sts["Z3 有界规划"], seed=4)
    done = c.wait(run["id"], timeout=600)
    row.update({"scenario": scenario, "run_id": run["id"], "run_status": done["status"], "steps": done["last_step"]})
    with open(state, "a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
