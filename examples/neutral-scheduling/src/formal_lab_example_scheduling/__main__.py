"""Standalone entry point (no server, no database, no Temporal) — the phase-1 regression sentinel.

    python -m formal_lab_example_scheduling run --scenario state-delay --strategy z3 --seed 2 [--bundle out.zip]
    python -m formal_lab_example_scheduling compare --seeds 1,2,3,4,5 --out results/comparison.json
    python -m formal_lab_example_scheduling check
    python -m formal_lab_example_scheduling export-model model.json

All commands use the same step engine, simulator, scorers and statistics as the platform.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from formal_lab_contracts import CheckQuery, PluginRef

from .scenarios import SCENARIO_CONFIGS, STRATEGIES, model_package, scenario

EVALUATORS = [PluginRef(plugin_id="formal-lab.eval.generic", version="1.0.0"),
              PluginRef(plugin_id="formal-lab.example.scheduling.scorer", version="1.0.0")]


def _run(key: str, strategy: str, seed: int, registry, package):
    from formal_lab_runtime import make_manifest, new_run_id, run_local

    sc = scenario(key, package, seed=seed, strategy=STRATEGIES[strategy])
    manifest = make_manifest(run_id=new_run_id(), project_id="standalone", scenario=sc, package=package,
                             registry=registry, evaluators=EVALUATORS)
    return run_local(manifest, package, registry)


def cmd_run(args: argparse.Namespace) -> int:
    from formal_lab_runtime import default_registry
    from formal_lab_runtime.bundles import bundle_from_local

    package, registry = model_package(), default_registry()
    res = _run(args.scenario, args.strategy, args.seed, registry, package)
    print(f"{res.manifest.run_id}: {res.status.value} ({res.reason}) steps={res.usage.steps} events={len(res.events)}")
    for m in res.metrics:
        print(f"  {m.metric_id:18s} {m.value if m.value is not None else m.status.value}")
    if args.bundle:
        Path(args.bundle).write_bytes(bundle_from_local(res, package))
        print(f"replay bundle: {args.bundle}")
    return 0 if res.status.value == "SUCCEEDED" else 1


def cmd_compare(args: argparse.Namespace) -> int:
    from formal_lab_eval.matrix import Cell, CellRun, build_report
    from formal_lab_runtime import default_registry

    package, registry = model_package(), default_registry()
    scenarios = args.scenarios.split(",") if args.scenarios else list(SCENARIO_CONFIGS)
    strategies = args.strategies.split(",")
    seeds = [int(s) for s in args.seeds.split(",")]
    defs = {}
    for ref in EVALUATORS:
        from formal_lab_runtime.engine import RuntimeServices

        for d in registry.create(ref, {}, RuntimeServices(package)).metric_definitions():
            defs[d.metric_id] = d
    runs: list[CellRun] = []
    t0 = time.time()
    for key in scenarios:
        for strat in strategies:
            for seed in seeds:
                res = _run(key, strat, seed, registry, package)
                kinds = sorted({s.proposal.source.kind.value for s in res.steps if s.proposal})
                runs.append(CellRun(Cell(key, strat, seed, "scenario-default", ()), res.manifest.run_id,
                                    res.status.value, {m.metric_id: m for m in res.metrics},
                                    SCENARIO_CONFIGS[key]["name"], strat, kinds))
                print(f"{key:22s} {strat:9s} seed={seed} {res.status.value:17s} "
                      f"cost={next((m.value for m in res.metrics if m.metric_id == 'delay_cost'), None)}", flush=True)
    report = build_report(list(defs.values()), runs)
    report["setup"] = {"scenarios": scenarios, "strategies": strategies, "seeds": seeds,
                       "model": package.ref().model_dump(mode="json"), "evaluators": [e.model_dump() for e in EVALUATORS],
                       "note": "same simulator, budget and scoring functions for every strategy; LLM_STUB results are "
                               "a deterministic stand-in, not a real model", "duration_s": round(time.time() - t0, 1)}
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n")
        print(f"wrote {args.out}")
    return 0 if all(r.status == "SUCCEEDED" for r in runs if r.strategy_label in ("rule", "z3")) else 1


def cmd_check(args: argparse.Namespace) -> int:
    from formal_lab_solver_z3.verifier import Z3Verifier

    package = model_package()
    v = Z3Verifier()
    ok = True
    for kind, prop, k in (("GOAL_REACHABILITY", "all_done", 12), ("GOAL_REACHABILITY", "all_done", 16),
                          ("INVARIANT_VIOLATION", "machine_capacity", 8), ("INVARIANT_VIOLATION", "on_time", 12)):
        r = v.check(package, CheckQuery(kind=kind, property_id=prop, bound={"max_steps": k, "timeout_ms": 60000}))
        replay = r.witness.replay if r.witness else "-"
        print(f"{kind:20s} {prop:18s} k={k:2d} → {r.verdict!s:24s} replay={replay} ({r.stats.elapsed_ms:.0f} ms)")
        ok &= r.witness is None or r.witness.replay == "CONFIRMED"
    return 0 if ok else 1


def cmd_export(args: argparse.Namespace) -> int:
    Path(args.path).write_text(model_package().ir.model_dump_json(indent=2) + "\n")
    print(f"wrote {args.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m formal_lab_example_scheduling", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--scenario", choices=list(SCENARIO_CONFIGS), default="normal")
    r.add_argument("--strategy", choices=list(STRATEGIES), default="rule")
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--bundle")
    c = sub.add_parser("compare")
    c.add_argument("--scenarios", default="")
    c.add_argument("--strategies", default="rule,z3,llm-stub")
    c.add_argument("--seeds", default="1,2,3")
    c.add_argument("--out")
    sub.add_parser("check")
    e = sub.add_parser("export-model")
    e.add_argument("path")
    args = p.parse_args(argv)
    return {"run": cmd_run, "compare": cmd_compare, "check": cmd_check, "export-model": cmd_export}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
