"""Small models used by tests, docs and differential checks (interpreter vs Z3)."""

from __future__ import annotations

import random
from typing import Any

from formal_lab_contracts import ModelIR


def c(value: Any, domain: str | None = None) -> dict[str, Any]:
    return {"op": "const", "value": value} | ({"domain": domain} if domain else {})


def v(name: str, *index: dict[str, Any]) -> dict[str, Any]:
    return {"op": "var", "name": name, "index": list(index)}


def r(name: str) -> dict[str, Any]:
    return {"op": "ref", "name": name}


def ap(op: str, *args: dict[str, Any]) -> dict[str, Any]:
    return {"op": op, "args": list(args)}


def assign(var: str, value: dict[str, Any], *index: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "assign", "target": {"var": var, "index": list(index)}, "value": value}


def lamp() -> ModelIR:
    return ModelIR.model_validate(
        {
            "name": "lamp-counter",
            "state": [
                {"name": "on", "type": {"kind": "bool"}, "initial": {"default": False}},
                {"name": "toggles", "type": {"kind": "int", "min": 0, "max": 3}, "initial": {"default": 0}},
            ],
            "actions": [
                {"name": "toggle", "effects": [assign("on", ap("not", v("on"))),
                                               assign("toggles", ap("add", v("toggles"), c(1)))]},
                {"name": "reset", "precondition": ap("gt", v("toggles"), c(0)),
                 "effects": [assign("toggles", c(0)), assign("on", c(False))]},
            ],
            "properties": [
                {"id": "lit", "kind": "goal", "expr": v("on")},
                {"id": "three_toggles", "kind": "goal", "expr": ap("eq", v("toggles"), c(3))},
                {"id": "few_toggles", "kind": "invariant", "expr": ap("le", v("toggles"), c(2))},
                {"id": "never_four", "kind": "invariant", "expr": ap("le", v("toggles"), c(3))},
            ],
        }
    )


def two_jobs() -> ModelIR:
    """Two jobs, two machines, a single shared tool; job b depends on job a."""
    jobs = {"kind": "entity", "set": "jobs"}
    machines = {"kind": "entity", "set": "machines"}
    return ModelIR.model_validate(
        {
            "name": "two-jobs",
            "enums": [{"name": "phase", "values": ["waiting", "running", "done"]}],
            "entity_sets": [{"name": "jobs", "members": ["a", "b"]}, {"name": "machines", "members": ["m1", "m2"]}],
            "constants": [
                {"name": "duration", "type": {"kind": "int", "min": 0, "max": 5}, "index": ["jobs"],
                 "value": {"cells": [{"index": ["a"], "value": 2}, {"index": ["b"], "value": 1}]}},
                {"name": "needs", "type": {"kind": "bool"}, "index": ["jobs", "jobs"],
                 "value": {"default": False, "cells": [{"index": ["b", "a"], "value": True}]}},
            ],
            "state": [
                {"name": "status", "type": {"kind": "enum", "name": "phase"}, "index": ["jobs"],
                 "initial": {"default": "waiting"}},
                {"name": "on", "type": {"kind": "bool"}, "index": ["jobs", "machines"], "initial": {"default": False}},
                {"name": "left", "type": {"kind": "int", "min": 0, "max": 5}, "index": ["jobs"],
                 "initial": {"default": 0}},
                {"name": "clock", "type": {"kind": "int", "min": 0, "max": 6}, "initial": {"default": 0}},
            ],
            "actions": [
                {
                    "name": "start",
                    "params": [{"name": "j", "type": jobs}, {"name": "m", "type": machines}],
                    "precondition": ap(
                        "and",
                        ap("eq", v("status", r("j")), c("waiting")),
                        {"op": "forall", "var": "p", "domain": "jobs", "where": v("needs", r("j"), r("p")),
                         "body": ap("eq", v("status", r("p")), c("done"))},
                        ap("eq", {"op": "count", "var": "o", "domain": "jobs", "body": v("on", r("o"), r("m"))}, c(0)),
                        ap("eq", {"op": "count", "var": "o", "domain": "jobs",
                                  "body": ap("eq", v("status", r("o")), c("running"))}, c(0)),
                    ),
                    "effects": [
                        assign("status", c("running"), r("j")),
                        assign("on", c(True), r("j"), r("m")),
                        assign("left", v("duration", r("j")), r("j")),
                    ],
                },
                {
                    "name": "tick",
                    "effects": [
                        assign("clock", ap("add", v("clock"), c(1))),
                        {"kind": "forall", "var": "j", "domain": "jobs",
                         "where": ap("eq", v("status", r("j")), c("running")),
                         "effects": [
                             assign("left", ap("sub", v("left", r("j")), c(1)), r("j")),
                             {"kind": "when", "condition": ap("le", v("left", r("j")), c(1)),
                              "then": [assign("status", c("done"), r("j")),
                                       {"kind": "forall", "var": "m", "domain": "machines",
                                        "effects": [assign("on", c(False), r("j"), r("m"))]}]},
                         ]},
                    ],
                },
            ],
            "properties": [
                {"id": "all_done", "kind": "goal",
                 "expr": {"op": "forall", "var": "j", "domain": "jobs", "body": ap("eq", v("status", r("j")), c("done"))}},
                {"id": "done_by_2", "kind": "invariant",
                 "expr": ap("implies", ap("ge", v("clock"), c(4)),
                            ap("eq", v("status", c("a")), c("done")))},
                {"id": "b_after_a", "kind": "invariant",
                 "expr": ap("implies", ap("ne", v("status", c("b")), c("waiting")),
                            ap("eq", v("status", c("a")), c("done")))},
            ],
        }
    )


