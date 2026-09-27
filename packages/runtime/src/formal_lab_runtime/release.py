"""Model releases and regression cases (P2-072 … P2-076), shared by the platform and the CLI.

A release is the record of what was established about one model version (with an optional rule set) *before* it is
used: compilation by its semantic driver, type checks of the model and every rule, bounded queries on the model
itself (goals reachable, invariants within the bound, objectives), and the project's regression cases replayed on
it. `ModelReleaseRecord` states these facts — the bounds and assumptions they hold under, and the log — and the
verdict: RELEASED only when the model and rules type-check, every regression case passes and no check errored.
Query verdicts such as "an invariant can be violated within 6 steps" are facts of the record, not blockers: an
invariant of a scheduling model (e.g. "no order late") is a property worth knowing, not a requirement.

A regression case replays the recorded action(s) from the recorded state on a model version: PASS when the model
now predicts what was observed at every compared location (the difference is explained), FAIL otherwise.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from formal_lab_contracts import (
    CheckQuery,
    ModelPackage,
    ModelReleaseRecord,
    RegressionCase,
    RegressionResult,
    ReleaseCheck,
    RuleSet,
    StageRecord,
    digest_of,
    utcnow,
)
from formal_lab_contracts.errors import FormalLabError

from .registry import PluginRegistry


def _loaded(package: ModelPackage, registry: PluginRegistry) -> tuple[Any, list[str]]:
    entry = registry.driver_for(package.semantic_profile)
    driver = registry.create(entry.descriptor.ref(), {}, None)
    issues = list(driver.validate(package)) if hasattr(driver, "validate") else []
    return (driver.load(package) if not issues else None), issues


def replay_regression_case(case: RegressionCase, package: ModelPackage, registry: PluginRegistry,
                           loaded: Any = None) -> RegressionResult:
    try:
        if loaded is None:
            loaded, issues = _loaded(package, registry)
            if issues:
                return RegressionResult(case_id=case.case_id, status="ERROR",
                                        detail=f"model does not load: {issues[0]}")
        initial = loaded.initial_state()
        state = {**initial, **{k: v for k, v in case.initial_state.items() if k in initial}}
        for action in case.actions:
            pred = loaded.predict(state, action)
            if not pred.applicable or pred.next_state is None:
                return RegressionResult(case_id=case.case_id, status="FAIL",
                                        detail=f"{action.action_type} is not applicable on the recorded state "
                                               f"({pred.reason})")
            state = pred.next_state
    except FormalLabError as exc:
        return RegressionResult(case_id=case.case_id, status="ERROR", detail=exc.message[:300])
    wrong = {p: (state.get(p), case.observed[p]) for p in case.compared_paths if state.get(p) != case.observed.get(p)}
    if wrong:
        shown = ", ".join(f"{p}: predicts {a!r}, observed {b!r}" for p, (a, b) in list(wrong.items())[:4])
        return RegressionResult(case_id=case.case_id, status="FAIL", detail=f"still differs — {shown}")
    return RegressionResult(case_id=case.case_id, status="PASS",
                            detail=f"predicts the observed values at {len(case.compared_paths)} location(s)")


def check_release(package: ModelPackage, registry: PluginRegistry, *, ruleset: RuleSet | None = None,
                  cases: list[RegressionCase] | None = None, horizon: int = 6, timeout_ms: int = 10000,
                  verifier_ref: Any = None) -> tuple[ModelReleaseRecord, list[str]]:
    """Run every pre-release check; returns the record and the log lines (the platform stores the log as an
    artifact and references it from the record)."""
    from formal_lab_contracts import ExecutionStage, RetrySemantics, StageStatus

    log: list[str] = []
    checks: list[ReleaseCheck] = []
    stages: list[StageRecord] = []
    reasons: list[str] = []

    def stage(name: str, t0: float, ok: bool, note: str) -> None:
        stages.append(StageRecord(stage=ExecutionStage.CHECK, status=StageStatus.OK if ok else StageStatus.FAILED,
                                  retry=RetrySemantics.IDEMPOTENT, elapsed_ms=(time.perf_counter() - t0) * 1000,
                                  note=f"{name}: {note}"[:300]))
        log.append(f"[{name}] {note}")

    # 1. compile / type check through the semantic driver
    t0 = time.perf_counter()
    loaded, issues = _loaded(package, registry)
    checks.append(ReleaseCheck(kind="TYPE_CHECK", subject=f"{package.package_id}@{package.version}",
                               verdict="OK" if not issues else "INVALID", passed=not issues,
                               detail="; ".join(issues[:5]) or None))
    if issues:
        reasons.append(f"model does not type-check: {issues[0]}")
    stage("type-check", t0, not issues, f"{len(issues)} issue(s)")
    compiled = []
    if loaded is not None:
        from formal_lab_contracts import CompiledArtifact

        drv = registry.driver_for(package.semantic_profile).descriptor
        compiled.append(CompiledArtifact(backend=drv.plugin_id, backend_version=drv.version, digest=package.digest,
                                         stats={"state_locations": len(loaded.state_paths()),
                                                "ground_actions": len(loaded.ground_actions()),
                                                "properties": len(loaded.property_kinds())}))
    # 2. rules against the model
    if ruleset is not None and loaded is not None and hasattr(loaded, "checked"):
        from formal_lab_model.rules import check_rule, ruleset_digest

        t0 = time.perf_counter()
        bad = 0
        for rule in ruleset.rules:
            problems = check_rule(rule, loaded.checked)
            bad += bool(problems)
            checks.append(ReleaseCheck(kind="RULE_CHECK", subject=rule.rule_id, verdict="OK" if not problems
                                       else "INVALID", passed=not problems,
                                       detail="; ".join(p.message for p in problems[:3]) or None))
        if bad:
            reasons.append(f"{bad} rule(s) of {ruleset.ruleset_id}@{ruleset.version} do not type-check")
        stage("rules", t0, not bad, f"{len(ruleset.rules)} rule(s), digest {ruleset_digest(ruleset)[:12]}")
    # 3. bounded queries on the model itself (facts, within the stated bound)
    if loaded is not None and package.is_ir:
        from formal_lab_contracts import QueryKind

        fitting = sorted({e.descriptor.plugin_id for e in registry.entries("VERIFIER")
                          if package.semantic_profile in e.descriptor.semantic_profiles})
        verifier_entry = registry.resolve(verifier_ref) if verifier_ref else \
            (registry.latest(fitting[0]) if fitting else None)
        if verifier_entry is not None:
            verifier = registry.create(verifier_entry.descriptor.ref(), {}, None)
            kinds = loaded.property_kinds()
            bound = {"max_steps": horizon, "timeout_ms": timeout_ms}
            for prop, kind in sorted(kinds.items()):
                t0 = time.perf_counter()
                qkind = QueryKind.GOAL_REACHABILITY if kind == "goal" else QueryKind.INVARIANT_VIOLATION
                try:
                    res = verifier.check(package, CheckQuery(kind=qkind, property_id=prop, bound=bound))
                    verdict, detail = str(res.verdict), res.explanation
                    ok = verdict not in ("ERROR",)
                except FormalLabError as exc:
                    verdict, detail, ok = "ERROR", exc.message, False
                checks.append(ReleaseCheck(kind=qkind, subject=prop, bound=bound, verdict=verdict, passed=ok,
                                           detail=(detail or "")[:300]))
                if not ok:
                    reasons.append(f"check {qkind.value} {prop} errored: {detail}")
                stage(f"{qkind.value.lower()}:{prop}", t0, ok, f"{verdict} within {horizon} steps")
            for obj in package.ir.objectives:
                checks.append(ReleaseCheck(kind="OBJECTIVE_CHECK", subject=obj.id, verdict="DECLARED", passed=True,
                                           detail=f"{len(obj.terms)} term(s), unit {obj.unit or '—'}"))
    # 4. regression cases
    regression: list[RegressionResult] = []
    if cases:
        t0 = time.perf_counter()
        for case in cases:
            regression.append(replay_regression_case(case, package, registry, loaded=loaded))
        failed = [r for r in regression if r.status != "PASS"]
        if failed:
            reasons.append(f"{len(failed)} of {len(regression)} regression case(s) do not pass: "
                           + "; ".join(f"{r.case_id} {r.status}" for r in failed[:3]))
        stage("regression", t0, not failed, f"{len(regression) - len(failed)}/{len(regression)} pass")
    status = "RELEASED" if not reasons else "REJECTED"
    body = {"model": package.ref().model_dump(mode="json"), "ruleset": ruleset.digest.value if ruleset and
            ruleset.digest else None, "checks": [c.model_dump(mode="json") for c in checks],
            "regression": [r.model_dump(mode="json") for r in regression]}
    release_id = "rel_" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    from formal_lab_contracts import RuleSetRef

    record = ModelReleaseRecord(
        release_id=release_id, model=package.ref(),
        ruleset=RuleSetRef(ruleset_id=ruleset.ruleset_id, version=ruleset.version, digest=ruleset.digest)
        if ruleset is not None and ruleset.digest is not None else None,
        driver=registry.driver_for(package.semantic_profile).descriptor.ref(), compiled=compiled, checks=checks,
        regression=regression, bounds=[f"bounded queries: max_steps={horizon}, timeout_ms={timeout_ms}"],
        assumptions=["checks hold for the model itself (scope MODEL_INTERNAL), not for any environment",
                     "regression cases replay recorded states and actions; their observed values are the evidence"],
        status=status, reasons=reasons, digest=digest_of(body), created_at=utcnow(), stages=stages)
    log.append(f"[verdict] {status}" + (f": {'; '.join(reasons)}" if reasons else ""))
    return record, log
