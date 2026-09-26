"""Aggregation and comparison statistics for experiment matrices (pure Python, deterministic).

Missing semantics
- MISSING / ERROR results carry no value; they are excluded from the aggregate and counted in `missing_count`.
- NOT_APPLICABLE results are excluded and not counted as missing (the metric does not apply to that run).
- An aggregate with no observed value is itself MISSING (never 0).

Intervals
- RATE (0/1 values): Wilson score interval.
- MEAN: percentile bootstrap (5,000 resamples, fixed seed) when n ≥ 3; otherwise no interval is reported.
- Other aggregations: no interval.

Paired comparison (same scenario, seed and budget): mean difference B − A with a bootstrap interval (n ≥ 3), and
the exact two-sided Wilcoxon signed-rank test, reported only when there are ≥ 6 non-zero paired differences
(below that no two-sided p-value can reach 0.05, so the test is not informative and is not reported).
"""

from __future__ import annotations

import itertools
import math
import random
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import Aggregation, ConfidenceInterval, MetricDefinition, MetricResult, MetricStatus

BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260926
MIN_N_BOOTSTRAP = 3
MIN_NONZERO_FOR_TEST = 6


def _values(results: list[MetricResult]) -> tuple[list[float], int, int]:
    values, missing, not_applicable = [], 0, 0
    for r in results:
        if r.status is MetricStatus.OK and r.value is not None:
            values.append(float(r.value))
        elif r.status is MetricStatus.NOT_APPLICABLE:
            not_applicable += 1
        else:
            missing += 1
    return values, missing, not_applicable


def wilson(successes: float, n: int, level: float = 0.95) -> tuple[float, float]:
    z = statistics.NormalDist().inv_cdf(0.5 + level / 2)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def bootstrap_mean(values: list[float], level: float = 0.95, seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(BOOTSTRAP_RESAMPLES))
    lo = means[int((1 - level) / 2 * BOOTSTRAP_RESAMPLES)]
    hi = means[min(BOOTSTRAP_RESAMPLES - 1, int((1 + level) / 2 * BOOTSTRAP_RESAMPLES))]
    return lo, hi


def aggregate(definition: MetricDefinition, results: list[MetricResult], subject: str,
              level: float = 0.95) -> tuple[MetricResult, dict[str, Any]]:
    values, missing, not_applicable = _values(results)
    notes: dict[str, Any] = {"n": len(values), "missing": missing, "not_applicable": not_applicable,
                             "direction": definition.direction.value}
    if not values:
        reason = (f"no observed values ({missing} missing, {not_applicable} not applicable of {len(results)} runs)")
        return MetricResult(metric_id=definition.metric_id, metric_version=definition.version, subject=subject,
                            value=None, status="MISSING", missing_reason=reason, unit=definition.unit,
                            sample_size=0, missing_count=missing, aggregation=definition.aggregation), notes
    agg = definition.aggregation
    ci = None
    if agg is Aggregation.RATE:
        value = sum(1.0 for v in values if v) / len(values)
        lo, hi = wilson(value * len(values), len(values), level)
        ci = ConfidenceInterval(low=lo, high=hi, level=level, method="Wilson score interval", n=len(values))
    elif agg is Aggregation.MEAN:
        value = statistics.fmean(values)
        if len(values) >= MIN_N_BOOTSTRAP:
            lo, hi = bootstrap_mean(values, level)
            ci = ConfidenceInterval(low=lo, high=hi, level=level,
                                    method=f"percentile bootstrap of the mean ({BOOTSTRAP_RESAMPLES} resamples, "
                                           f"seed {BOOTSTRAP_SEED})", n=len(values))
        else:
            notes["ci_note"] = f"no interval: n={len(values)} < {MIN_N_BOOTSTRAP}"
    elif agg is Aggregation.SUM:
        value = sum(values)
    elif agg is Aggregation.MEDIAN:
        value = statistics.median(values)
    elif agg is Aggregation.MIN:
        value = min(values)
    else:
        value = max(values)
    return MetricResult(metric_id=definition.metric_id, metric_version=definition.version, subject=subject,
                        value=value, status="OK", unit=definition.unit, sample_size=len(values), missing_count=missing,
                        aggregation=agg, ci=ci), notes


# ------------------------------------------------------------------------------ paired comparison


