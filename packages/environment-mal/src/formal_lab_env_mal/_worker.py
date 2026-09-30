"""MAL toolchain worker (phase 3B, D1). Runs INSIDE the isolated `fal-mal` venv — stdlib + mal-toolbox +
mal-simulator only, no formal-lab packages. The platform side (formal_lab_env_mal.bridge) invokes it as a
subprocess and exchanges one JSON request / one JSON response, so the heavy, conflicting MAL dependencies never
enter the frozen platform environment (the pattern D-023 established for PRISM-games).

Request on argv[1] (a JSON file) or stdin; response JSON on stdout. Commands:
  versions                              -> tool + language versions and digests
  describe {lang, model}                -> assets, associations and the full attack graph (nodes, types, parents)
  simulate {lang, model, entry_points,  -> a deterministic run (ttc disabled, no Bernoulli draws): per-step the
            defenses?, actions?, goal?}    chosen steps, whether each was traversable, and the compromised set;
                                           with no `actions`, greedily traverses the whole reachable surface.
Everything is deterministic: TTCMode.DISABLED and the attack/defense Bernoulli draws are turned off, so a run is a
function of (language, model, entry points, defenses, action order) — the seed only labels the record.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as _md
import json
import sys
from typing import Any


def _load_language(path: str):
    from maltoolbox.language import LanguageGraph

    return LanguageGraph.from_mar_archive(path) if path.endswith(".mar") else LanguageGraph.from_mal_spec(path)


def _load_model(lang, spec: dict[str, Any] | str):
    """A model is either a saved YAML/JSON file path or an inline description
    {name, assets:[{type,name}], associations:[{asset, field, targets:[names]}]}."""
    from maltoolbox.model import Model

    if isinstance(spec, str):
        return Model.load_from_file(spec, lang)
    m = Model(spec.get("name", "model"), lang)
    by_name = {}
    for a in spec["assets"]:
        by_name[a["name"]] = m.add_asset(a["type"], a["name"])
    for assoc in spec.get("associations", []):
        by_name[assoc["asset"]].add_associated_assets(assoc["field"], {by_name[t] for t in assoc["targets"]})
    return m


def _node_json(n: Any) -> dict[str, Any]:
    return {
        "full_name": n.full_name,
        "asset": n.model_asset.name if getattr(n, "model_asset", None) else None,
        "step": n.name,
        "type": n.type,  # or | and | defense | exist | notExist
        "existence_status": bool(getattr(n, "existence_status", False)),
        "parents": sorted(p.full_name for p in n.parents),
        "children": sorted(c.full_name for c in n.children),
        "ttc": _ttc(n),
    }


def _ttc(n: Any) -> float | None:
    ttc = getattr(n, "ttc", None)
    if ttc is None:
        return None
    for attr in ("expected_value", "mean"):
        v = getattr(ttc, attr, None)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _assets(model) -> list[Any]:
    a = model.assets
    return list(a.values()) if hasattr(a, "values") else list(a)


def _asset_type(a: Any) -> str:
    t = getattr(a, "type", None)
    return t.name if hasattr(t, "name") else (str(t) if t is not None else "?")


def _graph(lang, model, lang_file: str, defenses: list[str]) -> dict[str, Any]:
    from maltoolbox.attackgraph import AttackGraph

    ag = AttackGraph(lang, model)
    nodes = list(ag.nodes.values()) if hasattr(ag.nodes, "values") else list(ag.nodes)
    out = [_node_json(n) for n in nodes]
    # ground truth for folding: auto-active / blocked at a bare reset
    baseline = _baseline(model, lang_file, defenses, [n.full_name for n in nodes])
    for j in out:
        j["auto"] = j["full_name"] in baseline["auto"]
        j["blocked"] = j["full_name"] in baseline["blocked"]
    return {"nodes": out, "assets": [{"name": a.name, "type": _asset_type(a)} for a in _assets(model)],
            "associations": _associations(model), "counts": _counts(nodes),
            "defenses_enabled": sorted(defenses)}


def _baseline(model, lang_file: str, defenses: list[str], names: list[str]) -> dict[str, list[str]]:
    """Which steps are true with no attacker action (existence steps, and the effect of enabled defenses): the fold
    oracle for lowering. Reset an attacker with no entry points and read every node's compromised / blocked flag."""
    from malsim.config.agent_settings import AttackerSettings
    from malsim.mal_simulator import MalSimulator, MalSimulatorSettings, TTCMode
    from malsim.scenario import Scenario

    settings = MalSimulatorSettings(ttc_mode=TTCMode.DISABLED, run_attack_step_bernoullis=False,
                                    run_defense_step_bernoullis=False, compromise_entrypoints_at_start=True)
    sc = Scenario(lang_file=lang_file, model=model,
                  agents=[AttackerSettings(name="_probe", entry_points=frozenset())], sim_settings=settings)
    sim = MalSimulator.from_scenario(sc)
    sim.reset()
    auto, blocked = [], []
    for fn in names:
        try:
            if sim.node_is_compromised(fn):
                auto.append(fn)
            if sim.node_is_blocked(fn):
                blocked.append(fn)
        except (LookupError, KeyError):
            continue
    return {"auto": auto, "blocked": blocked}


