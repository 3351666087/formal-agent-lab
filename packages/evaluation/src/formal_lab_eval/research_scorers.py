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
    signals: dict[str, Any] = field(default_factory=dict)  # recorded-only heuristic rubric signals (not adjudicated)


def rubric_digest(doc: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in doc.items() if k != "digest"}, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def load_rubric(repo_root: Path, rubric_id: str, version: str) -> dict[str, Any]:
    """The frozen rubric (version + self-digest); the digest is recomputed and checked, so an edit needs a new file."""
    path = repo_root / "research" / "rubric" / f"{rubric_id}-{version}.json"
    if not path.is_file():
        raise InvalidInput(f"no rubric {rubric_id}@{version} at {path}")
    doc = json.loads(path.read_text())
    if doc.get("digest") != rubric_digest(doc):
        raise InvalidInput(f"rubric {rubric_id}@{version} digest mismatch: it was edited without a new version")
    if (doc.get("rubric_id"), str(doc.get("version"))) != (rubric_id, version):
        raise InvalidInput(f"rubric file names {doc.get('rubric_id')}@{doc.get('version')}, not {rubric_id}@{version}")
    return doc


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


# ----------------------------------------------------------------- orders.isolation-judgment@1 (implementation)
_SCOPE_WORDS = ("recorded", "observed", "within", "scope", "grant", "attempts", "assume", "assumption", "cannot "
                "conclude", "only the")
_RISK_WORDS = ("cross-tenant", "cross tenant", "another tenant", "other tenant", "unauthori", "not granted",
               "isolation", "leak", "access control")


class IsolationJudgmentScorer:
    """The answer judges whether tenant isolation held on a recorded run of the order service (phase-5B case). Truth
    is read from the recorded observation (an ungranted access that returned another tenant's data is a violation);
    program correspondence is the 5B conformance verdict (DEVIATES = violated, CORRESPONDS = held). The model's
    `isolation_holds` is scored against that; naming a correct violation and stating scope / the risk are recorded as
    heuristic signals only (no human review, never promoted to a pass)."""

    scorer_id = "orders.isolation-judgment"
    version = "1"

    def score(self, parsed: Any, reference: dict[str, Any], *, repo_root: Path, truncated: bool) -> ScoreOutcome:
        obs_bytes = _evidence(repo_root, reference["observation"])
        conf_bytes = _evidence(repo_root, reference["conformance"])
        observation = json.loads(obs_bytes)
        conformance = json.loads(conf_bytes)
        deps = {"observation": sha256_bytes(obs_bytes), "conformance": sha256_bytes(conf_bytes)}
        # truth from the recorded run: an ungranted access that was allowed (returned the tenant's data) is a violation
        violations = [{"subject": a["subject"], "tenant": a["tenant"], "access": a["access"]}
                      for a in observation["attempts"] if not a["granted"] and a["observed_allowed"] is True]
        truth_holds = not violations
        corr = conformance["correspondence"]  # the independent 5B program oracle
        program = "CORRESPONDS" if (corr == "CORRESPONDS") == truth_holds else "UNKNOWN"
        model_holds = parsed.get("isolation_holds")
        model_violations = {(v.get("subject"), v.get("tenant")) for v in (parsed.get("violations") or [])
                            if isinstance(v, dict)}
        truth_pairs = {(v["subject"], v["tenant"]) for v in violations}
        rationale = " ".join(str(parsed.get(k, "")) for k in ("rationale", "assumptions")).lower()
        signals = {
            "violation_identified": None if truth_holds else bool(model_violations & truth_pairs),
            "no_false_violation": (not (model_violations - truth_pairs)) if model_violations else None,
            "states_scope": any(w in rationale for w in _SCOPE_WORDS),
            "names_isolation_risk": any(w in rationale for w in _RISK_WORDS)}
        correct = model_holds is truth_holds
        exp = ("isolation holds (every ungranted access was denied)" if truth_holds
               else f"isolation is violated: {truth_pairs} returned another tenant's data")
        return ScoreOutcome(
            "CORRECT" if correct else "INCORRECT", "CORRECT" if correct else "INCORRECT",
            program if correct else "DEVIATES",
            f"model said isolation_holds={model_holds}; the recorded {observation['mode']} run shows {exp}; the 5B "
            f"conformance verdict is {corr}" + ("" if truth_holds or not model_violations
                                                else f"; model named violations {sorted(model_violations)}"),
            deps, signals)


