"""MAL model frontend (phase 3B, D1): a captured attack graph → a deterministic-finite IR ModelPackage.

The frontend is pure (no MAL toolchain): it consumes the attack-graph JSON that `formal_lab_env_mal.bridge.describe`
produces, lowers the goal-relevant subset to IR (see `lowering`), and preserves the raw model, the language version
and digest, and the full attack graph in the package's `org.mal-lang.attack-graph` extension — so a run keeps its
provenance and the native backend can be re-consulted. Registered as a MODEL_FRONTEND plugin whose source format is
`mal-attack-graph/v1` (source text = a JSON envelope {language, model, graph, entry_points, goal}).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from formal_lab_contracts import Extension, ModelPackage, ModelSource, PluginDescriptor
from formal_lab_contracts.errors import InvalidInput, Unsupported
from formal_lab_model import build_package

from .config import EXT_ATTACK_GRAPH
from .lowering import lower

FRONTEND_ID = "formal-lab.domain.mal.frontend"
SOURCE_FORMAT = "mal-attack-graph/v1"

DESCRIPTOR = PluginDescriptor(
    plugin_id=FRONTEND_ID, version="1.0.0", interface="MODEL_FRONTEND",
    capabilities=[{"id": "profile.deterministic_finite_v1"}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "additionalProperties": False},
    entrypoint="formal_lab_domain_mal.frontend:create_frontend",
    ui={"label": "MAL 攻击图（coreLang）", "category": "model_frontend",
        "description": "mal-attack-graph/v1 → 确定性有限 IR：攻击步骤可达性；保留原始 MAL 模型、语言版本与攻击图"},
    license="Apache-2.0", source="formal-lab-domain-mal")


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def package_from_graph(graph: dict[str, Any], entry_points: list[str], goal: str, *, package_id: str, version: int,
                       reachable: list[str] | None = None, model: dict[str, Any] | None = None,
                       language: dict[str, Any] | None = None) -> ModelPackage:
    """Lower a captured attack graph to a ModelPackage, preserving the MAL provenance in an extension."""
    reach = reachable if reachable is not None else entry_points
    ir, report = lower(graph, entry_points, goal, reach, name=package_id)
    language = language or {"name": graph.get("language", "coreLang"),
                            "version": graph.get("language_version", "unknown")}
    graph_digest = _digest(graph)
    source = ModelSource(
        format=SOURCE_FORMAT,
        text=json.dumps({"language": language, "model": model, "entry_points": entry_points, "goal": goal,
                         "graph_sha256": graph_digest}, ensure_ascii=False),
        origin=f"MAL {language.get('name')} {language.get('version')} attack graph (sha256 {graph_digest[:12]})")
    pkg = build_package(ir, package_id=package_id, version=version, source=source)
    ext = Extension(version="1.0.0", schema_id=f"{EXT_ATTACK_GRAPH}/v1", data={
        "language": language, "model": model, "entry_points": entry_points, "goal": goal,
        "graph_sha256": graph_digest, "graph": graph, "native_reachable": sorted(reach), "lowering": report})
    return pkg.model_copy(update={"extensions": {**pkg.extensions, EXT_ATTACK_GRAPH: ext}})


def attack_graph_of(pkg: ModelPackage) -> dict[str, Any]:
    """The preserved MAL attack graph + lowering report of a package built by this frontend."""
    ext = pkg.extensions.get(EXT_ATTACK_GRAPH)
    if ext is None:
        raise InvalidInput(f"{pkg.package_id}@{pkg.version} has no {EXT_ATTACK_GRAPH} extension")
    return ext.data


class MalFrontend:
    descriptor = DESCRIPTOR

    def compile(self, source: ModelSource, *, package_id: str, version: int) -> ModelPackage:
        if source.format != SOURCE_FORMAT:
            raise Unsupported(f"source format {source.format!r} is not {SOURCE_FORMAT}")
        if not source.text:
            raise InvalidInput("source.text (a mal-attack-graph/v1 JSON envelope) is required")
        env = json.loads(source.text)
        if "graph" not in env or "goal" not in env:
            raise InvalidInput("mal-attack-graph/v1 envelope needs `graph` and `goal`")
        return package_from_graph(env["graph"], env.get("entry_points", []), env["goal"],
                                  package_id=package_id, version=version, reachable=env.get("reachable"),
                                  model=env.get("model"), language=env.get("language"))


def create_frontend(config: dict[str, Any] | None = None, services: Any = None) -> MalFrontend:
    return MalFrontend()
