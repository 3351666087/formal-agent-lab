"""Bounded queries over deterministic_finite_v1 models with Z3, exposed as a Verifier plugin.

Query semantics (all conclusions are MODEL_INTERNAL and bounded):
- GOAL_REACHABILITY (EXISTS_PATH): is there a path of ≤ k actions from the initial state to a state where
  the goal holds? WITNESS = shortest such path; NO_WITNESS_WITHIN_BOUND = no path of length ≤ k exists.
- INVARIANT_VIOLATION (ALL_PATHS): do all paths of ≤ k actions keep the invariant? Answered by searching a
  violating path: WITNESS = shortest counterexample; NO_WITNESS_WITHIN_BOUND = every path of length ≤ k
  satisfies the invariant (nothing is claimed beyond k).
- ACTION_PRECONDITION (SINGLE_STEP): is the ground action applicable in the given state? Unknown locations
  are free variables: APPLICABLE if applicable in every completion, INAPPLICABLE in none, else UNKNOWN.
"""

from __future__ import annotations

import time
import uuid
from functools import lru_cache
from typing import Any

import z3
from formal_lab_contracts import (
    BackendInfo,
    BoundedCheckResult,
    CheckBound,
    CheckQuery,
    GroundAction as CGroundAction,
    ModelPackage,
    PluginDescriptor,
    PreconditionVerdict,
    QUERY_SEMANTICS,
    QueryKind,
    SearchVerdict,
    SolverStats,
    StateScalar,
    UnsupportedInfo,
    Witness,
    WitnessStep,
    digest_of,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import InvalidInput
from formal_lab_model import Interpreter, check_model
from formal_lab_model.checker import CheckedModel, GroundAction

from .compiler import Z3Model

VERIFIER_ID = "formal-lab.verifier.z3-bmc"
VERIFIER_VERSION = "1.0.0"
Z3_VERSION = z3.get_version_string()
BACKEND = BackendInfo(name="z3", version=Z3_VERSION)

DESCRIPTOR = PluginDescriptor(
    plugin_id=VERIFIER_ID,
    version=VERIFIER_VERSION,
    interface="VERIFIER",
    capabilities=[
        {"id": caps.PROFILE_DETERMINISTIC_FINITE_V1},
        {"id": caps.QUERY_GOAL_REACHABILITY},
        {"id": caps.QUERY_INVARIANT_VIOLATION},
        {"id": caps.QUERY_ACTION_PRECONDITION},
        {"id": caps.QUERY_PARTIAL_STATE},
    ],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "properties": {"default_timeout_ms": {"type": "integer", "minimum": 1}}},
    entrypoint="formal_lab_solver_z3.verifier:create",
    ui={"label": "Z3 bounded checker", "category": "verifier",
        "description": "Bounded model checking (incremental unrolling) with interpreter-replayed witnesses"},
    license="MIT (z3) / Apache-2.0 (adapter)",
    source="formal-lab-solver-z3",
)


@lru_cache(maxsize=32)
def _compiled(digest: str, ir_json: str) -> tuple[CheckedModel, Z3Model, Interpreter]:
    from formal_lab_contracts import ModelIR

    checked = check_model(ModelIR.model_validate_json(ir_json))
    return checked, Z3Model(checked), Interpreter(checked)


def compile_package(package: ModelPackage) -> tuple[CheckedModel, Z3Model, Interpreter]:
    return _compiled(package.digest.value, package.ir.model_dump_json())


def _to_contract_action(ga: GroundAction) -> CGroundAction:
    return CGroundAction(action_type=ga.action, params=dict(ga.params))


