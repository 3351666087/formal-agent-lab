"""Experiment matrices: scenario × strategy × seed × budget expansion and the comparison report."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

from formal_lab_contracts import MetricDefinition, MetricResult
from formal_lab_contracts.errors import InvalidInput

from .stats import aggregate, all_pairs, paired_compare

MAX_CELLS = 400


@dataclass(frozen=True)
class Cell:
    scenario: str
    strategy: str
    seed: int
    budget_key: str
    budget: tuple[tuple[str, Any], ...]

    def budget_dict(self) -> dict[str, Any]:
        return dict(self.budget)


def expand(spec: dict[str, Any]) -> list[Cell]:
    scenarios, strategies = list(spec.get("scenarios") or []), list(spec.get("strategies") or [])
    seeds = [int(s) for s in (spec.get("seeds") or [0])]
    budgets = spec.get("budgets") or [{}]
    if not scenarios or not strategies:
        raise InvalidInput("a matrix needs at least one scenario and one strategy")
    if len(set(seeds)) != len(seeds):
        raise InvalidInput("seeds must be unique")
    cells = []
    for sc, st, seed, b in itertools.product(scenarios, strategies, seeds, budgets):
        key = ",".join(f"{k}={v}" for k, v in sorted(b.items())) or "scenario-default"
        cells.append(Cell(sc, st, seed, key, tuple(sorted(b.items()))))
    if len(cells) > MAX_CELLS:
        raise InvalidInput(f"matrix has {len(cells)} cells (limit {MAX_CELLS})")
    return cells


@dataclass
class CellRun:
    cell: Cell
    run_id: str
    status: str
    metrics: dict[str, MetricResult]
    scenario_label: str
    strategy_label: str
    source_kinds: list[str]


def build_report(definitions: list[MetricDefinition], runs: list[CellRun]) -> dict[str, Any]:
    defs = {d.metric_id: d for d in definitions}
    groups: dict[tuple[str, str, str], list[CellRun]] = {}
    for r in runs:
        groups.setdefault((r.cell.scenario, r.cell.strategy, r.cell.budget_key), []).append(r)
    aggregates = []
    for (sc, st, bk), members in sorted(groups.items()):
        sample = members[0]
        row: dict[str, Any] = {"scenario": sc, "scenario_label": sample.scenario_label, "strategy": st,
                               "strategy_label": sample.strategy_label, "budget": bk, "runs": len(members),
                               "statuses": _count(m.status for m in members),
                               "source_kinds": sorted({k for m in members for k in m.source_kinds}), "metrics": {}}
        for mid, d in defs.items():
            results = [m.metrics.get(mid) or MetricResult(metric_id=mid, metric_version=d.version, subject=m.run_id,
                                                          value=None, status="MISSING",
                                                          missing_reason="run produced no value")
                       for m in members]
            agg, notes = aggregate(d, results, subject=f"{sc}|{st}|{bk}")
            row["metrics"][mid] = {"result": agg.model_dump(mode="json"), "notes": notes}
        aggregates.append(row)
    comparisons = []
    strategies = sorted({r.cell.strategy for r in runs})
    labels = {r.cell.strategy: r.strategy_label for r in runs}
    for a, b in all_pairs(strategies):
        for mid, d in defs.items():
            side = {s: {(r.cell.scenario, r.cell.seed, r.cell.budget_key): r.metrics.get(mid) for r in runs
                        if r.cell.strategy == s and r.metrics.get(mid) is not None} for s in (a, b)}
            cmp = paired_compare(d, labels[a], labels[b], side[a], side[b])
            comparisons.append({"strategy_a": a, "strategy_b": b, **cmp.as_dict()})
    return {
        "cells": [{"scenario": r.cell.scenario, "strategy": r.cell.strategy, "seed": r.cell.seed,
                   "budget": r.cell.budget_key, "run_id": r.run_id, "status": r.status} for r in runs],
        "aggregates": aggregates,
        "comparisons": comparisons,
        "definitions": [d.model_dump(mode="json") for d in definitions],
        "methods": {
            "missing": "MISSING/ERROR excluded and counted; NOT_APPLICABLE excluded, not counted as missing",
            "intervals": "RATE: Wilson score; MEAN: percentile bootstrap (n≥3); others: none",
            "pairing": "pairs share scenario, seed and budget; incomplete pairs are counted as unpaired",
            "significance": "exact Wilcoxon signed-rank, reported only with ≥6 non-zero paired differences",
        },
    }


def _count(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out
