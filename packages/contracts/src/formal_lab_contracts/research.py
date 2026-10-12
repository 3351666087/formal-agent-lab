"""Research case and conformance-result protocols (phase 5A): `fal-research-case/v1`, `fal-conformance-result/v1`.

Independently versioned schemas next to formal-lab-contracts/v2 (they reference its ModelRef / ArtifactRef / Digest but
are not part of the v2 object set, so the v2 digest and the frozen v1 contract are untouched). JSON Schemas are written
to contracts/research/ by `python -m formal_lab_contracts.research --out contracts/research` (part of `make contracts`,
so `make contracts-check` covers them).

A research case ties together four separately versioned identities — the software under study (repository revision +
the digests of its relevant trees and configuration), the formal model (ModelRef), the validation material (artifacts
by sha256) and, from phase 6, the provider model that is asked to work on a task input. A conformance result records,
apart from each other: the model-internal conclusion, the program's own regression result, and whether the two
correspond within a declared scope. A single passing regression never stands for semantic equivalence.

Phase 6A adds `fal-research-response/v1` (the raw record of one provider call: experiment and call identity, the raw
answer, the call outcome, cost — persisted before parsing), `fal-research-study/v1` (a pre-registered study: tasks,
providers, assistance modes, replicates, limits, primary metric) and `fal-research-evaluation/v1` (the answer axis and
the scores of one response, kept apart from the call axis).
"""

from __future__ import annotations

import argparse
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field
from pydantic.json_schema import models_json_schema

from .common import ArtifactRef, ContractModel, Identifier, Name
from .objects import MetricResult, ModelRef

CASE_PROTOCOL = "fal-research-case/v1"
CONFORMANCE_PROTOCOL = "fal-conformance-result/v1"
SHA256 = r"^[0-9a-f]{64}$"
GIT_REVISION = r"^[0-9a-f]{40}$"
REL_PATH = r"^[A-Za-z0-9._@+=,-][A-Za-z0-9._@+=,/-]*$"  # relative (no leading /); '..' segments rejected below


def _no_parent(value: str) -> str:
    if ".." in value.split("/"):
        raise ValueError(f"path {value!r} must stay inside its directory ('..' segment)")
    return value


RelPath = Annotated[str, Field(pattern=REL_PATH), AfterValidator(_no_parent)]


class Track(StrEnum):
    """The experiment lines, counted apart."""

    IMPLEMENTATION_CONFORMANCE = "implementation_conformance"  # software model verification with its real purpose
    SYNTHETIC_REPRESENTATION = "synthetic_representation"  # fixed, reviewed synthetic problems (representation study)
    FORMAL_MODEL_ANALYSIS = "formal_model_analysis"  # phase 8: hard analysis of a formal model, Z3-ground-truthed


class ArtifactRole(StrEnum):
    MODEL = "model"  # a model package / IR file
    SOURCE = "source"  # a source excerpt or patch
    FIXTURE = "fixture"  # test fixtures / instances / operating conditions
    CRITERION = "criterion"  # expected verdicts / acceptance criteria (not answers)
    OBSERVATION = "observation"  # program-side observations (e.g. a replay bundle of a real run)
    MODEL_CHECK = "model_check"  # model-internal check results (query bundles)
    REGRESSION = "regression"  # the program's own regression-test result
    CONFORMANCE = "conformance"  # fal-conformance-result/v1 documents
    REFERENCE = "reference"  # reference answers: verification only, never a task input
    TASK_INPUT = "task_input"  # what a later phase may hand to a provider model (chosen explicitly)
    LOG = "log"


class CaseArtifact(ContractModel):
    """One file of the case, by path inside the case directory and its sha256 (the file itself is the evidence)."""

    id: Identifier
    role: ArtifactRole
    path: RelPath = Field(description="relative to the case directory")
    sha256: str = Field(pattern=SHA256)
    media_type: str = Field(min_length=3)
    side: Literal["before", "after", "both", "none"] = Field(
        default="none", description="which compared software version the artifact belongs to")
    revision: str | None = Field(default=None, pattern=GIT_REVISION,
                                 description="software revision the artifact was produced at, when it was")
    description: str | None = None
    stored: ArtifactRef | None = Field(default=None, description="set by a platform import (artifact store)")


