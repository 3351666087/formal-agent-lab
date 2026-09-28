"""From an empty project work directory: create the environment, run an experiment, export, reset, rerun, clean up
(P2-069). Writes a timestamped log of what really happened and a JSON summary.

    python -m formal_lab_example_orders.e2e --workdir /tmp/orders-e2e --mode process \\
        --log docs/execution/evidence/phase2/orders/e2e-process.log

Modes: `process` (local-lite: a loopback service process) or `compose` (local-services: the example's Compose
definition, labelled with the project). The experiment: the rule and Z3 strategies on the normal, delayed and
deviation cases, seeds 1 and 2, all against the business service; the rerun after the service-side reset must
reproduce every trajectory.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .lifecycle import ServiceManager, cleanup_project, precheck, run_with_timeout
from .net import trust_env

CASES = ["normal", "delayed", "deviation"]
STRATEGIES = ["rule", "z3"]
SEEDS = [1, 2]


class Log:
    def __init__(self, path: Path | None):
        self.path = path
        self.lines: list[str] = []
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")

    def __call__(self, msg: str, **data: Any) -> None:
        line = f"{datetime.now(UTC).strftime('%H:%M:%S.%f')[:-3]}  {msg}"
        if data:
            line += "  " + json.dumps(data, ensure_ascii=False, default=str)
        self.lines.append(line)
        print(line, flush=True)
        if self.path:
            with self.path.open("a") as fh:
                fh.write(line + "\n")


def trajectory(res: Any) -> list[tuple]:
    return [(e.logical_step, e.payload["outcome"]["action"]["action_type"],
             json.dumps(e.payload["outcome"]["action"]["params"], sort_keys=True), e.payload["outcome"]["status"])
            for e in res.events if str(e.event_type) == "ACTION_OUTCOME"]


def experiment(mgr: ServiceManager, out: Path, label: str, log: Log) -> dict[str, Any]:
    from formal_lab_runtime import default_registry
    from formal_lab_runtime.bundles import bundle_from_local

    from .model import model_package
    from .scenarios import run

    reg = default_registry()
    pkg = model_package()
    cells: dict[str, Any] = {}
    for case in CASES:
        for strategy in STRATEGIES:
            for seed in SEEDS:
                key = f"{case}-{strategy}-{seed}"
                t0 = time.time()
                res = run(case, backend="service", seed=seed, strategy=strategy, endpoint=mgr.endpoint,
                          tenant=f"{case}-{strategy}-{seed}", registry=reg, run_id=f"run_{label}_{key}")
                bundle = out / "bundles" / f"{key}.replay.zip"
                bundle.parent.mkdir(parents=True, exist_ok=True)
                bundle.write_bytes(bundle_from_local(res, pkg))
                states: dict[str, int] = {}
                for o in res.operations:
                    states[o.state.value] = states.get(o.state.value, 0) + 1
                cells[key] = {"status": res.status.value, "steps": res.usage.steps,
                              "metrics": {m.metric_id: m.value for m in res.metrics
                                          if m.metric_id in ("orders_completed", "late_orders", "mean_latency")},
                              "operations": states, "trajectory": trajectory(res),
                              "bundle": str(bundle.relative_to(out)), "seconds": round(time.time() - t0, 2)}
                log(f"[{label}] {key}: {res.status.value} in {res.usage.steps} steps", operations=states,
                    metrics=cells[key]["metrics"], seconds=cells[key]["seconds"])
    return cells


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="order-service end-to-end from an empty work directory")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--mode", choices=["process", "compose"], default="process")
    ap.add_argument("--project", default="e2e")
    ap.add_argument("--log")
    ap.add_argument("--summary")
    ap.add_argument("--timeout", type=float, default=1800.0, help="runtime limit of each experiment (s)")
    args = ap.parse_args(argv)
    work = Path(args.workdir).resolve()
    log = Log(Path(args.log).resolve() if args.log else None)
    summary: dict[str, Any] = {"mode": args.mode, "project": args.project, "workdir": str(work), "steps": {}}
    if work.exists() and any(work.iterdir()):
        log("work directory is not empty; refusing to start", workdir=str(work))
        return 2
    work.mkdir(parents=True, exist_ok=True)
    log("start", mode=args.mode, project=args.project, workdir=str(work), empty=True)
    mgr = ServiceManager(work, project=args.project, mode=args.mode, supervise=args.mode == "process")
    ok = False
    try:
        summary["steps"]["precheck"] = precheck(work)
        log("precheck ok", **summary["steps"]["precheck"])
        t0 = time.time()
        mgr.create()
        mgr.start()
        health = mgr.ready(timeout_s=180 if args.mode == "compose" else 30)
        summary["steps"]["create"] = {"endpoint": mgr.endpoint, "health": health, "seconds": round(time.time() - t0, 2),
                                      "transitions": list(mgr.transitions)}
        log("environment ready", endpoint=mgr.endpoint, pid=health.get("pid"), seconds=summary["steps"]["create"]["seconds"])
        out = work / "results"
        first = run_with_timeout(experiment, args.timeout, mgr, out / "run1", "run1", log)
        summary["steps"]["experiment"] = {k: {x: v[x] for x in v if x != "trajectory"} for k, v in first.items()}
        # export: the service state of every tenant next to the replay bundles
        import httpx

        exports = out / "run1" / "service-state"
        exports.mkdir(parents=True, exist_ok=True)
        for key in first:
            state = httpx.get(f"{mgr.endpoint}/t/{key}/admin/export", trust_env=trust_env(f"{mgr.endpoint}/t/{key}/admin/export"), timeout=30).json()
            (exports / f"{key}.json").write_text(json.dumps(state, indent=1))
        summary["steps"]["export"] = {"bundles": len(first), "service_states": len(first),
                                      "bytes": sum(p.stat().st_size for p in out.rglob("*") if p.is_file())}
        log("exported", **summary["steps"]["export"])
        # reset: service-side reset of every tenant, verified against the probe of a fresh instance
        from .plugins import OrderProbe

        resets = {}
        for key in first:
            case, _, seed = key.rsplit("-", 2)[0], key.rsplit("-", 2)[1], int(key.rsplit("-", 1)[1])
            mgr.reset(key, case=case, seed=seed)
            metrics = httpx.get(f"{mgr.endpoint}/t/{key}/metrics", trust_env=trust_env(f"{mgr.endpoint}/t/{key}/metrics"), timeout=10).json()
            resets[key] = {"clock": metrics["clock"], "backlog": metrics["backlog"], "queue": metrics["queue_length"]}
        assert all(r["clock"] == 0 and r["queue"] == 0 for r in resets.values()), resets
        summary["steps"]["reset"] = {"tenants": len(resets), "probe_after_reset": next(iter(resets.values())),
                                     "probe_metrics": [d.metric_id for d in OrderProbe().definitions()]}
        log("service-side reset verified by the service metrics", tenants=len(resets))
        second = run_with_timeout(experiment, args.timeout, mgr, out / "run2", "run2", log)
        same = {k: first[k]["trajectory"] == second[k]["trajectory"] for k in first}
        summary["steps"]["rerun"] = {"identical_trajectories": sum(same.values()), "cells": len(same),
                                     "differing": [k for k, v in same.items() if not v]}
        log("rerun compared", **summary["steps"]["rerun"])
        summary["steps"]["resources"] = mgr.stats()
        log("resource usage", **summary["steps"]["resources"])
        ok = all(same.values()) and all(v["status"] == "SUCCEEDED" for v in first.values())
    except Exception as exc:  # the log must show what failed; cleanup still runs
        summary["error"] = f"{type(exc).__name__}: {exc}"
        log("FAILED", error=summary["error"], trace=traceback.format_exc()[-1500:])
    finally:
        try:
            removed = mgr.close(remove_data=True)
        except Exception as exc:  # fall back to label-based cleanup
            log("close failed; cleaning up by project label", error=str(exc))
            removed = cleanup_project(work, args.project)
        leftover = cleanup_project(work, args.project)
        summary["steps"]["cleanup"] = {"removed": removed, "leftover_after_close": leftover,
                                       "state_dir_gone": not (work / ".fal-orders" / args.project).exists()}
        log("cleanup", **summary["steps"]["cleanup"])
    summary["ok"] = ok and not any(summary["steps"]["cleanup"]["leftover_after_close"].values())
    log("done", ok=summary["ok"])
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
