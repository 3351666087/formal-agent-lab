"""Emit state-machine diagrams (Mermaid) for every LTS, and a neutral text serialisation
used as the model-query stimulus. The serialisation is exactly the diagram as a
transition table — the only thing that differs between the attack framing and the
real-world framing is the vocabulary of the state/action names (the whole point of the
study); the structure is identical by construction (proven in verify_isomorphism.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import LTS, TWINS  # noqa: E402


def mermaid(lts: LTS) -> str:
    lines = ["stateDiagram-v2", f"    %% {lts.name} — {lts.domain}", f"    [*] --> {lts.initial}"]
    for s, a, d in lts.transitions:
        lines.append(f"    {s} --> {d}: {a}")
    for b in lts.bad:
        lines.append(f"    {b} --> [*]")
        lines.append(f"    class {b} bad")
    lines.append("    classDef bad fill:#d7263d,color:#fff,stroke:#8b0000;")
    return "\n".join(lines)


def table(lts: LTS) -> str:
    """Neutral transition-table serialisation — the stimulus shown to the models."""
    rows = [f"States: {', '.join(lts.states)}",
            f"Initial state: {lts.initial}",
            f"Designated state of interest: {', '.join(lts.bad)}",
            "Transitions (source --action--> destination):"]
    for s, a, d in lts.transitions:
        rows.append(f"  {s} --{a}--> {d}")
    return "\n".join(rows)


def main() -> None:
    out = Path(__file__).resolve().parent / "diagrams"
    out.mkdir(exist_ok=True)
    for t in TWINS:
        for lts in (t.attack, t.real):
            (out / f"{lts.name}.mmd").write_text(mermaid(lts))
            (out / f"{lts.name}.txt").write_text(table(lts))
    print(f"Wrote Mermaid + table serialisations for {len(TWINS)*2} machines to {out}")


if __name__ == "__main__":
    main()
