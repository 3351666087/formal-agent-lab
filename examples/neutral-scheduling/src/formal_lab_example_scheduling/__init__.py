"""Neutral production-scheduling example: model, scenarios, rule strategy and scorer."""

from formal_lab_contracts.interfaces import PluginRegistration


def registrations() -> list[PluginRegistration]:
    from . import rule_planner, scorer

    return [PluginRegistration(rule_planner.DESCRIPTOR, rule_planner.create),
            PluginRegistration(scorer.DESCRIPTOR, scorer.create)]
