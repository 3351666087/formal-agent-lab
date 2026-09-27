"""Contract tests for formal-lab-contracts/v2 and the frozen v1 (reusable by later phases).

Three views of the contract must agree: the Pydantic source, the generated JSON Schemas and the generated
TypeScript (packages/contracts-ts/test uses the same fixtures). v1 samples (fixtures/v1, frozen since phase 1) must
keep validating as v1 and upgrade to valid v2 objects without changing their meaning.
"""

from __future__ import annotations

import json
from pathlib import Path

import formal_lab_contracts as c
import jsonschema
import pytest
from formal_lab_contracts import compat, schema_export
from formal_lab_contracts.capabilities import CapabilityRequirement, negotiate
from formal_lab_contracts.errors import ErrorCode, FormalLabError, InvalidInput, Timeout, VersionMismatch
from formal_lab_contracts.v1 import objects as v1
from formal_lab_contracts.v1 import schema_export as v1_export
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


def _load(version: str, sub: str) -> list[tuple[str, dict]]:
    return [(p.stem, json.loads(p.read_text())) for p in sorted((FIXTURES / version / sub).glob("*.json"))]


def _validator(version: str, type_name: str) -> jsonschema.protocols.Validator:
    schema = json.loads((ROOT / "contracts" / version / "schemas" / f"{type_name}.schema.json").read_text())
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


V1_VALID, V1_INVALID, V1_SEMANTIC = (_load("v1", s) for s in ("valid", "invalid", "semantic-invalid"))
V2_VALID, V2_INVALID, V2_SEMANTIC = (_load("v2", s) for s in ("valid", "invalid", "semantic-invalid"))
UPGRADABLE = {"ModelPackage", "ScenarioManifest", "RunManifest", "BoundedCheckResult", "ActionOutcome",
              "PluginDescriptor", "Observation", "ActionProposal", "MetricResult", "TraceEvent"}


# ------------------------------------------------------------------------ v2


def test_every_v2_object_has_a_sample():
    names = {name.split(".")[0] for name, _ in V2_VALID}
    required = {m.__name__ for m in schema_export.FROZEN_OBJECTS + schema_export.V2_OBJECTS}
    assert required <= names, f"missing samples for {required - names}"


@pytest.mark.parametrize(("name", "instance"), V2_VALID, ids=[n for n, _ in V2_VALID])
def test_v2_valid_samples_accepted_by_pydantic_and_schema(name, instance):
    type_name = name.split(".")[0]
    obj = getattr(c, type_name).model_validate(instance)
    assert json.loads(obj.model_dump_json()) == json.loads(json.dumps(instance)), "round trip must be lossless"
    _validator("v2", type_name).validate(instance)


@pytest.mark.parametrize(("name", "case"), V2_INVALID, ids=[n for n, _ in V2_INVALID])
def test_v2_invalid_samples_rejected_by_pydantic_and_schema(name, case):
    with pytest.raises(ValidationError):
        getattr(c, case["object"]).model_validate(case["instance"])
    errors = list(_validator("v2", case["object"]).iter_errors(case["instance"]))
    assert errors, f"schema accepted invalid sample {name}: {case['reason']}"


@pytest.mark.parametrize(("name", "case"), V2_SEMANTIC, ids=[n for n, _ in V2_SEMANTIC])
def test_v2_semantic_rules_enforced_by_pydantic(name, case):
    with pytest.raises(ValidationError):
        getattr(c, case["object"]).model_validate(case["instance"])


def test_generated_schemas_match_source():
    for version, module in (("v2", schema_export), ("v1", v1_export)):
        files = module.build_schemas()
        for rel, content in files.items():
            assert (ROOT / "contracts" / version / rel).read_text() == content, f"{version}/{rel} drifted"
        committed = json.loads((ROOT / "contracts" / version / "DIGEST.json").read_text())
        assert committed["digest"] == module.contract_digest(files)["digest"]


def test_v1_digest_is_the_phase1_digest():
    baseline = json.loads((ROOT / "docs/execution/evidence/phase2/baseline/phase1-baseline.json").read_text())
    assert v1_export.contract_digest(v1_export.build_schemas())["digest"] == baseline["phase1"]["contract_digest"]


# ------------------------------------------------------------------------ v1 (frozen) and upgrades


@pytest.mark.parametrize(("name", "instance"), V1_VALID, ids=[n for n, _ in V1_VALID])
def test_v1_samples_still_valid_v1_and_upgrade_to_v2(name, instance):
    type_name = name.split(".")[0]
    v1_obj = getattr(v1, type_name).model_validate(instance)
    _validator("v1", type_name).validate(instance)
    if type_name not in UPGRADABLE:
        return
    upgraded = compat.upgrade(type_name, instance)
    dumped = upgraded.model_dump(mode="json")
    _validator("v2", type_name).validate(dumped)
    # every v1 field keeps its value (the meaning is unchanged); ModelPackage.ir moved into the payload
    original = v1_obj.model_dump(mode="json")
    if type_name == "ModelPackage":
        assert dumped["payload"]["kind"] == "fal-ir" and _contains(dumped["payload"]["ir"], original["ir"])
        assert dumped["digest"] == original["digest"]
        original.pop("ir")
    for key, value in original.items():
        if key == "contract_version":
            continue
        assert _contains(dumped[key], value), f"{type_name}.{key} changed on upgrade"


