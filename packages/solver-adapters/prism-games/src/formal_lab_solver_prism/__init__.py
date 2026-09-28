"""PRISM-games extension (optional deepening track, P2-X01 … P2-X04).

A typed model payload (`AllocationGame`, schema `org.formal-lab.prism-games/allocation-game@1`, profile
`prism_smg_turn_based_v1`), a process-level adapter for a locally installed PRISM-games binary, and an independent
solver that verifies PRISM's numbers and exported strategy in-model. Results are `ProbabilisticCheckRecord`s
(`org.formal-lab.prism-games/result@1`), presented separately from deterministic Z3 results.
"""

from .adapter import (
    CAPABILITIES,
    PINNED,
    RESULT_SCHEMA,
    ProbabilisticCheckRecord,
    PropertyResult,
    Unavailable,
    check,
    locate,
    version,
)
from .game import (
    ASSUMPTIONS,
    EXAMPLE,
    GAME_SCHEMA,
    NAMESPACE,
    PROFILE,
    AllocationGame,
    Machine,
    evaluate,
    solve,
    to_prism,
)

__all__ = [
    "ASSUMPTIONS",
    "CAPABILITIES",
    "EXAMPLE",
    "GAME_SCHEMA",
    "NAMESPACE",
    "PINNED",
    "PROFILE",
    "RESULT_SCHEMA",
    "AllocationGame",
    "Machine",
    "ProbabilisticCheckRecord",
    "PropertyResult",
    "Unavailable",
    "check",
    "evaluate",
    "locate",
    "solve",
    "to_prism",
    "version",
]
