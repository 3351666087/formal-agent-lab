"""Bridge to the isolated CAGE Challenge 4 toolchain (phase 3B, D5).

CybORG 4.0 and its dependencies (gym/gymnasium, pettingzoo, pygame, numpy pins) conflict with the frozen platform
lock, so — like PRISM (D-023) and the MAL toolchain (D1) — CAGE lives in a separate virtual environment and is reached
through a typed subprocess (`_worker.py`), never imported here.

Locate it with:
    FAL_CAGE_HOME   a venv with bin/python and CybORG 4.0 installed (default ~/.venvs/fal-cage)
    FAL_CAGE_SRC    the cage-challenge-4 checkout (only needed to record its git revision; default ~/cage-src)

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
    """The CAGE toolchain is not installed / reachable; the reason explains how to provide it."""


def locate() -> Path:
    """Python of the fal-cage venv. Raises Unavailable with the fix if it is missing."""
    home = Path(os.environ.get("FAL_CAGE_HOME", Path.home() / ".venvs" / "fal-cage"))
    py = home / "bin" / "python"
    if not py.exists():
        raise Unavailable(f"CAGE venv not found at {home} (set FAL_CAGE_HOME to a venv with CybORG 4.0; see "
                          "docs/local-development.md)")
    return py


def available() -> str | None:
    try:
        locate()
        return None
    except Unavailable as exc:
        return str(exc)


def cage_src_revision() -> str | None:
    src = Path(os.environ.get("FAL_CAGE_SRC", Path.home() / "cage-src"))
    if not (src / ".git").exists():
        return None
    try:
        return subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except Exception:
        return None


def run(request: dict[str, Any], *, timeout: float = 900) -> dict[str, Any]:
    """Run one worker command in the isolated venv and return its JSON response (raises on a worker-level error)."""
    py = locate()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(request, fh)
        req_path = fh.name
    env = {**os.environ, "PYTHONWARNINGS": "ignore"}
    try:
        proc = subprocess.run([str(py), str(WORKER), req_path], capture_output=True, text=True, timeout=timeout,
                              env=env)
    finally:
        os.unlink(req_path)
    out = proc.stdout.strip()
    if not out:
        raise Unavailable(f"CAGE worker produced no output (exit {proc.returncode}): {proc.stderr[-500:]}")
    # the worker writes only the JSON response to stdout; tolerate leading gym warnings if any slipped through
    resp = json.loads(out[out.index("{"):]) if not out.startswith("{") else json.loads(out)
    if not resp.get("ok"):
        raise RuntimeError(f"CAGE worker error: {resp.get('error')}\n{resp.get('traceback', '')}")
    return resp


def versions() -> dict[str, Any]:
    resp = run({"cmd": "versions"}, timeout=180)
    resp["cage_src_revision"] = cage_src_revision()
    return resp


def baseline(*, steps: int = 30, episodes: int = 1, seed: int = 0, seeds: list[int] | None = None,
             timeout: float = 900) -> dict[str, Any]:
    """Run the official Scenario4 scripted baseline; with `seeds` runs each seed (paired evaluation)."""
    req: dict[str, Any] = {"cmd": "baseline", "steps": steps, "episodes": episodes}
    if seeds is not None:
        req["seeds"] = seeds
    else:
        req["seed"] = seed
    return run(req, timeout=timeout)


def describe(*, timeout: float = 180) -> dict[str, Any]:
    """Scenario4 host universe, declared blue actions and official agent classes (phase 4B, B2)."""
    return run({"cmd": "describe"}, timeout=timeout)


def native(*, seed: int, steps: int, red: str = "FiniteStateRedAgent", blue_native: str = "SleepAgent",
           controlled: list[str] | None = None, actions: list[dict[str, Any]] | None = None,
           timeout: float = 900) -> dict[str, Any]:
    """The direct path (phase 4B, B2): CybORG driven by the worker alone with the given blue actions per world step
    (an empty dict = the native blue class acts) — the reference a platform run is compared with."""
    req: dict[str, Any] = {"cmd": "native", "seed": seed, "steps": steps, "red": red, "blue_native": blue_native,
                           "actions": actions or []}
    if controlled is not None:
        req["controlled"] = controlled
    return run(req, timeout=timeout)