class Z3Verifier:
    descriptor = DESCRIPTOR

    def __init__(self, default_timeout_ms: int = 10_000):
        self.default_timeout_ms = default_timeout_ms

    # ------------------------------------------------------------------ entry point
    def check(
        self,
        package: ModelPackage,
        query: CheckQuery,
        *,
        state: dict[str, StateScalar] | None = None,
        unknown_paths: list[str] | None = None,
    ) -> BoundedCheckResult:
        t0 = time.perf_counter()
        checked = check_model(package.ir)
        unsupported = [i for i in checked.issues if i.code in ("UNSUPPORTED_PROFILE", "UNSUPPORTED_FEATURE")]
        if unsupported:
            return self._unsupported(package, query, unsupported[0].message, t0)
        if checked.issues:
            raise InvalidInput("model has issues", details={"issues": [i.model_dump() for i in checked.issues]})
        checked, zm, interp = compile_package(package)
        if query.kind is QueryKind.ACTION_PRECONDITION:
            return self._precondition(package, query, zm, interp, state, unknown_paths or [], t0)
        if query.property_id not in checked.properties:
            raise InvalidInput(f"unknown property {query.property_id!r}")
        return self._search(package, query, zm, interp, state, t0)

    # ------------------------------------------------------------------ helpers
    def _base(self, package: ModelPackage, query: CheckQuery, **kw: Any) -> dict[str, Any]:
        return dict(
            check_id=f"chk_{uuid.uuid4().hex[:16]}",
            query=query,
            semantics=QUERY_SEMANTICS[query.kind],
            bound=query.bound,
            model_digest=package.digest,
            backend=BACKEND,
            **kw,
        )

    def _unsupported(self, package: ModelPackage, query: CheckQuery, reason: str, t0: float) -> BoundedCheckResult:
        return BoundedCheckResult(
            **self._base(package, query),
            verdict="UNSUPPORTED",
            stats=SolverStats(solver_status="not-run", elapsed_ms=(time.perf_counter() - t0) * 1000),
            unsupported=UnsupportedInfo(feature="semantic_profile", reason=reason,
                                        extension_point="Verifier plugin declaring the required profile capability"),
            explanation=f"not checked: {reason}",
        )

    def _timeout(self, query: CheckQuery) -> int:
        return query.bound.timeout_ms or self.default_timeout_ms

    # ------------------------------------------------------------------ bounded search
    def _search(self, package, query, zm: Z3Model, interp: Interpreter, state, t0) -> BoundedCheckResult:
        k_max = query.bound.max_steps
        timeout_ms = self._timeout(query)
        deadline = t0 + timeout_ms / 1000
        goal_kind = query.kind is QueryKind.GOAL_REACHABILITY
        start_state = dict(state) if (query.initial_state == "GIVEN_STATE" and state) else interp.initial_state()
        if query.initial_state == "GIVEN_STATE" and state is None:
            raise InvalidInput("initial_state=GIVEN_STATE requires a state")
        solver = z3.Solver()
        S = [zm.state_vars(0)]
        solver.add(*zm.domain_constraints(S[0]))
        solver.add(*zm.fix_state(S[0], start_state))
        acts: list[z3.ArithRef] = []
        status = "unknown"
        reason = None
        explored = 0
        for k in range(k_max + 1):
            if k > 0:
                S.append(zm.state_vars(k))
                act, cons = zm.transition(k - 1, S[k - 1], S[k])
                acts.append(act)
                solver.add(*cons)
            remaining = int((deadline - time.perf_counter()) * 1000)
            if remaining <= 0:
                status, reason = "unknown", "timeout"
                break
            solver.set("timeout", remaining)
            target = zm.prop(query.property_id, S[k])
            solver.push()
            solver.add(target if goal_kind else z3.Not(target))
            res = solver.check()
            explored = k
            if res == z3.sat:
                model = solver.model()
                witness = self._witness(zm, interp, model, S, acts, k, query.property_id, goal_kind)
                solver.pop()
                return BoundedCheckResult(
                    **self._base(package, query),
                    verdict=SearchVerdict.WITNESS,
                    witness=witness,
                    state_digest=digest_of(start_state),
                    assumptions=self._assumptions(query),
                    variable_mapping=self._mapping(zm, k),
                    stats=SolverStats(solver_status="sat", steps_explored=k, timeout_ms=timeout_ms,
                                      elapsed_ms=(time.perf_counter() - t0) * 1000),
                    explanation=(f"shortest {'path to goal' if goal_kind else 'counterexample'} "
                                 f"{query.property_id!r} has {k} step(s)"),
                )
            solver.pop()
            if res == z3.unknown:
                status, reason = "unknown", solver.reason_unknown() or "unknown"
                break
            status = "unsat"
        else:
            return BoundedCheckResult(
                **self._base(package, query),
                verdict=SearchVerdict.NO_WITNESS_WITHIN_BOUND,
                state_digest=digest_of(start_state),
                assumptions=self._assumptions(query),
                stats=SolverStats(solver_status="unsat", steps_explored=k_max, timeout_ms=timeout_ms,
                                  elapsed_ms=(time.perf_counter() - t0) * 1000),
                explanation=(
                    f"no path of ≤ {k_max} step(s) reaches {query.property_id!r}" if goal_kind
                    else f"every path of ≤ {k_max} step(s) satisfies {query.property_id!r}"
                ) + " (bounded conclusion; nothing is claimed for longer paths)",
            )
        timed_out = reason is not None and ("timeout" in reason or "canceled" in reason)
        return BoundedCheckResult(
            **self._base(package, query),
            verdict=SearchVerdict.UNKNOWN,
            state_digest=digest_of(start_state),
            assumptions=self._assumptions(query),
            stats=SolverStats(solver_status=status, steps_explored=explored, timeout_ms=timeout_ms,
                              reason_unknown="timeout" if timed_out else reason,
                              elapsed_ms=(time.perf_counter() - t0) * 1000),
            explanation=f"solver returned unknown after exploring {explored} step(s): "
            + ("timeout" if timed_out else str(reason)),
        )

    def _witness(self, zm: Z3Model, interp: Interpreter, model, S, acts, k, prop, goal_kind) -> Witness:
        steps: list[WitnessStep] = []
        actions: list[GroundAction] = []
        for t in range(k + 1):
            state = {p: zm.decode_value(p, model.eval(S[t][p], model_completion=True)) for p in zm.state_paths}
            ga = None
            if t > 0:
                ga = zm.actions[model.eval(acts[t - 1], model_completion=True).as_long()]
                actions.append(ga)
            steps.append(WitnessStep(step=t, action=_to_contract_action(ga) if ga else None, state=state))
        # independent confirmation with the reference interpreter
        replayed, failed_at = interp.replay(steps[0].state, actions)
        if failed_at is not None:
            return Witness(steps=steps, replay="REFUTED", replay_note=f"action {failed_at + 1} inapplicable on replay")
        if replayed[-1] != steps[-1].state:
            return Witness(steps=steps, replay="REFUTED", replay_note="final state differs on replay")
        holds = interp.holds(prop, replayed[-1])
        if holds != goal_kind:
            return Witness(steps=steps, replay="REFUTED", replay_note="property value differs on replay")
        return Witness(steps=steps, replay="CONFIRMED", replay_note="replayed by the reference interpreter")

    def _mapping(self, zm: Z3Model, k: int) -> dict[str, str]:
        mapping = {f"{p}@t": p for p in zm.state_paths}
        mapping["act@t"] = "index into ground actions: " + ", ".join(ga.key for ga in zm.actions[:50])
        return mapping

    def _assumptions(self, query: CheckQuery) -> list[str]:
        start = "the given state" if query.initial_state == "GIVEN_STATE" else "the model initial state"
        return [
            f"paths start in {start}",
            "one ground action per logical step; deterministic effects as specified by deterministic_finite_v1",
            f"only paths of at most {query.bound.max_steps} step(s) are considered",
        ]

    # ------------------------------------------------------------------ single-step precondition
    def _precondition(self, package, query, zm: Z3Model, interp: Interpreter, state, unknown_paths, t0):
        if state is None:
            state = interp.initial_state() if query.initial_state == "MODEL_INITIAL" else None
        if state is None:
            raise InvalidInput("ACTION_PRECONDITION with GIVEN_STATE requires a state")
        a = query.action
        assert a is not None
        try:
            ga = interp.ground(a.action_type, dict(a.params))
        except KeyError as exc:
            raise InvalidInput(str(exc)) from exc
        idx = zm.actions.index(ga)
        timeout_ms = self._timeout(query)
        S = zm.state_vars(0)
        known = {p: v for p, v in state.items() if p not in set(unknown_paths)}
        base = [*zm.domain_constraints(S), *zm.fix_state(S, known)]
        enabled = zm.enabled(idx, S)
        enabled = z3.BoolVal(enabled) if isinstance(enabled, bool) else enabled
        results = {}
        for label, formula in (("can", enabled), ("cannot", z3.Not(enabled))):
            solver = z3.Solver()
            solver.set("timeout", timeout_ms)
            solver.add(*base, formula)
            results[label] = solver.check()
            if results[label] == z3.unknown:
                reason = solver.reason_unknown()
                return BoundedCheckResult(
                    **self._base(package, query),
                    verdict=PreconditionVerdict.UNKNOWN,
                    state_digest=digest_of(state),
                    action_digest=digest_of(a),
                    assumptions=[f"unknown locations: {sorted(unknown_paths)}"],
                    stats=SolverStats(solver_status="unknown", reason_unknown=reason, timeout_ms=timeout_ms,
                                      elapsed_ms=(time.perf_counter() - t0) * 1000),
                    explanation=f"solver returned unknown: {reason}",
                )
        can, cannot = results["can"] == z3.sat, results["cannot"] == z3.sat
        if can and not cannot:
            verdict, text = PreconditionVerdict.APPLICABLE, "applicable in every completion of the unknown facts"
        elif cannot and not can:
            verdict, text = PreconditionVerdict.INAPPLICABLE, "inapplicable in every completion of the unknown facts"
        else:
            verdict, text = PreconditionVerdict.UNKNOWN, "applicability depends on unknown facts (insufficient evidence)"
        if not unknown_paths:
            text = "precondition and domain guards evaluated on a fully known state"
        return BoundedCheckResult(
            **self._base(package, query),
            verdict=verdict,
            state_digest=digest_of(state),
            action_digest=digest_of(a),
            assumptions=[f"unknown locations treated as free: {sorted(unknown_paths)}"] if unknown_paths else [
                "state fully known"],
            stats=SolverStats(solver_status=f"can={results['can']},cannot={results['cannot']}", timeout_ms=timeout_ms,
                              elapsed_ms=(time.perf_counter() - t0) * 1000),
            explanation=text,
        )


def create(config: dict[str, Any] | None = None, services: Any = None) -> Z3Verifier:
    return Z3Verifier(**(config or {}))


__all__ = ["DESCRIPTOR", "Z3Verifier", "compile_package", "create", "CheckBound"]
