"""Experiment matrices v2 and their reports (P2-080 … P2-085, P2-087).

A cell is a complete run configuration: scenario (and revision), the strategy of every participant, the
environment backend, the rule setting, the model version, seed, budget and mechanism ablations, plus the split
(dev / acceptance) its seed was fixed to in advance. `cell_id` derives from the digest of that configuration, so the
same configuration is the same cell in every matrix (completed cells are deduplicated by it).

The report keeps apart what the task book keeps apart:
- run outcome (FAILED / CANCELLED …), goal not reached (a finished run that ended for another reason), metric
  missing — counted separately, with the actual denominators, per split;
- per-scenario aggregates over seeds (independent unit: one seed of one scenario) and a pooled estimate whose
  interval resamples *scenarios* (cluster bootstrap), never treating correlated records as independent;
- paired comparisons along one dimension at a time — the method (participants), a mechanism (ablation), the
  environment backend, the rules, the model version — pairing cells equal in every other dimension; method effects
  and environment differences are therefore never mixed;
- evaluator scores and independent probe observations side by side, each with its source.
"""

from __future__ import annotations

import csv
import io
import random
import statistics
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import MetricDefinition, MetricResult, MetricStatus, digest_of

from .stats import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, aggregate, paired_compare

DIMENSIONS = {"participants": "method", "ablation": "mechanism", "backend": "environment", "rules": "rules",
              "model": "model version"}
GOAL_REASONS = {"JOINT_GOAL_REACHED", "ACTOR_GOAL_REACHED", "ALL_ACTOR_GOALS_REACHED"}
FINISHED = {"SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"}


def config_digest(config: dict[str, Any]) -> str:
    return digest_of(config).value


def cell_id_of(digest: str) -> str:
    return f"cell_{digest[:16]}"


@dataclass(frozen=True)
class CellKey:
    scenario: str
    participants: str
    backend: str
    rules: str
    model: str
    ablation: str
    budget: str
    seed: int
    split: str

    def without(self, dim: str) -> tuple:
        return tuple(getattr(self, f) for f in ("split", "scenario", "participants", "backend", "rules", "model",
                                                  "ablation", "budget", "seed") if f != dim)


@dataclass
class CellResult:
    cell_id: str
    key: CellKey
    run_id: str | None
    status: str  # run status, or NOT_RUN (queued / could not start)
    termination_reason: str | None = None
    metrics: dict[str, MetricResult] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)  # dimension → human label
    # phase 4A
    status_reason: str | None = None
    reused_from: dict[str, Any] | None = None  # the completed cell whose run this cell reuses
    reuse_note: str | None = None  # why it was (not) reused
    participants_digest: str | None = None  # the effective strategies, to refuse comparing a strategy with itself
    sampling: str | None = None  # DETERMINISTIC / RECORDED (reused model decisions) / RESAMPLED (new model run)

    @property
    def goal_reached(self) -> bool | None:
        if self.status not in FINISHED:
            return None
        return self.termination_reason in GOAL_REASONS


def _cluster_bootstrap(by_cluster: dict[str, list[float]], level: float = 0.95) -> tuple[float, float] | None:
    clusters = [v for v in by_cluster.values() if v]
    if len(clusters) < 2:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        pick = [rng.choice(clusters) for _ in clusters]
        means.append(statistics.fmean(statistics.fmean(c) for c in pick))
    means.sort()
    return means[int((1 - level) / 2 * BOOTSTRAP_RESAMPLES)], \
        means[min(BOOTSTRAP_RESAMPLES - 1, int((1 + level) / 2 * BOOTSTRAP_RESAMPLES))]


def _ok(r: MetricResult | None) -> bool:
    return r is not None and r.status is MetricStatus.OK and r.value is not None


def _not_applicable(r: MetricResult | None) -> bool:
    return r is not None and r.status is MetricStatus.NOT_APPLICABLE


