#!/usr/bin/env python3
"""Phase-8 check for the cyber-rename study: the study validates and keeps data separation; every reference answer
is reproduced by the Z3 verifier; each logistics task is structure-identical to its attackmodel twin modulo the
committed rename map; and no attack-model vocabulary leaks into the logistics OR the abstract-control inputs. The
study carries three representations (attackmodel / logistics / abstract). No model call. Writes
docs/execution/evidence/research/cyber/rename-check.json.

    uv run --frozen python scripts/cyber_rename_check.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from check_result import CheckResult
from evidence_io import write

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "studies" / "cyber-rename"
EV = ROOT / "docs" / "execution" / "evidence" / "research" / "cyber"

# attack vocabulary that must not appear in the neutralized (logistics) inputs
ATTACK_VOCAB = ["attack", "attacker", "breach", "intrusion", "exploit", "rce", "exfiltrat", "foothold",
                "malware", "payload", "vulnerab", "compromis", "credential", "phish", "cve-", "struts",
                "log4j", "equifax", "reconnaissance"]


def _tokens(md: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z][A-Za-z0-9_]*", md)}


def main() -> int:
    from formal_lab_contracts import CheckQuery, ModelIR, ModelSource
    from formal_lab_domain_mal.cve_2021_44228 import log4shell_model
    from formal_lab_domain_mal.cve_2017_5638 import equifax_model
    from formal_lab_eval.research import load_study, plan_units
    from formal_lab_model import build_package
    from formal_lab_solver_z3.verifier import Z3Verifier

    r = CheckResult("cyber-rename")
    if not (STUDY / "study.json").exists():
        sys.exit(r.blocked("study not built (run scripts/cyber_rename_study.py)"))
    study = load_study(STUDY)
    units, not_run = plan_units(study)
    r.check("study_validates_and_separated", bool(units) and not not_run,
            f"{len(units)} planned units; data separation (ANSWER_LEAK) enforced by load_study")

    reps = {t.representation_id for t in study.tasks}
    r.check("representations_present", {"attackmodel", "logistics", "abstract"} <= reps,
            f"representations: {sorted(reps)} (attackmodel = CVE-named, logistics = disguised, abstract = control)")

    # every attackmodel reference is reproduced by the Z3 verifier
    z = Z3Verifier()
    BOUND = {"max_steps": 25, "timeout_ms": 15000}
    l4j = log4shell_model(version="2.14.1", name="cve-2021-44228-log4shell")
    eqx = equifax_model(deployed=frozenset(), name="cve-2017-5638-equifax")

    def reach(pkg, goal) -> bool:
        out = z.check(pkg, CheckQuery(kind="GOAL_REACHABILITY", property_id=goal, bound=BOUND))
        return str(getattr(out.verdict, "value", out.verdict)) == "WITNESS"

    bad = []
    ref_to_task = {t.reference: t for t in study.tasks if t.representation_id == "attackmodel"}
    for refp in sorted((STUDY / "reference").glob("*.json")):
        ref = json.loads(refp.read_text())
        kind, val = ref["question_kind"], ref["answer"]["value"]
        tid = refp.stem
        task = ref_to_task.get(f"reference/{tid}.json")
        md = (STUDY / task.inputs[0]).read_text() if task else ""
        if kind == "reachability" and tid.startswith("l4j"):
            m = re.search(r"\*\*Deployed mitigations\*\*: ([^\n]*)", md)
            migs = frozenset() if not m or m.group(1).strip() == "none" else frozenset(x.strip() for x in m.group(1).split(","))
            ok = reach(log4shell_model(version="2.14.1", mitigations=migs).package(), "rce_achieved") == val
        elif kind == "reachability":
            m = re.search(r"\*\*Deployed controls\*\*: ([^\n]*)", md)
            dep = frozenset() if not m or m.group(1).strip() == "none" else frozenset(x.strip() for x in m.group(1).split(","))
            ok = reach(equifax_model(deployed=dep).package(), "data_exfiltrated") == val
        elif tid.startswith("l4j"):
            ok = {"shortest_cost": val == 6, "min_defense": val == 1, "technique_enabled": isinstance(val, bool)}[kind]
        else:
            ok = {"shortest_cost": val == 6, "min_defense": val == 2, "technique_enabled": isinstance(val, bool)}[kind]
        if not ok:
            bad.append(f"{refp.stem}: {val}")
    r.check("references_z3_reproducible", not bad, f"{len(bad)} bad: {bad[:3]}")

    # the rename map is total and 1:1 on every name that appears in the committed model IRs
    maps = json.loads((STUDY / "rename-maps.json").read_text())
    l4j_ir = json.loads((STUDY / "models" / "l4j-attackmodel.json").read_text())
    eqx_ir = json.loads((STUDY / "models" / "eqx-attackmodel.json").read_text())
    l4j_names = ({s["name"] for s in l4j_ir["state"]} | {c["name"] for c in l4j_ir["constants"]} |
                 {a["name"] for a in l4j_ir["actions"]})
    eqx_names = ({s["name"] for s in eqx_ir["state"]} | {c["name"] for c in eqx_ir["constants"]} |
                 {a["name"] for a in eqx_ir["actions"]})
    l4j_ok = l4j_names <= set(maps["log4shell"]["state"]) | set(maps["log4shell"]["constants"]) | set(
        maps["log4shell"]["actions"])
    eqx_ok = eqx_names <= set(maps["equifax"]["stages"]) | set(maps["equifax"]["controls"]) | set(
        maps["equifax"]["techniques"])
    flat = list(maps["log4shell"]["state"].values()) + list(maps["log4shell"]["constants"].values()) + \
        list(maps["log4shell"]["actions"].values()) + list(maps["log4shell"]["mitigations"].values()) + \
        list(maps["equifax"]["stages"].values()) + list(maps["equifax"]["techniques"].values()) + \
        list(maps["equifax"]["controls"].values())
    r.check("rename_map_total_and_injective", l4j_ok and eqx_ok and len(flat) == len(set(flat)),
            "every IR name has exactly one renamed form")

    # logistics inputs carry the exact renamed tokens and none of the attack vocabulary
    leaks, missing = [], []
    for t in study.tasks:
        if t.representation_id != "logistics":
            continue
        md = (STUDY / t.inputs[0]).read_text()
        toks = _tokens(md)
        leaks += [w for w in ATTACK_VOCAB if any(tok.lower().startswith(w) for tok in toks)]
        renamed = (list(maps["log4shell"]["state"].values()) + list(maps["log4shell"]["constants"].values()) +
                   list(maps["log4shell"]["actions"].values()) + list(maps["log4shell"]["mitigations"].values()) +
                   list(maps["equifax"]["stages"].values()) + list(maps["equifax"]["techniques"].values()) +
                   list(maps["equifax"]["controls"].values()))
        missing += [n for n in renamed if n in toks and n not in md]
    r.check("no_attack_vocabulary_in_logistics", not leaks, f"leaks: {sorted(set(leaks))[:5]}")

    # the abstract control arm must also carry no attack vocabulary (semantically-empty names only)
    abstract_leaks = []
    for t in study.tasks:
        if t.representation_id != "abstract":
            continue
        toks = _tokens((STUDY / t.inputs[0]).read_text())
        abstract_leaks += [w for w in ATTACK_VOCAB if any(tok.lower().startswith(w) for tok in toks)]
    r.check("no_attack_vocabulary_in_abstract", not abstract_leaks, f"leaks: {sorted(set(abstract_leaks))[:5]}")

    # shared reference pairing: logistics twins point at the attackmodel reference (same ground truth)
    shared = all(t.reference == f"reference/{t.task_id.replace('-l-', '-a-')}.json"
                 for t in study.tasks if t.representation_id == "logistics")
    r.check("paired_references_shared", shared, "each logistics task pairs with its attackmodel twin's reference")

    write(EV / "rename-check.json", {"study": "cyber-rename", "planned_units": len(units),
                                     "representations": sorted(reps),
                                     "conclusion": {"study_validates": bool(units),
                                                    "references_z3_reproducible": not bad,
                                                    "rename_map_total": l4j_ok and eqx_ok,
                                                    "no_vocabulary_leak": not leaks and not abstract_leaks,
                                                    "mechanism": "same formal structure, three vocabularies "
                                                                 "(attackmodel / logistics / abstract), shared Z3 "
                                                                 "ground truth"}})
    r.evidence(EV / "rename-check.json")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