class CaseIdentity(ContractModel):
    case_id: Identifier
    case_version: int = Field(ge=1)
    track: Track
    mechanism_family: str = Field(min_length=1, description="e.g. timing-model-deviation, state-machine-transition")
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1, description="what the case is for, in plain words (kept, never disguised)")


class TreeDigest(ContractModel):
    path: RelPath
    git_tree: str = Field(pattern=r"^[0-9a-f]{40}$", description="`git rev-parse <revision>:<path>`")


class DependencyDigest(ContractModel):
    name: str = Field(min_length=1, description="e.g. uv.lock, pnpm-lock.yaml, a container image")
    sha256: str = Field(pattern=SHA256)


class SoftwareSource(ContractModel):
    repository: str = Field(min_length=1)
    license: str = Field(min_length=1)
    revision: str = Field(pattern=GIT_REVISION)
    trees: list[TreeDigest] = Field(min_length=1, description="the relevant directories at that revision")
    config_sha256: str | None = Field(default=None, pattern=SHA256,
                                      description="the configuration / operating conditions the program ran with")
    build_dependencies: list[DependencyDigest] = Field(default_factory=list)
    runtime_dependencies: list[DependencyDigest] = Field(default_factory=list)
    variant: Literal["upstream_release", "upstream_commit", "own_test_variant"]
    variant_note: str = Field(min_length=1, description="what was changed / configured; an own variant is not an "
                                                        "upstream release")


class VersionSide(ContractModel):
    present: bool
    revision: str | None = Field(default=None, pattern=GIT_REVISION)
    artifact_ids: list[Identifier] = Field(default_factory=list)
    absent_reason: str | None = None


class CounterexampleEvidence(ContractModel):
    """What is known about a model counterexample on the program side (it is UNCONFIRMED without either)."""

    status: Literal["reproduced", "abstraction_error"]
    artifact_id: Identifier
    note: str = Field(min_length=1)


class Comparison(ContractModel):
    before: VersionSide
    after: VersionSide
    change_basis: str = Field(min_length=1, description="why the versions differ (commit, issue, operating condition)")
    regression_test_source: str | None = Field(default=None, description="where the regression tests come from")


class PropertySpec(ContractModel):
    property_id: Name
    kind: Literal["goal", "invariant"]
    digest: str = Field(pattern=SHA256, description="sha256 of the canonical {id, kind, expr} of the property")
    summary: str = Field(min_length=1)


class Bounds(ContractModel):
    max_steps: int = Field(ge=1)
    timeout_ms: int | None = Field(default=None, ge=1)
    inputs: str = Field(min_length=1, description="input domain / instance the conclusions are bounded to")


class CaseModel(ContractModel):
    label: str = Field(min_length=1)
    role: Literal["belief", "revised", "reference"]
    model_ref: ModelRef
    artifact_id: Identifier = Field(description="the model package file in the case")
    semantic_profile: str
    properties: list[PropertySpec] = Field(min_length=1)
    bounds: Bounds
    assumptions: list[str] = Field(default_factory=list)
    uncovered_semantics: list[str] = Field(default_factory=list, description="what the model deliberately leaves out")


class ProgramElement(ContractModel):
    component: str = Field(min_length=1)
    path: RelPath = Field(description="repository path at the case's software revision")
    symbol: str | None = None


class ModelElement(ContractModel):
    kind: Literal["state", "action", "constant", "observation", "property"]
    name: str = Field(min_length=1)


