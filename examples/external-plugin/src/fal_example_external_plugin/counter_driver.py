"""`org.example.counter-driver`: a minimal semantic driver that implements only the public protocol (phase 3A, G3).

Profile `counter_v1`, a namespaced payload `{"target", "limit", "step"}`: one state location `count`, actions
`inc` (count + step ≤ limit) and `reset`, a goal `reached` (count ≥ target) and an invariant `bounded`
(count ≤ limit). The loaded model offers exactly the LoadedModel protocol — no neutral IR, no statistics — so the
platform must learn what it can do with this model from the declared capabilities alone: releases type-check it and
replay regression cases through predict(); rules, IR objectives and bounded queries are UNSUPPORTED (no verifier
declares `counter_v1`). Only `formal_lab_sdk` is imported.
"""

from __future__ import annotations

from typing import Any

from formal_lab_sdk.plugins import (
    ActionSpec,
    AssumptionItem,
    AssumptionSet,
    BeliefState,
    CandidateAction,
    GroundAction,
    ModelPackage,
    ModelSource,
    Observation,
    PluginDescriptor,
    Prediction,
    Provenance,
    capabilities,
    digest_of,
    utcnow,
)

PROFILE = "counter_v1"
NAMESPACE = "org.example.counter"
SCHEMA_ID = "counter-model@1"
DESCRIPTOR = PluginDescriptor(
    plugin_id="org.example.counter-driver", version="0.1.0", interface="SEMANTIC_DRIVER", interface_version="2",
    semantic_profiles=[PROFILE],
    capabilities=[{"id": f"profile.{PROFILE}"}, {"id": capabilities.DRIVER_CANDIDATES},
                  {"id": capabilities.DRIVER_PREDICT}, {"id": capabilities.DRIVER_PROPERTIES},
                  {"id": capabilities.DRIVER_BELIEF}, {"id": capabilities.DRIVER_DISPLAY}],
    config_schema={"type": "object", "additionalProperties": False},
    entrypoint="fal_example_external_plugin.counter_driver:create",
    ui={"label": "Example: counter driver (external, protocol only)", "category": "driver",
        "state_labels": {"count": "计数"}, "action_labels": {"inc": "加一步", "reset": "归零"}},
    license="Apache-2.0", source="fal-example-external-plugin")


def package(*, target: int = 3, limit: int = 5, step: int = 1, version: int = 1) -> ModelPackage:
    body = {"namespace": NAMESPACE, "schema_id": SCHEMA_ID, "data": {"target": target, "limit": limit, "step": step}}
    return ModelPackage(package_id="counter", version=version, frontend=DESCRIPTOR.ref(), semantic_profile=PROFILE,
                        digest=digest_of(body), payload={"kind": "namespaced", **body},
                        source=ModelSource(format="counter-json/v1", text=str(body["data"]),
                                           origin="fal_example_external_plugin.counter_driver"),
                        created_at=utcnow())


class CounterModel:
    """LoadedModel protocol, nothing more."""

    def __init__(self, pkg: ModelPackage):
        self.package = pkg
        data = pkg.payload.data
        self.target, self.limit, self.step = int(data["target"]), int(data["limit"]), int(data["step"])

    def action_specs(self) -> list[ActionSpec]:
        empty = {"type": "object", "properties": {}, "additionalProperties": False}
        return [ActionSpec(action_type="inc", label="加一步", params_schema=empty,
                           preconditions=[f"count + {self.step} ≤ {self.limit}"],
                           expected_effects=[f"count := count + {self.step}"]),
                ActionSpec(action_type="reset", label="归零", params_schema=empty, expected_effects=["count := 0"])]

    def state_paths(self) -> list[str]:
        return ["count"]

    def initial_state(self) -> dict[str, Any]:
        return {"count": 0}

    def belief(self, observation: Observation) -> BeliefState:
        state = dict(self.initial_state())
        seen = {f.path: f.value for f in observation.facts if f.path in state}
        state.update(seen)
        provenance = {p: Provenance.KNOWN if p in seen else Provenance.ASSUMED_INITIAL for p in state}
        items = [AssumptionItem(path=p, provenance=v, value=state[p], reason="never observed: initial value")
                 for p, v in provenance.items() if v != Provenance.KNOWN]
        return BeliefState(actor_id=observation.actor_id, step=observation.step,
                           world_revision=observation.state_revision, state=state, provenance=provenance,
                           assumptions=AssumptionSet(items=items, digest=digest_of([i.model_dump(mode="json")
                                                                                    for i in items]),
                                                     counts={"KNOWN": len(seen), "ASSUMED_INITIAL": len(items)}))

    def candidates(self, belief: BeliefState, *, scope: Any = None, partial_checker: Any = None) -> list[CandidateAction]:
        allowed = set(scope.action_types) if scope is not None and scope.action_types else None
        out = []
        for spec in self.action_specs():
            if allowed is not None and spec.action_type not in allowed:
                continue
            action = GroundAction(action_type=spec.action_type)
            pred = self.predict(belief.state, action)
            out.append(CandidateAction(action=action, label=spec.label, reason=pred.reason,
                                       belief_applicability="APPLICABLE" if pred.applicable else "INAPPLICABLE"))
        return out

    def predict(self, state: dict[str, Any], action: GroundAction) -> Prediction:
        count = int(state["count"])
        if action.action_type == "inc":
            if count + self.step > self.limit:
                return Prediction(applicable=False, reason=f"count {count} + {self.step} > limit {self.limit}",
                                  next_state=None)
            return Prediction(applicable=True, reason=None, next_state={"count": count + self.step},
                              written_paths=["count"])
        if action.action_type == "reset":
            return Prediction(applicable=True, reason=None, next_state={"count": 0}, written_paths=["count"])
        return Prediction(applicable=False, reason=f"unknown action {action.action_type}", next_state=None)

    def properties(self, state: dict[str, Any]) -> dict[str, bool]:
        return {"reached": int(state["count"]) >= self.target, "bounded": int(state["count"]) <= self.limit}

    def property_kinds(self) -> dict[str, str]:
        return {"reached": "goal", "bounded": "invariant"}

    def display(self) -> dict[str, Any]:
        return {"state_families": [{"name": "count", "label": "计数"}],
                "actions": [s.action_type for s in self.action_specs()],
                "properties": [{"id": "reached", "kind": "goal"}, {"id": "bounded", "kind": "invariant"}]}


class CounterDriver:
    descriptor = DESCRIPTOR

    def validate(self, pkg: ModelPackage) -> list[str]:
        p = pkg.payload
        if getattr(p, "kind", None) != "namespaced" or p.namespace != NAMESPACE or p.schema_id != SCHEMA_ID:
            return [f"payload is not {NAMESPACE} / {SCHEMA_ID}"]
        data = p.data
        problems = [f"{k} must be a positive integer" for k in ("target", "limit", "step")
                    if not isinstance(data.get(k), int) or data[k] < 1]
        if not problems and data["target"] > data["limit"]:
            problems.append(f"target {data['target']} exceeds limit {data['limit']}")
        return problems

    def load(self, pkg: ModelPackage) -> CounterModel:
        return CounterModel(pkg)


def create(config: dict[str, Any] | None, services: Any) -> CounterDriver:
    return CounterDriver()
