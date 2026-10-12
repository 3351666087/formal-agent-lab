"""Research scorers (phase 6A): the answer axis and the thin, registrable scoring interface for static tasks.

A scorer never sees the provider call — only the parsed answer and its own reference evidence (a file the model is
never given). The runner (`formal_lab_eval.research`) keeps the call axis apart: an answer is parsed only after the
raw response was saved, and only an answer the model actually produced reaches a scorer.

    register_scorer(MyScorer())                       # in-process
    [project.entry-points."formal_lab.research_scorers"]
    my-scorer = "my_package.scorers:SCORER"           # discovered on first lookup (an instance, a class or a list)

A scorer has `scorer_id`, `version` and `score(parsed, reference, *, repo_root, truncated) -> ScoreOutcome`. Phase 6B
registers professional scorers this way; the built-ins below are:

  orders.deviation-diagnosis@1   implementation_conformance — the answer names a model revision (constant, station,
                                 value); it is applied to the belief model and the *recorded program run* is replayed
                                 on the revised model: CORRESPONDS = correct. Grounded in the program observation, not
                                 in the reference answer (which is only reported alongside).
  synthetic.shortest-plan@1      synthetic_representation — the answer is a plan; it is replayed on the reference
                                 interpreter (the model driver) and compared with the breadth-first shortest length.
                                 Program correspondence does not apply (NOT_APPLICABLE, never filled in as a pass).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Protocol

import jsonschema
from formal_lab_contracts.errors import InvalidInput

ENTRY_POINT_GROUP = "formal_lab.research_scorers"


@dataclass
class ScoreOutcome:
    behavior: str  # CORRECT / PARTIAL / INCORRECT
    model_internal: str  # CORRECT / INCORRECT / NOT_EVALUATED / NOT_APPLICABLE
    program_correspondence: str  # CORRESPONDS / DEVIATES / UNKNOWN / NOT_APPLICABLE / NOT_EVALUATED
    explanation: str
    dependencies: dict[str, str] = field(default_factory=dict)


class ResearchScorer(Protocol):
    scorer_id: str
    version: str

    def score(self, parsed: Any, reference: dict[str, Any], *, repo_root: Path, truncated: bool) -> ScoreOutcome: ...


_REGISTRY: dict[tuple[str, str], ResearchScorer] = {}
_DISCOVERED = False


def register_scorer(scorer: ResearchScorer) -> ResearchScorer:
    _REGISTRY[(scorer.scorer_id, str(scorer.version))] = scorer
    return scorer


def scorer_for(scorer_id: str, version: str) -> ResearchScorer:
    global _DISCOVERED
    if (scorer_id, version) not in _REGISTRY and not _DISCOVERED:
        _DISCOVERED = True
        for ep in entry_points(group=ENTRY_POINT_GROUP):
            obj = ep.load()
            for item in obj if isinstance(obj, list | tuple) else [obj]:
                register_scorer(item() if isinstance(item, type) else item)
    try:
        return _REGISTRY[(scorer_id, version)]
    except KeyError:
        raise InvalidInput(f"no research scorer {scorer_id}@{version} is registered "
                           f"(known: {sorted(f'{a}@{b}' for a, b in _REGISTRY)})") from None


def registered() -> list[str]:
    return sorted(f"{a}@{b}" for a, b in _REGISTRY)


# ------------------------------------------------------------------------------------------------------ answer axis
def parse_answer(answer_format: str, schema: dict[str, Any] | None, outcome: str, visible: str | None
                 ) -> tuple[str, Any, str]:
    """(AnswerStatus, parsed, note) for a saved response. Only a model-produced, non-refused answer is parsed."""
    from formal_lab_contracts.research import MODEL_PRODUCED

    if outcome not in MODEL_PRODUCED or outcome == "CONTENT_REFUSAL":
        return "NO_ANSWER", None, f"no answer to parse ({outcome})"
    text = (visible or "").strip()
    if not text:
        return "EMPTY", None, "no visible text"
    if answer_format == "free_text":
        return "VALID", text, ""
    candidate, note = text, ""
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S)
    if m:
        candidate, note = m.group(1), "one fenced JSON block"
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return "INVALID_JSON", None, f"not JSON: {exc.msg} at {exc.pos}"
    if schema:
        errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(value), key=lambda e: list(e.path))
        if errors:
            kind = "TYPE_ERROR" if any(e.validator == "type" for e in errors) else "SCHEMA_VIOLATION"
            return kind, value, errors[0].message[:300]
    return "VALID", value, note


# ------------------------------------------------------------------------------------------------ shared helpers
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _evidence(repo_root: Path, ref: dict[str, Any]) -> bytes:
    """A reference dependency, checked against the digest the reference file pins."""
    data = (repo_root / ref["path"]).read_bytes()
    if sha256_bytes(data) != ref["sha256"]:
        raise InvalidInput(f"reference evidence {ref['path']} changed (sha256 mismatch): rescoring needs a new "
                           "reference version")
    return data


def _loaded(package: Any) -> Any:
    from formal_lab_runtime import default_registry

    reg = default_registry()
    return reg.create(reg.driver_for(package.semantic_profile).descriptor.ref(), {}, None).load(package)


def _label(action: Any) -> str:
    params = list((action.params or {}).values())
    return action.action_type if not params else f"{action.action_type}({','.join(str(p) for p in params)})"


# --------------------------------------------------------------------- orders.deviation-diagnosis@1 (implementation)
class DeviationDiagnosisScorer:
    scorer_id = "orders.deviation-diagnosis"
    version = "1"

    def score(self, parsed: Any, reference: dict[str, Any], *, repo_root: Path, truncated: bool) -> ScoreOutcome:
        from formal_lab_contracts import ModelIR, ModelPackage, ModelSource
        from formal_lab_model import build_package
        from formal_lab_runtime.research import decide_correspondence, replay_items

        model_bytes = _evidence(repo_root, reference["belief_model"])
        bundle = _evidence(repo_root, reference["observation"])
        pkg = ModelPackage.model_validate_json(model_bytes)
        deps = {"belief_model": sha256_bytes(model_bytes), "observation": sha256_bytes(bundle)}
        name, station, value = parsed.get("constant"), parsed.get("station"), parsed.get("value")
        const = next((c for c in pkg.ir.constants if c.name == name), None)
        stations = next((e.members for e in pkg.ir.entity_sets if e.name == "stations"), [])
        if const is None or list(const.index) != ["stations"] or station not in stations or \
                const.type.kind != "bool" or not isinstance(value, bool):
            return ScoreOutcome("INCORRECT", "INCORRECT", "NOT_EVALUATED",
                                f"{name}[{station}]={value!r} is not a revision of a boolean station constant of the "
                                "belief model, so it cannot be applied", deps)
        data = pkg.ir.model_dump(mode="json")
        cdata = next(c for c in data["constants"] if c["name"] == name)
        cells = cdata["value"].setdefault("cells", [])
        cell = next((c for c in cells if c["index"] == [station]), None)
        if cell is None:
            cells.append({"index": [station], "value": value})
        else:
            cell["value"] = value
        revised_ir = ModelIR.model_validate(data)
        candidate = build_package(revised_ir, package_id=pkg.package_id, version=pkg.version,
                                  source=ModelSource(format="fal-ir-json/v1", text=revised_ir.model_dump_json(),
                                                     origin=f"research answer: {name}[{station}]={value}"))
        items, meta = replay_items(candidate, bundle)
        status, note = decide_correspondence(items, has_observation=True)
        exp = reference.get("expected", {})
        agrees = (name, station, value) == (exp.get("constant"), exp.get("station"), exp.get("value"))
        behavior = "CORRECT" if status == "CORRESPONDS" else "INCORRECT"
        return ScoreOutcome(behavior, "CORRECT", status,
                            f"revision {name}[{station}]={value}: the recorded run ({meta['steps']} steps) replayed on "
                            f"the revised model → {status} ({note}); the reference revision is "
                            f"{exp.get('constant')}[{exp.get('station')}]={exp.get('value')} "
                            f"({'same' if agrees else 'different'})", deps)


# --------------------------------------------------------------------- synthetic.shortest-plan@1 (representation)
def shortest_length(loaded: Any, goal: str, bound: int) -> int | None:
    """Breadth-first search on the reference interpreter: the fewest actions that reach the goal, within the bound."""
    start = loaded.initial_state()
    if loaded.properties(start).get(goal):
        return 0
    actions = loaded.ground_actions()
    frontier, seen = [start], {json.dumps(start, sort_keys=True)}
    for depth in range(1, bound + 1):
        nxt = []
        for state in frontier:
            for action in actions:
                pred = loaded.predict(state, action)
                if not pred.applicable or pred.next_state is None:
                    continue
                key = json.dumps(pred.next_state, sort_keys=True)
                if key in seen:
                    continue
                if loaded.properties(pred.next_state).get(goal):
                    return depth
                seen.add(key)
                nxt.append(pred.next_state)
        frontier = nxt
    return None


def sample_package(sample: str) -> Any:
    from formal_lab_contracts import ModelSource
    from formal_lab_model import build_package, samples

    ir = getattr(samples, sample)()
    return build_package(ir, package_id=f"sample-{sample}", version=1,
                         source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(),
                                            origin=f"formal_lab_model.samples.{sample}"))


class ShortestPlanScorer:
    scorer_id = "synthetic.shortest-plan"
    version = "1"

    def score(self, parsed: Any, reference: dict[str, Any], *, repo_root: Path, truncated: bool) -> ScoreOutcome:
        pkg = sample_package(reference["sample"])
        if pkg.digest.value != reference["model_digest"]:
            raise InvalidInput(f"sample {reference['sample']} changed since the reference was fixed")
        loaded = _loaded(pkg)
        goal, bound = reference["goal"], int(reference["bound"])
        shortest = shortest_length(loaded, goal, bound)
        if shortest != reference["shortest_length"]:
            raise InvalidInput(f"reference shortest length {reference['shortest_length']} ≠ recomputed {shortest}")
        deps = {"sample_model": pkg.digest.value}
        na = "NOT_APPLICABLE"
        if not parsed.get("reachable"):
            ok = shortest is None
            return ScoreOutcome("CORRECT" if ok else "INCORRECT", "CORRECT" if ok else "INCORRECT", na,
                                f"claimed unreachable within {bound}; the interpreter finds "
                                f"{'none' if ok else f'a {shortest}-step plan'}", deps)
        by_label = {_label(a): a for a in loaded.ground_actions()}
        state = loaded.initial_state()
        for i, step in enumerate(parsed.get("plan") or []):
            action = by_label.get(str(step).strip())
            if action is None:
                return ScoreOutcome("INCORRECT", "INCORRECT", na, f"step {i + 1}: {step!r} is not an action of the "
                                    f"model (actions: {sorted(by_label)})", deps)
            pred = loaded.predict(state, action)
            if not pred.applicable or pred.next_state is None:
                return ScoreOutcome("INCORRECT", "INCORRECT", na,
                                    f"step {i + 1}: {step} is not applicable ({pred.reason or 'precondition false'})",
                                    deps)
            state = pred.next_state
        n = len(parsed.get("plan") or [])
        if not loaded.properties(state).get(goal):
            return ScoreOutcome("INCORRECT", "INCORRECT", na, f"the {n}-step plan is valid but {goal} does not hold "
                                "at its end", deps)
        if shortest is not None and n == shortest:
            return ScoreOutcome("CORRECT", "CORRECT", na, f"a valid shortest plan ({n} steps)", deps)
        return ScoreOutcome("PARTIAL", "CORRECT", na, f"a valid plan reaching {goal} in {n} steps; the shortest has "
                            f"{shortest}", deps)


register_scorer(DeviationDiagnosisScorer())
register_scorer(ShortestPlanScorer())
