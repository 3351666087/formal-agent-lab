"""Regression sentinel for later phases: the standalone example must keep these behaviours."""

from __future__ import annotations

import json

import pytest

from formal_lab_example_scheduling.__main__ import main


@pytest.mark.parametrize(("scenario", "strategy"), [("normal", "rule"), ("normal", "z3"),
                                                     ("resource-shortage", "rule"), ("expectation-mismatch", "z3")])
def test_standalone_runs_succeed(scenario, strategy, capsys):
    assert main(["run", "--scenario", scenario, "--strategy", strategy, "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "SUCCEEDED" in out and "delay_cost" in out


def test_standalone_bundle_is_replayable(tmp_path):
    from formal_lab_contracts.bundle import read_bundle

    path = tmp_path / "b.zip"
    assert main(["run", "--scenario", "state-delay", "--strategy", "z3", "--seed", "2", "--bundle", str(path)]) == 0
    bundle = read_bundle(path.read_bytes())
    assert bundle.manifest.status == "SUCCEEDED"
    assert any(u for s in bundle.steps() for u in (bundle.step(s).get("observation", {}).get("observation", {})
                                                  .get("unknowns", [])))


def test_standalone_checks_and_compare(tmp_path):
    assert main(["check"]) == 0
    out = tmp_path / "c.json"
    assert main(["compare", "--scenarios", "normal,expectation-mismatch", "--strategies", "rule,z3", "--seeds", "1,2",
                 "--out", str(out)]) == 0
    report = json.loads(out.read_text())
    assert len(report["cells"]) == 8 and {c["status"] for c in report["cells"]} == {"SUCCEEDED"}
    mismatch = [a for a in report["aggregates"] if a["scenario"] == "expectation-mismatch"]
    assert all(a["metrics"]["effect_mismatches"]["result"]["value"] > 0 for a in mismatch)