def _counts(nodes: list[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for n in nodes:
        out[n.type] = out.get(n.type, 0) + 1
    return out


def _associations(model) -> list[dict[str, Any]]:
    out = []
    for a in _assets(model):
        for field, targets in (a.associated_assets.items() if hasattr(a, "associated_assets") else []):
            out.append({"asset": a.name, "field": field, "targets": sorted(t.name for t in targets)})
    return out


def _simulate(req: dict[str, Any]) -> dict[str, Any]:
    from malsim.config.agent_settings import AttackerSettings
    from malsim.mal_simulator import MalSimulator, MalSimulatorSettings, TTCMode
    from malsim.scenario import Scenario
    from maltoolbox.attackgraph import AttackGraph

    lang = _load_language(req["lang"])
    model = _load_model(lang, req["model"])
    AttackGraph(lang, model)  # validates the model against the language
    entry = set(req["entry_points"])
    goal = req.get("goal")
    settings = MalSimulatorSettings(ttc_mode=TTCMode.DISABLED, run_attack_step_bernoullis=False,
                                    run_defense_step_bernoullis=False, compromise_entrypoints_at_start=True)
    agent = AttackerSettings(name="red", entry_points=entry, goals={goal} if goal else frozenset())
    sim = MalSimulator.from_scenario(Scenario(lang_file=req["lang"], model=model, agents=[agent],
                                              sim_settings=settings))
    sim.reset()
    for full in req.get("defenses", []):  # enable configured defenses before the attacker moves
        node = sim.get_node(full)
        if node is not None:
            sim.step({})  # defenses are model config here; recorded for the lowering, no defender agent needed
    steps = []
    compromised0 = sorted(n.full_name for n in sim.compromised_nodes)
    actions = req.get("actions")
    if actions is None:  # greedy: traverse the whole reachable surface until nothing new
        actions = []
        for _ in range(req.get("max_steps", 200)):
            surf = [n for n in sim.agent_states["red"].action_surface if not sim.node_is_compromised(n)]
            if not surf:
                break
            actions.append([n.full_name for n in surf])
            _apply(sim, surf, steps)
            if goal and sim.node_is_compromised(sim.get_node(goal)):
                break
    else:
        for chosen in actions:
            nodes = [sim.get_node(c) for c in chosen]
            _apply(sim, [n for n in nodes if n is not None], steps)
    compromised = sorted(n.full_name for n in sim.compromised_nodes)
    return {"ok": True, "entry_points": sorted(entry), "goal": goal,
            "goal_reached": bool(goal) and goal in compromised,
            "compromised_at_start": compromised0, "steps": steps,
            "compromised": compromised, "compromised_count": len(compromised)}


def _apply(sim, nodes, steps: list[dict[str, Any]]) -> None:
    performed = set(sim.compromised_nodes)
    chosen = [{"full_name": n.full_name, "traversable": sim.node_is_traversable(performed, n),
               "already": sim.node_is_compromised(n)} for n in nodes]
    sim.step({"red": nodes})
    for c, n in zip(chosen, nodes, strict=True):
        c["compromised_after"] = sim.node_is_compromised(n)
    steps.append({"chosen": chosen, "compromised_total": len(list(sim.compromised_nodes))})


def _versions(req: dict[str, Any]) -> dict[str, Any]:
    out = {"ok": True, "python": sys.version.split()[0],
           "mal_toolbox": _md.version("mal-toolbox"), "mal_simulator": _md.version("mal-simulator")}
    lang = req.get("lang")
    if lang:
        with open(lang, "rb") as fh:
            data = fh.read()
        out["language_file"] = lang
        out["language_sha256"] = hashlib.sha256(data).hexdigest()
        lg = _load_language(lang)
        out["language_assets"] = sorted(lg.assets) if hasattr(lg, "assets") else []
    return out


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        with open(argv[1]) as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    req = json.loads(raw)
    try:
        cmd = req["cmd"]
        if cmd == "versions":
            resp = _versions(req)
        elif cmd == "describe":
            lang = _load_language(req["lang"])
            resp = {"ok": True, "graph": _graph(lang, _load_model(lang, req["model"]), req["lang"],
                                                req.get("defenses", []))}
        elif cmd == "simulate":
            resp = _simulate(req)
        else:
            resp = {"ok": False, "error": f"unknown cmd {cmd!r}"}
    except Exception as exc:  # the bridge turns a non-ok response into a clear platform error
        import traceback

        resp = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-2000:]}
    sys.stdout.write(json.dumps(resp))
    return 0 if resp.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
