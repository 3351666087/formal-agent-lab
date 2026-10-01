"""CAGE Challenge 4 worker (phase 3B, D5). Runs INSIDE the isolated `fal-cage` venv — CybORG 4.0 + its core
simulator dependencies only (no torch / ray / tensorboard: the official *scripted* baseline needs none of them). The
platform side (`formal_lab_env_cage.bridge`) invokes it as a subprocess and exchanges one JSON request / one JSON
response, so CybORG's heavy, conflicting dependencies never enter the frozen platform environment (the D-023 pattern).

Commands (JSON on argv[1] or stdin; JSON response on stdout):
  versions                          -> CybORG version, scenario, agent classes, key package versions
  baseline {seed, steps, episodes}  -> the official Scenario4 baseline with scripted agents (blue=Sleep,
                                       green=EnterpriseGreen auto, red=FiniteStateRed): per-step joint actions,
                                       per-team rewards, active counts and termination; per-episode native totals.

One `cyborg.step()` advances exactly one native world step, in which every internal scripted agent acts (joint
actions). Deterministic in the seed.
"""

from __future__ import annotations

import collections
import importlib.metadata as _md
import json
import os
import sys
from pathlib import Path
from typing import Any

SCENARIO = "Scenario4"


def _ensure_path() -> None:
    """CybORG is installed editable; its finder is not always portable across working directories, so put the
    checkout on sys.path directly (the checkout is the parent of the CybORG package)."""
    src = os.environ.get("FAL_CAGE_SRC") or str(Path.home() / "cage-src")
    if src and src not in sys.path and (Path(src) / "CybORG").exists():
        sys.path.insert(0, src)


def _imports():
    _ensure_path()
    from CybORG import CYBORG_VERSION, CybORG
    from CybORG.Agents import EnterpriseGreenAgent, FiniteStateRedAgent, SleepAgent
    from CybORG.Simulator.Scenarios import EnterpriseScenarioGenerator

    return (CybORG, CYBORG_VERSION, SleepAgent, EnterpriseGreenAgent, FiniteStateRedAgent,
            EnterpriseScenarioGenerator)


def _versions(req: dict[str, Any]) -> dict[str, Any]:
    _, ver, *_ = _imports()
    pkgs = {}
    for p in ("numpy", "networkx", "gymnasium", "pettingzoo", "PyYAML"):
        try:
            pkgs[p] = _md.version(p)
        except Exception:
            pkgs[p] = None
    return {"ok": True, "cyborg_version": ver, "scenario": SCENARIO, "python": sys.version.split()[0],
            "agents": {"blue": "SleepAgent", "green": "EnterpriseGreenAgent", "red": "FiniteStateRedAgent"},
            "packages": pkgs}


def _team(agent: str) -> str:
    return agent.split("_")[0]


def _episode(cyborg, steps: int) -> dict[str, Any]:
    per_step = []
    team_reward_totals: dict[str, float] = collections.defaultdict(float)
    terminated_at = None
    for j in range(steps):
        cyborg.step()  # one native world step; all internal scripted agents act (joint actions)
        active = cyborg.active_agents
        teams = collections.Counter(_team(a) for a in active)
        rewards = cyborg.get_rewards()  # {team: {agent: reward}}
        team_rewards = {t: round(sum(v.values()), 3) for t, v in rewards.items()}
        for t, r in team_rewards.items():
            team_reward_totals[t] += r
        done = bool(cyborg.environment_controller.done)
        # a sample joint action (one per team) for the record
        sample = {}
        for t in ("blue", "red"):
            ag = next((a for a in active if a.startswith(t)), None)
            if ag is not None:
                sample[ag] = str(cyborg.get_last_action(ag))[:80]
        per_step.append({"world_step": j + 1, "active": dict(teams), "team_rewards": team_rewards,
                         "sample_joint_action": sample, "done": done})
        if done:
            terminated_at = j + 1
            break
    return {"steps_run": len(per_step), "terminated_at": terminated_at,
            "team_reward_totals": {t: round(v, 3) for t, v in team_reward_totals.items()},
            "per_step": per_step}


def _baseline(req: dict[str, Any]) -> dict[str, Any]:
    (CybORG, ver, Sleep, Green, Red, ESG) = _imports()
    steps = int(req.get("steps", 30))
    episodes = int(req.get("episodes", 1))
    seeds = req.get("seeds") or [int(req.get("seed", 0))]
    runs = []
    for seed in seeds:
        for ep in range(episodes):
            sg = ESG(blue_agent_class=Sleep, green_agent_class=Green, red_agent_class=Red, steps=steps)
            cyborg = CybORG(sg, "sim", seed=seed)
            cyborg.reset(seed=seed)
            agents0 = cyborg.active_agents
            teams0 = collections.Counter(_team(a) for a in agents0)
            episode = _episode(cyborg, steps)
            episode.update({"seed": seed, "episode": ep, "agent_counts": dict(teams0)})
            runs.append(episode)
    return {"ok": True, "cyborg_version": ver, "scenario": SCENARIO, "requested_steps": steps,
            "episodes": episodes, "seeds": seeds, "runs": runs}


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
        elif cmd == "baseline":
            resp = _baseline(req)
        else:
            resp = {"ok": False, "error": f"unknown cmd {cmd!r}"}
    except Exception as exc:
        import traceback

        resp = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-2000:]}
    sys.stdout.write(json.dumps(resp))
    return 0 if resp.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
