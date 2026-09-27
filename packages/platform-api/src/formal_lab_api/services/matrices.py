"""Experiment matrices (scenario × strategy × seed × budget) and their comparison reports."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import MetricDefinition, MetricResult, PluginRef, RunManifest, compat
from formal_lab_contracts.errors import FormalLabError, InvalidInput
from formal_lab_eval.matrix import Cell, CellRun, build_report, expand
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Matrix, MatrixCellRow, MetricRow, Project, Run, RunEvent, Scenario, StrategyConfig
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
    """Strategy key/label of a run; several participants → the combination (actor=strategy, in turn order)."""
    parts = []
    for part in manifest.participants:
        p = part.strategy
        stub = p.config.get("client") == "stub"
        entry = registry().resolve(p.plugin)
        parts.append((part.actor_id, p.plugin.plugin_id + (":stub" if stub else ""),
                      entry.descriptor.ui.label + (" (stub)" if stub else "")))
    if len(parts) == 1:
        return parts[0][1], parts[0][2]
    return "+".join(f"{a}={k}" for a, k, _ in parts), " + ".join(f"{a}: {lab}" for a, _, lab in parts)


def report(s: Session, matrix_id: str) -> dict[str, Any]:
    mx = get_or_404(s, Matrix, matrix_id, "matrix")
    runs = list(s.scalars(select(Run).where(Run.matrix_id == mx.id).order_by(Run.created_at)))
    if not runs:
        raise InvalidInput("matrix has no runs")
    definitions: dict[str, MetricDefinition] = {}
    cell_runs: list[CellRun] = []
    for run in runs:
        manifest = compat.upgrade_run_manifest(run.manifest)
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


# ====================================================================== matrix v2: cell queue (P2-080 … P2-085)
#
# spec (body): {"version": 2, "name", "scenarios": [id], "participants": [{"*": strategy_id} | {actor: id}],
#   "backends": [null | {"label", "environment": {plugin, config}}], "rules": [null | "off" | {ruleset_id, version}],
#   "model_versions": [null | model_version_id], "seeds": {"dev": [..], "acceptance": [..]} | [..],
#   "budgets": [{}], "ablations": [{} | {"label", "env": {...patch}, "strategy": {...patch}}], "max_parallel": 2}

V2_KEYS = {"participants", "backends", "rules", "model_versions", "ablations", "max_parallel"}
MAX_V2_CELLS = 600


def is_v2(body: dict[str, Any]) -> bool:
    return body.get("version") == 2 or bool(V2_KEYS & set(body))


def _label(value: Any, default: str = "scenario") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and value.get("label"):
        return str(value["label"])
    if isinstance(value, dict) and value.get("ruleset_id"):
        return f"{value['ruleset_id']}@{value['version']}"
    return "custom"


def expand_v2(s: Session, project_id: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Cells of a v2 spec, each with its full configuration, digest and cell_id (the same configuration → the same
    cell id in any matrix)."""
    import itertools

    from formal_lab_eval.experiments import cell_id_of, config_digest

    scenarios = list(spec.get("scenarios") or [])
    combos = list(spec.get("participants") or [{"*": sid} for sid in spec.get("strategies") or []])
    if not scenarios or not combos:
        raise InvalidInput("a matrix needs at least one scenario and one participant combination")
    seeds_spec = spec.get("seeds") or [0]
    splits = seeds_spec if isinstance(seeds_spec, dict) else {"acceptance": seeds_spec}
    overlap = set(splits.get("dev", [])) & set(splits.get("acceptance", []))
    if overlap:
        raise InvalidInput(f"seeds {sorted(overlap)} are in both the dev and the acceptance split")
    backends, rules = spec.get("backends") or [None], spec.get("rules") or [None]
    models, budgets = spec.get("model_versions") or [None], spec.get("budgets") or [{}]
    ablations = spec.get("ablations") or [{}]
    strategies = {st.id: st for st in s.scalars(select(StrategyConfig).where(StrategyConfig.project_id == project_id))}
    cells = []
    for sid, combo, backend, rule, mv, budget, abl in itertools.product(scenarios, combos, backends, rules, models,
                                                                         budgets, ablations):
        sc = get_or_404(s, Scenario, sid, "scenario")
        manifest = compat.upgrade_scenario(sc.manifest)
        actors = [p.actor_id for p in manifest.participants]
        chosen: dict[str, dict[str, Any]] = {}
        for actor in actors:
            st_id = combo.get(actor) or combo.get("*")
            if st_id is None:
                raise InvalidInput(f"participant combination {combo} names no strategy for {actor}")
            st = strategies.get(st_id) or get_or_404(s, StrategyConfig, st_id, "strategy")
            chosen[actor] = {"strategy_config_id": st.id, "plugin": {"plugin_id": st.plugin_id,
                                                                     "version": st.plugin_version},
                             "config": st.config, "label": st.name}
        env = backend["environment"] if backend else manifest.environment.model_dump(mode="json")
        model_ref = manifest.model.model_dump(mode="json")
        if mv:
            model_ref = package_of_version(s, mv).ref().model_dump(mode="json")
        for split, seeds in sorted(splits.items()):
            for seed in seeds:
                config = {"scenario_id": sid, "scenario_revision": sc.revision,
                          "participants": {a: {k: v for k, v in c.items() if k != "label"} for a, c in chosen.items()},
                          "environment": env, "rules": rule if rule not in (None,) else "scenario",
                          "model": model_ref, "seed": int(seed), "budget": budget,
                          "ablations": {k: v for k, v in abl.items() if k != "label"}}
                digest = config_digest(config)
                label = "+".join(f"{a}={c['label']}" for a, c in chosen.items()) if len(chosen) > 1 else \
                    next(iter(chosen.values()))["label"]
                cells.append({
                    "cell_id": cell_id_of(digest), "config_digest": digest, "split": split, "seed": int(seed),
                    "scenario_id": sid, "scenario_revision": sc.revision, "config": config,
                    "labels": {"scenario": manifest.name, "participants": label, "backend": _label(backend),
                               "rules": _label(rule), "model": model_ref["package_id"] + f"@{model_ref['version']}",
                               "ablation": _label(abl, "none") if abl else "none",
                               "budget": ",".join(f"{k}={v}" for k, v in sorted(budget.items())) or "scenario-default"},
                    "run_body": {"scenario_id": sid, "seed": int(seed), "budget": budget,
                                 "participant_strategies": {a: c["strategy_config_id"] for a, c in chosen.items()},
                                 "overrides": {"environment": backend["environment"] if backend else None,
                                               "rules": rule, "model_version_id": mv,
                                               "env_config_patch": abl.get("env"),
                                               "strategy_config_patch": abl.get("strategy")}}})
    unique = {c["cell_id"]: c for c in cells}
    if len(unique) > MAX_V2_CELLS:
        raise InvalidInput(f"matrix has {len(unique)} cells (limit {MAX_V2_CELLS})")
    return list(unique.values())