def build_report(definitions: list[MetricDefinition], sources: dict[str, str], cells: list[CellResult]) -> dict:
    defs = {d.metric_id: d for d in definitions}
    splits = sorted({c.key.split for c in cells})
    out: dict[str, Any] = {"splits": {}, "definitions": [d.model_dump(mode="json") for d in definitions],
                           "metric_sources": sources}
    for split in splits:
        mine = [c for c in cells if c.key.split == split]
        section: dict[str, Any] = {"cells": len(mine), "outcomes": _outcomes(mine, defs)}
        # per-scenario aggregates over seeds
        groups: dict[tuple, list[CellResult]] = {}
        for c in mine:
            k = c.key
            groups.setdefault((k.scenario, k.participants, k.backend, k.rules, k.model, k.ablation, k.budget),
                              []).append(c)
        rows = []
        for gk, members in sorted(groups.items()):
            row: dict[str, Any] = dict(zip(("scenario", "participants", "backend", "rules", "model", "ablation",
                                            "budget"), gk, strict=True))
            row["labels"] = members[0].labels
            row["unit"] = "one seed of this scenario"
            row["n_cells"] = len(members)
            row["metrics"] = {}
            for mid, d in defs.items():
                results = [m.metrics.get(mid) or MetricResult(metric_id=mid, metric_version=d.version,
                                                              subject=m.cell_id, value=None, status="MISSING",
                                                              missing_reason="no value (run failed, not run or "
                                                                             "metric not produced)")
                           for m in members]
                agg, notes = aggregate(d, results, subject="|".join(map(str, gk)))
                row["metrics"][mid] = {"value": agg.value, "status": agg.status.value, "n": notes["n"],
                                       "missing": notes["missing"],
                                       "ci": agg.ci.model_dump() if agg.ci else None, "source": sources.get(mid)}
            rows.append(row)
        section["per_scenario"] = rows
        # pooled across scenarios, clustered by scenario
        pooled_groups: dict[tuple, list[CellResult]] = {}
        for c in mine:
            k = c.key
            pooled_groups.setdefault((k.participants, k.backend, k.rules, k.model, k.ablation, k.budget),
                                     []).append(c)
        pooled = []
        for gk, members in sorted(pooled_groups.items()):
            row = dict(zip(("participants", "backend", "rules", "model", "ablation", "budget"), gk, strict=True))
            row["unit"] = "scenario (cluster); seeds within a scenario are not independent"
            row["metrics"] = {}
            for mid in defs:
                by_sc: dict[str, list[float]] = {}
                for m in members:
                    r = m.metrics.get(mid)
                    if _ok(r):
                        by_sc.setdefault(m.key.scenario, []).append(float(r.value))
                if not by_sc:
                    row["metrics"][mid] = {"value": None, "status": "MISSING", "clusters": 0, "n": 0}
                    continue
                value = statistics.fmean(statistics.fmean(v) for v in by_sc.values())
                ci = _cluster_bootstrap(by_sc)
                row["metrics"][mid] = {"value": value, "status": "OK", "clusters": len(by_sc),
                                       "n": sum(len(v) for v in by_sc.values()),
                                       "ci": {"low": ci[0], "high": ci[1], "level": 0.95,
                                              "method": "scenario-cluster bootstrap of the mean of scenario means"}
                                       if ci else None,
                                       "ci_note": None if ci else "one scenario: no cross-scenario interval",
                                       "source": sources.get(mid)}
            pooled.append(row)
        section["pooled"] = pooled
        section["comparisons"] = _comparisons(mine, defs)
        out["splits"][split] = section
    return out


def _timed_out(c: CellResult) -> bool:
    text = (c.status_reason or "").lower()
    return c.status == "TIMED_OUT" or "wall-clock" in text or "timed out" in text or "timeout" in text


