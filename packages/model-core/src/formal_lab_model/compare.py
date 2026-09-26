"""Generic effect comparison: expected post-state (from a model) vs what was observed."""

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
) -> EffectComparison:
    """Compare field by field.

    A field is MATCH / DIFFERENT only when it was observed fresh at the observation's step; stale
    or unknown fields are UNKNOWN. Checked fields: those the action writes, those the model predicts
    to change, and any observed field that differs from the prediction.

    Verdict: DIFFERENT if any field differs, else INSUFFICIENT_INFORMATION if any relevant field is
    unknown, else MATCH. With no expectation at all the verdict is INSUFFICIENT_INFORMATION.
    """
    if expected_post is None:
        return EffectComparison(verdict=ComparisonVerdict.INSUFFICIENT_INFORMATION, expected_by=expected_by,
                                evidence=evidence or [])
    fresh = {f.path: f.value for f in observation.facts if f.observed_at_step >= observation.step}
    relevant = set(written_paths) | {p for p, v in expected_post.items() if pre_state.get(p) != v}
    relevant |= {p for p, v in fresh.items() if p in expected_post and expected_post[p] != v}
    diffs: list[FieldDiff] = []
    for path in sorted(relevant):
        expected = expected_post.get(path)
        if path not in fresh:
            diffs.append(FieldDiff(path=path, expected=expected, observed=None, status="UNKNOWN"))
        else:
            status = "MATCH" if fresh[path] == expected else "DIFFERENT"
            diffs.append(FieldDiff(path=path, expected=expected, observed=fresh[path], status=status))
    if any(d.status == "DIFFERENT" for d in diffs):
        verdict = ComparisonVerdict.DIFFERENT
    elif any(d.status == "UNKNOWN" for d in diffs):
        verdict = ComparisonVerdict.INSUFFICIENT_INFORMATION
    else:
        verdict = ComparisonVerdict.MATCH
    return EffectComparison(verdict=verdict, expected_by=expected_by, diffs=diffs, evidence=evidence or [])
