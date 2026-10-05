"""D5 evidence: CAGE Challenge 4 official baseline and a paired comparison on the platform path.

Records, offline-readable:
  * toolchain     — the fixed CAGE 4 (CybORG 4.0) version, git revision, scenario, scripted agent classes and the pinned
                    core package versions (traceable, re-runnable);
  * native_baseline — the official Scenario4 scripted baseline (blue=Sleep, green=EnterpriseGreen auto, red=FiniteStateRed):
                    per world step the joint actions, per-team rewards, active counts and termination — the native rounds;
  * platform_metrics — the platform's own projection of the same run (task effect, business survival, cost, time),
                    kept separate from the native CAGE scores; incomparable items are named, not merged;
  * paired_comparison — dev vs holdout seeds, mean/stdev of the defender's reward (uncertainty reported), all runs kept;
  * reproducibility — the same seed re-run reproduces the native totals;
  * cross_check   — MAL / CAGE / the local service probe (D4), each in its own semantic scope, with what is and is not comparable;
  * conditional   — the full RL-agent baselines (torch / ray) are NOT installed here; reported as a conditional item, not claimed.

If the CAGE toolchain is not installed the whole deliverable is recorded BLOCKED with the reason (never a fake score).
Run: scripts/in-vm.sh 'export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/formal-agent-lab; export FAL_CAGE_HOME=$HOME/.venvs/fal-cage; cd <repo>; uv run --no-sync python scripts/d5_cage_evidence.py'
Writes $FAL_EVIDENCE_DIR/d5-cage.json (default docs/execution/evidence/phase3).
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

from evidence_io import write as write_evidence
from formal_lab_env_cage import bridge

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3") / "d5-cage.json"

STEPS = 50           # a small sample for engineering acceptance; the official length is 500
DEV_SEEDS = [1, 2, 3, 4]
HOLDOUT_SEEDS = [101, 102]


def _defender_reward(run: dict) -> float:
    return run["team_reward_totals"].get("Blue", 0.0)


def _platform_metrics(run: dict) -> dict:
    """The platform's projection of one native run, in platform terms (kept apart from the native scores)."""
    steps = run["steps_run"]
    blue = run["agent_counts"].get("blue", 0)
    return {
        "seed": run["seed"], "world_steps": steps, "terminated_at": run["terminated_at"],
        "task_effect_defender_reward": _defender_reward(run),
        "business_survival_blue_agents": blue,  # blue defenders still present (the service surviving)
        "cost_model_fees": 0.0,  # scripted agents: no model calls
        "rejections": None, "unknowns": None, "model_deviation": None,  # not applicable to the native scripted baseline
    }


