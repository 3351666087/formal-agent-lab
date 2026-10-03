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

Phase 4B (B2) adds:
  describe                          -> the Scenario4 host universe (subnets x router / user / server hosts from the
                                       generator's MIN/MAX constants), blue action names, official agent classes
  native {seed, steps, red, blue_native, actions}
                                    -> the *direct* path: CybORG driven here with `parallel_step`, external blue
                                       actions per world step as given (none = the native blue class acts); the same
                                       per-step record the session writes, for trajectory comparison
  serve                             -> a session over JSON lines on stdin/stdout (protocol formal-lab/cage4-session@1):
                                       hello, reset, observe, step, report, digest, truth, close — one `step` request
                                       is one `parallel_step`, i.e. exactly one native world step.

Blue actions are built only from the declared names below with a hostname the agent's own action space allows; any
other request is answered as an error, never executed.
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


# ---------------------------------------------------------------------------------------------------- phase 4B (B2)

PROTOCOL = "formal-lab/cage4-session@1"
BLUE_ACTIONS = ("Sleep", "Monitor", "Analyse", "Remove", "Restore", "DeployDecoy")  # declared; block/allow not mapped
HOSTED = ("Analyse", "Remove", "Restore", "DeployDecoy")


def _agent_classes():
    _ensure_path()
    from CybORG import Agents

    return {
        "red": {n: getattr(Agents, n) for n in ("FiniteStateRedAgent", "DiscoveryFSRed", "VerboseFSRed",
                                                 "RandomSelectRedAgent")},
        "blue": {n: getattr(Agents, n) for n in ("SleepAgent", "MonitorAgent", "cc4BlueRandomAgent")},
        "green": {"EnterpriseGreenAgent": Agents.EnterpriseGreenAgent},
    }


def _describe(req: dict[str, Any]) -> dict[str, Any]:
    _ensure_path()
    from CybORG.Simulator.Scenarios import EnterpriseScenarioGenerator as ESG
    from CybORG.Simulator.Scenarios.EnterpriseScenarioGenerator import SUBNET

    subnets = [s.value for s in SUBNET if s is not SUBNET.INTERNET]
    hosts = []
    for sub in subnets:
        hosts.append(f"{sub}_router")
        hosts += [f"{sub}_user_host_{i}" for i in range(ESG.MAX_USER_HOSTS)]
        hosts += [f"{sub}_server_host_{i}" for i in range(ESG.MAX_SERVER_HOSTS)]
    classes = _agent_classes()
    return {"ok": True, "scenario": SCENARIO, "subnets": subnets, "hosts": hosts,
            "limits": {"user_hosts": [ESG.MIN_USER_HOSTS, ESG.MAX_USER_HOSTS],
                       "server_hosts": [ESG.MIN_SERVER_HOSTS, ESG.MAX_SERVER_HOSTS]},
            "blue_actions": list(BLUE_ACTIONS), "agent_classes": {k: sorted(v) for k, v in classes.items()}}


class Session:
    """One CybORG episode driven from outside: `step` = one `parallel_step` = one native world step."""

    def __init__(self) -> None:
        self.cyborg = None
        self.args: dict[str, Any] = {}
        self.controlled: list[str] = []
        self.applied: dict[str, dict[str, Any]] = {}  # operation id -> step answer (idempotent steps)
        self.log: list[dict[str, Any]] = []  # committed world steps (the rebuild log)
        self.last: dict[str, Any] | None = None
        self.green_totals = collections.Counter()
        self.timeline: list[dict[str, Any]] = []  # referee record per world step (never part of an observation)

    # ------------------------------------------------------------------ setup
    def reset(self, args: dict[str, Any]) -> dict[str, Any]:
        (CybORG, ver, *_r, ESG) = _imports()
        classes = _agent_classes()
        red = classes["red"][args.get("red", "FiniteStateRedAgent")]
        blue = classes["blue"][args.get("blue_native", "SleepAgent")]
        green = classes["green"]["EnterpriseGreenAgent"]
        sg = ESG(blue_agent_class=blue, green_agent_class=green, red_agent_class=red, steps=int(args["steps"]))
        self.cyborg = CybORG(sg, "sim", seed=int(args["seed"]))
        self.cyborg.reset(seed=int(args["seed"]))
        self.args = dict(args)
        blues = sorted(a for a in self.cyborg.agents if a.startswith("blue"))
        self.controlled = [a for a in (args.get("controlled") or blues) if a in blues]
        self.applied, self.log, self.last = {}, [], None
        self.green_totals = collections.Counter()
        self.timeline = []
        return {"world_step": 0, "agents": {t: sum(1 for a in self.cyborg.agents if a.startswith(t))
                                            for t in ("blue", "red", "green")},
                "controlled": self.controlled, "cyborg_version": ver, "digest": self.digest()}

    @property
    def ec(self):
        return self.cyborg.environment_controller

    def world_step(self) -> int:
        return int(self.ec.step_count)

    # ------------------------------------------------------------------ actions
    def allowed_hosts(self, agent: str) -> list[str]:
        space = self.cyborg.get_action_space(agent)
        return sorted(h for h, ok in space.get("hostname", {}).items() if ok)

    def build(self, agent: str, spec: dict[str, Any]):
        _ensure_path()
        import CybORG.Simulator.Actions as A

        name = spec.get("name")
        if name not in BLUE_ACTIONS:
            raise ValueError(f"{name!r} is not a declared blue action {BLUE_ACTIONS}")
        if name == "Sleep":
            return A.Sleep()
        if name == "Monitor":
            return A.Monitor(session=0, agent=agent)
        host = spec.get("hostname")
        if host not in self.allowed_hosts(agent):
            raise ValueError(f"{agent} may not act on host {host!r} (not in its action space)")
        return getattr(A, name)(session=0, agent=agent, hostname=host)

    def busy(self, agent: str) -> bool:
        """An action of this agent is still in progress: CybORG will not start a new one at the next step."""
        return self.ec.actions_in_progress.get(agent) is not None

    # ------------------------------------------------------------------ the world step
    def step(self, args: dict[str, Any]) -> dict[str, Any]:
        op = args["operation_id"]
        if op in self.applied:  # the same operation is answered, never applied twice
            return {**self.applied[op], "replayed": True}
        specs = args.get("actions") or {}
        unknown = sorted(set(specs) - set(self.controlled))
        if unknown:
            raise ValueError(f"not platform-controlled agents: {unknown}")
        actions, started = {}, {}
        for agent, spec in specs.items():
            actions[agent] = self.build(agent, spec)
            started[agent] = not self.busy(agent)  # CybORG ignores a new action while one is still in progress
        self.cyborg.parallel_step(actions=actions)
        record = self.record(specs, started)
        answer = {"operation_id": op, "record": record, "digest": self.digest(), "replayed": False}
        self.applied[op] = answer
        self.log.append({"operation_id": op, "actions": specs})
        self.last = record
        return answer

    def record(self, specs: dict[str, Any], started: dict[str, bool]) -> dict[str, Any]:
        c = self.cyborg
        rewards = {t: round(sum(v.values()), 4) for t, v in c.get_rewards().items()}
        blue = {}
        for agent in sorted(a for a in c.agents if a.startswith("blue")):
            obs = c.get_observation(agent)
            blue[agent] = {"submitted": specs.get(agent), "started": started.get(agent),
                           "executed": str(c.get_last_action(agent)), "success": str(obs.get("success")),
                           "controlled": agent in self.controlled}
        red = {a: str(c.get_last_action(a)) for a in sorted(c.active_agents) if a.startswith("red")}
        green = collections.Counter()
        for a in c.active_agents:
            if not a.startswith("green"):
                continue
            act = str(c.get_last_action(a))
            if "Sleep" in act:
                continue
            ok = str(c.get_observation(a).get("success"))
            green[f"{'work' if 'LocalWork' in act else 'access' if 'AccessService' in act else 'other'}:{ok}"] += 1
        self.green_totals.update(green)
        self.timeline.append({"world_step": self.world_step(), "rewards": rewards, "green": dict(sorted(green.items())),
                              "red_foothold_hosts": self.footholds()})
        return {"world_step": self.world_step(), "phase": int(self.ec.state.mission_phase),
                "done": bool(self.ec.done), "rewards": rewards, "blue": blue, "red": red,
                "green": dict(sorted(green.items())), "red_footholds": len(self.footholds()),
                "red_foothold_hosts": self.footholds()}

    # ------------------------------------------------------------------ views
    def footholds(self) -> list[str]:
        """Referee only: hosts where a red agent holds a session (never part of a blue observation)."""
        hosts = set()
        for agent, sessions in self.ec.state.sessions.items():
            if agent.startswith("red"):
                for sess in sessions.values():
                    if sess.hostname:
                        hosts.add(sess.hostname)
        return sorted(hosts)

    def observe(self, agent: str) -> dict[str, Any]:
        """The blue agent's own native observation, summarised. At world step 0 CybORG lists the agent's inventory
        (its own sessions per host) — not alerts. Afterwards a host appears only when this agent's Monitor / Analyse
        reported something there: connections of processes ("connection") or files ("file"). Green traffic produces
        connections too, so an alert is evidence to act on, not the truth about red (that stays with the referee)."""
        obs = self.cyborg.get_observation(agent)
        hosts = {h: v for h, v in obs.items() if h not in ("success", "action", "message") and isinstance(v, dict) and v}
        kinds: dict[str, str] = {}
        if self.world_step() > 0:
            for h, v in hosts.items():
                if v.get("Files"):
                    kinds[h] = "file"
                elif any(p.get("Connections") for p in v.get("Processes", []) if isinstance(p, dict)):
                    kinds[h] = "connection"
                else:
                    kinds[h] = "other"
        last = self.cyborg.get_last_action(agent)
        return {"agent": agent, "world_step": self.world_step(), "phase": int(self.ec.state.mission_phase),
                "done": bool(self.ec.done), "allowed_hosts": self.allowed_hosts(agent), "alerts": sorted(kinds),
                "alert_kinds": dict(sorted(kinds.items())),
                "success": str(obs.get("success")), "last_action": str(last) if last is not None else None,
                "busy": self.busy(agent), "controlled": agent in self.controlled}

    def truth(self) -> dict[str, Any]:
        return {"world_step": self.world_step(), "done": bool(self.ec.done), "red_footholds": self.footholds(),
                "green_totals": dict(sorted(self.green_totals.items())), "timeline": self.timeline}

    def digest(self) -> str:
        """State + RNG digest: sessions per host and agent, mission phase, step, done, and both RNG states — equal
        digests after a rebuild mean the same world and the same random stream."""
        import hashlib

        state = self.ec.state
        sessions = sorted((agent, s.hostname or "", s.username or "", type(s).__name__)
                          for agent, ss in state.sessions.items() for s in ss.values())
        processes = sorted((h, len(host.processes)) for h, host in state.hosts.items())
        rng = [str(self.cyborg.np_random.bit_generator.state), str(self.ec.np_random.bit_generator.state)]
        body = json.dumps([self.world_step(), int(state.mission_phase), bool(self.ec.done), sessions, processes, rng])
        return hashlib.sha256(body.encode()).hexdigest()


def _native(req: dict[str, Any]) -> dict[str, Any]:
    """The direct path: the same Session code without the platform — one `parallel_step` per given action set."""
    s = Session()
    start = s.reset({k: req[k] for k in ("seed", "steps", "red", "blue_native", "controlled") if k in req})
    steps = []
    plan = req.get("actions") or []
    for t in range(int(req["steps"])):
        specs = plan[t] if t < len(plan) else {}
        steps.append(s.step({"operation_id": f"native-{t + 1}", "actions": specs})["record"]
                     | {"digest": s.digest()})
        if steps[-1]["done"]:
            break
    return {"ok": True, "start": start, "steps": steps, "truth": s.truth()}


def _serve() -> int:
    """JSON lines: {"id", "op", "args"} -> {"id", "ok", "result" | "error"}; exits on `close` or end of input."""
    session = Session()
    _, ver, *_ = _imports()
    ops = {
        "hello": lambda a: {"protocol": PROTOCOL, "pid": os.getpid(), "cyborg_version": ver, "scenario": SCENARIO,
                            "python": sys.version.split()[0], "batch_semantics": "cage4.parallel_step"},
        "reset": session.reset,
        "observe": lambda a: session.observe(a["agent"]),
        "step": session.step,
        "report": lambda a: session.last,
        "digest": lambda a: session.digest(),
        "truth": lambda a: session.truth(),
        "log": lambda a: session.log,
    }
    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        if req.get("op") == "close":
            sys.stdout.write(json.dumps({"id": req.get("id"), "ok": True, "result": None}) + "\n")
            sys.stdout.flush()
            return 0
        try:
            fn = ops[req["op"]]
            answer = {"id": req.get("id"), "ok": True, "result": fn(req.get("args") or {})}
        except Exception as exc:  # reported, never swallowed: the adapter decides what it means
            answer = {"id": req.get("id"), "ok": False,
                      "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}
        sys.stdout.write(json.dumps(answer, default=str) + "\n")
        sys.stdout.flush()
    return 0


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "serve":
        return _serve()
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
        elif cmd == "describe":
            resp = _describe(req)
        elif cmd == "native":
            resp = _native(req)
        else:
            resp = {"ok": False, "error": f"unknown cmd {cmd!r}"}
    except Exception as exc:
        import traceback

        resp = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-2000:]}
    sys.stdout.write(json.dumps(resp))
    return 0 if resp.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
