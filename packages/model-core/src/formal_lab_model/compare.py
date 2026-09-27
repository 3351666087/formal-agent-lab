"""Generic effect comparison: expected post-state (from a model) vs what was observed.

v2 makes the evidence behind every compared field explicit (P2-074):
- observed               — the field was observed fresh at the observation's step;
- verified-within-scope  — not in the actor's fresh view, but established by an independent source whose scope is
                           stated (a probe or an operation query of the business service), passed in `verified`;
- unknown                — neither: the field is not comparable (freshness MISSING or STALE);
- predicted              — (expected side) what the model predicts; every diff's `expected` is a prediction.
"""

from __future__ import annotations

from collections.abc import Iterable

from formal_lab_contracts import (
    ComparisonVerdict,
    EffectComparison,
    EvidenceRef,
    FieldDiff,
    Observation,
    StateScalar,
)


def compare_effects(
    *,
    expected_post: dict[str, StateScalar] | None,
    pre_state: dict[str, StateScalar],
    observation: Observation,
    written_paths: Iterable[str],
    expected_by: str,
    evidence: list[EvidenceRef] | None = None,
    verified: dict[str, StateScalar] | None = None,
) -> EffectComparison:
    """Compare field by field.

    A field is MATCH / DIFFERENT only when it was observed fresh at the observation's step (or verified by an
    independent source); stale or unknown fields are UNKNOWN. Checked fields: those the action writes, those the
    model predicts to change, and any observed field that differs from the prediction.

    Verdict: DIFFERENT if any field differs, else INSUFFICIENT_INFORMATION if any relevant field is
    unknown, else MATCH. With no expectation at all the verdict is INSUFFICIENT_INFORMATION.
    """
    if expected_post is None:
        return EffectComparison(verdict=ComparisonVerdict.INSUFFICIENT_INFORMATION, expected_by=expected_by,
                                evidence=evidence or [])
    fresh = {f.path: f for f in observation.facts if f.observed_at_step >= observation.step}
    stale = {f.path: f for f in observation.facts if f.observed_at_step < observation.step}
    stale.update({u.path: u.last_known for u in observation.unknowns if u.last_known is not None})
    verified = verified or {}
    relevant = set(written_paths) | {p for p, v in expected_post.items() if pre_state.get(p) != v}
    relevant |= {p for p, f in fresh.items() if p in expected_post and expected_post[p] != f.value}
    relevant |= {p for p, v in verified.items() if p in expected_post and expected_post[p] != v}
    diffs: list[FieldDiff] = []
    for path in sorted(relevant):
        expected = expected_post.get(path)
        if path in fresh:
            f = fresh[path]
            diffs.append(FieldDiff(path=path, expected=expected, observed=f.value,
                                   status="MATCH" if f.value == expected else "DIFFERENT", evidence="observed",
                                   observed_at_step=f.observed_at_step, freshness="FRESH"))
        elif path in verified:
            diffs.append(FieldDiff(path=path, expected=expected, observed=verified[path],
                                   status="MATCH" if verified[path] == expected else "DIFFERENT",
                                   evidence="verified-within-scope", observed_at_step=observation.step,
                                   freshness="FRESH"))
        else:
            last = stale.get(path)
            diffs.append(FieldDiff(path=path, expected=expected, observed=None, status="UNKNOWN", evidence="unknown",
                                   observed_at_step=last.observed_at_step if last is not None else None,
                                   freshness="STALE" if last is not None else "MISSING"))
    if any(d.status == "DIFFERENT" for d in diffs):
        verdict = ComparisonVerdict.DIFFERENT
    elif any(d.status == "UNKNOWN" for d in diffs):
        verdict = ComparisonVerdict.INSUFFICIENT_INFORMATION
    else:
        verdict = ComparisonVerdict.MATCH
    counts: dict[str, int] = {}
    for d in diffs:
        counts[d.evidence] = counts.get(d.evidence, 0) + 1
    return EffectComparison(verdict=verdict, expected_by=expected_by, diffs=diffs, evidence=evidence or [],
                            evidence_counts=counts)
