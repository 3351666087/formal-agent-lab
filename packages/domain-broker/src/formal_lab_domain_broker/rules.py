"""Typed event–condition–action rules for domain admission (phase 3B, D2).

A rule reads: **on** an event, **when** its conditions hold, **then** apply a handling (ADMIT / DENY / REQUIRE_RECEIPT
/ REPLAN / OBSERVE). Rules are data, reviewable as text before they are trusted: each carries the natural-language
`source` it was written from and a `status` (DRAFT → REVIEWED → RELEASED). Only a RELEASED `RuleSet` — frozen with a
version and a content digest — is consulted at execution time (D2: 自然语言转换的规则先可审查、再固定版本发布).

The engine is deliberately small and total: conditions are typed predicates over a plain context dict, evaluated with
no eval/exec. A condition that cannot be determined returns None (UNKNOWN); a rule that needs an UNKNOWN condition does
not fire its positive handling — the caller stops the side effect and asks for another observation / re-plan, exactly
as D2 requires for missing / unknown / timeout / unsupported checks.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Handling(StrEnum):
    ADMIT = "ADMIT"
    DENY = "DENY"
    REQUIRE_RECEIPT = "REQUIRE_RECEIPT"
    REPLAN = "REPLAN"
    OBSERVE = "OBSERVE"


class RuleStatus(StrEnum):
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    RELEASED = "RELEASED"


# A condition is a named, typed predicate over the context; returns True / False / None(=unknown).
Predicate = Callable[[dict[str, Any]], bool | None]
_REGISTRY: dict[str, Predicate] = {}


def condition(name: str) -> Callable[[Predicate], Predicate]:
    def deco(fn: Predicate) -> Predicate:
        _REGISTRY[name] = fn
        return fn
    return deco


def evaluate_condition(name: str, ctx: dict[str, Any]) -> bool | None:
    if name not in _REGISTRY:
        return None  # unknown condition → undeterminable, never silently true
    return _REGISTRY[name](ctx)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    on: str  # event kind, e.g. "side_effect_action"
    when: list[str]  # condition names, all must hold (True) for the rule to fire
    then: Handling
    kind: str = "action_precondition"  # lab_policy | action_precondition | role_rule | target_security
    source: str = ""  # the natural-language requirement this rule was written from (for review)
    status: RuleStatus = RuleStatus.DRAFT
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FiredRule:
    rule_id: str
    kind: str
    handling: Handling
    holds: bool | None  # True fired; False conditions failed; None a condition was unknown
    detail: str
    unknown_conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuleSet:
    ruleset_id: str
    version: int
    rules: list[Rule]
    status: RuleStatus = RuleStatus.DRAFT
    note: str = ""

    def digest(self) -> str:
        body = json.dumps([r.to_dict() for r in self.rules], sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(f"{self.ruleset_id}:{self.version}:{body}".encode()).hexdigest()

    def released(self) -> RuleSet:
        """Freeze a reviewed ruleset for execution: every rule must be REVIEWED or RELEASED first."""
        pending = [r.rule_id for r in self.rules if r.status == RuleStatus.DRAFT]
        if pending:
            raise ValueError(f"cannot release {self.ruleset_id}: rules still in DRAFT: {pending}")
        from dataclasses import replace

        rules = [replace(r, status=RuleStatus.RELEASED) for r in self.rules]
        return replace(self, rules=rules, status=RuleStatus.RELEASED)

    def for_event(self, event: str) -> list[Rule]:
        return [r for r in self.rules if r.on == event]


def evaluate(ruleset: RuleSet, event: str, ctx: dict[str, Any]) -> list[FiredRule]:
    """Evaluate every rule registered for `event`. A rule fires (holds=True) only when all its conditions are True;
    if any condition is None the rule is undetermined (holds=None) and its positive handling must not be applied."""
    if ruleset.status != RuleStatus.RELEASED:
        raise ValueError(f"ruleset {ruleset.ruleset_id} v{ruleset.version} is {ruleset.status}, not RELEASED")
    out: list[FiredRule] = []
    for rule in ruleset.for_event(event):
        results = {c: evaluate_condition(c, ctx) for c in rule.when}
        unknown = [c for c, v in results.items() if v is None]
        if unknown:
            holds: bool | None = None
        else:
            holds = all(results.values())
        out.append(FiredRule(rule_id=rule.rule_id, kind=rule.kind, handling=rule.then, holds=holds,
                             detail=rule.detail or rule.source, unknown_conditions=unknown))
    return out