def package_of_version(s: Session, version_id: str):
    from ..db import ModelVersion
    from .modeling import package_of

    return package_of(get_or_404(s, ModelVersion, version_id, "model version"))


def _done_elsewhere(s: Session, project_id: str, digest: str) -> MatrixCellRow | None:
    return s.scalar(select(MatrixCellRow).join(Matrix, Matrix.id == MatrixCellRow.matrix_id)
                    .where(Matrix.project_id == project_id, MatrixCellRow.config_digest == digest,
                           MatrixCellRow.status == "DONE").limit(1))


def add_cells(s: Session, mx: Matrix, cells: list[dict[str, Any]]) -> dict[str, int]:
    """Queue new cells (incremental merge, P2-081): a cell already in this matrix is skipped; one completed with the
    same full configuration elsewhere in the project is linked to that run instead of being run again."""
    have = {c.cell_id for c in s.scalars(select(MatrixCellRow).where(MatrixCellRow.matrix_id == mx.id))}
    counts = {"queued": 0, "reused": 0, "skipped": 0}
    for c in cells:
        if c["cell_id"] in have:
            counts["skipped"] += 1
            continue
        done = _done_elsewhere(s, mx.project_id, c["config_digest"])
        s.add(MatrixCellRow(matrix_id=mx.id, cell_id=c["cell_id"], config_digest=c["config_digest"], spec=c,
                            status="DONE" if done else "QUEUED", run_id=done.run_id if done else None,
                            attempts=0, error=None if not done else f"reused from matrix {done.matrix_id}"))
        counts["reused" if done else "queued"] += 1
    s.flush()
    return counts


