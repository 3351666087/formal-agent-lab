"""Phase 7 (P7-01) regression for the token-bucket capacity fixture: the defect lets the bucket exceed its capacity,
the fix caps it, and the secure specification's invariant holds."""

from __future__ import annotations

from formal_lab_contracts import CheckQuery
from formal_lab_example_orders.research_ratelimit import (
    CAPACITY,
    REFILL,
    TokenBucket,
    capacity_model_package,
    derive_items,
    run_capacity_probes,
)
from formal_lab_runtime import default_registry
from formal_lab_runtime.query import run_query


def test_defect_bucket_exceeds_capacity():
    obs = run_capacity_probes(mode="uncapped")
    assert max(s["observed_tokens"] for s in obs["steps"]) > CAPACITY
    statuses = {i["status"] for i in derive_items(obs)}
    assert statuses == {"MATCH", "DIFFERENT"}  # deviates from the capped specification


def test_fix_bucket_caps_at_capacity():
    obs = run_capacity_probes(mode="capped")
    assert max(s["observed_tokens"] for s in obs["steps"]) == CAPACITY
    assert {i["status"] for i in derive_items(obs)} == {"MATCH"}  # corresponds


def test_take_never_goes_negative_and_denies_when_empty():
    b = TokenBucket(capped=True)
    assert b.take() is False and b.tokens == 0 and b.denied == 1  # empty → denied, not negative
    b.refill()
    assert b.take() is True and b.tokens == REFILL - 1  # refill added REFILL, take spent one


def test_secure_model_invariant_holds():
    pkg = capacity_model_package()
    reg = default_registry()
    qb = run_query(reg, pkg, CheckQuery(kind="INVARIANT_VIOLATION", property_id="within_capacity",
                                        bound={"max_steps": 10, "timeout_ms": 30000}))
    assert getattr(qb.result.verdict, "value", str(qb.result.verdict)) == "NO_WITNESS_WITHIN_BOUND"
