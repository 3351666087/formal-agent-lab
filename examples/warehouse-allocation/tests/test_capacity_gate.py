"""The warehouse execution gate (phase 3A, G2) on the pure-data driver world: a put-away that would fill a zone
beyond `max_fill` is denied before it is sent (the world does not change), the decision and its values are recorded,
and the rule planner puts the pallet elsewhere on its next turn. Without a gate the trajectory is unchanged."""

from __future__ import annotations

from formal_lab_example_warehouse.model import demo_model
from formal_lab_example_warehouse.plugins import build_package
from formal_lab_example_warehouse.scenarios import package, receiver_and_picker
from formal_lab_runtime import default_registry, make_manifest, run_local


def run(pkg, max_fill):
    reg = default_registry()
    m = make_manifest(run_id=f"run_gate_{str(max_fill).replace('.', '_')}", project_id="p",
                      scenario=receiver_and_picker(pkg, seed=1, max_fill=max_fill), package=pkg, registry=reg, seed=1,
                      config={"initial_check_horizon": 0})
    return run_local(m, pkg, reg)


def test_denied_putaway_changes_nothing_and_the_pallet_goes_elsewhere():
    pkg = build_package(demo_model(zones=[{"id": "z1", "capacity": 4}, {"id": "z2", "capacity": 8}]),
                        package_id="warehouse-gate")
    res = run(pkg, 0.5)
    assert res.status.value == "SUCCEEDED", res.reason
    decisions = [e.payload["decision"] for e in res.events if str(e.event_type) == "EXECUTION_DECIDED"]
    denied = [d for d in decisions if d["verdict"] == "DENY"]
    assert denied and all(d["conditions"][0]["name"] == "zone_fill" for d in denied)
    outcomes = {e.payload["outcome"]["operation_id"]: e.payload["outcome"] for e in res.events
                if str(e.event_type) == "ACTION_OUTCOME"}
    for d in denied:
        out = outcomes[d["operation_id"]]
        assert out["status"] == "REJECTED" and out["effect_applied"] is False and out["result"]["not_sent"]
        assert out["revision_before"] == out["revision_after"]
    by_step = sorted(outcomes.values(), key=lambda o: int(o["step_id"].rsplit(":s", 1)[1]))
    for d in denied:  # the denied action is not proposed again on the actor's very next turn
        nxt = next(o for o in by_step if o["action"] and int(o["step_id"].rsplit(":s", 1)[1]) > d["step"]
                   and o["operation_id"].split(":")[2] == d["actor_id"])
        assert nxt["action"] != outcomes[d["operation_id"]]["action"]
    applied_after = [o for o in by_step if o["action"]["action_type"] == "putaway" and o["status"] == "APPLIED"]
    assert len(applied_after) == 3  # every pallet is put away in the end, within the fill limit

def test_without_a_gate_the_trajectory_is_the_phase_2_one():
    pkg = package()
    plain, gated = run(pkg, None), run(pkg, 1.0)
    steps = lambda r: [(e.logical_step, e.payload["outcome"]["action"], e.payload["outcome"]["status"])  # noqa: E731
                       for e in r.events if str(e.event_type) == "ACTION_OUTCOME"]
    assert steps(plain) == steps(gated)  # a gate that always allows changes nothing but adds its records
    assert not [e for e in plain.events if str(e.event_type) == "EXECUTION_DECIDED"]
