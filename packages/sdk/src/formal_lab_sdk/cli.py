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
app.add_typer(model_app, name="model")
app.add_typer(run_app, name="run")
app.add_typer(matrix_app, name="matrix")
app.add_typer(replay_app, name="replay")

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


for _name, _method in (("cancel", "cancel"), ("pause", "pause"), ("resume", "resume"), ("rerun", "rerun")):
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
def matrix_report(matrix_id: str, output: Path | None = None, api: str = API) -> None:
    try:
        rep = _client(api).matrix_report(matrix_id)
    except FormalLabError as exc:
        _fail(exc)
    _print_report(rep)
    if output:
        output.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))


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
    typer.echo(f"OK {b.info['format']} run={b.manifest.run_id} events={len(b.events)} artifacts={len(b.artifacts)} "
               f"contract={b.info['contract_version']} digest={b.info.get('contract_digest')}")


@replay_app.command("view")
def replay_view(path: Path, events: bool = typer.Option(False, "--events")) -> None:
    """Show the run summary and step-by-step trajectory from a bundle (offline)."""
    try:
        b = read_bundle(path.read_bytes())
    except FormalLabError as exc:
        _fail(exc)
    m = b.manifest
    typer.echo(f"run {m.run_id}  status {m.status.value} ({m.status_reason})")
    typer.echo(f"scenario {m.scenario.name}  seed {m.seed}  model {m.model.package_id}@{m.model.version}")
    strat = m.participants[0].strategy
    typer.echo(f"strategy {strat.plugin.plugin_id}@{strat.plugin.version} {strat.config or ''}")
    for step in b.steps():
        d = b.step(step)
        a = d.get("proposal", {}).get("proposal", {}).get("action", {})
        o = d.get("outcome", {}).get("outcome", {})
        cmp = (o.get("effect_comparison") or {}).get("verdict", "")
        chk = d.get("check", {}).get("result", {}).get("verdict", "")
        typer.echo(f"  step {step:3d}  {a.get('action_type', '?')}({', '.join(f'{k}={v}' for k, v in a.get('params', {}).items())})"
                   f"  check={chk} outcome={o.get('status')} effect={cmp}")
    typer.echo("metrics: " + ", ".join(f"{x.metric_id}={x.value if x.value is not None else x.status.value}"
                                       for x in b.metrics))
    if events:
        for row in b.timeline():
            typer.echo(f"{row['seq']:5d} {row['type']:18s} step={row['step']}")


@replay_app.command("step")
def replay_step(path: Path, step: int) -> None:
    """Full observation / candidates / proposal / check / outcome / comparison of one step (offline)."""
    _out(read_bundle(path.read_bytes()).step(step))


def main() -> None:
    try:
        app()
    except BrokenPipeError:
        sys.exit(0)


if __name__ == "__main__":
    main()