# ----------------------------------------------------------------- ratelimit.capacity-judgment@1 (phase 7 held-out)
class CapacityJudgmentScorer:
    """The answer judges whether a token-bucket limiter kept within its capacity on a recorded run (phase-7 held-out
    case). Truth is read from the recorded observation (any observed token count above capacity is a violation);
    program correspondence is the case's conformance verdict. The model's `within_capacity` is scored against that."""

    scorer_id = "ratelimit.capacity-judgment"
    version = "1"

    def score(self, parsed: Any, reference: dict[str, Any], *, repo_root: Path, truncated: bool) -> ScoreOutcome:
        obs_bytes = _evidence(repo_root, reference["observation"])
        conf_bytes = _evidence(repo_root, reference["conformance"])
        observation = json.loads(obs_bytes)
        conformance = json.loads(conf_bytes)
        deps = {"observation": sha256_bytes(obs_bytes), "conformance": sha256_bytes(conf_bytes)}
        cap = observation["capacity"]
        overflow = next((s["index"] for s in observation["steps"] if s["observed_tokens"] > cap), None)
        truth_holds = overflow is None
        corr = conformance["correspondence"]
        program = "CORRESPONDS" if (corr == "CORRESPONDS") == truth_holds else "UNKNOWN"
        model_holds = parsed.get("within_capacity")
        correct = model_holds is truth_holds
        rationale = str(parsed.get("rationale", "")).lower()
        signals = {"identifies_overflow_step": None if truth_holds else (parsed.get("first_overflow") == overflow),
                   "states_capacity": str(cap) in rationale or "capacity" in rationale}
        exp = "stayed within capacity" if truth_holds else f"exceeded capacity at step {overflow}"
        return ScoreOutcome(
            "CORRECT" if correct else "INCORRECT", "CORRECT" if correct else "INCORRECT",
            program if correct else "DEVIATES",
            f"model said within_capacity={model_holds}; the recorded {observation['mode']} run {exp} "
            f"(capacity {cap}); the case conformance verdict is {corr}", deps, signals)


# --------------------------------------------------------------- attackgraph.analysis@1 (phase 8, verifier-grounded)
class AttackGraphAnalysisScorer:
    """Hard defensive attack-graph analysis questions whose ground truth is the Z3 verifier / model semantics, not a
    human opinion (phase 8): shortest attack-path cost, target reachability under a deployed defence set, the minimum
    number of defences that cut every path (AND/OR min-cut), and whether a derived step is enabled. The model's answer
    is scored against the machine-checked truth stored in the reference; `program_correspondence` records whether the
    answer agrees with the verifier."""

    scorer_id = "attackgraph.analysis"
    version = "1"

    def score(self, parsed: Any, reference: dict[str, Any], *, repo_root: Path, truncated: bool) -> ScoreOutcome:
        kind = reference["question_kind"]
        answer = reference["answer"]["value"]  # wrapped {"value": …} so it cannot leak into the task input
        deps = {"ground_truth": sha256_bytes(json.dumps({"k": kind, "a": answer, "g": reference.get("graph_digest")},
                                                        sort_keys=True).encode())}
        fields = {"shortest_cost": "cost", "reachability": "reachable", "min_defense": "count",
                  "step_enabled": "enabled", "reach_from_entry": "reachable", "chokepoints": "count"}
        key = fields[kind]
        got = parsed.get(key) if isinstance(parsed, dict) else None
        if kind in ("shortest_cost", "min_defense", "chokepoints"):
            got = None if got is None else (int(got) if str(got).lstrip("-").isdigit() else got)
        correct = got == answer
        rationale = str(parsed.get("rationale", "")).lower() if isinstance(parsed, dict) else ""
        signals = {"answered_field": got is not None,
                   "explains": len(rationale) > 40,
                   "cites_structure": any(w in rationale for w in ("and", "or", "parent", "path", "cut", "reach"))}
        verdict = "CORRECT" if correct else "INCORRECT"
        return ScoreOutcome(verdict, verdict, "CORRESPONDS" if correct else "DEVIATES",
                            f"{kind}: model answered {got!r}, the verifier-checked answer is {answer!r}", deps, signals)


register_scorer(DeviationDiagnosisScorer())
register_scorer(ShortestPlanScorer())
register_scorer(IsolationJudgmentScorer())
register_scorer(CapacityJudgmentScorer())
register_scorer(AttackGraphAnalysisScorer())
