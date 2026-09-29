"""FastAPI application: REST + SSE over the shared services and contracts."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Body, FastAPI, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from formal_lab_contracts import CONTRACT_VERSION, TERMINAL_RUN_STATUSES, RunStatus
from formal_lab_contracts.errors import (
    HTTP_STATUS,
    ErrorCode,
    ErrorInfo,
    FieldError,
    FormalLabError,
    InvalidInput,
    NotFound,
)
from formal_lab_runtime.manifest import PLATFORM_VERSION
from sqlalchemy import select, text

from .db import (
    CheckRow,
    Matrix,
    Model,
    ModelVersion,
    Project,
    Run,
    RunEvent,
    Scenario,
    StrategyConfig,
    session_scope,
)
from .orchestration import TemporalOrchestrator
from .services import catalog, governance, modeling, operations, probabilistic, runs, scenarios
from .services.common import artifact_store, get_or_404
from .services.events import list_events, to_trace_event
from .settings import get_settings

log = logging.getLogger("formal_lab.api")
API = "/api/v1"
BATCH_EVENT_TYPES = ("BATCH_OPENED", "BATCH_SUBMITTED", "BATCH_CANCELLED", "ACTION_PROPOSED", "ACTION_OUTCOME",
                     "EFFECT_COMPARED")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app.state.orchestrator = TemporalOrchestrator(settings)
    try:
        await run_in_threadpool(_sync_catalog)
    except Exception:
        log.exception("plugin catalog sync failed (database unavailable?)")
    yield


def _sync_catalog() -> None:
    with session_scope() as s:
        catalog.sync_catalog(s)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="formal-agent-lab platform API", version=PLATFORM_VERSION, lifespan=lifespan,
                  description=f"Contracts: {CONTRACT_VERSION}. Deployment profile: {settings.deployment_profile}.")
    app.add_middleware(CORSMiddleware, allow_origins=[o for o in settings.cors_origins.split(",") if o],
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])

    @app.exception_handler(FormalLabError)
    async def _fl_error(_: Request, exc: FormalLabError) -> JSONResponse:
        info = exc.to_info()
        return JSONResponse(status_code=HTTP_STATUS[info.code], content={"error": info.model_dump(mode="json")})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        info = ErrorInfo(code=ErrorCode.INVALID_INPUT, message="request validation failed", retryable=False,
                         field_errors=[FieldError(path="/" + "/".join(map(str, e["loc"])), message=e["msg"])
                                       for e in exc.errors()])
        return JSONResponse(status_code=422, content={"error": info.model_dump(mode="json")})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        info = ErrorInfo(code=ErrorCode.NON_RETRYABLE_FAILURE, message=f"{type(exc).__name__}: {exc}", retryable=False)
        return JSONResponse(status_code=500, content={"error": info.model_dump(mode="json")})

    _routes(app)
    return app


def db(fn, *args: Any, **kwargs: Any):
    """Run a sync service call inside a transaction in the thread pool."""

    def call():
        with session_scope() as s:
            return jsonable_encoder(fn(s, *args, **kwargs))

    return run_in_threadpool(call)


def _routes(app: FastAPI) -> None:
    orch = lambda: app.state.orchestrator  # noqa: E731

    # ------------------------------------------------------------------ meta / health
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API}/health/ready")
    async def ready() -> JSONResponse:
        def check_db():
            with session_scope() as s:
                s.execute(text("select 1"))
            return {"ok": True}

        try:
            database = await run_in_threadpool(check_db)
        except Exception as exc:
            database = {"ok": False, "error": str(exc)}
        temporal = await orch().health()
        try:
            store = {"ok": True, **artifact_store().describe()}
        except Exception as exc:
            store = {"ok": False, "error": str(exc)}
        ok = database["ok"] and temporal["ok"] and store["ok"]
        return JSONResponse(status_code=200 if ok else 503,
                            content=jsonable_encoder({"ready": ok, "database": database, "temporal": temporal,
                                                      "artifact_store": store}))

    @app.get(f"{API}/meta")
    async def meta() -> dict[str, Any]:
        from formal_lab_contracts.schema_export import build_schemas, contract_digest
        from formal_lab_model.capability_matrix import MATRIX
        from formal_lab_runtime.manifest import PLATFORM_VERSION, source_revision
        from formal_lab_runtime.settings import get_setting, llm_configured

        settings = get_settings()
        return {
            "platform_version": PLATFORM_VERSION, "source_revision": source_revision(),
            "contract_version": CONTRACT_VERSION, "contract_digest": contract_digest(build_schemas())["digest"],
            "readable_contract_versions": ["formal-lab-contracts/v1", CONTRACT_VERSION],
            "deployment_profile": settings.deployment_profile,
            "capability_level": "single-user local development: loopback-bound services, no authentication, "
                                "no multi-tenant isolation",
            "llm": {"configured": llm_configured(), "model": get_setting("FAL_LLM_MODEL") if llm_configured() else None},
            "capability_matrix": [r.model_dump() for r in MATRIX],
            "plugin_load_errors": catalog.load_errors(),
        }

    @app.get(f"{API}/plugins")
    async def plugins(interface: str | None = None) -> list[dict[str, Any]]:
        return jsonable_encoder(catalog.catalog(interface))

    # ------------------------------------------------------------------ projects
    @app.get(f"{API}/projects")
    async def list_projects():
        return await db(lambda s: [modeling.project_dict(p, s) for p in
                                   s.scalars(select(Project).order_by(Project.created_at.desc()))])

    @app.post(f"{API}/projects", status_code=201)
    async def create_project(body: dict[str, Any] = Body(...)):
        return await db(lambda s: modeling.project_dict(
            modeling.create_project(s, body.get("name", ""), body.get("description"), body.get("group")), s))

    @app.get(f"{API}/projects/{{project_id}}")
    async def get_project(project_id: str):
        return await db(lambda s: modeling.project_dict(get_or_404(s, Project, project_id, "project"), s))

    @app.patch(f"{API}/projects/{{project_id}}")
    async def patch_project(project_id: str, body: dict[str, Any] = Body(...)):
        return await db(lambda s: modeling.project_dict(modeling.update_project(s, project_id, **body), s))

    @app.delete(f"{API}/projects/{{project_id}}", status_code=204)
    async def delete_project(project_id: str):
        def go(s):
            s.delete(get_or_404(s, Project, project_id, "project"))

        await db(go)
        return Response(status_code=204)

    # ------------------------------------------------------------------ models
    @app.post(f"{API}/models/validate")
    async def validate_model(body: dict[str, Any] = Body(...)):
        return await run_in_threadpool(modeling.validate_ir, body.get("ir", body))

    @app.get(f"{API}/projects/{{project_id}}/models")
    async def list_models(project_id: str):
        return await db(lambda s: [modeling.model_dict(m) for m in
                                   s.scalars(select(Model).where(Model.project_id == project_id)
                                             .order_by(Model.created_at))])

    @app.post(f"{API}/projects/{{project_id}}/models", status_code=201)
    async def create_model(project_id: str, body: dict[str, Any] = Body(...)):
        def go(s):
            m, v = modeling.create_model(s, project_id, package_id=body["package_id"], name=body.get("name"),
                                         ir=body.get("ir"), payload=body.get("payload"),
                                         description=body.get("description"))
            return {**modeling.model_dict(m), "version": modeling.version_dict(v)}

        return await db(go)

    @app.get(f"{API}/models/{{model_id}}")
    async def get_model(model_id: str):
        def go(s):
            m = get_or_404(s, Model, model_id, "model")
            return {**modeling.model_dict(m),
                    "versions": [modeling.version_dict(v, full=False) for v in modeling.list_versions(s, model_id)]}

        return await db(go)

    @app.post(f"{API}/models/{{model_id}}/versions", status_code=201)
    async def add_version(model_id: str, body: dict[str, Any] = Body(...)):
        return await db(lambda s: modeling.version_dict(modeling.add_version(
            s, model_id, ir=body.get("ir"), payload=body.get("payload"), note=body.get("note"),
            parent_version=body.get("parent_version"))))

    @app.get(f"{API}/models/{{model_id}}/versions/{{version}}")
    async def get_version(model_id: str, version: int):
        return await db(lambda s: modeling.version_details(modeling.get_version(s, model_id, version)))

    @app.get(f"{API}/models/{{model_id}}/diff")
    async def diff(model_id: str, from_version: int = Query(alias="from"), to_version: int = Query(alias="to")):
        return await db(lambda s: modeling.diff_versions(s, model_id, from_version, to_version))

    @app.post(f"{API}/model-versions/{{version_id}}/checks", status_code=201)
    async def run_check(version_id: str, body: dict[str, Any] = Body(...)):
        return await db(lambda s: modeling.check_dict(modeling.run_check(
            s, version_id, body["query"], body.get("state"), body.get("unknown_paths")), s))

    @app.get(f"{API}/model-versions/{{version_id}}/checks")
    async def list_checks(version_id: str):  # deterministic (Z3) checks only; probabilistic ones have their own list
        return await db(lambda s: [modeling.check_dict(c, s) for c in s.scalars(
            select(CheckRow).where(CheckRow.model_version_id == version_id,
                                   CheckRow.verdict != probabilistic.VERDICT).order_by(CheckRow.created_at.desc()))])

    @app.get(f"{API}/model-versions/{{version_id}}/capabilities")
    async def model_capabilities(version_id: str):  # G3: feature support from declared capabilities
        return await db(lambda s: governance.capability_report(s, version_id))

    # ---- optional PRISM-games extension: numerical results, kept apart from the deterministic checks
    @app.get(f"{API}/extensions/prism-games")
    async def prism_games():
        return await run_in_threadpool(probabilistic.availability)

    @app.post(f"{API}/model-versions/{{version_id}}/probabilistic-checks", status_code=201)
    async def run_probabilistic(version_id: str, body: dict[str, Any] = Body(default={})):
        return await db(lambda s: probabilistic.run(s, version_id, body))

    @app.get(f"{API}/model-versions/{{version_id}}/probabilistic-checks")
    async def list_probabilistic(version_id: str):
        return await db(lambda s: probabilistic.listing(s, version_id))

    @app.get(f"{API}/query-bundles/{{bundle_id}}")
    async def get_query_bundle(bundle_id: str):
        return await db(lambda s: modeling.query_bundle(s, bundle_id))

    @app.get(f"{API}/query-bundles/{{bundle_id}}/export")
    async def export_query_bundle(bundle_id: str):
        data = await db(lambda s: modeling.query_bundle(s, bundle_id, embed_package=True))
        return Response(content=json.dumps(data, indent=2, ensure_ascii=False).encode(), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{bundle_id}.query.json"'})

    @app.post(f"{API}/query-bundles/replay")
    async def replay_query_bundle(body: dict[str, Any] = Body(...)):
        """Re-ask a (stored or uploaded) query bundle and compare the answer (P2-029)."""
        return await db(lambda s: modeling.replay_bundle(s, body))

    # ------------------------------------------------------------------ scenarios / strategies
    # ---- rule sets, releases, regression cases, revision suggestions (P2-070 … P2-077)
    @app.get(f"{API}/projects/{{project_id}}/rulesets")
    async def rulesets_list(project_id: str, ruleset_id: str | None = None):
        return jsonable_encoder(await db(lambda s: governance.list_rulesets(s, project_id, ruleset_id)))

    @app.post(f"{API}/projects/{{project_id}}/rulesets", status_code=201)
    async def rulesets_save(project_id: str, body: dict[str, Any] = Body(...)):
        return jsonable_encoder(await db(lambda s: governance.save_ruleset(s, project_id, body)))

    @app.post(f"{API}/model-versions/{{version_id}}/releases", status_code=201)
    async def release_create(version_id: str, body: dict[str, Any] | None = Body(default=None)):
        return jsonable_encoder(await db(lambda s: governance.create_release(s, version_id, body or {})))

    @app.get(f"{API}/projects/{{project_id}}/releases")
    async def releases_list(project_id: str):
        return jsonable_encoder(await db(lambda s: governance.list_releases(s, project_id)))

    @app.get(f"{API}/releases/{{release_id}}")
    async def release_get(release_id: str):
        return jsonable_encoder(await db(lambda s: governance.get_release(s, release_id)))

    @app.get(f"{API}/projects/{{project_id}}/regression-cases")
    async def regression_list(project_id: str, package_id: str | None = None):
        return jsonable_encoder(await db(lambda s: governance.list_cases(s, project_id, package_id)))

    @app.post(f"{API}/regression-cases/{{case_id}}/replay")
    async def regression_replay(case_id: str, body: dict[str, Any] = Body(...)):
        return jsonable_encoder(await db(lambda s: governance.replay_case(s, case_id, body["model_version_id"])))

    @app.get(f"{API}/runs/{{run_id}}/revision-suggestions")
    async def run_suggestions(run_id: str):
        def go(s):
            get_or_404(s, Run, run_id, "run")
            return governance.revision_suggestions(s, run_id)

        return jsonable_encoder(await db(go))

    @app.get(f"{API}/projects/{{project_id}}/scenarios")
    async def list_scenarios(project_id: str):
        return await db(lambda s: [scenarios.scenario_dict(x, s) for x in scenarios.list_scenarios(s, project_id)])

    @app.post(f"{API}/projects/{{project_id}}/scenarios", status_code=201)
    async def create_scenario(project_id: str, body: dict[str, Any] = Body(...)):
        return await db(lambda s: scenarios.scenario_dict(scenarios.create_scenario(s, project_id, body), s))

    @app.get(f"{API}/scenarios/{{scenario_id}}")
    async def get_scenario(scenario_id: str):
        return await db(lambda s: scenarios.scenario_dict(get_or_404(s, Scenario, scenario_id, "scenario"), s))

    @app.put(f"{API}/scenarios/{{scenario_id}}")
    async def update_scenario(scenario_id: str, body: dict[str, Any] = Body(...)):
        return await db(lambda s: scenarios.scenario_dict(scenarios.update_scenario(s, scenario_id, body), s))

    @app.post(f"{API}/scenarios/{{scenario_id}}/copy", status_code=201)
    async def copy_scenario(scenario_id: str, body: dict[str, Any] = Body(default={})):
        return await db(lambda s: scenarios.scenario_dict(scenarios.copy_scenario(s, scenario_id, body.get("name")), s))

    @app.delete(f"{API}/scenarios/{{scenario_id}}", status_code=204)
    async def delete_scenario(scenario_id: str):
        await db(lambda s: s.delete(get_or_404(s, Scenario, scenario_id, "scenario")))
        return Response(status_code=204)

    @app.get(f"{API}/projects/{{project_id}}/strategies")
    async def list_strategies(project_id: str):
        return await db(lambda s: [scenarios.strategy_dict(x) for x in scenarios.list_strategies(s, project_id)])

    @app.post(f"{API}/projects/{{project_id}}/strategies", status_code=201)
    async def create_strategy(project_id: str, body: dict[str, Any] = Body(...)):
        return await db(lambda s: scenarios.strategy_dict(scenarios.upsert_strategy(s, project_id, body)))

    @app.put(f"{API}/strategies/{{strategy_id}}")
    async def update_strategy(strategy_id: str, body: dict[str, Any] = Body(...)):
        def go(s):
            row = get_or_404(s, StrategyConfig, strategy_id, "strategy")
            return scenarios.strategy_dict(scenarios.upsert_strategy(s, row.project_id, body, strategy_id))

        return await db(go)

    @app.delete(f"{API}/strategies/{{strategy_id}}", status_code=204)
    async def delete_strategy(strategy_id: str):
        await db(lambda s: s.delete(get_or_404(s, StrategyConfig, strategy_id, "strategy")))
        return Response(status_code=204)

    @app.get(f"{API}/strategies/{{strategy_id}}/compatibility")
    async def strategy_compat(strategy_id: str, scenario_id: str):
        return await db(lambda s: scenarios.compatibility(s, strategy_id, scenario_id))

    # ------------------------------------------------------------------ runs
    async def _start(run: dict[str, Any]) -> dict[str, Any]:
        if run["status"] != RunStatus.CREATED.value:
            return run
        # QUEUED is committed before the workflow exists, so RUN_QUEUED always precedes the worker's RUN_STARTED
        await db(lambda s: runs.mark_queued(s, run["id"]).id)
        try:
            await orch().start(run["id"], f"run-{run['id']}")
        except Exception as exc:
            reason = f"workflow could not be started: {exc}"
            await db(lambda s: runs.mark_start_failed(s, run["id"], reason).id)
            raise
        return await db(lambda s: runs.run_dict(get_or_404(s, Run, run["id"], "run"), s))

    @app.post(f"{API}/projects/{{project_id}}/runs", status_code=201)
    async def create_run(project_id: str, response: Response, body: dict[str, Any] = Body(...),
                         idempotency_key: str | None = Header(default=None)):
        def go(s):
            run, created = runs.create_run(s, project_id, body, client_request_id=idempotency_key)
            return {"run": runs.run_dict(run, s), "created": created}

        res = await db(go)
        if not res["created"]:
            response.status_code = 200
        return await _start(res["run"])

    @app.post(f"{API}/runs/{{run_id}}/start")
    async def start_run(run_id: str):
        return await _start(await db(lambda s: runs.run_dict(get_or_404(s, Run, run_id, "run"), s)))

    @app.get(f"{API}/projects/{{project_id}}/runs")
    async def list_runs(project_id: str, status: str | None = None, scenario_id: str | None = None,
                        matrix_id: str | None = None):
        return await db(lambda s: [runs.run_dict(r, s) for r in runs.list_runs(
            s, project_id, status=status, scenario_id=scenario_id, matrix_id=matrix_id)])

    @app.get(f"{API}/runs/{{run_id}}")
    async def get_run(run_id: str):
        return await db(lambda s: runs.run_dict(get_or_404(s, Run, run_id, "run"), s, full=True))

    @app.get(f"{API}/runs/{{run_id}}/events")
    async def get_events(run_id: str, after_seq: int = 0, limit: int = Query(default=500, le=5000),
                         event_type: list[str] | None = Query(default=None), step: int | None = None):
        def go(s):
            get_or_404(s, Run, run_id, "run")
            return [to_trace_event(e).model_dump(mode="json")
                    for e in list_events(s, run_id, after_seq=after_seq, limit=limit, event_types=event_type,
                                         step=step)]

        return await db(go)

    @app.get(f"{API}/runs/{{run_id}}/steps/{{step}}")
    async def get_step(run_id: str, step: int):
        return await db(lambda s: runs.step_detail(s, run_id, step))

    @app.get(f"{API}/runs/{{run_id}}/events/stream")
    async def stream_events(request: Request, run_id: str, after_seq: int = 0,
                            last_event_id: str | None = Header(default=None)):
        await db(lambda s: get_or_404(s, Run, run_id, "run").id)
        start = int(last_event_id) if last_event_id and last_event_id.isdigit() else after_seq
        poll = get_settings().sse_poll_seconds

        def fetch(after: int):
            # Read the status BEFORE the events: under READ COMMITTED, a terminal status observed here
            # guarantees that the events committed with it are visible to the following query.
            with session_scope() as s:
                status = s.scalar(select(Run.status).where(Run.id == run_id))
                rows = list_events(s, run_id, after_seq=after, limit=200)
                return [to_trace_event(r).model_dump(mode="json") for r in rows], status

        async def gen():
            cursor, idle = start, 0.0
            yield "retry: 2000\n\n"
            while True:
                if await request.is_disconnected():
                    return
                events, status = await run_in_threadpool(fetch, cursor)
                for ev in events:
                    cursor = ev["seq"]
                    yield f"id: {ev['seq']}\nevent: {ev['event_type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if not events:
                    if RunStatus(status) in TERMINAL_RUN_STATUSES:
                        yield f"event: end\ndata: {json.dumps({'status': status, 'last_seq': cursor})}\n\n"
                        return
                    idle += poll
                    if idle >= 15:
                        idle = 0.0
                        yield ": keep-alive\n\n"
                    await asyncio.sleep(poll)
                else:
                    idle = 0.0

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post(f"{API}/runs/{{run_id}}/pause")
    async def pause_run(run_id: str):
        res = await db(lambda s: runs.run_dict(runs.request_pause(s, run_id), s))
        if res["status"] == RunStatus.PAUSING.value:
            await orch().signal(f"run-{run_id}", "pause")
        return res

    @app.post(f"{API}/runs/{{run_id}}/resume")
    async def resume_run(run_id: str):
        res = await db(lambda s: runs.run_dict(runs.request_resume(s, run_id), s))
        await orch().signal(f"run-{run_id}", "resume")
        return res

    @app.post(f"{API}/runs/{{run_id}}/cancel")
    async def cancel_run(run_id: str, body: dict[str, Any] | None = Body(default=None)):
        """Cancel at the next step boundary; with {"reason", "operations"} it is an explained termination."""
        body = body or {}

        def go(s):
            run, needs = runs.request_cancel(s, run_id, body.get("reason"), body.get("operations"))
            return {"run": runs.run_dict(run, s), "needs": needs}

        res = await db(go)
        if res["needs"]:
            await orch().cancel(f"run-{run_id}")
        return res["run"]

    @app.get(f"{API}/runs/{{run_id}}/operations")
    async def run_operations(run_id: str, state: str | None = None, needs_review: bool | None = None,
                             abnormal: bool = False):
        def go(s):
            get_or_404(s, Run, run_id, "run")
            return operations.list_operations(s, run_id, state=state, needs_review=needs_review, abnormal=abnormal)

        return jsonable_encoder(await db(go))

    @app.get(f"{API}/runs/{{run_id}}/batches")
    async def run_batches(run_id: str):
        """JOINT_BATCH rounds of a run (phase 3A): members, statuses, environment step, outcomes."""
        from formal_lab_contracts.bundle import summarize_batches

        def go(s):
            get_or_404(s, Run, run_id, "run")
            rows = s.scalars(select(RunEvent).where(RunEvent.run_id == run_id,
                                                    RunEvent.event_type.in_(BATCH_EVENT_TYPES)).order_by(RunEvent.seq))
            return summarize_batches([{"event_type": r.event_type, "logical_step": r.logical_step,
                                       "actor_id": r.actor_id, "payload": r.payload} for r in rows])

        return jsonable_encoder(await db(go))

    @app.post(f"{API}/operations/{{operation_id:path}}/review")
    async def operation_review(operation_id: str, body: dict[str, Any] = Body(...)):
        return jsonable_encoder(await db(lambda s: operations.review_operation(s, operation_id, body)))

    @app.get(f"{API}/operations/{{operation_id:path}}")
    async def operation_get(operation_id: str):
        return jsonable_encoder(await db(lambda s: operations.get_operation(s, operation_id)))

    @app.post(f"{API}/runs/{{run_id}}/rerun", status_code=201)
    async def rerun(run_id: str):
        def go(s):
            src = get_or_404(s, Run, run_id, "run")
            run, _ = runs.create_run(s, src.project_id, {}, source_run=src)
            return runs.run_dict(run, s)

        return await _start(await db(go))

    @app.get(f"{API}/runs/{{run_id}}/diagnostics")
    async def diagnostics(run_id: str):
        def go(s):
            from .db import Operation

            run = get_or_404(s, Run, run_id, "run")
            ops = s.scalars(select(Operation).where(Operation.run_id == run_id)
                            .order_by(Operation.updated_at.desc()).limit(10))
            return {"run": runs.run_dict(run, s), "events": runs.run_events_count(s, run_id),
                    "recent_operations": [{"operation_id": o.operation_id, "status": o.status,
                                           "attempts": o.attempts, "updated_at": o.updated_at} for o in ops]}

        base = await db(go)
        try:
            base["workflow"] = await orch().describe(f"run-{run_id}")
        except FormalLabError as exc:
            base["workflow"] = {"error": exc.message}
        return jsonable_encoder(base)

    @app.get(f"{API}/runs/{{run_id}}/artifacts")
    async def run_artifacts(run_id: str):
        def go(s):
            from .db import Artifact, Snapshot

            get_or_404(s, Run, run_id, "run")
            steps = {x.artifact["digest"]["value"]: x.step for x in s.scalars(select(Snapshot).where(Snapshot.run_id == run_id))}
            return [{"kind": a.kind, "digest": a.digest, "ref": a.ref, "step": steps.get(a.ref["digest"]["value"]),
                     "created_at": a.created_at}
                    for a in s.scalars(select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.id))]

        return await db(go)

    @app.get(f"{API}/artifacts/{{digest}}")
    async def get_artifact(digest: str):
        def go(s):
            from .db import Artifact

            row = s.scalar(select(Artifact).where(Artifact.digest == digest))
            if row is None:
                raise NotFound(f"artifact {digest} not found")
            return row.ref

        ref = await db(go)
        from formal_lab_contracts import ArtifactRef

        data = await run_in_threadpool(artifact_store().get, ArtifactRef.model_validate(ref))
        return Response(content=data, media_type=ref["media_type"],
                        headers={"X-Artifact-Digest": digest, "X-Format-Version": ref["format_version"]})

    # ------------------------------------------------------------------ replay bundles
    @app.get(f"{API}/runs/{{run_id}}/export")
    async def export_run(run_id: str):
        from .services import bundles

        def go():
            with session_scope() as s:
                return bundles.export_run(s, run_id)

        data, name = await run_in_threadpool(go)
        return Response(content=data, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.post(f"{API}/projects/{{project_id}}/imports", status_code=201)
    async def import_bundle(project_id: str, request: Request, matrix_id: str | None = None):
        from .services import bundles

        data = await request.body()
        return await db(lambda s: runs.run_dict(bundles.import_bundle(s, project_id, data, matrix_id=matrix_id), s,
                                                full=True))

    # ------------------------------------------------------------------ matrices
    @app.post(f"{API}/projects/{{project_id}}/matrices", status_code=201)
    async def create_matrix(project_id: str, body: dict[str, Any] = Body(...)):
        from .services import matrices

        if matrices.is_v2(body):  # full cell configurations, queued and driven by a durable MatrixWorkflow
            def go2(s):
                mx, counts = matrices.create_matrix_v2(s, project_id, body)
                return {"matrix": matrices.matrix_dict(mx, s), "cells": counts,
                        "max_parallel": mx.spec["max_parallel"]}

            res = await db(go2)
            await orch().start_matrix(res["matrix"]["id"], res["max_parallel"])
            return res

        def go(s):
            mx, created = matrices.create_matrix(s, project_id, body)
            return {"matrix": matrices.matrix_dict(mx, s), "runs": [runs.run_dict(r, s) for r in created]}

        res = await db(go)
        for r in res["runs"]:
            await _start(r)
        return await db(lambda s: {"matrix": matrices.matrix_dict(s.get(Matrix, res["matrix"]["id"]), s),
                                   "run_ids": [r["id"] for r in res["runs"]]})

    async def _matrix_queue(matrix_id: str) -> None:
        mx = await db(lambda s: get_or_404(s, Matrix, matrix_id, "matrix").spec)
        await orch().start_matrix(matrix_id, int(mx.get("max_parallel", 2)))

    @app.get(f"{API}/matrices/{{matrix_id}}/cells")
    async def matrix_cells(matrix_id: str):
        from .services import matrices

        return jsonable_encoder(await db(lambda s: matrices.cells_dict(s, matrix_id)))

    @app.post(f"{API}/matrices/{{matrix_id}}/resume")
    async def matrix_resume(matrix_id: str):
        """Continue an interrupted queue (the queue state is in the database)."""
        await _matrix_queue(matrix_id)
        return {"matrix_id": matrix_id, "queue": "started"}

    @app.post(f"{API}/matrices/{{matrix_id}}/rerun-failed")
    async def matrix_rerun_failed(matrix_id: str):
        from .services import matrices

        n = await db(lambda s: matrices.rerun_failed(s, matrix_id))
        await _matrix_queue(matrix_id)
        return {"matrix_id": matrix_id, "requeued": n}

    @app.post(f"{API}/matrices/{{matrix_id}}/cells", status_code=201)
    async def matrix_merge(matrix_id: str, body: dict[str, Any] = Body(...)):
        """Incremental merge: new cells are queued; cells already done with the same configuration are reused."""
        from .services import matrices

        counts = await db(lambda s: matrices.merge_cells(s, matrix_id, body))
        await _matrix_queue(matrix_id)
        return {"matrix_id": matrix_id, "cells": counts}

    @app.post(f"{API}/matrices/{{matrix_id}}/cancel")
    async def matrix_cancel(matrix_id: str):
        from .services import matrices

        with contextlib.suppress(Exception):  # the queue may already be finished; the cells are what matter
            await orch().cancel(f"matrix-{matrix_id}")
        run_ids = await db(lambda s: matrices.cancel_cells(s, matrix_id))
        for rid in run_ids:
            await orch().cancel(f"run-{rid}")
        return {"matrix_id": matrix_id, "cancelled_runs": run_ids}

    @app.post(f"{API}/projects/{{project_id}}/matrices/imported", status_code=201)
    async def create_imported_matrix(project_id: str, body: dict[str, Any] = Body(...)):
        """Group imported runs (e.g. from an Inspect evaluation) into a matrix for reporting."""
        from .services import matrices
        from .services.common import new_id

        def go(s):
            get_or_404(s, Project, project_id, "project")
            mx = Matrix(id=new_id("mtx"), project_id=project_id, name=body.get("name") or "imported",
                        spec={"source": body.get("source", "import"), **(body.get("spec") or {})})
            s.add(mx)
            s.flush()
            matrices.attach_runs(s, mx.id, body.get("run_ids", []))
            return matrices.matrix_dict(mx, s)

        return await db(go)

    @app.get(f"{API}/projects/{{project_id}}/matrices")
    async def list_matrices(project_id: str):
        from .services import matrices

        return await db(lambda s: [matrices.matrix_dict(m, s) for m in s.scalars(
            select(Matrix).where(Matrix.project_id == project_id).order_by(Matrix.created_at.desc()))])

    @app.get(f"{API}/matrices/{{matrix_id}}")
    async def get_matrix(matrix_id: str):
        from .services import matrices

        return await db(lambda s: {**matrices.matrix_dict(get_or_404(s, Matrix, matrix_id, "matrix"), s),
                                   "run_list": [runs.run_dict(r, s) for r in s.scalars(
                                       select(Run).where(Run.matrix_id == matrix_id).order_by(Run.created_at))]})

    @app.get(f"{API}/matrices/{{matrix_id}}/report")
    async def matrix_report(matrix_id: str, format: str = "json"):
        """v1 matrices: the phase-1 report; v2: splits, per-scenario / pooled (scenario clusters), paired comparisons
        per dimension, probes with sources; also as CSV or Markdown (`?format=csv|md`)."""
        from fastapi.responses import PlainTextResponse
        from formal_lab_contracts import MetricDefinition
        from formal_lab_eval.experiments import to_csv, to_markdown

        from .services import matrices

        def go(s):
            mx = get_or_404(s, Matrix, matrix_id, "matrix")
            return matrices.report_v2(s, matrix_id) if mx.spec.get("version") == 2 else matrices.report(s, matrix_id)

        rep = await db(go)
        if format == "json":
            return jsonable_encoder(rep)
        if "splits" not in rep:
            raise InvalidInput("CSV / Markdown reports are produced for v2 matrices")
        if format == "csv":
            return PlainTextResponse(to_csv(rep), media_type="text/csv")
        defs = [MetricDefinition.model_validate(d) for d in rep["definitions"]]
        return PlainTextResponse(to_markdown(rep, f"Matrix {rep['matrix']['name']}", defs),
                                 media_type="text/markdown")

    # ------------------------------------------------------------------ uploads (e.g. Inspect .eval logs)
    @app.post(f"{API}/projects/{{project_id}}/artifacts", status_code=201)
    async def upload_artifact(project_id: str, request: Request, name: str, kind: str = "upload",
                              format_version: str = "opaque", matrix_id: str | None = None):
        from .db import Artifact

        data = await request.body()
        media_type = request.headers.get("content-type", "application/octet-stream")

        def go(s):
            get_or_404(s, Project, project_id, "project")
            ref = artifact_store().put(data, name=name, media_type=media_type, format_version=format_version)
            s.add(Artifact(run_id=None, kind=kind, digest=ref.digest.value, ref=ref.model_dump(mode="json")))
            if matrix_id:
                mx = get_or_404(s, Matrix, matrix_id, "matrix")
                mx.spec = {**mx.spec, "artifacts": [*mx.spec.get("artifacts", []), ref.model_dump(mode="json")]}
            return ref.model_dump(mode="json")

        return await db(go)

    _ = ModelVersion  # imported for type completeness


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("formal_lab_api.app:app", host=settings.api_host, port=settings.api_port,
                log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