class Correspondence(ContractModel):
    program: ProgramElement
    model: ModelElement
    relation: Literal["MANUAL_REVIEW", "MEASURED", "FORMAL_PROOF"] = Field(
        description="reviewed by a person / established by measured agreement / proven formally")
    evidence_artifact_ids: list[Identifier] = Field(default_factory=list)
    note: str | None = None


class Criterion(ContractModel):
    id: Identifier
    text: str = Field(min_length=1)


class Validation(ContractModel):
    criteria: list[Criterion] = Field(default_factory=list)
    fixture_ids: list[Identifier] = Field(default_factory=list)
    observation_ids: list[Identifier] = Field(default_factory=list)
    model_check_ids: list[Identifier] = Field(default_factory=list)
    regression_ids: list[Identifier] = Field(default_factory=list)
    conformance_ids: list[Identifier] = Field(default_factory=list)
    reference_ids: list[Identifier] = Field(default_factory=list, description="verification only")
    task_input_ids: list[Identifier] = Field(default_factory=list, description="what a provider model may be given")


class Command(ContractModel):
    command: str = Field(min_length=1)
    purpose: str = Field(min_length=1)


class Reproduction(ContractModel):
    environment: str = Field(min_length=1, description="the local entry point (profile, services)")
    reset: str = Field(min_length=1)
    cleanup: str = Field(min_length=1)
    seeds: list[int] = Field(default_factory=list)
    nondeterminism: list[str] = Field(default_factory=list, description="external sources of variation")
    commands: list[Command] = Field(default_factory=list, description="commands that were actually run")
    prerequisites: list[str] = Field(default_factory=list)


class ResearchCase(ContractModel):
    protocol: Literal["fal-research-case/v1"] = CASE_PROTOCOL
    identity: CaseIdentity
    software: SoftwareSource
    comparison: Comparison
    models: list[CaseModel] = Field(min_length=1)
    correspondence: list[Correspondence] = Field(default_factory=list)
    validation: Validation
    reproduction: Reproduction
    artifacts: list[CaseArtifact] = Field(min_length=1)
    case_digest: str = Field(pattern=SHA256, description="sha256 of the canonical case without this field and "
                                                         "without platform-local `stored` references")


# ---------------------------------------------------------------- conformance result

# the platform's SearchVerdict values, plus TIMEOUT (a solver timeout kept apart from UNKNOWN) and NOT_RUN
ModelVerdict = Literal["WITNESS", "NO_WITNESS_WITHIN_BOUND", "UNKNOWN", "UNSUPPORTED", "TIMEOUT", "NOT_RUN"]
RegressionStatus = Literal["PASS", "FAIL", "NOT_RUN", "UNKNOWN"]
CorrespondenceStatus = Literal["CORRESPONDS", "DEVIATES", "UNCONFIRMED", "SPURIOUS", "UNKNOWN", "NOT_COMPARABLE",
                               "UNSUPPORTED", "TIMEOUT"]
ItemStatus = Literal["MATCH", "DIFFERENT", "UNKNOWN", "NOT_COMPARABLE"]


class CaseRef(ContractModel):
    case_id: Identifier
    case_version: int = Field(ge=1)
    definition_digest: str = Field(pattern=SHA256, description="sha256 of the case definition (identity, software, "
                                   "comparison, models, correspondence) — results are case artifacts themselves, so "
                                   "they bind to the definition, not to the whole case digest")


class SoftwareRef(ContractModel):
    revision: str = Field(pattern=GIT_REVISION)
    trees: list[TreeDigest] = Field(min_length=1)
    config_sha256: str | None = Field(default=None, pattern=SHA256)


class ModelConclusion(ContractModel):
    verdict: ModelVerdict
    query: str | None = Field(default=None, description="e.g. GOAL_REACHABILITY(all_completed)")
    explanation: str | None = None
    artifact_id: Identifier | None = None
    artifact_sha256: str | None = Field(default=None, pattern=SHA256)


class ProgramRegression(ContractModel):
    status: RegressionStatus
    summary: str | None = None
    artifact_id: Identifier | None = None
    artifact_sha256: str | None = Field(default=None, pattern=SHA256)


