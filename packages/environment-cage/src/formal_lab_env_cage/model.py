"""The CAGE 4 blue-team model and its semantic driver (phase 4B, B2): profile `cage4_v1`.

What the platform knows about a CAGE Challenge 4 episode is the *interface* of a blue agent, not CybORG's dynamics:

- **state** (per blue agent, from its own native observation): `allowed[h]` — host h is in the agent's action space;
  `alert[h]` / `alert_kind[h]` — the agent's Monitor / Analyse reported something on h this world step (connections
  or files; green traffic produces connections too, so an alert is evidence, not truth); `busy` — an action of this
  agent is still in progress (CybORG starts nothing new until it ends); `last_success`, `world_step`, `phase`, `done`;
- **actions**: `sleep`, `monitor`, and `analyse` / `remove` / `restore` / `deploy_decoy` on an allowed host — the
  declared blue actions; block / allow traffic zone are not mapped by this adapter version;
- **property** `episode_complete` (goal): the native episode ended (CybORG `done`). It ends the run; it says nothing
  about how well blue did — the native reward and the platform metrics judge that.

The driver predicts applicability (declared action, allowed host) but **not** native effects: `predict` returns no
next state, so every effect comparison is INSUFFICIENT_INFORMATION instead of an invented MATCH or deviation. The
host universe (8 enterprise subnets x router / user / server hosts up to the generator's limits) is fixed in the
payload; which hosts exist in an episode depends on the seed.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
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
    Provenance,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.interfaces import Prediction

PROFILE = "cage4_v1"
NAMESPACE = "org.cage-challenge.cage4"
SCHEMA_ID = "cage4-blue@1"
DRIVER_ID = "formal-lab.driver.cage4"
PACKAGE_ID = "cage4-blue"
NATIVE = {"sleep": "Sleep", "monitor": "Monitor", "analyse": "Analyse", "remove": "Remove", "restore": "Restore",
          "deploy_decoy": "DeployDecoy"}
HOSTED = ("analyse", "remove", "restore", "deploy_decoy")
SCALARS = {"busy": False, "last_success": "UNKNOWN", "world_step": 0, "phase": 0, "done": False}
STATE_LABELS = {"allowed": "可操作主机", "alert": "告警", "alert_kind": "告警类型", "busy": "动作进行中",
                "last_success": "上一动作结果", "world_step": "原生世界步", "phase": "任务阶段", "done": "原生回合结束"}
ACTION_LABELS = {"sleep": "等待", "monitor": "监控", "analyse": "分析主机", "remove": "清除进程", "restore": "恢复主机",
                 "deploy_decoy": "部署诱饵"}

DESCRIPTOR = PluginDescriptor(
    plugin_id=DRIVER_ID, version="1.0.0", interface="SEMANTIC_DRIVER", interface_version="2",
    semantic_profiles=[PROFILE],
    capabilities=[{"id": f"profile.{PROFILE}"}, {"id": caps.DRIVER_CANDIDATES}, {"id": caps.DRIVER_PREDICT},
                  {"id": caps.DRIVER_PROPERTIES}, {"id": caps.DRIVER_BELIEF}, {"id": caps.DRIVER_DISPLAY}],
    config_schema={"type": "object", "additionalProperties": False},
    entrypoint="formal_lab_env_cage.model:create_driver",
    ui={"label": "CAGE 4 蓝方接口模型", "category": "driver",
        "description": "a blue agent's action interface and own observation in CybORG 4 Scenario4; applicability "
                       "only — native effects are not predicted",
        "state_labels": STATE_LABELS, "action_labels": ACTION_LABELS},
    license="Apache-2.0", source="formal-lab-env-cage")


def package(describe: dict[str, Any], *, version: int = 1, package_id: str = PACKAGE_ID) -> ModelPackage:
    """The model package from the worker's `describe` answer (host universe, declared blue actions)."""
    data = {"scenario": describe["scenario"], "hosts": list(describe["hosts"]),
            "blue_actions": [a for a in NATIVE if NATIVE[a] in describe["blue_actions"]],
            "subnets": list(describe["subnets"]), "limits": describe.get("limits", {})}
    body = {"namespace": NAMESPACE, "schema_id": SCHEMA_ID, "data": data}
    return ModelPackage(package_id=package_id, version=version, frontend=DESCRIPTOR.ref(), semantic_profile=PROFILE,
                        digest=digest_of(body), payload={"kind": "namespaced", **body},
                        source=ModelSource(format="cage4-describe/v1", text=None,
                                           origin=f"CybORG {describe.get('scenario')} host universe and blue actions"),
                        created_at=utcnow())


