"""`fal` — command line interface (uses the same API and contracts as the Web UI and the SDK).

Offline commands (`fal model validate`, `fal replay …`) need no server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer
from formal_lab_contracts.bundle import read_bundle
from formal_lab_contracts.errors import FormalLabError

from .client import DEFAULT_URL, Client

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)
model_app = typer.Typer(no_args_is_help=True, help="model validation and versions")
run_app = typer.Typer(no_args_is_help=True, help="start, inspect and control experiment runs")
matrix_app = typer.Typer(no_args_is_help=True, help="scenario × strategy × seed × budget matrices")
replay_app = typer.Typer(no_args_is_help=True, help="offline replay of exported bundles (no server needed)")
ops_app = typer.Typer(no_args_is_help=True, help="environment operations of a run: abnormal ones, reviews")
rules_app = typer.Typer(no_args_is_help=True, help="rule sets (event–condition–handler), versioned")
release_app = typer.Typer(no_args_is_help=True, help="pre-release checks of a model version (and rules)")
regression_app = typer.Typer(no_args_is_help=True, help="regression cases from effect differences / counterexamples")
app.add_typer(model_app, name="model")
app.add_typer(run_app, name="run")
app.add_typer(matrix_app, name="matrix")
app.add_typer(replay_app, name="replay")
app.add_typer(ops_app, name="ops")
app.add_typer(rules_app, name="rules")
app.add_typer(release_app, name="release")
app.add_typer(regression_app, name="regression")

API = typer.Option(DEFAULT_URL, "--api", envvar="FAL_API_URL", help="platform API base URL")


def _client(api: str) -> Client:
    return Client(api)


def _out(obj: Any) -> None:
    typer.echo(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _fail(exc: FormalLabError) -> None:
    typer.secho(f"error [{exc.code.value}]: {exc.message}", fg="red", err=True)
    for fe in exc.field_errors:
        typer.secho(f"  {fe.path}: {fe.message}", fg="red", err=True)
    raise typer.Exit(2)


def _project(client: Client, project: str) -> str:
    return client.find_project(project)["id"]


def _resolve(items: list[dict[str, Any]], ref: str, kind: str) -> str:
    for it in items:
        if ref in (it["id"], it.get("name")):
            return it["id"]
    raise typer.BadParameter(f"{kind} {ref!r} not found; available: {[i.get('name') for i in items]}")


# ---------------------------------------------------------------------------- meta
@app.command()
def meta(api: str = API) -> None:
    """Platform version, contract digest, capability level."""
    try:
        _out(_client(api).meta())
    except FormalLabError as exc:
        _fail(exc)


@app.command()
def plugins(interface: str = typer.Option(None, help="filter by interface"), api: str = API) -> None:
    """Installed plugins with versions and capabilities."""
    try:
        for p in _client(api).plugins(interface):
            d = p["descriptor"]
            caps = ",".join(c["id"] for c in d["capabilities"])
            typer.echo(f"{d['interface']:15s} {d['plugin_id']}@{d['version']}  [{caps}]"
                       + ("" if p.get("available", True) else f"  (unavailable: {p.get('availability_note')})"))
    except FormalLabError as exc:
        _fail(exc)


# ---------------------------------------------------------------------------- models
@model_app.command("validate")
def model_validate(path: Path, api: str = typer.Option(None, "--api", help="validate via the API instead")) -> None:
    """Parse and type-check a model (offline when formal-lab-model-core is installed)."""
    ir = json.loads(path.read_text())
    try:
        if api is None:
            try:
                from formal_lab_model import check_model, ir_digest, parse_ir
            except ImportError:
                api = DEFAULT_URL
        if api is not None:
            res = _client(api).validate_model(ir)
        else:
            parsed = parse_ir(ir)
            checked = check_model(parsed)
            res = {"valid": not checked.issues, "issues": [i.model_dump() for i in checked.issues],
                   "digest": ir_digest(parsed).value, "ground_actions": len(checked.ground_actions)}
    except FormalLabError as exc:
        _fail(exc)
    _out(res)
    if not res["valid"]:
        raise typer.Exit(1)


@model_app.command("push")
def model_push(path: Path, project: str = typer.Option(...), package_id: str = typer.Option(...),
               note: str = typer.Option(None), api: str = API) -> None:
    """Create a model or add a new immutable version."""
    c = _client(api)
    ir = json.loads(path.read_text())
    try:
        pid = _project(c, project)
        existing = next((m for m in c.models(pid) if m["package_id"] == package_id), None)
        res = c.add_model_version(existing["id"], ir, note) if existing else c.create_model(pid, package_id, ir)
    except FormalLabError as exc:
        _fail(exc)
    _out(res if "version" not in res or isinstance(res.get("version"), int) else res["version"])


@model_app.command("check")
def model_check(version_id: str, kind: str = typer.Option("GOAL_REACHABILITY", help="query kind"),
                prop: str = typer.Option(None, "--property", help="goal / invariant property"),
                steps: int = typer.Option(16, help="bound (max steps / horizon)"),
                timeout_ms: int = typer.Option(20000),
                action: str = typer.Option(None, help="ACTION_PRECONDITION: action as JSON {action_type, params}"),
                objective: Path = typer.Option(None, help="OPTIMIZE_OBJECTIVE: ObjectiveSpec JSON file"),
                state: Path = typer.Option(None, help="start state JSON file (GIVEN_STATE)"),
                unknown: list[str] = typer.Option(None, help="unknown location (repeatable)"),
                export: Path = typer.Option(None, help="write the replayable query bundle here"),
                api: str = API) -> None:
    """Run a bounded check on a stored model version; print the shared explanation (P2-029)."""
    c = _client(api)
    query: dict[str, Any] = {"kind": kind, "bound": {"max_steps": steps, "timeout_ms": timeout_ms}}
    if prop:
        query["property_id"] = prop
    if action:
        query["action"] = json.loads(action)
    if objective:
        query["objective"] = json.loads(objective.read_text())
    if state:
        query["initial_state"] = "GIVEN_STATE"
    try:
        rec = c.check_record(version_id, query, json.loads(state.read_text()) if state else None, unknown or None)
        for line in rec.get("explanation", []):
            typer.echo(line)
        if export and rec.get("query_bundle_id"):
            bundle = c.query_bundle(rec["query_bundle_id"], export=True)
            export.write_text(json.dumps(bundle.model_dump(mode="json"), indent=2, ensure_ascii=False))
            typer.echo(f"query bundle → {export}")
    except FormalLabError as exc:
        _fail(exc)


query_app = typer.Typer(no_args_is_help=True, help="replayable query bundles")
app.add_typer(query_app, name="query")


@query_app.command("replay")
def query_replay(path: Path, offline: bool = typer.Option(False, "--offline",
                                                         help="replay locally with the installed verifier"),
                 api: str = API) -> None:
    """Re-ask a query bundle and compare the answer (offline needs formal-lab-runtime + verifier plugins)."""
    from formal_lab_contracts import QueryBundle

    bundle = QueryBundle.model_validate_json(path.read_text())
    try:
        if offline:
            if bundle.package is None:
                raise typer.BadParameter("the bundle does not embed its model package (export it with --export)")
            from formal_lab_runtime import default_registry
            from formal_lab_runtime.query import replay_query

            res = replay_query(default_registry(), bundle.package, bundle)
        else:
            res = _client(api).replay_query(bundle)
    except FormalLabError as exc:
        _fail(exc)
    _out(res)
    if not res.get("same"):
        raise typer.Exit(1)


@query_app.command("explain")
def query_explain(path: Path) -> None:
    """Print the explanation stored in a query bundle (offline)."""
    from formal_lab_contracts import QueryBundle

    for line in QueryBundle.model_validate_json(path.read_text()).explanation:
        typer.echo(line)


# ---------------------------------------------------------------------------- runs
@run_app.command("start")
def run_start(project: str = typer.Option(...), scenario: str = typer.Option(...),
              strategy: str = typer.Option(None), seed: int = typer.Option(None),
              max_steps: int = typer.Option(None), follow: bool = typer.Option(False, "--follow"),
              wait: bool = typer.Option(False, "--wait"), idempotency_key: str = typer.Option(None), api: str = API):
    """Start a run (scenario / strategy by id or name)."""
    c = _client(api)
    try:
        pid = _project(c, project)
        sid = _resolve(c.scenarios(pid), scenario, "scenario")
        stid = _resolve(c.strategies(pid), strategy, "strategy") if strategy else None
        run = c.start_run(pid, sid, stid, seed, {"max_steps": max_steps} if max_steps else None, idempotency_key)
        typer.echo(f"run {run['id']} {run['status']}")
        if follow:
            _follow(c, run["id"])
        if wait or follow:
            run = c.wait(run["id"])
            _summary(run)
            raise typer.Exit(0 if run["status"] == "SUCCEEDED" else 1)
    except FormalLabError as exc:
        _fail(exc)


def _summary(run: dict[str, Any]) -> None:
    typer.echo(f"{run['id']}: {run['status']} ({run.get('status_reason')}) steps={run['last_step']}")
    for k, v in sorted(run.get("metrics", {}).items()):
        typer.echo(f"  {k:20s} {v['value'] if v['value'] is not None else v['status']}")


def _follow(c: Client, run_id: str, after: int = 0) -> None:
    for ev in c.follow(run_id, after_seq=after):
        detail = ""
        if ev.event_type == "ACTION_PROPOSED":
            a = ev.payload["proposal"]["action"]
            detail = f"{a['action_type']}({', '.join(f'{k}={v}' for k, v in a['params'].items())})"
        elif ev.event_type == "ACTION_OUTCOME":
            o = ev.payload["outcome"]
            detail = f"{o['status']} {o['effect_comparison']['verdict'] if o.get('effect_comparison') else ''}"
        typer.echo(f"{ev.seq:5d} s{ev.logical_step if ev.logical_step is not None else '-':<3} {ev.event_type:18s} {detail}")


@run_app.command("show")
def run_show(run_id: str, manifest: bool = typer.Option(False), api: str = API) -> None:
    try:
        run = _client(api).run(run_id)
    except FormalLabError as exc:
        _fail(exc)
    _out(run if manifest else {k: v for k, v in run.items() if k not in ("manifest", "final_state")})


@run_app.command("events")
def run_events(run_id: str, follow: bool = typer.Option(False, "--follow"), after: int = 0, api: str = API) -> None:
    c = _client(api)
    try:
        if follow:
            _follow(c, run_id, after)
        else:
            for ev in c.events(run_id, after_seq=after):
                typer.echo(f"{ev.seq:5d} s{ev.logical_step if ev.logical_step is not None else '-':<3} {ev.event_type}")
    except FormalLabError as exc:
        _fail(exc)


@run_app.command("step")
def run_step(run_id: str, step: int, api: str = API) -> None:
    try:
        _out(_client(api).step(run_id, step))
    except FormalLabError as exc:
        _fail(exc)


@run_app.command("cancel")
def run_cancel(run_id: str, reason: str = typer.Option(None, help="explained termination: why the operator ends it"),
               operation: list[str] = typer.Option(None, help="operation ids the reason concerns"),
               api: str = API) -> None:
    """cancel a run at the next step boundary (with --reason: an explained termination)"""
    try:
        res = _client(api).cancel(run_id, reason, operation)
    except FormalLabError as exc:
        _fail(exc)
    typer.echo(f"{res['id']} {res['status']}" + (f" ({res['status_reason']})" if res.get("status_reason") else ""))


for _name, _method in (("pause", "pause"), ("resume", "resume"), ("rerun", "rerun")):
    def _make(method: str):
        def cmd(run_id: str, api: str = API) -> None:
            try:
                res = getattr(_client(api), method)(run_id)
            except FormalLabError as exc:
                _fail(exc)
            typer.echo(f"{res['id']} {res['status']}" + (f" (source {res['source_run_id']})"
                                                          if res.get("source_run_id") else ""))

        cmd.__doc__ = f"{method} a run"
        return cmd

    run_app.command(_name)(_make(_method))


# ---------------------------------------------------------------------------- operations
@ops_app.command("list")
def ops_list(run_id: str, abnormal: bool = typer.Option(False, "--abnormal", help="only operations whose outcome "
                                                                                   "was unknown, failed or reviewed"),
             state: str = typer.Option(None), needs_review: bool = typer.Option(None, "--needs-review/--reviewed"),
             api: str = API) -> None:
    """environment operations of a run with their coordination state"""
    try:
        rows = _client(api).operations(run_id, state=state, needs_review=needs_review, abnormal=abnormal)
    except FormalLabError as exc:
        _fail(exc)
    for o in rows:
        path = " → ".join(t["state"] for t in o["transitions"])
        review = f"  [{o['review']['status']}]" if o.get("review") else ""
        typer.echo(f"{o['operation_id']}  step {o['step']}  {o['state']}  {path}{review}")


@ops_app.command("show")
def ops_show(operation_id: str, api: str = API) -> None:
    """one operation: transitions with reasons, reconciliation, review"""
    try:
        _out(_client(api).operation(operation_id))
    except FormalLabError as exc:
        _fail(exc)


@ops_app.command("review")
def ops_review(operation_id: str,
               status: str = typer.Option(..., help="CONFIRMED_APPLIED | CONFIRMED_NOT_APPLIED | TERMINATED"),
               note: str = typer.Option(..., help="what was checked"), by: str = typer.Option("operator"),
               supersede: bool = typer.Option(False), api: str = API) -> None:
    """record a manual review of an operation (appended to the run's events)"""
    try:
        res = _client(api).review_operation(operation_id, status, note, by, supersede)
    except FormalLabError as exc:
        _fail(exc)
    typer.echo(f"{res['operation_id']} {res['state']} reviewed: {res['review']['status']} by {res['review']['by']}")


# ---------------------------------------------------------------------------- rules / releases / regression
@rules_app.command("push")
def rules_push(path: Path, project: str = typer.Option(...), model_version: str = typer.Option(...),
               ruleset_id: str = typer.Option(None, help="default: the file's ruleset_id"), api: str = API) -> None:
    """save a rule-set file (JSON: {ruleset_id, name, rules}) as a new version, type-checked with the model"""
    data = json.loads(path.read_text())
    c = _client(api)
    try:
        row = c.save_ruleset(_project(c, project), model_version, ruleset_id or data["ruleset_id"], data["rules"],
                             name=data.get("name"), note=data.get("note"))
    except FormalLabError as exc:
        _fail(exc)
    typer.echo(f"{row['ruleset_id']}@{row['version']}  digest {row['digest'][:12]}")


@rules_app.command("list")
def rules_list(project: str = typer.Option(...), api: str = API) -> None:
    c = _client(api)
    for r in c.rulesets(_project(c, project)):
        typer.echo(f"{r['ruleset_id']}@{r['version']}  {len(r['ruleset']['rules'])} rule(s)  model version "
                   f"{r['model_version_id']}  digest {r['digest'][:12]}")


@release_app.command("check")
def release_check(model_version: str, ruleset: str = typer.Option(None, help="id@version"),
                  regression: str = typer.Option("model", help="model | none | comma-separated case ids"),
                  horizon: int = 6,
                  require: list[str] = typer.Option([], help="required check (TYPE_CHECK, RULE_CHECK, "
                                                             "GOAL_REACHABILITY, INVARIANT_VIOLATION, OBJECTIVE_CHECK, "
                                                             "REGRESSION); repeatable"),
                  require_holds: list[str] = typer.Option([], help="property that must hold; repeatable"),
                  api: str = API) -> None:
    """compile, type-check, query and replay regression cases; prints the release record"""
    rs = None
    if ruleset:
        rid, _, ver = ruleset.partition("@")
        rs = (rid, int(ver))
    sel: str | list[str] = regression if regression in ("model", "none") else regression.split(",")
    try:
        rel = _client(api).release(model_version, ruleset=rs, regression=sel, horizon=horizon,
                                   required_checks=[r.upper() for r in require] or None,
                                   required_holds=require_holds or None)
    except FormalLabError as exc:
        _fail(exc)
    rec = rel["record"]
    typer.echo(f"{rel['release_id']}  {rel['status']}  model {rec['model']['package_id']}@{rec['model']['version']}")
    done = rec.get("process_completed")
    if done is not None:
        typer.echo(f"  process {'completed' if done else 'INCOMPLETE'} (required: "
                   f"{', '.join((rec.get('config') or {}).get('required_checks', []))})")
    for chk in rec["checks"]:
        holds = {True: "holds", False: "does not hold", None: ""}[chk.get("property_holds")]
        flag = "✓" if chk["passed"] else "✗"
        typer.echo(f"  {flag} {chk['kind']:<20} {chk['subject']:<28} {chk['verdict']:<24} {holds}"
                   + ("  [required]" if chk.get("required") else ""))
    for r in rec["regression"]:
        typer.echo(f"  {'✓' if r['status'] == 'PASS' else '✗'} regression {r['case_id']}  {r['status']}: {r['detail']}")
    for reason in rec["reasons"]:
        typer.secho(f"  reason: {reason}", fg="red")
    if rel["status"] != "RELEASED":
        raise typer.Exit(1)


@release_app.command("capabilities")
def release_capabilities(model_version: str, api: str = API) -> None:
    """what the platform can do with a model version (from declared capabilities)"""
    try:
        rep = _client(api).capabilities(model_version)
    except FormalLabError as exc:
        _fail(exc)
    typer.echo(f"{rep['model']['package_id']}@{rep['model']['version']}  profile {rep['semantic_profile']}  "
               f"driver {rep['driver']['plugin_id']}@{rep['driver']['version']}")
    for f in rep["features"]:
        provider = f"{f['provider']['plugin_id']}" if f.get("provider") else "—"
        typer.echo(f"  {f['status']:<11} {f['feature']:<28} {provider:<40} {f['reason']}")


@regression_app.command("list")
def regression_list(project: str = typer.Option(...), package_id: str = typer.Option(None), api: str = API) -> None:
    c = _client(api)
    for r in c.regression_cases(_project(c, project), package_id):
        case = r["case"]
        typer.echo(f"{r['case_id']}  {r['source']}  {case['model']['package_id']}@{case['model']['version']}  "
                   f"run {r['origin_run_id']}  {', '.join(case['compared_paths'][:3])}")


@regression_app.command("replay")
def regression_replay(case_id: str, model_version: str = typer.Option(...), api: str = API) -> None:
    """replay one case on a model version: PASS when it predicts what was observed"""
    try:
        res = _client(api).replay_case(case_id, model_version)
    except FormalLabError as exc:
        _fail(exc)
    typer.echo(f"{case_id} on {res['model']['package_id']}@{res['model']['version']}: {res['status']} — "
               f"{res['detail']}")
    if res["status"] != "PASS":
        raise typer.Exit(1)


@run_app.command("suggestions")
def run_suggestions(run_id: str, api: str = API) -> None:
    """model revision suggestions of a run (effect differences) and the regression case each produced"""
    try:
        rows = _client(api).revision_suggestions(run_id)
    except FormalLabError as exc:
        _fail(exc)
    for r in rows:
        fields = ", ".join(f"{d['path']}: {d['expected']}→{d['observed']}" for d in r["different_fields"][:3])
        typer.echo(f"step {r['step']} {r['actor_id']}  {r['action']['action_type']}  {fields}  "
                   f"constants read: {', '.join(r.get('constants_read', []))}  case {r['regression_case_id']}")


# ---------------------------------------------------------------------------- matrices
@matrix_app.command("run")
def matrix_run(project: str = typer.Option(...), scenario: list[str] = typer.Option(...),
               strategy: list[str] = typer.Option(...), seeds: str = typer.Option("1,2,3"),
               max_steps: list[int] = typer.Option(None, help="budget variants (max_steps); default: scenario budget"),
               name: str = typer.Option("cli-matrix"), wait: bool = typer.Option(True), report: Path | None = None,
               api: str = API) -> None:
    """Run every scenario × strategy × seed × budget combination and print the comparison report."""
    c = _client(api)
    try:
        pid = _project(c, project)
        scs = [_resolve(c.scenarios(pid), s, "scenario") for s in scenario]
        sts = [_resolve(c.strategies(pid), s, "strategy") for s in strategy]
        budgets = [{"max_steps": m} for m in max_steps] if max_steps else None
        res = c.create_matrix(pid, scenarios=scs, strategies=sts, seeds=[int(x) for x in seeds.split(",")],
                              budgets=budgets, name=name)
        mid = res["matrix"]["id"]
        typer.echo(f"matrix {mid}: {len(res['run_ids'])} runs")
        if wait:
            for rid in res["run_ids"]:
                c.wait(rid, timeout=1800)
            rep = c.matrix_report(mid)
            _print_report(rep)
            if report:
                report.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    except FormalLabError as exc:
        _fail(exc)


@matrix_app.command("report")
def matrix_report(matrix_id: str, output: Path | None = None,
                  fmt: str = typer.Option("json", "--format", help="json | csv | md (csv/md: v2 matrices)"),
                  api: str = API) -> None:
    try:
        rep = _client(api).matrix_report(matrix_id, fmt)
    except FormalLabError as exc:
        _fail(exc)
    if fmt != "json":
        if output:
            output.write_text(rep)
        else:
            typer.echo(rep)
        return
    if "splits" in rep:
        _print_report_v2(rep)
    else:
        _print_report(rep)
    if output:
        output.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))