def _ranks(abs_values: list[float]) -> list[float]:
    order = sorted(range(len(abs_values)), key=lambda i: abs_values[i])
    ranks = [0.0] * len(abs_values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs_values[order[j + 1]] == abs_values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def wilcoxon_signed_rank(diffs: list[float]) -> dict[str, Any]:
    """Exact two-sided test on non-zero differences (sign enumeration, tie-aware); normal approx above n=20."""
    d = [x for x in diffs if x != 0]
    n = len(d)
    if n == 0:
        return {"n_nonzero": 0, "w_plus": 0.0, "p_value": 1.0, "method": "no non-zero differences"}
    ranks = _ranks([abs(x) for x in d])
    w_plus = sum(r for r, x in zip(ranks, d, strict=True) if x > 0)
    if n <= 20:
        twice = [int(round(2 * r)) for r in ranks]
        dist: Counter[int] = Counter({0: 1})
        for r in twice:  # distribution of 2·W+ under H0 (each sign ±1 w.p. 1/2)
            nxt: Counter[int] = Counter()
            for s, c in dist.items():
                nxt[s] += c
                nxt[s + r] += c
            dist = nxt
        total = 2 ** n
        w2 = int(round(2 * w_plus))
        lower = sum(c for s, c in dist.items() if s <= w2) / total
        upper = sum(c for s, c in dist.items() if s >= w2) / total
        return {"n_nonzero": n, "w_plus": w_plus, "p_value": min(1.0, 2 * min(lower, upper)),
                "method": "Wilcoxon signed-rank, exact, two-sided (zeros dropped, average ranks for ties)"}
    mean = n * (n + 1) / 4
    ties = Counter(ranks)
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(t ** 3 - t for t in ties.values()) / 48
    z = (w_plus - mean) / math.sqrt(var)
    p = 2 * (1 - statistics.NormalDist().cdf(abs(z)))
    return {"n_nonzero": n, "w_plus": w_plus, "p_value": p,
            "method": "Wilcoxon signed-rank, normal approximation with tie correction, two-sided"}


@dataclass
class PairedComparison:
    metric_id: str
    a: str
    b: str
    n_pairs: int
    pairs: list[dict[str, Any]] = field(default_factory=list)
    mean_diff: float | None = None
    ci: ConfidenceInterval | None = None
    better: str | None = None
    test: dict[str, Any] = field(default_factory=dict)
    unpaired: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"metric_id": self.metric_id, "a": self.a, "b": self.b, "n_pairs": self.n_pairs,
                "mean_diff_b_minus_a": self.mean_diff, "ci": self.ci.model_dump() if self.ci else None,
                "better": self.better, "test": self.test, "unpaired": self.unpaired, "pairs": self.pairs}


def paired_compare(definition: MetricDefinition, a_label: str, b_label: str,
                   a: dict[Any, MetricResult], b: dict[Any, MetricResult], level: float = 0.95) -> PairedComparison:
    """Pair by key (scenario, seed, budget); pairs where either side has no value are counted as unpaired."""
    keys = sorted(set(a) | set(b), key=str)
    pairs, unpaired = [], 0
    for k in keys:
        ra, rb = a.get(k), b.get(k)
        if ra is None or rb is None or ra.value is None or rb.value is None or \
                ra.status is not MetricStatus.OK or rb.status is not MetricStatus.OK:
            unpaired += 1
            continue
        pairs.append({"key": list(k) if isinstance(k, tuple) else k, "a": ra.value, "b": rb.value,
                      "diff": rb.value - ra.value})
    cmp = PairedComparison(definition.metric_id, a_label, b_label, len(pairs), pairs, unpaired=unpaired)
    if not pairs:
        cmp.test = {"reported": False, "reason": "no complete pairs"}
        return cmp
    diffs = [p["diff"] for p in pairs]
    cmp.mean_diff = statistics.fmean(diffs)
    if len(diffs) >= MIN_N_BOOTSTRAP:
        lo, hi = bootstrap_mean(diffs, level)
        cmp.ci = ConfidenceInterval(low=lo, high=hi, level=level, n=len(diffs),
                                    method=f"percentile bootstrap of the mean paired difference "
                                           f"({BOOTSTRAP_RESAMPLES} resamples, seed {BOOTSTRAP_SEED})")
    direction = definition.direction.value
    if cmp.mean_diff != 0 and direction != "NONE":
        b_better = (cmp.mean_diff > 0) == (direction == "HIGHER_IS_BETTER")
        cmp.better = b_label if b_better else a_label
    result = wilcoxon_signed_rank(diffs)
    if result["n_nonzero"] >= MIN_NONZERO_FOR_TEST:
        cmp.test = {"reported": True, **result, "alpha": 0.05, "significant": result["p_value"] < 0.05}
    else:
        cmp.test = {"reported": False, "n_nonzero": result["n_nonzero"],
                    "reason": f"significance not reported: {result['n_nonzero']} non-zero paired differences "
                              f"< {MIN_NONZERO_FOR_TEST} (exact two-sided p cannot reach 0.05)"}
    return cmp


def all_pairs(labels: list[str]) -> list[tuple[str, str]]:
    return list(itertools.combinations(sorted(labels), 2))
