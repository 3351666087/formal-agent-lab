"""Red / blue role boundaries (phase 3B, D2).

Two things are kept apart, and this module enforces both with the platform's own `ParticipantView` (G4) plus an
independent leak guard:

1. **Visibility** — each role's planner receives only the locations its `ParticipantView` includes; hidden ground
   truth (the other side's configuration, the referee's answer key) and any credential are excluded before the belief
   is built. The kernel still works on the full truth; the planner never sees the withheld values.

2. **Leak guard** — an independent check that a payload actually handed to a planner (observation, model payload,
   candidates, explanations, counterexamples, last_outcome, checkpoints, downloads) contains none of the marked secret
   locations or credential fields. This does not trust the view to be applied correctly; it inspects the real payload.

`redact()` returns the payload a role may receive; `leaks()` reports any secret that survived, so a test can assert an
empty result (legitimate observation complete, hidden data absent).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import ParticipantView


def _family(path: str) -> str:
    return path.split("[", 1)[0]


def _matches(path: str, patterns: list[str]) -> bool:
    return any(path == p or _family(path) == p or _family(path) == _family(p) for p in patterns)


def view_allows(view: ParticipantView, path: str) -> bool:
    if view.exclude and _matches(path, view.exclude):
        return False
    if not view.include:
        return True
    return _matches(path, view.include)


@dataclass(frozen=True)
class RoleBoundary:
    """One role's data boundary: what its planner may see, plus the secrets it must never see."""

    role: str
    view: ParticipantView
    secret_paths: list[str] = field(default_factory=list)  # ground-truth / other-side locations
    credential_fields: list[str] = field(default_factory=list)  # key names never allowed in any planner payload

    def redact_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """The state locations this role's planner may receive."""
        return {p: v for p, v in state.items() if view_allows(self.view, p) and not _matches(p, self.secret_paths)}

    def leaks(self, payload: Any) -> list[str]:
        """Every marked secret location or credential field found anywhere in `payload` (a dict / list / scalar)."""
        found: list[str] = []
        self._scan(payload, found)
        return sorted(set(found))

    def _scan(self, obj: Any, found: list[str]) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and (k in self.credential_fields or _matches(k, self.secret_paths)):
                    found.append(k)
                self._scan(v, found)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                self._scan(v, found)
        elif isinstance(obj, str) and _matches(obj, self.secret_paths):
            found.append(obj)


def red_blue_boundaries(*, secret_paths: list[str] | None = None,
                        credential_fields: list[str] | None = None) -> dict[str, RoleBoundary]:
    """The standard two-role setup: the attacker sees only compromise state, the defender sees defence config and
    service health; neither sees the referee's ground-truth reachability or any signing / service credential."""
    creds = credential_fields or ["signing_key", "receipt_key", "service_token", "api_key", "secret"]
    secrets = secret_paths or ["ground_truth", "answer_key"]
    return {
        "attacker": RoleBoundary(
            role="attacker",
            view=ParticipantView(include=["compromised"], exclude=["defense", *secrets], label="红方视图"),
            secret_paths=[*secrets, "defense"], credential_fields=creds),
        "defender": RoleBoundary(
            role="defender",
            view=ParticipantView(include=["defense", "health", "compromised"], exclude=list(secrets),
                                 label="蓝方视图"),
            secret_paths=list(secrets), credential_fields=creds),
    }
