"""Build the phase-5B research case (P5B-01/02): tenant/object access isolation on the order service.

One secure-specification model (`tenant_isolation` invariant), one authorization research fixture with a defect/fix
configuration, and three conformance results against the recorded real-service observations:
  defect  (authenticate_only): a subject reaches another tenant        -> DEVIATES (a real, observed model/program gap)
  fix     (per_tenant):        the cross-tenant request is denied       -> CORRESPONDS
  partial (authenticate_only): the request is let through but rejected  -> UNKNOWN (insufficient evidence to decide)
by the business layer, so no state changes

Everything is produced here, for real, against a running subprocess over real SQLite storage. Writes
research/cases/orders-tenant-isolation/ then validates it against this repository.

    scripts/in-vm.sh 'uv run --frozen python scripts/p5b_isolation_case.py'
"""

from __future__ import annotations

import contextlib
import json
import socket
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "orders-tenant-isolation"
CASE_DIR = ROOT / "research" / "cases" / CASE_ID
EXAMPLE_TREE = "examples/local-order-service"
REPO_URL = "https://github.com/3351666087/formal-agent-lab"
BOUND = {"max_steps": 8, "timeout_ms": 60000}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextlib.contextmanager
def fixture(mode: str, data_dir: Path):
    import httpx

    port = free_port()
    proc = subprocess.Popen([sys.executable, "-m", "formal_lab_example_orders.research_isolation",
                             "--data", str(data_dir), "--port", str(port), "--mode", mode],
                            cwd=ROOT, env={**_clean_env()})
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                if httpx.get(f"{base}/health", timeout=1, trust_env=False).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            raise RuntimeError(f"isolation fixture ({mode}) did not start")
        yield base
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)