def _outcomes(cells: list[CellResult], defs: dict[str, MetricDefinition]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    for c in cells:
        statuses[c.status] = statuses.get(c.status, 0) + 1
    finished = [c for c in cells if c.status in FINISHED]
    reached = sum(1 for c in finished if c.goal_reached)
    missing_reasons: dict[str, dict[str, int]] = {}
    for c in finished:
        for mid in defs:
            r = c.metrics.get(mid)
            if r is not None and not _ok(r):
                why = f"{r.status.value}: {r.missing_reason or 'no value'}"
                missing_reasons.setdefault(mid, {})[why] = missing_reasons.setdefault(mid, {}).get(why, 0) + 1
    sampling: dict[str, int] = {}
    for c in cells:
        sampling[c.sampling or "UNKNOWN"] = sampling.get(c.sampling or "UNKNOWN", 0) + 1
    return {
        # phase 4A: the success rate's denominator is fixed by the experiment definition before any run — every
        # planned cell of the split; a failed, cancelled, timed-out or never-run cell counts as not reached
        "success": {"definition": "goal reached / every planned cell of this split (fixed before the runs; failed, "
                                  "cancelled, timed-out and not-run cells count as not reached)",
                    "numerator": reached, "denominator": len(cells),
                    "rate": reached / len(cells) if cells else None,
                    "finished_only": {"numerator": reached, "denominator": len(finished),
                                      "rate": reached / len(finished) if finished else None,
                                      "note": "for reference only: excludes cells whose run did not finish"}},
        "timed_out": [{"cell_id": c.cell_id, "run_id": c.run_id, "status": c.status, "reason": c.status_reason}
                      for c in cells if _timed_out(c)],
        "reused": [{"cell_id": c.cell_id, "run_id": c.run_id, "reused_from": c.reused_from, "reason": c.reuse_note}
                   for c in cells if c.reused_from],
        "new_runs": sum(1 for c in cells if c.run_id and not c.reused_from),
        "not_reused": [{"cell_id": c.cell_id, "reason": c.reuse_note} for c in cells
                       if not c.reused_from and c.reuse_note],
        "sampling": sampling,
        "metric_missing_reasons": missing_reasons,

        "denominator_cells": len(cells),
        "run_status": statuses,
        "not_run": sum(1 for c in cells if c.status == "NOT_RUN"),
        "run_failed": sum(1 for c in cells if c.status in ("FAILED", "CANCELLED")),
        "finished": len(finished),
        "goal_reached": sum(1 for c in finished if c.goal_reached),
        "goal_not_reached": [{"cell_id": c.cell_id, "run_id": c.run_id, "status": c.status,
                              "termination_reason": c.termination_reason} for c in finished if not c.goal_reached],
        # missing = the evaluator produced the metric without a value (MISSING / ERROR) or the run failed before
        # scoring; a metric a run's evaluators never produce is not applicable to it, not missing
        "metric_missing": {mid: sum(1 for c in finished if (mid in c.metrics or not c.metrics)
                                    and not _ok(c.metrics.get(mid)) and not _not_applicable(c.metrics.get(mid)))
                           for mid in defs},
        "metric_not_applicable": {mid: n for mid in defs
                                  if (n := sum(1 for c in finished if _not_applicable(c.metrics.get(mid))))},
        "failures": [{"cell_id": c.cell_id, "run_id": c.run_id, "status": c.status,
                      "termination_reason": c.termination_reason, "reason": c.status_reason}
                     for c in cells if c.status in ("FAILED", "CANCELLED", "NOT_RUN")],
    }


def _comparisons(cells: list[CellResult], defs: dict[str, MetricDefinition]) -> list[dict[str, Any]]:
    out = []
    applicable = {mid for mid in defs if any(not _not_applicable(c.metrics.get(mid)) and mid in c.metrics
                                             for c in cells)}
    for dim, kind in DIMENSIONS.items():
        values = sorted({getattr(c.key, dim) for c in cells})
        if len(values) < 2:
            continue
        # the reference is the unmodified configuration when there is one (no ablation, the scenario's own
        # backend / rules), so every variant is compared against it rather than against another variant
        base = next((v for v in ("none", "scenario", "scenario-default") if v in values), values[0])
        for other in [v for v in values if v != base]:
            if dim == "participants" and _same_strategy(cells, base, other):
                out.append({"dimension": dim, "kind": kind, "a_key": base, "b_key": other, "skipped": True,
                            "reason": "both sides run the same strategies (same effective configuration): not a "
                                      "comparison of different methods"})
                continue
            for mid, d in defs.items():
                if mid not in applicable:  # the metric does not apply to these runs: nothing to compare
                    continue
                side: dict[str, dict[tuple, MetricResult]] = {base: {}, other: {}}
                for c in cells:
                    v = getattr(c.key, dim)
                    if v not in side:
                        continue
                    r = c.metrics.get(mid)
                    if r is None:
                        if c.metrics and c.status not in ("FAILED", "CANCELLED", "NOT_RUN"):
                            continue  # this run's evaluators do not produce the metric: not applicable to it
                        # phase 4A: a run that failed or never ran stays visible as an incomplete pair, with why
                        r = MetricResult(metric_id=mid, metric_version=d.version, subject=c.cell_id, value=None,
                                         status="MISSING", missing_reason=f"run {c.status}"
                                         + (f": {c.status_reason}" if c.status_reason else ""))
                    side[v][c.key.without(dim)] = r
                cmp = paired_compare(d, _dim_label(cells, dim, base), _dim_label(cells, dim, other), side[base],
                                     side[other])
                row = cmp.as_dict()
                row.update({"dimension": dim, "kind": kind, "a_key": base, "b_key": other,
                            "paired_on": "all other dimensions equal (scenario, seed, budget, …)"})
                row["pairs"] = row["pairs"][:20]
                out.append(row)
    return out


def _same_strategy(cells: list[CellResult], a: str, b: str) -> bool:
    da = {c.participants_digest for c in cells if c.key.participants == a}
    db = {c.participants_digest for c in cells if c.key.participants == b}
    return bool(da) and None not in da and da == db


def _dim_label(cells: list[CellResult], dim: str, value: str) -> str:
    return next((c.labels.get(dim, value) for c in cells if getattr(c.key, dim) == value), value)


# ------------------------------------------------------------------ exports


def to_csv(report: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["section", "split", "scenario", "participants", "backend", "rules", "model", "ablation", "budget",
                "metric", "value", "ci_low", "ci_high", "n", "missing_or_unpaired", "source_or_kind"])
    for split, sec in report["splits"].items():
        for row in sec["per_scenario"]:
            for mid, m in row["metrics"].items():
                ci = m.get("ci") or {}
                w.writerow(["per_scenario", split, row["scenario"], row["participants"], row["backend"], row["rules"],
                            row["model"], row["ablation"], row["budget"], mid, m["value"], ci.get("low"),
                            ci.get("high"), m["n"], m["missing"], m.get("source")])
        for row in sec["pooled"]:
            for mid, m in row["metrics"].items():
                ci = m.get("ci") or {}
                w.writerow(["pooled", split, "*", row["participants"], row["backend"], row["rules"], row["model"],
                            row["ablation"], row["budget"], mid, m["value"], ci.get("low"), ci.get("high"),
                            m.get("n"), "", m.get("source")])
        for c in sec["comparisons"]:
            if c.get("skipped"):
                continue
            ci = c.get("ci") or {}
            w.writerow(["comparison", split, "*", f"{c['a']} → {c['b']}", "", "", "", "", "", c["metric_id"],
                        c["mean_diff_b_minus_a"], ci.get("low"), ci.get("high"), c["n_pairs"], c["unpaired"],
                        f"{c['dimension']} ({c['kind']})"])
    return buf.getvalue()


def conclusions(report: dict[str, Any], defs: list[MetricDefinition]) -> list[str]:
    """Plain engineering conclusions: data quality first, then differences whose interval excludes zero."""
    out: list[str] = []
    for split, sec in report["splits"].items():
        o = sec["outcomes"]
        out.append(f"[{split}] {o['denominator_cells']} cell(s): {o['finished']} finished, {o['run_failed']} failed or "
                   f"cancelled, {o['not_run']} not run; goal reached in {o['goal_reached']} of {o['finished']}; "
                   f"missing metrics: " + (", ".join(f"{k} {v}" for k, v in o["metric_missing"].items() if v)
                                            or "none"))
        sc = o.get("success") or {}
        if sc:
            rate = "—" if sc.get("rate") is None else f"{sc['rate']:.0%}"
            out.append(f"[{split}] success {sc['numerator']}/{sc['denominator']} = {rate} (denominator: every planned "
                       f"cell); timed out {len(o.get('timed_out', []))}, reused {len(o.get('reused', []))}, new runs "
                       f"{o.get('new_runs', 0)}")
        for c in sec["comparisons"]:
            if c.get("skipped"):
                out.append(f"[{split}] {c['kind']} {c['a_key']} vs {c['b_key']}: not compared — {c['reason']}")
        empty = [c for c in sec["comparisons"] if not c.get("skipped") and c["n_pairs"] == 0]
        if empty:
            out.append(f"[{split}] {len(empty)} comparison(s) have no complete pairs (the metric is missing on one side "
                       "or the dimension varies only where the other does not) — no conclusion from them")
        for c in sec["comparisons"]:
            ci = c.get("ci")
            if c.get("skipped") or c["n_pairs"] == 0:
                continue
            if ci and (ci["low"] > 0 or ci["high"] < 0) and c.get("better"):
                reading = " — engineering reading (small sample)" if c.get("reading") == "ENGINEERING" else ""
                out.append(f"[{split}] {c['kind']}: {c['better']} is better on {c['metric_id']} (mean paired "
                           f"difference {c['mean_diff_b_minus_a']:+.3g}, 95% CI [{ci['low']:+.3g}, {ci['high']:+.3g}], "
                           f"{c['n_pairs']} pairs, {c['unpaired']} unpaired){reading}")
    if not any("better" in line for line in out):
        out.append("no paired difference has an interval excluding zero at this sample size")
    return out


def to_markdown(report: dict[str, Any], title: str, defs: list[MetricDefinition]) -> str:
    lines = [f"# {title}", "", "## Conclusions", ""]
    lines += [f"- {c}" for c in conclusions(report, defs)]
    for split, sec in report["splits"].items():
        o = sec["outcomes"]
        sc = o.get("success") or {}
        lines += ["", f"## Split `{split}`", "",
                  f"Denominator: {o['denominator_cells']} cells — run status {o['run_status']}; goal not reached: "
                  f"{len(o['goal_not_reached'])}; missing metrics {o['metric_missing']}.", "",
                  f"Success: {sc.get('numerator')}/{sc.get('denominator')} ({sc.get('definition')}); finished only "
                  f"{(sc.get('finished_only') or {}).get('numerator')}/{(sc.get('finished_only') or {}).get('denominator')}"
                  f". Timed out: {len(o.get('timed_out', []))}. Reused: {len(o.get('reused', []))} "
                  f"({'; '.join(sorted({str(r['reason']) for r in o.get('reused', [])})) or '—'}); new runs "
                  f"{o.get('new_runs', 0)}; sampling {o.get('sampling', {})}.", "",
                  "### Per scenario (unit: one seed of one scenario)", "",
                  "| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n "
                  "| missing | source |", "|" + "---|" * 13]
        for row in sec["per_scenario"]:
            for mid, m in row["metrics"].items():
                ci = m.get("ci")
                lines.append(f"| {row['labels'].get('scenario', row['scenario'])} | "
                             f"{row['labels'].get('participants', row['participants'])} | {row['backend']} | "
                             f"{row['rules']} | {row['model']} | {row['ablation']} | {row['budget']} | {mid} | "
                             f"{_fmt(m['value'])} | {_ci(ci)} | {m['n']} | {m['missing']} | {m.get('source') or ''} |")
        lines += ["", "### Pooled across scenarios (unit: scenario; cluster bootstrap)", "",
                  "| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios "
                  "| n |", "|" + "---|" * 11]
        for row in sec["pooled"]:
            for mid, m in row["metrics"].items():
                lines.append(f"| {row['participants']} | {row['backend']} | {row['rules']} | {row['model']} | "
                             f"{row['ablation']} | {row['budget']} | {mid} | {_fmt(m['value'])} | {_ci(m.get('ci'))} | "
                             f"{m.get('clusters', 0)} | {m.get('n', 0)} |")
        lines += ["", "### Paired comparisons (one dimension at a time)", "",
                  "| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |",
                  "|" + "---|" * 10]
        for c in sec["comparisons"]:
            if c.get("skipped"):
                lines.append(f"| {c['kind']} | {c['a_key']} | {c['b_key']} | — | — | — | — | — | — | {c['reason']} |")
                continue
            test = c["test"]
            t = f"p={test['p_value']:.3g}" if test.get("reported") else (test.get("reason") or "")[:60]
            lines.append(f"| {c['kind']} | {c['a']} | {c['b']} | {c['metric_id']} | {_fmt(c['mean_diff_b_minus_a'])} | "
                         f"{_ci(c.get('ci'))} | {c['n_pairs']} | {c['unpaired']} | {c.get('better') or '—'} | {t} "
                         f"({c.get('reading', '').lower()}) |")
            for u in c.get("unpaired_detail", [])[:10]:
                lines.append(f"|  | incomplete pair {u['key']} | missing {u['missing']} | a: {u['a']} | b: {u['b']} "
                             "| | | | | |")
    lines += ["", "## Metric sources", ""]
    lines += [f"- `{k}`: {v}" for k, v in sorted(report["metric_sources"].items())]
    return "\n".join(lines) + "\n"


def _fmt(v: Any) -> str:
    return "—" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v))


def _ci(ci: dict[str, Any] | None) -> str:
    return "—" if not ci else f"[{ci['low']:.3g}, {ci['high']:.3g}]"
