"""formal-lab-contracts/v2 — rules, model releases, regression cases and matrix cells."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import ArtifactRef, ContractModel, Digest, Identifier, Name, PluginRef, StateScalar
from .execution import StageRecord
from .ir import Expr
from .kernel import ExecutionStage, ObjectiveSpec, RuleOutcome, RuleSetRef
from .objects import (
    CheckBound,
    CompiledArtifact,
    EventType,
    GroundAction,
    ModelRef,
    QueryKind,
    ScenarioManifest,
)

# =========================================================================== rules (P2-070 / P2-071)


class RuleParam(ContractModel):
    """A value the rule context provides besides the belief state, referenced as `{"op": "ref", "name": …}`."""

    name: Name
    type: Literal["bool", "int", "symbol"]
    values: list[str] = Field(default_factory=list, description="symbol: allowed values (an enum for the checker)")
    description: str | None = None


# the context every rule can read; values come from the triggering event
RULE_CONTEXT_PARAMS: list[RuleParam] = [
    RuleParam(name="ev_verdict", type="symbol", values=["MATCH", "DIFFERENT", "INSUFFICIENT_INFORMATION", "NONE"],
              description="effect comparison verdict of the step (NONE if not compared)"),
    RuleParam(name="ev_outcome", type="symbol",
              values=["APPLIED", "REJECTED", "FAILED_RETRYABLE", "FAILED_NON_RETRYABLE", "TIMED_OUT", "UNKNOWN",
                      "CANCELLED", "NONE"], description="outcome status of the step's action"),
    RuleParam(name="ev_unknown_count", type="int", description="unknown locations in the actor's observation"),
    RuleParam(name="ev_stale_count", type="int", description="stale locations in the actor's belief"),
    RuleParam(name="ev_different_count", type="int", description="fields whose observed value differs"),
    RuleParam(name="ev_step", type="int", description="global logical step"),
    RuleParam(name="ev_rejected_streak", type="int", description="consecutive rejected actions of the actor"),
]


class RuleTrigger(ContractModel):
    events: list[EventType] = Field(min_length=1, description="event types that make the rule evaluate")
    stage: ExecutionStage | None = Field(default=None, description="restrict to events of this stage")


class Rule(ContractModel):
    """Typed event–condition–handler rule. The condition is a pure IR expression over the actor's belief state and
    the rule context parameters; it is type-checked against the model before release."""

    rule_id: Name
    label: str | None = None
    trigger: RuleTrigger
    condition: Expr
    priority: int = Field(default=0, description="higher first; ties with different outcomes are a CONFLICT")
    outcome: RuleOutcome
    message: str = Field(min_length=1)
    observe_paths: list[str] = Field(default_factory=list, description="OBSERVE_MORE: locations to request")
    enabled: bool = True

    @model_validator(mode="after")
    def _observe(self) -> Rule:
        if self.outcome is RuleOutcome.OBSERVE_MORE and not self.observe_paths:
            raise ValueError("OBSERVE_MORE rules must name `observe_paths`")
        return self


class RuleSet(ContractModel):
    ruleset_id: Identifier
    version: int = Field(ge=1)
    name: str
    model: ModelRef = Field(description="model the rules are written against (checked with it)")
    rules: list[Rule] = Field(default_factory=list)
    parent_version: int | None = None
    digest: Digest | None = None
    created_at: datetime | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _unique(self) -> RuleSet:
        ids = [r.rule_id for r in self.rules]
        if len(set(ids)) != len(ids):
            raise ValueError("rule ids must be unique within a rule set")
        return self

    def ref(self) -> RuleSetRef:
        if self.digest is None:
            raise ValueError("rule set has no digest yet")
        return RuleSetRef(ruleset_id=self.ruleset_id, version=self.version, digest=self.digest)


class RuleResult(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"  # completions of unknown locations disagree
    TIMEOUT = "TIMEOUT"  # too many completions to decide within the limit
    CONFLICT = "CONFLICT"  # equal-priority rules fired with different outcomes
    UNSUPPORTED = "UNSUPPORTED"  # the condition cannot be evaluated for this model / driver


class RuleEvaluation(ContractModel):
    rule_id: Name
    ruleset: RuleSetRef | None = None
    result: RuleResult
    outcome: RuleOutcome | None = Field(description="outcome applied (null when the rule did not decide)")
    priority: int
    explanation: str
    completions_checked: int = 0


class RuleDecision(ContractModel):
    """Resolution of all rules that evaluated for one event: the winning outcome and why."""

    event_type: EventType
    evaluations: list[RuleEvaluation]
    outcome: RuleOutcome
    winner: Name | None
    priority_explanation: str


# =========================================================================== releases (P2-072 / P2-073)


ReleaseCheckKind = Literal["TYPE_CHECK", "RULE_CHECK", "GOAL_REACHABILITY", "INVARIANT_VIOLATION",
                           "OBJECTIVE_CHECK", "REGRESSION"]


class SupportStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


class FeatureSupport(ContractModel):
    """Whether one feature (a release check, rules, a query kind, statistics …) is available for a model, derived
    from the declared capabilities of its semantic driver and of the installed verifiers (phase 3A, G3)."""

    feature: str = Field(min_length=1, description="e.g. release.type_check, rules, query.goal_reachability")
    status: SupportStatus
    provider: PluginRef | None = Field(default=None, description="plugin that provides it (when supported)")
    requires: list[str] = Field(default_factory=list, description="capability ids it needs")
    reason: str


class CapabilityReport(ContractModel):
    """What the platform can do with one model version, feature by feature — never inferred from the payload's
    shape, only from declared capabilities and the public protocols."""

    model: ModelRef
    semantic_profile: str
    driver: PluginRef
    features: list[FeatureSupport] = Field(default_factory=list)
    generated_at: datetime

    def status(self, feature: str) -> SupportStatus | None:
        return next((f.status for f in self.features if f.feature == feature), None)


class ReleaseConfig(ContractModel):
    """What a release must establish (phase 3A, G3). `required_checks` must run and give a conclusive result;
    `required_holds` names properties that must hold within the bound. Without a required capability or result the
    release is not passed, with the reason."""

    required_checks: list[ReleaseCheckKind] = Field(default_factory=lambda: ["TYPE_CHECK"])
    required_holds: list[str] = Field(default_factory=list, description="property ids that must hold (bounded)")
    horizon: int = Field(default=6, ge=1)
    timeout_ms: int = Field(default=10000, ge=1)


class ReleaseCheck(ContractModel):
    kind: QueryKind | Literal["TYPE_CHECK", "RULE_CHECK", "OBJECTIVE_CHECK", "REGRESSION"]
    subject: str = Field(description="property / rule / objective checked")
    bound: CheckBound | None = None
    verdict: str
    check_id: str | None = None
    passed: bool = Field(description="this check does not block the release (a violated invariant found by a query "
                                     "is a fact, not a failure, unless its property is in required_holds)")
    detail: str | None = None
    required: bool = Field(default=False, description="named in the release config (phase 3A)")
    executed: bool = Field(default=True, description="the check ran and produced a result (False: UNSUPPORTED)")
    backend: PluginRef | None = Field(default=None, description="plugin that produced the result")
    scope: str | None = Field(default=None, description="what the result covers, e.g. MODEL_INTERNAL within 6 steps")
    property_holds: bool | None = Field(default=None, description="the checked property holds (None: no claim)")
    claim: str | None = Field(default=None, description="the result in words, as far as the verdict supports it")


class RegressionResult(ContractModel):
    case_id: str
    status: Literal["PASS", "FAIL", "ERROR"]
    detail: str


class ModelReleaseRecord(ContractModel):
    """Compilation and checking facts of a model (+ rules + objective) at release time. A run that pins a release
    runs exactly what was checked; nothing here claims correctness outside the stated bounds and assumptions."""

    release_id: Identifier
    model: ModelRef
    ruleset: RuleSetRef | None = None
    objective: ObjectiveSpec | None = None
    driver: PluginRef | None = None
    compiled: list[CompiledArtifact] = Field(default_factory=list)
    checks: list[ReleaseCheck] = Field(default_factory=list)
    regression: list[RegressionResult] = Field(default_factory=list)
    bounds: list[str] = Field(default_factory=list, description="bounds the checks used")
    assumptions: list[str] = Field(default_factory=list)
    scope: Literal["MODEL_INTERNAL"] = "MODEL_INTERNAL"
    status: Literal["RELEASED", "REJECTED"]
    reasons: list[str] = Field(default_factory=list)
    digest: Digest
    created_at: datetime
    log: ArtifactRef | None = None
    stages: list[StageRecord] = Field(default_factory=list)
    config: ReleaseConfig | None = Field(default=None, description="required checks / properties (phase 3A)")
    process_completed: bool | None = Field(
        default=None, description="every required check ran with a conclusive result (phase 3A); independent of "
                                  "whether any property holds — see each check's property_holds")
    capabilities: list[FeatureSupport] = Field(default_factory=list, description="capability report used (phase 3A)")


class RegressionCase(ContractModel):
    """Minimal replayable case from a counterexample or an effect difference (P2-076)."""

    case_id: Identifier
    source: Literal["COUNTEREXAMPLE", "EFFECT_DIFFERENCE"]
    model: ModelRef
    scenario: ScenarioManifest | None = None
    seed: int | None = None
    initial_state: dict[str, StateScalar]
    actions: list[GroundAction]
    expected: dict[str, StateScalar] = Field(description="model prediction for the compared locations")
    observed: dict[str, StateScalar] = Field(description="what the run observed")
    compared_paths: list[str]
    minimized: bool = False
    origin: dict[str, Any] = Field(default_factory=dict, description="run_id / step / check_id it came from")
    created_at: datetime


# =========================================================================== matrices (P2-080)


class MatrixCellSpec(ContractModel):
    """One matrix cell: the complete configuration; `cell_id` is derived from its canonical digest."""

    cell_id: str
    scenario_id: str
    scenario_revision: int | None = None
    participants: dict[str, dict[str, Any]] = Field(description="actor → {plugin, config}")
    environment: dict[str, Any] = Field(description="{plugin, config} (backend)")
    rules: RuleSetRef | None = None
    rules_enabled: bool = True
    model: ModelRef | None = None
    seed: int
    budget: dict[str, Any] = Field(default_factory=dict)
    ablations: dict[str, Any] = Field(default_factory=dict, description="mechanism switches (e.g. observation delay)")
    split: Literal["dev", "acceptance"] = "acceptance"
    config_digest: str
