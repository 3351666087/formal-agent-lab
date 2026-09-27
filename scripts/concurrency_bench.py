#!/usr/bin/env python3
"""Experiment / solver concurrency measured on this machine (P2-102).

1. Reads the resources actually available to this VM (cgroup CPU / memory limits, available memory) — the same
   readings as `make doctor`.
2. Runs a fixed workload — scheduling cells {normal, state-delay} × {rule, Z3} × seeds {1, 2}: 8 runs, each in its
   own process (the local runner) — first with concurrency 1 (baseline), then with the concurrency the resources
   allow (at most 2 here: memory for 2 × the baseline peak plus a 1 GiB reserve, and ≥ 2 usable CPUs).
3. Optionally (--api URL, a running platform) the same comparison on the durable path: a v2 matrix queue with
   max_parallel 1 and then 2, the worker's resident memory sampled from /proc.

Records wall time, per-run times, peak resident memory (sum over the concurrent processes) and every failure with
its reason in docs/execution/evidence/phase2/concurrency.json.

    scripts/in-vm.sh 'uv run --frozen python scripts/concurrency_bench.py [--api http://127.0.0.1:8000/api/v1]'
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/execution/evidence/phase2/concurrency.json"
CELLS = [(sc, st, seed) for sc in ("normal", "state-delay") for st in ("rule", "z3") for seed in (1, 2)]


def _doctor():
    spec = importlib.util.spec_from_file_location("doctor", ROOT / "scripts" / "doctor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def run_cell(cell: tuple[str, str, int]) -> dict:
    from formal_lab_example_scheduling.scenarios import STRATEGIES, model_package, scenario
    from formal_lab_runtime import default_registry, make_manifest, run_local

    sc_key, st, seed = cell
    t0 = time.perf_counter()
    try:
        reg = default_registry()
        pkg = model_package()
        sc = scenario(sc_key, pkg, seed=seed, strategy=STRATEGIES[st])
        m = make_manifest(run_id=f"run_bench_{sc_key}_{st}_{seed}".replace("-", "_"), project_id="bench", scenario=sc,
                          package=pkg, registry=reg, seed=seed, config={"initial_check_horizon": 0})
        res = run_local(m, pkg, reg)
        status, error = res.status.value, None
    except Exception as exc:  # a failure is a measurement, not a crash of the benchmark
        status, error = "ERROR", f"{type(exc).__name__}: {exc}"
    import resource

    return {"cell": list(cell), "pid": os.getpid(), "status": status, "error": error,
            "seconds": round(time.perf_counter() - t0, 3),
            "max_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}


def _rss_of(pids: set[int]) -> float:
    total = 0
    for pid in pids:
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1])
        except OSError:
            continue
    return total / 1024


def _children(parent: int) -> set[int]:
    out = set()
    for p in Path("/proc").iterdir():
        if p.name.isdigit():
            try:
                if int((p / "stat").read_text().rsplit(")", 1)[1].split()[1]) == parent:
                    out.add(int(p.name))
            except (OSError, ValueError, IndexError):
                continue
    return out


def local(concurrency: int) -> dict:
    peak = 0.0
    stop = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not stop.wait(0.2):
            peak = max(peak, _rss_of(_children(os.getpid())))

    th = threading.Thread(target=sample, daemon=True)
    th.start()
    t0 = time.perf_counter()
    results = []
    with ProcessPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(run_cell, c) for c in CELLS]
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception as exc:  # the worker process itself died (e.g. out of memory)
                results.append({"cell": None, "status": "CRASHED", "error": f"{type(exc).__name__}: {exc}"})
    wall = time.perf_counter() - t0
    stop.set()
    th.join()
    return {"concurrency": concurrency, "wall_seconds": round(wall, 2), "runs": len(results),
            "failures": [r for r in results if r["status"] not in ("SUCCEEDED", "BUDGET_EXHAUSTED")],
            "peak_rss_mib_all_processes": round(peak, 1),
            "max_rss_mib_single_run": max((r.get("max_rss_mib") or 0) for r in results),
            "run_seconds": sorted(r.get("seconds", 0) for r in results)}


def platform(api: str, concurrency: int) -> dict:
    from formal_lab_sdk import Client

    c = Client(api)
    pid = c.find_project("生产调度示例")["id"]
    scs = {s["name"]: s["id"] for s in c.scenarios(pid)}
    sts = {s["name"]: s["id"] for s in c.strategies(pid)}
    worker = {int(p.name) for p in Path("/proc").iterdir() if p.name.isdigit()
              and "formal_lab_orchestrator.worker" in _cmdline(p)}
    peak = 0.0
    stop = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not stop.wait(0.5):
            peak = max(peak, _rss_of(worker))

    th = threading.Thread(target=sample, daemon=True)
    th.start()
    t0 = time.perf_counter()
    mx = c.create_matrix_v2(pid, {"name": f"concurrency-{concurrency}-{int(t0)}", "max_parallel": concurrency,
                                  "scenarios": [scs["正常调度"], scs["状态延迟"]],
                                  "participants": [{"*": sts["EDD 规则"]}, {"*": sts["Z3 有界规划"]}],
                                  "seeds": {"acceptance": [101, 102]},
                                  "ablations": [{"label": f"bench-{concurrency}-{int(t0)}"}]})
    cells = c.wait_matrix(mx["matrix"]["id"], timeout=1800)
    wall = time.perf_counter() - t0
    stop.set()
    th.join()
    return {"concurrency": concurrency, "matrix_id": mx["matrix"]["id"], "wall_seconds": round(wall, 2),
            "cells": len(cells), "failed_cells": [x for x in cells if x["status"] != "DONE"],
            "worker_peak_rss_mib": round(peak, 1), "worker_pids": sorted(worker)}


def _cmdline(p: Path) -> str:
    try:
        return (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", help="platform API base URL for the durable-path measurement")
    args = ap.parse_args()
    doctor = _doctor()
    res = doctor.cpu_memory()
    usable_cpus = res.get("cpus_usable") or os.cpu_count() or 1
    avail_mib = res.get("memory_available_mib") or 0
    baseline = local(1)
    per_run = baseline["max_rss_mib_single_run"]
    allowed = max(1, min(2, int(usable_cpus), int((avail_mib - 1024) // max(per_run, 1)) if avail_mib else 1))
    report = {"resources": res, "workload": {"cells": [list(c) for c in CELLS], "runner": "local, one process per run"},
              "allowed_concurrency": allowed,
              "rule": "min(2, usable CPUs, (available memory − 1 GiB reserve) ÷ baseline peak per run)",
              "local": [baseline]}
    if allowed >= 2:
        report["local"].append(local(2))
    else:
        report["local_note"] = f"concurrency 2 not attempted: allowed = {allowed}"
    if args.api:
        report["platform"] = [platform(args.api, 1)]
        if allowed >= 2:
            report["platform"].append(platform(args.api, 2))
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    summary = {k: [{x: r[x] for x in ("concurrency", "wall_seconds") if x in r} for r in report.get(k, [])]
               for k in ("local", "platform")}
    print(json.dumps({"allowed": allowed, **summary}, ensure_ascii=False))
    return 0 if all(not r.get("failures") and not r.get("failed_cells") for k in ("local", "platform")
                    for r in report.get(k, [])) else 1


if __name__ == "__main__":
    sys.exit(main())
