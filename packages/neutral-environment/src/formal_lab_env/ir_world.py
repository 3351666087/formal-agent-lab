"""IR world: a pure-data simulator that runs a deterministic_finite_v1 model as the environment truth.

Truth vs. observation
- The *truth state* is the full state of the truth model; it never leaves the environment except via
  snapshots (for persistence/replay) and the final episode record used by deterministic scorers.
- An *Observation* is what an actor may know: facts (possibly stale) and unknown items.

Scenario configuration (all optional, validated against CONFIG_SCHEMA):
- initial_overrides: {path: value} fixed changes to the model's initial state for this scenario.
- seeded_variation: [{var, delta_min, delta_max}] per-seed integer perturbation of initial values
  (clamped to the declared range). The actor observes the result, so belief and truth stay consistent.
- truth_constant_overrides: {path: value} constants of the *truth* model that differ from the pinned
  model the actors plan with (used for "expectation vs. simulation mismatch" scenarios).
- observation.delay_steps: {var: k} the actor sees var's value from k steps ago (stale facts + unknowns).
- observation.hidden: [var] never revealed (unknown, NOT_OBSERVABLE).
- observation.per_actor: {actor: {delay_steps, hidden}} per-participant overrides (v1.1).
- observation.on_request: false disables fresh observations on request (OBSERVE_MORE); default true (v1.1).

Several participants (v1.1): every actor observes the same truth through its own view; the world revision counts
applied actions. A proposal carries the revision its observation reflected; the scenario's conflict policy decides
what happens when the world moved on since then — REVALIDATE applies it if its precondition still holds on the
current state, REJECT_STALE rejects it when a location its precondition reads was written since that revision.
Either way a rejection caused by a newer revision carries `ConflictInfo` (which locations changed, by whom).
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
    ModelIR,
    ModelPackage,
    Observation,
    OutcomeStatus,
    PluginDescriptor,
    ScenarioManifest,
    UnknownItem,
    digest_of,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import Conflict, InvalidInput, NonRetryableFailure
from formal_lab_model import Interpreter, check_model
from formal_lab_model.checker import CheckedModel, TInt

ENV_ID = "formal-lab.env.ir-world"
ENV_VERSION = "1.1.0"
MAX_OP_MEMORY = 64

CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "initial_overrides": {"type": "object", "additionalProperties": {"type": ["boolean", "integer", "string"]}},
        "seeded_variation": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"var": {"type": "string"}, "delta_min": {"type": "integer"},
                               "delta_max": {"type": "integer"}},
                "required": ["var", "delta_min", "delta_max"],
                "additionalProperties": False,
            },
        },
        "truth_constant_overrides": {"type": "object",
                                     "additionalProperties": {"type": ["boolean", "integer", "string"]}},
        "observation": {
            "type": "object",
            "properties": {
                "delay_steps": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
                "hidden": {"type": "array", "items": {"type": "string"}},
                "per_actor": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "delay_steps": {"type": "object",
                                            "additionalProperties": {"type": "integer", "minimum": 0}},
                            "hidden": {"type": "array", "items": {"type": "string"}},
                        },
                        "additionalProperties": False,
                    },
                },
                "on_request": {"type": "boolean", "default": True},
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
    capabilities=[
        {"id": caps.PROFILE_DETERMINISTIC_FINITE_V1},
        {"id": caps.ENV_SNAPSHOT_RESTORE},
        {"id": caps.ENV_OBSERVATION_DELAY},
        {"id": caps.ENV_TRUTH_OVERRIDES},
        {"id": caps.ENV_SEEDED_VARIATION},
        {"id": caps.ENV_PURE_REPLAYABLE},
        {"id": caps.ENV_SNAPSHOT},
        {"id": caps.ENV_RESTORE},
        {"id": caps.ENV_IDEMPOTENT_STEP},
        {"id": caps.ENV_MULTI_ACTOR},
        {"id": caps.ENV_OBSERVE_ON_REQUEST},
    ],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_env.ir_world:create",
    ui={"label": "IR world simulator", "category": "environment",
        "description": "Pure-data simulator: runs the pinned model (optionally with truth overrides) as the world"},
    license="Apache-2.0",
    source="formal-lab-neutral-env",
)


def _check_config(config: dict[str, Any]) -> None:
    unknown = set(config) - set(CONFIG_SCHEMA["properties"])
    if unknown:
        raise InvalidInput(f"unknown environment config keys: {sorted(unknown)}")
    obs = config.get("observation", {})
    allowed = {"delay_steps", "hidden", "per_actor", "on_request"}
    if set(obs) - allowed:
        raise InvalidInput(f"unknown observation config keys: {sorted(set(obs) - allowed)}")


def truth_model_ir(package: ModelPackage, overrides: dict[str, Any]) -> ModelIR:
    """Pinned model with constant cells replaced (the environment's hidden reality)."""
    if not overrides:
        return package.ir
    data = package.ir.model_dump(mode="json")
    consts = {c["name"]: c for c in data["constants"]}
    for path, value in overrides.items():
        name, _, rest = path.partition("[")
        if name not in consts:
            raise InvalidInput(f"truth override {path!r} does not name a constant")
        index = rest.rstrip("]").split(",") if rest else []
        cells = consts[name]["value"]["cells"]
        for cell in cells:
            if cell["index"] == index:
                cell["value"] = value
                break
        else:
            cells.append({"index": index, "value": value})
    return ModelIR.model_validate(data)


class IRWorldEnvironment:
    descriptor = DESCRIPTOR

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = copy.deepcopy(config or {})
        _check_config(self.config)
        self._truth: CheckedModel | None = None
        self._interp: Interpreter | None = None
        self._data: dict[str, Any] | None = None

    # ------------------------------------------------------------------ lifecycle
    def reset(self, scenario: ScenarioManifest, package: ModelPackage, *, run_id: str, seed: int) -> Observation:
        truth_ir = truth_model_ir(package, self.config.get("truth_constant_overrides", {}))
        self._truth = check_model(truth_ir)
        if self._truth.issues:
            raise InvalidInput("truth model is invalid", details={"issues": [i.model_dump() for i in self._truth.issues]})
        self._interp = Interpreter(self._truth)
        state = self._interp.initial_state()
        for path, value in self.config.get("initial_overrides", {}).items():
            if path not in state:
                raise InvalidInput(f"initial override {path!r} is not a state location")
            state[path] = value
        rng = random.Random(seed)
        for rule in self.config.get("seeded_variation", []):
            fam = self._truth.families.get(rule["var"])
            if fam is None or not fam.is_state or not isinstance(fam.ty, TInt):
                raise InvalidInput(f"seeded variation needs an int state variable, got {rule['var']!r}")
            for path in sorted(fam.table):
                delta = rng.randint(rule["delta_min"], rule["delta_max"])
                state[path] = max(fam.ty.lo, min(fam.ty.hi, int(state[path]) + delta))  # type: ignore[type-var]
        self._data = {
            "run_id": run_id,
            "seed": seed,
            "scenario_id": scenario.scenario_id,
            "package": {"package_id": package.package_id, "version": package.version, "digest": package.digest.value},
            "truth_ir_digest": digest_of(truth_ir).value,
            "step": 0,
            "revision": 0,
            "state": state,
            "history": [state],  # truth states by step (bounded by the largest delay)
            "applied_ops": {},
            "closed": False,
            "conflict_policy": scenario.turns.conflict_policy.value,
            "writes": {},  # path → [revision, actor] of the last write (conflict arbitration)
        }
        return self.observe(scenario.participants[0].actor_id)

    def close(self) -> None:
        if self._data is not None:
            self._data["closed"] = True

    # ------------------------------------------------------------------ observation
    def _require(self) -> dict[str, Any]:
        if self._data is None or self._interp is None:
            raise NonRetryableFailure("environment used before reset/restore")
        if self._data["closed"]:
            raise Conflict("environment is closed")
        return self._data

    def _view(self, actor_id: str) -> tuple[dict[str, int], set[str]]:
        obs_cfg = self.config.get("observation", {})
        own = obs_cfg.get("per_actor", {}).get(actor_id, {})
        delays = {**obs_cfg.get("delay_steps", {}), **own.get("delay_steps", {})}
        hidden = set(obs_cfg.get("hidden", [])) | set(own.get("hidden", []))
        return delays, hidden

    def observe(self, actor_id: str, fresh_paths: list[str] | None = None) -> Observation:
        data = self._require()
        assert self._truth is not None
        step = data["step"]
        delays, hidden = self._view(actor_id)
        fresh = set(fresh_paths or [])
        history = data["history"]
        facts: list[Fact] = []
        unknowns: list[UnknownItem] = []
        for fam in self._truth.state_families:
            for path in fam.table:
                if path in fresh:
                    facts.append(Fact(path=path, value=data["state"][path], observed_at_step=step))
                    continue
                if fam.name in hidden or not fam.observable:
                    unknowns.append(UnknownItem(path=path, reason="NOT_OBSERVABLE"))
                    continue
                k = delays.get(fam.name, 0)
                if k == 0:
                    facts.append(Fact(path=path, value=data["state"][path], observed_at_step=step))
                    continue
                seen_step = max(0, step - k)
                value = history[len(history) - 1 - (step - seen_step)][path]
                fact = Fact(path=path, value=value, observed_at_step=seen_step,
                            source="DELAYED" if seen_step < step else "DIRECT")
                if seen_step < step:
                    unknowns.append(UnknownItem(path=path, reason="OBSERVATION_DELAY", last_known=fact))
                else:
                    facts.append(fact)
        return Observation(
            run_id=data["run_id"],
            actor_id=actor_id,
            step=step,
            state_revision=data["revision"],
            facts=facts,
            unknowns=unknowns,
            evidence=[EvidenceRef(kind="snapshot", id=f"{data['run_id']}:env@{step}",
                                  note=f"truth revision {data['revision']}")],
            requested_paths=sorted(fresh),
        )

    def observe_paths(self, actor_id: str, paths: list[str]) -> Observation:
        """Fresh values for the requested locations (OBSERVE_MORE); the rest of the view is unchanged."""
        if not self.config.get("observation", {}).get("on_request", True):
            from formal_lab_contracts.errors import Unsupported

            raise Unsupported("observations on request are disabled for this scenario")
        assert self._truth is not None
        known = set(self._truth.state_paths())
        unknown = [p for p in paths if p not in known]
        if unknown:
            raise InvalidInput(f"not state locations: {unknown}")
        return self.observe(actor_id, fresh_paths=paths)

    # ------------------------------------------------------------------ transition
    def step(self, proposal: ActionProposal, *, operation_id: str) -> ActionOutcome:
        data = self._require()
        assert self._interp is not None
        if operation_id in data["applied_ops"]:  # idempotent re-delivery of the same operation
            return ActionOutcome.model_validate(data["applied_ops"][operation_id])
        before = data["revision"]
        try:
            ga = self._interp.ground(proposal.action.action_type, dict(proposal.action.params))
        except KeyError as exc:
            outcome = ActionOutcome(
                operation_id=operation_id, run_id=data["run_id"], step_id=proposal.step_id,
                proposal_id=proposal.proposal_id, action=proposal.action, status=OutcomeStatus.REJECTED,
                effect_applied=False, revision_before=before, revision_after=before,
                result={"reason": f"INVALID_ACTION: {exc}", "properties": self.truth_properties()},
            )
        else:
            conflict = self._conflict(ga, proposal, before)
            res = self._interp.step(ga, data["state"])
            if conflict is not None and conflict.policy.value == "REJECT_STALE":
                outcome = ActionOutcome(
                    operation_id=operation_id, run_id=data["run_id"], step_id=proposal.step_id,
                    proposal_id=proposal.proposal_id, action=proposal.action, status=OutcomeStatus.REJECTED,
                    effect_applied=False, revision_before=before, revision_after=before, conflict=conflict,
                    result={"reason": f"STALE_REVISION: {conflict.reason}", "properties": self.truth_properties()},
                )
            elif res.applicable and res.next_state is not None:
                data["state"] = res.next_state
                data["revision"] = before + 1
                for path in {p for p, _ in res.writes}:
                    data["writes"][path] = [before + 1, proposal.actor_id]
                outcome = ActionOutcome(
                    operation_id=operation_id, run_id=data["run_id"], step_id=proposal.step_id,
                    proposal_id=proposal.proposal_id, action=proposal.action, status=OutcomeStatus.APPLIED,
                    effect_applied=True, revision_before=before, revision_after=before + 1,
                    result={"written_paths": sorted({p for p, _ in res.writes}),
                            "properties": self.truth_properties()},
                )
            else:
                outcome = ActionOutcome(
                    operation_id=operation_id, run_id=data["run_id"], step_id=proposal.step_id,
                    proposal_id=proposal.proposal_id, action=proposal.action, status=OutcomeStatus.REJECTED,
                    effect_applied=False, revision_before=before, revision_after=before,
                    conflict=conflict.model_copy(update={"reason": f"precondition no longer holds: {res.reason}; "
                                                                   + conflict.reason}) if conflict else None,
                    result={"reason": res.reason, "properties": self.truth_properties()},
                )
        data["step"] += 1
        data["history"].append(data["state"])
        keep = max([1, *self.config.get("observation", {}).get("delay_steps", {}).values()]) + 1
        data["history"] = data["history"][-keep:]
        data["applied_ops"][operation_id] = outcome.model_dump(mode="json")
        if len(data["applied_ops"]) > MAX_OP_MEMORY:
            data["applied_ops"].pop(next(iter(data["applied_ops"])))
        return outcome

    def _conflict(self, ga: Any, proposal: ActionProposal, current: int) -> ConflictInfo | None:
        """Locations the action's precondition reads that were written after the proposal's revision."""
        data = self._data
        assert data is not None and self._truth is not None
        if proposal.based_on_revision >= current:
            return None
        from formal_lab_model.rules import read_set

        decl = self._truth.actions[ga.action]
        reads = read_set(decl.precondition, self._truth)
        changed = sorted(p for p, (rev, _) in data.get("writes", {}).items()
                         if rev > proposal.based_on_revision and p in reads)
        if not changed:
            return None
        writers = sorted({data["writes"][p][1] for p in changed if data["writes"][p][1]})
        return ConflictInfo(policy=data.get("conflict_policy", "REVALIDATE"),
                            based_on_revision=proposal.based_on_revision, current_revision=current,
                            changed_paths=changed,
                            reason=f"observed at revision {proposal.based_on_revision}, world at {current}; "
                                   f"{len(changed)} location(s) it depends on changed since"
                                   + (f" (written by {', '.join(writers)})" if writers else ""))

    # ------------------------------------------------------------------ persistence
    def snapshot(self) -> EnvironmentSnapshot:
        data = self._require() if self._data and not self._data["closed"] else self._data
        if data is None:
            raise NonRetryableFailure("nothing to snapshot before reset")
        payload = {"config": self.config, "data": data}
        return EnvironmentSnapshot(environment=self.descriptor.ref(), step=data["step"], state_revision=data["revision"],
                                   digest=digest_of(payload), data=copy.deepcopy(payload))

    def restore_with_model(self, snapshot: EnvironmentSnapshot, package: ModelPackage) -> None:
        if snapshot.environment.plugin_id != ENV_ID:
            raise InvalidInput(f"snapshot belongs to {snapshot.environment.plugin_id}")
        if digest_of(snapshot.data) != snapshot.digest:
            raise InvalidInput("snapshot digest mismatch")
        payload = copy.deepcopy(snapshot.data)
        self.config = payload["config"]
        _check_config(self.config)
        truth_ir = truth_model_ir(package, self.config.get("truth_constant_overrides", {}))
        if digest_of(truth_ir).value != payload["data"]["truth_ir_digest"]:
            raise InvalidInput("snapshot was taken with a different model")
        self._truth = check_model(truth_ir)
        self._interp = Interpreter(self._truth)
        self._data = payload["data"]

    def restore(self, snapshot: EnvironmentSnapshot) -> None:
        if self._package is None:
            raise NonRetryableFailure("restore() needs the pinned model; use restore_with_model or create() services")
        self.restore_with_model(snapshot, self._package)

    _package: ModelPackage | None = None

    # ------------------------------------------------------------------ evaluator access
    def truth_properties(self) -> dict[str, bool]:
        """Truth values of all model properties on the current truth state (reported in outcomes)."""
        data = self._data
        assert data is not None and self._interp is not None
        return {pid: self._interp.holds(pid, data["state"]) for pid in self._interp.model.properties}

    def truth_state(self) -> dict[str, Any]:
        data = self._data
        if data is None:
            raise NonRetryableFailure("environment not initialised")
        return dict(data["state"])

    @property
    def current_step(self) -> int:
        return self._require()["step"]


def create(config: dict[str, Any] | None, services: Any = None) -> IRWorldEnvironment:
    env = IRWorldEnvironment(config)
    if services is not None:
        env._package = services.pinned_model()
    return env


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    return [PluginRegistration(DESCRIPTOR, create)]
