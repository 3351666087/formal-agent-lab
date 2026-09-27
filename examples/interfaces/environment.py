"""Environment.reset/observe/step/snapshot/restore/close on the pure-data IR world (no external systems)."""

from formal_lab_contracts import ActionProposal
from formal_lab_env.ir_world import create
from formal_lab_example_scheduling.scenarios import model_package, scenario

package = model_package()
sc = scenario("state-delay", package, seed=1)


class Services:  # what the platform hands to plugin factories
    def pinned_model(self):
        return package


env = create(sc.environment.config, Services())
obs = env.reset(sc, package, run_id="example", seed=1)
print("step", obs.step, "facts", len(obs.facts), "unknowns", len(obs.unknowns))
proposal = ActionProposal(proposal_id="p1", run_id="example", step_id="example:s1", step=1, actor_id="dispatcher",
                          action={"action_type": "assign", "params": {"op": "o1_cut", "m": "m1"}},
                          based_on_revision=obs.state_revision,
                          source={"kind": "HUMAN", "strategy": {"plugin_id": "example", "version": "1.0.0"}})
outcome = env.step(proposal, operation_id="example:s1:apply")
snap = env.snapshot()
after = env.observe("dispatcher")
print(outcome.status, "revision", outcome.revision_after, "unknown now", len(after.unknowns))
env2 = create(sc.environment.config, Services())
env2.restore(snap)
assert env2.truth_state() == env.truth_state()
env.close()
env2.close()
