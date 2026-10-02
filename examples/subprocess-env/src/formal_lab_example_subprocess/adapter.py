"""Subprocess environment adapter (phase 4A, A4): the reference for wrapping a world that runs in its own process.

It implements the existing Environment interface (reset / observe / step / step_batch / query_operation / snapshot /
restore / close) by talking JSON lines to a child (`formal_lab_example_subprocess.world`, hosting the generic driver
world). What a later adapter has to make explicit, and how this one does it:

- **session identity** — one child per adapter instance; `session()` names it (`subproc-<pid>-<nonce>`); a restart is a
  new session, recorded as such;
- **request identity** — every request carries an increasing id that the answer must echo; any other answer is a
  protocol error, never accepted as the result;
- **timeouts** — every request waits at most `timeout_s`; a child that does not answer is killed and the call raises
  `ResultUnknown` (a step) or `Timeout` (anything else), so the kernel's recovery takes over instead of hanging;
- **cleanup** — `close()` asks the child to exit, then terminates / kills it; the child also exits when its stdin
  closes, and a finaliser closes the pipe when the adapter is dropped, so no child outlives its parent;
- **versions** — the descriptor version, the protocol (`formal-lab/subprocess-env@1`, checked at the handshake) and
  the backend (`formal-lab.env.driver-world@…`) are recorded in the session;
- **capabilities** — declared only what is checked: FULL_STATE snapshots whose digest is verified on every restore;
  re-execution after a restore (`env.snapshot_restore`, the kernel then compares the re-executed outcome with the
  recorded one); idempotent steps and lookup by operation id (the child keeps applied ids); one world step per batch
  (`env.batch_step`, start-state / disjoint-writes semantics, as the backend reports at the handshake); the world
  step's own index and the automatic participants' actions (`env.world_step_report`). Persistent
  sessions, observation on request, observation delay and seeded variation are **not** declared.
- **recovery or rebuild by backend capability** — a backend that can load a state (`load_state` at the handshake) is
  restored from the snapshot; one that cannot is rebuilt: a fresh child is reset with the same scenario / run / seed and
  the recorded operations are replayed with their original ids, and the result must have the snapshot's digest, else
  the restore fails.
"""

from __future__ import annotations

import contextlib
import json
import os
import selectors
import subprocess
import sys
import uuid
import weakref
from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    EnvironmentSession,
    EnvironmentSnapshot,
    ModelPackage,
    Observation,
    PluginDescriptor,
    ScenarioManifest,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import (
    InvalidInput,
    NonRetryableFailure,
    ResultUnknown,
    Timeout,
    VersionMismatch,
)

from .world import PROTOCOL

ENV_ID = "formal-lab.example.subprocess-world"
ENV_VERSION = "1.0.0"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "world": {"type": "object", "description": "configuration of the hosted driver world"},
        "timeout_s": {"type": "number", "exclusiveMinimum": 0, "default": 20,
                      "description": "longest wait for one answer of the child"},
        "world_log": {"type": "string", "description": "file the child appends one line per world step to"},
        "automatic": {"type": "array", "items": {"type": "object", "required": ["actor_id", "actions"],
                                                 "properties": {"actor_id": {"type": "string"},
                                                                "actions": {"type": "array"}}},
                      "description": "the world's own automatic participants: they act at the end of every world "
                                     "step and are reported apart from the batch members"},
        "backend_load_state": {"type": "boolean", "default": True,
                               "description": "example knob: false makes the child a backend that cannot load a "
                                              "state, so restores rebuild it by reset + replay"},
    },
    "additionalProperties": False,
}

DESCRIPTOR = PluginDescriptor(
    plugin_id=ENV_ID, version=ENV_VERSION, interface="ENVIRONMENT",
    capabilities=[{"id": "env.driver_generic"}, {"id": caps.ENV_SNAPSHOT}, {"id": caps.ENV_RESTORE},
                  {"id": caps.ENV_SNAPSHOT_RESTORE}, {"id": caps.ENV_QUERY_OPERATION},
                  {"id": caps.ENV_IDEMPOTENT_STEP}, {"id": caps.ENV_MULTI_ACTOR},
                  {"id": caps.ENV_BATCH_STEP, "params": {"semantics": caps.BATCH_START_STATE_DISJOINT_WRITES}},
                  {"id": caps.ENV_WORLD_STEP_REPORT}],
    requires=[{"id": caps.DRIVER_PREDICT, "params": {"of": "driver"}},
              {"id": caps.DRIVER_PROPERTIES, "params": {"of": "driver"}}],
    semantic_profiles=[], config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_example_subprocess.adapter:create",
    ui={"label": "子进程环境（适配范例）", "category": "environment",
        "description": "A world in its own process behind the Environment interface: session / request identity, "
                       "timeouts, cleanup, versions and only verified capabilities"},
    license="Apache-2.0", source="formal-lab-example-subprocess")


