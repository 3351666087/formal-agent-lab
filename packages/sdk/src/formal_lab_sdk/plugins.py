"""Public plugin API for packages outside this repository.

A plugin package depends only on `formal-lab-sdk` (which brings the contracts), implements one interface and
declares an entry point in the `formal_lab.plugins` group:

    [project.entry-points."formal_lab.plugins"]
    my-plugin = "my_package:registrations"

Phase-2 extension points are public here too: a planner that keeps a TaskPlan and implements checkpoint / restore
(CheckpointingPlanner) is resumed exactly after a pause or a worker restart; an environment backed by a persistent
service implements SessionEnvironment; probes, semantic drivers and turn schedulers have their own protocols.
`formal_lab_sdk.plugin_testing` runs any of them through the kernel's lifecycle.
"""

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    CandidateAction,
    EnvironmentSession,
    EpisodeRecord,
    MetricDefinition,
    MetricResult,
    Observation,
    PlanGenerator,
    PlannerCheckpoint,
    PlanningContext,
    PlanRevision,
    PlanTrigger,
    PluginDescriptor,
    ProbeResult,
    ProposalSource,
    TaskNode,
    TaskPlan,
    TaskStatus,
    capabilities,
)
from formal_lab_contracts.interfaces import (
    ENTRY_POINT_GROUP,
    CheckpointingPlanner,
    Environment,
    Evaluator,
    ModelFrontend,
    Planner,
    PluginRegistration,
    PluginServices,
    Probe,
    SemanticDriver,
    SessionEnvironment,
    TurnScheduler,
    Verifier,
)

__all__ = [
    "ENTRY_POINT_GROUP",
    "ActionOutcome",
    "ActionProposal",
    "CandidateAction",
    "CheckpointingPlanner",
    "Environment",
    "EnvironmentSession",
    "EpisodeRecord",
    "Evaluator",
    "MetricDefinition",
    "MetricResult",
    "ModelFrontend",
    "Observation",
    "PlanGenerator",
    "PlanRevision",
    "PlanTrigger",
    "Planner",
    "PlannerCheckpoint",
    "PlanningContext",
    "PluginDescriptor",
    "PluginRegistration",
    "PluginServices",
    "Probe",
    "ProbeResult",
    "ProposalSource",
    "SemanticDriver",
    "SessionEnvironment",
    "TaskNode",
    "TaskPlan",
    "TaskStatus",
    "TurnScheduler",
    "Verifier",
    "capabilities",
]