def _print_report_v2(rep: dict[str, Any]) -> None:
    for line in rep.get("conclusions", []):  # computed by the platform from the v2 report
        typer.echo(line)


@matrix_app.command("create")
def matrix_create(spec: Path, project: str = typer.Option(...), wait: bool = typer.Option(False),
                  api: str = API) -> None:
    """v2 matrix from a JSON spec (participants / backends / rules / model_versions / seeds {dev, acceptance} /
    budgets / ablations / max_parallel); names or ids of scenarios and strategies are accepted."""
    c = _client(api)
    try:
        pid = _project(c, project)
        body = json.loads(spec.read_text())
        scs, sts = c.scenarios(pid), c.strategies(pid)
        body["scenarios"] = [_resolve(scs, x, "scenario") for x in body.get("scenarios", [])]
        body["participants"] = [{a: _resolve(sts, v, "strategy") for a, v in combo.items()}
                                for combo in body.get("participants", [])]
        if body.get("strategies"):
            body["strategies"] = [_resolve(sts, x, "strategy") for x in body["strategies"]]
        res = c.create_matrix_v2(pid, body)
        mid = res["matrix"]["id"]
        typer.echo(f"matrix {mid}: cells {res['cells']} (max_parallel {res['max_parallel']})")
        if wait:
            cells = c.wait_matrix(mid)
            done = sum(1 for x in cells if x["status"] == "DONE")
            typer.echo(f"matrix {mid}: {done}/{len(cells)} cells done")
            _print_report_v2(c.matrix_report(mid))
    except FormalLabError as exc:
        _fail(exc)