class ProgramObservation(ContractModel):
    artifact_id: Identifier
    sha256: str = Field(pattern=SHA256, description="the observation the result was computed from (staleness check)")
    summary: str = Field(min_length=1)


class ConformanceItem(ContractModel):
    step: int | None = Field(default=None, ge=0)
    action: str | None = None
    element: str = Field(min_length=1, description="model location / element the item compares")
    predicted: bool | int | str | None = None
    observed: bool | int | str | None = None
    status: ItemStatus
    evidence: str = Field(description="observed / verified-within-scope / unknown / not-comparable")


class ToolIdentity(ContractModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    digest: str | None = None


class ConformanceResult(ContractModel):
    protocol: Literal["fal-conformance-result/v1"] = CONFORMANCE_PROTOCOL
    case: CaseRef
    model: ModelRef
    software: SoftwareRef
    property_id: Name
    property_digest: str = Field(pattern=SHA256)
    bound: Bounds
    assumptions: list[str] = Field(default_factory=list)
    model_conclusion: ModelConclusion
    program_regression: ProgramRegression
    program_observations: list[ProgramObservation] = Field(default_factory=list)
    items: list[ConformanceItem] = Field(default_factory=list)
    counterexample: CounterexampleEvidence | None = None
    correspondence: CorrespondenceStatus
    correspondence_note: str = Field(min_length=1)
    scope: str = Field(min_length=1, description="what the correspondence covers — never semantic equivalence")
    counts: dict[str, int] = Field(default_factory=dict, description="item status → number")
    tools: list[ToolIdentity] = Field(min_length=1)


# ---------------------------------------------------------------- phase 6A: research responses, studies, evaluations
RESPONSE_PROTOCOL = "fal-research-response/v1"
STUDY_PROTOCOL = "fal-research-study/v1"
EVALUATION_PROTOCOL = "fal-research-evaluation/v1"


class AssistanceMode(StrEnum):
    STATIC_UNASSISTED = "STATIC_UNASSISTED"  # the specification and the question only
    ASSISTED = "ASSISTED"  # plus recorded assistance (a candidate set, validation feedback …) — never "independent"


class Route(StrEnum):
    """How the request reached a model, declared in the study and checked against the endpoint host at call time."""

    OFFICIAL_NATIVE = "OFFICIAL_NATIVE"  # the provider's own API (api.openai.com / api.anthropic.com)
    COMPATIBLE_RELAY = "COMPATIBLE_RELAY"  # a third-party gateway speaking a provider protocol: identity not verifiable
    LOOPBACK_TEST = "LOOPBACK_TEST"  # the local protocol test service — not a model
    STUB = "STUB"


class CallOutcome(StrEnum):
    """The call axis — one stable class per call. Kept apart from how the answer is parsed and scored."""

    ANSWERED = "ANSWERED"  # HTTP success, visible answer, normal stop
    TRUNCATED = "TRUNCATED"  # HTTP success, stopped at the output-token limit (the partial answer is kept)
    CONTENT_REFUSAL = "CONTENT_REFUSAL"  # HTTP success, the provider signals a refusal / content filter
    EMPTY_CONTENT = "EMPTY_CONTENT"  # HTTP success, no visible text and no refusal signal
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"  # HTTP success, but the body is not the provider protocol
    AUTH_ERROR = "AUTH_ERROR"  # 401 / 403 — never a content refusal
    RATE_LIMITED = "RATE_LIMITED"  # 429 after the fixed retries
    PROVIDER_ERROR = "PROVIDER_ERROR"  # 5xx / overloaded after the fixed retries
    REQUEST_REJECTED = "REQUEST_REJECTED"  # other 4xx (invalid request / parameter)
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"  # the provider says the requested model does not exist / is not available
    TRANSPORT_ERROR = "TRANSPORT_ERROR"  # never reached the provider (connect error)
    UNCERTAIN = "UNCERTAIN"  # sent, but no response arrived — it may have been billed
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"  # not sent: a study limit was reached
    CANCELLED = "CANCELLED"  # not sent / aborted between attempts
    BLOCKED_NO_CREDENTIAL = "BLOCKED_NO_CREDENTIAL"  # not sent: no authorized endpoint / credential configured


MODEL_PRODUCED: frozenset[str] = frozenset({"ANSWERED", "TRUNCATED", "CONTENT_REFUSAL", "EMPTY_CONTENT"})
"""Outcomes where the model itself produced the response — the only ones that count toward a model's scores."""


class FinishClass(StrEnum):
    STOP = "STOP"
    LENGTH = "LENGTH"
    REFUSAL = "REFUSAL"
    CONTENT_FILTER = "CONTENT_FILTER"
    TOOL_USE = "TOOL_USE"
    PAUSE = "PAUSE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class ModelIdentityStatus(StrEnum):
    CONFIRMED_BY_PROVIDER = "CONFIRMED_BY_PROVIDER"  # official route, the response names the model
    RELAY_REPORTED = "RELAY_REPORTED"  # a relay names a model: recorded, not independently verifiable
    TEST_SERVICE = "TEST_SERVICE"  # the protocol test service (not a model)
    STUB = "STUB"
    UNKNOWN = "UNKNOWN"  # the response named no model


class ExperimentIdentity(ContractModel):
    study_id: Identifier
    unit_id: str = Field(min_length=1)
    track: Track
    case_id: str | None = None
    case_version: int | None = Field(default=None, ge=1)
    task_id: Identifier
    task_digest: str = Field(pattern=SHA256)
    representation_id: str = Field(min_length=1)
    replicate_id: int = Field(ge=0)
    assistance_mode: AssistanceMode
    sampling_id: str = Field(min_length=1, description="a new id for every fresh sample (a resample is a new one)")


class CallIdentity(ContractModel):
    provider: str = Field(min_length=1, description="openai / anthropic / protocol-test / stub")
    provider_config_id: str = Field(min_length=1)
    api: str = Field(min_length=1, description="openai.chat.completions / anthropic.messages")
    api_version: str = Field(min_length=1)
    endpoint: str = Field(description="scheme://host/path — no credentials, no query")
    route: Route
    endpoint_kind: str = Field(description="what answered, from the answer itself: PROVIDER / PROTOCOL_TEST / STUB")
    model_requested: str
    model_returned: str | None = None
    model_switched: bool = False
    model_identity: ModelIdentityStatus
    response_id: str | None = Field(default=None, description="the provider's response id")
    request_id: str | None = Field(default=None, description="the provider's request id header, when sent")
    started_at: str
    finished_at: str | None = None
    params: dict[str, Any] = Field(default_factory=dict, description="exactly the sampling parameters sent")
    params_digest: str


class ReasoningAvailability(StrEnum):
    NOT_EXPOSED = "NOT_EXPOSED"  # the provider exposes no internal reasoning: none is inferred
    SUMMARY_ONLY = "SUMMARY_ONLY"  # a provider-written summary exists; it is not the raw reasoning


class RawAnswer(ContractModel):
    body: Any = Field(default=None, description="the provider's JSON body as returned (when it is JSON)")
    body_text: str | None = Field(default=None, description="the body as text when it is not JSON")
    visible_text: str | None = None
    finish_reason: str | None = Field(default=None, description="exactly as the provider wrote it")
    finish_class: FinishClass = FinishClass.UNKNOWN
    refusal: str | None = Field(default=None, description="the provider's explicit refusal field / signal")
    truncated: bool | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    reasoning: ReasoningAvailability = ReasoningAvailability.NOT_EXPOSED


class AttemptRecord(ContractModel):
    attempt_no: int = Field(ge=1)
    attempt_id: str
    sent: bool
    confirmed: bool = Field(description="a complete HTTP response arrived for this attempt")
    http_status: int | None = None
    error_class: str | None = None
    error: str | None = Field(default=None, description="redacted, truncated")
    latency_ms: float = 0.0


class CallStatus(ContractModel):
    outcome: CallOutcome
    transport_ok: bool
    http_status: int | None = None
    provider_error_type: str | None = None
    provider_error: str | None = None
    model_switched: bool = False
    attempts: list[AttemptRecord] = Field(default_factory=list)
    network_retries: int = Field(ge=0, description="the fixed retry allowance the call ran with")
    note: str | None = None


class CostRecord(ContractModel):
    usage_known: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = Field(default=None, description="prompt-cache writes (Anthropic "
                                           "cache_creation_input_tokens); input_tokens is as the provider counts it")
    latency_ms: float = 0.0
    http_attempts: int = Field(ge=0)
    possibly_billed_unconfirmed: int = Field(ge=0, description="attempts sent without a confirmed response")
    prompt_digest: str
    config_digest: str


class ResearchResponse(ContractModel):
    """The raw record of one research call, persisted before anything parses or scores it."""

    protocol: Literal["fal-research-response/v1"] = RESPONSE_PROTOCOL
    experiment: ExperimentIdentity
    call: CallIdentity
    raw: RawAnswer
    status: CallStatus
    cost: CostRecord
    task_input_digest: str = Field(pattern=SHA256, description="sha256 of exactly what was sent (system + user)")
    reuse_key: str = Field(pattern=SHA256)
    recorded_at: str


class ProviderConfig(ContractModel):
    provider_config_id: Identifier
    provider: Literal["openai", "anthropic", "protocol-test"]
    api: Literal["openai.chat.completions", "anthropic.messages"]
    api_version: str = Field(min_length=1)
    route: Route = Field(description="declared; the runner checks it against the endpoint host before sending")
    base_url: str | None = Field(default=None, description="literal endpoint (loopback / official default)")
    base_url_setting: str | None = Field(default=None, description="settings name holding the endpoint")
    api_key_setting: str | None = Field(default=None, description="settings name of the credential (never its value)")
    model: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict, description="sampling parameters sent verbatim")
    comparability_note: str | None = None


