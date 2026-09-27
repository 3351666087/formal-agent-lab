#!/usr/bin/env python3
"""Evidence for P2-087 (and the v2 report semantics of P2-082 … P2-085) without a server.

1. Runs a small study locally and exports one replay bundle per cell: scenarios normal and state-delay; strategies
   rule (EDD), shortest path (Z3), cost-optimal (Z3 cost mode), model-assisted (the labelled LLM stand-in) and a
   task plan (rule generator); seeds fixed in advance — dev [1], acceptance [2, 3, 4]; ablations: on state-delay
   "no-observation-delay" (observation delay switched off), for the Z3 planner "no-plan-memory" (re-plan every step).
   Plus the order service (a real service process) for the normal and deviation cases, so independent probe metrics
   appear next to evaluator scores. One extra bundle is corrupted on purpose.
2. Copies the bundles into a new empty directory and runs `python -m formal_lab_eval.offline` there, with no API
   configured (offline), capturing its output.
3. Stores the log and the JSON / CSV / Markdown report in docs/execution/evidence/phase2/offline-report/.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from formal_lab_contracts import ScenarioManifest
from formal_lab_example_scheduling.__main__ import EVALUATORS
from formal_lab_example_scheduling.scenarios import STRATEGIES, model_package, scenario
from formal_lab_runtime import default_registry, make_manifest, run_local
from formal_lab_runtime.bundles import bundle_from_local

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/execution/evidence/phase2/offline-report"
SPLITS = {"dev": [1], "acceptance": [2, 3, 4]}
LABELS = {"rule": "规则（EDD）", "z3": "最短路径（Z3）", "z3-cost": "成本优化（Z3）", "llm-stub": "模型辅助（替身）",
          "task-rule": "任务计划（规则生成）"}


def order_service_bundles(work: Path) -> int:
    """Rule and Z3 on the order service (normal / deviation): bundles carry the service probe's samples."""
    from formal_lab_example_orders.lifecycle import ServiceManager
    from formal_lab_example_orders.model import model_package as order_package
    from formal_lab_example_orders.scenarios import run as order_run

    n = 0
    with tempfile.TemporaryDirectory() as tmp, ServiceManager(Path(tmp), project="offline-evidence") as mgr:
        mgr.ready()
        pkg = order_package()
        for case in ("normal", "deviation"):
            for strat, label in (("rule", "订单规则"), ("z3", "最短路径（Z3）")):
                for split, seeds in SPLITS.items():
                    for seed in seeds:
                        run_id = f"run_off_orders_{case}_{strat}_{seed}"
                        labels = {"participants": label, "backend": "order service", "ablation": "none",
                                  "rules": "none", "model": f"{pkg.package_id}@{pkg.version}",
                                  "budget": "scenario-default"}
                        res = order_run(case, backend="service", seed=seed, strategy=strat, endpoint=mgr.endpoint,
                                        tenant=f"{case}-{strat}-{seed}", run_id=run_id,
                                        config={"matrix_split": split, "matrix_labels": labels})
                        (work / f"{run_id}.replay.zip").write_bytes(bundle_from_local(res, pkg))
                        n += 1
    return n


def main() -> int:
    reg = default_registry()
    pkg = model_package()
    work = Path(tempfile.mkdtemp(prefix="fal-bundles-"))
    n = 0
    for key in ("normal", "state-delay"):
        for strat in LABELS:
            ablations = [("none", None)]
            if key == "state-delay":
                ablations.append(("no-observation-delay", "drop"))
            if strat == "z3":
                ablations.append(("no-plan-memory", "memory"))
            for abl, how in ablations:
                for split, seeds in SPLITS.items():
                    for seed in seeds:
                        spec = STRATEGIES[strat]
                        if how == "memory":
                            spec = {"plugin": spec["plugin"], "config": {**spec["config"], "plan_memory": False}}
                        sc = scenario(key, pkg, seed=seed, strategy=spec)
                        if how == "drop":
                            data = sc.model_dump(mode="json")
                            data["environment"]["config"].pop("observation", None)
                            sc = ScenarioManifest.model_validate(data)
                        labels = {"participants": LABELS[strat], "ablation": abl, "backend": "ir-world",
                                  "rules": "none", "model": f"{pkg.package_id}@{pkg.version}",
                                  "budget": "scenario-default"}
                        run_id = f"run_off_{key}_{strat}_{abl}_{seed}".replace("-", "_")
                        m = make_manifest(run_id=run_id, project_id="offline", scenario=sc, package=pkg,
                                          registry=reg, seed=seed, evaluators=EVALUATORS,
                                          config={"initial_check_horizon": 0, "matrix_split": split,
                                                  "matrix_labels": labels})
                        res = run_local(m, pkg, reg)
                        (work / f"{run_id}.replay.zip").write_bytes(bundle_from_local(res, pkg))
                        n += 1
    n += order_service_bundles(work)
    good = sorted(work.glob("*.replay.zip"))
    bad = work / "run_off_corrupted.replay.zip"
    data = bytearray(good[0].read_bytes())
    data[len(data) // 2] ^= 0xFF
    bad.write_bytes(bytes(data))
    empty = Path(tempfile.mkdtemp(prefix="fal-offline-"))
    assert not any(empty.iterdir())
    for p in [*good, bad]:
        shutil.copy(p, empty / p.name)
    env = {k: v for k, v in os.environ.items() if not k.startswith("FAL_API")}
    proc = subprocess.run([sys.executable, "-m", "formal_lab_eval.offline", *sorted(x.name for x in empty.iterdir()),
                           "--out", "report", "--title", "Offline report: scheduling strategies and the "
                                                        "observation-delay ablation"],
                          cwd=empty, env=env, capture_output=True, text=True, timeout=900)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "run.log").write_text(f"$ cd <empty dir> && python -m formal_lab_eval.offline <{n + 1} bundles> --out report"
                                 f"\n(exit {proc.returncode}; FAL_API_* unset)\n\n{proc.stdout}{proc.stderr}")
    for name in ("report.json", "report.csv", "report.md"):
        shutil.copy(empty / "report" / name, OUT / name)
    rep = json.loads((OUT / "report.json").read_text())
    print(json.dumps({"bundles": n + 1, "verified": len(rep["verification"]["verified"]),
                      "rejected": [r["bundle"] for r in rep["verification"]["rejected"]], "exit": proc.returncode}))
    shutil.rmtree(work)
    shutil.rmtree(empty)
    return 0 if len(rep["verification"]["rejected"]) == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
