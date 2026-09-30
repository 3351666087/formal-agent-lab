"""MAL security-lab domain (phase 3B): coreLang attack graphs → deterministic finite IR (profile
deterministic_finite_v1), reusing the platform's IR driver, Z3 verifier and G3 release checks. The native MAL
toolchain lives in a separate venv reached through `formal_lab_env_mal.bridge` (D-023 pattern)."""

from __future__ import annotations

from .admission import issue_receipt, mal_ruleset, target_check_basis
from .config import BusinessSLO, LabPolicy, TargetSecurity
from .frontend import DESCRIPTOR, SOURCE_FORMAT, attack_graph_of, package_from_graph
from .lowering import lower
from .run import red_team_scenario, run_red_team, run_summary
from .strategies import harden_package, min_cost_cut


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    from . import frontend, gate, strategies

    return [PluginRegistration(frontend.DESCRIPTOR, frontend.create_frontend),
            PluginRegistration(gate.DESCRIPTOR, gate.create_mal_broker_gate),
            PluginRegistration(strategies.RED_RULE, strategies.create_red_rule),
            PluginRegistration(strategies.RED_HYBRID, strategies.create_red_hybrid)]


__all__ = [
    "DESCRIPTOR",
    "SOURCE_FORMAT",
    "BusinessSLO",
    "LabPolicy",
    "TargetSecurity",
    "attack_graph_of",
    "harden_package",
    "issue_receipt",
    "lower",
    "mal_ruleset",
    "min_cost_cut",
    "package_from_graph",
    "red_team_scenario",
    "registrations",
    "run_red_team",
    "run_summary",
    "target_check_basis",
]