@matrix_app.command("cells")
def matrix_cells_cmd(matrix_id: str, api: str = API) -> None:
    """cells of a v2 matrix with their queue state"""
    for x in _client(api).matrix_cells(matrix_id):
        lab = x["labels"]
        typer.echo(f"{x['cell_id']}  {x['status']:<9} {x['split']:<10} seed {x['seed']:<3} {lab['scenario']} × "
                   f"{lab['participants']} [{lab['backend']}, {lab['rules']}, {lab['model']}, {lab['ablation']}]"
                   f"  run {x['run_id'] or '—'} {x['run_status'] or ''}")


for _name, _method, _doc in (("resume", "matrix_resume", "continue an interrupted matrix queue"),
                             ("rerun-failed", "matrix_rerun_failed", "queue the failed cells again"),
                             ("cancel", "matrix_cancel", "stop the queue and cancel running cells")):
    def _mk(method: str, doc: str):
        def cmd(matrix_id: str, api: str = API) -> None:
            try:
                _out(getattr(_client(api), method)(matrix_id))
            except FormalLabError as exc:
                _fail(exc)

        cmd.__doc__ = doc
        return cmd

    matrix_app.command(_name)(_mk(_method, _doc))


@matrix_app.command("merge")
def matrix_merge(matrix_id: str, spec: Path, project: str = typer.Option(...), api: str = API) -> None:
    """add cells from a JSON spec fragment (e.g. more seeds or strategies); completed identical cells are reused"""
    c = _client(api)
    try:
        pid = _project(c, project)
        body = json.loads(spec.read_text())
        sts = c.strategies(pid)
        if "participants" in body:
            body["participants"] = [{a: _resolve(sts, v, "strategy") for a, v in combo.items()}
                                    for combo in body["participants"]]
        _out(c.matrix_merge(matrix_id, body))
    except FormalLabError as exc:
        _fail(exc)


