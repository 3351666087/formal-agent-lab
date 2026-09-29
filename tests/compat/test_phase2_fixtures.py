"""Phase-2 v2 replay bundles (captured at 0ae4571, tests/compat/capture_phase2.py) stay readable (phase 3, G1).

Compatibility policy: phase-3 additions to formal-lab-contracts/v2 are additive — new objects and optional fields
with defaults — so v2 data written by phase 2 validates unchanged; a breaking change would publish v3 with a reader
for v2 (as v2 did for v1, decision D-015).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from formal_lab_contracts import CONTRACT_VERSION
from formal_lab_contracts.bundle import read_bundle

FIX = Path(__file__).parent / "fixtures" / "phase2"
CAPTURE = json.loads((FIX / "CAPTURE.json").read_text())


@pytest.mark.parametrize("name", sorted(CAPTURE["runs"]))
def test_phase2_bundle_reads_with_the_same_trajectory(name):
    b = read_bundle(FIX / f"{name}.replay.zip")
    expected = CAPTURE["runs"][name]
    assert CAPTURE["contract_version"] == CONTRACT_VERSION == b.info["contract_version"]
    assert len(b.events) == expected["events"] and len(b.operations) == expected["operations"]
    assert [p.actor_id for p in b.manifest.participants] == expected["participants"]
    assert {m.metric_id: m.value for m in b.metrics} == expected["metrics"]
    assert not b.verify_causality()
    assert b.turns() and all("actor_id" in row for row in b.turns())


def test_phase2_features_survive_in_the_fixtures():
    two = read_bundle(FIX / "two-dispatchers.replay.zip")
    assert {row["actor_id"] for row in two.turns()} == {p.actor_id for p in two.manifest.participants}
    assert len(two.manifest.participants) == 2
    assert any(str(e.event_type) == "PLANNER_CHECKPOINT" for e in two.events) and two.plans()
    assert all(e.stage is not None for e in two.events if str(e.event_type) == "ACTION_OUTCOME")
    orders = read_bundle(FIX / "orders-delayed.replay.zip")
    assert {str(o.state.value if hasattr(o.state, "value") else o.state) for o in orders.operations} >= {"RECONCILED"}
    assert orders.probes()
    wh = read_bundle(FIX / "warehouse.replay.zip")
    assert not wh.package.is_ir and wh.package.payload.kind == "namespaced"
