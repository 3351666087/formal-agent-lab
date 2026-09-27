"""Planner.propose: the same PlanningContext drives the rule, Z3 and (stub) LLM strategies."""

from formal_lab_contracts import BudgetUsage, CandidateAction, GroundAction, PlanningContext, PreconditionVerdict
from formal_lab_env.ir_world import create as create_env
from formal_lab_example_scheduling.rule_planner import create as create_rule
from formal_lab_example_scheduling.scenarios import model_package, scenario
from formal_lab_model import Interpreter, action_specs, check_model
from formal_lab_solver_z3.planner import create as create_z3
from formal_lab_strategies.llm_planner import create as create_llm

package = model_package()
sc = scenario("normal", package, seed=1)


class Services:
    def pinned_model(self):
        return package

    def get_setting(self, key):
        return None


env = create_env(sc.environment.config, Services())
obs = env.reset(sc, package, run_id="example", seed=1)
checked = check_model(package.ir)
interp = Interpreter(checked)
state = {f.path: f.value for f in obs.facts}
candidates = [CandidateAction(action=GroundAction(action_type=ga.action, params=dict(ga.params)),
                              belief_applicability=PreconditionVerdict.APPLICABLE if interp.step(ga, state).applicable
                              else PreconditionVerdict.INAPPLICABLE) for ga in checked.ground_actions]
context = PlanningContext(run_id="example", step=1, step_id="example:s1", actor_id="dispatcher", observation=obs,
                          action_specs=action_specs(checked), candidates=candidates, model=package.ref(),
                          budget=sc.budget, usage=BudgetUsage(), seed=1)
for name, planner in (("rule", create_rule({}, Services())), ("z3", create_z3({"horizon": 18}, Services())),
                      ("llm-stub", create_llm({"client": "stub", "stub_preference": ["assign"]}, Services()))):
    p = planner.propose(context)
    print(f"{name:9s} {p.source.kind.value:9s} {p.action.action_type}{p.action.params} — {p.rationale[:70]}")
