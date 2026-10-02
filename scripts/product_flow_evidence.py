#!/usr/bin/env python3
"""The two G5 product flows through the SDK and the `fal` CLI against a running platform (phase 3A, G5).

1. Warehouse joint batch ("仓储：收货员 + 拣货员同步批次"): run → query rounds (`fal run batches`, `Client.batches`) →
   export the replay bundle → read it offline (`fal replay verify / batches / view`).
2. Order service recovery ("订单：延迟响应（业务服务）"): every answer is held past the client timeout, so operations
   end OUTCOME_UNKNOWN and are settled by asking the service (RECONCILED) → query (`fal ops list --abnormal`) →
   export → offline (`fal replay operations --abnormal`).
The Web side of the same flows is `scripts/capture_screens.py`. Evidence: docs/execution/evidence/phase3/g5-flows.json.

    scripts/in-vm.sh 'FAL_API_URL=http://127.0.0.1:8000/api/v1 uv run --frozen python scripts/product_flow_evidence.py'
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from formal_lab_contracts.bundle import read_bundle
from formal_lab_sdk.client import Client

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3") / "g5-flows.json"
API = os.environ.get("FAL_API_URL", "http://127.0.0.1:8000/api/v1")
FLOWS = {"warehouse_batch": ("仓储分配示例", "仓储：收货员 + 拣货员同步批次"),
         "order_recovery": ("订单服务示例", "订单：延迟响应（业务服务）")}


def fal(*args: str) -> str:
    res = subprocess.run([sys.executable, "-m", "formal_lab_sdk.cli", *args, *(["--api", API] if args[0] in (
        "run", "ops", "export") else [])], capture_output=True, text=True, timeout=900,
        env={**os.environ, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
    if res.returncode != 0:
        raise SystemExit(f"fal {' '.join(args)} failed ({res.returncode}): {res.stderr[-800:]}")
    return res.stdout


def run_id_of(text: str) -> str:
    for token in text.split():
        if token.startswith("run_"):
            return token.strip(",:")
    raise SystemExit(f"no run id in: {text[:300]}")


def main() -> int:
    t0 = time.time()
    client = Client(API)
    out: dict = {"api": API}
    with tempfile.TemporaryDirectory() as tmp:
        for key, (project, scenario) in FLOWS.items():
            started = fal("run", "start", "--project", project, "--scenario", scenario, "--wait")
            rid = run_id_of(started)
            run = client.get(f"/runs/{rid}")
            bundle = Path(tmp) / f"{key}.replay.zip"
            exported = fal("export", rid, "-o", str(bundle))
            b = read_bundle(bundle.read_bytes())
            flow = {"run_id": rid, "status": run["status"], "steps": run["last_step"], "cli_start": started.strip()[-400:],
                    "export": exported.strip().replace(tmp, "<tmp>"), "bundle_bytes": bundle.stat().st_size,
                    "offline_verify": fal("replay", "verify", str(bundle)).strip().replace(tmp, "<tmp>")}
            if key == "warehouse_batch":
                online = client.batches(rid)
                offline = b.batches()
                flow.update(online_rounds=len(online), offline_rounds=len(offline),
                            same_online_offline=[(x["round"], x["env_step"], [m["status"] for m in x["members"]])
                                                 for x in online] == [(x["round"], x["env_step"],
                                                                       [m["status"] for m in x["members"]])
                                                                      for x in offline],
                            cli_batches=fal("run", "batches", rid).splitlines()[:7],
                            offline_batches=fal("replay", "batches", str(bundle)).splitlines()[:7],
                            env_step_per_round=all(x["env_step"] == x["round"] for x in online))
            else:
                ops = client.operations(rid)
                abnormal = client.operations(rid, abnormal=True)
                flow.update(operations=len(ops), reconciled=sum(1 for o in ops if o["state"] == "RECONCILED"),
                            outcome_unknown=len(abnormal),
                            cli_ops=fal("ops", "list", rid, "--abnormal").splitlines()[:6],
                            offline_ops=fal("replay", "operations", str(bundle), "--abnormal").splitlines()[:6],
                            offline_reconciled=sum(1 for o in b.operations if o.state.value == "RECONCILED"))
            flow["offline_view"] = fal("replay", "view", str(bundle)).splitlines()[:5]
            out[key] = flow
    w, o = out["warehouse_batch"], out["order_recovery"]
    checks = {
        "warehouse batch: run succeeded via CLI": w["status"] == "SUCCEEDED",
        "warehouse batch: one environment step per round (online)": w["env_step_per_round"] and w["online_rounds"] > 0,
        "warehouse batch: exported bundle reads offline with the same rounds": w["same_online_offline"]
                                                                             and w["offline_verify"].startswith("OK"),
        "order recovery: run succeeded via CLI": o["status"] == "SUCCEEDED",
        "order recovery: unknown outcomes settled by query": o["reconciled"] > 0 and o["outcome_unknown"] > 0,
        "order recovery: offline bundle keeps the reconciliations": o["offline_reconciled"] == o["reconciled"]
                                                                    and o["offline_verify"].startswith("OK"),
    }
    doc = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "duration_s": round(time.time() - t0, 1),
           "checks": checks, "ok": all(checks.values()), **out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(checks, indent=1, ensure_ascii=False))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