class StudyTask(ContractModel):
    task_id: Identifier
    track: Track
    case_id: str | None = None
    case_version: int | None = Field(default=None, ge=1)
    representation_id: str = Field(min_length=1)
    representation_version: int = Field(default=1, ge=1)
    purpose: str = Field(min_length=1, description="the real purpose, kept in the task (never disguised)")
    inputs: list[RelPath] = Field(min_length=1, description="study-relative files the model may see")
    assisted_inputs: list[RelPath] = Field(default_factory=list, description="added only in ASSISTED mode")
    question: str = Field(min_length=1)
    answer_format: Literal["json", "free_text"] = "json"
    answer_schema: dict[str, Any] | None = None
    reference: RelPath = Field(description="scorer-only evidence; never sent to a model")
    scorer_id: str = Field(min_length=1)
    scorer_version: str = Field(min_length=1)
    bound: dict[str, Any] = Field(default_factory=dict)
    split: Literal["dev", "acceptance"] = "acceptance"


class StudyLimits(ContractModel):
    max_calls: int = Field(ge=0)
    max_http_attempts: int = Field(ge=0)
    max_output_tokens_per_call: int = Field(ge=1)
    max_total_output_tokens: int | None = Field(default=None, ge=1)
    network_retries: int = Field(ge=0, le=5, description="fixed per call; a refusal is never retried")


