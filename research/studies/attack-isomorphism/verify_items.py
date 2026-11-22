"""Verify every item: three arms pairwise isomorphic (Z3, unique bijection), and compute the
exact ground truth (shortest path to bad / to success, minimal control set) per arm."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from families import ITEMS
from verify_isomorphism import z3_isomorphism
from ground_truth import shortest_path, minimal_defence_sets
from grade2 import shortest_to

def amap(src, dst):
    return dict(zip(src.actions, dst.actions))

out = []; allok = True
for it in ITEMS:
    a = it["arms"]
    iso = {}
    for other in ("business", "abstract"):
        r = z3_isomorphism(a["attack"], a[other], amap(a["attack"], a[other]), free_actions=False)
        iso[other] = bool(r.get("exists") and r.get("unique"))
    gt = {}
    for arm, l in a.items():
        sp = shortest_path(l); md = minimal_defence_sets(l)
        gt[arm] = {"path_bad": sp["length"], "path_success": shortest_to(l, set(l.success)),
                   "mincontrol": md["size"], "mincontrol_example": md["sets"][0]}
    same = len({json.dumps({k: v for k, v in g.items() if k != "mincontrol_example"}, sort_keys=True) for g in gt.values()}) == 1
    ok = all(iso.values()) and same
    allok &= ok
    out.append({"item": it["item"], "family": it["family"], "n": it["n"], "k": it["k"],
                "states": len(a["attack"].states), "transitions": len(a["attack"].transitions),
                "iso_business": iso["business"], "iso_abstract": iso["abstract"],
                "gt": gt, "ok": ok})
    g = gt["attack"]
    print(f"{it['item']:18} states={len(a['attack'].states):2} edges={len(a['attack'].transitions):2} "
          f"iso(biz,abs)={iso['business']},{iso['abstract']}  path_bad={g['path_bad']} "
          f"path_success={g['path_success']} mincontrol={g['mincontrol']}  {'OK' if ok else 'FAIL'}")
json.dump(out, open(HERE / "items-groundtruth.json", "w"), indent=1)
print("ALL ITEMS OK:", allok, "| items:", len(out))