def _print_report(rep: dict[str, Any]) -> None:
    for row in rep["aggregates"]:
        typer.echo(f"\n{row['scenario_label']} × {row['strategy_label']} [{row['budget']}] runs={row['runs']} "
                   f"statuses={row['statuses']}")
        for mid, m in row["metrics"].items():
            r = m["result"]
            ci = f" CI[{r['ci']['low']:.2f}, {r['ci']['high']:.2f}]" if r.get("ci") else ""
            val = f"{r['value']:.3f}" if r["value"] is not None else f"MISSING ({r.get('missing_reason')})"
            typer.echo(f"  {mid:18s} {val} n={r.get('sample_size')} missing={r.get('missing_count')}{ci}")
    for cmp in rep["comparisons"]:
        if cmp["n_pairs"] and cmp["metric_id"] in ("delay_cost", "goal_reached", "steps_used", "makespan"):
            t = cmp["test"]
            test = f"p={t['p_value']:.3g}" if t.get("reported") else t.get("reason", "")
            typer.echo(f"{cmp['metric_id']:14s} {cmp['a']} vs {cmp['b']}: pairs={cmp['n_pairs']} "
                       f"mean diff={cmp['mean_diff_b_minus_a']} better={cmp['better']} {test}")


# ---------------------------------------------------------------------------- export / import / replay
@app.command("export")
def export(run_id: str, output: Path = typer.Option(None, "-o"), api: str = API) -> None:
    """Export a self-contained replay bundle."""
    try:
        data = _client(api).export_run(run_id)
    except FormalLabError as exc:
        _fail(exc)
    path = output or Path(f"{run_id}.replay.zip")
    path.write_bytes(data)
    typer.echo(f"wrote {path} ({len(data)} bytes)")


