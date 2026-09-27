"""Contract test harness for plugins (P2-018), public API for packages outside this repository.

Runs a plugin through the lifecycle the kernel uses and reports every stage, so a plugin author can test against
the real engine without the platform:

    from formal_lab_sdk.plugin_testing import check_planner
    report = check_planner(("org.example.preference-planner", "0.1.0"), {"preference": ["serve"]})
    assert report.ok, report.failures()

Planner stages: registered (descriptor + config schema) → initialised (created by the registry with its config) →
negotiated (the run manifest's capability negotiation for the participant) → observe & propose (the first step's
proposal names the plugin and one of the offered candidates) → state advanced (outcomes recorded) → recovered (a
run stopped mid-way, serialised to JSON and continued equals the uninterrupted run) → finished (terminal status,
termination reason, metrics).

Environment stages: registered → initialised → reset & observe → step (an applicable action is applied, the
revision moves) → snapshot / restore (FULL_STATE: restored exactly; SESSION_MARKER: re-attached) → operation lookup
(when env.query_operation is declared) → closed.

The reference model is the built-in `queue-costs` sample (profile deterministic_finite_v1) unless one is given.
Needs the engine installed (`formal-lab-runtime`); the platform is not involved.
"""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Stage:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class ContractReport:
    plugin: str
    stages: list[Stage] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.stages) and all(s.ok for s in self.stages)

    def failures(self) -> list[str]:
        return [f"{s.name}: {s.detail}" for s in self.stages if not s.ok]

    def as_dict(self) -> dict[str, Any]:
        return {"plugin": self.plugin, "ok": self.ok, "stages": [s.__dict__ for s in self.stages]}

    def run(self, name: str, fn: Callable[[], str]) -> bool:
        if self.stages and not self.stages[-1].ok:
            self.stages.append(Stage(name, False, "skipped: an earlier stage failed"))
            return False
        try:
            self.stages.append(Stage(name, True, fn() or "ok"))
        except AssertionError as exc:
            self.stages.append(Stage(name, False, str(exc) or "assertion failed"))
        except Exception as exc:  # the report must say what broke, not crash the caller
            self.stages.append(Stage(name, False, f"{type(exc).__name__}: {exc} | "
                                                  f"{traceback.format_exc(limit=2).splitlines()[-1]}"))
        return self.stages[-1].ok


def _services(reg: Any, pkg: Any) -> Any:
    """Plugin services as the kernel builds them: the pinned model and the model loaded by its profile's driver."""
    from formal_lab_runtime.engine import RuntimeServices

    driver = reg.create(reg.driver_for(pkg.semantic_profile).descriptor.ref(), {}, None)
    return RuntimeServices(pkg, loaded=driver.load(pkg))


def _reference_package() -> Any:
    from formal_lab_contracts import ModelSource
    from formal_lab_model import build_package
    from formal_lab_model.samples import queue_costs

    ir = queue_costs()
    return build_package(ir, package_id="contract-test", version=1,
                         source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(), origin="plugin_testing"))


def _scenario(package: Any, planner: dict[str, Any], environment: dict[str, Any] | None, max_steps: int) -> Any:
    from formal_lab_contracts import ScenarioManifest

    goal = next((p.id for p in package.ir.properties if str(p.kind) == "goal"), None) if package.is_ir else None
    return ScenarioManifest(
        scenario_id="plugin-contract", name="plugin contract test", model=package.ref(),
        environment=environment or {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.1.0"},
                                     "config": {}},
        participants=[{"actor_id": "agent", "role": "operator", "strategy": planner}],
        budget={"max_steps": max_steps}, seed=0,
        termination={"joint_goal": goal, "on_no_action": "END"})


def _trajectory(events: list[Any]) -> list[tuple]:
    return [(e.logical_step, json.dumps(e.payload["outcome"]["action"], sort_keys=True), e.payload["outcome"]["status"])
            for e in events if str(e.event_type) == "ACTION_OUTCOME"]


