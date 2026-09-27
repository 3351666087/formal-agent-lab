"""Offline comparison report from replay bundles (P2-087): no server, no plugins, an empty working directory.

    python -m formal_lab_eval.offline bundles/*.replay.zip --out report/    (or: fal-report …)

Every bundle is verified first — readable format and contract version, content digests (the reader checks every
file against the bundle's digest list), causal order of events, required parts (manifest, events, model package,
metrics) and that the bundled model is the one the manifest pins. Bundles that fail are listed and excluded; the
report says so. The rest become matrix cells (dimension labels from the run's matrix configuration when present,
otherwise derived from the manifest) and go through the same v2 report as the platform: splits, per-scenario and
scenario-clustered pooled statistics, one-dimension paired comparisons, probes and evaluators with their sources,
failures / goal-not-reached / missing metrics with the actual denominators — written as JSON, CSV and Markdown with
explicit engineering conclusions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from formal_lab_contracts import MetricDefinition, MetricResult
from formal_lab_contracts.bundle import READABLE_FORMATS, read_bundle
from formal_lab_contracts.common import SUPPORTED_CONTRACT_VERSIONS
from formal_lab_contracts.errors import FormalLabError

from .experiments import (
    CellKey,
    CellResult,
    build_report,
    cell_id_of,
    conclusions,
    config_digest,
    to_csv,
    to_markdown,
)


def verify(path: Path) -> tuple[Any | None, list[str]]:
    problems: list[str] = []
    try:
        b = read_bundle(path.read_bytes())
    except FormalLabError as exc:
        return None, [f"unreadable: {exc.message}"]
    except Exception as exc:  # a truncated zip is a broken bundle, not a crash of the report
        return None, [f"unreadable: {type(exc).__name__}: {exc}"]
    if b.info.get("format") not in READABLE_FORMATS:
        problems.append(f"format {b.info.get('format')} is not readable here")
    if b.info.get("contract_version") not in SUPPORTED_CONTRACT_VERSIONS:
        problems.append(f"contract {b.info.get('contract_version')} is not supported")
    problems += [f"causality: {p}" for p in b.info.get("causality_problems", []) or b.verify_causality()]
    if not b.events:
        problems.append("no events")
    if b.package is None:
        problems.append("no model package")
    elif b.package.digest != b.manifest.model.digest:
        problems.append("bundled model is not the one the manifest pins")
    if not b.metrics and str(b.manifest.status.value) in ("SUCCEEDED", "BUDGET_EXHAUSTED"):
        problems.append("finished run without metrics")
    return b, problems


def _cell(b: Any) -> CellResult:
    m = b.manifest
    labels = dict(m.config.get("matrix_labels") or {})
    participants = labels.get("participants") or " + ".join(
        f"{p.actor_id}={p.strategy.plugin.plugin_id}" + (":stub" if p.strategy.config.get("client") == "stub" else "")
        for p in m.participants) if len(m.participants) > 1 else labels.get("participants") or (
        m.participants[0].strategy.plugin.plugin_id + (
            ":stub" if m.participants[0].strategy.config.get("client") == "stub" else ""))
    key = CellKey(scenario=m.scenario.scenario_id, participants=participants,
                  backend=labels.get("backend") or m.scenario.environment.plugin.plugin_id,
                  rules=labels.get("rules") or (f"{m.rules.ruleset_id}@{m.rules.version}" if m.rules else "none"),
                  model=labels.get("model") or f"{m.model.package_id}@{m.model.version}",
                  ablation=labels.get("ablation") or m.config.get("ablation", "none"),
                  budget=labels.get("budget") or m.config.get("matrix_budget_key", "scenario-default"),
                  seed=m.seed, split=m.config.get("matrix_split", "acceptance"))
    metrics = {x.metric_id: x for x in b.metrics}
    last: dict[str, Any] = {}
    for p in b.probes():
        if p.get("status") == "OK":
            last[p["metric"]] = p
    for metric, p in last.items():
        metrics[f"probe.{metric}"] = MetricResult(metric_id=f"probe.{metric}", metric_version="1", subject=m.run_id,
                                                  value=float(p["value"]), status="OK", unit=p.get("unit"))
    cid = m.config.get("matrix_cell") or cell_id_of(config_digest({"key": key.__dict__}))
    return CellResult(cell_id=cid, key=key, run_id=m.run_id, status=m.status.value,
                      termination_reason=m.termination_reason.value if m.termination_reason else None,
                      metrics=metrics, labels={"scenario": m.scenario.name, "participants": participants,
                                               **labels})


def build(paths: list[Path]) -> tuple[dict[str, Any], list[MetricDefinition]]:
    verified, rejected, cells = [], [], []
    defs: dict[str, MetricDefinition] = {}
    sources: dict[str, str] = {}
    for path in paths:
        b, problems = verify(path)
        if b is None or problems:
            rejected.append({"bundle": path.name, "problems": problems})
            continue
        verified.append({"bundle": path.name, "run_id": b.manifest.run_id, "format": b.info["format"],
                         "contract": b.info["contract_version"], "events": len(b.events),
                         "operations": len(b.operations)})
        for x in b.metrics:
            defs.setdefault(x.metric_id, MetricDefinition(
                metric_id=x.metric_id, label=x.metric_id, unit=x.unit or "",
                direction=_direction(b, x.metric_id), aggregation="MEAN", value_type="float"))
            ev = next((p.plugin_id for p in b.manifest.plugins if p.role.startswith("evaluator")), "evaluator")
            sources.setdefault(x.metric_id, f"evaluator ({ev}) as recorded in the bundle")
        for p in b.probes():
            mid = f"probe.{p['metric']}"
            defs.setdefault(mid, MetricDefinition(metric_id=mid, label=mid, unit=p.get("unit") or "", direction="NONE",
                                                  aggregation="MEAN", value_type="float"))
            sources.setdefault(mid, f"probe {p['probe']['plugin_id']} ({p['source']})")
        cells.append(_cell(b))
    report = build_report(list(defs.values()), sources, cells)
    report["verification"] = {"bundles": len(paths), "verified": verified, "rejected": rejected}
    report["conclusions"] = [f"{len(verified)} of {len(paths)} bundle(s) verified (format, contract, digests, "
                             f"causality, required parts); {len(rejected)} rejected and excluded",
                             *conclusions(report, list(defs.values()))]
    return report, list(defs.values())


def _direction(b: Any, metric_id: str) -> str:
    known = {"goal_reached": "HIGHER_IS_BETTER", "orders_completed": "HIGHER_IS_BETTER",
             "delay_cost": "LOWER_IS_BETTER", "steps_used": "LOWER_IS_BETTER", "makespan": "LOWER_IS_BETTER",
             "late_orders": "LOWER_IS_BETTER", "mean_tardiness": "LOWER_IS_BETTER", "effect_mismatches": "LOWER_IS_BETTER",
             "invalid_actions": "LOWER_IS_BETTER", "mean_latency": "LOWER_IS_BETTER"}
    return known.get(metric_id, "NONE")


def _package_of(path: Path) -> str:
    try:
        return read_bundle(path.read_bytes()).manifest.model.package_id
    except Exception:  # an unreadable bundle is reported by `build` of any group
        return "_unreadable"


def main(argv: list[str] | None = None) -> int:
    """One report per model package (metrics of different domains are never mixed), plus an index."""
    ap = argparse.ArgumentParser(description="offline comparison report from replay bundles")
    ap.add_argument("bundles", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("report"))
    ap.add_argument("--title", default="Offline comparison report")
    args = ap.parse_args(argv)
    groups: dict[str, list[Path]] = {}
    for p in args.bundles:
        groups.setdefault(_package_of(p), []).append(p)
    unreadable = groups.pop("_unreadable", [])
    args.out.mkdir(parents=True, exist_ok=True)
    index = [f"# {args.title}", "", "Bundles are verified first (format, contract version, digests, event causality, "
             "required parts, pinned model); one report per model package.", ""]
    rejected_total = 0
    for pkg, paths in sorted(groups.items()):
        report, defs = build(paths + (unreadable if pkg == sorted(groups)[0] else []))
        out = args.out / pkg
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n")
        (out / "report.csv").write_text(to_csv(report))
        md = to_markdown(report, f"{args.title} — {pkg}", defs)
        md = md.replace("## Conclusions\n\n", "## Conclusions\n\n" + f"- {report['conclusions'][0]}\n", 1)
        if report["verification"]["rejected"]:
            md += "\n## Rejected bundles\n\n" + "\n".join(f"- `{r['bundle']}`: {'; '.join(r['problems'])}"
                                                        for r in report["verification"]["rejected"]) + "\n"
        (out / "report.md").write_text(md)
        rejected_total += len(report["verification"]["rejected"])
        index += [f"## {pkg}", "", f"[report.md]({pkg}/report.md) · [report.csv]({pkg}/report.csv) · "
                  f"[report.json]({pkg}/report.json)", "", *[f"- {c}" for c in report["conclusions"]], ""]
        print(f"== {pkg}")
        for line in report["conclusions"]:
            print(line)
    (args.out / "index.md").write_text("\n".join(index) + "\n")
    return 0 if not rejected_total else 1


if __name__ == "__main__":
    sys.exit(main())
