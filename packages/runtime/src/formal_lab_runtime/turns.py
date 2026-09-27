"""Turn scheduling (P2-030 / P2-031): exactly one participant acts per global logical step.

The schedule is a cycle of actor ids — the participants in declaration order (ROUND_ROBIN) or the scenario's
`table` (FIXED_TABLE, may repeat actors). `TurnState.position` is the absolute index of the next cycle slot;
round r covers slots [(r-1)·L, r·L) for a cycle of length L. Slots of retired actors are passed over without
consuming a global step. The persistent `TurnState` (position, round, per-actor steps, skipped turns, retired
actors, no-progress counter) lets a run resume on exactly the right turn after a pause, a worker crash or
continue-as-new. A single participant under ROUND_ROBIN reproduces phase-1 numbering
(round = actor step = global step).
"""

from __future__ import annotations

from formal_lab_contracts import TurnMode, TurnPolicy, TurnRef, TurnState


class CycleScheduler:
    """TurnScheduler over a fixed cycle of actor ids."""

    def __init__(self, policy: TurnPolicy, participants: list[str]):
        if not participants:
            raise ValueError("a run needs at least one participant")
        self.policy = policy
        self.participants = list(participants)
        self.cycle = list(policy.table) if policy.mode is TurnMode.FIXED_TABLE else list(participants)
        unknown = [a for a in self.cycle if a not in participants]
        if unknown:
            raise ValueError(f"turn table names unknown participants {unknown}")

    @staticmethod
    def initial_state() -> TurnState:
        return TurnState(global_step=0, round=0, position=0)

    def _slot(self, state: TurnState, actor: str | None = None) -> int | None:
        """First slot at or after the cursor whose actor is active (and equals `actor` if given)."""
        n = len(self.cycle)
        for k in range(n):
            slot = state.position + k
            who = self.cycle[slot % n]
            if who not in state.retired and (actor is None or who == actor):
                return slot
        return None

    def next_turn(self, state: TurnState) -> TurnRef | None:
        """The turn of global step `state.global_step + 1`, or None when every scheduled actor is retired."""
        slot = self._slot(state)
        if slot is None:
            return None
        actor = self.cycle[slot % len(self.cycle)]
        return TurnRef(global_step=state.global_step + 1, round=slot // len(self.cycle) + 1, actor_id=actor,
                       actor_step=state.actor_steps.get(actor, 0) + 1)

    def advance(self, state: TurnState, turn: TurnRef, *, acted: bool, progressed: bool) -> TurnState:
        """State after `turn` was taken (acted = an action was executed; otherwise the actor passed its turn)."""
        slot = self._slot(state, turn.actor_id)
        if slot is None:
            raise ValueError(f"{turn.actor_id} has no pending turn")
        steps, skipped = dict(state.actor_steps), dict(state.skipped)
        if acted:
            steps[turn.actor_id] = steps.get(turn.actor_id, 0) + 1
        else:
            skipped[turn.actor_id] = skipped.get(turn.actor_id, 0) + 1
        return state.model_copy(update={
            "global_step": turn.global_step,
            "round": turn.round,
            "position": slot + 1,
            "actor_steps": steps,
            "skipped": skipped,
            "no_progress": 0 if progressed else state.no_progress + 1,
        })

    @staticmethod
    def retire(state: TurnState, actor_id: str) -> TurnState:
        if actor_id in state.retired:
            return state
        return state.model_copy(update={"retired": [*state.retired, actor_id]})

    @staticmethod
    def round_starts(state: TurnState, turn: TurnRef) -> bool:
        """True when `turn` opens a new round (round-start observations are taken then)."""
        return turn.round > state.round

    def active(self, state: TurnState) -> list[str]:
        return [a for a in self.participants if a not in state.retired]


def scheduler_for(policy: TurnPolicy, participants: list[str]) -> CycleScheduler:
    return CycleScheduler(policy, participants)