def _contains(new, old) -> bool:
    """`new` keeps every v1 value of `old` (v2 may only add keys, never change or drop v1 values)."""
    if isinstance(old, dict):
        return isinstance(new, dict) and all(k == "contract_version" or (k in new and _contains(new[k], v))
                                             for k, v in old.items())
    if isinstance(old, list):
        return isinstance(new, list) and len(new) == len(old) and all(_contains(a, b) for a, b in zip(new, old, strict=True))
    return new == old


@pytest.mark.parametrize(("name", "case"), V1_INVALID, ids=[n for n, _ in V1_INVALID])
def test_v1_invalid_samples_still_rejected(name, case):
    with pytest.raises(ValidationError):
        getattr(v1, case["object"]).model_validate(case["instance"])
    assert list(_validator("v1", case["object"]).iter_errors(case["instance"]))
    # a v1-shaped object relabelled as v2 is a valid v2 object, so only the other cases must fail to upgrade
    if case["object"] in UPGRADABLE and case["object"] != "PluginDescriptor" and name != "bad-contract-version":
        with pytest.raises((InvalidInput, ValidationError, VersionMismatch)):
            compat.upgrade(case["object"], case["instance"])


@pytest.mark.parametrize(("name", "case"), V1_SEMANTIC, ids=[n for n, _ in V1_SEMANTIC])
def test_v1_semantic_rules_still_enforced(name, case):
    with pytest.raises(ValidationError):
        getattr(v1, case["object"]).model_validate(case["instance"])


def test_v1_scenario_keeps_its_stop_semantics():
    sample = json.loads((FIXTURES / "v1" / "valid" / "ScenarioManifest.json").read_text())
    scenario = compat.upgrade("ScenarioManifest", sample)
    term = scenario.effective_termination()
    assert term.joint_goal == "lit" and term.on_no_action == "END"  # no NO_APPLICABLE_ACTION condition in v1 sample
    assert scenario.turns.mode == "ROUND_ROBIN" and len(scenario.participants) == 1


def test_unknown_contract_version_rejected():
    sample = json.loads((FIXTURES / "v1" / "valid" / "ScenarioManifest.json").read_text())
    sample["contract_version"] = "formal-lab-contracts/v9"
    with pytest.raises(VersionMismatch):
        compat.upgrade("ScenarioManifest", sample)


# ------------------------------------------------------------------------ behaviour


def test_error_model_round_trip_and_retryability():
    err = Timeout("solver exceeded 50ms", details={"timeout_ms": 50})
    info = err.to_info()
    assert info.code is ErrorCode.TIMEOUT and info.retryable
    back = FormalLabError.from_info(c.ErrorInfo.model_validate_json(info.model_dump_json()))
    assert isinstance(back, Timeout) and back.details == {"timeout_ms": 50}
    assert not InvalidInput("x").retryable


def test_capability_negotiation_explains_itself():
    descriptor = c.PluginDescriptor.model_validate(json.loads((FIXTURES / "v2" / "valid" / "PluginDescriptor.json")
                                                              .read_text()))
    ok = negotiate(descriptor, [CapabilityRequirement(id="plan.bounded_search"),
                                CapabilityRequirement(id="plan.llm", optional=True)], role="strategy:a")
    assert ok.compatible and ok.verdict == "PARTIAL" and ok.missing_optional == ["plan.llm"] and ok.role == "strategy:a"
    bad = negotiate(descriptor, [CapabilityRequirement(id="query.probabilistic_reachability")],
                    why={"query.probabilistic_reachability": "probabilistic goals"})
    assert not bad.compatible and bad.verdict == "UNSUPPORTED" and "probabilistic goals" in bad.reasons[0]
    assert not negotiate(descriptor, [CapabilityRequirement(id="plan.bounded_search", min_version="2")]).compatible


def test_extension_namespace_rules():
    base = json.loads((FIXTURES / "v2" / "valid" / "ModelPackage.json").read_text())
    base["extensions"] = {"formal-lab.core.hack": {"version": "1.0.0", "schema_id": "x", "data": {}}}
    with pytest.raises(ValidationError):
        c.ModelPackage.model_validate(base)


def test_verdict_is_coerced_to_kind_specific_enum():
    for name, enum in (("BoundedCheckResult", c.SearchVerdict), ("BoundedCheckResult.unsupported",
                                                                  c.PreconditionVerdict),
                       ("BoundedCheckResult.optimize", c.OptimizationStatus),
                       ("BoundedCheckResult.robust", c.RobustnessVerdict)):
        r = c.BoundedCheckResult.model_validate(json.loads((FIXTURES / "v2" / "valid" / f"{name}.json").read_text()))
        assert isinstance(r.verdict, enum), name


def test_canonical_ir_keeps_v1_digests():
    """A v1 model has the same canonical form (and digest) under v2; v2-only fields change the digest only when
    they are actually used."""
    v1_pkg = json.loads((FIXTURES / "v1" / "valid" / "ModelPackage.json").read_text())
    ir = c.ModelIR.model_validate(v1_pkg["ir"])
    assert c.digest_of(c.canonical_ir_dump(ir)).model_dump() == v1_pkg["digest"]
    with_objective = ir.model_copy(update={"objectives": [c.ObjectiveDecl(id="n", terms=[{"kind": "action_cost"}])]})
    assert c.digest_of(c.canonical_ir_dump(with_objective)).model_dump() != v1_pkg["digest"]


def test_namespaced_package_has_no_ir():
    pkg = c.ModelPackage.model_validate(json.loads((FIXTURES / "v2" / "valid" / "ModelPackage.namespaced.json")
                                                   .read_text()))
    assert not pkg.is_ir
    with pytest.raises(c.errors.Unsupported):
        _ = pkg.ir
