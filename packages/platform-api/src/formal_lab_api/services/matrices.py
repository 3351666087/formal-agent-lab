"""Experiment matrices (scenario × strategy × seed × budget) and their comparison reports."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import MetricDefinition, MetricResult, PluginRef, RunManifest
from formal_lab_contracts.errors import InvalidInput
from formal_lab_eval.matrix import Cell, CellRun, build_report, expand
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Matrix, MetricRow, Project, Run, RunEvent, Scenario, StrategyConfig
from .common import get_or_404, new_id, registry
from .runs import create_run


def matrix_dict(mx: Matrix, s: Session) -> dict[str, Any]:
    runs = list(s.scalars(select(Run).where(Run.matrix_id == mx.id)))
    statuses: dict[str, int] = {}
    for r in runs:
        statuses[r.status] = statuses.get(r.status, 0) + 1
    return {"id": mx.id, "project_id": mx.project_id, "name": mx.name, "spec": mx.spec, "created_at": mx.created_at,
            "runs": len(runs), "statuses": statuses}


def create_matrix(s: Session, project_id: str, body: dict[str, Any]) -> tuple[Matrix, list[Run]]:
    get_or_404(s, Project, project_id, "project")
    spec = {"scenarios": body.get("scenarios", []), "strategies": body.get("strategies", []),
            "seeds": body.get("seeds", [0]), "budgets": body.get("budgets") or [{}], "source": "platform"}
    cells = expand(spec)
    for sid in spec["scenarios"]:
        get_or_404(s, Scenario, sid, "scenario")
    for stid in spec["strategies"]:
        get_or_404(s, StrategyConfig, stid, "strategy")
    mx = Matrix(id=new_id("mtx"), project_id=project_id, name=body.get("name") or "matrix", spec=spec)
    s.add(mx)
    s.flush()
    runs = []
    for cell in cells:
        run, _ = create_run(s, project_id, {"scenario_id": cell.scenario, "strategy_config_id": cell.strategy,
                                            "seed": cell.seed, "budget": cell.budget_dict(),
                                            "config": {"matrix_budget_key": cell.budget_key}},
                            matrix_id=mx.id, client_request_id=f"{mx.id}:{cell.scenario}:{cell.strategy}:{cell.seed}:"
                                                               f"{cell.budget_key}")
        runs.append(run)
    return mx, runs


def attach_runs(s: Session, matrix_id: str, run_ids: list[str]) -> None:
    for rid in run_ids:
        get_or_404(s, Run, rid, "run").matrix_id = matrix_id


def _strategy_label(manifest: RunManifest) -> tuple[str, str]:
    p = manifest.participants[0].strategy
    stub = p.config.get("client") == "stub"
    entry = registry().get(p.plugin)
    key = p.plugin.plugin_id + (":stub" if stub else "")
    return key, entry.descriptor.ui.label + (" (stub)" if stub else "")


def report(s: Session, matrix_id: str) -> dict[str, Any]:
    mx = get_or_404(s, Matrix, matrix_id, "matrix")
    runs = list(s.scalars(select(Run).where(Run.matrix_id == mx.id).order_by(Run.created_at)))
    if not runs:
        raise InvalidInput("matrix has no runs")
    definitions: dict[str, MetricDefinition] = {}
    cell_runs: list[CellRun] = []
    for run in runs:
        manifest = RunManifest.model_validate(run.manifest)
        package = _package(s, manifest)
        for pin in manifest.plugins:
            if pin.role.startswith("evaluator"):
                for d in _definitions((pin.plugin_id, pin.version), package):
                    definitions.setdefault(d.metric_id, d)
        metrics = {m.metric_id: MetricResult.model_validate(m.result)
                   for m in s.scalars(select(MetricRow).where(MetricRow.run_id == run.id))}
        strategy_key, strategy_label = _strategy_label(manifest)
        budget_key = manifest.config.get("matrix_budget_key", "scenario-default")
        sources = sorted({str(p["proposal"]["source"]["kind"]) for p in s.scalars(
            select(RunEvent.payload).where(RunEvent.run_id == run.id, RunEvent.event_type == "ACTION_PROPOSED")
            .limit(200))})
        cell_runs.append(CellRun(Cell(manifest.scenario.scenario_id, strategy_key, manifest.seed, budget_key, ()),
                                 run.id, run.status, metrics, manifest.scenario.name, strategy_label, sources))
    out = build_report(list(definitions.values()), cell_runs)
    out["matrix"] = matrix_dict(mx, s)
    out["complete"] = all(r.status in ("SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED") for r in runs)
    return out


_DEF_CACHE: dict[tuple[str, str, str], list[MetricDefinition]] = {}


def _package(s: Session, manifest: RunManifest):
    from ..db import ModelVersion
    from .modeling import package_of

    row = s.scalar(select(ModelVersion).where(ModelVersion.digest == manifest.model.digest.value,
                                              ModelVersion.version == manifest.model.version))
    return package_of(row) if row is not None else None


def _definitions(ref: tuple[str, str], package) -> list[MetricDefinition]:
    """Metric definitions of an evaluator plugin, instantiated with the run's own pinned model."""
    key = (*ref, package.digest.value if package is not None else "")
    if key not in _DEF_CACHE:
        from formal_lab_runtime.engine import RuntimeServices

        try:
            evaluator = registry().create(PluginRef(plugin_id=ref[0], version=ref[1]), {}, RuntimeServices(package))
            _DEF_CACHE[key] = evaluator.metric_definitions()
        except Exception:
            _DEF_CACHE[key] = []
    return _DEF_CACHE[key]