def random_model(seed: int) -> ModelIR:
    """Seeded random small model for differential testing (always type-correct)."""
    rng = random.Random(seed)
    ents = ["e1", "e2"]
    bool_e = lambda i: v("flag", i)  # noqa: E731
    ints = ["x", "y"]

    def int_atom(scope: list[str]) -> dict[str, Any]:
        roll = rng.random()
        if roll < 0.45:
            return v(rng.choice(ints))
        if roll < 0.75:
            return c(rng.randint(0, 3))
        if roll < 0.9 and scope:
            return {"op": "count", "var": "q", "domain": "ents", "body": bool_e(r("q"))}
        return v("level", r(scope[0]) if scope else c(rng.choice(ents)))

    def int_expr(scope: list[str], depth: int = 0) -> dict[str, Any]:
        if depth > 1 or rng.random() < 0.5:
            return int_atom(scope)
        return ap(rng.choice(["add", "sub", "min", "max"]), int_expr(scope, depth + 1), int_expr(scope, depth + 1))

    def ent_ref(scope: list[str]) -> dict[str, Any]:
        return r(scope[0]) if scope and rng.random() < 0.7 else c(rng.choice(ents))

    def bool_expr(scope: list[str], depth: int = 0) -> dict[str, Any]:
        roll = rng.random()
        if depth > 1 or roll < 0.35:
            pick = rng.random()
            if pick < 0.4:
                return bool_e(ent_ref(scope))
            if pick < 0.7:
                return ap(rng.choice(["lt", "le", "eq", "ne", "ge"]), int_expr(scope), int_expr(scope))
            return ap("eq", v("mode"), c(rng.choice(["idle", "busy", "off"])))
        if roll < 0.6:
            return ap(rng.choice(["and", "or"]), bool_expr(scope, depth + 1), bool_expr(scope, depth + 1))
        if roll < 0.75:
            return ap("not", bool_expr(scope, depth + 1))
        if roll < 0.85:
            return ap("implies", bool_expr(scope, depth + 1), bool_expr(scope, depth + 1))
        return {"op": rng.choice(["forall", "exists"]), "var": "q", "domain": "ents", "body": bool_e(r("q"))}

    def effect(scope: list[str], depth: int = 0) -> dict[str, Any]:
        roll = rng.random()
        if roll < 0.3:
            return assign(rng.choice(ints), int_expr(scope))
        if roll < 0.5:
            return assign("flag", bool_expr(scope), ent_ref(scope))
        if roll < 0.62:
            return assign("mode", c(rng.choice(["idle", "busy", "off"])))
        if roll < 0.74:
            return assign("level", int_expr(scope), ent_ref(scope))
        if roll < 0.88 and depth == 0:
            return {"kind": "when", "condition": bool_expr(scope), "then": [effect(scope, 1)],
                    "otherwise": [effect(scope, 1)] if rng.random() < 0.5 else []}
        return {"kind": "forall", "var": "q", "domain": "ents", "where": bool_e(r("q")) if rng.random() < 0.5 else None,
                "effects": [assign("flag", ap("not", bool_e(r("q"))), r("q"))]}

    def loose_guard(scope: list[str]) -> dict[str, Any]:
        roll = rng.random()
        if roll < 0.35:
            return c(True)
        if roll < 0.7:
            return ap("or", bool_expr(scope), bool_expr(scope))
        return bool_expr(scope)

    ent = {"name": "p", "type": {"kind": "entity", "set": "ents"}}
    templates = [
        lambda k: {"name": f"inc{k}", "precondition": loose_guard([]),
                   "effects": [assign(var := rng.choice(ints), ap("add", v(var), c(1)))]},
        lambda k: {"name": f"dec{k}", "precondition": loose_guard([]),
                   "effects": [assign(var := rng.choice(ints), ap("sub", v(var), c(1)))]},
        lambda k: {"name": f"move{k}", "precondition": loose_guard([]),
                   "effects": [assign("x", ap("sub", v("x"), c(1))), assign("y", ap("add", v("y"), c(1)))]},
        lambda k: {"name": f"flip{k}", "params": [ent], "precondition": loose_guard(["p"]),
                   "effects": [assign("flag", ap("not", v("flag", r("p"))), r("p")),
                               {"kind": "when", "condition": v("flag", r("p")),
                                "then": [assign("level", ap("add", v("level", r("p")), c(1)), r("p"))]}]},
        lambda k: {"name": f"cycle{k}", "precondition": loose_guard([]),
                   "effects": [assign("mode", {"op": "ite", "args": [
                       ap("eq", v("mode"), c("idle")), c("busy"),
                       {"op": "ite", "args": [ap("eq", v("mode"), c("busy")), c("off"), c("idle")]}]})]},
        lambda k: {"name": f"mix{k}", "params": [ent] if rng.random() < 0.6 else [],
                   "precondition": loose_guard([]), "effects": [effect([]) for _ in range(rng.randint(1, 2))]},
    ]
    actions = []
    for k in range(rng.randint(3, 5)):
        actions.append(rng.choice(templates)(k))
    return ModelIR.model_validate(
        {
            "name": f"random-{seed}",
            "enums": [{"name": "modes", "values": ["idle", "busy", "off"]}],
            "entity_sets": [{"name": "ents", "members": ents}],
            "state": [
                {"name": "x", "type": {"kind": "int", "min": 0, "max": 3}, "initial": {"default": rng.randint(0, 3)}},
                {"name": "y", "type": {"kind": "int", "min": 0, "max": 3}, "initial": {"default": rng.randint(0, 3)}},
                {"name": "flag", "type": {"kind": "bool"}, "index": ["ents"], "initial": {"default": rng.random() < 0.5}},
                {"name": "level", "type": {"kind": "int", "min": 0, "max": 2}, "index": ["ents"],
                 "initial": {"default": 0}},
                {"name": "mode", "type": {"kind": "enum", "name": "modes"}, "initial": {"default": "idle"}},
            ],
            "actions": actions,
            "properties": [
                {"id": "goal", "kind": "goal", "expr": bool_expr([])},
                {"id": "inv", "kind": "invariant", "expr": bool_expr([])},
            ],
        }
    )