def _clean_env() -> dict[str, str]:
    import os

    env = {**os.environ, "NO_PROXY": "127.0.0.1,localhost,::1", "no_proxy": "127.0.0.1,localhost,::1"}
    return env


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
    from formal_lab_example_orders.research_isolation import (
        GRANTS,
        MECHANISM,
        PRINCIPALS,
        derive_items,
        isolation_model_package,
        run_access_probes,
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

    def jbytes(obj) -> bytes:
        return (json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode()

    # ---- the secure-specification model + its model-internal check ----
    model = isolation_model_package()
    put("model", "model", "models/orders-tenant-isolation.package.json", model.model_dump_json(indent=1).encode(),
        "application/json", desc="secure specification: an access succeeds only when the subject is granted the tenant")
    qb = run_query(reg, model, CheckQuery(kind="INVARIANT_VIOLATION", property_id="tenant_isolation", bound=BOUND))
    verdict = getattr(qb.result.verdict, "value", str(qb.result.verdict))
    check_art = put("check-isolation", "model_check", "model_checks/tenant_isolation.qb.json",
                    qb.model_copy(update={"package": model}).model_dump_json(indent=1).encode(), "application/json",
                    desc=f"INVARIANT_VIOLATION(tenant_isolation): {verdict}")

    # ---- fixture config + mechanism note ----
    config = {"principals": PRINCIPALS, "grants": {k: sorted(v) for k, v in GRANTS.items()}}
    put("fixture-config", "fixture", "fixtures/authorization.json", jbytes(config), "application/json",
        side="both", rev=revision, desc="the fixed grant table and principals (local test tenants only)")
    put("mechanism", "source", "MECHANISM.md", MECHANISM.encode(), "text/markdown",
        side="both", rev=revision, desc="one-page mechanism note (subject/resource/capability/trust-boundary/action)")
    config_sha = sha256_bytes(canonical_json(config))

    # ---- run the real fixture (both variants) and record the independently-read observations ----
    observations: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        with fixture("authenticate_only", Path(tmp) / "defect") as base:
            observations["defect"] = run_access_probes(base, mode="authenticate_only", scenario="standard")
            observations["partial"] = run_access_probes(base, mode="authenticate_only", scenario="partial")
        with fixture("per_tenant", Path(tmp) / "fix") as base:
            observations["fix"] = run_access_probes(base, mode="per_tenant", scenario="standard")
    obs_art = {}
    obs_art["defect"] = put("obs-defect", "observation", "observations/defect.json", jbytes(observations["defect"]),
                            "application/json", side="before", rev=revision,
                            desc="authenticate_only variant: recorded access attempts + independent oracle")
    obs_art["fix"] = put("obs-fix", "observation", "observations/fix.json", jbytes(observations["fix"]),
                         "application/json", side="after", rev=revision,
                         desc="per_tenant variant: recorded access attempts + independent oracle")
    obs_art["partial"] = put("obs-partial", "observation", "observations/partial.json", jbytes(observations["partial"]),
                             "application/json", side="before", rev=revision,
                             desc="authenticate_only: a cross-tenant write the business layer rejects (not classifiable)")

    # ---- program regression: the fixture's own tests ----
    junit = CASE_DIR / "regression" / "isolation-junit.xml"
    junit.parent.mkdir(parents=True)
    rc = subprocess.run([sys.executable, "-m", "pytest",
                         str(ROOT / EXAMPLE_TREE / "tests" / "test_research_isolation.py"), "-q", "-p",
                         "no:cacheprovider", f"--junitxml={junit}"], cwd=ROOT, capture_output=True, text=True)
    root_xml = ET.parse(junit).getroot()
    suite = root_xml.find("testsuite")
    if suite is None:
        suite = root_xml
    fails = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    tests = int(suite.get("tests", 0))
    reg_status = "PASS" if rc.returncode == 0 and fails == 0 and tests > 0 else "FAIL"
    reg_art = put("regression", "regression", "regression/isolation-junit.xml", junit.read_bytes(), "application/xml",
                  side="both", rev=revision, desc=f"pytest test_research_isolation.py: {tests - fails}/{tests} passed")
    reg_rec = ProgramRegression(status=reg_status, summary=f"{tests - fails}/{tests} passed at {revision[:12]}",
                                artifact_id=reg_art.id, artifact_sha256=reg_art.sha256)

    # ---- task input for phase 6 (model + property + mechanism + fixture; NO reference answers) ----
    prop_digest = property_digest(model, "tenant_isolation")
    task_input = {"model": json.loads(model.model_dump_json()),
                  "property": {"id": "tenant_isolation", "kind": "invariant", "digest": prop_digest},
                  "mechanism": MECHANISM, "grants": {k: sorted(v) for k, v in GRANTS.items()},
                  "question": "Does the authorization component enforce tenant isolation on every access?"}
    put("task-input", "task_input", "task_inputs/isolation-task.json", jbytes(task_input), "application/json",
        desc="phase-6 task material: model + property + mechanism + grants only (no reference answers)")

    # ---- case definition ----
    identity = CaseIdentity(case_id=CASE_ID, case_version=1, track="implementation_conformance",
                            mechanism_family="access-control-isolation",
                            title="Order service: tenant/object access isolation",
                            purpose="Verify that the authorization component isolates tenants on the real order "
                            "service: a subject may use a tenant only when granted. Defensive software verification "
                            "on local test tenants; the oracle reads real state, never a self-reported success.")
    software = SoftwareSource(repository=REPO_URL, license="Apache-2.0", revision=revision,
                              trees=tree_digests(ROOT, revision, [EXAMPLE_TREE]) or [], config_sha256=config_sha,
                              variant="own_test_variant",
                              variant_note="the order service plus the phase-5B authorization research fixture "
                              "(research_isolation.py), separate from the default startup path; defect/fix is one "
                              "configuration flag (authenticate_only vs per_tenant) on the authorization component")
    comparison = Comparison(
        before=VersionSide(present=True, revision=revision, artifact_ids=["obs-defect", "obs-partial"]),
        after=VersionSide(present=True, revision=revision, artifact_ids=["obs-fix", "regression"]),
        change_basis="configuration: the authorization mode — authenticate_only omits the object-level tenant grant "
        "check (defect); per_tenant enforces it (fix)",
        regression_test_source=f"{EXAMPLE_TREE}/tests/test_research_isolation.py")
    assumptions = ["finite abstraction: two subjects, two tenants, one access action; reads and writes both abstracted "
                   "as access(subject, tenant)",
                   "fixed synthetic grant table and instances; local test tenants only"]
    uncovered = ["concurrency between requests", "token/credential strength and transport", "partial-read leakage that "
                 "is not visible in the tenant's stored state (kept UNKNOWN, not asserted)"]
    spec_model = CaseModel(label="secure-spec", role="reference", model_ref=model.ref(), artifact_id="model",
                           semantic_profile=model.semantic_profile,
                           properties=[PropertySpec(property_id="tenant_isolation", kind="invariant",
                                                    digest=prop_digest,
                                                    summary="no access succeeds unless the subject is granted the "
                                                    "tenant: forall s,t: accessed[s][t] -> grant[s][t]")],
                           bounds=Bounds(max_steps=BOUND["max_steps"], timeout_ms=BOUND["timeout_ms"],
                                         inputs="two subjects × two tenants; the fixed grant table"),
                           assumptions=assumptions, uncovered_semantics=uncovered)
    iso = f"{EXAMPLE_TREE}/src/formal_lab_example_orders/research_isolation.py"
    correspondence = [
        Correspondence(program=ProgramElement(component="authorization layer", path=iso,
                                              symbol="create_isolation_app.Authorization.dispatch"),
                       model=ModelElement(kind="action", name="access"), relation="MEASURED",
                       evidence_artifact_ids=["obs-defect", "obs-fix"],
                       note="the per-request authorization decision is the model action's precondition grant[s][t]"),
        Correspondence(program=ProgramElement(component="grant table", path=iso, symbol="PRINCIPALS"),
                       model=ModelElement(kind="constant", name="grant"), relation="MANUAL_REVIEW",
                       note="the principal→tenant grants are the model constant grant[subject][tenant]"),
        Correspondence(program=ProgramElement(component="tenant store",
                                              path=f"{EXAMPLE_TREE}/src/formal_lab_example_orders/service.py",
                                              symbol="store"),
                       model=ModelElement(kind="state", name="accessed"), relation="MEASURED",
                       evidence_artifact_ids=["obs-defect"],
                       note="a landed cross-tenant write / returned read, read back by the tenant's owner, is accessed"),
    ]

    # ---- conformance results (one model, three recorded observations) ----
    model_conclusion = ModelConclusion(verdict=verdict, query="INVARIANT_VIOLATION(tenant_isolation)",
                                       explanation="the secure specification admits no state violating the invariant "
                                       "within the bound", artifact_id=check_art.id, artifact_sha256=check_art.sha256)
    software_ref = SoftwareRef(revision=revision, trees=software.trees, config_sha256=config_sha)

    def build_conf(obs_key: str) -> ConformanceResult:
        observation = observations[obs_key]
        art = obs_art[obs_key]
        raw = derive_items(observation)
        items = [ConformanceItem(**d) for d in raw]
        status, note = decide_correspondence(items, has_observation=True)
        counts = dict(Counter(i.status for i in items))
        scope = (f"the {len(items)} recorded access attempt(s) of the {observation['mode']} variant, over subjects × "
                 "tenants in the grant table; agreement on these attempts is not a semantic-equivalence proof")
        return ConformanceResult(
            case=CaseRef(case_id=CASE_ID, case_version=1, definition_digest="0" * 64),  # filled after definition_digest
            model=model.ref(), software=software_ref, property_id="tenant_isolation", property_digest=prop_digest,
            bound=spec_model.bounds, assumptions=assumptions, model_conclusion=model_conclusion,
            program_regression=reg_rec,
            program_observations=[ProgramObservation(artifact_id=art.id, sha256=art.sha256,
                                  summary=f"{observation['mode']}/{observation['scenario']}: "
                                  f"{len(observation['attempts'])} attempt(s)")],
            items=items, correspondence=status, correspondence_note=note, scope=scope, counts=counts,
            tools=[ToolIdentity(name="formal_lab_example_orders.research_isolation.derive_items", version="0.4.0"),
                   ToolIdentity(name="formal_lab_runtime.research.decide_correspondence", version="0.4.0")])

    def build(conformance_ids, reference_ids, digest) -> ResearchCase:
        validation = Validation(
            criteria=[Criterion(id="c-defect-deviates", text="the defect variant lets a subject reach another tenant"),
                      Criterion(id="c-fix-corresponds", text="the fix variant denies the cross-tenant access"),
                      Criterion(id="c-partial-unknown", text="a request the business layer rejects stays UNKNOWN"),
                      Criterion(id="c-regression", text="same-tenant access keeps working in both variants")],
            fixture_ids=["fixture-config"], observation_ids=["obs-defect", "obs-fix", "obs-partial"],
            model_check_ids=["check-isolation"], regression_ids=["regression"], conformance_ids=conformance_ids,
            reference_ids=reference_ids, task_input_ids=["task-input"])
        reproduction = Reproduction(
            environment="Colima VM; the isolation fixture as a uvicorn subprocess over real SQLite; Z3 verifier",
            reset="each tenant reset by its own authorized principal (POST /t/{tenant}/admin/reset)",
            cleanup="the fixture subprocess is terminated and its data dir removed", seeds=[1],
            nondeterminism=["none in scope: fixed grants, fixed instances, local subprocess"],
            commands=[Command(command="python scripts/p5b_isolation_case.py", purpose="build and validate this case"),
                      Command(command=f"pytest {EXAMPLE_TREE}/tests/test_research_isolation.py",
                              purpose="program regression"),
                      Command(command="python -m formal_lab_example_orders.research_isolation --mode per_tenant",
                              purpose="run the fixture")],
            prerequisites=["uv sync --frozen", "the order-service example installed in the project venv"])
        return ResearchCase(identity=identity, software=software, comparison=comparison, models=[spec_model],
                            correspondence=correspondence, validation=validation, reproduction=reproduction,
                            artifacts=arts, case_digest=digest)

    zero = "0" * 64
    provisional = build([], [], zero)
    defn = definition_digest(provisional.model_dump(mode="json"))
    confs = {k: build_conf(k).model_copy(update={"case": CaseRef(case_id=CASE_ID, case_version=1,
                                                                 definition_digest=defn)}) for k in
             ("defect", "fix", "partial")}
    for key, aid, rel in (("defect", "conf-defect", "conformance/defect.result.json"),
                          ("fix", "conf-fix", "conformance/fix.result.json"),
                          ("partial", "conf-partial", "conformance/partial.result.json")):
        put(aid, "conformance", rel, confs[key].model_dump_json(indent=1).encode(), "application/json",
            desc=f"{key}: {confs[key].correspondence}")

    reference = {"defect": {"correspondence": confs["defect"].correspondence, "counts": confs["defect"].counts},
                 "fix": {"correspondence": confs["fix"].correspondence, "counts": confs["fix"].counts},
                 "partial": {"correspondence": confs["partial"].correspondence, "counts": confs["partial"].counts},
                 "model_conclusion": verdict, "regression": reg_status,
                 "note": "expected verdicts for these recorded observations; verification only, never a task input"}
    put("reference", "reference", "reference/expected.json", jbytes(reference), "application/json",
        desc="expected correspondence verdicts (defect DEVIATES, fix CORRESPONDS, partial UNKNOWN)")

    final_noidg = build(["conf-defect", "conf-fix", "conf-partial"], ["reference"], zero)
    digest = compute_case_digest(final_noidg.model_dump(mode="json"))
    final = build(["conf-defect", "conf-fix", "conf-partial"], ["reference"], digest)
    (CASE_DIR / "case.json").write_text(final.model_dump_json(indent=1) + "\n")

    report, _ = validate_case(load_case(CASE_DIR), repo=ROOT)
    print(json.dumps({"revision": revision, "model_conclusion": verdict, "regression": reg_status,
                      "correspondence": {k: confs[k].correspondence for k in confs},
                      "validation": report.as_dict()}, indent=2, ensure_ascii=False))
    if not report.ok:
        return 1
    print("OK: case validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
