"""Build the first research case (P5A-01): the order service's processing-speed model/reality deviation.

The program is this repo's own order service (examples/local-order-service) at HEAD, run under its `deviation`
operating condition (station p2 at half speed). Two models are compared against the one recorded run:
  belief  (v1) assumes nominal speed  -> replay DEVIATES from the program
  revised (v2) encodes slow[p2]=true  -> replay CORRESPONDS with the program
Every artifact below is produced here, for real. Writes research/cases/orders-p2-speed/ then validates it.

    scripts/in-vm.sh 'UV_PROJECT_ENVIRONMENT=$HOME/.venvs/formal-agent-lab uv run --frozen python scripts/p5a_orders_case.py'
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "orders-p2-speed"
CASE_DIR = ROOT / "research" / "cases" / CASE_ID
EXAMPLE_TREE = "examples/local-order-service"
REPO_URL = "https://github.com/3351666087/formal-agent-lab"
BOUND = {"max_steps": 26, "timeout_ms": 120000}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    from formal_lab_contracts import CheckQuery, ModelSource, canonical_json
    from formal_lab_contracts.research import (
        Bounds,
        CaseArtifact,
        CaseIdentity,
        CaseModel,
        Command,
        Comparison,
        Correspondence,
        Criterion,
        ModelConclusion,
        ModelElement,
        ProgramElement,
        ProgramRegression,
        PropertySpec,
        Reproduction,
        ResearchCase,
        SoftwareSource,
        Validation,
        VersionSide,
    )
    from formal_lab_env.ir_world import truth_model_ir
    from formal_lab_example_orders.instance import CASES, instance
    from formal_lab_example_orders.lifecycle import ServiceManager
    from formal_lab_example_orders.model import model_package
    from formal_lab_example_orders.scenarios import EVALUATORS, scenario
    from formal_lab_model import build_package
    from formal_lab_runtime import default_registry, make_manifest, run_local
    from formal_lab_runtime.bundles import bundle_from_local
    from formal_lab_runtime.query import run_query
    from formal_lab_runtime.research import (
        CaseFiles,
        compute_case_digest,
        load_case,
        property_digest,
        replay_conformance,
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

    def put(aid: str, role: str, rel: str, data: bytes, media: str, *, side: str = "none", rev: str | None = None,
            desc: str | None = None) -> CaseArtifact:
        path = CASE_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        a = CaseArtifact(id=aid, role=role, path=rel, sha256=sha256_bytes(data), media_type=media, side=side,
                         revision=rev, description=desc)
        arts.append(a)
        return a

    # ---- models: the belief (nominal) and the phase-3 revision (slow[p2] = true) ----
    v1 = model_package()
    slow = CASES["deviation"]["service"]["slow_stations"]
    ir2 = truth_model_ir(v1, {f"slow[{st}]": True for st in slow})
    v2 = build_package(ir2, package_id=v1.package_id, version=2,
                       source=ModelSource(format="fal-ir-json/v1", text=ir2.model_dump_json(),
                                          origin=f"revision slow{slow}: phase-3 model revision of {v1.package_id}@1"))
    put("model-v1", "model", "models/orders-v1.package.json", v1.model_dump_json(indent=1).encode(),
        "application/json", desc="belief model: every station at nominal speed")
    put("model-v2", "model", "models/orders-v2.package.json", v2.model_dump_json(indent=1).encode(),
        "application/json", desc="revised model: slow[p2] = true")

    # ---- fixture: the instance and the lab operating conditions the program ran with ----
    inst = instance("deviation", 1)
    conditions = CASES["deviation"]["service"]
    fixture = {"case": "deviation", "seed": 1, "label": CASES["deviation"].get("label"),
               "instance": inst.as_dict(), "conditions": conditions}
    put("fixture-deviation", "fixture", "fixtures/deviation.json",
        (json.dumps(fixture, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode(), "application/json",
        side="after", rev=revision, desc="instance seed 1 + operating conditions (station p2 at half speed)")
    config_sha = sha256_bytes(canonical_json(conditions))

    # ---- program observations: one real run against the service process (rule strategy, belief model in loop) ----
    with tempfile.TemporaryDirectory() as tmp:
        mgr = ServiceManager(Path(tmp), project="p5a-case").start()
        try:
            mgr.ready()
            sc = scenario("deviation", seed=1, endpoint=mgr.endpoint, tenant="p5a").model_copy(
                update={"model": v1.ref()})
            m = make_manifest(run_id="run_p5a_orders_deviation", project_id="research", scenario=sc, package=v1,
                              registry=reg, seed=1, evaluators=EVALUATORS, config={"initial_check_horizon": 0})
            res = run_local(m, v1, reg)
        finally:
            mgr.close(remove_data=True)
    bundle = bundle_from_local(res, v1)
    put("obs-run", "observation", "observations/run-deviation.replay.zip", bundle, "application/zip",
        side="after", rev=revision, desc="replay bundle of the recorded deviation run against the real service")

    # ---- model-internal checks: Z3 GOAL_REACHABILITY(all_completed) on each model ----
    def check(label: str, pkg: object) -> tuple[CaseArtifact, str]:
        qb = run_query(reg, pkg, CheckQuery(kind="GOAL_REACHABILITY", property_id="all_completed", bound=BOUND))
        verdict = getattr(qb.result.verdict, "value", str(qb.result.verdict))
        exported = qb.model_copy(update={"package": pkg})
        art = put(f"check-{label}", "model_check", f"model_checks/{label}-all_completed.qb.json",
                  exported.model_dump_json(indent=1).encode(), "application/json",
                  desc=f"GOAL_REACHABILITY(all_completed) on {label}: {verdict}")
        return art, verdict

    check_v1, verdict_v1 = check("v1", v1)
    check_v2, verdict_v2 = check("v2", v2)

    # ---- program regression: the service's own test suite at this revision ----
    junit = CASE_DIR / "regression" / "orders-junit.xml"
    junit.parent.mkdir(parents=True)
    rc = subprocess.run([sys.executable, "-m", "pytest", str(ROOT / EXAMPLE_TREE / "tests"), "-q", "-p",
                         "no:cacheprovider", f"--junitxml={junit}"], cwd=ROOT, capture_output=True, text=True)
    root = ET.parse(junit).getroot()
    suite = root.find("testsuite")
    if suite is None:
        suite = root
    fails = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    tests = int(suite.get("tests", 0))
    reg_status = "PASS" if rc.returncode == 0 and fails == 0 and tests > 0 else "FAIL"
    reg_art = put("regression", "regression", "regression/orders-junit.xml", junit.read_bytes(),
                  "application/xml", side="after", rev=revision,
                  desc=f"pytest {EXAMPLE_TREE}/tests: {tests - fails}/{tests} passed")
    reg_rec = ProgramRegression(status=reg_status, summary=f"{tests - fails}/{tests} passed at {revision[:12]}",
                                artifact_id=reg_art.id, artifact_sha256=reg_art.sha256)

    # ---- task input: what a provider model may be given later (model + property + fixture; no answers) ----
    prop_digest = property_digest(v1, "all_completed")
    task_input = {"model": json.loads(v1.model_dump_json()), "property": {"id": "all_completed", "kind": "goal"},
                  "fixture": fixture, "question": "Is all_completed reachable within the bound for this program run?"}
    put("task-input", "task_input", "task_inputs/belief-all_completed.json",
        (json.dumps(task_input, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode(), "application/json",
        desc="belief model + property + fixture only (reference answers kept out)")

    # ---- the case definition (identity, software, comparison, models, correspondence) ----
    identity = CaseIdentity(case_id=CASE_ID, case_version=1, track="implementation_conformance",
                            mechanism_family="timing-model-deviation", title="Order service: p2 processing-speed deviation",
                            purpose="Verify that a belief model's timing prediction deviates from the real order "
                            "service while the revised model corresponds, on one recorded run.")
    software = SoftwareSource(repository=REPO_URL, license="Apache-2.0", revision=revision,
                              trees=tree_digests(ROOT, revision, [EXAMPLE_TREE]) or [], config_sha256=config_sha,
                              variant="own_test_variant",
                              variant_note="the repo's own order service run under the lab `deviation` operating "
                              "condition (station p2 at half speed); not an upstream release")
    comparison = Comparison(
        before=VersionSide(present=False, absent_reason="the program code is unchanged; what differs is the model "
                           "(belief vs revised) and the operating condition, not a source revision"),
        after=VersionSide(present=True, revision=revision, artifact_ids=["obs-run", "fixture-deviation", "regression"]),
        change_basis="operating condition: station p2 runs at half speed; the belief model assumes nominal speed, the "
        "revised model encodes slow[p2]=true",
        regression_test_source=f"{EXAMPLE_TREE}/tests (the service's own suite)")
    assumptions = ["deterministic finite abstraction of the service state machine",
                   "one lab operating condition (slow[p2]); other stations nominal"]
    uncovered = ["HTTP transport and serialization", "process concurrency and retries", "database persistence details"]
    models = [
        CaseModel(label="v1", role="belief", model_ref=v1.ref(), artifact_id="model-v1",
                  semantic_profile=v1.semantic_profile,
                  properties=[PropertySpec(property_id="all_completed", kind="goal", digest=prop_digest,
                                           summary="every order eventually reaches completed")],
                  bounds=Bounds(max_steps=BOUND["max_steps"], timeout_ms=BOUND["timeout_ms"],
                                inputs="deviation instance, seed 1"),
                  assumptions=assumptions, uncovered_semantics=uncovered),
        CaseModel(label="v2", role="revised", model_ref=v2.ref(), artifact_id="model-v2",
                  semantic_profile=v2.semantic_profile,
                  properties=[PropertySpec(property_id="all_completed", kind="goal",
                                           digest=property_digest(v2, "all_completed"),
                                           summary="every order eventually reaches completed")],
                  bounds=Bounds(max_steps=BOUND["max_steps"], timeout_ms=BOUND["timeout_ms"],
                                inputs="deviation instance, seed 1"),
                  assumptions=assumptions, uncovered_semantics=uncovered),
    ]
    svc = f"{EXAMPLE_TREE}/src/formal_lab_example_orders/service.py"
    correspondence = [
        Correspondence(program=ProgramElement(component="tick handler", path=svc, symbol="apply_operation"),
                       model=ModelElement(kind="action", name="tick"), relation="MEASURED",
                       evidence_artifact_ids=["obs-run"],
                       note="one tick advances the clock; slow stations advance every other tick"),
        Correspondence(program=ProgramElement(component="station speed", path=svc, symbol="stations.slow"),
                       model=ModelElement(kind="constant", name="slow"), relation="MANUAL_REVIEW",
                       note="the slow-station column is the model constant slow[station]"),
        Correspondence(program=ProgramElement(component="reservation", path=svc, symbol="apply_operation"),
                       model=ModelElement(kind="action", name="reserve"), relation="MEASURED",
                       evidence_artifact_ids=["obs-run"], note="reserve decrements stock and sets status"),
        Correspondence(program=ProgramElement(component="order ledger", path=svc, symbol="values"),
                       model=ModelElement(kind="observation", name="remaining"), relation="MEASURED",
                       evidence_artifact_ids=["obs-run"], note="remaining[oid] is the program's per-order work left"),
    ]

    # ---- pass 1: a provisional case (definition final, conformance not yet in) → compute conformance ----
    def build(conformance_ids: list[str], reference_ids: list[str], digest: str) -> ResearchCase:
        validation = Validation(
            criteria=[Criterion(id="c-belief-deviates", text="the belief model (v1) deviates from the recorded run"),
                      Criterion(id="c-revised-corresponds", text="the revised model (v2) corresponds on the same run"),
                      Criterion(id="c-regression", text="the service's own regression suite passes at this revision")],
            fixture_ids=["fixture-deviation"], observation_ids=["obs-run"],
            model_check_ids=["check-v1", "check-v2"], regression_ids=["regression"],
            conformance_ids=conformance_ids, reference_ids=reference_ids, task_input_ids=["task-input"])
        reproduction = Reproduction(
            environment="Colima VM; order service via ServiceManager(process); Z3 verifier; no network",
            reset="a fresh ServiceManager workdir per run (remove_data on close)",
            cleanup="ServiceManager.close(remove_data=True)", seeds=[1],
            nondeterminism=["none in scope: rule strategy, fixed seed, local process"],
            commands=[Command(command="python scripts/p5a_orders_case.py", purpose="build and validate this case"),
                      Command(command=f"pytest {EXAMPLE_TREE}/tests", purpose="program regression")],
            prerequisites=["uv sync --frozen", "the order-service example installed in the project venv"])
        return ResearchCase(identity=identity, software=software, comparison=comparison, models=models,
                            correspondence=correspondence, validation=validation, reproduction=reproduction,
                            artifacts=arts, case_digest=digest)

    zero = "0" * 64
    provisional = build([], [], zero)
    files = CaseFiles(source=str(CASE_DIR), document=provisional.model_dump(mode="json"), _dir=CASE_DIR)

    conf_v1 = replay_conformance(files, provisional, model_label="v1", property_id="all_completed",
                                 observation_id="obs-run",
                                 model_conclusion=ModelConclusion(verdict=verdict_v1,
                                                                  query="GOAL_REACHABILITY(all_completed)",
                                                                  artifact_id=check_v1.id,
                                                                  artifact_sha256=check_v1.sha256),
                                 program_regression=reg_rec)
    conf_v2 = replay_conformance(files, provisional, model_label="v2", property_id="all_completed",
                                 observation_id="obs-run",
                                 model_conclusion=ModelConclusion(verdict=verdict_v2,
                                                                  query="GOAL_REACHABILITY(all_completed)",
                                                                  artifact_id=check_v2.id,
                                                                  artifact_sha256=check_v2.sha256),
                                 program_regression=reg_rec)
    put("conf-v1", "conformance", "conformance/v1-all_completed.result.json", conf_v1.model_dump_json(indent=1).encode(),
        "application/json", desc=f"belief model vs run: {conf_v1.correspondence}")
    put("conf-v2", "conformance", "conformance/v2-all_completed.result.json", conf_v2.model_dump_json(indent=1).encode(),
        "application/json", desc=f"revised model vs run: {conf_v2.correspondence}")

    # ---- reference answers (verification only; kept apart from task inputs) ----
    first_diff = next((it.step for it in conf_v1.items if it.status == "DIFFERENT"), None)
    reference = {"v1": {"correspondence": conf_v1.correspondence, "first_difference_step": first_diff,
                        "model_conclusion": verdict_v1},
                 "v2": {"correspondence": conf_v2.correspondence, "model_conclusion": verdict_v2},
                 "regression": reg_status,
                 "note": "expected verdicts for this recorded run; verification only, never handed to a model"}
    put("reference", "reference", "reference/expected.json",
        (json.dumps(reference, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode(), "application/json",
        desc="expected correspondence verdicts (v1 DEVIATES, v2 CORRESPONDS)")

    # ---- pass 2: the final case, digest computed over the complete content ----
    final_noidg = build(["conf-v1", "conf-v2"], ["reference"], zero)
    digest = compute_case_digest(final_noidg.model_dump(mode="json"))
    final = build(["conf-v1", "conf-v2"], ["reference"], digest)
    (CASE_DIR / "case.json").write_text(final.model_dump_json(indent=1) + "\n")

    # ---- validate what we just wrote, against this repository ----
    report, _case = validate_case(load_case(CASE_DIR), repo=ROOT)
    print(json.dumps({"revision": revision, "verdict_v1": verdict_v1, "verdict_v2": verdict_v2,
                      "conf_v1": conf_v1.correspondence, "conf_v2": conf_v2.correspondence,
                      "first_difference_step": first_diff, "regression": reg_status,
                      "validation": report.as_dict()}, indent=2, ensure_ascii=False))
    if not report.ok:
        return 1
    print("OK: case validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
