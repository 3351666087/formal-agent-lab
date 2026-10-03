"""CAGE Challenge 4 as a platform environment (phase 4B, B2): `formal-lab.env.cage4`.

A CybORG 4.0 Scenario4 episode runs in a child process inside the isolated `fal-cage` venv (`_worker.py serve`,
protocol formal-lab/cage4-session@1); this adapter is the platform side, built on the subprocess-environment
pattern of phase 4A (session identity, request ids echoed, timeouts that kill the child, cleanup, versions).

Who acts:
- **platform-controlled** blue agents — the run's participants (actor id = CybORG agent name, `blue_agent_0`…); every
  JOINT_BATCH round collects their proposals and sends them in **one** `parallel_step`, i.e. exactly one native world
  step. A member that proposes nothing (absent, timed out, rejected before the send) is played that step by the
  native blue class named in `blue_native` (default SleepAgent), and the record says so;
- **native automatic** participants — CybORG's own red agents (`red`, an official FSM variant) and the green
  (normal business) agents act inside the same world step; they are reported per world step through
  `world_step_report` (red per agent, green aggregated), apart from the batch members.

A blue action CybORG does not start because the agent's previous action is still in progress (actions take 1–5
ticks) comes back REJECTED with AGENT_BUSY — the world step still happened. An action outside the agent's own action
space is rejected here and never sent.

Recovery is a **rebuild**: CybORG cannot load a state, so a snapshot is the reset arguments plus the committed world
steps; `restore` starts a fresh child, resets it with the same seed and replays the steps with their original ids,
and accepts the result only if the state + RNG digest equals the snapshot's (else the restore fails and nothing is
re-sent blindly). A worker lost *between* world steps is rebuilt the same way from the adapter's own committed log
and must reach the last committed digest; a worker lost *during* a step raises ResultUnknown — the kernel then
restores the pre-step snapshot (a verified rebuild) and executes that world step once on it. The referee view
(`truth_state`: red footholds, green results) is never part of an observation.
"""

from __future__ import annotations

import contextlib
import json
import os
import selectors
import subprocess
import uuid
import weakref
from pathlib import Path
from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
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

from . import bridge
from .model import HOSTED, NATIVE, PROFILE

ENV_ID = "formal-lab.env.cage4"
ENV_VERSION = "1.0.0"
PROTOCOL = "formal-lab/cage4-session@1"
BATCH_SEMANTICS = "cage4.parallel_step"  # CybORG's own: submitted actions resolved in its priority order
RED = ("FiniteStateRedAgent", "DiscoveryFSRed", "VerboseFSRed", "RandomSelectRedAgent")
BLUE_NATIVE = ("SleepAgent", "cc4BlueRandomAgent")  # MonitorAgent: a CAGE-2-era class Scenario4 cannot build

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {"type": "integer", "minimum": 1, "default": 30,
                  "description": "native episode length in world steps (the official evaluation uses 500)"},
        "red": {"type": "string", "enum": list(RED), "default": "FiniteStateRedAgent",
                "description": "CybORG's red agent class (an official variant)"},
        "blue_native": {"type": "string", "enum": list(BLUE_NATIVE), "default": "SleepAgent",
                        "description": "native blue class acting for a blue agent the platform does not control or "
                                       "that submits nothing in a world step"},
        "controlled": {"type": "array", "items": {"type": "string", "pattern": "^blue_agent_[0-4]$"},
                       "description": "platform-controlled blue agents (default: the scenario's participants)"},
        "timeout_s": {"type": "number", "exclusiveMinimum": 0, "default": 120},
        "world_log": {"type": "string", "description": "file to append one JSON line per committed world step"},
    },
    "additionalProperties": False,
}

DESCRIPTOR = PluginDescriptor(
    plugin_id=ENV_ID, version=ENV_VERSION, interface="ENVIRONMENT",
    capabilities=[{"id": f"profile.{PROFILE}"}, {"id": caps.ENV_SNAPSHOT}, {"id": caps.ENV_RESTORE},
                  {"id": caps.ENV_SNAPSHOT_RESTORE},
                  {"id": caps.ENV_QUERY_OPERATION}, {"id": caps.ENV_IDEMPOTENT_STEP}, {"id": caps.ENV_MULTI_ACTOR},
                  {"id": caps.ENV_BATCH_STEP, "params": {"semantics": BATCH_SEMANTICS}},
                  {"id": caps.ENV_WORLD_STEP_REPORT}],
    requires=[{"id": caps.DRIVER_CANDIDATES, "params": {"of": "driver"}}],
    semantic_profiles=[PROFILE], config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_env_cage.adapter:create",
    ui={"label": "CAGE 4（CybORG Scenario4）", "category": "environment",
        "description": "CybORG 4.0 in an isolated venv: platform-controlled blue agents, native red / green; one "
                       "joint batch = one native world step; rebuild-verified recovery"},
    license="Apache-2.0", source="formal-lab-env-cage")


