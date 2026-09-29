"""Driver world: a pure-data simulator for any semantic profile, driven by the model's semantic driver.

The truth state is the driver's state space; transitions are the driver's predictions applied to the truth
(`LoadedModel.predict`), properties are the driver's (`LoadedModel.properties`). The environment therefore needs no
knowledge of the profile — it proves that environments, like the run kernel, can work through the driver only
(P2-012). IR models have the richer `formal-lab.env.ir-world` (truth-constant overrides); this one serves every
profile that has a driver.

Configuration (validated against CONFIG_SCHEMA):
- initial_overrides: {path: value} scenario changes to the model's initial state.
- seeded_variation: [{prefix, delta_min, delta_max}] per-seed integer perturbation of int locations whose path
  starts with `prefix` (the actor observes the result).
- observation: {delay_steps: {prefix: k}, hidden: [prefix], per_actor: {actor: {delay_steps, hidden}},
  on_request: bool} — prefixes match the location name before `[` or the full path.

Several participants: every actor sees the same truth through its own view; the world revision counts applied
actions; the scenario's conflict policy decides about proposals made on an older revision (REVALIDATE: apply if
still applicable; REJECT_STALE: reject when a location the action reads — `LoadedModel.reads` when the driver
offers it, otherwise any written location — changed since that revision).

JOINT_BATCH rounds (phase 3A, `step_batch`, semantics START_STATE_DISJOINT_WRITES): every proposal is evaluated on
the batch's start state; the writes of applicable proposals are merged; a proposal writing a location an earlier
proposal of the same batch already wrote is rejected as a conflict. The world revision and the environment step
advance once per batch (the revision only if something was applied).
"""

from __future__ import annotations

import copy
import random
from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    ConflictInfo,
    EnvironmentSnapshot,
    EvidenceRef,
    Fact,
    ModelPackage,
    Observation,
    OutcomeStatus,
    PluginDescriptor,
    ScenarioManifest,
    UnknownItem,
    digest_of,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import Conflict, InvalidInput, NonRetryableFailure, Unsupported

ENV_ID = "formal-lab.env.driver-world"
ENV_VERSION = "1.0.0"
MAX_OP_MEMORY = 64
DRIVER_GENERIC = "env.driver_generic"  # simulates any profile through its semantic driver

