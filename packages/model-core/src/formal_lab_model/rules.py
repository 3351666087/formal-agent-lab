"""Event–condition–handler rules over the neutral IR (P2-070 / P2-071).

A rule's condition is a pure IR expression over the actor's belief state plus the rule context parameters
(`RULE_CONTEXT_PARAMS`, read with `{"op": "ref", …}`), e.g. "the effect comparison differs and a machine is
paused". Evaluation is three-valued over the belief:

- the locations the condition reads (static read set) that are *free* in the belief (unknown) are enumerated
  over their declared domains: TRUE if the condition holds in every completion, FALSE if in none, UNKNOWN if the
  completions disagree; more than `MAX_COMPLETIONS` completions → TIMEOUT (undecided within the limit);
- an expression the IR cannot evaluate (non-IR driver, evaluation error) → UNSUPPORTED.

Resolution for one event: the enabled rules triggered by it are evaluated; among those that are TRUE the highest
`priority` wins. Several TRUE rules at the top priority with *different* outcomes are a CONFLICT: every one of them
is reported as CONFLICT and the most conservative outcome is applied (PAUSE > REPLAN > OBSERVE_MORE > CONTINUE).
UNKNOWN / TIMEOUT / UNSUPPORTED rules never fire, but they are reported.
"""

from __future__ import annotations

import itertools
from typing import Any

from formal_lab_contracts import (
    RULE_CONTEXT_PARAMS,
    Rule,
    RuleDecision,
    RuleEvaluation,
    RuleOutcome,
    RuleResult,
    RuleSet,
    RuleSetRef,
    digest_of,
)
from formal_lab_contracts.ir import ApplyExpr, ConstExpr, QuantExpr, RefExpr, VarExpr

from .checker import CheckedModel, ModelIssue, check_expression
from .interpreter import Interpreter

MAX_COMPLETIONS = 4096
CONSERVATIVE = [RuleOutcome.PAUSE, RuleOutcome.REPLAN, RuleOutcome.OBSERVE_MORE, RuleOutcome.CONTINUE]


def _context_types() -> tuple[dict[str, str], dict[str, list[str]]]:
    params, domains = {}, {}
    for p in RULE_CONTEXT_PARAMS:
        if p.type == "symbol":
            domains[f"__{p.name}"] = list(p.values)
            params[p.name] = f"__{p.name}"
        else:
            params[p.name] = p.type
    return params, domains


def check_rule(rule: Rule, model: CheckedModel) -> list[ModelIssue]:
    """Type problems of a rule against the model (empty when it can be released)."""
    params, domains = _context_types()
    issues = check_expression(model, rule.condition, expected="bool", params=params, extra_domains=domains,
                              where=f"/rules/{rule.rule_id}/condition")
    paths = set(model.state_paths())
    for path in rule.observe_paths:
        if path not in paths:
            issues.append(ModelIssue(path=f"/rules/{rule.rule_id}/observe_paths", code="UNKNOWN_LOCATION",
                                     message=f"{path!r} is not a state location"))
    return issues


def ruleset_digest(ruleset: RuleSet) -> str:
    return digest_of({"ruleset_id": ruleset.ruleset_id, "version": ruleset.version,
                      "model": ruleset.model.model_dump(mode="json"),
                      "rules": [r.model_dump(mode="json") for r in ruleset.rules]}).value


def read_set(expr: Any, model: CheckedModel) -> set[str]:
    """Over-approximation of the state locations an expression may read."""
    out: set[str] = set()

    def visit(e: Any) -> None:
        if isinstance(e, VarExpr):
            fam = model.families.get(e.name)
            if fam is not None and fam.is_state:
                if all(isinstance(i, ConstExpr) for i in e.index):
                    out.add(f"{e.name}[{','.join(str(i.value) for i in e.index)}]" if e.index else e.name)
                else:
                    out.update(fam.table)
            for i in e.index:
                visit(i)
        elif isinstance(e, ApplyExpr):
            for a in e.args:
                visit(a)
        elif isinstance(e, QuantExpr):
            visit(e.body)
            if e.where is not None:
                visit(e.where)
            if e.default is not None:
                visit(e.default)
        elif isinstance(e, (ConstExpr, RefExpr)):
            return

    visit(expr)
    return out


