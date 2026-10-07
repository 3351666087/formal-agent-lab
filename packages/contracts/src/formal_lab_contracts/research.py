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
"""

from __future__ import annotations

import argparse
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field
from pydantic.json_schema import models_json_schema

from .common import ArtifactRef, ContractModel, Identifier, Name
from .objects import ModelRef

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
    """The two experiment lines of phases 5–7, counted apart."""

    IMPLEMENTATION_CONFORMANCE = "implementation_conformance"  # software model verification with its real purpose
    SYNTHETIC_REPRESENTATION = "synthetic_representation"  # fixed, reviewed synthetic problems (representation study)


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


PROTOCOLS: dict[str, type[BaseModel]] = {CASE_PROTOCOL: ResearchCase, CONFORMANCE_PROTOCOL: ConformanceResult}


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
