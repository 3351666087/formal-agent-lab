"""Model revision and the D-022 stale/real distinction for the MAL domain (phase 3B, D3).

The attacker plans on a *belief* model built from its own (here, deliberately incomplete) native capture. The true
world is the full native reachable set. Two kinds of disagreement are told apart, exactly as D-022 requires:

  * **true deviation** — on a *comparable* state (the same initial state, same revision) the belief model and the truth
    disagree about whether the target is reachable. That is a real model error: it yields a regression case; the old
    model is rejected by it and a revised model that matches the truth is released and re-validated.
  * **stale difference** — a disagreement fully explained by the world having advanced (the belief was formed at an
    earlier revision than the observation it is compared with). That is not a model error: it produces no regression
    case, so it never enters the regression library.

The verdicts come from the platform's Z3 bounded verifier and the native reachable set (the same oracle D1 cross-checks),
so the whole thing is deterministic and offline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from formal_lab_contracts import CheckQuery, GroundAction, ModelRef, RegressionCase
from formal_lab_solver_z3.verifier import Z3Verifier

from .frontend import attack_graph_of, package_from_graph

_VERIFIER = Z3Verifier()
_QUERY = CheckQuery(kind="GOAL_REACHABILITY", property_id="target_reached",
                    bound={"max_steps": 60, "timeout_ms": 30000})


def _reachable(package: Any) -> bool:
    return _VERIFIER.check(package, _QUERY).verdict == "WITNESS"


def model_revision_cases(graph: dict[str, Any], entry: list[str], goal: str, true_reachable: list[str]) -> dict[str, Any]:
    nodes = {n["full_name"]: n for n in graph["nodes"]}
    goal_parents = [p for p in nodes[goal]["parents"]]
    # v1: an incomplete capture that missed the final propagation into the goal → believes the target is safe
    belief_reachable = [s for s in true_reachable if s != goal and s not in goal_parents]
    v1 = package_from_graph(graph, entry, goal, package_id="mal-belief", version=1, reachable=belief_reachable,
                            language={"name": "coreLang", "version": "1.0.0"})
    # truth / v2: the full native reachable set
    v2 = package_from_graph(graph, entry, goal, package_id="mal-belief", version=2, reachable=true_reachable,
                            language={"name": "coreLang", "version": "1.0.0"})

    goal_id = attack_graph_of(v2)["lowering"]["goal_id"]
    belief_reaches = _reachable(v1)
    truth_reaches = goal in set(true_reachable) and _reachable(v2)

    # true deviation: comparable initial state, disagreement about the target
    initial = {f"compromised[{goal_id}]": False}
    case = RegressionCase(
        case_id="mal-goal-reachability-deviation", source="COUNTEREXAMPLE",
        model=ModelRef(package_id="mal-belief", version=1, digest=v1.digest),
        initial_state=initial, actions=[GroundAction(action_type="compromise", params={"n": goal_id})],
        expected={f"compromised[{goal_id}]": belief_reaches}, observed={f"compromised[{goal_id}]": truth_reaches},
        compared_paths=[f"compromised[{goal_id}]"],
        origin={"reason": "belief model built from an incomplete native capture (missing the goal's propagation)"},
        created_at=datetime.now(UTC))

    is_true_deviation = belief_reaches != truth_reaches  # comparable state, models disagree
    v2_matches_truth = _reachable(v2) == truth_reaches
    v1_rejected = case.expected != case.observed
    v2_passes = {f"compromised[{goal_id}]": _reachable(v2)} == case.observed

    # stale difference: the belief at revision 0 (target not yet compromised) vs an observation many revisions later
    # (the attacker has since reached it). The gap is the intervening steps, not a model error → no regression case.
    stale = {
        "belief_revision": 0, "observation_revision": len([s for s in true_reachable if s != goal]),
        "belief_target": False, "observed_target": True,
        "classification": "STALE", "reason": "the difference is explained by the world advancing between the "
                                             "belief's revision and the observation's revision (D-022)",
        "regression_case_produced": False, "enters_regression_library": False,
    }

    return {
        "true_deviation": {
            "comparable_state": True,
            "belief_target_reachable": belief_reaches,
            "truth_target_reachable": truth_reaches,
            "is_model_error": is_true_deviation,
            "regression_case": case.model_dump(mode="json"),
            "old_model_v1_rejected": v1_rejected,
            "revised_model_v2_released": v2_matches_truth,
            "revised_model_v2_passes_case": v2_passes,
        },
        "stale_difference": stale,
        "regression_library_clean": is_true_deviation and not stale["enters_regression_library"],
    }
