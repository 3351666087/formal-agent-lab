"""Verifier.check: the three bounded query kinds, including a partial-state precondition check."""

from formal_lab_contracts import CheckQuery, ModelSource
from formal_lab_model import build_package
from formal_lab_model.samples import two_jobs
from formal_lab_solver_z3.verifier import Z3Verifier

package = build_package(two_jobs(), package_id="two-jobs", version=1, source=ModelSource(format="fal-ir-json/v1"))
verifier = Z3Verifier()
reach = verifier.check(package, CheckQuery(kind="GOAL_REACHABILITY", property_id="all_done", bound={"max_steps": 8}))
inv = verifier.check(package, CheckQuery(kind="INVARIANT_VIOLATION", property_id="b_after_a", bound={"max_steps": 6}))
pre = verifier.check(package, CheckQuery(kind="ACTION_PRECONDITION", initial_state="GIVEN_STATE", bound={"max_steps": 0},
                                         action={"action_type": "start", "params": {"j": "a", "m": "m1"}}),
                     state={"status[a]": "waiting", "status[b]": "waiting", "on[a,m1]": False, "on[a,m2]": False,
                            "on[b,m1]": False, "on[b,m2]": False, "left[a]": 0, "left[b]": 0, "clock": 0},
                     unknown_paths=["status[a]"])
print(reach.verdict, len(reach.witness.steps) - 1, reach.witness.replay)
print(inv.verdict, inv.explanation)
print(pre.verdict, pre.explanation)
assert (str(reach.verdict), str(inv.verdict), str(pre.verdict)) == ("WITNESS", "NO_WITNESS_WITHIN_BOUND", "UNKNOWN")
