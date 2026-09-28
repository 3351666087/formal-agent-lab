"""PRISM-games extension: payload, generated model, independent solver, and — where PRISM-games is installed — the
adapter's numbers and exported strategy checked in-model (P2-X01 … P2-X03)."""

from __future__ import annotations

import pytest
from formal_lab_solver_prism import (
    EXAMPLE,
    AllocationGame,
    Machine,
    Unavailable,
    check,
    evaluate,
    locate,
    solve,
    to_prism,
)
from pydantic import ValidationError


def one_job(p: float, rounds: int, slowdown: float = 0.5, adversary: bool = True) -> AllocationGame:
    return AllocationGame(game_id="one", jobs=["a"], machines=[Machine(id="m1", success=p)], rounds=rounds,
                          slowdown=slowdown, adversary=adversary)


def test_payload_is_typed_and_bounded():
    with pytest.raises(ValidationError):
        AllocationGame(game_id="x", jobs=["a", "a"], machines=[Machine(id="m1", success=0.5)], rounds=2, slowdown=1)
    with pytest.raises(ValidationError):
        AllocationGame(game_id="x", jobs=["a"], machines=[Machine(id="m1", success=0.5)], rounds=9, slowdown=1)
    with pytest.raises(ValidationError):
        Machine(id="M-1", success=0.5)
    assert AllocationGame.model_validate_json(EXAMPLE.model_dump_json()) == EXAMPLE


def test_generated_model_declares_players_turns_and_goal():
    text = to_prism(EXAMPLE)
    assert text.splitlines()[2] == "smg"
    assert "player dispatcher [asg_a_m1]" in text and "[slow_m1], [slow_m2], [work] endplayer" in text
    # two jobs on two machines: 2 single assignments per job + 2 pairings
    assert sum(1 for line in text.splitlines() if line.strip().startswith("[asg_")) == 6
    assert 'label "done" = d_a & d_b;' in text


def test_independent_solver_matches_hand_computation():
    # one job, one machine, the adversary always slows it: success 0.8 * 0.5 = 0.4 per round
    assert solve(one_job(0.8, 1)).value == pytest.approx(0.4)
    assert solve(one_job(0.8, 2)).value == pytest.approx(1 - 0.6**2)
    # cooperative environment never slows it... but it must pick a machine: only one exists, so it is slowed too
    assert solve(one_job(0.8, 2), cooperative=True).value == pytest.approx(1 - 0.6**2)
    # without an adversary the environment is calm: 0.8 per round
    assert solve(one_job(0.8, 2, adversary=False)).value == pytest.approx(1 - 0.2**2)


def test_robust_value_is_below_cooperative_and_optimal_strategy_achieves_it():
    robust, coop = solve(EXAMPLE), solve(EXAMPLE, cooperative=True)
    assert 0 < robust.value < coop.value < 1
    assert evaluate(EXAMPLE, robust.policy) == pytest.approx(robust.value)
    # a strategy that only ever uses the weak machine is worse against the adversary
    weak = {k: "asg_a_m2" if "a" not in k[1] else "asg_b_m2" for k in robust.policy}
    assert evaluate(EXAMPLE, weak) < robust.value
    assert robust.states == 91  # the same count PRISM-games reports for this game


def _installed() -> bool:
    try:
        locate()
        return True
    except Unavailable:
        return False


@pytest.mark.skipif(not _installed(), reason="PRISM-games not installed (optional extension track)")
def test_prism_games_result_and_strategy_are_verified_in_model(tmp_path):
    rec = check(EXAMPLE, keep=tmp_path)
    assert rec.verified, rec.model_dump(exclude={"model_text"})
    robust, coop = rec.properties
    assert robust.value == pytest.approx(solve(EXAMPLE).value, abs=1e-6)
    assert coop.value == pytest.approx(solve(EXAMPLE, cooperative=True).value, abs=1e-6)
    assert rec.size["states"] == rec.reference_states == 91
    assert rec.strategy_value == pytest.approx(robust.value, abs=1e-6)
    assert rec.backend["version"] == "3.2.4" and rec.backend["license"] == "GPL-2.0"
    assert (tmp_path / "strat.txt").exists() and (tmp_path / "model.tra").exists()