@app.command("import")
def import_(path: Path, project: str = typer.Option(...), api: str = API) -> None:
    """Import a replay bundle into a project."""
    c = _client(api)
    try:
        run = c.import_bundle(_project(c, project), path.read_bytes())
    except FormalLabError as exc:
        _fail(exc)
    typer.echo(f"imported {run['id']} ({run['status']}, {run['event_seq']} events)")


@replay_app.command("verify")
def replay_verify(path: Path) -> None:
    """Verify digests and consistency of a bundle (offline)."""
    try:
        b = read_bundle(path.read_bytes())
    except FormalLabError as exc:
        _fail(exc)
    causality = b.info.get("causality_problems", [])
    upgraded = f" upgraded-from={b.info['upgraded_from']}" if b.info.get("upgraded_from") else ""
    typer.echo(f"OK {b.info['format']} run={b.manifest.run_id} events={len(b.events)} artifacts={len(b.artifacts)} "
               f"operations={len(b.operations)} participants={len(b.manifest.participants)} "
               f"contract={b.info['contract_version']} digest={b.info.get('contract_digest')}{upgraded} "
               f"causality={'ok' if not causality else f'{len(causality)} problem(s)'}")


@replay_app.command("view")
def replay_view(path: Path, events: bool = typer.Option(False, "--events")) -> None:
    """Show the run summary and step-by-step trajectory from a bundle (offline)."""
    try:
        b = read_bundle(path.read_bytes())
    except FormalLabError as exc:
        _fail(exc)
    m = b.manifest
    typer.echo(f"run {m.run_id}  status {m.status.value} ({m.status_reason})"
               + (f"  termination={m.termination_reason.value}" if m.termination_reason else ""))
    typer.echo(f"scenario {m.scenario.name}  seed {m.seed}  model {m.model.package_id}@{m.model.version}"
               f"  turns={m.turns.mode.value}")
    for p in m.participants:
        typer.echo(f"participant {p.actor_id}: {p.strategy.plugin.plugin_id}@{p.strategy.plugin.version} "
                   f"{p.strategy.config or ''}")
    multi = len(m.participants) > 1
    for step in b.steps():
        d = b.step(step)
        a = d.get("proposal", {}).get("proposal", {}).get("action", {})
        o = d.get("outcome", {}).get("outcome", {})
        cmp = (o.get("effect_comparison") or {}).get("verdict", "")
        chk = (d.get("checks") or [{}])[0].get("result", {}).get("verdict", "")
        who = f" [{d.get('actor_id')} r{(d.get('turn_ref') or {}).get('round', '?')}]" if multi else ""
        typer.echo(f"  step {step:3d}{who}  {a.get('action_type', '?')}"
                   f"({', '.join(f'{k}={v}' for k, v in a.get('params', {}).items())})"
                   f"  check={chk} outcome={o.get('status')} effect={cmp}")
    typer.echo("metrics: " + ", ".join(f"{x.metric_id}={x.value if x.value is not None else x.status.value}"
                                       for x in b.metrics))
    if events:
        for row in b.timeline():
            typer.echo(f"{row['seq']:5d} {row['type']:24s} step={row['step']} actor={row['actor'] or '-'}")


