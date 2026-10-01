"""D5: the bridge to the isolated CAGE 4 toolchain. Marked `cage`; skipped when the fal-cage venv is not present, so
CI without CybORG stays green while a developer with it installed gets a real round-trip check."""

from __future__ import annotations

import pytest
from formal_lab_env_cage import bridge

pytestmark = pytest.mark.cage

_UNAVAILABLE = bridge.available()
skip_no_cage = pytest.mark.skipif(_UNAVAILABLE is not None, reason=f"CAGE toolchain unavailable: {_UNAVAILABLE}")


@skip_no_cage
def test_versions_report_cage4():
    v = bridge.versions()
    assert v["cyborg_version"].startswith("4")
    assert v["scenario"] == "Scenario4"
    assert v["agents"]["red"] == "FiniteStateRedAgent"
    assert v["packages"]["numpy"] == "1.26.4"


@skip_no_cage
def test_baseline_runs_joint_world_steps():
    b = bridge.baseline(steps=8, seeds=[1])
    run = b["runs"][0]
    assert run["steps_run"] >= 1
    # one native world step advances once; every team acts (joint)
    step = run["per_step"][0]
    assert step["world_step"] == 1
    assert set(step["active"]) <= {"blue", "green", "red"}
    assert "Blue" in run["team_reward_totals"]


@skip_no_cage
def test_paired_seeds_are_deterministic():
    a = bridge.baseline(steps=20, seeds=[7])
    b = bridge.baseline(steps=20, seeds=[7])
    assert a["runs"][0]["team_reward_totals"] == b["runs"][0]["team_reward_totals"]
