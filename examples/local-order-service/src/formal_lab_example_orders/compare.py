"""Pure-data model vs business service under the same action contract (P2-066).

Two runs of the same case, seed and strategy — one on the ir-world backend, one on the order service — are aligned
step by step and compared on:

- preconditions: each candidate action's applicability on the step's observation;
- outcomes:      status and reason of the executed action;
- effects:       every state location after the step (field level: path, pure value, service value);
- evidence:      what backs the outcome (a pure snapshot vs a service operation record).

Every difference names the step, both operation ids and the field, so it can be located in either run. When the
trajectories diverge (different actions), alignment stops there and the divergence is the last difference.
"""

from __future__ import annotations

import json
from typing import Any


def _by_step(events: list[Any], kind: str) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for e in events:
        if str(e.event_type) == kind and e.logical_step is not None:
            out.setdefault(int(e.logical_step), []).append(e.payload)
    return out


def _post_states(result: Any) -> dict[int, dict[str, Any]]:
    """State after step k = the observation that opens step k+1 (the final state after the last step)."""
    obs = {k: v[0]["observation"] for k, v in _by_step(result.events, "OBSERVATION").items()}
    steps = sorted(_by_step(result.events, "ACTION_OUTCOME"))
    out = {}
    for k in steps:
        nxt = obs.get(k + 1)
        out[k] = ({f["path"]: f["value"] for f in nxt["facts"]} if nxt is not None else dict(result.final_state))
    return out


def compare_runs(pure: Any, service: Any) -> dict[str, Any]:
    diffs: list[dict[str, Any]] = []
    p_out, s_out = _by_step(pure.events, "ACTION_OUTCOME"), _by_step(service.events, "ACTION_OUTCOME")
    p_cand, s_cand = _by_step(pure.events, "CANDIDATES"), _by_step(service.events, "CANDIDATES")
    p_post, s_post = _post_states(pure), _post_states(service)
    aligned = 0
    compared_fields = 0
    for step in sorted(set(p_out) | set(s_out)):
        po, so = (p_out.get(step) or [{}])[0].get("outcome"), (s_out.get(step) or [{}])[0].get("outcome")
        where = {"step": step, "pure_operation": po and po["operation_id"], "service_operation": so and so["operation_id"]}
        if po is None or so is None:
            diffs.append({**where, "kind": "trajectory", "field": "step",
                          "pure": po and po["action"], "service": so and so["action"],
                          "note": "one run has no action at this step"})
            break
        if json.dumps(po["action"], sort_keys=True) != json.dumps(so["action"], sort_keys=True):
            diffs.append({**where, "kind": "trajectory", "field": "action", "pure": po["action"],
                          "service": so["action"], "note": "the strategies chose differently; alignment stops"})
            break
        aligned += 1
        pc = {json.dumps(c["action"], sort_keys=True): c["belief_applicability"]
              for c in (p_cand.get(step) or [{"candidates": []}])[0]["candidates"]}
        sc = {json.dumps(c["action"], sort_keys=True): c["belief_applicability"]
              for c in (s_cand.get(step) or [{"candidates": []}])[0]["candidates"]}
        for key in sorted(set(pc) | set(sc)):
            if pc.get(key) != sc.get(key):
                diffs.append({**where, "kind": "precondition", "field": key, "pure": pc.get(key),
                              "service": sc.get(key)})
        for fld in ("status", "effect_applied"):
            if po.get(fld) != so.get(fld):
                diffs.append({**where, "kind": "outcome", "field": fld, "pure": po.get(fld), "service": so.get(fld)})
        if po.get("status") == so.get("status") == "REJECTED" and \
                (po.get("result", {}).get("reason") or "").split(":")[0] != \
                (so.get("result", {}).get("reason") or "").split(":")[0]:
            diffs.append({**where, "kind": "outcome", "field": "reason", "pure": po["result"].get("reason"),
                          "service": so["result"].get("reason")})
        pp, sp = p_post.get(step, {}), s_post.get(step, {})
        for path in sorted(set(pp) | set(sp)):
            compared_fields += 1
            if pp.get(path) != sp.get(path):
                diffs.append({**where, "kind": "effect", "field": path, "pure": pp.get(path),
                              "service": sp.get(path)})
    evidence = {"pure": sorted({ev["kind"] for v in p_out.values() for ev in v[0]["outcome"].get("evidence", [])}),
                "service": sorted({ev["kind"] for v in s_out.values() for ev in v[0]["outcome"].get("evidence", [])})}
    kinds: dict[str, int] = {}
    for d in diffs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    return {"aligned_steps": aligned, "compared_fields": compared_fields, "differences": diffs, "by_kind": kinds,
            "evidence_kinds": evidence,
            "pure": {"run_id": pure.manifest.run_id, "status": pure.status.value, "steps": pure.usage.steps},
            "service": {"run_id": service.manifest.run_id, "status": service.status.value,
                        "steps": service.usage.steps}}


def markdown(title: str, report: dict[str, Any], limit: int = 60) -> str:
    lines = [f"### {title}", "",
             f"aligned steps: {report['aligned_steps']}; fields compared: {report['compared_fields']}; differences: "
             f"{len(report['differences'])} {report['by_kind'] or ''}; evidence — pure: "
             f"{', '.join(report['evidence_kinds']['pure']) or 'none'}, service: "
             f"{', '.join(report['evidence_kinds']['service']) or 'none'}",
             ""]
    if report["differences"]:
        lines += ["| step | kind | field | pure | service | pure op | service op |", "|---|---|---|---|---|---|---|"]
        for d in report["differences"][:limit]:
            lines.append(f"| {d['step']} | {d['kind']} | `{d['field']}` | {d['pure']} | {d['service']} | "
                         f"`{d['pure_operation']}` | `{d['service_operation']}` |")
        if len(report["differences"]) > limit:
            lines.append(f"| … | {len(report['differences']) - limit} more in the JSON report | | | | | |")
    return "\n".join(lines) + "\n"