def create_matrix_v2(s: Session, project_id: str, body: dict[str, Any]) -> tuple[Matrix, dict[str, int]]:
    get_or_404(s, Project, project_id, "project")
    spec = {k: body.get(k) for k in ("scenarios", "participants", "strategies", "backends", "rules", "model_versions",
                                     "seeds", "budgets", "ablations") if body.get(k) is not None}
    spec.update({"version": 2, "max_parallel": int(body.get("max_parallel") or 2), "source": "platform"})
    cells = expand_v2(s, project_id, spec)
    mx = Matrix(id=new_id("mtx"), project_id=project_id, name=body.get("name") or "matrix", spec=spec)
    s.add(mx)
    s.flush()
    return mx, add_cells(s, mx, cells)


def merge_cells(s: Session, matrix_id: str, body: dict[str, Any]) -> dict[str, int]:
    mx = get_or_404(s, Matrix, matrix_id, "matrix")
    spec = {**mx.spec, **{k: v for k, v in body.items() if k in ("scenarios", "participants", "strategies",
                                                                  "backends", "rules", "model_versions", "seeds",
                                                                  "budgets", "ablations")}}
    counts = add_cells(s, mx, expand_v2(s, mx.project_id, spec))
    mx.spec = {**mx.spec, "merged": [*mx.spec.get("merged", []), {k: v for k, v in body.items()}]}
    return counts


def cell_rows(s: Session, matrix_id: str) -> list[Any]:
    return list(s.scalars(select(MatrixCellRow).where(MatrixCellRow.matrix_id == matrix_id)
                          .order_by(MatrixCellRow.created_at, MatrixCellRow.cell_id)))


def cells_dict(s: Session, matrix_id: str) -> list[dict[str, Any]]:
    runs = {r.id: r for r in s.scalars(select(Run).where(Run.id.in_(
        [c.run_id for c in cell_rows(s, matrix_id) if c.run_id])))}
    return [{"cell_id": c.cell_id, "status": c.status, "run_id": c.run_id, "attempts": c.attempts, "error": c.error,
             "split": c.spec["split"], "seed": c.spec["seed"], "labels": c.spec["labels"],
             "config_digest": c.config_digest,
             "run_status": runs[c.run_id].status if c.run_id in runs else None} for c in cell_rows(s, matrix_id)]


def settle(s: Session, matrix_id: str) -> dict[str, int]:
    """Mark RUNNING cells whose run finished: DONE (the run ended, whatever its outcome) or FAILED (the run failed
    or was cancelled — eligible for a rerun). Returns the queue counts."""
    counts = {"queued": 0, "running": 0, "done": 0, "failed": 0}
    for c in cell_rows(s, matrix_id):
        if c.status == "RUNNING" and c.run_id:
            run = s.get(Run, c.run_id)
            if run is not None and run.status in ("SUCCEEDED", "BUDGET_EXHAUSTED"):
                c.status = "DONE"
            elif run is not None and run.status in ("FAILED", "CANCELLED"):
                c.status, c.error = "FAILED", f"run {run.status}: {run.status_reason}"
        counts[c.status.lower()] = counts.get(c.status.lower(), 0) + 1
    return counts


def claim(s: Session, matrix_id: str, slots: int) -> list[str]:
    """Create runs for up to `slots` queued cells (in order) and mark them RUNNING; the caller starts the runs."""
    mx = get_or_404(s, Matrix, matrix_id, "matrix")
    out = []
    for c in cell_rows(s, matrix_id):
        if len(out) >= slots:
            break
        if c.status != "QUEUED":
            continue
        c.attempts += 1
        body = {**c.spec["run_body"], "config": {"matrix_cell": c.cell_id, "matrix_split": c.spec["split"],
                                                 "matrix_labels": c.spec["labels"]}}  # travel with the bundle
        try:
            run, _ = create_run(s, mx.project_id, body, matrix_id=mx.id,
                                client_request_id=f"{mx.id}:{c.cell_id}:{c.attempts}")
        except FormalLabError as exc:
            c.status, c.error = "FAILED", f"could not create the run: {exc.message}"
            continue
        from .runs import mark_queued

        mark_queued(s, run.id)
        c.status, c.run_id, c.error = "RUNNING", run.id, None
        out.append(run.id)
    return out


