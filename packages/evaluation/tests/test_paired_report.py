"""A paired report that can be checked by hand (phase 4A, A4): known inputs, every number recomputed here by plain
arithmetic — success over a fixed denominator, failed / timed-out / reused cells with reasons, incomplete pairs with
the side and reason, the engineering-reading label and a refused comparison of a strategy with itself."""

from __future__ import annotations

import statistics

from formal_lab_contracts import MetricDefinition, MetricResult
from formal_lab_eval.experiments import CellKey, CellResult, build_report, conclusions, to_markdown

COST = MetricDefinition(metric_id="delay_cost", label="cost", unit="cost", direction="LOWER_IS_BETTER",
                        aggregation="MEAN", observable="Σ late_cost × tardiness", window="whole run")

# rule vs z3 on one scenario, seeds 0..4; known costs
RULE = {0: 10.0, 1: 12.0, 2: 8.0, 3: 11.0, 4: 9.0}
Z3 = {0: 7.0, 1: 9.0, 2: 8.0, 3: None, 4: 5.0}  # seed 3: the z3 run failed (no metric)


def cell(strategy: str, seed: int, value: float | None, *, status: str = "SUCCEEDED", reason: str | None = None,
         reused: bool = False, digest: str | None = None) -> CellResult:
    key = CellKey(scenario="sc", participants=strategy, backend="scenario", rules="scenario", model="m@1",
                  ablation="none", budget="scenario-default", seed=seed, split="acceptance")
    metrics = {} if value is None else {"delay_cost": MetricResult(metric_id="delay_cost", metric_version="1",
                                                                   subject=f"{strategy}{seed}", value=value,
                                                                   status="OK")}
    if value is None and status == "SUCCEEDED":
        metrics = {"delay_cost": MetricResult(metric_id="delay_cost", metric_version="1", subject="x", value=None,
                                              status="MISSING", missing_reason="not all operations finished")}
    return CellResult(cell_id=f"{strategy}-{seed}", key=key, run_id=f"run_{strategy}_{seed}", status=status,
                      termination_reason="JOINT_GOAL_REACHED" if status == "SUCCEEDED" else "FAILED",
                      metrics=metrics, labels={"participants": strategy}, status_reason=reason,
                      reused_from={"matrix_id": "mx_a", "cell_id": f"{strategy}-{seed}"} if reused else None,
                      reuse_note="same full configuration completed in mx_a" if reused else None,
                      participants_digest=digest or strategy, sampling="DETERMINISTIC")


def cells() -> list[CellResult]:
    out = [cell("rule", s, v, reused=s < 2) for s, v in RULE.items()]
    for s, v in Z3.items():
        if v is None:
            out.append(cell("z3", s, None, status="FAILED", reason="worker error: solver crashed"))
        else:
            out.append(cell("z3", s, v))
    # a timed-out cell of a third strategy whose configuration equals the rule strategy's
    out.append(cell("edd-copy", 0, 10.0, digest="rule"))
    out.append(cell("edd-copy", 1, None, status="BUDGET_EXHAUSTED", reason="wall-clock budget exhausted (600s/600s)",
                    digest="rule"))
    return out


def test_report_matches_hand_arithmetic():
    report = build_report([COST], {"delay_cost": "evaluator test"}, cells())
    sec = report["splits"]["acceptance"]
    o = sec["outcomes"]
    # success: 12 planned cells; reached = every SUCCEEDED cell (5 rule + 4 z3 + 1 edd-copy) = 10
    assert o["success"]["denominator"] == 12 and o["success"]["numerator"] == 10
    assert o["success"]["finished_only"]["denominator"] == 12  # FAILED / BUDGET_EXHAUSTED runs also finished
    assert [t["cell_id"] for t in o["timed_out"]] == ["edd-copy-1"]
    assert sorted(r["cell_id"] for r in o["reused"]) == ["rule-0", "rule-1"] and o["new_runs"] == 10
    assert all(r["reason"] for r in o["reused"])
    assert o["failures"] == [{"cell_id": "z3-3", "run_id": "run_z3_3", "status": "FAILED",
                              "termination_reason": "FAILED", "reason": "worker error: solver crashed"}]
    comps = {(c["a_key"], c["b_key"]): c for c in sec["comparisons"]}
    z3 = comps.get(("edd-copy", "z3"))
    # base is the first value in sorted order ("edd-copy"); the rule-vs-copy comparison is refused (same strategy)
    assert comps[("edd-copy", "rule")]["skipped"] and "same strategies" in comps[("edd-copy", "rule")]["reason"]
    # edd-copy has seed 0 (10.0) and seed 1 (timed out); z3 has 0, 1, 2, 4 and a failed seed 3 → one pair (seed 0),
    # four incomplete pairs, each with the side and the reason
    assert z3 is not None and z3["n_pairs"] == 1 and z3["unpaired"] == 4 and z3["mean_diff_b_minus_a"] == -3.0
    why = {tuple(u["key"])[-1]: (u["missing"], u["a"], u["b"]) for u in z3["unpaired_detail"]}
    assert why[1] == ("a", "MISSING: run BUDGET_EXHAUSTED: wall-clock budget exhausted (600s/600s)", "present")
    assert why[3] == ("both", "no cell with this key on this side", "MISSING: run FAILED: worker error: solver crashed")
    assert why[2][0] == why[4][0] == "a"
    # rule vs z3 is not a base comparison here: recompute it directly with the same pairing rule
    from formal_lab_eval.stats import paired_compare

    a = {(s,): MetricResult(metric_id="delay_cost", metric_version="1", subject="r", value=v, status="OK")
         for s, v in RULE.items()}
    b = {(s,): MetricResult(metric_id="delay_cost", metric_version="1", subject="z", value=v, status="OK")
         for s, v in Z3.items() if v is not None}
    cmp = paired_compare(COST, "rule", "z3", a, b)
    diffs = [Z3[s] - RULE[s] for s in RULE if Z3[s] is not None]  # [-3, -3, 0, -4]
    assert cmp.n_pairs == 4 and cmp.unpaired == 1 and cmp.mean_diff == statistics.fmean(diffs) == -2.5
    assert cmp.unpaired_detail == [{"key": [3], "missing": "b", "a": "present",
                                    "b": "no cell with this key on this side"}]
    assert cmp.better == "z3" and cmp.reading == "ENGINEERING" and cmp.test["reported"] is False
    text = "\n".join(conclusions(report, [COST]))
    assert "success 10/12" in text and "not compared" in text
    md = to_markdown(report, "hand check", [COST])
    assert "incomplete pair" in md and "Timed out: 1" in md and "Reused: 2" in md
