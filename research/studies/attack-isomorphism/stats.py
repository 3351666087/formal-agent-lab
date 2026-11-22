"""Statistics for the guardrail experiment (pure Python — no scipy dependency).

Implements Wilson score intervals, two-sided Fisher exact, exact McNemar, Cohen's kappa,
and runs the pre-registered comparisons:
  * dose-response of refusal across guardrail levels (off < generic < explicit?);
  * the guardrail's cost on the LEGITIMATE business problems (off vs explicit), per subject;
  * attack vs business vs abstract within each guardrail (is refusal about the domain or the
    task shape?);
  * path-to-bad vs path-to-success (benign-goal control: is it the path task or the bad
    target that is refused?);
  * annotator A vs annotator B agreement (Cohen's kappa), if judge output is present.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
Z = 1.959963984540054  # 95%


def wilson(k: int, n: int):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = p + Z * Z / (2 * n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return (p, (c - half) / d, (c + half) / d)


def _hyper(a, b, c, d):
    n = a + b + c + d
    return (math.comb(a + b, a) * math.comb(c + d, c)) / math.comb(n, a + c)


def fisher_exact(a, b, c, d):
    """Two-sided Fisher exact p for the 2x2 [[a,b],[c,d]]."""
    r1, r2 = a + b, c + d
    col1 = a + c
    n = a + b + c + d
    p_obs = _hyper(a, b, c, d)
    lo = max(0, col1 - r2)
    hi = min(r1, col1)
    p = 0.0
    for aa in range(lo, hi + 1):
        bb, cc, dd = r1 - aa, col1 - aa, r2 - (col1 - aa)
        pr = _hyper(aa, bb, cc, dd)
        if pr <= p_obs * (1 + 1e-9):
            p += pr
    return min(1.0, p)


def mcnemar_exact(b: int, c: int):
    """Exact McNemar two-sided p for discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return min(1.0, 2 * tail)


def cohen_kappa(n11, n10, n01, n00):
    n = n11 + n10 + n01 + n00
    if n == 0:
        return None
    po = (n11 + n00) / n
    p_yes = (n11 + n10) / n * (n11 + n01) / n
    p_no = (n01 + n00) / n * (n10 + n00) / n
    pe = p_yes + p_no
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def load():
    return json.load(open(HERE / "experiment2-graded.json"))


def rate(cells, pred):
    k = sum(1 for c in cells if pred(c))
    n = len(cells)
    return k, n, wilson(k, n)


def main() -> int:
    g = load()
    ok = [c for c in g if c["outcome"] not in ("error", "unparseable")]
    print(f"records={len(g)}  usable={len(ok)}  "
          f"(errors={sum(c['outcome']=='error' for c in g)}, "
          f"unparseable={sum(c['outcome']=='unparseable' for c in g)})")

    refused = lambda c: c["outcome"] == "refused"
    correct = lambda c: c["outcome"] == "correct"

    def sub(**kw):
        return [c for c in ok if all(c[k] == v for k, v in kw.items())]

    print("\n=== refusal rate by subject x guardrail (all cells) ===")
    for s in sorted({c["subject"] for c in ok}):
        for gd in ("off", "generic", "explicit"):
            k, n, (p, lo, hi) = rate(sub(subject=s, guardrail=gd), refused)
            print(f"  {s:16} guard={gd:9} refused {k:3}/{n:3} = {p:.2f} [{lo:.2f},{hi:.2f}]")

    print("\n=== the key result: business-vocab problems, off vs explicit ===")
    for s in sorted({c["subject"] for c in ok}):
        biz = lambda gd: sub(subject=s, guardrail=gd, vocab="business")
        for metric, pred in (("solved", correct), ("refused", refused)):
            ko, no, (po, lo, hi) = rate(biz("off"), pred)
            ke, ne, (pe, le, he) = rate(biz("explicit"), pred)
            print(f"  {s:16} {metric:8} off {ko}/{no}={po:.2f}[{lo:.2f},{hi:.2f}] "
                  f"-> explicit {ke}/{ne}={pe:.2f}[{le:.2f},{he:.2f}]")
        # Fisher on refusal: off vs explicit (business)
        a = sum(refused(c) for c in biz("off")); b = len(biz("off")) - a
        cc = sum(refused(c) for c in biz("explicit")); d = len(biz("explicit")) - cc
        print(f"    Fisher (refused: off vs explicit, business): p={fisher_exact(a, b, cc, d):.2e}")

    print("\n=== task shape: path_bad vs path_success vs mincontrol (explicit guardrail, business) ===")
    for s in sorted({c["subject"] for c in ok}):
        for task in ("path_bad", "path_success", "mincontrol"):
            k, n, (p, lo, hi) = rate(sub(subject=s, guardrail="explicit", vocab="business", task=task), refused)
            print(f"  {s:16} {task:13} refused {k:3}/{n:3} = {p:.2f} [{lo:.2f},{hi:.2f}]")

    print("\n=== vocabulary: attack vs business vs abstract (explicit guardrail, path_bad) ===")
    for s in sorted({c["subject"] for c in ok}):
        for v in ("attack", "business", "abstract"):
            k, n, (p, lo, hi) = rate(sub(subject=s, guardrail="explicit", vocab=v, task="path_bad"), refused)
            print(f"  {s:16} vocab={v:9} refused {k:3}/{n:3} = {p:.2f} [{lo:.2f},{hi:.2f}]")

    # kappa if judge present
    jp = HERE / "experiment2-judged.json"
    if jp.exists():
        J = json.load(open(jp))
        n11 = n10 = n01 = n00 = 0
        for r in J:
            if r.get("refused_A") is None or r.get("refused_B") is None:
                continue
            A, B = bool(r["refused_A"]), bool(r["refused_B"])
            n11 += A and B; n10 += A and not B; n01 += (not A) and B; n00 += (not A) and (not B)
        kap = cohen_kappa(n11, n10, n01, n00)
        print(f"\n=== inter-annotator agreement (refused: A vs B), n={n11+n10+n01+n00} ===")
        print(f"  Cohen's kappa = {kap:.3f}  (A&B={n11}, A!B={n10}, !A&B={n01}, neither={n00})")
    else:
        print("\n(judge output not present yet; run judge.py for inter-annotator kappa)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
