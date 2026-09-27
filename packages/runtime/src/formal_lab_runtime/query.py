"""Replayable query bundles (P2-029): run a check with everything it depends on recorded, and replay it later.

A QueryBundle holds the model reference, driver and verifier versions, the query, the start state, the unknown
locations, the assumption set, the result (with witness / counterexample / optimisation bounds) and the shared
explanation lines. `replay_query` re-asks the same verifier version on the same inputs and independently replays
the witness with the model's semantic driver, reporting any difference.
"""

from __future__ import annotations

import uuid
from typing import Any

from formal_lab_contracts import (
    AssumptionSet,
    CheckQuery,
    ModelPackage,
    PluginInterface,
    PluginRef,
    QueryBundle,
    StateScalar,
    utcnow,
)

from .registry import PluginRegistry

DEFAULT_VERIFIER = PluginRef(plugin_id="formal-lab.verifier.z3-bmc", version="1.1.0")


def _explain(result) -> list[str]:
    from formal_lab_model.explain import explain_check

    return explain_check(result)


def run_query(registry: PluginRegistry, package: ModelPackage, query: CheckQuery, *,
              verifier: PluginRef | None = None, state: dict[str, StateScalar] | None = None,
              unknown_paths: list[str] | None = None, assumptions: AssumptionSet | None = None,
              services: Any = None) -> QueryBundle:
    entry = registry.resolve(verifier or DEFAULT_VERIFIER)
    plugin = registry.create(entry.descriptor.ref(), {}, services, expect=PluginInterface.VERIFIER)
    result = plugin.check(package, query, state=state, unknown_paths=unknown_paths)
    if assumptions is not None and result.assumption_set is None:
        result = result.model_copy(update={"assumption_set": assumptions})
    driver = None
    try:
        driver = registry.driver_for(package.semantic_profile).descriptor.ref()
    except Exception:  # no driver for the profile: the bundle still records the answer (UNSUPPORTED)
        driver = None
    bundle = QueryBundle(bundle_id=f"qb_{uuid.uuid4().hex[:20]}", created_at=utcnow(), model=package.ref(),
                         driver=driver, verifier=entry.descriptor.ref(), query=query, state=state,
                         unknown_paths=sorted(unknown_paths or []), assumptions=assumptions, result=result,
                         explanation=_explain(result))
    return bundle.model_copy(update={"replay": _witness_replay(registry, package, bundle)})


def _witness_replay(registry: PluginRegistry, package: ModelPackage, bundle: QueryBundle) -> dict[str, Any]:
    """Independent replay of the witness with the semantic driver (not the solver)."""
    w = bundle.result.witness
    if w is None:
        return {"witness": "none"}
    try:
        driver = registry.create(registry.driver_for(package.semantic_profile).descriptor.ref(), {}, None,
                                 expect=PluginInterface.SEMANTIC_DRIVER)
        loaded = driver.load(package)
    except Exception as exc:
        return {"witness": "NOT_REPLAYED", "note": f"no driver: {exc}"}
    state = dict(w.steps[0].state)
    for i, step in enumerate(w.steps[1:], start=1):
        pred = loaded.predict(state, step.action)
        if not pred.applicable:
            return {"witness": "REFUTED", "note": f"step {i} ({step.action.action_type}) inapplicable: {pred.reason}"}
        state = pred.next_state
        if state != step.state:
            return {"witness": "REFUTED", "note": f"state after step {i} differs"}
    return {"witness": "CONFIRMED", "note": f"{len(w.steps) - 1} step(s) replayed by the semantic driver"}


def replay_query(registry: PluginRegistry, package: ModelPackage, bundle: QueryBundle, *,
                 services: Any = None) -> dict[str, Any]:
    """Re-run the recorded query and compare. The package must be the recorded model (digest-checked)."""
    if package.digest != bundle.model.digest:
        return {"same": False, "reason": "model digest differs from the bundle's model"}
    again = run_query(registry, package, bundle.query, verifier=bundle.verifier, state=bundle.state,
                      unknown_paths=bundle.unknown_paths, assumptions=bundle.assumptions, services=services)
    before, after = bundle.result, again.result
    same_verdict = str(before.verdict) == str(after.verdict)
    values_before = {lv.level: lv.value for lv in before.optimization.levels} if before.optimization else None
    values_after = {lv.level: lv.value for lv in after.optimization.levels} if after.optimization else None
    optimal_before = [lv.optimal for lv in before.optimization.levels] if before.optimization else None
    comparable = values_before is None or not (all(optimal_before or []) and values_before != values_after)
    return {"same": same_verdict and comparable, "verdict_before": str(before.verdict),
            "verdict_after": str(after.verdict), "values_before": values_before, "values_after": values_after,
            "witness_replay": again.replay, "verifier": bundle.verifier.model_dump(),
            "note": "a FEASIBLE (timed-out) optimisation may improve on replay; OPTIMAL values must be equal"}
