"""Contract tests for formal-lab-contracts/v1 (reusable by later phases).

Three views of the contract must agree: the Pydantic source, the generated JSON Schemas and the
generated TypeScript (checked by packages/contracts-ts/test with the same fixtures).
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

import formal_lab_contracts as c
from formal_lab_contracts import schema_export
from formal_lab_contracts.capabilities import CapabilityRequirement, negotiate
from formal_lab_contracts.errors import ErrorCode, FormalLabError, InvalidInput, Timeout

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
SCHEMAS = ROOT / "contracts" / "v1" / "schemas"


def _load(sub: str) -> list[tuple[str, dict]]:
    return [(p.stem, json.loads(p.read_text())) for p in sorted((FIXTURES / sub).glob("*.json"))]


def _model(type_name: str):
    return getattr(c, type_name)


def _schema_validator(type_name: str) -> jsonschema.protocols.Validator:
    schema = json.loads((SCHEMAS / f"{type_name}.schema.json").read_text())
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


VALID = _load("valid")
INVALID = _load("invalid")
SEMANTIC_INVALID = _load("semantic-invalid")


def test_every_frozen_object_has_a_sample():
    names = {name.split(".")[0] for name, _ in VALID}
    frozen = {m.__name__ for m in schema_export.FROZEN_OBJECTS}
    assert frozen <= names, f"missing samples for {frozen - names}"


@pytest.mark.parametrize(("name", "instance"), VALID, ids=[n for n, _ in VALID])
def test_valid_samples_accepted_by_pydantic_and_schema(name, instance):
    type_name = name.split(".")[0]
    obj = _model(type_name).model_validate(instance)
    # round trip is lossless
    assert json.loads(obj.model_dump_json()) == json.loads(json.dumps(instance))
    _schema_validator(type_name).validate(instance)


@pytest.mark.parametrize(("name", "case"), INVALID, ids=[n for n, _ in INVALID])
def test_invalid_samples_rejected_by_pydantic_and_schema(name, case):
    with pytest.raises(ValidationError):
        _model(case["object"]).model_validate(case["instance"])
    errors = list(_schema_validator(case["object"]).iter_errors(case["instance"]))
    assert errors, f"schema accepted invalid sample {name}: {case['reason']}"


@pytest.mark.parametrize(("name", "case"), SEMANTIC_INVALID, ids=[n for n, _ in SEMANTIC_INVALID])
def test_semantic_rules_enforced_by_pydantic(name, case):
    with pytest.raises(ValidationError):
        _model(case["object"]).model_validate(case["instance"])


def test_generated_schemas_match_source():
    files = schema_export.build_schemas()
    for rel, content in files.items():
        assert (ROOT / "contracts" / "v1" / rel).read_text() == content, f"{rel} drifted; run make contracts"
    committed = json.loads((ROOT / "contracts" / "v1" / "DIGEST.json").read_text())
    assert committed["digest"] == schema_export.contract_digest(files)["digest"]


def test_error_model_round_trip_and_retryability():
    err = Timeout("solver exceeded 50ms", details={"timeout_ms": 50})
    info = err.to_info()
    assert info.code is ErrorCode.TIMEOUT and info.retryable
    back = FormalLabError.from_info(c.ErrorInfo.model_validate_json(info.model_dump_json()))
    assert isinstance(back, Timeout) and back.details == {"timeout_ms": 50}
    assert not InvalidInput("x").retryable
    assert {e.value for e in ErrorCode} >= {
        "INVALID_INPUT", "VERSION_MISMATCH", "UNSUPPORTED", "TIMEOUT", "RESULT_UNKNOWN", "CANCELLED",
        "RETRYABLE_FAILURE", "NON_RETRYABLE_FAILURE",
    }


def test_capability_negotiation():
    descriptor = c.PluginDescriptor.model_validate(json.loads((FIXTURES / "valid" / "PluginDescriptor.json").read_text()))
    ok = negotiate(descriptor, [CapabilityRequirement(id="plan.bounded_search"),
                                CapabilityRequirement(id="plan.llm", optional=True)])
    assert ok.compatible and ok.granted == ["plan.bounded_search"] and ok.missing_optional == ["plan.llm"]
    bad = negotiate(descriptor, [CapabilityRequirement(id="query.probabilistic_reachability")])
    assert not bad.compatible and bad.missing_required == ["query.probabilistic_reachability"]
    too_new = negotiate(descriptor, [CapabilityRequirement(id="plan.bounded_search", min_version="2")])
    assert not too_new.compatible


def test_extension_namespace_rules():
    base = json.loads((FIXTURES / "valid" / "ModelPackage.json").read_text())
    base["extensions"] = {"formal-lab.core.hack": {"version": "1.0.0", "schema_id": "x", "data": {}}}
    with pytest.raises(ValidationError):
        c.ModelPackage.model_validate(base)


def test_verdict_is_coerced_to_kind_specific_enum():
    sample = json.loads((FIXTURES / "valid" / "BoundedCheckResult.unsupported.json").read_text())
    result = c.BoundedCheckResult.model_validate(sample)
    assert isinstance(result.verdict, c.PreconditionVerdict)
    search = c.BoundedCheckResult.model_validate(json.loads((FIXTURES / "valid" / "BoundedCheckResult.json").read_text()))
    assert isinstance(search.verdict, c.SearchVerdict)
