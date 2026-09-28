"""Independent adapter for the PRISM-games binary (P2-X02 / P2-X03).

PRISM-games (GPL-2.0) is never imported or linked: it runs as a separate process from a local installation, and this
package only writes its input files and reads its output files. Nothing of PRISM-games is redistributed with the
platform (images, wheels and the offline bundle do not contain it); `locate()` finds a user installation:

    FAL_PRISM_GAMES_HOME   directory with bin/prism (default ~/.local/opt/prism-games-*/ )
    FAL_PRISM_JAVA_HOME    Java runtime for it (default: JAVA_HOME, else ~/.local/opt/jdk-*/)

`check(game)` runs one PRISM invocation per property (the robust one with strategy and model export), keeps the raw
model, properties, logs and strategy, and checks the result in-model: the independent solver in `game.py` must give
the same value, its reachable-state count must equal PRISM's, and the exported dispatcher strategy, evaluated
against the worst-case environment, must achieve the reported value.
"""

from __future__ import annotations

import glob
import hashlib
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .game import (
    ASSUMPTIONS,
    COOPERATIVE,
    NAMESPACE,
    PROFILE,
    ROBUST,
    AllocationGame,
    evaluate,
    solve,
    to_prism,
)

RESULT_SCHEMA = f"{NAMESPACE}/result@1"
PINNED = {"version": "3.2.4", "license": "GPL-2.0",
          "source": "https://github.com/prismmodelchecker/prism-games/releases/tag/v3.2.4",
          "artifacts": {"linux64-arm": "prism-games-3.2.4-linux64-arm.tar.gz "
                                       "sha256 366f5fedf6d8be8b089372f64714edebda3fab26001bf38323905b8fcb62ce52",
                        "linux64-x86": "prism-games-3.2.4-linux64-x86.tar.gz (same release; not run here)"}}
TOLERANCE = 1e-6  # PRISM's default value-iteration termination epsilon (relative); the game is acyclic here


class Unavailable(RuntimeError):
    """PRISM-games (or its Java runtime) is not installed; the extension answers UNSUPPORTED, never a guess."""


class PropertyResult(BaseModel):
    property: str
    coalition: list[str]
    value: float
    reference_value: float = Field(description="independent backward induction over the same game (game.solve)")
    agrees: bool
    method: str | None = None
    iterations: int | None = None
    seconds: float | None = None
    log: str = Field(description="PRISM-games stdout/stderr of this invocation")


class ProbabilisticCheckRecord(BaseModel):
    """Result of a probabilistic query: typed extension `org.formal-lab.prism-games/result@1`. Kept apart from the
    deterministic Z3 BoundedCheckResult: a number with a numerical tolerance, not a SAT/UNSAT verdict."""

    schema_id: Literal["org.formal-lab.prism-games/result@1"] = RESULT_SCHEMA
    kind: Literal["PROBABILISTIC"] = "PROBABILISTIC"
    profile: str = PROFILE
    game: AllocationGame
    backend: dict[str, Any]
    assumptions: list[str] = Field(default_factory=lambda: list(ASSUMPTIONS))
    model_text: str
    model_sha256: str
    properties: list[PropertyResult]
    size: dict[str, int] = Field(description="states / transitions / choices reported by PRISM")
    reference_states: int
    strategy: dict[str, str] = Field(description="dispatcher decision per (round, finished jobs), from PRISM's export")
    strategy_value: float = Field(description="the exported strategy evaluated against the worst-case environment")
    verified: bool
    tolerance: float = TOLERANCE
    started_at: str
    seconds: float
    notes: list[str] = Field(default_factory=list)


def _first(pattern: str, text: str, cast=str):
    m = re.search(pattern, text)
    return cast(m.group(1)) if m else None


def locate() -> tuple[Path, Path | None]:
    home = os.environ.get("FAL_PRISM_GAMES_HOME") or next(iter(sorted(
        glob.glob(str(Path.home() / ".local/opt/prism-games-*")), reverse=True)), None)
    if not home or not (Path(home) / "bin" / "prism").exists():
        raise Unavailable("PRISM-games is not installed (set FAL_PRISM_GAMES_HOME to a directory with bin/prism; "
                          "see docs/local-development.md, 'PRISM-games')")
    java = os.environ.get("FAL_PRISM_JAVA_HOME") or os.environ.get("JAVA_HOME") or next(iter(sorted(
        glob.glob(str(Path.home() / ".local/opt/jdk-*")), reverse=True)), None)
    return Path(home), Path(java) if java else None


