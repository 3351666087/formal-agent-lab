"""Model releases and regression cases (P2-072 … P2-076), shared by the platform and the CLI.

A release is the record of what was established about one model version (with an optional rule set) *before* it is
used: compilation by its semantic driver, type checks of the model and every rule, bounded queries on the model
itself (goals reachable, invariants within the bound, objectives), and the project's regression cases replayed on
it. `ModelReleaseRecord` states these facts — the bounds and assumptions they hold under, and the log — and the
verdict: RELEASED only when the model and rules type-check, every regression case passes and no check errored.
Query verdicts such as "an invariant can be violated within 6 steps" are facts of the record, not blockers: an
invariant of a scheduling model (e.g. "no order late") is a property worth knowing, not a requirement — unless the
release config names it in `required_holds`.

Phase 3A (G3): what can run is decided by a capability report built only from declared capabilities (the driver's
`driver.*`, the verifiers' `query.*` for the model's profile) and the public LoadedModel protocol — never from the
payload's shape. A check without its capability is recorded as UNSUPPORTED (executed False); when the config
requires it, `process_completed` is False and the release is REJECTED with the reason. "The process completed" and
"a property holds" are separate fields (`process_completed`, per check `property_holds` / `claim`).

A regression case replays the recorded action(s) from the recorded state on a model version: PASS when the model
now predicts what was observed at every compared location (the difference is explained), FAIL otherwise.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from formal_lab_contracts import (
    CapabilityReport,
    CheckQuery,
    FeatureSupport,
    ModelPackage,
    ModelReleaseRecord,
    RegressionCase,
    RegressionResult,
    ReleaseCheck,
    ReleaseConfig,
    RuleSet,
    StageRecord,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
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


# ---------------------------------------------------------------------------- capability report (phase 3A, G3)

QUERY_FEATURES = {"GOAL_REACHABILITY": caps.QUERY_GOAL_REACHABILITY,
                  "INVARIANT_VIOLATION": caps.QUERY_INVARIANT_VIOLATION,
                  "ACTION_PRECONDITION": caps.QUERY_ACTION_PRECONDITION,
                  "OPTIMIZE_OBJECTIVE": caps.QUERY_OPTIMIZE_OBJECTIVE,
                  "ROBUST_SEQUENCE": caps.QUERY_ROBUST_SEQUENCE}


def _verifier_for(package: ModelPackage, registry: PluginRegistry, capability: str, verifier_ref: Any = None):
    """The verifier that answers `capability` for this profile: the given one if it declares both, else the first
    installed verifier (by id) that does."""
    profile = package.semantic_profile
    if verifier_ref is not None:
        entries = [registry.resolve(verifier_ref)]
    else:
        entries = sorted((registry.latest(e.descriptor.plugin_id) for e in registry.entries("VERIFIER")),
                         key=lambda e: e.descriptor.plugin_id)
    for e in entries:
        d = e.descriptor
        if profile in d.semantic_profiles and d.has_capability(capability):
            return e
    return None


def capability_report(package: ModelPackage, registry: PluginRegistry, verifier_ref: Any = None) -> CapabilityReport:
    """What the platform can do with this model, feature by feature, from declared capabilities only (G3): the
    semantic driver's `driver.*` capabilities and the verifiers' `query.*` capabilities for the model's profile."""
    entry = registry.driver_for(package.semantic_profile)
    d = entry.descriptor
    have = {c.id for c in d.capabilities}
    out: list[FeatureSupport] = []

    def driver_feature(feature: str, needs: list[str], why: str, missing: str) -> None:
        ok = set(needs) <= have
        out.append(FeatureSupport(feature=feature, status="SUPPORTED" if ok else "UNSUPPORTED",
                                  provider=d.ref() if ok else None, requires=needs,
                                  reason=why if ok else f"{d.plugin_id} does not declare {missing}"))

    out.append(FeatureSupport(feature="release.type_check", status="SUPPORTED", provider=d.ref(), requires=[],
                              reason=f"{d.plugin_id} validates {package.semantic_profile} payloads"))
    driver_feature("run.candidates", [caps.DRIVER_CANDIDATES], "ground candidates with applicability on a belief",
                   caps.DRIVER_CANDIDATES)
    driver_feature("run.predict", [caps.DRIVER_PREDICT], "predicted effects for effect comparison",
                   caps.DRIVER_PREDICT)
    driver_feature("release.regression_replay", [caps.DRIVER_PREDICT],
                   "regression cases are replayed through the driver's predict()", caps.DRIVER_PREDICT)
    driver_feature("rules", [caps.DRIVER_IR], "rules are type-checked and evaluated on the neutral IR",
                   f"{caps.DRIVER_IR} (rule evaluation needs the neutral IR)")
    driver_feature("release.objectives", [caps.DRIVER_IR], "cost objectives are declared in the neutral IR",
                   f"{caps.DRIVER_IR} (objectives are part of the neutral IR)")
    driver_feature("release.stats", [caps.DRIVER_STATS], "sizes from the loaded model's stats()",
                   f"{caps.DRIVER_STATS} (release records then count only protocol-level sizes)")
    for kind, capability in QUERY_FEATURES.items():
        v = _verifier_for(package, registry, capability, verifier_ref)
        out.append(FeatureSupport(
            feature=f"query.{kind.lower()}", status="SUPPORTED" if v else "UNSUPPORTED",
            provider=v.descriptor.ref() if v else None, requires=[f"{caps.PROFILE_PREFIX}{package.semantic_profile}",
                                                                 capability],
            reason=(f"{v.descriptor.plugin_id} declares {capability} for {package.semantic_profile}" if v else
                    f"no installed verifier declares {capability} for profile {package.semantic_profile}")))
    return CapabilityReport(model=package.ref(), semantic_profile=package.semantic_profile, driver=d.ref(),
                            features=out, generated_at=utcnow())