def main() -> int:
    reason = bridge.available()
    if reason is not None:
        ev = {"deliverable": "phase3B-D5", "status": "BLOCKED", "reason": reason,
              "note": "install CybORG 4.0 in ~/.venvs/fal-cage (see docs/local-development.md); the deliverable is not "
                      "claimed until the toolchain is present"}
        _write(ev)
        print(f"  BLOCKED: {reason}")
        return 0

    versions = bridge.versions()
    t0 = time.time()
    dev = bridge.baseline(steps=STEPS, seeds=DEV_SEEDS)
    holdout = bridge.baseline(steps=STEPS, seeds=HOLDOUT_SEEDS)
    # reproducibility: the same seed re-run
    rerun = bridge.baseline(steps=STEPS, seeds=[DEV_SEEDS[0]])
    wall = round(time.time() - t0, 2)

    first = dev["runs"][0]
    dev_rewards = [_defender_reward(r) for r in dev["runs"]]
    hold_rewards = [_defender_reward(r) for r in holdout["runs"]]
    repro_match = rerun["runs"][0]["team_reward_totals"] == first["team_reward_totals"]
    platform = [_platform_metrics(r) for r in dev["runs"] + holdout["runs"]]
    # the platform projection leaves what does not apply to a scripted native run unset, and carries no native totals
    separate = all(m["rejections"] is None and m["unknowns"] is None and m["model_deviation"] is None
                   and "team_reward_totals" not in m for m in platform)
    cross = _cross_check(dev_rewards)

    ev = {
        "deliverable": "phase3B-D5",
        "status": "OK",
        "toolchain": {
            "cage_version": versions["cyborg_version"], "scenario": versions["scenario"],
            "cage_src_revision": versions.get("cage_src_revision"), "agents": versions["agents"],
            "packages": versions["packages"], "isolated_venv": "~/.venvs/fal-cage (typed subprocess, D-023 pattern)",
            "not_installed": "torch / ray[rllib] / tensorboard / torch_geometric — needed only for RL-trained agents",
        },
        "native_baseline": {
            "requested_steps": STEPS, "official_episode_length": 500,
            "example_run": {"seed": first["seed"], "steps_run": first["steps_run"],
                            "terminated_at": first["terminated_at"], "agent_counts": first["agent_counts"],
                            "team_reward_totals": first["team_reward_totals"],
                            "first_steps": first["per_step"][:3],
                            "reward_steps": [s for s in first["per_step"]
                                             if any(v for v in s["team_rewards"].values())][:5]},
            "one_world_step_advances_once": [s["world_step"] for s in first["per_step"]]
            == list(range(1, first["steps_run"] + 1)),
            "joint_actions_per_step": "every internal scripted agent acts in one native world step",
            "auto_participants": "green agents (EnterpriseGreenAgent) act automatically",
        },
        "platform_metrics": {
            "dev": platform[:len(dev["runs"])],
            "holdout": platform[len(dev["runs"]):],
            "kept_separate_from_native_scores": separate,
            "incomparable_items": [
                "CAGE per-team reward is on CybORG's own scale; it is not the platform's reachability verdict or the "
                "order service's success rate — magnitudes are not comparable across the three",
                "the native scripted baseline has no admission gate, so rejections / unknowns / model-deviation do not "
                "apply to it (they belong to the broker-gated platform runs of D2–D4)",
            ],
        },
        "paired_comparison": {
            "dev_seeds": DEV_SEEDS, "holdout_seeds": HOLDOUT_SEEDS,
            "dev_defender_reward": {"mean": round(statistics.mean(dev_rewards), 3),
                                    "stdev": round(statistics.stdev(dev_rewards), 3) if len(dev_rewards) > 1 else 0.0,
                                    "values": dev_rewards},
            "holdout_defender_reward": {"mean": round(statistics.mean(hold_rewards), 3),
                                        "stdev": round(statistics.stdev(hold_rewards), 3) if len(hold_rewards) > 1
                                        else 0.0, "values": hold_rewards},
            "all_runs_kept": len(dev["runs"]) + len(holdout["runs"]),
            "uncertainty_note": "a small engineering-acceptance sample; the reward mean/stdev are reported with the "
                                "sample size, not presented as a converged result",
        },
        "reproducibility": {"seed": DEV_SEEDS[0], "same_seed_reproduces_totals": repro_match, "wall_seconds": wall},
        "lab_policy": "the CAGE run is a pure simulation ablation inside CybORG; no real network — the LabPolicy "
                      "boundary is preserved (the experiment never leaves the simulator)",
        "cross_check": {
            "scopes": {
                "MAL": "deterministic reachability of a target attack step (boolean, model-internal)",
                "CAGE": "per-team reward and compromise dynamics over the CybORG enterprise simulation (native scores)",
                "local_probe_D4": "business success rate and service state on the real order service (observed)",
            },
            "consistent_direction": "in each scope an unmitigated red presence worsens the defender's objective — MAL: "
                                    "the target becomes reachable (property false); CAGE: Blue reward is negative under "
                                    "red activity; D4: the privileged action is prevented only by the broker — but the "
                                    "magnitudes are on different scales and are not merged",
            "comparable": False,
            "observed": cross,
        },
        "conditional_items": [
            {"item": "RL-trained agent baselines (e.g. Masked PPO) and the EnterpriseMAE/ray wrapper",
             "status": "NOT_RUN", "reason": "torch / ray[rllib] are not installed in this environment (disk / weight); "
             "the scripted official baseline is what is delivered here, RL baselines remain a conditional item"},
        ],
        "conclusion": {
            "official_baseline_ran": bool(versions.get("cyborg_version"))
            and all(r["steps_run"] > 0 for r in dev["runs"] + holdout["runs"]),
            "native_and_platform_kept_separate": separate,
            "reproducible": repro_match,
            "cross_checked_within_scopes": all(cross.values()),
            "traceable": bool(versions.get("cage_src_revision")),
        },
    }
    _write(ev)
    print(f"  CAGE {versions['cyborg_version']} {versions['scenario']} rev {(versions.get('cage_src_revision') or '')[:12]}")
    print(f"  dev defender reward mean={ev['paired_comparison']['dev_defender_reward']['mean']} "
          f"stdev={ev['paired_comparison']['dev_defender_reward']['stdev']} | "
          f"holdout mean={ev['paired_comparison']['holdout_defender_reward']['mean']}")
    print(f"  reproducible={repro_match} | runs kept={ev['paired_comparison']['all_runs_kept']} | wall={wall}s")
    return 0


def _cross_check(dev_rewards: list[float]) -> dict[str, bool]:
    """The direction in each scope, from its own evidence in this directory (D1, D4) and this run (CAGE)."""
    def concl(name: str) -> dict:
        p = OUT.parent / name
        try:
            return json.loads(p.read_text()).get("conclusion") or {}
        except (OSError, json.JSONDecodeError):
            return {}

    return {"MAL_target_reachable_three_engines": concl("d1-mal.json").get("three_engines_agree_reachable") is True,
            "D4_privileged_action_only_via_broker": concl("d4-service-lab.json").get("contract_action_only_via_broker")
            is True,
            "CAGE_blue_reward_negative_under_red": bool(dev_rewards) and statistics.mean(dev_rewards) < 0}


def _write(ev: dict) -> None:
    write_evidence(OUT, ev)  # sets conclusion.offline_readable from reading the written file back
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
