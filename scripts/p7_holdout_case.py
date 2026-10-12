"""Build the phase-7 held-out research case (P7-01): a token-bucket capacity limiter — a different mechanism from the
order service and the tenant-isolation fixture, to check the method generalises beyond the first sample.

One secure-specification model (`within_capacity` invariant), the defect/fix program variants, and two conformance
results against the recorded runs: the uncapped (defect) bucket DEVIATES from the capped specification, the capped
(fix) bucket CORRESPONDS. Everything is produced here, in process, from real program runs. Writes
research/cases/ratelimit-token-bucket/ and validates it.

    scripts/in-vm.sh 'uv run --frozen python scripts/p7_holdout_case.py'
"""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "ratelimit-token-bucket"
CASE_DIR = ROOT / "research" / "cases" / CASE_ID
EXAMPLE_TREE = "examples/local-order-service"
REPO_URL = "https://github.com/3351666087/formal-agent-lab"
BOUND = {"max_steps": 10, "timeout_ms": 30000}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    from formal_lab_contracts import CheckQuery, canonical_json
    from formal_lab_contracts.research import (
        Bounds,
        CaseArtifact,
        CaseIdentity,
        CaseModel,
        CaseRef,
        Command,
        Comparison,
        ConformanceItem,
        ConformanceResult,
        Correspondence,
        Criterion,
        ModelConclusion,
        ModelElement,
        ProgramElement,
        ProgramObservation,
        ProgramRegression,
        PropertySpec,
        Reproduction,
        ResearchCase,
        SoftwareRef,
        SoftwareSource,
        ToolIdentity,
        Validation,
        VersionSide,
    )
    from formal_lab_example_orders.research_ratelimit import (
        CAPACITY,
        PROBE,
        REFILL,
        capacity_model_package,
        derive_items,
        run_capacity_probes,
    )
    from formal_lab_runtime import default_registry
    from formal_lab_runtime.query import run_query
    from formal_lab_runtime.research import (
        compute_case_digest,
        decide_correspondence,
        definition_digest,
        load_case,
        property_digest,
        sha256_bytes,
        tree_digests,
        validate_case,
    )

    revision = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--", EXAMPLE_TREE, "uv.lock"):
        raise SystemExit(f"{EXAMPLE_TREE} or uv.lock has uncommitted changes: a case must name a real revision")
    reg = default_registry()
    if CASE_DIR.exists():
        import shutil

        shutil.rmtree(CASE_DIR)
    CASE_DIR.mkdir(parents=True)
    arts: list[CaseArtifact] = []

    def put(aid, role, rel, data: bytes, media, *, side="none", rev=None, desc=None) -> CaseArtifact:
        path = CASE_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        a = CaseArtifact(id=aid, role=role, path=rel, sha256=sha256_bytes(data), media_type=media, side=side,
                         revision=rev, description=desc)
        arts.append(a)
        return a

    def jb(obj) -> bytes:
        return (json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode()

    # model + its model-internal check
    model = capacity_model_package()
    put("model", "model", "models/capacity.package.json", model.model_dump_json(indent=1).encode(),
        "application/json", desc="secure specification: refill never raises the bucket above its capacity")
    qb = run_query(reg, model, CheckQuery(kind="INVARIANT_VIOLATION", property_id="within_capacity", bound=BOUND))
    verdict = getattr(qb.result.verdict, "value", str(qb.result.verdict))
    check_art = put("check-capacity", "model_check", "model_checks/within_capacity.qb.json",
                    qb.model_copy(update={"package": model}).model_dump_json(indent=1).encode(), "application/json",
                    desc=f"INVARIANT_VIOLATION(within_capacity): {verdict}")

    config = {"capacity": CAPACITY, "refill": REFILL, "sequence": list(PROBE)}
    put("fixture-config", "fixture", "fixtures/limiter.json", jb(config), "application/json", side="both", rev=revision,
        desc="the fixed capacity, refill amount and operation sequence (held out)")
    put("mechanism", "source", "MECHANISM.md", MECHANISM.encode(), "text/markdown", side="both", rev=revision,
        desc="one-page mechanism note (subject/resource/capability/trust-boundary/action/property/oracle)")
    config_sha = sha256_bytes(canonical_json(config))

    observations = {m: run_capacity_probes(mode=m) for m in ("uncapped", "capped")}
    obs_art = {
        "uncapped": put("obs-defect", "observation", "observations/uncapped.json", jb(observations["uncapped"]),
                        "application/json", side="before", rev=revision, desc="defect variant: refill ignores capacity"),
        "capped": put("obs-fix", "observation", "observations/capped.json", jb(observations["capped"]),
                      "application/json", side="after", rev=revision, desc="fix variant: refill caps at capacity"),
    }

    junit = CASE_DIR / "regression" / "ratelimit-junit.xml"
    junit.parent.mkdir(parents=True)
    rc = subprocess.run([sys.executable, "-m", "pytest",
                         str(ROOT / EXAMPLE_TREE / "tests" / "test_research_ratelimit.py"), "-q", "-p",
                         "no:cacheprovider", f"--junitxml={junit}"], cwd=ROOT, capture_output=True, text=True)
    root_xml = ET.parse(junit).getroot()
    suite = root_xml.find("testsuite") or root_xml
    fails = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    tests = int(suite.get("tests", 0))
    reg_status = "PASS" if rc.returncode == 0 and fails == 0 and tests > 0 else "FAIL"
    reg_art = put("regression", "regression", "regression/ratelimit-junit.xml", junit.read_bytes(), "application/xml",
                  side="both", rev=revision, desc=f"pytest test_research_ratelimit.py: {tests - fails}/{tests} passed")
    reg_rec = ProgramRegression(status=reg_status, summary=f"{tests - fails}/{tests} passed at {revision[:12]}",
                                artifact_id=reg_art.id, artifact_sha256=reg_art.sha256)

    prop_digest = property_digest(model, "within_capacity")
    task_input = {"model": json.loads(model.model_dump_json()),
                  "property": {"id": "within_capacity", "kind": "invariant", "digest": prop_digest},
                  "mechanism": MECHANISM, "capacity": CAPACITY, "refill": REFILL,
                  "question": "Did the limiter stay within its capacity on the recorded run?"}
    put("task-input", "task_input", "task_inputs/capacity-task.json", jb(task_input), "application/json",
        desc="phase-6 task material: model + property + mechanism only (no reference answers)")

    identity = CaseIdentity(case_id=CASE_ID, case_version=1, track="implementation_conformance",
                            mechanism_family="rate-limit-capacity",
                            title="Token-bucket capacity limiter (phase-7 held-out case)",
                            purpose="Verify that a token-bucket limiter respects its capacity, as a new held-out case "
                            "with a mechanism different from the order service — to check the method generalises.")
    software = SoftwareSource(repository=REPO_URL, license="Apache-2.0", revision=revision,
                              trees=tree_digests(ROOT, revision, [EXAMPLE_TREE]) or [], config_sha256=config_sha,
                              variant="own_test_variant",
                              variant_note="the phase-7 token-bucket research fixture (research_ratelimit.py), a "
                              "finite in-process program; defect/fix is one line of refill (uncapped vs capped)")
    comparison = Comparison(
        before=VersionSide(present=True, revision=revision, artifact_ids=["obs-defect"]),
        after=VersionSide(present=True, revision=revision, artifact_ids=["obs-fix", "regression"]),
        change_basis="the refill operation: uncapped (defect, adds with no cap) vs capped (fix, min(capacity, …))",
        regression_test_source=f"{EXAMPLE_TREE}/tests/test_research_ratelimit.py")
    assumptions = ["finite abstraction: one bucket, integer token count 0..2·capacity, a fixed operation sequence",
                   "the capped specification is the reference; the program is the system under test"]
    uncovered = ["concurrency between callers", "wall-clock refill timing (the model steps are logical)"]
    spec_model = CaseModel(label="secure-spec", role="reference", model_ref=model.ref(), artifact_id="model",
                           semantic_profile=model.semantic_profile,
                           properties=[PropertySpec(property_id="within_capacity", kind="invariant", digest=prop_digest,
                                                    summary="the bucket is never above its capacity: tokens <= cap")],
                           bounds=Bounds(max_steps=BOUND["max_steps"], timeout_ms=BOUND["timeout_ms"],
                                         inputs=f"capacity {CAPACITY}, refill {REFILL}, the fixed {len(PROBE)}-op run"),
                           assumptions=assumptions, uncovered_semantics=uncovered)
    rl = f"{EXAMPLE_TREE}/src/formal_lab_example_orders/research_ratelimit.py"
    correspondence = [
        Correspondence(program=ProgramElement(component="refill", path=rl, symbol="TokenBucket.refill"),
                       model=ModelElement(kind="action", name="refill"), relation="MEASURED",
                       evidence_artifact_ids=["obs-defect", "obs-fix"],
                       note="the program's refill vs the model's capped refill"),
        Correspondence(program=ProgramElement(component="token count", path=rl, symbol="TokenBucket.tokens"),
                       model=ModelElement(kind="state", name="tokens"), relation="MEASURED",
                       evidence_artifact_ids=["obs-defect"], note="the observed token count after each operation"),
        Correspondence(program=ProgramElement(component="capacity", path=rl, symbol="TokenBucket.capacity"),
                       model=ModelElement(kind="constant", name="cap"), relation="MANUAL_REVIEW",
                       note="the bucket capacity is the model constant cap"),
    ]
    model_conclusion = ModelConclusion(verdict=verdict, query="INVARIANT_VIOLATION(within_capacity)",
                                       explanation="the capped specification admits no state above capacity within the "
                                       "bound", artifact_id=check_art.id, artifact_sha256=check_art.sha256)
    software_ref = SoftwareRef(revision=revision, trees=software.trees, config_sha256=config_sha)

    def build_conf(mode: str) -> ConformanceResult:
        observation, art = observations[mode], obs_art[mode]
        items = [ConformanceItem(**d) for d in derive_items(observation)]
        status, note = decide_correspondence(items, has_observation=True)
        scope = (f"the {len(items)} operations of the recorded {mode} run; agreement is not a semantic-equivalence "
                 "proof")
        return ConformanceResult(
            case=CaseRef(case_id=CASE_ID, case_version=1, definition_digest="0" * 64), model=model.ref(),
            software=software_ref, property_id="within_capacity", property_digest=prop_digest, bound=spec_model.bounds,
            assumptions=assumptions, model_conclusion=model_conclusion, program_regression=reg_rec,
            program_observations=[ProgramObservation(artifact_id=art.id, sha256=art.sha256,
                                  summary=f"{mode}: {len(observation['steps'])} operations")],
            items=items, correspondence=status, correspondence_note=note, scope=scope,
            counts=dict(Counter(i.status for i in items)),
            tools=[ToolIdentity(name="formal_lab_example_orders.research_ratelimit.derive_items", version="0.4.0"),
                   ToolIdentity(name="formal_lab_runtime.research.decide_correspondence", version="0.4.0")])

    def build(conformance_ids, reference_ids, digest) -> ResearchCase:
        validation = Validation(
            criteria=[Criterion(id="c-defect-deviates", text="the uncapped variant exceeds capacity (deviates)"),
                      Criterion(id="c-fix-corresponds", text="the capped variant stays within capacity (corresponds)"),
                      Criterion(id="c-regression", text="the fixture's own tests pass at this revision")],
            fixture_ids=["fixture-config"], observation_ids=["obs-defect", "obs-fix"],
            model_check_ids=["check-capacity"], regression_ids=["regression"], conformance_ids=conformance_ids,
            reference_ids=reference_ids, task_input_ids=["task-input"])
        reproduction = Reproduction(
            environment="Colima VM; an in-process finite program (no network); Z3 verifier",
            reset="each run starts a fresh TokenBucket", cleanup="none (in-process)", seeds=[],
            nondeterminism=["none: a fixed operation sequence, deterministic program"],
            commands=[Command(command="python scripts/p7_holdout_case.py", purpose="build and validate this case"),
                      Command(command=f"pytest {EXAMPLE_TREE}/tests/test_research_ratelimit.py",
                              purpose="program regression")],
            prerequisites=["uv sync --frozen", "the order-service example installed in the project venv"])
        return ResearchCase(identity=identity, software=software, comparison=comparison, models=[spec_model],
                            correspondence=correspondence, validation=validation, reproduction=reproduction,
                            artifacts=arts, case_digest=digest)

    zero = "0" * 64
    provisional = build([], [], zero)
    defn = definition_digest(provisional.model_dump(mode="json"))
    confs = {m: build_conf(m).model_copy(update={"case": CaseRef(case_id=CASE_ID, case_version=1,
                                                                 definition_digest=defn)}) for m in observations}
    for mode, aid, rel in (("uncapped", "conf-defect", "conformance/defect.result.json"),
                           ("capped", "conf-fix", "conformance/fix.result.json")):
        put(aid, "conformance", rel, confs[mode].model_dump_json(indent=1).encode(), "application/json",
            desc=f"{mode}: {confs[mode].correspondence}")
    reference = {"defect": {"correspondence": confs["uncapped"].correspondence, "within_capacity": False},
                 "fix": {"correspondence": confs["capped"].correspondence, "within_capacity": True},
                 "model_conclusion": verdict, "regression": reg_status,
                 "note": "expected verdicts for the recorded runs; verification only, never a task input"}
    put("reference", "reference", "reference/expected.json", jb(reference), "application/json",
        desc="expected correspondence verdicts (defect DEVIATES, fix CORRESPONDS)")

    final_noidg = build(["conf-defect", "conf-fix"], ["reference"], zero)
    digest = compute_case_digest(final_noidg.model_dump(mode="json"))
    final = build(["conf-defect", "conf-fix"], ["reference"], digest)
    (CASE_DIR / "case.json").write_text(final.model_dump_json(indent=1) + "\n")

    report, _ = validate_case(load_case(CASE_DIR), repo=ROOT)
    art_by_id = {a.id: a for a in arts}
    if report.ok:
        _build_study(observations, art_by_id, prop_digest)
    print(json.dumps({"revision": revision, "model_conclusion": verdict, "regression": reg_status,
                      "correspondence": {m: confs[m].correspondence for m in confs},
                      "validation": report.as_dict()}, indent=2, ensure_ascii=False))
    if not report.ok:
        return 1
    print("OK: case validated and held-out study p7-holdout written")
    return 0


CAPACITY_SCHEMA = {
    "type": "object",
    "properties": {"within_capacity": {"type": "boolean"}, "first_overflow": {"type": ["integer", "null"]},
                   "rationale": {"type": "string"}},
    "required": ["within_capacity", "first_overflow"], "additionalProperties": False,
}


def _build_study(observations: dict, art_by_id: dict, prop_digest: str) -> None:
    """The frozen held-out study p7-holdout: before/after (defect/fix) × 2 relay models × 2 replicates = 8 requests.
    The reference answers were fixed from the program runs above, before any model saw the task."""
    from formal_lab_contracts.research import ResearchStudy

    study_dir = ROOT / "research" / "studies" / "p7-holdout"
    mech = (CASE_DIR / "MECHANISM.md").read_text()
    tasks = []
    for variant, mode in (("defect", "uncapped"), ("fix", "capped")):
        obs = observations[mode]
        rows = "\n".join(f"| {s['index']} | {s['op']} | {s['result'] or '—'} | {s['observed_tokens']} |"
                         for s in obs["steps"])
        body = (f"{mech}\n\n## The recorded run to judge\n\nCapacity is {obs['capacity']}. Each row is one operation "
                "and the bucket's token count straight after it:\n\n| step | operation | result | tokens after |\n"
                f"|---|---|---|---|\n{rows}\n")
        (study_dir / "inputs").mkdir(parents=True, exist_ok=True)
        (study_dir / "inputs" / f"capacity-{variant}.md").write_text(body)
        overflow = next((s["index"] for s in obs["steps"] if s["observed_tokens"] > obs["capacity"]), None)
        obs_art, conf_art = art_by_id["obs-" + variant], art_by_id["conf-" + variant]
        reference = {
            "case_id": CASE_ID, "variant": variant,
            "observation": {"path": f"research/cases/{CASE_ID}/{obs_art.path}", "sha256": obs_art.sha256},
            "conformance": {"path": f"research/cases/{CASE_ID}/{conf_art.path}", "sha256": conf_art.sha256},
            "answer": {"within_capacity": overflow is None, "first_overflow": overflow},
            "criterion": "within_capacity must match the recorded run (any token count above capacity is a "
                         "violation); program correspondence is the case conformance verdict"}
        (study_dir / "reference").mkdir(parents=True, exist_ok=True)
        (study_dir / "reference" / f"capacity-{variant}.json").write_text(json.dumps(reference, indent=1) + "\n")
        tasks.append({
            "task_id": f"capacity-{variant}", "track": "implementation_conformance", "case_id": CASE_ID,
            "case_version": 1, "representation_id": "transcript",
            "purpose": f"judge whether a token-bucket limiter stayed within its capacity on a recorded run "
                       f"({'before' if variant == 'defect' else 'after'} the fix)",
            "inputs": [f"inputs/capacity-{variant}.md"],
            "question": "Did the limiter stay within its capacity on this run? Answer within_capacity (true/false) and "
                        "first_overflow (the step index where it first exceeded capacity, or null).",
            "answer_format": "json", "answer_schema": CAPACITY_SCHEMA, "reference": f"reference/capacity-{variant}.json",
            "scorer_id": "ratelimit.capacity-judgment", "scorer_version": "1", "bound": {"operations": len(obs["steps"])}})
    providers = [
        {"provider_config_id": "gpt-6-astra-relay", "provider": "openai", "api": "openai.chat.completions",
         "api_version": "v1", "route": "COMPATIBLE_RELAY", "base_url_setting": "FAL_RESEARCH_RELAY_BASE_URL",
         "api_key_setting": "FAL_RESEARCH_GPT_API_KEY", "model": "gpt-6-astra", "params": {"max_completion_tokens": 4000},
         "comparability_note": "relay route; returned model name is the relay's report, not verifiable"},
        {"provider_config_id": "claude-opus-5-5-relay", "provider": "anthropic", "api": "anthropic.messages",
         "api_version": "2023-06-01", "route": "COMPATIBLE_RELAY", "base_url_setting": "FAL_RESEARCH_RELAY_BASE_URL",
         "api_key_setting": "FAL_RESEARCH_CLAUDE_API_KEY", "model": "claude-opus-5-5", "params": {"max_tokens": 4000},
         "comparability_note": "relay route; returned model name is the relay's report, not verifiable"}]
    study = ResearchStudy.model_validate({
        "study_id": "p7-holdout", "title": "Phase 7 held-out case: token-bucket capacity judgment",
        "purpose": "a new real case with a different mechanism, frozen before any model saw it, to check the method "
                   "generalises beyond the first sample — a descriptive 8-request batch, not a ranking claim",
        "tasks": tasks, "providers": providers, "assistance_modes": ["STATIC_UNASSISTED"], "replicates": 2,
        "rubric_id": "fal-research-rubric", "rubric_version": "1", "primary_metric": "correct",
        "secondary_metrics": ["format_valid", "refused", "responded", "program_corresponds", "output_tokens"],
        "limits": {"max_calls": 16, "max_http_attempts": 32, "max_output_tokens_per_call": 4000,
                   "max_total_output_tokens": 32000, "network_retries": 1},
        "comparisons": [{"vary": "provider", "a": "gpt-6-astra-relay", "b": "claude-opus-5-5-relay",
                         "note": "both via the same relay; engineering reading, not a verified provider comparison"}],
        "missing_policy": "the denominator is the 8 planned units; a unit without a model-produced response is MISSING "
                          "in the model metrics; a refusal is never retried; the frozen call cap (16) covers the 8 "
                          "planned requests plus bounded resamples, and the denominator never changes"})
    (study_dir / "study.json").write_text(study.model_dump_json(indent=1, exclude_none=True) + "\n")


MECHANISM = """\
# Mechanism: token-bucket capacity limiter (phase-7 held-out case)

A finite, in-process program (no network), different in mechanism from the order service and the tenant-isolation
fixture.

- **Subject.** A caller driving the limiter through a fixed operation sequence (`refill`, `take`). It controls only
  which operation runs next; it cannot set the token count directly.
- **Resource.** One bucket holding an integer token count between 0 and twice the capacity.
- **Capability.** `take()` spends one token when any remain (else it is denied); `refill()` adds the refill amount.
- **Trust boundary.** The capacity cap is enforced inside `refill`; the caller cannot bypass it. The defect is a
  missing cap in that one place.
- **Action.** `take` (precondition: tokens > 0; effect: tokens − 1) and `refill` (secure effect: tokens ←
  min(capacity, tokens + refill)).
- **Property.** `within_capacity` (invariant): the bucket is never above its capacity (`tokens ≤ cap`). Machine-checked
  on the finite model.
- **Oracle.** The real program's token count after each operation, read independently; the capped specification is the
  model. A recorded run above capacity is a violation.
"""


if __name__ == "__main__":
    raise SystemExit(main())