def _close_pipe(proc: subprocess.Popen) -> None:
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def native_spec(action: Any) -> dict[str, Any]:
    spec = {"name": NATIVE[action.action_type]}
    if action.action_type in HOSTED:
        spec["hostname"] = action.params.get("host")
    return spec


class Cage4Environment:
    descriptor = DESCRIPTOR

    def __init__(self, config: dict[str, Any] | None, services: Any = None):
        unknown = set(config or {}) - set(CONFIG_SCHEMA["properties"])
        if unknown:
            raise InvalidInput(f"unknown CAGE environment config keys {sorted(unknown)}")
        self.config = {"steps": 30, "red": "FiniteStateRedAgent", "blue_native": "SleepAgent", "timeout_s": 120,
                       **(config or {})}
        self.services = services
        self._proc: subprocess.Popen | None = None
        self._next_id = 0
        self._hello: dict[str, Any] = {}
        self._session_id: str | None = None
        self._sessions: list[dict[str, Any]] = []
        self._reset_args: dict[str, Any] | None = None
        self._run_id = ""
        self._history: list[dict[str, Any]] = []  # committed world steps: the rebuild log
        self._report: dict[str, Any] | None = None
        self._outcomes: dict[str, dict[str, Any]] = {}  # operation id (batch and member) -> outcome(s), for queries
        self._last_digest: str | None = None  # state + RNG digest after the last committed world step
        self._rebuilds: list[dict[str, Any]] = []  # automatic rebuilds after a lost worker
        self._created = utcnow()

    # ------------------------------------------------------------------ child process
    def _spawn(self) -> None:
        py = bridge.locate()
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONWARNINGS": "ignore"}
        self._proc = subprocess.Popen([str(py), str(bridge.WORKER), "serve"], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                      env=env)
        weakref.finalize(self, _close_pipe, self._proc)
        self._hello = self._request("hello")
        if self._hello.get("protocol") != PROTOCOL:
            self._kill()
            raise VersionMismatch(f"CAGE worker speaks {self._hello.get('protocol')!r}, adapter {PROTOCOL!r}")
        self._session_id = f"cage4-{self._hello['pid']}-{uuid.uuid4().hex[:8]}"
        self._sessions.append({"session_id": self._session_id, "pid": self._hello["pid"],
                               "started_at": utcnow().isoformat()})

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _kill(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait(timeout=10)

    def _request(self, op: str, args: dict[str, Any] | None = None, *, step: bool = False) -> Any:
        assert self._proc is not None and self._proc.stdin is not None and self._proc.stdout is not None
        self._next_id += 1
        rid = self._next_id
        try:
            self._proc.stdin.write(json.dumps({"id": rid, "op": op, "args": args or {}}) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._kill()
            raise (ResultUnknown if step else NonRetryableFailure)(f"CAGE worker gone before {op}: {exc}") from exc
        sel = selectors.DefaultSelector()
        sel.register(self._proc.stdout, selectors.EVENT_READ)
        ready = sel.select(timeout=float(self.config["timeout_s"]))
        sel.close()
        if not ready:
            self._kill()
            raise (ResultUnknown if step else Timeout)(f"no answer to {op} within {self.config['timeout_s']}s "
                                                       "(worker killed)")
        line = self._proc.stdout.readline()
        if not line:
            self._kill()
            raise (ResultUnknown if step else NonRetryableFailure)(f"CAGE worker exited during {op}")
        answer = json.loads(line)
        if answer.get("id") != rid:
            self._kill()
            raise NonRetryableFailure(f"protocol error: answer {answer.get('id')} to request {rid} ({op})")
        if not answer.get("ok"):
            err = answer.get("error") or {}
            raise NonRetryableFailure(f"CAGE worker {op} failed: {err.get('type')}: {err.get('message')}")
        return answer.get("result")

    def _ensure(self) -> None:
        if not self._alive():
            if self._reset_args is not None:  # a lost child is rebuilt from the committed log, never replaced by a
                self._rebuild_from_log()  # fresh episode
            else:
                self._spawn()

    def _rebuild_from_log(self) -> None:
        """The worker died between world steps: a new worker, the same reset, the committed steps replayed — and the
        state + RNG digest must equal the last committed one, else the run stops here (nothing re-sent blindly)."""
        self._kill()
        self._spawn()
        self._start = self._request("reset", self._reset_args)
        for h in self._history:
            self._request("step", h, step=True)
        got = self._request("digest")
        if self._last_digest is not None and got != self._last_digest:
            raise NonRetryableFailure(f"rebuild after a lost worker diverged: digest {got[:12]} after "
                                      f"{len(self._history)} world step(s), last committed {self._last_digest[:12]}")
        self._rebuilds.append({"world_steps": len(self._history), "digest": got, "session_id": self._session_id})

    # ------------------------------------------------------------------ lifecycle
    def reset(self, scenario: ScenarioManifest, package: ModelPackage, *, run_id: str, seed: int) -> Observation:
        if not self._alive():
            self._spawn()
        controlled = self.config.get("controlled") or [p.actor_id for p in scenario.participants]
        bad = [a for a in controlled if not a.startswith("blue_agent_")]
        if bad:
            raise InvalidInput(f"participants must be CybORG blue agents (blue_agent_0..4): {bad}")
        self._run_id = run_id
        self._reset_args = {"seed": int(seed), "steps": int(self.config["steps"]), "red": self.config["red"],
                            "blue_native": self.config["blue_native"], "controlled": sorted(controlled)}
        self._history, self._report = [], None
        self._start = self._request("reset", self._reset_args)
        self._last_digest = self._start.get("digest")
        return self.observe(sorted(controlled)[0])

    def observe(self, actor_id: str, fresh_paths: list[str] | None = None) -> Observation:
        self._ensure()
        o = self._request("observe", {"agent": actor_id})
        n = int(o["world_step"])
        allowed, alerts = set(o["allowed_hosts"]), o.get("alert_kinds") or {}
        hosts = self._hosts()
        facts = [Fact(path=f"allowed[{h}]", value=h in allowed, observed_at_step=n) for h in hosts]
        facts += [Fact(path=f"alert[{h}]", value=h in alerts, observed_at_step=n) for h in hosts]
        facts += [Fact(path=f"alert_kind[{h}]", value=alerts.get(h, "none"), observed_at_step=n) for h in hosts]
        facts += [Fact(path="busy", value=bool(o["busy"]), observed_at_step=n),
                  Fact(path="last_success", value=str(o["success"]), observed_at_step=n),
                  Fact(path="world_step", value=n, observed_at_step=n),
                  Fact(path="phase", value=int(o["phase"]), observed_at_step=n),
                  Fact(path="done", value=bool(o["done"]), observed_at_step=n)]
        return Observation(run_id=self._run_id, actor_id=actor_id, step=n, state_revision=n, facts=facts,
                           evidence=[EvidenceRef(kind="snapshot", id=f"{self._run_id}:cage4@{n}",
                                                 note=f"{actor_id}'s own CybORG observation at world step {n}")])

    def _hosts(self) -> list[str]:
        return list(self.services.pinned_model().payload.data["hosts"])

    def current_revision(self) -> int:
        self._ensure()
        return int(self._request("truth")["world_step"])

    # ------------------------------------------------------------------ the world step
    def step(self, proposal: ActionProposal, *, operation_id: str) -> ActionOutcome:
        return self.step_batch([proposal], operation_id=operation_id)[0]

    def step_batch(self, proposals: list[ActionProposal], *, operation_id: str) -> list[ActionOutcome]:
        self._ensure()
        controlled = set((self._reset_args or {}).get("controlled") or [])
        specs, refused = {}, {}
        for p in proposals:
            a = p.action
            if p.actor_id not in controlled:
                refused[p.actor_id] = f"NOT_CONTROLLED: {p.actor_id} is not a platform-controlled blue agent"
            elif a.action_type not in NATIVE:
                refused[p.actor_id] = f"INVALID_ACTION: {a.action_type!r} is not a declared blue action"
            elif a.action_type in HOSTED and a.params.get("host") not in \
                    self._request("observe", {"agent": p.actor_id})["allowed_hosts"]:
                refused[p.actor_id] = (f"INVALID_ACTION: host {a.params.get('host')!r} is not in {p.actor_id}'s "
                                       "action space (not sent)")
            else:
                specs[p.actor_id] = native_spec(a)
        if f"batch:{operation_id}" in self._outcomes:  # the same batch again: answered, never applied twice
            return [ActionOutcome.model_validate(o) for o in self._outcomes[f"batch:{operation_id}"]]
        before = int(self._request("truth")["world_step"])
        answer = self._request("step", {"operation_id": operation_id, "actions": specs}, step=True)
        rec = answer["record"]
        self._last_digest = answer.get("digest")
        if not answer.get("replayed"):
            self._history.append({"operation_id": operation_id, "actions": specs})
            self._log(operation_id, {**rec, "digest": answer.get("digest")})
        self._report = {"world_step": int(rec["world_step"]), "operation_id": operation_id,
                        "automatic": self._automatic(rec)}
        after = int(rec["world_step"])
        outcomes = []
        for p in proposals:
            if p.actor_id in refused:
                outcomes.append(self._outcome(p, operation_id, before, after, OutcomeStatus.REJECTED, False,
                                              {"reason": refused[p.actor_id], "world_step": after}))
                continue
            native = rec["blue"][p.actor_id]
            # what the member may know: its own action as CybORG ran it and the blue team's reward for this world
            # step (the feedback CybORG gives blue). Red footholds and green results are referee data: they stay in
            # truth_state (the evaluator's input), never in an outcome a planner sees
            result = {"native": native, "world_step": after, "batch": operation_id,
                      "blue_reward": rec["rewards"].get("Blue")}
            if native.get("started"):
                outcomes.append(self._outcome(p, operation_id, before, after, OutcomeStatus.APPLIED, True, result))
            else:
                result["reason"] = ("AGENT_BUSY: CybORG did not start this action — the agent's previous action was "
                                    "still in progress; the world step happened")
                outcomes.append(self._outcome(p, operation_id, before, after, OutcomeStatus.REJECTED, False, result))
        self._outcomes[f"batch:{operation_id}"] = [o.model_dump(mode="json") for o in outcomes]
        for o in outcomes:
            self._outcomes[o.operation_id] = o.model_dump(mode="json")
        return outcomes

    def _outcome(self, p: ActionProposal, op: str, before: int, after: int, status: OutcomeStatus, applied: bool,
                 result: dict[str, Any]) -> ActionOutcome:
        return ActionOutcome(operation_id=f"{op}:{p.actor_id}", run_id=self._run_id, step_id=p.step_id,
                             proposal_id=p.proposal_id, action=p.action, status=status, effect_applied=applied,
                             revision_before=before, revision_after=after, result=result)

    @staticmethod
    def _automatic(rec: dict[str, Any]) -> list[dict[str, Any]]:
        out = [{"actor_id": a, "action": {"action_type": "native", "params": {"cyborg": text}}, "status": "APPLIED",
                "note": "CybORG red agent (native)"} for a, text in sorted(rec["red"].items())]
        if rec.get("green"):
            counts = {k.replace(":", "_").lower(): int(v) for k, v in rec["green"].items()}
            out.append({"actor_id": "green_agents", "action": {"action_type": "native", "params": counts},
                        "status": "APPLIED", "note": "CybORG green agents (normal business), aggregated: "
                                                     "<work|access>_<success> -> count"})
        for a, b in sorted(rec["blue"].items()):
            if not b.get("controlled") or b.get("submitted") is None:
                out.append({"actor_id": a, "action": {"action_type": "native", "params": {"cyborg": b["executed"]}},
                            "status": "APPLIED", "note": "native blue class (not submitted by the platform this "
                                                         "world step)"})
        return out

    def world_step_report(self) -> dict[str, Any]:
        return self._report or {"world_step": 0, "automatic": []}

    def query_operation(self, operation_id: str) -> ActionOutcome | None:
        """What happened to a member operation (`<batch id>:<actor>`) — kept here and in every snapshot."""
        found = self._outcomes.get(operation_id)
        return ActionOutcome.model_validate(found) if isinstance(found, dict) else None

    def _log(self, operation_id: str, rec: dict[str, Any]) -> None:
        path = self.config.get("world_log")
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as fh:
                fh.write(json.dumps({"operation_id": operation_id, **rec}, default=str) + "\n")

    # ------------------------------------------------------------------ session / persistence
    def session(self) -> EnvironmentSession:
        return EnvironmentSession(
            session_id=self._session_id or "cage4-not-started", environment=self.descriptor.ref(),
            backend="PURE_DATA", status="READY" if self._alive() else "CLOSED",
            capabilities=[c.id for c in self.descriptor.capabilities], recovery_modes=["RESEED"],
            endpoint=f"pid:{self._hello.get('pid')}", project_label="formal-lab",
            owner={"run_id": self._run_id}, revision=len(self._history), created_at=self._created,
            updated_at=utcnow(),
            health={"protocol": self._hello.get("protocol"), "cyborg": self._hello.get("cyborg_version"),
                    "scenario": self._hello.get("scenario"), "adapter": f"{ENV_ID}@{ENV_VERSION}",
                    "batch_semantics": BATCH_SEMANTICS, "sessions": len(self._sessions),
                    "rebuilds": len(self._rebuilds)})

    def snapshot(self) -> EnvironmentSnapshot:
        self._ensure()
        digest = self._request("digest")
        n = len(self._history)
        data = {"reset": self._reset_args, "history": list(self._history), "state_digest": digest,
                "run_id": self._run_id, "outcomes": dict(self._outcomes)}
        return EnvironmentSnapshot(environment=self.descriptor.ref(), step=n, state_revision=n,
                                   digest=digest_of(data), data=data, session_id=self._session_id)

    def restore(self, snapshot: EnvironmentSnapshot) -> None:
        """Rebuild: fresh worker, same reset, the committed world steps replayed with their ids; the state + RNG
        digest must equal the snapshot's, else the restore fails (no blind re-execution)."""
        if snapshot.environment.plugin_id != ENV_ID:
            raise InvalidInput(f"snapshot belongs to {snapshot.environment.plugin_id}")
        if digest_of(snapshot.data) != snapshot.digest:
            raise InvalidInput("snapshot digest mismatch")
        data = snapshot.data
        if self._alive() and self._history == data["history"] and self._reset_args == data["reset"] \
                and self._request("digest") == data["state_digest"]:
            self._outcomes = dict(data.get("outcomes") or {})  # the live worker already is that state (same
            self._report = None  # committed steps, same state + RNG digest): nothing to rebuild
            self._last_digest = data["state_digest"]
            return
        self._kill()
        self._spawn()
        self._run_id = data.get("run_id", self._run_id)
        self._reset_args = data["reset"]
        self._start = self._request("reset", self._reset_args)
        for h in data["history"]:
            self._request("step", h, step=True)
        got = self._request("digest")
        if got != data["state_digest"]:
            raise NonRetryableFailure(f"rebuild diverged: replaying {len(data['history'])} world step(s) gives "
                                      f"digest {got[:12]}, the snapshot has {data['state_digest'][:12]}")
        self._history = list(data["history"])
        self._outcomes = dict(data.get("outcomes") or {})
        self._last_digest = got
        self._report = None

    def rebuild_check(self) -> dict[str, Any]:
        """For evidence: rebuild in a second worker from the current log and compare digests (state and RNG)."""
        snap = self.snapshot()
        other = Cage4Environment(self.config, self.services)
        try:
            other.restore(snap)
            return {"world_steps": len(snap.data["history"]), "digest": snap.data["state_digest"], "equal": True}
        except NonRetryableFailure as exc:
            return {"world_steps": len(snap.data["history"]), "digest": snap.data["state_digest"], "equal": False,
                    "detail": str(exc)}
        finally:
            other.close()

    # ------------------------------------------------------------------ referee / evaluator access
    def truth_state(self) -> dict[str, Any]:
        self._ensure()
        t = self._request("truth")
        return {"world_step": t["world_step"], "done": t["done"], "red_footholds": len(t["red_footholds"]),
                "green_totals": json.dumps(t["green_totals"], sort_keys=True),
                "referee_timeline": json.dumps(t["timeline"], sort_keys=True)}

    def truth_detail(self) -> dict[str, Any]:
        self._ensure()
        return self._request("truth")

    def truth_properties(self) -> dict[str, bool]:
        self._ensure()
        return {"episode_complete": bool(self._request("truth")["done"])}

    def committed_log(self) -> list[dict[str, Any]]:
        return list(self._history)

    def close(self) -> None:
        if self._alive():
            with contextlib.suppress(Exception):
                self._request("close")
            assert self._proc is not None
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
        self._kill()

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else None

    @property
    def sessions(self) -> list[dict[str, Any]]:
        return list(self._sessions)

    @property
    def rebuilds(self) -> list[dict[str, Any]]:
        return list(self._rebuilds)


def create(config: dict[str, Any] | None, services: Any = None) -> Cage4Environment:
    return Cage4Environment(config, services)
