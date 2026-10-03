"""Native direct path vs platform path, world step by world step (phase 4B, B2).

Both sides are the worker's own per-world-step records: the direct path (`bridge.native`: CybORG driven with
`parallel_step` by the worker alone) and the platform path (the adapter's `world_log`: the same record for each
world step a platform run committed). The comparison is computed, never asserted: for every world step it checks the
fields below and reports the first difference. `digest` covers CybORG's sessions per host, processes per host,
mission phase, step, `done` and both RNG states — equal digests mean the same world and the same random stream.
"""

from __future__ import annotations

from typing import Any

FIELDS = ("world_step", "phase", "done", "rewards", "red", "green", "red_footholds", "red_foothold_hosts",
          "digest")


def platform_actions(platform_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The blue actions a platform run submitted, per world step — to drive the direct path with the same sequence."""
    return [{a: b["submitted"] for a, b in st["blue"].items() if b.get("submitted") is not None}
            for st in platform_steps]


def compare(native_steps: list[dict[str, Any]], platform_steps: list[dict[str, Any]]) -> dict[str, Any]:
    rows, first = [], None
    for i in range(max(len(native_steps), len(platform_steps))):
        n = native_steps[i] if i < len(native_steps) else None
        p = platform_steps[i] if i < len(platform_steps) else None
        if n is None or p is None:
            diff = {"world_step": i + 1, "field": "presence", "native": n is not None, "platform": p is not None}
            rows.append({"world_step": i + 1, "equal": False, "differences": [diff]})
            first = first or diff
            continue
        diffs = [{"field": f, "native": n.get(f), "platform": p.get(f)} for f in FIELDS if n.get(f) != p.get(f)]
        for agent in sorted(set(n["blue"]) | set(p["blue"])):
            nb, pb = n["blue"].get(agent, {}), p["blue"].get(agent, {})
            for key in ("executed", "success"):
                if nb.get(key) != pb.get(key):
                    diffs.append({"field": f"blue.{agent}.{key}", "native": nb.get(key), "platform": pb.get(key)})
        rows.append({"world_step": n["world_step"], "equal": not diffs, "differences": diffs})
        if diffs and first is None:
            first = {"world_step": n["world_step"], **diffs[0]}
    terminal = {"native": native_steps[-1]["done"] if native_steps else None,
                "platform": platform_steps[-1]["done"] if platform_steps else None,
                "native_world_steps": len(native_steps), "platform_world_steps": len(platform_steps)}
    totals = {side: _totals(steps) for side, steps in (("native", native_steps), ("platform", platform_steps))}
    return {"compared_fields": [*FIELDS, "blue.<agent>.executed", "blue.<agent>.success"],
            "world_steps": len(rows), "equal_world_steps": sum(1 for r in rows if r["equal"]),
            "equal": bool(rows) and all(r["equal"] for r in rows) and terminal["native"] == terminal["platform"],
            "first_difference": first, "termination": terminal, "reward_totals": totals, "rows": rows}


def _totals(steps: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for st in steps:
        for team, r in st["rewards"].items():
            out[team] = round(out.get(team, 0.0) + float(r), 4)
    return out