class StudyComparison(ContractModel):
    vary: Literal["provider", "representation", "assistance"]
    a: str
    b: str
    note: str | None = None


class ResearchStudy(ContractModel):
    protocol: Literal["fal-research-study/v1"] = STUDY_PROTOCOL
    study_id: Identifier
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    tasks: list[StudyTask] = Field(min_length=1)
    providers: list[ProviderConfig] = Field(min_length=1)
    assistance_modes: list[AssistanceMode] = Field(min_length=1)
    replicates: int = Field(ge=1, description="independent samples per condition")
    rubric_id: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    primary_metric: str = Field(min_length=1)
    secondary_metrics: list[str] = Field(default_factory=list)
    limits: StudyLimits
    missing_policy: str = Field(min_length=1)
    comparisons: list[StudyComparison] = Field(default_factory=list)


class AnswerStatus(StrEnum):
    """The answer axis: how the recorded answer parses (after it was saved)."""

    VALID = "VALID"
    INVALID_JSON = "INVALID_JSON"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    TYPE_ERROR = "TYPE_ERROR"
    EMPTY = "EMPTY"
    NO_ANSWER = "NO_ANSWER"  # the call produced no visible answer to parse


class BehaviorLabel(StrEnum):
    CORRECT = "CORRECT"
    PARTIAL = "PARTIAL"
    INCORRECT = "INCORRECT"
    INVALID_FORMAT = "INVALID_FORMAT"
    REFUSED = "REFUSED"
    EMPTY = "EMPTY"
    NO_MODEL_ANSWER = "NO_MODEL_ANSWER"  # transport / auth / limit / budget / cancel / blocked: not the model's doing
    NOT_RUN = "NOT_RUN"


