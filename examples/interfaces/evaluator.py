"""Evaluator.score: deterministic metrics from the simulator truth of an episode."""

from formal_lab_example_scheduling.__main__ import EVALUATORS
from formal_lab_example_scheduling.scenarios import model_package, scenario
from formal_lab_runtime import default_registry, make_manifest, new_run_id, run_local

package, registry = model_package(), default_registry()
manifest = make_manifest(run_id=new_run_id(), project_id="example", scenario=scenario("normal", package, seed=1),
                         package=package, registry=registry, evaluators=EVALUATORS)
result = run_local(manifest, package, registry)  # run_local calls every pinned Evaluator.score at the end
for m in result.metrics:
    print(f"{m.metric_id:18s} {m.status.value:14s} {m.value}")
assert {m.metric_id for m in result.metrics} >= {"goal_reached", "delay_cost", "makespan"}
