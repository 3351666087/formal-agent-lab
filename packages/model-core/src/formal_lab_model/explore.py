"""Exhaustive bounded exploration with the reference interpreter (ground truth for small models)."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from .checker import GroundAction
from .interpreter import Interpreter, State


@dataclass
class SearchOutcome:
    found: bool
    path: list[tuple[GroundAction | None, State]] = field(default_factory=list)
    states_explored: int = 0
    depth_completed: int = 0
    truncated: bool = False  # hit max_states before completing the bound
    elapsed_ms: float = 0.0


def bfs(
    interp: Interpreter,
    start: State,
    target: Callable[[State], bool],
    max_depth: int,
    max_states: int = 200_000,
) -> SearchOutcome:
    """Shortest path (≤ max_depth actions) from `start` to a state satisfying `target`."""
    t0 = time.perf_counter()
    order = sorted(start)

    def key(s: State) -> tuple:
        return tuple(s[p] for p in order)

    if target(start):
        return SearchOutcome(True, [(None, start)], 1, 0, False, (time.perf_counter() - t0) * 1000)
    parent: dict[tuple, tuple[tuple | None, GroundAction | None, State]] = {key(start): (None, None, start)}
    frontier = deque([(start, 0)])
    depth_completed = 0
    while frontier:
        state, depth = frontier.popleft()
        depth_completed = max(depth_completed, depth)
        if depth >= max_depth:
            continue
        for ga, nxt in interp.successors(state):
            k = key(nxt)
            if k in parent:
                continue
            parent[k] = (key(state), ga, nxt)
            if target(nxt):
                path: list[tuple[GroundAction | None, State]] = []
                cur: tuple | None = k
                while cur is not None:
                    pk, act, st = parent[cur]
                    path.append((act, st))
                    cur = pk
                path.reverse()
                return SearchOutcome(True, path, len(parent), depth + 1, False, (time.perf_counter() - t0) * 1000)
            if len(parent) >= max_states:
                return SearchOutcome(False, [], len(parent), depth, True, (time.perf_counter() - t0) * 1000)
            frontier.append((nxt, depth + 1))
    return SearchOutcome(False, [], len(parent), min(depth_completed + 1, max_depth), False,
                         (time.perf_counter() - t0) * 1000)


def reachable_states(interp: Interpreter, start: State, max_depth: int, max_states: int = 200_000) -> list[State]:
    order = sorted(start)
    seen = {tuple(start[p] for p in order)}
    out = [start]
    frontier = deque([(start, 0)])
    while frontier:
        state, depth = frontier.popleft()
        if depth >= max_depth:
            continue
        for _, nxt in interp.successors(state):
            k = tuple(nxt[p] for p in order)
            if k not in seen:
                seen.add(k)
                out.append(nxt)
                if len(out) >= max_states:
                    return out
                frontier.append((nxt, depth + 1))
    return out
