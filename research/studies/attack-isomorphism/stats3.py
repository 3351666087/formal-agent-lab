"""Item-level statistics for experiment3 (pure Python).

The unit of analysis is the ITEM (18 isomorphic triples), not the API call: repeated
samples of one prompt are averaged into one item-level rate first, so the tests are not
pseudo-replicated. Each contrast is a paired difference across items, reported with
  * the mean difference,
  * a 95% cluster-bootstrap CI (resampling items, 10 000 draws),
  * a two-sided sign-flip permutation p across items (20 000 random flips),
  * how many items move in each direction.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_ALL = json.load(open(HERE / "experiment3-graded.json"))
# a (subject, item) pair is only analysed if every one of its calls succeeded — partially
# covered items (e.g. a provider stopping mid-run) are dropped rather than averaged over
# whichever cells happened to finish.
_n = defaultdict(int); _ok = defaultdict(int)
for r in _ALL:
    _n[(r["subject"], r["item"])] += 1
    _ok[(r["subject"], r["item"])] += r["outcome"] in ("refused", "correct", "wrong")
COMPLETE = {k for k in _n if _ok[k] == _n[k]}
DROPPED = sorted(k for k in _n if k not in COMPLETE)
G = [r for r in _ALL if (r["subject"], r["item"]) in COMPLETE and r["outcome"] in ("refused", "correct", "wrong")]
ITEMS = sorted({r["item"] for r in G})
FAMILY = {r["item"]: r["family"] for r in G}
SUBJECTS = [s for s in ["deepseek-chat", "gpt-6.2-astra", "gemini-4-carbon"] if any(r["subject"] == s for r in G)]
GUARDS = ["off", "generic", "policy", "explicit"]
VOCABS = ["attack", "business", "abstract"]
TASKS = ["path_bad", "path_success", "mincontrol"]

cell = defaultdict(list)
for r in G:
    cell[(r["subject"], r["guardrail"], r["vocab"], r["task"], r["item"])].append(r["outcome"])


def item_rates(subject, guard, vocab, tasks, metric):
    """item -> rate, averaging over reps and over the given tasks."""
    out = {}
    for it in ITEMS:
        vals = []
        for t in tasks:
            oc = cell.get((subject, guard, vocab, t, it), [])
            if not oc:
                continue
            if metric == "refused":
                vals.append(sum(o == "refused" for o in oc) / len(oc))
            elif metric == "solved":
                vals.append(sum(o == "correct" for o in oc) / len(oc))
            elif metric == "cond_acc":
                ans = [o for o in oc if o != "refused"]
                if ans:
                    vals.append(sum(o == "correct" for o in ans) / len(ans))
        if vals:
            out[it] = sum(vals) / len(vals)
    return out


def contrast(a: dict, b: dict, seed=0):
    its = sorted(set(a) & set(b))
    d = [a[i] - b[i] for i in its]
    n = len(d)
    mean = sum(d) / n
    rng = random.Random(seed)
    boots = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(10000))
    lo, hi = boots[249], boots[9749]
    obs = abs(mean)
    ext = 0
    for _ in range(20000):
        s = sum(x if rng.random() < 0.5 else -x for x in d) / n
        ext += abs(s) >= obs - 1e-12
    p = (ext + 1) / 20001
    return {"n_items": n, "mean_diff": mean, "ci": [lo, hi], "p_perm": p,
            "items_up": sum(x > 1e-9 for x in d), "items_down": sum(x < -1e-9 for x in d),
            "items_equal": sum(abs(x) <= 1e-9 for x in d)}


def mean_ci(rates: dict, seed=0):
    v = list(rates.values()); n = len(v)
    rng = random.Random(seed)
    boots = sorted(sum(v[rng.randrange(n)] for _ in range(n)) / n for _ in range(10000))
    return {"mean": sum(v) / n, "ci": [boots[249], boots[9749]], "n_items": n}


def fmt(c):
    return (f"Δ={c['mean_diff']:+.2f} [{c['ci'][0]:+.2f},{c['ci'][1]:+.2f}] p={c['p_perm']:.4f} "
            f"items↑{c['items_up']} ↓{c['items_down']} ={c['items_equal']} (n={c['n_items']})")


def main() -> int:
    S = {"descriptive": {}, "contrasts": {}, "family": {}}
    print(f"usable records: {len(G)}; items: {len(ITEMS)}")

    print("\n== descriptive (item-mean over all tasks, 95% cluster-bootstrap CI) ==")
    for s in SUBJECTS:
        for g in GUARDS:
            for v in VOCABS:
                rf = mean_ci(item_rates(s, g, v, TASKS, "refused"))
                sv = mean_ci(item_rates(s, g, v, TASKS, "solved"))
                ca = mean_ci(item_rates(s, g, v, TASKS, "cond_acc"))
                S["descriptive"][f"{s}|{g}|{v}"] = {"refused": rf, "solved": sv, "cond_acc": ca}
                print(f"  {s:14} {g:8} {v:9} refused {rf['mean']:.2f}[{rf['ci'][0]:.2f},{rf['ci'][1]:.2f}] "
                      f"solved {sv['mean']:.2f}[{sv['ci'][0]:.2f},{sv['ci'][1]:.2f}] "
                      f"acc|answered {ca['mean']:.2f}")

    def add(name, c):
        S["contrasts"][name] = c
        print(f"  {name:62} {fmt(c)}")

    for s in SUBJECTS:
        print(f"\n== {s}: C1 guardrail cost on legitimate (business) problems — solve rate, off minus guard ==")
        off = item_rates(s, "off", "business", TASKS, "solved")
        for g in ("generic", "policy", "explicit"):
            add(f"{s}|C1 solve(business) off−{g}", contrast(off, item_rates(s, g, "business", TASKS, "solved")))
        for g in ("policy", "explicit"):
            for t in TASKS:
                add(f"{s}|C1 solve(business,{t}) off−{g}",
                    contrast(item_rates(s, "off", "business", [t], "solved"), item_rates(s, g, "business", [t], "solved")))

        print(f"\n== {s}: C2 native guardrail (no system prompt), path_bad refusal by vocabulary ==")
        ra = item_rates(s, "off", "attack", ["path_bad"], "refused")
        rb = item_rates(s, "off", "business", ["path_bad"], "refused")
        rx = item_rates(s, "off", "abstract", ["path_bad"], "refused")
        add(f"{s}|C2 native refusal(path_bad) attack−business", contrast(ra, rb))
        add(f"{s}|C2 native refusal(path_bad) business−abstract", contrast(rb, rx))
        add(f"{s}|C2 native refusal(path_bad) attack−abstract", contrast(ra, rx))

        print(f"\n== {s}: C3 bad target vs success target (business), refusal ==")
        for g in ("off", "policy", "explicit"):
            add(f"{s}|C3 refusal(business,{g}) path_bad−path_success",
                contrast(item_rates(s, g, "business", ["path_bad"], "refused"),
                         item_rates(s, g, "business", ["path_success"], "refused")))

        print(f"\n== {s}: C4 naming under policy/explicit, path_bad refusal ==")
        for g in ("policy", "explicit"):
            a_ = item_rates(s, g, "attack", ["path_bad"], "refused")
            b_ = item_rates(s, g, "business", ["path_bad"], "refused")
            x_ = item_rates(s, g, "abstract", ["path_bad"], "refused")
            add(f"{s}|C4 refusal(path_bad,{g}) attack−business", contrast(a_, b_))
            add(f"{s}|C4 refusal(path_bad,{g}) business−abstract", contrast(b_, x_))

        print(f"\n== {s}: C5 capability across arms with no guardrail (solve rate) ==")
        add(f"{s}|C5 solve(off) business−abstract",
            contrast(item_rates(s, "off", "business", TASKS, "solved"), item_rates(s, "off", "abstract", TASKS, "solved")))
        add(f"{s}|C5 solve(off) attack−business",
            contrast(item_rates(s, "off", "attack", TASKS, "solved"), item_rates(s, "off", "business", TASKS, "solved")))

    print("\n== heterogeneity by family: business path_bad refusal (off / policy / explicit) ==")
    for s in SUBJECTS:
        for fam in ("base", "TLS", "KRACK", "TCP"):
            row = {}
            for g in ("off", "policy", "explicit"):
                r = item_rates(s, g, "business", ["path_bad"], "refused")
                vals = [v for it, v in r.items() if FAMILY[it] == fam]
                row[g] = sum(vals) / len(vals) if vals else None
            S["family"][f"{s}|{fam}"] = row
            print(f"  {s:14} {fam:6} " + "  ".join(f"{g}=" + ("n/a" if row[g] is None else f"{row[g]:.2f}") for g in row))

    S["coverage"] = {s: sorted(it for (ss, it) in COMPLETE if ss == s) for s in SUBJECTS}
    S["dropped"] = [list(k) for k in DROPPED]
    print("\ncoverage (complete items per subject):", {s: len(v) for s, v in S["coverage"].items()})
    print("dropped (subject, item) pairs:", len(DROPPED))
    json.dump(S, open(HERE / "stats3-summary.json", "w"), indent=1)
    print("\nsaved stats3-summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
