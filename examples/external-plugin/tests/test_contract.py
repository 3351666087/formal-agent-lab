"""The out-of-tree plugin passes the public plugin contract harness (P2-018 / P2-124): installed only through its
entry point, tested only through `formal_lab_sdk.plugin_testing`."""

from __future__ import annotations

from formal_lab_sdk.plugin_testing import check_environment, check_planner


def test_external_planner_passes_every_lifecycle_stage():
    report = check_planner(("org.example.preference-planner", "0.1.0"), {"preference": ["serve"]})
    assert report.ok, report.failures()
    assert [s.name for s in report.stages] == ["registered", "initialised", "negotiated", "observe & propose",
                                               "state advanced", "recovered", "finished"]
    assert "SUCCEEDED" in report.stages[-1].detail


def test_harness_reports_a_broken_configuration_at_the_right_stage():
    report = check_planner(("org.example.preference-planner", "0.1.0"), {"preference": "not-a-list"})
    assert not report.ok and report.stages[0].name == "registered" and not report.stages[0].ok
    assert all(s.detail.startswith("skipped") for s in report.stages[1:])


def test_harness_checks_the_pure_environment_too():
    report = check_environment(("formal-lab.env.ir-world", "1.1.0"))
    assert report.ok, report.failures()
    assert "FULL_STATE" in next(s.detail for s in report.stages if s.name == "snapshot / restore")