@replay_app.command("step")
def replay_step(path: Path, step: int) -> None:
    """Full observation / candidates / proposal / check / outcome / comparison of one step (offline)."""
    _out(read_bundle(path.read_bytes()).step(step))


def _bundle(path: Path):
    try:
        return read_bundle(path.read_bytes())
    except FormalLabError as exc:
        _fail(exc)


@replay_app.command("turns")
def replay_turns(path: Path, actor: str = typer.Option(None), round_: int = typer.Option(None, "--round"),
                 step_from: int = typer.Option(None, "--from"), step_to: int = typer.Option(None, "--to")) -> None:
    """Navigate by turn: global step, round, actor, the actor's own step, action and outcome (offline)."""
    for row in _bundle(path).turns():
        if (actor and row.get("actor_id") != actor) or (round_ is not None and row.get("round") != round_):
            continue
        if (step_from is not None and row["step"] < step_from) or (step_to is not None and row["step"] > step_to):
            continue
        typer.echo(f"step {row['step']:3d}  round {row.get('round', '-')!s:>3}  {row.get('actor_id', '-'):<14} "
                   f"#{row.get('actor_step', '-')!s:<3} {row.get('action', ''):<40} {row.get('outcome', '')}")


@replay_app.command("plans")
def replay_plans(path: Path, actor: str = typer.Option(None), nodes: bool = typer.Option(False, "--nodes")) -> None:
    """Navigate task plans: every version with its trigger, parent, generator and progress (offline)."""
    for p in _bundle(path).plans(actor):
        plan = p["plan"]
        rev = plan.get("revision") or {}
        counts: dict[str, int] = {}
        for n in plan.get("nodes", []):
            counts[n["status"]] = counts.get(n["status"], 0) + 1
        typer.echo(f"{plan['actor_id']} v{plan['version']} (parent {plan.get('parent_version')}) at step "
                   f"{rev.get('at_step', plan.get('created_at_step'))}: {rev.get('trigger')} — "
                   f"{(rev.get('detail') or '')[:90]}  [{plan['generator']['kind']}] {counts}")
        if nodes:
            for n in plan.get("nodes", []):
                typer.echo(f"    {n['node_id']:<12} {n['status']:<12} after {', '.join(n['depends_on']) or '—'}")


