"""Semantic driver for the neutral IR (profile deterministic_finite_v1) — the kernel's only view of IR semantics.

The run kernel never builds a CheckedModel or an Interpreter itself: it asks the registry for the driver of the
pinned model's profile and talks to the returned `LoadedModel` (candidates, predictions, properties, belief with
provenance, display structure). This module is that driver for IR payloads (P2-010 / P2-011); other profiles
bring their own driver plugin.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Any

from formal_lab_contracts import (
    ActionSpec,
    BeliefState,
    CandidateAction,
    GroundAction,
    ModelPackage,
    Observation,
    PluginDescriptor,
    PreconditionVerdict,
    StateScalar,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import InvalidInput
from formal_lab_contracts.interfaces import PartialChecker, Prediction

from .belief import belief_state
from .checker import CheckedModel, check_model
from .checker import GroundAction as IRGroundAction
from .interpreter import Interpreter
from .specs import action_specs

DRIVER_ID = "formal-lab.driver.ir-finite"
DRIVER_VERSION = "1.0.0"

DESCRIPTOR = PluginDescriptor(
    plugin_id=DRIVER_ID,
    version=DRIVER_VERSION,
    interface="SEMANTIC_DRIVER",
    capabilities=[
        {"id": caps.PROFILE_DETERMINISTIC_FINITE_V1},
        {"id": caps.DRIVER_CANDIDATES},
        {"id": caps.DRIVER_PREDICT},
        {"id": caps.DRIVER_PROPERTIES},
        {"id": caps.DRIVER_BELIEF},
        {"id": caps.DRIVER_DISPLAY},
        {"id": caps.DRIVER_IR},
        {"id": caps.DRIVER_STATS},
    ],
    semantic_profiles=["deterministic_finite_v1"],
    input_schema={"$ref": "https://formal-lab.dev/contracts/v2/IRPayload.schema.json"},
    config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    entrypoint="formal_lab_model.driver:create",
    ui={"label": "IR 有限状态语义", "category": "semantic_driver",
        "description": "deterministic_finite_v1: reference interpreter semantics; partial-state preconditions are "
        "decided by the run's verifier over all completions"},
    license="Apache-2.0",
    source="formal-lab-model-core",
)


class IRLoadedModel:
    """LoadedModel of an IR payload. Thread-safe: evaluation is pure Python over immutable tables."""

    def __init__(self, package: ModelPackage, checked: CheckedModel):
        self.package = package
        self.checked = checked
        self.interp = Interpreter(checked)
        self._specs = action_specs(checked)
        self._labels = {s.action_type: s.label for s in self._specs}
        self._kinds = {pid: p.kind for pid, p in checked.properties.items()}

    # ------------------------------------------------------------------ LoadedModel protocol
    def action_specs(self) -> list[ActionSpec]:
        return list(self._specs)

    def state_paths(self) -> list[str]:
        return self.checked.state_paths()

    def initial_state(self) -> dict[str, StateScalar]:
        return self.checked.initial_state()

    def belief(self, observation: Observation) -> BeliefState:
        return belief_state(observation, self.checked)

    def stats(self) -> dict[str, int]:
        """Sizes for release records (capability driver.stats)."""
        return {"ground_actions": len(self.ground_actions()), "state_locations": len(self.state_paths())}

    def ground_actions(self, scope: Any = None) -> list[GroundAction]:
        out = []
        for ga in self.checked.ground_actions:
            if scope is not None:
                if scope.action_types and ga.action not in scope.action_types:
                    continue
                params = dict(ga.params)
                if any(name in params and params[name] not in allowed for name, allowed in scope.params.items()):
                    continue
            out.append(GroundAction(action_type=ga.action, params=dict(ga.params)))
        return out

    def candidates(self, belief: BeliefState, *, scope: Any = None, partial_checker: PartialChecker | None = None,
                   free: list[str] | None = None) -> list[CandidateAction]:
        """All ground actions in the participant's scope with their applicability on the belief.

        Fully known belief → decided by the interpreter. With free (unknown) locations → decided over all
        completions by `partial_checker` (the run's verifier), else by explicit enumeration (bounded)."""
        free = sorted(free if free is not None else belief.free_paths)
        out: list[CandidateAction] = []
        for action in self.ground_actions(scope):
            ga = self._ground(action)
            request = None
            reason = None
            if not free:
                res = self.interp.step(ga, belief.state)
                verdict = PreconditionVerdict.APPLICABLE if res.applicable else PreconditionVerdict.INAPPLICABLE
                reason = res.reason
            elif partial_checker is not None:
                verdict, request = partial_checker(action, belief.state, free)
            else:
                known = {p: v for p, v in belief.state.items() if p not in set(free)}
                answer, _ = self.interp.applicability_with_unknowns(ga, known, free)
                verdict = PreconditionVerdict(answer)
            out.append(CandidateAction(action=action, label=self._labels.get(action.action_type),
                                       belief_applicability=verdict, reason=reason, observation_request=request))
        return out

    def predict(self, state: dict[str, StateScalar], action: GroundAction) -> Prediction:
        try:
            ga = self._ground(action)
        except InvalidInput as exc:
            return Prediction(applicable=False, reason=f"INVALID_ACTION: {exc.message}", next_state=None)
        res = self.interp.step(ga, state)
        if not res.applicable:
            return Prediction(applicable=False, reason=res.reason, next_state=None)
        return Prediction(applicable=True, reason=None, next_state=res.next_state,
                          written_paths=sorted({p for p, _ in res.writes}))

    def properties(self, state: dict[str, StateScalar]) -> dict[str, bool]:
        return {pid: self.interp.holds(pid, state) for pid in self.checked.properties}

    def property_kinds(self) -> dict[str, str]:
        return dict(self._kinds)

    def display(self) -> dict[str, Any]:
        ir = self.checked.ir
        return {
            "kind": "fal-ir",
            "name": ir.name,
            "entities": {es.name: {"label": es.label, "members": es.members} for es in ir.entity_sets},
            "state": [{"name": v.name, "label": v.label, "index": v.index} for v in ir.state],
            "actions": [{"name": a.name, "label": a.label, "params": [p.name for p in a.params], "cost": a.cost}
                        for a in ir.actions],
            "properties": [{"id": p.id, "kind": p.kind, "label": p.label} for p in ir.properties],
            "objectives": [{"id": o.id, "label": o.label, "unit": o.unit} for o in ir.objectives],
            "ground_actions": len(self.checked.ground_actions),
            "locations": len(self.checked.state_paths()),
        }

    # ------------------------------------------------------------------ IR-specific helpers
    def _ground(self, action: GroundAction) -> IRGroundAction:
        try:
            return self.interp.ground(action.action_type, dict(action.params))
        except KeyError as exc:
            raise InvalidInput(str(exc).strip("'\"")) from exc

    def evaluate(self, expr: Any, state: dict[str, StateScalar], env: dict[str, Any] | None = None) -> Any:
        return self.interp.evaluate(expr, state, env)


@lru_cache(maxsize=64)
def _load(digest: str, payload_json: str, thread: int) -> CheckedModel:
    from formal_lab_contracts import ModelIR

    return check_model(ModelIR.model_validate_json(payload_json))


class IRFiniteDriver:
    descriptor = DESCRIPTOR

    def validate(self, package: ModelPackage) -> list[str]:
        if not package.is_ir:
            return [f"{DRIVER_ID} reads fal-ir payloads, got {package.payload.kind}"]
        checked = check_model(package.ir)
        return [f"{i.path}: [{i.code}] {i.message}" for i in checked.issues]

    def load(self, package: ModelPackage) -> IRLoadedModel:
        problems = self.validate(package)
        if problems:
            raise InvalidInput(f"model {package.package_id}@{package.version} cannot be loaded",
                               details={"problems": problems[:20]})
        checked = _load(package.digest.value, package.ir.model_dump_json(), threading.get_ident())
        return IRLoadedModel(package, checked)


def create(config: dict[str, Any] | None = None, services: Any = None) -> IRFiniteDriver:
    return IRFiniteDriver()