_VIEW = {
    "type": "object",
    "properties": {
        "delay_steps": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
        "hidden": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}
CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "initial_overrides": {"type": "object", "additionalProperties": {"type": ["boolean", "integer", "string"]}},
        "seeded_variation": {"type": "array", "items": {
            "type": "object", "properties": {"prefix": {"type": "string"}, "delta_min": {"type": "integer"},
                                             "delta_max": {"type": "integer"}},
            "required": ["prefix", "delta_min", "delta_max"], "additionalProperties": False}},
        "observation": {
            "type": "object",
            "properties": {
                "delay_steps": _VIEW["properties"]["delay_steps"],
                "hidden": _VIEW["properties"]["hidden"],
                "per_actor": {"type": "object", "additionalProperties": _VIEW},
                "on_request": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

DESCRIPTOR = PluginDescriptor(
    plugin_id=ENV_ID,
    version=ENV_VERSION,
    interface="ENVIRONMENT",
    capabilities=[{"id": DRIVER_GENERIC}, {"id": caps.ENV_PURE_REPLAYABLE}, {"id": caps.ENV_SNAPSHOT},
                  {"id": caps.ENV_RESTORE}, {"id": caps.ENV_IDEMPOTENT_STEP}, {"id": caps.ENV_MULTI_ACTOR},
                  {"id": caps.ENV_OBSERVE_ON_REQUEST}, {"id": caps.ENV_OBSERVATION_DELAY},
                  {"id": caps.ENV_SEEDED_VARIATION},
                  {"id": caps.ENV_BATCH_STEP, "params": {"semantics": caps.BATCH_START_STATE_DISJOINT_WRITES}}],
    requires=[{"id": caps.DRIVER_PREDICT, "params": {"of": "driver"}},
              {"id": caps.DRIVER_PROPERTIES, "params": {"of": "driver"}}],
    semantic_profiles=[],
    config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_env.driver_world:create",
    ui={"label": "Driver world simulator", "category": "environment",
        "description": "Pure-data simulator for any semantic profile: the model's semantic driver is the world"},
    license="Apache-2.0",
    source="formal-lab-neutral-env",
)


def _family(path: str) -> str:
    return path.split("[", 1)[0]


def _matches(path: str, prefixes: dict[str, Any] | set[str] | list[str]) -> str | None:
    for p in prefixes:
        if path == p or _family(path) == p:
            return p
    return None


class DriverWorldEnvironment:
    descriptor = DESCRIPTOR

    def __init__(self, config: dict[str, Any] | None, services: Any):
        self.config = copy.deepcopy(config or {})
        self.services = services
        self._loaded = None
        self._data: dict[str, Any] | None = None

    @property
    def loaded(self):
        if self._loaded is None:
            self._loaded = self.services.loaded_model()
        return self._loaded

    # ------------------------------------------------------------------ lifecycle
    def reset(self, scenario: ScenarioManifest, package: ModelPackage, *, run_id: str, seed: int) -> Observation:
        state = dict(self.loaded.initial_state())
        for path, value in self.config.get("initial_overrides", {}).items():
            if path not in state:
                raise InvalidInput(f"initial override {path!r} is not a state location")
            state[path] = value
        rng = random.Random(seed)
        for rule in self.config.get("seeded_variation", []):
            for path in sorted(state):
                if _matches(path, [rule["prefix"]]) and isinstance(state[path], int) and not isinstance(state[path],
                                                                                                           bool):
                    state[path] = max(0, state[path] + rng.randint(rule["delta_min"], rule["delta_max"]))
        self._data = {"run_id": run_id, "seed": seed, "step": 0, "revision": 0, "state": state, "history": [state],
                      "applied_ops": {}, "closed": False, "writes": {},
                      "conflict_policy": scenario.turns.conflict_policy.value,
                      "package": {"package_id": package.package_id, "version": package.version,
                                  "digest": package.digest.value}}
        return self.observe(scenario.participants[0].actor_id)

    def close(self) -> None:
        if self._data is not None:
            self._data["closed"] = True

    def _require(self) -> dict[str, Any]:
        if self._data is None:
            raise NonRetryableFailure("environment used before reset/restore")
        if self._data["closed"]:
            raise Conflict("environment is closed")
        return self._data

    # ------------------------------------------------------------------ observation
    def _view(self, actor_id: str) -> tuple[dict[str, int], set[str]]:
        obs = self.config.get("observation", {})
        own = obs.get("per_actor", {}).get(actor_id, {})
        return {**obs.get("delay_steps", {}), **own.get("delay_steps", {})}, \
            set(obs.get("hidden", [])) | set(own.get("hidden", []))

    def observe(self, actor_id: str, fresh_paths: list[str] | None = None) -> Observation:
        data = self._require()
        step, history = data["step"], data["history"]
        delays, hidden = self._view(actor_id)
        fresh = set(fresh_paths or [])
        facts, unknowns = [], []
        for path in sorted(data["state"]):
            if path in fresh:
                facts.append(Fact(path=path, value=data["state"][path], observed_at_step=step))
                continue
            if _matches(path, hidden):
                unknowns.append(UnknownItem(path=path, reason="NOT_OBSERVABLE"))
                continue
            key = _matches(path, delays)
            k = delays[key] if key else 0
            seen = max(0, step - k)
            value = history[len(history) - 1 - (step - seen)][path]
            fact = Fact(path=path, value=value, observed_at_step=seen, source="DELAYED" if seen < step else "DIRECT")
            if seen < step:
                unknowns.append(UnknownItem(path=path, reason="OBSERVATION_DELAY", last_known=fact))
            else:
                facts.append(fact)
        return Observation(run_id=data["run_id"], actor_id=actor_id, step=step, state_revision=data["revision"],
                           facts=facts, unknowns=unknowns, requested_paths=sorted(fresh),
                           evidence=[EvidenceRef(kind="snapshot", id=f"{data['run_id']}:env@{step}",
                                                 note=f"truth revision {data['revision']}")])

    def observe_paths(self, actor_id: str, paths: list[str]) -> Observation:
        if self.config.get("observation", {}).get("on_request", True) is False:
            raise Unsupported("observations on request are disabled for this scenario")
        unknown = [p for p in paths if p not in self._require()["state"]]
        if unknown:
            raise InvalidInput(f"not state locations: {unknown}")
        return self.observe(actor_id, fresh_paths=paths)

    # ------------------------------------------------------------------ transition
    def _conflict(self, proposal: ActionProposal, current: int) -> ConflictInfo | None:
        data = self._require()
        if proposal.based_on_revision >= current:
            return None
        reads = self.loaded.reads(proposal.action) if hasattr(self.loaded, "reads") else None
        changed = sorted(p for p, (rev, _) in data["writes"].items()
                         if rev > proposal.based_on_revision and (reads is None or p in reads))
        if not changed:
            return None
        writers = sorted({data["writes"][p][1] for p in changed if data["writes"][p][1]})
        return ConflictInfo(policy=data["conflict_policy"], based_on_revision=proposal.based_on_revision,
                            current_revision=current, changed_paths=changed,
                            reason=f"observed at revision {proposal.based_on_revision}, world at {current}; "
                                   f"{len(changed)} location(s) it depends on changed since"
                                   + (f" (written by {', '.join(writers)})" if writers else ""))

    def step(self, proposal: ActionProposal, *, operation_id: str) -> ActionOutcome:
        data = self._require()
        if operation_id in data["applied_ops"]:
            return ActionOutcome.model_validate(data["applied_ops"][operation_id])
        before = data["revision"]
        conflict = self._conflict(proposal, before)
        pred = self.loaded.predict(data["state"], proposal.action)
        common = dict(operation_id=operation_id, run_id=data["run_id"], step_id=proposal.step_id,
                      proposal_id=proposal.proposal_id, action=proposal.action, revision_before=before)
        if conflict is not None and conflict.policy.value == "REJECT_STALE":
            outcome = ActionOutcome(**common, status=OutcomeStatus.REJECTED, effect_applied=False,
                                    revision_after=before, conflict=conflict,
                                    result={"reason": f"STALE_REVISION: {conflict.reason}",
                                            "properties": self.truth_properties()})
        elif pred.applicable and pred.next_state is not None:
            data["state"] = pred.next_state
            data["revision"] = before + 1
            for path in pred.written_paths:
                data["writes"][path] = [before + 1, proposal.actor_id]
            outcome = ActionOutcome(**common, status=OutcomeStatus.APPLIED, effect_applied=True,
                                    revision_after=before + 1,
                                    result={"written_paths": pred.written_paths, "properties": self.truth_properties()})
        else:
            outcome = ActionOutcome(**common, status=OutcomeStatus.REJECTED, effect_applied=False,
                                    revision_after=before,
                                    conflict=conflict.model_copy(update={
                                        "reason": f"precondition no longer holds: {pred.reason}; {conflict.reason}"})
                                    if conflict else None,
                                    result={"reason": pred.reason, "properties": self.truth_properties()})
        self._advance(data["state"])
        data["applied_ops"][operation_id] = outcome.model_dump(mode="json")
        if len(data["applied_ops"]) > MAX_OP_MEMORY:
            data["applied_ops"].pop(next(iter(data["applied_ops"])))
        return outcome

    def step_batch(self, proposals: list[ActionProposal], *, operation_id: str) -> list[ActionOutcome]:
        data = self._require()
        key = f"batch:{operation_id}"
        if key in data["applied_ops"]:
            return [ActionOutcome.model_validate(o) for o in data["applied_ops"][key]]
        before, start = data["revision"], data["state"]
        merged = dict(start)
        written_by: dict[str, str] = {}
        results: list[tuple[ActionProposal, str, list[str], ConflictInfo | None, str | None]] = []
        for proposal in proposals:
            conflict = self._conflict(proposal, before)
            pred = self.loaded.predict(start, proposal.action)
            if conflict is not None and conflict.policy.value == "REJECT_STALE":
                results.append((proposal, "REJECTED", [], conflict, f"STALE_REVISION: {conflict.reason}"))
                continue
            if not (pred.applicable and pred.next_state is not None):
                results.append((proposal, "REJECTED", [], None, pred.reason))
                continue
            writes = sorted(set(pred.written_paths) | {p for p, v in pred.next_state.items() if start.get(p) != v})
            clash = sorted(p for p in writes if p in written_by)
            if clash:
                by = sorted({written_by[p] for p in clash})
                why = (f"batch write conflict: {', '.join(clash)} already written by {', '.join(by)} in this batch "
                       f"(semantics {caps.BATCH_START_STATE_DISJOINT_WRITES})")
                info = ConflictInfo(policy=data["conflict_policy"], based_on_revision=proposal.based_on_revision,
                                    current_revision=before, changed_paths=clash, reason=why)
                results.append((proposal, "REJECTED", [], info, why))
                continue
            for path in writes:
                merged[path] = pred.next_state[path]
                written_by[path] = proposal.actor_id
            results.append((proposal, "APPLIED", writes, None, None))
        progressed = bool(written_by)
        after = before + 1 if progressed else before
        data["state"] = merged
        data["revision"] = after
        for path, actor in written_by.items():
            data["writes"][path] = [after, actor]
        props = self.loaded.properties(merged)
        outcomes = []
        for proposal, status, writes, conflict, reason in results:
            common = dict(operation_id=f"{operation_id}:{proposal.actor_id}", run_id=data["run_id"],
                          step_id=proposal.step_id, proposal_id=proposal.proposal_id, action=proposal.action,
                          revision_before=before)
            if status == "APPLIED":
                outcomes.append(ActionOutcome(**common, status=OutcomeStatus.APPLIED, effect_applied=True,
                                              revision_after=after,
                                              result={"written_paths": writes, "properties": props,
                                                      "batch": operation_id}))
            else:
                outcomes.append(ActionOutcome(**common, status=OutcomeStatus.REJECTED, effect_applied=False,
                                              revision_after=after, conflict=conflict,
                                              result={"reason": reason, "properties": props, "batch": operation_id}))
        self._advance(merged)
        data["applied_ops"][key] = [o.model_dump(mode="json") for o in outcomes]
        if len(data["applied_ops"]) > MAX_OP_MEMORY:
            data["applied_ops"].pop(next(iter(data["applied_ops"])))
        return outcomes

    def _advance(self, state: dict[str, Any]) -> None:
        data = self._require()
        data["step"] += 1
        data["history"].append(state)
        keep = max([1, *self.config.get("observation", {}).get("delay_steps", {}).values(),
                    *(v for view in self.config.get("observation", {}).get("per_actor", {}).values()
                      for v in view.get("delay_steps", {}).values())]) + 1
        data["history"] = data["history"][-keep:]

    # ------------------------------------------------------------------ persistence
    def snapshot(self) -> EnvironmentSnapshot:
        if self._data is None:
            raise NonRetryableFailure("nothing to snapshot before reset")
        payload = {"config": self.config, "data": self._data}
        return EnvironmentSnapshot(environment=self.descriptor.ref(), step=self._data["step"],
                                   state_revision=self._data["revision"], digest=digest_of(payload),
                                   data=copy.deepcopy(payload))

    def restore(self, snapshot: EnvironmentSnapshot) -> None:
        if snapshot.environment.plugin_id != ENV_ID:
            raise InvalidInput(f"snapshot belongs to {snapshot.environment.plugin_id}")
        if digest_of(snapshot.data) != snapshot.digest:
            raise InvalidInput("snapshot digest mismatch")
        payload = copy.deepcopy(snapshot.data)
        pinned = self.services.pinned_model()
        if payload["data"]["package"]["digest"] != pinned.digest.value:
            raise InvalidInput("snapshot was taken with a different model")
        self.config, self._data = payload["config"], payload["data"]

    # ------------------------------------------------------------------ evaluator access
    def truth_properties(self) -> dict[str, bool]:
        return self.loaded.properties(self._require()["state"])

    def truth_state(self) -> dict[str, Any]:
        if self._data is None:
            raise NonRetryableFailure("environment not initialised")
        return dict(self._data["state"])


def create(config: dict[str, Any] | None, services: Any = None) -> DriverWorldEnvironment:
    unknown = set(config or {}) - set(CONFIG_SCHEMA["properties"])
    if unknown:
        raise InvalidInput(f"unknown environment config keys: {sorted(unknown)}")
    return DriverWorldEnvironment(config, services)
