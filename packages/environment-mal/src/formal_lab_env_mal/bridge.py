"""Bridge to the isolated MAL toolchain (phase 3B, D1).

The MAL toolchain (mal-toolbox, mal-simulator and their antlr/tree-sitter/pettingzoo dependencies) is heavy and
conflicts with the frozen platform lock, so — like PRISM-games (D-023) — it lives in a separate virtual
environment and is reached through a typed subprocess (`_worker.py`), never imported here.

Locate it with:
    FAL_MAL_HOME    a venv with bin/python and mal-toolbox + mal-simulator installed (default ~/.venvs/fal-mal)
    FAL_MAL_MAR     the compiled MAL language archive (default $FAL_MAL_HOME/corelang/corelang-*.mar)

`Unavailable` (with the reason) is raised when it is not installed, so callers can record BLOCKED rather than fail.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

WORKER = Path(__file__).with_name("_worker.py")


class Unavailable(RuntimeError):
    """The MAL toolchain is not installed / reachable; the reason explains how to provide it."""


def locate() -> tuple[Path, Path]:
    """(python of the fal-mal venv, compiled .mar language). Raises Unavailable with the fix if either is missing."""
    home = Path(os.environ.get("FAL_MAL_HOME", Path.home() / ".venvs" / "fal-mal"))
    py = home / "bin" / "python"
    if not py.exists():
        raise Unavailable(f"MAL venv not found at {home} (set FAL_MAL_HOME to a venv with mal-toolbox + "
                          "mal-simulator; see docs/local-development.md)")
    mar = os.environ.get("FAL_MAL_MAR")
    if mar:
        mar_path = Path(mar)
    else:
        found = sorted((home / "corelang").glob("*.mar")) if (home / "corelang").exists() else []
        if not found:
            raise Unavailable(f"no compiled MAL language under {home}/corelang (set FAL_MAL_MAR to a .mar archive)")
        mar_path = found[-1]
    if not mar_path.exists():
        raise Unavailable(f"MAL language archive {mar_path} does not exist")
    return py, mar_path


def available() -> str | None:
    try:
        locate()
        return None
    except Unavailable as exc:
        return str(exc)


def run(request: dict[str, Any], *, timeout: float = 300) -> dict[str, Any]:
    """Run one worker command in the isolated venv and return its JSON response (raises on a worker-level error)."""
    py, _ = locate()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(request, fh)
        req_path = fh.name
    try:
        proc = subprocess.run([str(py), str(WORKER), req_path], capture_output=True, text=True, timeout=timeout)
    finally:
        os.unlink(req_path)
    if not proc.stdout.strip():
        raise Unavailable(f"MAL worker produced no output (exit {proc.returncode}): {proc.stderr[-500:]}")
    resp = json.loads(proc.stdout)
    if not resp.get("ok"):
        raise RuntimeError(f"MAL worker error: {resp.get('error')}\n{resp.get('traceback', '')}")
    return resp


def versions(mar: str | Path | None = None) -> dict[str, Any]:
    _, default_mar = locate()
    return run({"cmd": "versions", "lang": str(mar or default_mar)}, timeout=120)


def describe(model: dict[str, Any] | str, *, defenses: list[str] | None = None, mar: str | Path | None = None) -> dict[str, Any]:
    """Compile/load the model against the language and return the attack graph (assets, associations, nodes)."""
    _, default_mar = locate()
    return run({"cmd": "describe", "lang": str(mar or default_mar), "model": model, "defenses": defenses or []})["graph"]


def simulate(model: dict[str, Any] | str, entry_points: list[str], *, goal: str | None = None,
             actions: list[list[str]] | None = None, defenses: list[str] | None = None,
             mar: str | Path | None = None, timeout: float = 300) -> dict[str, Any]:
    """Run a deterministic native simulation; with no `actions`, greedily traverse the reachable surface."""
    _, default_mar = locate()
    req = {"cmd": "simulate", "lang": str(mar or default_mar), "model": model, "entry_points": entry_points,
           "defenses": defenses or []}
    if goal is not None:
        req["goal"] = goal
    if actions is not None:
        req["actions"] = actions
    return run(req, timeout=timeout)
