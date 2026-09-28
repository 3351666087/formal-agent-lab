"""Environment adapter for the local order service (P2-061): the platform's only way to reach the business service.

It implements the formal Environment + SessionEnvironment interfaces over the service's fixed HTTP API; the generic
engine never sees a business client. Declared capabilities (negotiated at run start, P2-050):

- env.persistent_session  — the business state lives in the service; snapshots are SESSION_MARKERs and are never
                            restored (after a crash the adapter re-attaches to the live session);
- env.snapshot            — a marker (tenant, revision, operation count) per step;
- env.query_operation     — "what happened to operation <id>?" (GET /operations/{id});
- env.idempotent_step     — the service executes an operation id at most once;
- env.multi_actor         — revision-based conflict arbitration by the service's conditional updates;
- env.observe_on_request  — every observation is fresh from the service;
- env.reset_session / env.state_import — service-side reset to a case instance; export / import of the state.

Not declared: env.pure_replayable, env.restore — a worker restoring an old snapshot cannot roll the service back.

Failure mapping: no answer (timeout, connection refused / reset, 502–504) → ResultUnknown (the operation may have been
committed; the coordinator settles it by id); 409 / other 4xx → NonRetryableFailure; service REJECTED → a REJECTED
outcome with the service's reason (and ConflictInfo for stale revisions).
"""

from __future__ import annotations

import copy
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    ConflictInfo,
    EnvironmentSession,
    EnvironmentSnapshot,
    EvidenceRef,
    Fact,
    ModelPackage,
    Observation,
    OutcomeStatus,
    PluginDescriptor,
    ScenarioManifest,
    digest_of,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import InvalidInput, NonRetryableFailure, ResultUnknown

from .instance import CASES, instance
from .net import trust_env

ENV_ID = "formal-lab.example.orders.service-env"
ENV_VERSION = "1.0.0"

CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "endpoint": {"type": "string", "default": "http://127.0.0.1:8765",
                     "description": "service base URL: a loopback port (local-lite) or the Compose service name "
                                    "(http://orders:8765, local-services)"},
        "tenant": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]{0,63}$",
                   "description": "service tenant (default: derived from the run id)"},
        "case": {"type": "string", "enum": sorted(CASES), "default": "normal"},
        "conditions": {"type": "object", "description": "override the case's service operating conditions"},
        "timeout_s": {"type": "number", "exclusiveMinimum": 0, "default": 5.0,
                      "description": "per-request client timeout; a later answer counts as lost"},
        "ready_timeout_s": {"type": "number", "exclusiveMinimum": 0, "default": 30.0,
                            "description": "how long to wait for the service to come back before giving up"},
        "project": {"type": "string", "default": "formal-lab"},
        "profile": {"type": "string", "enum": ["local-lite", "local-services", "local-kind"],
                    "default": "local-lite"},
    },
    "additionalProperties": False,
}

CAPABILITIES = [caps.ENV_PERSISTENT_SESSION, caps.ENV_SNAPSHOT, caps.ENV_QUERY_OPERATION, caps.ENV_IDEMPOTENT_STEP,
                caps.ENV_MULTI_ACTOR, caps.ENV_OBSERVE_ON_REQUEST, caps.ENV_RESET, caps.ENV_STATE_IMPORT]

DEPLOYMENT_PROFILES = {"local-lite": "loopback port started by the dev script or lifecycle manager (127.0.0.1)",
                       "local-services": "Compose service `orders` (http://orders:8765 inside the stack)",
                       "local-kind": "not provided for this example"}

DESCRIPTOR = PluginDescriptor(
    plugin_id=ENV_ID, version=ENV_VERSION, interface="ENVIRONMENT",
    capabilities=[{"id": caps.PROFILE_DETERMINISTIC_FINITE_V1},
                  {"id": caps.ENV_PERSISTENT_SESSION, "params": {"deployment_profiles": DEPLOYMENT_PROFILES,
                                                                 "recovery_modes": ["SERVICE_RESET", "STATE_IMPORT"]}},
                  *({"id": c} for c in CAPABILITIES[1:])],
    semantic_profiles=["deterministic_finite_v1"], config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_example_orders.env:create",
    ui={"label": "本地订单服务（持久会话）", "category": "environment",
        "description": "Independent FastAPI + SQLite order service reached over HTTP: persistent session, operation "
                       "lookup by id, idempotent steps, service-side reset and state import. Deployment: loopback "
                       "port (local-lite) or Compose service `orders` (local-services)"},
    license="Apache-2.0", source="formal-lab-example-orders")