@replay_app.command("operations")
def replay_operations(path: Path, abnormal: bool = typer.Option(False, "--abnormal")) -> None:
    """Navigate operation coordination: each operation's states with reasons, reconciliation and review (offline)."""
    for op in _bundle(path).operations:
        states = [t.state.value for t in op.transitions]
        if abnormal and "OUTCOME_UNKNOWN" not in states and op.review is None and op.state.value != "FAILED":
            continue
        what = op.action.action_type if op.action else f"batch {op.batch_id} ({len(op.batch_outcomes)} proposals)"
        typer.echo(f"{op.operation_id}  step {op.step}  {what}  {' → '.join(states)}"
                   + (f"  [review {op.review.status}]" if op.review else ""))
        for t in op.transitions:
            typer.echo(f"    {t.state.value:<16} {t.reason}")


def _print_batches(batches: list[dict[str, Any]]) -> None:
    for b in batches:
        env = f"env step {b['env_step']}" if b.get("env_step") is not None else "not sent"
        typer.echo(f"{b['batch_id']}  round {b['round']}  {b['status']}  {env}"
                   + (f"  [{b['semantics']}{', joint prediction' if b.get('joint_prediction') else ''}]"
                      if b.get("semantics") else ""))
        for m in b["members"]:
            a = m.get("action") or {}
            act = f"{a.get('action_type')}({', '.join(f'{k}={v}' for k, v in a.get('params', {}).items())})" if a else ""
            typer.echo(f"    {m['actor_id']:<14} {m['status']:<10} step {m.get('global_step') or '-'!s:>3}  {act:<36} "
                       f"{m.get('outcome') or ''} {m.get('comparison') or ''}"
                       + (f"  — {m.get('reason')}" if m.get("reason") else ""))