class ResearchEvaluation(ContractModel):
    """A small static-task evaluation record (no fabricated steps, world state or execution success)."""

    protocol: Literal["fal-research-evaluation/v1"] = EVALUATION_PROTOCOL
    study_id: Identifier
    unit_id: str = Field(min_length=1)
    response_digest: str = Field(pattern=SHA256)
    response_path: RelPath
    scorer_id: str
    scorer_version: str
    reference_sha256: str = Field(pattern=SHA256)
    dependency_digests: dict[str, str] = Field(default_factory=dict)
    call_outcome: CallOutcome
    answer_status: AnswerStatus
    parsed: Any = None
    behavior_label: BehaviorLabel
    refusal_status: Literal["NONE", "EXPLICIT_REFUSAL", "CONTENT_FILTER"] = "NONE"
    model_internal: Literal["CORRECT", "INCORRECT", "NOT_EVALUATED", "NOT_APPLICABLE"] = "NOT_EVALUATED"
    program_correspondence: Literal["CORRESPONDS", "DEVIATES", "UNKNOWN", "NOT_APPLICABLE", "NOT_EVALUATED"] = \
        "NOT_EVALUATED"
    metrics: list[MetricResult] = Field(default_factory=list)
    rubric_signals: dict[str, Any] = Field(default_factory=dict, description="phase 6B: recorded-only heuristic rubric "
                                           "signals (e.g. did the answer state scope / name the risk); not adjudicated, "
                                           "no human review — never promoted to a pass")
    explanation: str = ""
    scoring_reuse_key: str = Field(pattern=SHA256)


PROTOCOLS: dict[str, type[BaseModel]] = {CASE_PROTOCOL: ResearchCase, CONFORMANCE_PROTOCOL: ConformanceResult,
                                         RESPONSE_PROTOCOL: ResearchResponse, STUDY_PROTOCOL: ResearchStudy,
                                         EVALUATION_PROTOCOL: ResearchEvaluation}


def write_schemas(out: Path) -> list[Path]:
    """One JSON Schema per protocol (draft 2020-12, definitions under $defs)."""
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for protocol, model in PROTOCOLS.items():
        _, schema = models_json_schema([(model, "validation")], ref_template="#/$defs/{model}")
        name = protocol.replace("/", "-")
        doc = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"https://formal-lab.dev/{protocol}",
               "title": protocol, "$ref": f"#/$defs/{model.__name__}", **schema}
        path = out / f"{name}.schema.json"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        written.append(path)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="write the research protocol JSON Schemas")
    ap.add_argument("--out", default="contracts/research")
    for path in write_schemas(Path(ap.parse_args().out)):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