class RuleEvaluator:
    """Evaluates the rules of one rule set for one model (IR)."""

    def __init__(self, ruleset: RuleSet, model: CheckedModel, interpreter: Interpreter | None = None):
        self.ruleset = ruleset
        self.model = model
        self.interp = interpreter or Interpreter(model)
        self.ref = RuleSetRef(ruleset_id=ruleset.ruleset_id, version=ruleset.version,
                              digest=ruleset.digest or digest_of({"x": ruleset.ruleset_id}))
        self._reads = {r.rule_id: read_set(r.condition, model) for r in ruleset.rules}
        self._compiled = {r.rule_id: self.interp.compile_expr(r.condition) for r in ruleset.rules}

    def triggered(self, event_type: str, stage: str | None = None) -> list[Rule]:
        return [r for r in self.ruleset.rules if r.enabled and event_type in {str(e) for e in r.trigger.events}
                and (r.trigger.stage is None or stage is None or str(r.trigger.stage) == stage)]

    def evaluate(self, rule: Rule, state: dict[str, Any], free: list[str], context: dict[str, Any]) -> RuleEvaluation:
        cond = self._compiled[rule.rule_id]
        relevant = sorted(self._reads[rule.rule_id] & set(free))
        domains = [self.model.param_domain(self.model.location_type(p)) for p in relevant]
        total = 1
        for d in domains:
            total *= len(d)
        if total > MAX_COMPLETIONS:
            return RuleEvaluation(rule_id=rule.rule_id, ruleset=self.ref, result=RuleResult.TIMEOUT, outcome=None,
                                  priority=rule.priority, completions_checked=0,
                                  explanation=f"{total} completions of {len(relevant)} unknown location(s) exceed "
                                              f"the limit {MAX_COMPLETIONS}; undecided")
        seen: set[bool] = set()
        checked = 0
        try:
            for combo in itertools.product(*domains):
                s = dict(state)
                s.update(zip(relevant, combo, strict=True))
                seen.add(bool(cond(s, context)))
                checked += 1
                if len(seen) == 2:
                    break
        except Exception as exc:  # evaluation error of this model/context
            return RuleEvaluation(rule_id=rule.rule_id, ruleset=self.ref, result=RuleResult.UNSUPPORTED, outcome=None,
                                  priority=rule.priority, explanation=f"cannot evaluate: {exc}")
        if len(seen) == 2:
            return RuleEvaluation(rule_id=rule.rule_id, ruleset=self.ref, result=RuleResult.UNKNOWN, outcome=None,
                                  priority=rule.priority, completions_checked=checked,
                                  explanation=f"depends on unknown {relevant}: completions disagree")
        value = seen.pop() if seen else False
        how = f"over {checked} completion(s) of {relevant}" if relevant else "on known values"
        return RuleEvaluation(rule_id=rule.rule_id, ruleset=self.ref,
                              result=RuleResult.TRUE if value else RuleResult.FALSE,
                              outcome=rule.outcome if value else None, priority=rule.priority,
                              completions_checked=checked, explanation=f"condition {'holds' if value else 'fails'} "
                                                                        f"{how}")

    def decide(self, event_type: str, state: dict[str, Any], free: list[str], context: dict[str, Any],
               stage: str | None = None) -> RuleDecision | None:
        rules = self.triggered(event_type, stage)
        if not rules:
            return None
        evals = [self.evaluate(r, state, free, context) for r in rules]
        fired = [(r, e) for r, e in zip(rules, evals, strict=True) if e.result is RuleResult.TRUE]
        if not fired:
            return RuleDecision(event_type=event_type, evaluations=evals, outcome=RuleOutcome.CONTINUE, winner=None,
                                priority_explanation="no rule fired; continue")
        top = max(r.priority for r, _ in fired)
        best = [(r, e) for r, e in fired if r.priority == top]
        outcomes = {r.outcome for r, _ in best}
        if len(outcomes) > 1:
            outcome = next(o for o in CONSERVATIVE if o in outcomes)
            conflicted = {r.rule_id for r, _ in best}
            evals = [e.model_copy(update={"result": RuleResult.CONFLICT, "outcome": outcome if e.rule_id in conflicted
                                          else e.outcome}) if e.rule_id in conflicted else e for e in evals]
            names = ", ".join(sorted(conflicted))
            return RuleDecision(event_type=event_type, evaluations=evals, outcome=outcome, winner=None,
                                priority_explanation=f"conflict at priority {top} between {names} "
                                                     f"({', '.join(sorted(o.value for o in outcomes))}); applied the "
                                                     f"most conservative outcome {outcome.value}")
        winner = best[0][0]
        others = sorted({r.rule_id for r, _ in fired} - {winner.rule_id})
        return RuleDecision(event_type=event_type, evaluations=evals, outcome=winner.outcome, winner=winner.rule_id,
                            priority_explanation=f"{winner.rule_id} fired with the highest priority {top}"
                            + (f"; lower-priority rules also fired: {others}" if others else ""))
