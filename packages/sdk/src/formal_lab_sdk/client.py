"""HTTP client for the formal-agent-lab platform API (the same services the Web UI and CLI use)."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from typing import Any

import httpx
from formal_lab_contracts import BoundedCheckResult, QueryBundle, RunManifest, TraceEvent
from formal_lab_contracts.errors import ErrorInfo, FormalLabError, RetryableFailure

DEFAULT_URL = os.environ.get("FAL_API_URL", "http://127.0.0.1:8000/api/v1")
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"}


def is_loopback(url: str) -> bool:
    """True for localhost / 127.0.0.0/8 / ::1: such traffic never goes through an HTTP proxy from the environment
    (a system-wide HTTP_PROXY without NO_PROXY would otherwise send it to a proxy that cannot reach this machine's
    loopback — the proxy answers 502 or the connection times out)."""
    host = httpx.URL(url).host
    return host in ("localhost", "::1") or host.startswith("127.")


class Client:
    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 60.0, transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport,
                                  trust_env=not is_loopback(self.base_url))

    # ------------------------------------------------------------------ plumbing
    def _request(self, method: str, path: str, **kw: Any) -> Any:
        try:
            resp = self._http.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise RetryableFailure(f"platform API unreachable at {self.base_url}: {exc}") from exc
        if resp.status_code >= 400:
            try:
                info = ErrorInfo.model_validate(resp.json()["error"])
            except Exception:
                raise FormalLabError(f"HTTP {resp.status_code}: {resp.text[:300]}") from None
            raise FormalLabError.from_info(info)
        if resp.status_code == 204 or not resp.content:
            return None
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.content

    def get(self, path: str, **kw: Any) -> Any:
        return self._request("GET", path, **kw)

    def post(self, path: str, json_body: Any = None, **kw: Any) -> Any:
        return self._request("POST", path, json=json_body, **kw)

    # ------------------------------------------------------------------ catalog / meta
    def meta(self) -> dict[str, Any]:
        return self.get("/meta")

    def plugins(self, interface: str | None = None) -> list[dict[str, Any]]:
        return self.get("/plugins", params={"interface": interface} if interface else None)

    # ------------------------------------------------------------------ projects / models
    def projects(self) -> list[dict[str, Any]]:
        return self.get("/projects")

    def create_project(self, name: str, description: str | None = None, group: str | None = None) -> dict[str, Any]:
        return self.post("/projects", {"name": name, "description": description, "group": group})

    def find_project(self, name_or_id: str) -> dict[str, Any]:
        for p in self.projects():
            if name_or_id in (p["id"], p["name"]):
                return p
        raise FormalLabError.from_info(ErrorInfo(code="NOT_FOUND", message=f"project {name_or_id!r} not found",
                                                 retryable=False))

    def validate_model(self, ir: dict[str, Any]) -> dict[str, Any]:
        return self.post("/models/validate", {"ir": ir})

    def models(self, project_id: str) -> list[dict[str, Any]]:
        return self.get(f"/projects/{project_id}/models")

    def create_model(self, project_id: str, package_id: str, ir: dict[str, Any] | None = None,
                     name: str | None = None, *, source: dict[str, Any] | None = None,
                     frontend: dict[str, Any] | None = None) -> dict:
        """Create a model from neutral IR, or from a frontend source envelope (`source` + `frontend`: the
        MODEL_FRONTEND plugin that compiles it, e.g. the MAL attack-graph frontend)."""
        body = {"package_id": package_id, "name": name}
        body.update({"source": source, "frontend": frontend} if source is not None else {"ir": ir})
        return self.post(f"/projects/{project_id}/models", body)

    def add_model_version(self, model_id: str, ir: dict[str, Any] | None = None, note: str | None = None, *,
                          source: dict[str, Any] | None = None, frontend: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"note": note}
        body.update({"source": source, "frontend": frontend} if source is not None else {"ir": ir})
        return self.post(f"/models/{model_id}/versions", body)

    def model_version(self, model_id: str, version: int) -> dict[str, Any]:
        return self.get(f"/models/{model_id}/versions/{version}")

    def check(self, model_version_id: str, query: dict[str, Any], state: dict | None = None,
              unknown_paths: list[str] | None = None) -> BoundedCheckResult:
        return BoundedCheckResult.model_validate(self.check_record(model_version_id, query, state,
                                                                   unknown_paths)["result"])

    def check_record(self, model_version_id: str, query: dict[str, Any], state: dict | None = None,
                     unknown_paths: list[str] | None = None) -> dict[str, Any]:
        """Stored check with its query bundle id, explanation and witness replay."""
        return self.post(f"/model-versions/{model_version_id}/checks",
                         {"query": query, "state": state, "unknown_paths": unknown_paths})

    def query_bundle(self, bundle_id: str, *, export: bool = False) -> QueryBundle:
        """A replayable query bundle; `export=True` embeds the model package for offline replay."""
        data = self.get(f"/query-bundles/{bundle_id}/export" if export else f"/query-bundles/{bundle_id}")
        return QueryBundle.model_validate(data)

    def replay_query(self, bundle: QueryBundle | dict[str, Any]) -> dict[str, Any]:
        body = bundle.model_dump(mode="json") if isinstance(bundle, QueryBundle) else bundle
        return self.post("/query-bundles/replay", body)

    # ------------------------------------------------------------------ scenarios / strategies
    def scenarios(self, project_id: str) -> list[dict[str, Any]]:
        return self.get(f"/projects/{project_id}/scenarios")

    def create_scenario(self, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.post(f"/projects/{project_id}/scenarios", body)

    def strategies(self, project_id: str) -> list[dict[str, Any]]:
        return self.get(f"/projects/{project_id}/strategies")

    def create_strategy(self, project_id: str, name: str, plugin_id: str, config: dict | None = None,
                        plugin_version: str | None = None) -> dict[str, Any]:
        return self.post(f"/projects/{project_id}/strategies", {"name": name, "plugin_id": plugin_id,
                                                                "plugin_version": plugin_version,
                                                                "config": config or {}})

    # ------------------------------------------------------------------ runs
    def start_run(self, project_id: str, scenario_id: str, strategy_config_id: str | None = None,
                  seed: int | None = None, budget: dict | None = None, idempotency_key: str | None = None) -> dict:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self.post(f"/projects/{project_id}/runs", {"scenario_id": scenario_id,
                                                          "strategy_config_id": strategy_config_id, "seed": seed,
                                                          "budget": budget}, headers=headers)

    def run(self, run_id: str) -> dict[str, Any]:
        return self.get(f"/runs/{run_id}")

    def manifest(self, run_id: str) -> RunManifest:
        return RunManifest.model_validate(self.run(run_id)["manifest"])

    def runs(self, project_id: str, **filters: Any) -> list[dict[str, Any]]:
        return self.get(f"/projects/{project_id}/runs", params={k: v for k, v in filters.items() if v})

    def events(self, run_id: str, after_seq: int = 0, limit: int = 5000) -> list[TraceEvent]:
        return [TraceEvent.model_validate(e) for e in self.get(f"/runs/{run_id}/events",
                                                                params={"after_seq": after_seq, "limit": limit})]

    def step(self, run_id: str, step: int) -> dict[str, Any]:
        return self.get(f"/runs/{run_id}/steps/{step}")

    def pause(self, run_id: str) -> dict[str, Any]:
        return self.post(f"/runs/{run_id}/pause")

    def resume(self, run_id: str) -> dict[str, Any]:
        return self.post(f"/runs/{run_id}/resume")

    def cancel(self, run_id: str, reason: str | None = None, operations: list[str] | None = None) -> dict[str, Any]:
        """Cancel at the next step boundary; with a reason it is an explained termination by an operator."""
        body = {"reason": reason, "operations": list(operations or [])} if reason else None
        return self.post(f"/runs/{run_id}/cancel", body)

    # ------------------------------------------------------------------ rules / releases / regression (P2-070 …)
    def rulesets(self, project_id: str, ruleset_id: str | None = None) -> list[dict[str, Any]]:
        return self.get(f"/projects/{project_id}/rulesets", params={"ruleset_id": ruleset_id} if ruleset_id else None)

    def save_ruleset(self, project_id: str, model_version_id: str, ruleset_id: str, rules: list[dict[str, Any]],
                     name: str | None = None, note: str | None = None) -> dict[str, Any]:
        return self.post(f"/projects/{project_id}/rulesets", {"model_version_id": model_version_id,
                                                               "ruleset_id": ruleset_id, "rules": rules,
                                                               "name": name, "note": note})

    def release(self, model_version_id: str, *, ruleset: tuple[str, int] | None = None,
                regression: str | list[str] = "model", horizon: int = 6, required_checks: list[str] | None = None,
                required_holds: list[str] | None = None) -> dict[str, Any]:
        """Run the pre-release checks. `required_checks` must run with a conclusive result, `required_holds` names
        properties that must hold within the horizon (phase 3A)."""
        body: dict[str, Any] = {"regression": regression, "horizon": horizon}
        if ruleset:
            body["ruleset"] = {"ruleset_id": ruleset[0], "version": ruleset[1]}
        if required_checks:
            body["required_checks"] = required_checks
        if required_holds:
            body["required_holds"] = required_holds
        return self.post(f"/model-versions/{model_version_id}/releases", body)

    def capabilities(self, model_version_id: str) -> dict[str, Any]:
        """Feature support of a model version from declared capabilities (phase 3A)."""
        return self.get(f"/model-versions/{model_version_id}/capabilities")

    def releases(self, project_id: str) -> list[dict[str, Any]]:
        return self.get(f"/projects/{project_id}/releases")

    def regression_cases(self, project_id: str, package_id: str | None = None) -> list[dict[str, Any]]:
        return self.get(f"/projects/{project_id}/regression-cases",
                        params={"package_id": package_id} if package_id else None)

    def replay_case(self, case_id: str, model_version_id: str) -> dict[str, Any]:
        return self.post(f"/regression-cases/{case_id}/replay", {"model_version_id": model_version_id})

    def revision_suggestions(self, run_id: str) -> list[dict[str, Any]]:
        return self.get(f"/runs/{run_id}/revision-suggestions")

    def operations(self, run_id: str, *, state: str | None = None, needs_review: bool | None = None,
                   abnormal: bool = False) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"abnormal": str(abnormal).lower()}
        if state:
            params["state"] = state
        if needs_review is not None:
            params["needs_review"] = str(needs_review).lower()
        return self.get(f"/runs/{run_id}/operations", params=params)

    def batches(self, run_id: str) -> list[dict[str, Any]]:
        """JOINT_BATCH rounds of a run: members, statuses, environment step, outcomes (phase 3A)."""
        return self.get(f"/runs/{run_id}/batches")

    def operation(self, operation_id: str) -> dict[str, Any]:
        return self.get(f"/operations/{operation_id}")

    def review_operation(self, operation_id: str, status: str, note: str, by: str = "operator",
                         supersede: bool = False) -> dict[str, Any]:
        return self.post(f"/operations/{operation_id}/review",
                         {"status": status, "note": note, "by": by, "supersede": supersede})

    def rerun(self, run_id: str) -> dict[str, Any]:
        return self.post(f"/runs/{run_id}/rerun")

    def wait(self, run_id: str, timeout: float = 600, poll: float = 0.5) -> dict[str, Any]:
        deadline = time.time() + timeout
        while True:
            run = self.run(run_id)
            if run["status"] in TERMINAL or time.time() > deadline:
                return run
            time.sleep(poll)

    def follow(self, run_id: str, after_seq: int = 0, max_reconnects: int = 20) -> Iterator[TraceEvent]:
        """Stream events over SSE; reconnects with Last-Event-ID so no event is lost or repeated."""
        last = after_seq
        for _ in range(max_reconnects + 1):
            headers = {"Last-Event-ID": str(last)} if last else {}
            try:
                with self._http.stream("GET", f"/runs/{run_id}/events/stream", headers=headers,
                                       timeout=httpx.Timeout(10, read=60)) as resp:
                    event, data = None, []
                    for line in resp.iter_lines():
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:"):
                            data.append(line[5:].strip())
                        elif line == "":
                            if event == "end":
                                return
                            if data and event:
                                ev = TraceEvent.model_validate(json.loads("\n".join(data)))
                                last = ev.seq
                                yield ev
                            event, data = None, []
                return
            except httpx.HTTPError:
                time.sleep(1.0)
        raise RetryableFailure(f"event stream for {run_id} kept failing")

    # ------------------------------------------------------------------ replay / matrices
    def export_run(self, run_id: str) -> bytes:
        return self.get(f"/runs/{run_id}/export")

    def import_bundle(self, project_id: str, data: bytes, matrix_id: str | None = None) -> dict[str, Any]:
        return self._request("POST", f"/projects/{project_id}/imports", content=data,
                             params={"matrix_id": matrix_id} if matrix_id else None,
                             headers={"content-type": "application/zip"})

    # ------------------------------------------------------------------ research cases (phase 5A)
    def research_cases(self, project_id: str) -> list[dict[str, Any]]:
        return self.get(f"/projects/{project_id}/research/cases")

    def import_research_case(self, project_id: str, data: bytes) -> dict[str, Any]:
        """Import a case directory packaged as a zip; the platform validates it (digests, identities, separation)."""
        return self._request("POST", f"/projects/{project_id}/research/cases", content=data,
                             headers={"content-type": "application/zip"})

    def research_case(self, rc_id: str) -> dict[str, Any]:
        return self.get(f"/research/cases/{rc_id}")

    def export_research_case(self, rc_id: str) -> bytes:
        return self.get(f"/research/cases/{rc_id}/export")

    def model_version_research(self, version_id: str) -> list[dict[str, Any]]:
        return self.get(f"/model-versions/{version_id}/research")

    def run_research(self, run_id: str) -> list[dict[str, Any]]:
        return self.get(f"/runs/{run_id}/research")

    def create_matrix(self, project_id: str, *, scenarios: list[str], strategies: list[str], seeds: list[int],
                      budgets: list[dict] | None = None, name: str | None = None) -> dict[str, Any]:
        return self.post(f"/projects/{project_id}/matrices", {"scenarios": scenarios, "strategies": strategies,
                                                              "seeds": seeds, "budgets": budgets, "name": name})

    def matrix(self, matrix_id: str) -> dict[str, Any]:
        return self.get(f"/matrices/{matrix_id}")

    def matrix_report(self, matrix_id: str, fmt: str = "json") -> Any:
        """JSON report (dict); for v2 matrices also `fmt="csv"` or `"md"` (text)."""
        res = self.get(f"/matrices/{matrix_id}/report", params={"format": fmt})
        return res.decode() if isinstance(res, bytes) else res

    # ---- matrix v2: full cell configurations in a durable queue (P2-080 / P2-081)
    def create_matrix_v2(self, project_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        return self.post(f"/projects/{project_id}/matrices", {**spec, "version": 2})

    def matrix_cells(self, matrix_id: str) -> list[dict[str, Any]]:
        return self.get(f"/matrices/{matrix_id}/cells")

    def matrix_resume(self, matrix_id: str) -> dict[str, Any]:
        return self.post(f"/matrices/{matrix_id}/resume")

    def matrix_rerun_failed(self, matrix_id: str) -> dict[str, Any]:
        return self.post(f"/matrices/{matrix_id}/rerun-failed")

    def matrix_merge(self, matrix_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        return self.post(f"/matrices/{matrix_id}/cells", spec)

    def matrix_cancel(self, matrix_id: str) -> dict[str, Any]:
        return self.post(f"/matrices/{matrix_id}/cancel")

    def wait_matrix(self, matrix_id: str, timeout: float = 3600, poll: float = 2.0) -> list[dict[str, Any]]:
        """Until no cell is queued or running; returns the cells."""
        import time

        deadline = time.monotonic() + timeout
        while True:
            cells = self.matrix_cells(matrix_id)
            if all(c["status"] in ("DONE", "FAILED", "CANCELLED") for c in cells):
                return cells
            if time.monotonic() > deadline:
                raise RetryableFailure(f"matrix {matrix_id} not finished after {timeout}s")
            time.sleep(poll)

    def create_imported_matrix(self, project_id: str, name: str, run_ids: list[str], source: str,
                               spec: dict | None = None) -> dict[str, Any]:
        return self.post(f"/projects/{project_id}/matrices/imported", {"name": name, "run_ids": run_ids,
                                                                       "source": source, "spec": spec or {}})

    def upload_artifact(self, project_id: str, data: bytes, *, name: str, kind: str, format_version: str,
                        media_type: str = "application/octet-stream", matrix_id: str | None = None) -> dict:
        params = {"name": name, "kind": kind, "format_version": format_version}
        if matrix_id:
            params["matrix_id"] = matrix_id
        return self._request("POST", f"/projects/{project_id}/artifacts", content=data, params=params,
                             headers={"content-type": media_type})