def check_planner(ref: tuple[str, str] | Any, config: dict[str, Any] | None = None, *, package: Any = None,
                  environment: dict[str, Any] | None = None, max_steps: int = 12, registry: Any = None) -> ContractReport:
    from formal_lab_contracts import PluginRef
    from formal_lab_runtime import default_registry, make_manifest, resume_local, run_local
    from formal_lab_runtime.local_runner import LocalRunState

    reg = registry or default_registry()
    pref = ref if isinstance(ref, PluginRef) else PluginRef(plugin_id=ref[0], version=ref[1])
    report = ContractReport(f"{pref.plugin_id}@{pref.version}")
    pkg = package or _reference_package()
    cfg = dict(config or {})
    state: dict[str, Any] = {}

    def registered() -> str:
        entry = reg.resolve(pref)
        d = entry.descriptor
        assert str(d.interface) in ("PLANNER", "PluginInterface.PLANNER"), f"interface is {d.interface}, not PLANNER"
        reg.validate_config(pref, cfg, path="/config")
        return f"{d.interface} v{d.interface_version}, contract {d.contract_version}, {len(d.capabilities)} capability(ies)"

    def initialised() -> str:
        planner = reg.create(pref, cfg, _services(reg, pkg))
        assert hasattr(planner, "propose"), "the created object has no propose()"
        return type(planner).__name__

    def negotiated() -> str:
        sc = _scenario(pkg, {"plugin": pref.model_dump(mode="json"), "config": cfg}, environment, max_steps)
        m = make_manifest(run_id="run_contract", project_id="contract", scenario=sc, package=pkg, registry=reg, seed=0,
                          config={"initial_check_horizon": 0})
        state["manifest"] = m
        mine = [n for n in m.negotiation if n.plugin_id == pref.plugin_id]
        assert mine and all(n.compatible for n in mine), f"negotiation: {[n.reasons for n in mine]}"
        return f"compatible; granted {sorted({g for n in mine for g in n.granted})}"

    def observe_and_propose() -> str:
        part = run_local(state["manifest"], pkg, reg, stop_after=1)
        assert isinstance(part, LocalRunState), f"the run ended before its first step ({getattr(part, 'status', '?')})"
        props = [d for d in part.drafts if str(d.event_type) == "ACTION_PROPOSED"]
        cands = [d for d in part.drafts if str(d.event_type) == "CANDIDATES"]
        assert props, "no proposal in the first step"
        p = props[0].payload["proposal"]
        assert p["source"]["strategy"]["plugin_id"] == pref.plugin_id, "the proposal does not name the planner"
        offered = {json.dumps(c["action"], sort_keys=True) for c in cands[0].payload["candidates"]}
        assert json.dumps(p["action"], sort_keys=True) in offered, "the proposed action was not among the candidates"
        return f"proposed {p['action']['action_type']} from {len(offered)} candidate(s)"

    def advanced() -> str:
        res = run_local(state["manifest"], pkg, reg)
        state["full"] = res
        traj = _trajectory(res.events)
        assert traj, "no outcome was recorded"
        applied = sum(1 for _, _, st in traj if st == "APPLIED")
        return f"{len(traj)} step(s), {applied} applied"

    def recovered() -> str:
        full = state["full"]
        cut = max(1, len(_trajectory(full.events)) // 2)
        part = run_local(state["manifest"], pkg, reg, stop_after=cut)
        if not isinstance(part, LocalRunState):
            return "run shorter than one step boundary: nothing to recover"
        again = resume_local(json.loads(json.dumps(part.to_json())), pkg, reg)
        assert _trajectory(again.events) == _trajectory(full.events), "resumed trajectory differs from the uninterrupted one"
        return f"stopped after step {cut}, serialised, continued: identical trajectory"

    def finished() -> str:
        full = state["full"]
        assert str(full.status.value) in ("SUCCEEDED", "BUDGET_EXHAUSTED", "FAILED"), f"status {full.status}"
        assert full.metrics, "no metrics were computed"
        return f"{full.status.value} ({full.termination_reason.value if full.termination_reason else '—'}), " \
               f"{len(full.metrics)} metric(s)"

    for name, fn in (("registered", registered), ("initialised", initialised), ("negotiated", negotiated),
                     ("observe & propose", observe_and_propose), ("state advanced", advanced),
                     ("recovered", recovered), ("finished", finished)):
        report.run(name, fn)
    return report


def check_environment(ref: tuple[str, str] | Any, config: dict[str, Any] | None = None, *, package: Any = None,
                      registry: Any = None, seed: int = 0) -> ContractReport:
    from formal_lab_contracts import ActionProposal, PluginRef, ProposalSource
    from formal_lab_contracts import capabilities as caps
    from formal_lab_runtime import default_registry

    reg = registry or default_registry()
    pref = ref if isinstance(ref, PluginRef) else PluginRef(plugin_id=ref[0], version=ref[1])
    report = ContractReport(f"{pref.plugin_id}@{pref.version}")
    pkg = package or _reference_package()
    cfg = dict(config or {})
    st: dict[str, Any] = {}
    services = _services(reg, pkg)

    def registered() -> str:
        d = reg.resolve(pref).descriptor
        assert "ENVIRONMENT" in str(d.interface), f"interface is {d.interface}"
        reg.validate_config(pref, cfg, path="/environment/config")
        st["caps"] = {c.id for c in d.capabilities}
        return ", ".join(sorted(st["caps"]))

    def initialised() -> str:
        st["env"] = reg.create(pref, cfg, services)
        return type(st["env"]).__name__

    def reset_observe() -> str:
        sc = _scenario(pkg, {"plugin": {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.1.0"},
                             "config": {}}, {"plugin": pref.model_dump(mode="json"), "config": cfg}, 10)
        obs = st["env"].reset(sc, pkg, run_id="run_env_contract", seed=seed)
        st["obs"] = obs
        assert obs.facts or obs.unknowns, "the first observation is empty"
        return f"{len(obs.facts)} fact(s), {len(obs.unknowns)} unknown, revision {obs.state_revision}"

    def step() -> str:
        loaded = services.loaded_model()
        belief = loaded.belief(st["obs"])
        cands = [c for c in loaded.candidates(belief) if str(c.belief_applicability) == "APPLICABLE"]
        assert cands, "no applicable action on the first observation"
        prop = ActionProposal(proposal_id="p1", run_id="run_env_contract", step_id="s1", step=1, actor_id="agent",
                              action=cands[0].action, based_on_revision=st["obs"].state_revision,
                              source=ProposalSource(kind="RULE", strategy=pref), rationale="contract test")
        st["prop"] = prop
        out = st["env"].step(prop, operation_id="op-contract-1")
        assert str(out.status.value) == "APPLIED", f"{out.status}: {out.result.get('reason')}"
        assert (out.revision_after or 0) > out.revision_before, "the revision did not move"
        return f"{prop.action.action_type} applied, revision {out.revision_before}→{out.revision_after}"

    def snapshot_restore() -> str:
        snap = st["env"].snapshot()
        if snap.kind == "FULL_STATE":
            before = st["env"].truth_state() if hasattr(st["env"], "truth_state") else None
            st["env"].restore(snap)
            if before is not None:
                assert st["env"].truth_state() == before, "restored state differs"
            return "FULL_STATE snapshot restored exactly"
        assert caps.ENV_PERSISTENT_SESSION in st["caps"], "SESSION_MARKER without env.persistent_session"
        st["env"].attach(snap)
        return f"SESSION_MARKER re-attached (revision {snap.state_revision})"

    def lookup() -> str:
        if caps.ENV_QUERY_OPERATION not in st["caps"]:
            return "not declared (env.query_operation)"
        found = st["env"].query_operation("op-contract-1")
        assert found is not None and str(found.status.value) == "APPLIED", "the applied operation is not found"
        assert st["env"].query_operation("op-never-sent") is None, "an unknown operation id is reported as found"
        return "applied operation found by id; unknown id → None"

    def closed() -> str:
        st["env"].close()
        return "closed"

    for name, fn in (("registered", registered), ("initialised", initialised), ("reset & observe", reset_observe),
                     ("step", step), ("snapshot / restore", snapshot_restore), ("operation lookup", lookup),
                     ("closed", closed)):
        report.run(name, fn)
    return report