@replay_app.command("batches")
def replay_batches(path: Path) -> None:
    """Navigate JOINT_BATCH rounds: members, statuses, environment step, outcomes (offline)."""
    _print_batches(_bundle(path).batches())


@run_app.command("batches")
def run_batches(run_id: str, api: str = API) -> None:
    """JOINT_BATCH rounds of a run (online)."""
    try:
        _print_batches(_client(api).batches(run_id))
    except FormalLabError as exc:
        _fail(exc)


@replay_app.command("model")
def replay_model(path: Path) -> None:
    """Which model version, rules and release the run used, and the revision suggestions it produced (offline)."""
    b = _bundle(path)
    m = b.manifest
    typer.echo(f"model {m.model.package_id}@{m.model.version} digest {m.model.digest.value[:16]} "
               f"(bundled package digest {b.package.digest.value[:16]})")
    typer.echo(f"rules {m.rules.ruleset_id}@{m.rules.version}" if m.rules else "rules —")
    typer.echo(f"release {m.release.release_id}" if m.release else "release — (not pinned)")
    for e in b.events:
        if str(e.event_type) == "MODEL_REVISION_SUGGESTED":
            fields = ", ".join(f"{d['path']}: {d['expected']}→{d['observed']}" for d in e.payload["different_fields"][:3])
            typer.echo(f"  step {e.logical_step}: {e.payload['action']['action_type']} differs — {fields}; constants "
                       f"read: {', '.join(e.payload.get('constants_read', []))}")


@replay_app.command("reexecute")
def replay_reexecute(path: Path, allow_live: bool = typer.Option(False, "--allow-live",
                                                                  help="also re-execute against a live service")) -> None:
    """RE-EXECUTE the bundled run locally with the installed plugins (not a recorded replay): the pinned manifest and
    model run again and the new trajectory is compared with the recorded one. Needs the engine and plugins."""
    b = _bundle(path)
    from formal_lab_runtime import default_registry, run_local

    reg = default_registry()
    env = reg.resolve(b.manifest.scenario.environment.plugin).descriptor
    live = "env.persistent_session" in {c.id for c in env.capabilities}
    if live and not allow_live:
        typer.secho(f"{env.plugin_id} is a live service: re-executing would act on it again; pass --allow-live",
                    fg="red", err=True)
        raise typer.Exit(2)
    res = run_local(b.manifest, b.package, reg)

    def traj(events):
        return [(e.logical_step, json.dumps(e.payload["outcome"]["action"], sort_keys=True),
                 e.payload["outcome"]["status"]) for e in events if str(e.event_type) == "ACTION_OUTCOME"]

    old, new = traj(b.events), traj(res.events)
    first = next((i for i, (x, y) in enumerate(zip(old, new, strict=False)) if x != y), None)
    same = first is None and len(old) == len(new)
    typer.echo(f"re-executed {b.manifest.run_id}: status {res.status.value} (recorded {b.manifest.status.value}); "
               f"{len(new)} steps (recorded {len(old)}); trajectory "
               + ("identical" if same else f"diverges at step {old[first][0] if first is not None else len(old)}"))
    if not same:
        raise typer.Exit(1)


def main() -> None:
    try:
        app()
    except BrokenPipeError:
        sys.exit(0)


if __name__ == "__main__":
    main()