def _close_pipe(proc: subprocess.Popen) -> None:
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.wait(timeout=2)
    except Exception:
        proc.kill()


class SubprocessWorldEnvironment:
    descriptor = DESCRIPTOR

    def __init__(self, config: dict[str, Any] | None, services: Any):
        unknown = set(config or {}) - set(CONFIG_SCHEMA["properties"])
        if unknown:
            raise InvalidInput(f"unknown subprocess environment config keys {sorted(unknown)}")
        self.config = {"world": {}, "timeout_s": 20, "backend_load_state": True, **(config or {})}
        self.services = services
        self._proc: subprocess.Popen | None = None
        self._next_id = 0
        self._hello: dict[str, Any] = {}
        self._session_id: str | None = None
        self._sessions: list[dict[str, Any]] = []  # every child this adapter started (restart = new session)
        self._reset_args: dict[str, Any] | None = None
        self._history: list[dict[str, Any]] = []  # applied requests, for a rebuild
        self._created = utcnow()

    # ------------------------------------------------------------------ child process
    def _spawn(self) -> None:
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        self._proc = subprocess.Popen([sys.executable, "-m", "formal_lab_example_subprocess.world"],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      text=True, bufsize=1, env=env)
        weakref.finalize(self, _close_pipe, self._proc)
        self._hello = self._request("hello", {"load_state": bool(self.config["backend_load_state"])})
        if self._hello.get("protocol") != PROTOCOL:
            self._kill()
            raise VersionMismatch(f"child speaks {self._hello.get('protocol')!r}, this adapter {PROTOCOL!r}")
        if self._hello.get("batch_semantics") != caps.BATCH_START_STATE_DISJOINT_WRITES:
            self._kill()
            raise VersionMismatch(f"child batch semantics {self._hello.get('batch_semantics')!r} differ from the "
                                  f"declared {caps.BATCH_START_STATE_DISJOINT_WRITES!r}")
        package: ModelPackage = self.services.pinned_model()
        self._request("init", {"package": package.model_dump(mode="json"), "world": self.config["world"],
                               "options": {"world_log": self.config.get("world_log"),
                                           "automatic": self.config.get("automatic") or [],
                                           "load_state": bool(self.config["backend_load_state"])}})
        self._session_id = f"subproc-{self._hello['pid']}-{uuid.uuid4().hex[:8]}"
        self._sessions.append({"session_id": self._session_id, "pid": self._hello["pid"],
                               "started_at": utcnow().isoformat()})

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _ensure(self) -> None:
        if not self._alive():
            self._spawn()

    def _kill(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait(timeout=5)

    def _request(self, op: str, args: dict[str, Any] | None = None, *, step: bool = False) -> Any:
        assert self._proc is not None and self._proc.stdin is not None and self._proc.stdout is not None
        self._next_id += 1
        rid = self._next_id
        try:
            self._proc.stdin.write(json.dumps({"id": rid, "op": op, "args": args or {}}, default=str) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._kill()
            raise (ResultUnknown if step else NonRetryableFailure)(f"child process gone before {op}: {exc}") from exc
        sel = selectors.DefaultSelector()
        sel.register(self._proc.stdout, selectors.EVENT_READ)
        ready = sel.select(timeout=float(self.config["timeout_s"]))
        sel.close()
        if not ready:
            self._kill()  # a child that does not answer is not waited for: the kernel's recovery takes over
            raise (ResultUnknown if step else Timeout)(f"no answer to {op} within {self.config['timeout_s']}s "
                                                       "(child killed)")
        line = self._proc.stdout.readline()
        if not line:
            self._kill()
            raise (ResultUnknown if step else NonRetryableFailure)(f"child process exited during {op}")
        answer = json.loads(line)
        if answer.get("id") != rid:
            self._kill()
            raise NonRetryableFailure(f"protocol error: answer {answer.get('id')} to request {rid} ({op})")
        if not answer.get("ok"):
            err = answer.get("error") or {}
            raise NonRetryableFailure(f"child {op} failed: {err.get('type')}: {err.get('message')}")
        return answer.get("result")

    # ------------------------------------------------------------------ lifecycle
    def reset(self, scenario: ScenarioManifest, package: ModelPackage, *, run_id: str, seed: int) -> Observation:
        self._ensure()
        self._reset_args = {"scenario": scenario.model_dump(mode="json"), "run_id": run_id, "seed": int(seed)}
        self._history = []
        return Observation.model_validate(self._request("reset", self._reset_args))

    def observe(self, actor_id: str, fresh_paths: list[str] | None = None) -> Observation:
        self._ensure()
        return Observation.model_validate(self._request("observe", {"actor_id": actor_id}))

    def step(self, proposal: ActionProposal, *, operation_id: str) -> ActionOutcome:
        self._ensure()
        args = {"proposal": proposal.model_dump(mode="json"), "operation_id": operation_id}
        res = self._request("step", args, step=True)
        if not res["replayed"]:
            self._history.append({"op": "step", **args})
        return ActionOutcome.model_validate(res["outcome"])

    def step_batch(self, proposals: list[ActionProposal], *, operation_id: str) -> list[ActionOutcome]:
        self._ensure()
        args = {"proposals": [p.model_dump(mode="json") for p in proposals], "operation_id": operation_id}
        res = self._request("step_batch", args, step=True)
        if not res["replayed"]:
            self._history.append({"op": "step_batch", **args})
        return [ActionOutcome.model_validate(o) for o in res["outcomes"]]

    def world_step_report(self) -> dict[str, Any]:
        """The world step just taken (the child's own index) and its automatic participants' actions."""
        self._ensure()
        return self._request("world_step_report")

    def query_operation(self, operation_id: str) -> ActionOutcome | None:
        self._ensure()
        found = self._request("query_operation", {"operation_id": operation_id})
        return ActionOutcome.model_validate(found) if found else None

    def session(self) -> EnvironmentSession:
        return EnvironmentSession(
            session_id=self._session_id or "subproc-not-started", environment=self.descriptor.ref(),
            backend="PURE_DATA", status="READY" if self._alive() else "CLOSED",
            capabilities=[c.id for c in self.descriptor.capabilities],
            recovery_modes=["SNAPSHOT" if self._hello.get("load_state", True) else "RESEED"],
            endpoint=f"pid:{self._hello.get('pid')}", project_label="formal-lab",
            owner={"run_id": (self._reset_args or {}).get("run_id", "")}, revision=0, created_at=self._created,
            updated_at=utcnow(), health={"protocol": self._hello.get("protocol"),
                                         "backend": self._hello.get("backend"), "adapter": f"{ENV_ID}@{ENV_VERSION}",
                                         "sessions": len(self._sessions)})

    def close(self) -> None:
        if self._alive():
            with contextlib.suppress(Exception):  # a child that cannot even say goodbye is terminated below
                self._request("close")
            assert self._proc is not None
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
        self._kill()

    # ------------------------------------------------------------------ persistence
    def snapshot(self) -> EnvironmentSnapshot:
        self._ensure()
        inner = EnvironmentSnapshot.model_validate(self._request("snapshot"))
        data = {"inner": inner.model_dump(mode="json"), "history": self._history, "reset": self._reset_args}
        return EnvironmentSnapshot(environment=self.descriptor.ref(), step=inner.step,
                                   state_revision=inner.state_revision, digest=digest_of(data), data=data)

    def restore(self, snapshot: EnvironmentSnapshot) -> None:
        if snapshot.environment.plugin_id != ENV_ID:
            raise InvalidInput(f"snapshot belongs to {snapshot.environment.plugin_id}")
        if digest_of(snapshot.data) != snapshot.digest:
            raise InvalidInput("snapshot digest mismatch")
        inner = EnvironmentSnapshot.model_validate(snapshot.data["inner"])
        self._ensure()
        if self._hello.get("load_state", True):
            self._request("restore", {"snapshot": inner.model_dump(mode="json")})
        else:
            self._rebuild(snapshot.data, inner)
        self._reset_args = snapshot.data["reset"]
        self._history = list(snapshot.data["history"])

    def _rebuild(self, data: dict[str, Any], inner: EnvironmentSnapshot) -> None:
        """A backend that cannot load a state: a fresh child, reset as recorded, the recorded operations replayed with
        their original ids — and the result must be the snapshot's state."""
        self._kill()
        self._spawn()
        self._request("reset", data["reset"])
        for h in data["history"]:
            self._request(h["op"], {**{k: v for k, v in h.items() if k != "op"}, "rebuild": True}, step=True)
        got = EnvironmentSnapshot.model_validate(self._request("snapshot"))
        if got.digest != inner.digest:
            raise NonRetryableFailure("rebuild diverged: reset + replay of the recorded operations does not "
                                      "reproduce the snapshot")

    # ------------------------------------------------------------------ evaluator access
    def truth_state(self) -> dict[str, Any]:
        self._ensure()
        return self._request("truth_state")

    def truth_properties(self) -> dict[str, bool]:
        self._ensure()
        return self._request("truth_properties")

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else None

    @property
    def sessions(self) -> list[dict[str, Any]]:
        return list(self._sessions)


def create(config: dict[str, Any] | None, services: Any = None) -> SubprocessWorldEnvironment:
    return SubprocessWorldEnvironment(config, services)
