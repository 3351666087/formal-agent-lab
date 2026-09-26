"""Inspect task for the neutral scheduling experiment.

    inspect eval examples/neutral-scheduling/src/formal_lab_example_scheduling/inspect_task.py \
        -T strategy=z3 -T seeds=1,2,3 --model mockllm/model --log-dir var/inspect/logs

The Inspect model argument is not used for decisions by rule / z3 strategies (mockllm is only a placeholder);
scores are the platform's deterministic MetricResults computed from the simulator truth state.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import PluginRef
from formal_lab_eval.inspect_adapter import platform_task
from formal_lab_runtime import default_registry, make_manifest, new_run_id
from inspect_ai import Task, task
from inspect_ai.dataset import Sample

from formal_lab_example_scheduling.scenarios import SCENARIO_CONFIGS, STRATEGIES, model_package, scenario

EVALUATORS = [PluginRef(plugin_id="formal-lab.eval.generic", version="1.0.0"),
              PluginRef(plugin_id="formal-lab.example.scheduling.scorer", version="1.0.0")]
ALWAYS = ["goal_reached", "delay_cost", "orders_completed", "steps_used", "rejected_actions"]


def _items(value: str | int | list) -> list[str]:
    """Inspect's CLI turns `-T seeds=1,2` into a list; accept lists, ints and comma strings."""
    if isinstance(value, list):
        return [str(v) for v in value]
    return [v for v in str(value).split(",") if v]


@task
def neutral_scheduling(strategy: str = "rule", scenarios: str | list = ",".join(SCENARIO_CONFIGS),
                       seeds: str | list = "1,2", bundle_dir: str = "var/inspect/bundles") -> Task:
    package = model_package()
    registry = default_registry()
    keys = _items(scenarios)
    seed_list = [int(x) for x in _items(seeds)]
    samples = [Sample(id=f"{key}-s{seed}-{strategy}", input=f"{SCENARIO_CONFIGS[key]['name']} (seed {seed})",
                      target="all_done", metadata={"scenario": key, "seed": seed, "strategy": strategy})
               for key in keys for seed in seed_list]

    def factory(meta: dict[str, Any]):
        sc = scenario(meta["scenario"], package, seed=meta["seed"], strategy=STRATEGIES[meta["strategy"]])
        manifest = make_manifest(run_id=new_run_id(), project_id="inspect", scenario=sc, package=package,
                                 registry=registry, evaluators=EVALUATORS)
        return manifest, package

    return platform_task(samples, factory, bundle_dir=bundle_dir, always=ALWAYS, name=f"neutral_scheduling_{strategy}")