def _feature(report: CapabilityReport, name: str) -> FeatureSupport:
    return next(f for f in report.features if f.feature == name)


def _query_claim(kind: str, prop: str, verdict: str, horizon: int) -> tuple[bool | None, str]:
    """What a bounded query result says about its property — and only that (G3)."""
    if kind == "GOAL_REACHABILITY":
        if verdict == "WITNESS":
            return True, f"goal {prop} is reachable within {horizon} steps (witness found)"
        if verdict == "NO_WITNESS_WITHIN_BOUND":
            return False, f"goal {prop} is not reachable within {horizon} steps (nothing claimed beyond the bound)"
    if kind == "INVARIANT_VIOLATION":
        if verdict == "WITNESS":
            return False, f"invariant {prop} can be violated within {horizon} steps (counterexample found)"
        if verdict == "NO_WITNESS_WITHIN_BOUND":
            return True, f"invariant {prop} holds on every path of up to {horizon} steps"
    return None, f"{verdict}: no claim about {prop}"


def check_release(package: ModelPackage, registry: PluginRegistry, *, ruleset: RuleSet | None = None,
                  cases: list[RegressionCase] | None = None, horizon: int | None = None,
                  timeout_ms: int | None = None, verifier_ref: Any = None,
                  config: ReleaseConfig | None = None) -> tuple[ModelReleaseRecord, list[str]]:
    """Run the pre-release checks the capability report allows; returns the record and the log lines (the platform
    stores the log as an artifact and references it from the record).

    Required checks (config.required_checks, plus RULE_CHECK with a rule set and REGRESSION with cases) must run
    and give a conclusive result; a missing capability or result leaves `process_completed` False and the release
    REJECTED with the reason. Whether a property holds is recorded per check (`property_holds`, `claim`) and blocks
    the release only for properties in config.required_holds."""
    from formal_lab_contracts import ExecutionStage, RetrySemantics, StageStatus

    cfg = config or ReleaseConfig(horizon=horizon or 6, timeout_ms=timeout_ms or 10000)
    if horizon is not None or timeout_ms is not None:
        cfg = cfg.model_copy(update={"horizon": horizon or cfg.horizon, "timeout_ms": timeout_ms or cfg.timeout_ms})
    required = set(cfg.required_checks) | ({"RULE_CHECK"} if ruleset is not None else set()) | \
        ({"REGRESSION"} if cases else set())
    bound = {"max_steps": cfg.horizon, "timeout_ms": cfg.timeout_ms}
    scope = f"MODEL_INTERNAL, paths of up to {cfg.horizon} steps"
    log: list[str] = []
    checks: list[ReleaseCheck] = []
    stages: list[StageRecord] = []
    reasons: list[str] = []
    incomplete: list[str] = []
    report = capability_report(package, registry, verifier_ref)
    driver_ref = report.driver

    def stage(name: str, t0: float, ok: bool, note: str) -> None:
        stages.append(StageRecord(stage=ExecutionStage.CHECK, status=StageStatus.OK if ok else StageStatus.FAILED,
                                  retry=RetrySemantics.IDEMPOTENT, elapsed_ms=(time.perf_counter() - t0) * 1000,
                                  note=f"{name}: {note}"[:300]))
        log.append(f"[{name}] {note}")

    def unsupported(kind: str, subject: str, feature: str) -> None:
        f = _feature(report, feature)
        is_required = kind in required
        checks.append(ReleaseCheck(kind=kind, subject=subject, verdict="UNSUPPORTED", passed=not is_required,
                                   required=is_required, executed=False, detail=f.reason, scope=scope))
        log.append(f"[{kind.lower()}:{subject}] UNSUPPORTED — {f.reason}")
        if is_required:
            incomplete.append(f"required check {kind} ({subject}) cannot run: {f.reason}")

    # 1. compile / type check through the semantic driver
    t0 = time.perf_counter()
    loaded, issues = _loaded(package, registry)
    checks.append(ReleaseCheck(kind="TYPE_CHECK", subject=f"{package.package_id}@{package.version}",
                               verdict="OK" if not issues else "INVALID", passed=not issues,
                               required="TYPE_CHECK" in required, backend=driver_ref, scope="the model payload",
                               property_holds=not issues, claim="the payload is valid for its profile" if not issues
                               else f"{len(issues)} problem(s): {issues[0]}", detail="; ".join(issues[:5]) or None))
    if issues:
        reasons.append(f"model does not type-check: {issues[0]}")
    stage("type-check", t0, not issues, f"{len(issues)} issue(s)")
    compiled = []
    if loaded is not None:
        from formal_lab_contracts import CompiledArtifact

        stats: dict[str, Any] = {"state_locations": len(loaded.state_paths()),
                                 "action_types": len(loaded.action_specs()),
                                 "properties": len(loaded.property_kinds())}
        if report.status("release.stats") == "SUPPORTED" and hasattr(loaded, "stats"):
            stats.update(loaded.stats())
        compiled.append(CompiledArtifact(backend=driver_ref.plugin_id, backend_version=driver_ref.version,
                                         digest=package.digest, stats=stats))
    # 2. rules against the model
    if ruleset is not None and loaded is not None:
        if report.status("rules") == "SUPPORTED":
            from formal_lab_model.rules import check_rule, ruleset_digest

            t0 = time.perf_counter()
            bad = 0
            for rule in ruleset.rules:
                problems = check_rule(rule, loaded.checked)
                bad += bool(problems)
                checks.append(ReleaseCheck(kind="RULE_CHECK", subject=rule.rule_id, verdict="OK" if not problems
                                           else "INVALID", passed=not problems, required=True, backend=driver_ref,
                                           scope="the rule against the model's IR", property_holds=not problems,
                                           detail="; ".join(p.message for p in problems[:3]) or None))
            if bad:
                reasons.append(f"{bad} rule(s) of {ruleset.ruleset_id}@{ruleset.version} do not type-check")
            stage("rules", t0, not bad, f"{len(ruleset.rules)} rule(s), digest {ruleset_digest(ruleset)[:12]}")
        else:
            unsupported("RULE_CHECK", f"{ruleset.ruleset_id}@{ruleset.version}", "rules")
    # 3. bounded queries on the model itself (facts within the bound, not requirements)
    if loaded is not None:
        kinds = loaded.property_kinds()
        for kind in ("GOAL_REACHABILITY", "INVARIANT_VIOLATION"):
            props = sorted(p for p, k in kinds.items() if k == ("goal" if kind == "GOAL_REACHABILITY" else "invariant"))
            if not props and kind in required:
                incomplete.append(f"required check {kind}: the model declares no "
                                  f"{'goal' if kind == 'GOAL_REACHABILITY' else 'invariant'} property")
            feature = _feature(report, f"query.{kind.lower()}")
            for prop in props:
                if feature.status != "SUPPORTED":
                    unsupported(kind, prop, feature.feature)
                    continue
                verifier = registry.create(feature.provider, {}, None)
                t0 = time.perf_counter()
                try:
                    res = verifier.check(package, CheckQuery(kind=kind, property_id=prop, bound=bound))
                    verdict, detail = str(res.verdict), res.explanation
                except FormalLabError as exc:
                    verdict, detail = "ERROR", exc.message
                holds, claim = _query_claim(kind, prop, verdict, cfg.horizon)
                conclusive = verdict in ("WITNESS", "NO_WITNESS_WITHIN_BOUND")
                blocks = verdict == "ERROR" or (prop in cfg.required_holds and holds is not True) or \
                    (kind in required and not conclusive)
                checks.append(ReleaseCheck(kind=kind, subject=prop, bound=bound, verdict=verdict, passed=not blocks,
                                           required=kind in required or prop in cfg.required_holds,
                                           backend=feature.provider, scope=scope, property_holds=holds, claim=claim,
                                           detail=(detail or "")[:300]))
                if verdict == "ERROR":
                    reasons.append(f"check {kind} {prop} errored: {detail}")
                elif kind in required and not conclusive:
                    incomplete.append(f"required check {kind} ({prop}) gave no conclusive result: {verdict}")
                if prop in cfg.required_holds and holds is not True:
                    reasons.append(f"required property {prop} does not hold: {claim}")
                stage(f"{kind.lower()}:{prop}", t0, not blocks, f"{verdict} within {cfg.horizon} steps")
        missing_holds = sorted(set(cfg.required_holds) - set(kinds))
        if missing_holds:
            reasons.append(f"required properties not declared by the model: {missing_holds}")
        if report.status("release.objectives") == "SUPPORTED" and package.is_ir:
            for obj in package.ir.objectives:
                checks.append(ReleaseCheck(kind="OBJECTIVE_CHECK", subject=obj.id, verdict="DECLARED", passed=True,
                                           required="OBJECTIVE_CHECK" in required, backend=driver_ref,
                                           scope="declaration in the model", claim="objective declared",
                                           detail=f"{len(obj.terms)} term(s), unit {obj.unit or '—'}"))
        elif "OBJECTIVE_CHECK" in required:
            unsupported("OBJECTIVE_CHECK", "objectives", "release.objectives")
    # 4. regression cases
    regression: list[RegressionResult] = []
    if cases:
        if report.status("release.regression_replay") == "SUPPORTED":
            t0 = time.perf_counter()
            for case in cases:
                regression.append(replay_regression_case(case, package, registry, loaded=loaded))
            failed = [r for r in regression if r.status != "PASS"]
            if failed:
                reasons.append(f"{len(failed)} of {len(regression)} regression case(s) do not pass: "
                               + "; ".join(f"{r.case_id} {r.status}" for r in failed[:3]))
            checks.append(ReleaseCheck(kind="REGRESSION", subject=f"{len(regression)} case(s)",
                                       verdict="PASS" if not failed else "FAIL", passed=not failed, required=True,
                                       backend=driver_ref, scope="recorded states and actions replayed on the model",
                                       property_holds=not failed,
                                       claim=f"{len(regression) - len(failed)}/{len(regression)} case(s) predict what "
                                             "was observed"))
            stage("regression", t0, not failed, f"{len(regression) - len(failed)}/{len(regression)} pass")
        else:
            unsupported("REGRESSION", f"{len(cases)} case(s)", "release.regression_replay")
    process_completed = loaded is not None and not incomplete
    reasons = incomplete + reasons
    status = "RELEASED" if process_completed and not reasons else "REJECTED"
    body = {"model": package.ref().model_dump(mode="json"), "ruleset": ruleset.digest.value if ruleset and
            ruleset.digest else None, "checks": [c.model_dump(mode="json") for c in checks],
            "regression": [r.model_dump(mode="json") for r in regression], "config": cfg.model_dump(mode="json")}
    release_id = "rel_" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    from formal_lab_contracts import RuleSetRef

    record = ModelReleaseRecord(
        release_id=release_id, model=package.ref(),
        ruleset=RuleSetRef(ruleset_id=ruleset.ruleset_id, version=ruleset.version, digest=ruleset.digest)
        if ruleset is not None and ruleset.digest is not None else None,
        driver=driver_ref, compiled=compiled, checks=checks,
        regression=regression, bounds=[f"bounded queries: max_steps={cfg.horizon}, timeout_ms={cfg.timeout_ms}"],
        assumptions=["checks hold for the model itself (scope MODEL_INTERNAL), not for any environment",
                     "regression cases replay recorded states and actions; their observed values are the evidence"],
        status=status, reasons=reasons, digest=digest_of(body), created_at=utcnow(), stages=stages, config=cfg,
        process_completed=process_completed, capabilities=report.features)
    log.append(f"[process] {'completed' if process_completed else 'incomplete'}")
    log.append(f"[verdict] {status}" + (f": {'; '.join(reasons)}" if reasons else ""))
    return record, log
