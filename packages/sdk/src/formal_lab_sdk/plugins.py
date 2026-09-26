"""Public plugin API for packages outside this repository.

A plugin package depends only on `formal-lab-sdk` (which brings the contracts), implements one interface and
declares an entry point in the `formal_lab.plugins` group:

    [project.entry-points."formal_lab.plugins"]
    my-plugin = "my_package:registrations"
"""

from formal_lab_contracts import (
    ActionProposal,
    CandidateAction,
    EpisodeRecord,
    MetricDefinition,
    MetricResult,
    Observation,
    PlanningContext,
    PluginDescriptor,
    ProposalSource,
    capabilities,
)
from formal_lab_contracts.interfaces import (
    ENTRY_POINT_GROUP,
    Environment,
    Evaluator,
    ModelFrontend,
    Planner,
    PluginRegistration,
    PluginServices,
    Verifier,
)

__all__ = [
    "ENTRY_POINT_GROUP",
    "ActionProposal",
    "CandidateAction",
    "Environment",
    "EpisodeRecord",
    "Evaluator",
    "MetricDefinition",
    "MetricResult",
    "ModelFrontend",
    "Observation",
    "Planner",
    "PlanningContext",
    "PluginDescriptor",
    "PluginRegistration",
    "PluginServices",
    "ProposalSource",
    "Verifier",
    "capabilities",
]
