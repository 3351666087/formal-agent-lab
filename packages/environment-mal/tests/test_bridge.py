"""D1: the bridge to the isolated MAL toolchain. Marked `mal`; skipped when the fal-mal venv is not present, so CI
without the toolchain stays green while a developer with it installed gets a real round-trip check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from formal_lab_env_mal import bridge

pytestmark = pytest.mark.mal

_UNAVAILABLE = bridge.available()
skip_no_mal = pytest.mark.skipif(_UNAVAILABLE is not None, reason=f"MAL toolchain unavailable: {_UNAVAILABLE}")

FIX = Path(__file__).parents[2] / "domain-mal" / "tests" / "fixtures"
MODEL = json.loads((Path(__file__).parents[2] / "domain-mal" /
                    "src/formal_lab_domain_mal/models/net_app_data.json").read_text())


@skip_no_mal
def test_versions_match_pins():
    v = bridge.versions()
    assert v["mal_toolbox"] == "2.11.0"
    assert v["mal_simulator"] == "3.2.1"
    assert v["language_sha256"] == "9aabc828b5174ebe202cf8120a8e13a989c2f6e03d5908d8c65a4cc8adb3b150"


@skip_no_mal
def test_describe_matches_committed_fixture():
    import hashlib

    def digest(o):
        return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    graph = bridge.describe(MODEL)
    graph.setdefault("model_name", MODEL["name"])
    fixture = json.loads((FIX / "net_app_data.graph.json").read_text())
    assert digest(graph) == digest(fixture), "live attack graph drifted from the committed fixture"


@skip_no_mal
def test_simulate_reaches_the_secret():
    run = bridge.simulate(MODEL, ["app:fullAccess"], goal="secret:read")
    assert run["goal_reached"] is True
    assert "secret:read" in run["compromised"]
    # active vs automatic: with no entry point nothing is compromised at start (no auto-active attack steps)
    empty = bridge.simulate(MODEL, [], goal="secret:read")
    assert empty["goal_reached"] is False
    assert empty["compromised"] == []


@skip_no_mal
def test_import_scenario_builds_a_verifiable_package():
    from formal_lab_contracts import CheckQuery
    from formal_lab_env_mal import import_scenario
    from formal_lab_model.driver import IRFiniteDriver
    from formal_lab_solver_z3.verifier import Z3Verifier

    scn = Path(__file__).parents[2] / "domain-mal" / "scenarios" / "net_app_data.scenario.json"
    pkg, run = import_scenario(scn)
    assert run["goal_reached"] is True
    assert IRFiniteDriver().validate(pkg) == []
    z = Z3Verifier().check(pkg, CheckQuery(kind="GOAL_REACHABILITY", property_id="target_reached",
                                           bound={"max_steps": 60, "timeout_ms": 30000}))
    assert z.verdict == "WITNESS"