def tenant_for(run_id: str) -> str:
    return ("r-" + re.sub(r"[^a-z0-9_-]", "-", run_id.lower()))[:64]


class OrderServiceEnvironment:
    descriptor = DESCRIPTOR

    def __init__(self, config: dict[str, Any] | None = None, *, transport: httpx.BaseTransport | None = None):
        self.config = {"endpoint": "http://127.0.0.1:8765", "case": "normal", "timeout_s": 5.0,
                       "ready_timeout_s": 30.0, "project": "formal-lab", "profile": "local-lite", **(config or {})}
        unknown = set(self.config) - set(CONFIG_SCHEMA["properties"])
        if unknown:
            raise InvalidInput(f"unknown order-service environment config keys {sorted(unknown)}")
        self._transport = transport
        self._client: httpx.Client | None = None
        self._data: dict[str, Any] | None = None
        self._state: dict[str, Any] | None = None  # last /state answer (cache for the current step)

    # ------------------------------------------------------------------ http
    @property
    def endpoint(self) -> str:
        return str(self.config["endpoint"]).rstrip("/")

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self.endpoint, timeout=float(self.config["timeout_s"]),
                                         trust_env=trust_env(self.endpoint),
                                        transport=self._transport)
        return self._client

    def _t(self, path: str = "") -> str:
        return f"/t/{self._require()['tenant']}{path}"

    def _call(self, method: str, url: str, *, lost_ok: bool = False, **kw: Any) -> httpx.Response:
        try:
            resp = self._http().request(method, url, **kw)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if lost_ok:
                raise ResultUnknown(f"no answer from the order service ({type(exc).__name__}: {exc})") from exc
            raise
        if resp.status_code in (502, 503, 504) and lost_ok:
            raise ResultUnknown(f"order service answered {resp.status_code}")
        return resp

    def wait_ready(self, timeout_s: float | None = None) -> dict[str, Any]:
        """Poll the tenant until the service answers (it may be restarting)."""
        deadline = time.monotonic() + float(timeout_s or self.config["ready_timeout_s"])
        last = ""
        while True:
            try:
                resp = self._http().get(self._t("/health"))
                if resp.status_code == 200:
                    return resp.json()
                last = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code == 404:
                    raise NonRetryableFailure(f"order service has no tenant {self._require()['tenant']}: {last}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last = f"{type(exc).__name__}: {exc}"
            if time.monotonic() > deadline:
                raise ResultUnknown(f"order service not ready after {timeout_s or self.config['ready_timeout_s']}s "
                                    f"({last})")
            time.sleep(0.2)

    # ------------------------------------------------------------------ lifecycle
    def reset(self, scenario: ScenarioManifest, package: ModelPackage, *, run_id: str, seed: int) -> Observation:
        tenant = self.config.get("tenant") or tenant_for(run_id)
        self._data = {"run_id": run_id, "tenant": tenant, "seed": seed, "case": self.config["case"],
                      "scenario_id": scenario.scenario_id, "conflict_policy": scenario.turns.conflict_policy.value,
                      "created_at": datetime.now(UTC).isoformat(), "status": "STARTING"}
        self._reset_service(seed)
        self._data["status"] = "READY"
        return self.observe(scenario.participants[0].actor_id)

    def _reset_service(self, seed: int) -> dict[str, Any]:
        inst = instance(self._require()["case"], seed)
        body: dict[str, Any] = {"instance": inst.as_dict()}
        if "conditions" in self.config:
            body["conditions"] = self.config["conditions"]
        resp = self._http().post(self._t("/admin/reset"), json=body)
        if resp.status_code != 200:
            raise NonRetryableFailure(f"order service reset failed: HTTP {resp.status_code} {resp.text[:300]}")
        self._state = resp.json()
        return self._state

    def reset_session(self, *, seed: int) -> Observation:
        self._require()["seed"] = seed
        self._reset_service(seed)
        return self.observe("reset")

    def close(self) -> None:
        if self._data is not None:
            self._data["status"] = "CLOSED"
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------ observation
    def _require(self) -> dict[str, Any]:
        if self._data is None:
            raise NonRetryableFailure("environment used before reset/attach")
        return self._data

    def _fetch(self) -> dict[str, Any]:
        resp = self._call("GET", self._t("/state"))
        if resp.status_code != 200:
            raise NonRetryableFailure(f"order service /state: HTTP {resp.status_code} {resp.text[:300]}")
        self._state = resp.json()
        return self._state

    def observe(self, actor_id: str, fresh_paths: list[str] | None = None) -> Observation:
        data = self._require()
        try:
            st = self._fetch()
        except (httpx.TimeoutException, httpx.TransportError):
            self.wait_ready()
            st = self._fetch()
        step = self._op_count(st)
        facts = [Fact(path=p, value=v, observed_at_step=step) for p, v in sorted(st["values"].items())]
        return Observation(run_id=data["run_id"], actor_id=actor_id, step=step, state_revision=st["revision"],
                           facts=facts, unknowns=[],
                           evidence=[EvidenceRef(kind="session", id=f"{data['tenant']}@{st['revision']}",
                                                 note=f"GET {self.endpoint}/t/{data['tenant']}/state")],
                           requested_paths=sorted(fresh_paths or []))

    def observe_paths(self, actor_id: str, paths: list[str]) -> Observation:
        return self.observe(actor_id, fresh_paths=paths)

    @staticmethod
    def _op_count(st: dict[str, Any]) -> int:
        return int(st.get("operations", st.get("revision", 0)))

    # ------------------------------------------------------------------ transition
    def _outcome(self, answer: dict[str, Any]) -> ActionOutcome:
        """The service's stored answer as an ActionOutcome (the caller's step / proposal / turn come back from the
        context the service stored with the operation, so a looked-up outcome equals the one that was lost)."""
        from formal_lab_contracts import GroundAction, TurnRef

        data = self._require()
        ctx = answer.get("context") or {}
        applied = answer["status"] == "APPLIED"
        result = {k: answer[k] for k in ("written_paths", "written", "properties", "reason") if k in answer}
        result.update({"service_seq": answer.get("seq"), "replayed": answer.get("replayed", False),
                       "handling_ms": answer.get("handling_ms")})
        conflict = None
        if answer.get("conflict"):
            c = answer["conflict"]
            conflict = ConflictInfo(policy=data.get("conflict_policy", "REVALIDATE"),
                                    based_on_revision=int(c.get("based_on_revision") or 0),
                                    current_revision=int(c.get("current_revision") or answer["revision_before"]),
                                    changed_paths=list(c.get("changed_paths", [])),
                                    reason=f"service conditional update refused: {answer.get('reason')}"
                                           + (f" (written by {', '.join(c['writers'])})" if c.get("writers") else ""))
        return ActionOutcome(
            operation_id=answer["operation_id"], run_id=data["run_id"], step_id=ctx.get("step_id") or
            answer["operation_id"], proposal_id=ctx.get("proposal_id"),
            action=GroundAction(action_type=answer["action"], params=answer["params"]),
            status=OutcomeStatus.APPLIED if applied else OutcomeStatus.REJECTED, effect_applied=applied,
            revision_before=answer["revision_before"], revision_after=answer["revision_after"], result=result,
            conflict=conflict, turn=TurnRef.model_validate(ctx["turn"]) if ctx.get("turn") else None,
            evidence=[EvidenceRef(kind="operation", id=answer["operation_id"],
                                  note=f"service seq {answer.get('seq')}"
                                       + (" (stored answer re-sent)" if answer.get("replayed") else ""))])

    def step(self, proposal: ActionProposal, *, operation_id: str) -> ActionOutcome:
        data = self._require()
        body = {"operation_id": operation_id, "actor_id": proposal.actor_id,
                "action": proposal.action.action_type, "params": dict(proposal.action.params),
                "based_on_revision": proposal.based_on_revision, "conflict_policy": data.get("conflict_policy"),
                "step_id": proposal.step_id, "proposal_id": proposal.proposal_id,
                "turn": proposal.turn.model_dump(mode="json") if proposal.turn else None}
        resp = self._call("POST", self._t("/operations"), json=body, lost_ok=True)
        if resp.status_code != 200:
            raise NonRetryableFailure(f"order service refused operation {operation_id}: HTTP {resp.status_code} "
                                      f"{resp.text[:300]}")
        self._state = None
        return self._outcome(resp.json())

    def query_operation(self, operation_id: str) -> ActionOutcome | None:
        self.wait_ready()
        resp = self._call("GET", self._t(f"/operations/{operation_id}"))
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise NonRetryableFailure(f"order service lookup of {operation_id}: HTTP {resp.status_code}")
        return self._outcome(resp.json())

    # ------------------------------------------------------------------ session / persistence
    def session(self) -> EnvironmentSession:
        data = self._require()
        try:
            health = self._http().get("/health").json()
        except (httpx.HTTPError, ValueError) as exc:
            health = {"status": "unreachable", "error": str(exc)[:200]}
        st = self._state or {}
        now = datetime.now(UTC)
        return EnvironmentSession(
            session_id=f"orders-{data['tenant']}", environment=self.descriptor.ref(), backend="SERVICE",
            status=data.get("status", "READY"), capabilities=list(CAPABILITIES),
            recovery_modes=["SERVICE_RESET", "STATE_IMPORT"], endpoint=self.endpoint,
            project_label=str(self.config["project"]),
            owner={"run_id": data["run_id"], "tenant": data["tenant"], "case": data["case"],
                   "profile": str(self.config["profile"])},
            revision=int(st.get("revision", 0)), created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=now, health=health)

    def snapshot(self) -> EnvironmentSnapshot:
        data = self._require()
        st = self._fetch()
        payload = {"config": self.config, "data": data, "service_revision": st["revision"]}
        return EnvironmentSnapshot(environment=self.descriptor.ref(), step=self._op_count(st),
                                   state_revision=st["revision"], digest=digest_of(payload),
                                   data=copy.deepcopy(payload), kind="SESSION_MARKER",
                                   session_id=f"orders-{data['tenant']}")

    def attach(self, snapshot: EnvironmentSnapshot) -> None:
        """Re-attach to the live session after a restart; the service must not be *behind* the marker."""
        if snapshot.environment.plugin_id != ENV_ID:
            raise InvalidInput(f"snapshot belongs to {snapshot.environment.plugin_id}")
        payload = copy.deepcopy(snapshot.data)
        self.config = payload["config"]
        self._data = payload["data"]
        if self._client is not None and str(self._client.base_url).rstrip("/") != self.endpoint:
            self._client.close()
            self._client = None
        self.wait_ready()
        st = self._fetch()
        if st["revision"] < snapshot.state_revision:
            raise NonRetryableFailure(f"order service tenant {self._data['tenant']} is at revision {st['revision']}, "
                                      f"behind the recorded session marker ({snapshot.state_revision}): it was reset "
                                      "or replaced outside this run")

    def restore(self, snapshot: EnvironmentSnapshot) -> None:
        raise NonRetryableFailure("a persistent order-service session cannot be restored to an earlier snapshot")

    def export_state(self) -> dict[str, Any]:
        resp = self._call("GET", self._t("/admin/export"))
        resp.raise_for_status()
        return resp.json()

    def import_state(self, state: dict[str, Any]) -> None:
        resp = self._call("POST", self._t("/admin/import"), json=state)
        if resp.status_code != 200:
            raise InvalidInput(f"order service import failed: HTTP {resp.status_code} {resp.text[:300]}")
        self._state = resp.json()

    def set_conditions(self, conditions: dict[str, Any]) -> dict[str, Any]:
        resp = self._call("POST", self._t("/admin/conditions"), json=conditions)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ evaluator access
    def truth_state(self) -> dict[str, Any]:
        return dict(self._fetch()["values"])  # always the live service: other writers may have acted

    def truth_properties(self) -> dict[str, bool]:
        return dict(self._fetch()["properties"])

    @property
    def current_step(self) -> int:
        return self._op_count(self._fetch())


def create(config: dict[str, Any] | None, services: Any = None) -> OrderServiceEnvironment:
    return OrderServiceEnvironment(config)