class Cage4Model:
    """LoadedModel for one blue agent's interface (see the module docstring)."""

    def __init__(self, pkg: ModelPackage):
        self.package = pkg
        data = pkg.payload.data
        self.hosts: list[str] = list(data["hosts"])
        self.actions: list[str] = list(data["blue_actions"])

    # ------------------------------------------------------------------ declarations
    def action_specs(self) -> list[ActionSpec]:
        none = {"type": "object", "properties": {}, "additionalProperties": False}
        host = {"type": "object", "properties": {"host": {"type": "string", "enum": self.hosts}},
                "required": ["host"], "additionalProperties": False}
        labels = ACTION_LABELS
        return [ActionSpec(action_type=a, label=labels.get(a, a), params_schema=host if a in HOSTED else none,
                           preconditions=["allowed[host]"] if a in HOSTED else [],
                           expected_effects=[f"native CybORG {NATIVE[a]} (not predicted by this model)"])
                for a in self.actions]

    def state_paths(self) -> list[str]:
        per_host = [f"{fam}[{h}]" for fam in ("allowed", "alert", "alert_kind") for h in self.hosts]
        return per_host + sorted(SCALARS)

    def initial_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for h in self.hosts:
            state[f"allowed[{h}]"] = False
            state[f"alert[{h}]"] = False
            state[f"alert_kind[{h}]"] = "none"
        return {**state, **SCALARS}

    # ------------------------------------------------------------------ belief and candidates
    def belief(self, observation: Observation) -> BeliefState:
        state = self.initial_state()
        seen = {f.path: f.value for f in observation.facts if f.path in state}
        state.update(seen)
        provenance = {p: Provenance.KNOWN if p in seen else Provenance.ASSUMED_INITIAL for p in state}
        items = [AssumptionItem(path=p, provenance=v, value=state[p], reason="not in this agent's observation")
                 for p, v in provenance.items() if v != Provenance.KNOWN]
        return BeliefState(actor_id=observation.actor_id, step=observation.step,
                           world_revision=observation.state_revision, state=state, provenance=provenance,
                           assumptions=AssumptionSet(items=items, digest=digest_of([i.model_dump(mode="json")
                                                                                    for i in items]),
                                                     counts={"KNOWN": len(seen), "ASSUMED_INITIAL": len(items)}))

    def candidates(self, belief: BeliefState, *, scope: Any = None, partial_checker: Any = None) -> list[CandidateAction]:
        allowed_types = set(scope.action_types) if scope is not None and getattr(scope, "action_types", None) else None
        state = belief.state
        labels = ACTION_LABELS
        busy = bool(state.get("busy"))
        note = " — an action is still in progress: CybORG will not start this one" if busy else ""
        out: list[CandidateAction] = []
        for a in self.actions:
            if allowed_types is not None and a not in allowed_types:
                continue
            if a not in HOSTED:
                out.append(CandidateAction(action=GroundAction(action_type=a), label=labels.get(a, a),
                                           reason=f"declared blue action{note}", belief_applicability="APPLICABLE"))
                continue
            for h in self.hosts:
                if state.get(f"allowed[{h}]") is True:
                    flag = "alert" if state.get(f"alert[{h}]") else "no alert"
                    out.append(CandidateAction(action=GroundAction(action_type=a, params={"host": h}),
                                               label=f"{labels.get(a, a)} {h}", reason=f"allowed host ({flag}){note}",
                                               belief_applicability="APPLICABLE"))
        return out

    def predict(self, state: dict[str, Any], action: GroundAction) -> Prediction:
        if action.action_type not in self.actions:
            return Prediction(applicable=False, reason=f"{action.action_type!r} is not a declared blue action",
                              next_state=None)
        if action.action_type in HOSTED:
            host = action.params.get("host")
            if state.get(f"allowed[{host}]") is not True:
                return Prediction(applicable=False, reason=f"host {host!r} is not in this agent's action space",
                                  next_state=None)
        # applicable; CybORG's effect (and its success) is not predicted by this model
        return Prediction(applicable=True, reason=None, next_state=None, written_paths=[])

    def properties(self, state: dict[str, Any]) -> dict[str, bool]:
        return {"episode_complete": bool(state.get("done"))}

    def property_kinds(self) -> dict[str, str]:
        return {"episode_complete": "goal"}

    def display(self) -> dict[str, Any]:
        labels = STATE_LABELS
        return {"state_families": [{"name": n, "label": labels[n]} for n in labels],
                "actions": list(self.actions),
                "properties": [{"id": "episode_complete", "kind": "goal", "label": "原生回合结束"}]}


class Cage4Driver:
    descriptor = DESCRIPTOR

    def validate(self, pkg: ModelPackage) -> list[str]:
        p = pkg.payload
        if getattr(p, "kind", None) != "namespaced" or p.namespace != NAMESPACE or p.schema_id != SCHEMA_ID:
            return [f"payload is not {NAMESPACE} / {SCHEMA_ID}"]
        problems = []
        if not p.data.get("hosts"):
            problems.append("the host universe is empty")
        unknown = [a for a in p.data.get("blue_actions", []) if a not in NATIVE]
        if unknown:
            problems.append(f"undeclared blue actions {unknown}")
        return problems

    def load(self, pkg: ModelPackage) -> Cage4Model:
        return Cage4Model(pkg)


def create_driver(config: dict[str, Any] | None, services: Any) -> Cage4Driver:
    return Cage4Driver()
