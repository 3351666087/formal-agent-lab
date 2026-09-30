"""Domain configuration for the MAL security lab (phase 3B, D1/D2).

Three kinds of intent are kept apart, because conflating them is the classic mistake (D1):

- **LabPolicy** — the experiment's own boundary: which steps / assets the red team may touch, budgets, and which
  actions the lab forbids regardless of the target's security. Violating LabPolicy is an experiment-conduct fault.
- **TargetSecurity** — a property of the modelled system: e.g. "the secret data cannot be read". The red team
  looking for a counterexample to a TargetSecurity property is doing its job — it is *not* a LabPolicy violation.
- **BusinessSLO** — the defender's / operator's objective: keep the service available and within cost while the
  attack and normal business run.

These are plain records carried in the scenario's `extensions` and read by the domain rules, the Broker (D2) and
the UI (D6); they are not platform contracts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

EXT_LAB_POLICY = "org.formal-lab.mal.lab-policy"
EXT_TARGET_SECURITY = "org.formal-lab.mal.target-security"
EXT_BUSINESS_SLO = "org.formal-lab.mal.business-slo"
EXT_ATTACK_GRAPH = "org.mal-lang.attack-graph"


@dataclass(frozen=True)
class LabPolicy:
    """The experiment boundary. `allowed_steps` empty = every modelled step is in bounds."""

    allowed_assets: list[str] = field(default_factory=list)
    allowed_steps: list[str] = field(default_factory=list)
    forbidden_steps: list[str] = field(default_factory=list)
    max_attack_steps: int | None = None
    note: str = ""

    def permits(self, full_name: str, asset: str | None = None) -> bool:
        if full_name in self.forbidden_steps:
            return False
        if self.allowed_steps and full_name not in self.allowed_steps:
            return False
        return not (self.allowed_assets and asset is not None and asset not in self.allowed_assets)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LabPolicy:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class TargetSecurity:
    """A security property of the target system. `reach_forbidden` = the step whose reachability breaks it (the red
    team seeks it); `kind` labels the CIA aspect."""

    property_id: str
    reach_forbidden: str
    kind: str = "confidentiality"  # confidentiality | integrity | availability
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TargetSecurity:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class BusinessSLO:
    """The operator's objective while the experiment runs."""

    metric: str
    direction: str = "HIGHER_IS_BETTER"  # HIGHER_IS_BETTER | LOWER_IS_BETTER
    threshold: float | None = None
    unit: str = ""
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BusinessSLO:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
