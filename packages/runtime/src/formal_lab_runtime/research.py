"""Research cases and model–program conformance (phase 5A; protocols in `formal_lab_contracts.research`).

    load_case(src)                         a case directory or an exported zip → CaseFiles (offline, no server)
    validate_case(files, repo=…)           every reference checked: digests, model / property identity, before/after
                                           sides, software revision + tree digests, data separation, stale results
    replay_conformance(...)                the program's recorded observations (a replay bundle) replayed on a model the
                                           way the engine compares effects (belief → predict → compare_effects), with
                                           the three layers kept apart: model conclusion, program regression, and
                                           whether the two correspond within the declared scope

Validation never trusts file names: an artifact is identified by its sha256, a model by its package digest, a property
by the digest of its canonical {id, kind, expr}, a software version by its commit and the git tree ids of the relevant
paths. A file that exists only proves the material exists.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from formal_lab_contracts import ModelPackage, Observation, canonical_json, digest_of
from formal_lab_contracts.research import (
    ArtifactRole,
    CaseModel,
    CaseRef,
    ConformanceItem,
    ConformanceResult,
    CounterexampleEvidence,
    ModelConclusion,
    ProgramObservation,
    ProgramRegression,
    ResearchCase,
    SoftwareRef,
    ToolIdentity,
    TreeDigest,
)

CASE_FILE = "case.json"
DEFINITION_FIELDS = ("protocol", "identity", "software", "comparison", "models", "correspondence")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------------------------------------ files and digests
@dataclass
class CaseFiles:
    """A case read from a directory or a zip: the raw case document and its files by relative path."""

    source: str
    document: dict[str, Any]
    _dir: Path | None = None
    _zip: dict[str, bytes] | None = None

    def read(self, rel: str) -> bytes | None:
        if self._zip is not None:
            return self._zip.get(rel)
        assert self._dir is not None
        path = (self._dir / rel).resolve()
        if not path.is_relative_to(self._dir.resolve()) or not path.is_file():
            return None
        return path.read_bytes()


def load_case(src: str | Path | bytes) -> CaseFiles:
    """A case directory (with case.json), a zip of one (bytes or a .zip path) — readable with no server."""
    if isinstance(src, bytes) or (isinstance(src, (str, Path)) and str(src).endswith(".zip")):
        data = src if isinstance(src, bytes) else Path(src).read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            prefix = next((n[: -len(CASE_FILE)] for n in names if n.endswith(CASE_FILE) and n.count("/") <= 1), None)
            if prefix is None:
                raise ValueError("no case.json in the zip")
            files = {n[len(prefix):]: zf.read(n) for n in names if n.startswith(prefix) and not n.endswith("/")}
        return CaseFiles(source="zip", document=json.loads(files[CASE_FILE]), _zip=files)
    root = Path(src)
    return CaseFiles(source=str(root), document=json.loads((root / CASE_FILE).read_text()), _dir=root)


def _strip_platform(doc: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in doc.items() if k != "case_digest"}
    out["artifacts"] = [{k: v for k, v in a.items() if k != "stored"} for a in doc.get("artifacts", [])]
    return out


def compute_case_digest(doc: dict[str, Any] | ResearchCase) -> str:
    """sha256 of the canonical case without `case_digest` and without platform-local `stored` references."""
    raw = doc.model_dump(mode="json") if isinstance(doc, ResearchCase) else doc
    return sha256_bytes(canonical_json(_strip_platform(raw)))


def definition_digest(doc: dict[str, Any] | ResearchCase) -> str:
    raw = doc.model_dump(mode="json") if isinstance(doc, ResearchCase) else doc
    return sha256_bytes(canonical_json({k: raw.get(k) for k in DEFINITION_FIELDS}))


def property_digest(package: ModelPackage, property_id: str) -> str | None:
    """sha256 of the canonical {id, kind, expr} of a model property (None when the model has no such property)."""
    if not package.is_ir:
        return None
    prop = next((p for p in package.ir.properties if p.id == property_id), None)
    if prop is None:
        return None
    return digest_of({"id": prop.id, "kind": prop.kind, "expr": prop.expr.model_dump(mode="json")}).value


def tree_digests(repo: Path, revision: str, paths: list[str]) -> list[TreeDigest] | None:
    """`git rev-parse <revision>:<path>` for each path; None when the revision is not in this repository."""
    out = []
    for p in paths:
        res = subprocess.run(["git", "rev-parse", f"{revision}:{p}"], cwd=repo, capture_output=True, text=True)
        if res.returncode != 0:
            return None
        out.append(TreeDigest(path=p, git_tree=res.stdout.strip()))
    return out


# ------------------------------------------------------------------------------------------------------ validation
@dataclass
class Problem:
    code: str
    where: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "where": self.where, "detail": self.detail}


@dataclass
class ValidationReport:
    case_id: str | None
    problems: list[Problem] = field(default_factory=list)
    warnings: list[Problem] = field(default_factory=list)
    checked: Counter = field(default_factory=Counter)

    @property
    def ok(self) -> bool:
        return not self.problems

    def add(self, code: str, where: str, detail: str) -> None:
        self.problems.append(Problem(code, where, detail))

    def as_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "ok": self.ok, "problems": [p.as_dict() for p in self.problems],
                "warnings": [w.as_dict() for w in self.warnings], "checked": dict(self.checked)}


def _parse_package(data: bytes) -> ModelPackage:
    return ModelPackage.model_validate_json(data)


def validate_case(files: CaseFiles, *, repo: Path | None = None) -> tuple[ValidationReport, ResearchCase | None]:
    """Check a case before it is imported or used. Problems reject the case; warnings say what this place could not
    verify (e.g. no repository at hand for the software trees)."""
    doc = files.document
    report = ValidationReport(case_id=(doc.get("identity") or {}).get("case_id"))
    try:
        case = ResearchCase.model_validate(doc)
    except Exception as exc:
        report.add("SCHEMA", "case.json", str(exc)[:600])
        return report, None

    # the case content and its digest
    expected = compute_case_digest(doc)
    report.checked["case_digest"] += 1
    if expected != case.case_digest:
        report.add("CASE_DIGEST_MISMATCH", "case_digest",
                   f"content digest {expected[:12]} ≠ recorded {case.case_digest[:12]}: the case was changed and its "
                   "digest not updated")

    # artifacts: present, intact, unique
    by_id = {}
    for a in case.artifacts:
        if a.id in by_id:
            report.add("DUPLICATE_ARTIFACT", f"artifacts[{a.id}]", "artifact id used twice")
        by_id[a.id] = a
        data = files.read(a.path)
        report.checked["artifact"] += 1
        if data is None:
            report.add("ARTIFACT_MISSING", f"artifacts[{a.id}]", f"{a.path} is not in the case")
        elif sha256_bytes(data) != a.sha256:
            report.add("ARTIFACT_DIGEST_MISMATCH", f"artifacts[{a.id}]",
                       f"{a.path}: sha256 {sha256_bytes(data)[:12]} ≠ recorded {a.sha256[:12]}")

    def ref(where: str, aid: str, role: ArtifactRole | None = None) -> None:
        report.checked["reference"] += 1
        art = by_id.get(aid)
        if art is None:
            report.add("UNKNOWN_ARTIFACT_REF", where, f"no artifact {aid!r}")
        elif role is not None and art.role != role:
            report.add("ROLE_MISMATCH", where, f"{aid} has role {art.role}, expected {role}")

    v = case.validation
    for name, ids, role in (("fixture_ids", v.fixture_ids, ArtifactRole.FIXTURE),
                            ("observation_ids", v.observation_ids, ArtifactRole.OBSERVATION),
                            ("model_check_ids", v.model_check_ids, ArtifactRole.MODEL_CHECK),
                            ("regression_ids", v.regression_ids, ArtifactRole.REGRESSION),
                            ("conformance_ids", v.conformance_ids, ArtifactRole.CONFORMANCE),
                            ("reference_ids", v.reference_ids, ArtifactRole.REFERENCE),
                            ("task_input_ids", v.task_input_ids, ArtifactRole.TASK_INPUT)):
        for aid in ids:
            ref(f"validation.{name}", aid, role)
    # data separation: reference answers are verification material, never something a model is handed
    task_shas = {by_id[a].sha256 for a in v.task_input_ids if a in by_id}
    for aid in v.reference_ids:
        if aid in v.task_input_ids or (aid in by_id and by_id[aid].sha256 in task_shas):
            report.add("REFERENCE_IN_TASK_INPUT", f"validation.reference_ids[{aid}]",
                       "a reference answer is also listed (or byte-identical) as a task input")
    for c in case.correspondence:
        for aid in c.evidence_artifact_ids:
            ref(f"correspondence[{c.program.component}→{c.model.name}]", aid)

    # models and properties: identity by digest, not by name
    packages: dict[str, ModelPackage] = {}
    for m in case.models:
        where = f"models[{m.label}]"
        ref(where, m.artifact_id, ArtifactRole.MODEL)
        art = by_id.get(m.artifact_id)
        data = files.read(art.path) if art else None
        if data is None:
            continue
        try:
            pkg = _parse_package(data)
        except Exception as exc:
            report.add("MODEL_UNREADABLE", where, str(exc)[:300])
            continue
        report.checked["model"] += 1
        if (pkg.package_id, pkg.version, pkg.digest.value) != (m.model_ref.package_id, m.model_ref.version,
                                                               m.model_ref.digest.value):
            report.add("MODEL_REF_MISMATCH", where, f"package {pkg.package_id}@{pkg.version} {pkg.digest.value[:12]} "
                       f"≠ ref {m.model_ref.package_id}@{m.model_ref.version} {m.model_ref.digest.value[:12]}")
        if pkg.is_ir:
            from formal_lab_model import ir_digest

            recomputed = ir_digest(pkg.ir).value
            if recomputed != pkg.digest.value:
                report.add("MODEL_DIGEST_MISMATCH", where, f"the package's IR digests to {recomputed[:12]}, it "
                           f"claims {pkg.digest.value[:12]}")
        if pkg.semantic_profile != m.semantic_profile:
            report.add("PROFILE_MISMATCH", where, f"{pkg.semantic_profile} ≠ declared {m.semantic_profile}")
        packages[m.label] = pkg
        for p in m.properties:
            report.checked["property"] += 1
            actual = property_digest(pkg, p.property_id)
            if actual is None:
                report.add("PROPERTY_UNKNOWN", f"{where}.properties[{p.property_id}]", "the model has no such property")
            elif actual != p.digest:
                report.add("PROPERTY_DIGEST_MISMATCH", f"{where}.properties[{p.property_id}]",
                           f"property digest {actual[:12]} ≠ declared {p.digest[:12]}: id and expression disagree")

    # compared versions: each side's artifacts must belong to that side (no before/after mix-up)
    comp = case.comparison
    for side_name in ("before", "after"):
        side = getattr(comp, side_name)
        where = f"comparison.{side_name}"
        if not side.present:
            if not side.absent_reason:
                report.add("ABSENT_WITHOUT_REASON", where, "a missing side must say why")
            if side.artifact_ids:
                report.add("SIDE_MISMATCH", where, "an absent side lists artifacts")
            continue
        if side.revision is None:
            report.add("SIDE_WITHOUT_REVISION", where, "a present side needs its revision")
        for aid in side.artifact_ids:
            ref(where, aid)
            art = by_id.get(aid)
            if art is None:
                continue
            if art.side not in (side_name, "both"):
                report.add("SIDE_MISMATCH", f"{where}[{aid}]", f"artifact belongs to side {art.side!r}")
            if art.revision is not None and side.revision is not None and art.revision != side.revision:
                report.add("SIDE_MISMATCH", f"{where}[{aid}]",
                           f"artifact produced at {art.revision[:12]}, the {side_name} side is {side.revision[:12]}")
    if comp.after.present and comp.after.revision and comp.after.revision != case.software.revision:
        report.add("VERSION_MISMATCH", "comparison.after",
                   f"after revision {comp.after.revision[:12]} ≠ software revision {case.software.revision[:12]}")

    # software: the revision and the trees, where a repository is at hand
    if repo is None:
        report.warnings.append(Problem("SOFTWARE_NOT_VERIFIED_HERE", "software",
                                       "no repository given: revision and tree digests were not recomputed"))
    else:
        report.checked["software"] += 1
        actual = tree_digests(repo, case.software.revision, [t.path for t in case.software.trees])
        if actual is None:
            report.add("REVISION_UNKNOWN", "software.revision",
                       f"{case.software.revision[:12]} (or one of its paths) is not in {repo}")
        else:
            for want, got in zip(case.software.trees, actual, strict=True):
                if want.git_tree != got.git_tree:
                    report.add("TREE_DIGEST_MISMATCH", f"software.trees[{want.path}]",
                               f"tree {got.git_tree[:12]} at {case.software.revision[:12]} ≠ recorded "
                               f"{want.git_tree[:12]}")

    # conformance results: bound to this definition, these models and properties, and to the current evidence
    defn = definition_digest(doc)
    for aid in v.conformance_ids:
        art = by_id.get(aid)
        data = files.read(art.path) if art else None
        if data is None:
            continue
        where = f"conformance[{aid}]"
        try:
            res = ConformanceResult.model_validate_json(data)
        except Exception as exc:
            report.add("CONFORMANCE_UNREADABLE", where, str(exc)[:300])
            continue
        report.checked["conformance"] += 1
        if (res.case.case_id, res.case.case_version) != (case.identity.case_id, case.identity.case_version):
            report.add("CASE_MISMATCH", where, f"result for {res.case.case_id} v{res.case.case_version}")
        elif res.case.definition_digest != defn:
            report.add("STALE_CONFORMANCE", where, "computed for another definition of this case (models, software "
                       "or correspondence changed since)")
        model = next((m for m in case.models if m.model_ref == res.model), None)
        if model is None:
            report.add("VERSION_MISMATCH", where, f"model {res.model.package_id}@{res.model.version} is not one of "
                       "the case's models")
        else:
            spec = next((p for p in model.properties if p.property_id == res.property_id), None)
            if spec is None or spec.digest != res.property_digest:
                report.add("PROPERTY_MISMATCH", where, f"{res.property_id} / {res.property_digest[:12]} does not match "
                           f"the case's property of {model.label}")
        if (res.software.revision, [t.model_dump() for t in res.software.trees]) != \
                (case.software.revision, [t.model_dump() for t in case.software.trees]):
            report.add("VERSION_MISMATCH", where, "computed for another software revision / tree")
        if not res.program_observations and res.correspondence not in ("NOT_COMPARABLE", "UNKNOWN", "UNSUPPORTED"):
            report.add("MISSING_OBSERVATION", where, f"{res.correspondence} without any program observation")
        for obs in res.program_observations:
            o = by_id.get(obs.artifact_id)
            if o is None or o.role != ArtifactRole.OBSERVATION:
                report.add("MISSING_OBSERVATION", where, f"observation {obs.artifact_id} is not in the case")
            elif o.sha256 != obs.sha256:
                report.add("STALE_CONFORMANCE", where, f"computed from observation {obs.sha256[:12]}, the case now "
                           f"holds {o.sha256[:12]}")
        for label, aid, sha in (("model check", res.model_conclusion.artifact_id, res.model_conclusion.artifact_sha256),
                                ("regression", res.program_regression.artifact_id,
                                 res.program_regression.artifact_sha256)):
            if aid is None:
                continue
            o = by_id.get(aid)
            if o is None:
                report.add("UNKNOWN_ARTIFACT_REF", where, f"{label} artifact {aid} is not in the case")
            elif sha is not None and o.sha256 != sha:
                report.add("STALE_CONFORMANCE", where, f"{label} {aid} changed since the result was computed")
    return report, case


# ----------------------------------------------------------------------------------------------------- conformance
def _driver_for(package: ModelPackage, registry: Any = None) -> Any:
    from formal_lab_runtime import default_registry

    reg = registry or default_registry()
    entry = reg.driver_for(package.semantic_profile)
    return reg.create(entry.descriptor.ref(), {}, None).load(package)


def _step_events(bundle: Any) -> dict[int, dict[str, Any]]:
    steps: dict[int, dict[str, Any]] = {}
    for e in bundle.events:
        if not e.logical_step:
            continue
        kind = str(e.event_type)
        slot = steps.setdefault(e.logical_step, {})
        if kind == "OBSERVATION" and "observation" not in slot:
            slot["observation"] = e.payload["observation"]
        elif kind == "ACTION_PROPOSED":
            slot["action"] = e.payload["proposal"]["action"]
        elif kind == "ACTION_OUTCOME":
            slot["outcome"] = e.payload["outcome"]
        elif kind == "EFFECT_COMPARED":
            slot["after"] = e.payload.get("observation_after")
    return steps


def replay_items(package: ModelPackage, bundle_bytes: bytes, *, scope: set[str] | None = None,
                 registry: Any = None) -> tuple[list[ConformanceItem], dict[str, Any]]:
    """Replay a recorded run on `package`: for each executed step, the model predicts from the belief built from the
    recorded observation, and the prediction is compared field by field with the recorded next observation — the same
    rule the engine uses (formal_lab_model.compare.compare_effects). `scope`: state families compared (None = all)."""
    from formal_lab_contracts import GroundAction
    from formal_lab_contracts.bundle import read_bundle
    from formal_lab_model.compare import compare_effects

    loaded = _driver_for(package, registry)
    bundle = read_bundle(bundle_bytes)
    items: list[ConformanceItem] = []
    meta = {"run_id": bundle.manifest.run_id, "events": len(bundle.events), "steps": 0, "skipped": 0}
    for step, slot in sorted(_step_events(bundle).items()):
        if not {"observation", "action", "after"} <= slot.keys() or slot["after"] is None:
            meta["skipped"] += 1
            continue
        meta["steps"] += 1
        obs = Observation.model_validate(slot["observation"])
        after = Observation.model_validate(slot["after"])
        action = GroundAction.model_validate(slot["action"])
        belief = loaded.belief(obs)
        pred = loaded.predict(belief.state, action)
        expected = pred.next_state if pred.applicable and pred.next_state is not None else dict(belief.state)
        written = pred.written_paths if pred.applicable else []
        verified = ((slot.get("outcome") or {}).get("result") or {}).get("verified") or {}
        cmp = compare_effects(expected_post=expected, pre_state=belief.state, observation=after,
                              written_paths=written, expected_by=f"model:{package.package_id}@{package.version}",
                              verified=verified)
        label = f"{action.action_type}({', '.join(str(v) for v in action.params.values())})"
        for d in cmp.diffs:
            family = d.path.split("[", 1)[0]
            in_scope = scope is None or family in scope
            items.append(ConformanceItem(step=step, action=label, element=d.path, predicted=d.expected,
                                         observed=d.observed if in_scope else None,
                                         status=d.status if in_scope else "NOT_COMPARABLE",
                                         evidence=d.evidence if in_scope else "not-comparable"))
    return items, meta


def decide_correspondence(items: list[ConformanceItem], *, has_observation: bool,
                          counterexample: CounterexampleEvidence | None = None,
                          model_conclusion: ModelConclusion | None = None) -> tuple[str, str]:
    """The correspondence layer, apart from the model's own verdict and the program's regression result."""
    counts = Counter(i.status for i in items)
    if not has_observation:
        return "NOT_COMPARABLE", "no program observation: nothing to compare the model with"
    if model_conclusion is not None and model_conclusion.verdict == "UNSUPPORTED":
        return "UNSUPPORTED", "the model's semantics are not supported by the checker for this property"
    if counts["DIFFERENT"]:
        return "DEVIATES", f"{counts['DIFFERENT']} field(s) differ between the model's prediction and the program"
    if counterexample is not None:
        if counterexample.status == "abstraction_error":
            return "SPURIOUS", f"the model counterexample comes from an abstraction error: {counterexample.note}"
        return "CORRESPONDS", f"the model counterexample is reproduced on the program: {counterexample.note}"
    if (model_conclusion is not None and model_conclusion.verdict == "WITNESS" and model_conclusion.query
            and model_conclusion.query.startswith("INVARIANT_VIOLATION")):
        return "UNCONFIRMED", "the model reports a counterexample that the program observations do not reproduce"
    if counts["UNKNOWN"]:
        return "UNKNOWN", f"{counts['UNKNOWN']} field(s) could not be compared (not observed fresh)"
    if not counts["MATCH"]:
        return "NOT_COMPARABLE", "no field in scope was compared"
    return "CORRESPONDS", f"all {counts['MATCH']} compared field(s) match within the declared scope"


def replay_conformance(files: CaseFiles, case: ResearchCase, *, model_label: str, property_id: str,
                       observation_id: str | None, model_conclusion: ModelConclusion,
                       program_regression: ProgramRegression, scope: set[str] | None = None,
                       counterexample: CounterexampleEvidence | None = None, tool_version: str = "0.4.0",
                       registry: Any = None) -> ConformanceResult:
    """A `fal-conformance-result/v1` for one model and property of the case, from one recorded program run."""
    m: CaseModel = next(x for x in case.models if x.label == model_label)
    spec = next(p for p in m.properties if p.property_id == property_id)
    art = {a.id: a for a in case.artifacts}
    package = _parse_package(files.read(art[m.artifact_id].path) or b"")
    items: list[ConformanceItem] = []
    observations: list[ProgramObservation] = []
    meta: dict[str, Any] = {}
    if observation_id is not None and (data := files.read(art[observation_id].path)) is not None:
        items, meta = replay_items(package, data, scope=scope, registry=registry)
        observations.append(ProgramObservation(
            artifact_id=observation_id, sha256=sha256_bytes(data),
            summary=f"run {meta['run_id']}: {meta['steps']} executed step(s) replayed, {meta['events']} events"))
    status, note = decide_correspondence(items, has_observation=bool(observations), counterexample=counterexample,
                                         model_conclusion=model_conclusion)
    scope_text = (f"the {meta.get('steps', 0)} executed step(s) of the recorded run, fields of "
                  f"{', '.join(sorted(scope)) if scope else 'every family'}; an agreement on these steps is not "
                  "semantic equivalence of model and program")
    return ConformanceResult(
        case=CaseRef(case_id=case.identity.case_id, case_version=case.identity.case_version,
                     definition_digest=definition_digest(case)),
        model=m.model_ref,
        software=SoftwareRef(revision=case.software.revision, trees=case.software.trees,
                             config_sha256=case.software.config_sha256),
        property_id=property_id, property_digest=spec.digest, bound=m.bounds, assumptions=m.assumptions,
        model_conclusion=model_conclusion, program_regression=program_regression, program_observations=observations,
        items=items, counterexample=counterexample, correspondence=status, correspondence_note=note, scope=scope_text,
        counts=dict(Counter(i.status for i in items)),
        tools=[ToolIdentity(name="formal_lab_runtime.research.replay_conformance", version=tool_version),
               ToolIdentity(name="formal_lab_model.compare.compare_effects", version=tool_version)])
