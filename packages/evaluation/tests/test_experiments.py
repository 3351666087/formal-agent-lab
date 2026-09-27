"""Matrix v2 reports (P2-082 … P2-085, P2-087) on synthetic cells with known effects."""

from __future__ import annotations

import csv
import io

from formal_lab_contracts import MetricDefinition, MetricResult
from formal_lab_eval.experiments import CellKey, CellResult, build_report, conclusions, to_csv, to_markdown

DEFS = [MetricDefinition(metric_id="cost", label="cost", unit="c", direction="LOWER_IS_BETTER", aggregation="MEAN",
                         value_type="float"),
        MetricDefinition(metric_id="probe.throughput", label="throughput", unit="o/t", direction="NONE",
                         aggregation="MEAN", value_type="float")]
SOURCES = {"cost": "evaluator formal-lab.example.scorer", "probe.throughput": "probe x (GET /metrics)"}


def cells() -> list[CellResult]:
    """2 scenarios × 2 methods × 2 backends × seeds (dev 1..3, acceptance 4..9). Method B lowers cost by 2 on every
    cell; the service backend adds 1 everywhere (an environment difference, not a method effect); scenario s2 is
    3 more expensive than s1. One acceptance cell failed, one did not run, one ended without reaching the goal."""
    out = []
    for split, seeds in (("dev", [1, 2, 3]), ("acceptance", [4, 5, 6, 7, 8, 9])):
        for sc, base in (("s1", 10.0), ("s2", 13.0)):
            for method, delta in (("A", 0.0), ("B", -2.0)):
                for backend, env in (("pure", 0.0), ("service", 1.0)):
                    for seed in seeds:
                        key = CellKey(sc, method, backend, "scenario", "m@1", "none", "default", seed, split)
                        cid = f"{split}-{sc}-{method}-{backend}-{seed}"
                        value = base + delta + env + (seed % 3) * 0.1
                        status, reason = "SUCCEEDED", "JOINT_GOAL_REACHED"
                        metrics = {"cost": MetricResult(metric_id="cost", metric_version="1", subject=cid,
                                                        value=value, status="OK"),
                                   "probe.throughput": MetricResult(metric_id="probe.throughput", metric_version="1",
                                                                    subject=cid, value=0.5, status="OK")}
                        if cid == "acceptance-s1-A-pure-4":
                            status, reason, metrics = "FAILED", "FAILED", {}
                        if cid == "acceptance-s2-B-pure-5":
                            status, reason, metrics = "NOT_RUN", None, {}
                        if cid == "acceptance-s2-A-service-6":
                            status, reason = "BUDGET_EXHAUSTED", "BUDGET_EXHAUSTED"
                        out.append(CellResult(cell_id=cid, key=key, run_id=None if status == "NOT_RUN" else f"r{cid}",
                                              status=status, termination_reason=reason, metrics=metrics,
                                              labels={"participants": f"strategy {method}"}))
    return out


def test_outcomes_are_separated_with_actual_denominators():
    rep = build_report(DEFS, SOURCES, cells())
    assert set(rep["splits"]) == {"dev", "acceptance"}
    o = rep["splits"]["acceptance"]["outcomes"]
    assert o["denominator_cells"] == 2 * 2 * 2 * 6
    assert o["run_failed"] == 1 and o["not_run"] == 1 and o["finished"] == 47  # a failed run has finished
    assert [g["cell_id"] for g in o["goal_not_reached"]] == ["acceptance-s1-A-pure-4", "acceptance-s2-A-service-6"]
    assert o["metric_missing"]["cost"] == 1  # the failed run; the not-run cell is counted as not run, not missing
    assert rep["splits"]["dev"]["outcomes"]["run_failed"] == 0


def test_method_and_environment_effects_are_compared_separately():
    """P2-082: pairs differ in exactly one dimension; the method effect (−2) and the backend difference (+1) are
    reported as different kinds, each with its own pairs and unpaired count."""
    rep = build_report(DEFS, SOURCES, cells())
    comps = {(c["dimension"], c["metric_id"]): c for c in rep["splits"]["acceptance"]["comparisons"]}
    method = comps[("participants", "cost")]
    env = comps[("backend", "cost")]
    assert method["kind"] == "method" and env["kind"] == "environment"
    assert abs(method["mean_diff_b_minus_a"] - (-2.0)) < 1e-9 and method["better"] == "strategy B"
    assert abs(env["mean_diff_b_minus_a"] - 1.0) < 1e-9
    assert method["unpaired"] == 2 and method["n_pairs"] == 22  # failed + not-run cells break their pairs
    assert method["ci"]["high"] < 0 and method["test"]["reported"]


def test_statistics_name_their_independent_unit():
    """P2-084: per-scenario rows aggregate seeds of one scenario; pooled rows resample scenarios (clusters)."""
    rep = build_report(DEFS, SOURCES, cells())
    sec = rep["splits"]["acceptance"]
    row = next(r for r in sec["per_scenario"] if r["scenario"] == "s2" and r["participants"] == "B"
               and r["backend"] == "pure")
    assert row["unit"] == "one seed of this scenario" and row["metrics"]["cost"]["n"] == 5
    assert row["metrics"]["cost"]["missing"] == 1 and row["metrics"]["cost"]["source"].startswith("evaluator")
    pooled = next(r for r in sec["pooled"] if r["participants"] == "A" and r["backend"] == "pure")
    m = pooled["metrics"]["cost"]
    assert "cluster" in pooled["unit"] and m["clusters"] == 2 and m["ci"]["method"].startswith("scenario-cluster")
    assert m["ci"]["low"] <= m["value"] <= m["ci"]["high"]
    assert pooled["metrics"]["probe.throughput"]["source"].startswith("probe")


def test_exports_and_conclusions():
    """P2-087: CSV rows for every section, Markdown with conclusions first; conclusions state data quality and
    only differences whose interval excludes zero."""
    rep = build_report(DEFS, SOURCES, cells())
    rows = list(csv.DictReader(io.StringIO(to_csv(rep))))
    assert {r["section"] for r in rows} == {"per_scenario", "pooled", "comparison"}
    text = conclusions(rep, DEFS)
    assert any("1 failed or cancelled, 1 not run" in c for c in text)
    assert any("method: strategy B is better on cost" in c for c in text)
    md = to_markdown(rep, "Synthetic matrix", DEFS)
    assert md.startswith("# Synthetic matrix") and "## Conclusions" in md and "scenario-cluster" not in md[:200]
    assert "| environment |" in md and "probe x (GET /metrics)" in md
