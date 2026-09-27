"""Inspect adapter: a real inspect_ai eval of the neutral task; platform ↔ Inspect conversions round-trip."""

from __future__ import annotations

from formal_lab_contracts.bundle import read_bundle
from formal_lab_eval.inspect_adapter import bundle_paths_from_log, metric_results_from_log
from inspect_ai import eval as inspect_eval


def test_inspect_eval_round_trip(tmp_path):
    from formal_lab_example_scheduling.inspect_task import neutral_scheduling

    task = neutral_scheduling(strategy="rule", scenarios="normal,expectation-mismatch", seeds="3",
                              bundle_dir=str(tmp_path / "bundles"))
    [log] = inspect_eval(task, model="mockllm/model", log_dir=str(tmp_path / "logs"), display="none")
    assert log.status == "success" and len(log.samples) == 2
    reducers = {s.name: s.metrics for s in log.results.scores}
    assert "goal_reached" in str(reducers) or log.results.scores  # Inspect aggregated the platform metrics
    per_sample = metric_results_from_log(log)
    bundles = bundle_paths_from_log(log)
    assert set(per_sample) == set(bundles) == {s.id for s in log.samples}
    for sample_id, path in bundles.items():
        with open(path, "rb") as fh:
            bundle = read_bundle(fh.read())
        assert [m.model_dump() for m in bundle.metrics] == [m.model_dump() for m in per_sample[sample_id]]
        assert bundle.manifest.status == "SUCCEEDED" and bundle.events[-1].event_type == "RUN_SUCCEEDED"
    mismatch = next(v for k, v in per_sample.items() if k.startswith("expectation-mismatch"))
    assert next(m for m in mismatch if m.metric_id == "effect_mismatches").value > 0
