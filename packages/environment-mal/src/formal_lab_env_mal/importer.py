"""Import a MAL model or a pinned scenario pack into a platform ModelPackage (phase 3B, D1).

This is the one place that joins the two halves of the MAL integration: the bridge to the isolated toolchain
(`formal_lab_env_mal.bridge`, this package) and the domain frontend that lowers an attack graph to the deterministic
IR (`formal_lab_domain_mal.frontend`). It runs the native simulator so the frontend can use the real reachable set as
its oracle, and preserves the model, language version and full attack graph in the package. Raises
`bridge.Unavailable` when the toolchain is not installed, so callers can record BLOCKED rather than fail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import bridge


def import_model(model: dict[str, Any] | str, entry_points: list[str], goal: str, *, package_id: str,
                 version: int = 1, defenses: list[str] | None = None,
                 language: dict[str, Any] | None = None, timeout: float = 300) -> tuple[Any, dict[str, Any]]:
    """Compile/load `model` against the language, run the native simulator from `entry_points`, and lower the goal
    subset to a ModelPackage. Returns (package, native_run)."""
    from formal_lab_domain_mal.frontend import package_from_graph

    graph = bridge.describe(model, defenses=defenses)
    name = model.get("name") if isinstance(model, dict) else Path(str(model)).stem
    graph.setdefault("model_name", name or package_id)
    run = bridge.simulate(model, entry_points, goal=goal, defenses=defenses, timeout=timeout)
    pkg = package_from_graph(graph, entry_points, goal, package_id=package_id, version=version,
                             reachable=run["compromised"],
                             model=model if isinstance(model, dict) else {"ref": str(model), "name": name},
                             language=language)
    return pkg, run


def import_scenario(scenario: dict[str, Any] | str, *, package_id: str | None = None,
                    version: int = 1) -> tuple[Any, dict[str, Any]]:
    """Import a `formal-lab.mal.scenario/v1` pack (a dict or a path to one). The pack pins the language and toolchain
    versions and carries the model, entry points, goal and the LabPolicy / TargetSecurity / BusinessSLO."""
    scn = scenario if isinstance(scenario, dict) else json.loads(Path(scenario).read_text())
    m = scn["model"]
    model = {k: m[k] for k in ("name", "language", "language_version", "assets", "associations") if k in m}
    language = {"name": scn["language"]["name"], "version": scn["language"]["version"]}
    return import_model(model, scn["entry_points"], scn["goal"],
                        package_id=package_id or scn["scenario_id"], version=version, language=language)
