from __future__ import annotations

import pytest
from formal_lab_contracts import MetricDefinition, MetricResult
from formal_lab_contracts.errors import InvalidInput
from formal_lab_eval.matrix import Cell, CellRun, build_report, expand
from formal_lab_eval.stats import aggregate, paired_compare, wilcoxon_signed_rank, wilson

COST = MetricDefinition(metric_id="delay_cost", label="cost", unit="cost", direction="LOWER_IS_BETTER",
                        aggregation="MEAN")
GOAL = MetricDefinition(metric_id="goal_reached", label="goal", unit="rate", direction="HIGHER_IS_BETTER",
                        aggregation="RATE", value_type="bool")


def ok(v, subject="r"):
    return MetricResult(metric_id="m", metric_version="1", subject=subject, value=v, status="OK")


def missing(subject="r"):
    return MetricResult(metric_id="m", metric_version="1", subject=subject, value=None, status="MISSING",
                        missing_reason="x")


def na(subject="r"):
    return MetricResult(metric_id="m", metric_version="1", subject=subject, value=None, status="NOT_APPLICABLE")


def test_aggregate_missing_semantics_and_intervals():
    agg, notes = aggregate(COST, [ok(2), ok(4), missing(), na(), ok(6)], "cell")
    assert agg.value == 4 and agg.sample_size == 3 and agg.missing_count == 1 and notes["not_applicable"] == 1
    assert agg.ci is not None and agg.ci.method.startswith("percentile bootstrap") and agg.ci.low <= 4 <= agg.ci.high
    small, notes = aggregate(COST, [ok(1), ok(3)], "cell")
    assert small.ci is None and "n=2" in notes["ci_note"]
    none, _ = aggregate(COST, [missing(), na()], "cell")
    assert none.status == "MISSING" and none.value is None and "1 missing, 1 not applicable" in none.missing_reason
    rate, _ = aggregate(GOAL, [ok(1), ok(1), ok(0), ok(1)], "cell")
    assert rate.value == 0.75 and rate.ci.method == "Wilson score interval" and 0 < rate.ci.low < 0.75 < rate.ci.high


def test_wilson_reference_values():
    lo, hi = wilson(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-3) and hi == pytest.approx(0.9433, abs=1e-3)


def _brute_force_p(diffs: list[float]) -> float:
    """Independent reference: enumerate all sign vectors over the ranks (no ties in these inputs)."""
    import itertools

    d = [x for x in diffs if x]
    order = sorted(range(len(d)), key=lambda i: abs(d[i]))
    rank = {i: r + 1 for r, i in enumerate(order)}
    w = sum(rank[i] for i in range(len(d)) if d[i] > 0)
    sums = [sum(rank[i] for i, sgn in enumerate(signs) if sgn) for signs in itertools.product([0, 1], repeat=len(d))]
    lower = sum(x <= w for x in sums) / len(sums)
    upper = sum(x >= w for x in sums) / len(sums)
    return min(1.0, 2 * min(lower, upper))


def test_wilcoxon_exact_matches_independent_enumeration():
    diffs = [6.0, 8.0, 14.0, 16.0, 23.0, 24.0, 28.0, 29.0, 41.0, -48.0]
    res = wilcoxon_signed_rank(diffs)
    assert res["n_nonzero"] == 10 and res["w_plus"] == 45
    # by hand: W- = 10; 43 of the 1024 sign vectors give W- <= 10, so p = 2 * 43 / 1024
    assert res["p_value"] == pytest.approx(86 / 1024) == pytest.approx(_brute_force_p(diffs))
    for diffs in ([1.0, -2.0, 3.0, 4.0, -5.0, 6.0, 7.0], [3.0, 1.0, 4.0, -1.5, 5.0, 9.0, -2.6, 5.3]):
        assert wilcoxon_signed_rank(diffs)["p_value"] == pytest.approx(_brute_force_p(diffs))
    assert wilcoxon_signed_rank([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])["p_value"] == pytest.approx(2 / 64)


def test_paired_comparison_reports_significance_only_when_conditions_hold():
    a = {("s", i, "b"): ok(10.0 + i) for i in range(8)}
    b = {("s", i, "b"): ok(8.0 + i + (0.1 if i == 3 else 0)) for i in range(8)}
    cmp = paired_compare(COST, "A", "B", a, b)
    assert cmp.n_pairs == 8 and cmp.mean_diff < 0 and cmp.better == "B"
    assert cmp.test["reported"] and cmp.test["significant"]
    few = paired_compare(COST, "A", "B", {k: a[k] for k in list(a)[:4]}, b)
    assert not few.test["reported"] and "< 6" in few.test["reason"] and few.unpaired == 4
    b[("s", 0, "b")] = missing()
    part = paired_compare(COST, "A", "B", a, b)
    assert part.n_pairs == 7 and part.unpaired == 1


def test_matrix_expansion_and_report():
    cells = expand({"scenarios": ["s1", "s2"], "strategies": ["rule", "z3"], "seeds": [1, 2, 3],
                    "budgets": [{}, {"max_steps": 20}]})
    assert len(cells) == 24 and cells[0].budget_key == "scenario-default"
    with pytest.raises(InvalidInput):
        expand({"scenarios": [], "strategies": ["x"]})
    runs = [CellRun(Cell("s1", st, seed, "d", ()), f"r-{st}-{seed}", "SUCCEEDED",
                    {"delay_cost": ok(float(seed if st == "rule" else seed - 1), f"r-{st}-{seed}")}, "S1", st, ["RULE"])
            for st in ("rule", "z3") for seed in (1, 2, 3)]
    report = build_report([COST], runs)
    assert len(report["cells"]) == 6 and len(report["aggregates"]) == 2
    z3 = next(a for a in report["aggregates"] if a["strategy"] == "z3")
    assert z3["metrics"]["delay_cost"]["result"]["value"] == 1.0 and z3["statuses"] == {"SUCCEEDED": 3}
    cmp = report["comparisons"][0]
    assert cmp["n_pairs"] == 3 and cmp["better"] == "z3" and not cmp["test"]["reported"]