def _env(java: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    if java:
        env["JAVA_HOME"] = str(java)
        env["PATH"] = f"{java / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    return env


def version() -> dict[str, Any]:
    home, java = locate()
    res = subprocess.run([str(home / "bin" / "prism"), "-version"], capture_output=True, text=True, env=_env(java),
                         timeout=120)
    if res.returncode != 0:
        raise Unavailable(f"PRISM-games did not start: {(res.stderr or res.stdout).strip()[:300]}")
    jv = subprocess.run([str((java / "bin" / "java") if java else "java"), "-version"], capture_output=True,
                        text=True, env=_env(java), timeout=60)
    return {"name": "prism-games", "version": _first(r"version\s+([\w.\-]+)", res.stdout) or res.stdout.strip(),
            "home": str(home), "java": (jv.stderr or jv.stdout).splitlines()[0] if (jv.stderr or jv.stdout) else "?",
            "arch": os.uname().machine, **{k: v for k, v in PINNED.items() if k != "version"},
            "pinned_version": PINNED["version"]}


def _run(home: Path, java: Path | None, work: Path, prop: int, extra: list[str]) -> str:
    cmd = [str(home / "bin" / "prism"), "model.prism", "props.props", "-prop", str(prop), *extra]
    res = subprocess.run(cmd, cwd=work, capture_output=True, text=True, env=_env(java), timeout=600)
    log = f"$ {' '.join(cmd[1:])}\n{res.stdout}{res.stderr}"
    if res.returncode != 0 or "Result:" not in res.stdout:
        raise RuntimeError(f"PRISM-games failed (exit {res.returncode}):\n{log[-2000:]}")
    return log


def _strategy(game: AllocationGame, work: Path) -> dict[tuple[int, frozenset[str]], str]:
    header = (work / "model.sta").read_text().splitlines()[0].strip("()").split(",")
    out = {}
    for line in (work / "strat.txt").read_text().splitlines():
        state, _, action = line.partition("=")
        values = dict(zip(header, state.strip("()").split(","), strict=True))
        if values["t"] != "0" or not action:
            continue  # environment / work states, and states where the game is over
        done = frozenset(j for j in game.jobs if values[f"d_{j}"] == "true")
        out[(int(values["r"]), done)] = action
    return out


def check(game: AllocationGame, *, keep: Path | None = None) -> ProbabilisticCheckRecord:
    """Run the robust and the cooperative reachability query and verify them in-model (see module doc)."""
    home, java = locate()
    backend = version()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.perf_counter()
    model = to_prism(game)
    with tempfile.TemporaryDirectory(prefix="fal-prism-") as tmp:
        work = keep or Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        (work / "model.prism").write_text(model)
        (work / "props.props").write_text(f"{ROBUST}\n{COOPERATIVE}\n")
        robust_log = _run(home, java, work, 1, ["-exportstrat", "strat.txt", "-exportmodel", "model.all"])
        coop_log = _run(home, java, work, 2, [])
        strategy = _strategy(game, work)
    reference = {False: solve(game), True: solve(game, cooperative=True)}
    props = []
    for text, log, coop in ((ROBUST, robust_log, False), (COOPERATIVE, coop_log, True)):
        value = _first(r"Result:\s+([0-9.eE+\-]+)", log, float)
        ref = reference[coop].value
        props.append(PropertyResult(
            property=text, coalition=["dispatcher", "environment"] if coop else ["dispatcher"], value=value,
            reference_value=ref, agrees=abs(value - ref) <= TOLERANCE,
            method=_first(r"Starting (value iteration[^.]*?)\.\.\.", log),
            iterations=_first(r"Value iteration[^\n]*? took (\d+) iterations", log, int),
            seconds=_first(r"Time for model checking:\s+([0-9.]+)", log, float), log=log))
    size = {"states": _first(r"States:\s+(\d+)", robust_log, int),
            "transitions": _first(r"Transitions:\s+(\d+)", robust_log, int),
            "choices": _first(r"Choices:\s+(\d+)", robust_log, int)}
    strategy_value = evaluate(game, strategy)
    notes = []
    if "Deadlocks detected and fixed" in robust_log:
        notes.append("PRISM added self-loops to terminal states (goal reached or rounds used up): expected, they "
                     "are absorbing in the game")
    verified = (all(p.agrees for p in props) and size["states"] == reference[False].states
                and abs(strategy_value - props[0].value) <= TOLERANCE)
    return ProbabilisticCheckRecord(
        game=game, backend=backend, model_text=model, model_sha256=hashlib.sha256(model.encode()).hexdigest(),
        properties=props, size=size, reference_states=reference[False].states,
        strategy={f"round {r}, finished {{{', '.join(sorted(d))}}}": a for (r, d), a in sorted(
            strategy.items(), key=lambda kv: (kv[0][0], sorted(kv[0][1])))},
        strategy_value=strategy_value, verified=verified, started_at=started,
        seconds=round(time.perf_counter() - t0, 3), notes=notes)


# capability table of the extension (P2-X03): what the adapter supports, measured on this machine
CAPABILITIES = [
    {"feature": "turn-based SMG reachability", "query": "<<C>> Pmax=? [ F \"done\" ]", "status": "SUPPORTED",
     "check": "value equals independent backward induction within 1e-6; state count equals the reference graph"},
    {"feature": "strategy export and in-model verification", "query": "-exportstrat (actions)", "status": "SUPPORTED",
     "check": "exported dispatcher strategy achieves the reported value against the worst-case environment"},
    {"feature": "cooperative coalition", "query": "<<dispatcher,environment>> Pmax=? [ F \"done\" ]",
     "status": "SUPPORTED", "check": "value equals the cooperative backward induction"},
    {"feature": "rewards, bounded / multi-objective, concurrent games (CSG)", "query": "R{..}, F<=k, multi(...)",
     "status": "UNSUPPORTED", "check": "PRISM-games supports them; this adapter does not generate or verify them"},
    {"feature": "partial observation", "query": "—", "status": "UNSUPPORTED",
     "check": "the allocation game is fully observed by construction"},
]
