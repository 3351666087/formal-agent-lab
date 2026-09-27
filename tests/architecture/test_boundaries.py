"""Module-boundary checks (P1-010 / P1-012 / P1-128), computed from the actual import statements.

- Every workspace package may import only the packages it is allowed to depend on (dependency direction).
- The core (contracts, model-core, runtime, platform-api, orchestrator, sdk) never imports a plugin package or
  the scheduling example: plugins are reached only through the entry-point registry.
- The main path only drives the neutral simulator: no subprocess / shell / network-execution helpers in
  environment, strategies or runtime code, and no action type outside the model's declared actions.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

PACKAGES = {
    "formal_lab_contracts": "packages/contracts/src/formal_lab_contracts",
    "formal_lab_model": "packages/model-core/src/formal_lab_model",
    "formal_lab_solver_z3": "packages/solver-adapters/z3/src/formal_lab_solver_z3",
    "formal_lab_env": "packages/neutral-environment/src/formal_lab_env",
    "formal_lab_strategies": "packages/strategies/src/formal_lab_strategies",
    "formal_lab_runtime": "packages/runtime/src/formal_lab_runtime",
    "formal_lab_eval": "packages/evaluation/src/formal_lab_eval",
    "formal_lab_api": "packages/platform-api/src/formal_lab_api",
    "formal_lab_orchestrator": "packages/orchestrator/src/formal_lab_orchestrator",
    "formal_lab_sdk": "packages/sdk/src/formal_lab_sdk",
    "formal_lab_example_scheduling": "examples/neutral-scheduling/src/formal_lab_example_scheduling",
    "fal_example_external_plugin": "examples/external-plugin/src/fal_example_external_plugin",
    "formal_lab_example_warehouse": "examples/warehouse-allocation/src/formal_lab_example_warehouse",
}

# allowed internal imports (dependency direction); anything not listed is a violation
ALLOWED: dict[str, set[str]] = {
    "formal_lab_contracts": set(),
    "formal_lab_model": {"formal_lab_contracts"},
    "formal_lab_solver_z3": {"formal_lab_contracts", "formal_lab_model"},
    "formal_lab_env": {"formal_lab_contracts", "formal_lab_model"},
    "formal_lab_strategies": {"formal_lab_contracts", "formal_lab_model"},
    "formal_lab_runtime": {"formal_lab_contracts", "formal_lab_model"},
    "formal_lab_eval": {"formal_lab_contracts", "formal_lab_runtime", "formal_lab_strategies", "formal_lab_sdk"},
    "formal_lab_api": {"formal_lab_contracts", "formal_lab_model", "formal_lab_runtime", "formal_lab_eval"},
    "formal_lab_orchestrator": {"formal_lab_contracts", "formal_lab_api"},
    # model-core via the optional [offline] extra; runtime only lazily, for `fal query replay --offline` (needs the
    # engine and a verifier plugin installed)
    "formal_lab_sdk": {"formal_lab_contracts", "formal_lab_model", "formal_lab_runtime"},
    # the example is a plugin package: it may use the engines it declares in its pyproject
    "formal_lab_example_scheduling": {"formal_lab_contracts", "formal_lab_model", "formal_lab_eval",
                                      "formal_lab_runtime", "formal_lab_solver_z3", "formal_lab_env",
                                      "formal_lab_strategies"},
    "fal_example_external_plugin": {"formal_lab_sdk"},
    # the second semantic profile: its own driver/strategies; only contracts + the model-agnostic belief helper
    "formal_lab_example_warehouse": {"formal_lab_contracts", "formal_lab_model"},
}
# demo tooling inside the API package that seeds the example project (not on any request/run path)
EXEMPT_FILES = {"packages/platform-api/src/formal_lab_api/seed.py"}
PLUGIN_PACKAGES = {"formal_lab_solver_z3", "formal_lab_env", "formal_lab_strategies",
                   "formal_lab_example_scheduling", "fal_example_external_plugin", "formal_lab_example_warehouse"}
CORE = {"formal_lab_contracts", "formal_lab_model", "formal_lab_runtime", "formal_lab_api",
        "formal_lab_orchestrator", "formal_lab_sdk"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


def _files(pkg: str) -> list[Path]:
    return sorted((ROOT / PACKAGES[pkg]).rglob("*.py"))


@pytest.mark.parametrize("pkg", sorted(PACKAGES))
def test_dependency_direction(pkg):
    violations = []
    for f in _files(pkg):
        rel = str(f.relative_to(ROOT))
        if rel in EXEMPT_FILES:
            continue
        for mod in _imports(f) & set(PACKAGES):
            if mod != pkg and mod not in ALLOWED[pkg]:
                violations.append(f"{rel} imports {mod}")
    assert not violations, "\n".join(violations)


def test_core_is_plugin_agnostic():
    """Core packages reach plugins only via the registry (entry points), never by import or by plugin id."""
    offenders = []
    for pkg in CORE:
        for f in _files(pkg):
            rel = str(f.relative_to(ROOT))
            if rel in EXEMPT_FILES:
                continue
            text = f.read_text()
            for mod in _imports(f) & PLUGIN_PACKAGES:
                offenders.append(f"{rel} imports plugin package {mod}")
            if "formal-lab.example." in text or "neutral-scheduling" in text:
                offenders.append(f"{rel} mentions the scheduling example")
            if "warehouse" in text.lower():  # P2-012: the kernel never needs to know a scenario / profile name
                offenders.append(f"{rel} mentions the warehouse example")
    assert not offenders, "\n".join(offenders)


FORBIDDEN_CALLS = {"subprocess", "os.system", "os.popen", "pty", "shlex", "socket", "paramiko", "pexpect"}


@pytest.mark.parametrize("pkg", ["formal_lab_env", "formal_lab_strategies", "formal_lab_runtime",
                                 "formal_lab_solver_z3", "formal_lab_model", "formal_lab_example_scheduling",
                                 "formal_lab_example_warehouse"])
def test_main_path_has_no_external_executors(pkg):
    """P1-128: environment, strategies and the step engine cannot execute commands or reach external targets;
    the only network use on the main path is the LLM client (httpx) inside formal_lab_strategies."""
    offenders = []
    for f in _files(pkg):
        imports = _imports(f)
        rel = str(f.relative_to(ROOT))
        for bad in FORBIDDEN_CALLS:
            if bad.split(".")[0] in imports and (bad in f.read_text() or "." not in bad):
                offenders.append(f"{rel}: {bad}")
        if "httpx" in imports and not rel.endswith("formal_lab_strategies/model_clients.py"):
            offenders.append(f"{rel}: network client outside the model client")
    allowed_git = "packages/runtime/src/formal_lab_runtime/manifest.py"  # reads `git rev-parse` for provenance only
    offenders = [o for o in offenders if not o.startswith(allowed_git)]
    assert not offenders, "\n".join(offenders)


def test_actions_are_limited_to_model_declared_types():
    """The environment rejects anything that is not a declared ground action (no free-form commands)."""
    from formal_lab_contracts import ActionProposal
    from formal_lab_env.ir_world import create
    from formal_lab_example_scheduling.scenarios import model_package, scenario

    pkg = model_package()
    sc = scenario("normal", pkg)

    class Svc:
        def pinned_model(self):
            return pkg

    env = create(sc.environment.config, Svc())
    env.reset(sc, pkg, run_id="r", seed=0)
    bogus = ActionProposal(proposal_id="p", run_id="r", step_id="r:s1", step=1, actor_id="dispatcher",
                           action={"action_type": "shell", "params": {"cmd": "rm -rf /"}}, based_on_revision=0,
                           source={"kind": "EXTERNAL", "strategy": {"plugin_id": "x", "version": "1.0.0"}})
    out = env.step(bogus, operation_id="r:s1:apply")
    assert out.status == "REJECTED" and out.effect_applied is False and "INVALID_ACTION" in out.result["reason"]