def rerun_failed(s: Session, matrix_id: str) -> int:
    n = 0
    for c in cell_rows(s, matrix_id):
        if c.status == "FAILED":
            c.status, n = "QUEUED", n + 1
    return n


def cancel_cells(s: Session, matrix_id: str) -> list[str]:
    """Stop the queue: queued cells are dropped (CANCELLED), running runs are asked to cancel."""
    from .runs import request_cancel

    to_cancel = []
    for c in cell_rows(s, matrix_id):
        if c.status == "QUEUED":
            c.status = "CANCELLED"
        elif c.status == "RUNNING" and c.run_id:
            run, needs = request_cancel(s, c.run_id, "matrix cancelled")
            if needs:
                to_cancel.append(run.id)
    return to_cancel


def report_v2(s: Session, matrix_id: str) -> dict[str, Any]:
    from formal_lab_eval.experiments import CellKey, CellResult, build_report, conclusions

    mx = get_or_404(s, Matrix, matrix_id, "matrix")
    definitions: dict[str, MetricDefinition] = {}
    sources: dict[str, str] = {}
    results: list[CellResult] = []
    for c in cell_rows(s, matrix_id):
        spec = c.spec
        lab = spec["labels"]
        key = CellKey(scenario=spec["scenario_id"], participants=lab["participants"], backend=lab["backend"],
                      rules=lab["rules"], model=lab["model"], ablation=lab["ablation"], budget=lab["budget"],
                      seed=spec["seed"], split=spec["split"])
        run = s.get(Run, c.run_id) if c.run_id else None
        metrics: dict[str, MetricResult] = {}
        if run is not None:
            manifest = compat.upgrade_run_manifest(run.manifest)
            package = _package(s, manifest)
            for pin in manifest.plugins:
                if pin.role.startswith("evaluator"):
                    for d in _definitions((pin.plugin_id, pin.version), package):
                        definitions.setdefault(d.metric_id, d)
                        sources.setdefault(d.metric_id, f"evaluator {pin.plugin_id}")
            metrics = {m.metric_id: MetricResult.model_validate(m.result)
                       for m in s.scalars(select(MetricRow).where(MetricRow.run_id == run.id))}
            metrics.update(_probe_metrics(s, run.id, definitions, sources))
        status = run.status if run is not None else ("NOT_RUN" if c.status in ("QUEUED", "CANCELLED", "FAILED")
                                                     else c.status)
        results.append(CellResult(cell_id=c.cell_id, key=key, run_id=c.run_id, status=status,
                                  termination_reason=run.termination_reason if run is not None else None,
                                  metrics=metrics, labels=lab))
    out = build_report(list(definitions.values()), sources, results)
    out["conclusions"] = conclusions(out, list(definitions.values()))
    out["matrix"] = matrix_dict(mx, s)
    out["cells"] = cells_dict(s, matrix_id)
    out["complete"] = all(c["status"] in ("DONE", "FAILED", "CANCELLED") for c in out["cells"])
    return out


def _probe_metrics(s: Session, run_id: str, definitions: dict[str, MetricDefinition],
                   sources: dict[str, str]) -> dict[str, MetricResult]:
    """Independent probe observations of a run as metrics `probe.<metric>` (last OK sample), source kept."""
    last: dict[str, Any] = {}
    for payload in s.scalars(select(RunEvent.payload).where(RunEvent.run_id == run_id,
                                                            RunEvent.event_type == "PROBE_SAMPLED")
                             .order_by(RunEvent.seq)):
        for p in payload.get("results", []):
            if p.get("status") == "OK":
                last[p["metric"]] = p
    out = {}
    for metric, p in last.items():
        mid = f"probe.{metric}"
        definitions.setdefault(mid, MetricDefinition(metric_id=mid, label=f"探针：{metric}", unit=p.get("unit") or "",
                                                     direction="NONE", aggregation="MEAN", value_type="float",
                                                     description=f"last OK sample of probe {p['probe']['plugin_id']}"))
        sources.setdefault(mid, f"probe {p['probe']['plugin_id']} ({p['source']})")
        out[mid] = MetricResult(metric_id=mid, metric_version="1", subject=run_id, value=float(p["value"]),
                                status="OK", unit=p.get("unit"))
    return out
