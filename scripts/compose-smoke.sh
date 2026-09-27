#!/usr/bin/env bash
# End-to-end check of the containerised stack (P1-111 / P1-112 / P1-127):
# build images, start compose, seed, run an experiment and a matrix through the web entry point (:8080),
# verify artifacts in the S3 store, export + offline-verify a replay bundle, record image references.
#   scripts/compose-smoke.sh [--keep]      (evidence: docs/execution/evidence/compose-smoke.json)
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/formal-agent-lab}"
export FAL_SOURCE_REVISION="$(git rev-parse HEAD)"
export FAL_IMAGE_TAG="${FAL_IMAGE_TAG:-local}"
C="docker compose -f deploy/compose/docker-compose.yaml"
OUT=docs/execution/evidence/phase2/compose-smoke.json   # phase-1 evidence (evidence/compose-smoke.json) stays
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "==> no other full stack of this project may run at the same time (heavy runs are serialised)"
for p in $(docker compose ls -a --format json | python3 -c "import json,sys; print(' '.join(x['Name'] for x in json.load(sys.stdin) if x['Name'].startswith(('fal-offline-verify', 'fal-orders-', 'formal-agent-lab-offline'))))"); do
  echo "removing leftover project stack $p"; docker compose -p "$p" down -v >/dev/null 2>&1 || true
done
echo "==> build"
$C build --quiet
echo "==> up"
$C down -v --remove-orphans >/dev/null 2>&1 || true
$C up -d --wait
$C run --rm api python -m formal_lab_api.seed >/dev/null
export FAL_API_URL=http://127.0.0.1:${FAL_WEB_PORT:-8080}/api/v1

echo "==> experiment + matrix through the web entry point"
uv run --frozen python - "$OUT" "$WORK" <<'PY'
import json, subprocess, sys, time
from pathlib import Path
from formal_lab_contracts.bundle import read_bundle
from formal_lab_sdk import Client

out, work = Path(sys.argv[1]), Path(sys.argv[2])
c = Client()
t0 = time.time()
ready = c.get("/health/ready")
assert ready["ready"] and ready["artifact_store"]["backend"] == "s3", ready
pid = c.find_project("生产调度示例")["id"]
scen = {s["name"]: s["id"] for s in c.scenarios(pid)}
strat = {s["name"]: s["id"] for s in c.strategies(pid)}
run = c.start_run(pid, scen["预期与模拟结果不一致"], strat["Z3 有界规划"], seed=2)
streamed = [e.seq for e in c.follow(run["id"])]          # SSE through Caddy
done = c.wait(run["id"])
assert done["status"] == "SUCCEEDED", done
assert streamed == list(range(1, done["event_seq"] + 1)), "SSE through the proxy delivered every event in order"
arts = c.get(f"/runs/{run['id']}/artifacts")
s3 = [a for a in arts if a["ref"]["uri"].startswith("s3://")]
assert s3 and len(s3) == len(arts), "artifacts are stored in the S3-compatible store"
bundle_path = work / "bundle.zip"
bundle_path.write_bytes(c.export_run(run["id"]))
bundle = read_bundle(bundle_path.read_bytes())
mx = c.create_matrix(pid, scenarios=[scen["正常调度"], scen["资源不足"]], strategies=[strat["EDD 规则"], strat["Z3 有界规划"]],
                     seeds=[1, 2], name="compose-smoke")
for rid in mx["run_ids"]:
    c.wait(rid, timeout=900)
report = c.matrix_report(mx["matrix"]["id"])
assert report["complete"] and all(x["status"] == "SUCCEEDED" for x in report["cells"]), report["cells"]
# phase 2 in the containerised stack: the order service (reached as http://orders:8765) and two participants
opid = c.find_project("订单服务示例")["id"]
oscen = {s["name"]: s["id"] for s in c.scenarios(opid)}
orders = {}
for name in ("订单：正常处理（业务服务）", "订单：延迟响应（业务服务）"):
    r = c.start_run(opid, oscen[name], seed=1)
    d = c.wait(r["id"], timeout=900)
    ops = c.operations(r["id"])
    probes = [e for e in c.events(r["id"]) if str(e.event_type) == "PROBE_SAMPLED"]
    orders[name] = {"run": r["id"], "status": d["status"], "steps": d["last_step"], "probes": len(probes),
                    "operations": {st: sum(1 for o in ops if o["state"] == st) for st in {o["state"] for o in ops}}}
    assert d["status"] == "SUCCEEDED" and probes, orders[name]
assert orders["订单：延迟响应（业务服务）"]["operations"].get("RECONCILED", 0) > 0, "lost answers were reconciled"
two = c.start_run(pid, scen["两名调度员（轮流）"], seed=1)
two_done = c.wait(two["id"], timeout=900)
assert two_done["status"] == "SUCCEEDED" and set(two_done["actor_usage"]) == {"dispatcher_a", "dispatcher_b"}
mx2 = c.create_matrix_v2(pid, {"name": "compose-smoke-v2", "scenarios": [scen["正常调度"]],
                               "participants": [{"*": strat["EDD 规则"]}, {"*": strat["Z3 有界规划"]}],
                               "seeds": {"dev": [1], "acceptance": [2]}, "max_parallel": 1})
cells = c.wait_matrix(mx2["matrix"]["id"], timeout=1800)
assert all(x["status"] == "DONE" for x in cells)
images = {}
for name in ("api", "worker", "web", "orders"):
    ref = f"formal-agent-lab/{name}:local"
    info = json.loads(subprocess.run(["docker", "image", "inspect", ref], capture_output=True, text=True, check=True).stdout)[0]
    images[name] = {"ref": ref, "id": info["Id"], "created": info["Created"], "size_mb": round(info["Size"] / 1e6, 1),
                    "architecture": info["Architecture"], "os": info["Os"],
                    "revision": info["Config"]["Labels"].get("org.opencontainers.image.revision")}
evidence = {
    "check": "compose end-to-end (P1-111/P1-112/P1-127; phase 2: P2-101/P2-103)",
    "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "entry_point": c.base_url,
    "ready": ready,
    "run": {"id": run["id"], "status": done["status"], "events": done["event_seq"], "sse_events_streamed": len(streamed),
            "metrics": {k: v["value"] for k, v in done["metrics"].items()}, "artifacts_in_s3": len(s3),
            "example_artifact_uri": s3[0]["ref"]["uri"]},
    "bundle": {"format": bundle.info["format"], "files": len(bundle.info["files"]), "events": len(bundle.events),
               "contract_digest": bundle.info["contract_digest"]},
    "matrix": {"id": mx["matrix"]["id"], "cells": len(report["cells"]),
               "statuses": sorted({x["status"] for x in report["cells"]})},
    "orders": orders,
    "two_participants": {"run": two["id"], "status": two_done["status"], "steps": two_done["last_step"]},
    "matrix_v2": {"id": mx2["matrix"]["id"], "cells": len(cells), "max_parallel": 1},
    "images": images,
    "services": ["postgres:16-alpine", "temporalio/temporal:1.9.1", "chrislusf/seaweedfs:4.47", "migrate", "api",
                 "worker", "web (caddy:2.11-alpine)", "orders (local order service)"],
    "duration_s": round(time.time() - t0, 1),
}
out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({k: evidence[k] for k in ("run", "matrix", "duration_s")}, ensure_ascii=False))
PY
if [[ "${1:-}" != "--keep" ]]; then $C down -v >/dev/null; echo "==> stack removed"; fi
echo "==> OK ($OUT)"
