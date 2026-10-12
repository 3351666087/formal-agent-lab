"""Research studies (phase 6A): a pre-registered `fal-research-study/v1` run against model providers, with the raw
answers saved first, independent scoring, and a report that keeps the two experiment lines apart.

    research/studies/<study_id>/study.json         the study (tasks, providers, assistance, replicates, limits …)
    research/results/<study_id>/ledger.jsonl       every response / evaluation event, append-only
                               responses/…json     fal-research-response/v1 — written before anything parses it
                               prompts/<digest>.json  exactly what was sent (system + user), by digest
                               evaluations/…json   fal-research-evaluation/v1 — the answer axis and the scores
                               report.json / report.md

    python -m formal_lab_eval.research run|score|report|show research/studies/<study_id>

Separation: a model gets only the task's listed `inputs` (plus `assisted_inputs` in ASSISTED mode); the `reference`
is read by the scorer only. Resume: a unit whose saved response carries an answer the provider made is reused (no
call); one that got no answer is called again as a new sample (a new sampling index; the earlier record and its
possibly-billed attempts stay in the ledger). Budget counters are rebuilt from the ledger, so a resumed study never
regains what it already spent. Rescoring (`score`) reuses saved responses and makes no call.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import signal
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from formal_lab_contracts import MetricDefinition, MetricResult
from formal_lab_contracts.errors import InvalidInput
from formal_lab_contracts.research import (
    MODEL_PRODUCED,
    AssistanceMode,
    ExperimentIdentity,
    ProviderConfig,
    ResearchEvaluation,
    ResearchResponse,
    ResearchStudy,
    StudyTask,
)
from formal_lab_strategies.model_clients import (
    ResearchBudget,
    ResearchRequest,
    read_setting,
    research_adapter,
    research_call,
    sha256_text,
)

from .research_scorers import load_rubric, parse_answer, scorer_for, sha256_bytes
from .stats import aggregate, paired_compare

# reused on resume: only a response the provider actually made (an answer, a refusal, an empty or a malformed body);
# an unavailable model, a rejected request or any failure is tried again — the route may have changed since
REUSABLE = MODEL_PRODUCED | {"MALFORMED_RESPONSE"}
NOT_SENT = {"BLOCKED_NO_CREDENTIAL", "CANCELLED", "BUDGET_EXHAUSTED"}
SYSTEM_PROMPT = ("You are taking part in a software-verification research study. Purpose of this task: {purpose}\n"
                 "Use only the material provided in the message. {format}")
FORMAT_JSON = "Reply with one JSON object that matches this JSON Schema, and nothing else:\n{schema}"
FORMAT_TEXT = "Reply in plain text."

METRICS = [
    MetricDefinition(metric_id="correct", label="正确", unit="rate", direction="HIGHER_IS_BETTER", aggregation="RATE",
                     value_type="bool", description="the scorer's CORRECT label; refusals, empty and invalid answers "
                     "count as not correct; units without a model-produced response are MISSING (never 0, never 1)",
                     observable="the scorer's behaviour label on a model-produced response"),
    MetricDefinition(metric_id="format_valid", label="格式有效", unit="rate", direction="HIGHER_IS_BETTER",
                     aggregation="RATE", value_type="bool", observable="answer parses and satisfies the task schema",
                     description="over responses with visible text"),
    MetricDefinition(metric_id="refused", label="拒绝", unit="rate", direction="NONE", aggregation="RATE",
                     value_type="bool", observable="provider-signalled refusal / content filter",
                     description="over model-produced responses"),
    MetricDefinition(metric_id="responded", label="有模型回答", unit="rate", direction="HIGHER_IS_BETTER",
                     aggregation="RATE", value_type="bool", observable="a model-produced response among sent calls",
                     description="units never sent (blocked / cancelled / budget) are NOT_APPLICABLE"),
    MetricDefinition(metric_id="program_corresponds", label="程序对应", unit="rate", direction="HIGHER_IS_BETTER",
                     aggregation="RATE", value_type="bool",
                     observable="the answer's model revision replayed on the recorded program run",
                     description="implementation_conformance only; NOT_APPLICABLE for synthetic tasks"),
    MetricDefinition(metric_id="output_tokens", label="输出 token", unit="tokens", direction="NONE",
                     aggregation="MEAN", value_type="int", observable="usage as reported; unknown usage is MISSING"),
    MetricDefinition(metric_id="latency_ms", label="耗时", unit="ms", direction="LOWER_IS_BETTER", aggregation="MEAN",
                     value_type="float", observable="wall time of the call, all attempts"),
]
METRIC_BY_ID = {m.metric_id: m for m in METRICS}


def repo_root_of(path: Path) -> Path:
    for p in (path.resolve(), *path.resolve().parents):
        if (p / "pyproject.toml").is_file() and (p / "packages").is_dir():
            return p
    raise InvalidInput(f"no repository root above {path}")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ------------------------------------------------------------------------------------------- the study definition
def load_study(study_dir: Path) -> ResearchStudy:
    study = ResearchStudy.model_validate_json((study_dir / "study.json").read_text())
    problems: list[str] = []
    seen_tasks, seen_providers = set(), set()
    for t in study.tasks:
        if t.task_id in seen_tasks:
            problems.append(f"task {t.task_id} defined twice")
        seen_tasks.add(t.task_id)
        files = [*t.inputs, *t.assisted_inputs, t.reference]
        for rel in files:
            if not (study_dir / rel).is_file():
                problems.append(f"{t.task_id}: {rel} does not exist")
        ref = study_dir / t.reference
        if ref.is_file():
            ref_sha = sha256_bytes(ref.read_bytes())
            for rel in [*t.inputs, *t.assisted_inputs]:
                p = study_dir / rel
                if rel == t.reference or (p.is_file() and sha256_bytes(p.read_bytes()) == ref_sha):
                    problems.append(f"{t.task_id}: REFERENCE_IN_TASK_INPUT — {rel} is (a copy of) the reference")
        if (t.track == "implementation_conformance") != bool(t.case_id):
            problems.append(f"{t.task_id}: implementation_conformance tasks name a case; synthetic ones do not")
        try:
            scorer_for(t.scorer_id, t.scorer_version)
        except InvalidInput as exc:
            problems.append(f"{t.task_id}: {exc.message}")
    for p in study.providers:
        if p.provider_config_id in seen_providers:
            problems.append(f"provider {p.provider_config_id} defined twice")
        seen_providers.add(p.provider_config_id)
    for c in study.comparisons:
        known = {"provider": seen_providers, "assistance": {m.value for m in AssistanceMode},
                 "representation": {t.representation_id for t in study.tasks}}[c.vary]
        for side in (c.a, c.b):
            if side not in known:
                problems.append(f"comparison {c.vary}: {side!r} is not one of {sorted(known)}")
    if study.primary_metric not in METRIC_BY_ID:
        problems.append(f"primary metric {study.primary_metric} is not one of {sorted(METRIC_BY_ID)}")
    try:
        load_rubric(repo_root_of(study_dir), study.rubric_id, study.rubric_version)
    except InvalidInput as exc:
        problems.append(exc.message)
    for t in study.tasks:  # P6B-01: the reference answer must not be reachable from the task inputs
        ref = study_dir / t.reference
        if ref.is_file():
            answer = (json.loads(ref.read_text()) or {}).get("answer")
            if answer is not None:
                needle = json.dumps(answer, sort_keys=True, ensure_ascii=False)
                seen = "\n".join((study_dir / rel).read_text() for rel in [*t.inputs, *t.assisted_inputs]
                                 if (study_dir / rel).is_file())
                if needle in seen or json.dumps(answer, ensure_ascii=False) in seen:
                    problems.append(f"{t.task_id}: ANSWER_LEAK — the reference answer appears in a task input")
    if problems:
        raise InvalidInput("study does not validate: " + "; ".join(problems))
    return study


def task_digest(study_dir: Path, task: StudyTask) -> str:
    """What defines the task as posed: question, format, schema, representation and the input files' content."""
    return sha256_text({"question": task.question, "answer_format": task.answer_format, "schema": task.answer_schema,
                        "representation": [task.representation_id, task.representation_version],
                        "purpose": task.purpose, "bound": task.bound,
                        "inputs": [[rel, sha256_bytes((study_dir / rel).read_bytes())] for rel in task.inputs]})


def render(study_dir: Path, task: StudyTask, mode: str) -> ResearchRequest:
    fmt = FORMAT_JSON.format(schema=json.dumps(task.answer_schema, ensure_ascii=False)) \
        if task.answer_format == "json" else FORMAT_TEXT
    parts = [task.question]
    for rel in task.inputs:
        parts.append(f"--- {rel} ---\n{(study_dir / rel).read_text()}")
    if mode == "ASSISTED":
        for rel in task.assisted_inputs:
            parts.append(f"--- assistance: {rel} ---\n{(study_dir / rel).read_text()}")
    return ResearchRequest(system=SYSTEM_PROMPT.format(purpose=task.purpose, format=fmt), user="\n\n".join(parts))


def cap_params(cfg: ProviderConfig, limit: int) -> dict[str, Any]:
    """The configured parameters, with the output-token cap of the study enforced (recorded exactly as sent)."""
    p = dict(cfg.params)
    if cfg.api == "anthropic.messages":
        p["max_tokens"] = min(int(p.get("max_tokens", limit)), limit)
    elif "max_tokens" in p:
        p["max_tokens"] = min(int(p["max_tokens"]), limit)
    else:
        p["max_completion_tokens"] = min(int(p.get("max_completion_tokens", limit)), limit)
    return p


@dataclass
class Unit:
    unit_id: str
    task: StudyTask
    provider: ProviderConfig
    mode: str
    replicate: int


def plan_units(study: ResearchStudy) -> tuple[list[Unit], list[dict[str, str]]]:
    """Every (task × provider × assistance × replicate); a mode a task does not define is NOT_RUN (listed, no units)."""
    units, not_run = [], []
    for t in study.tasks:
        for mode in study.assistance_modes:
            if mode == "ASSISTED" and not t.assisted_inputs:
                not_run.append({"task_id": t.task_id, "mode": mode.value,
                                "reason": "the task defines no assistance material"})
                continue
            for p in study.providers:
                for r in range(study.replicates):
                    short = "S" if mode == "STATIC_UNASSISTED" else "A"
                    units.append(Unit(f"{t.task_id}.{p.provider_config_id}.{short}.r{r}", t, p, mode.value, r))
    return units, not_run


# ---------------------------------------------------------------------------------------------------------- ledger
class Ledger:
    def __init__(self, results_dir: Path):
        self.dir = results_dir
        self.path = results_dir / "ledger.jsonl"

    def events(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def append(self, event: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({**event, "at": _now()}, ensure_ascii=False, sort_keys=True) + "\n")

    def budget(self, study: ResearchStudy) -> ResearchBudget:
        b = ResearchBudget(max_calls=study.limits.max_calls, max_http_attempts=study.limits.max_http_attempts,
                           max_total_output_tokens=study.limits.max_total_output_tokens)
        for e in self.events():
            if e["event"] == "response":
                b.calls += e["calls"]
                b.http_attempts += e["http_attempts"]
                b.output_tokens += e["output_tokens"]
                b.possibly_billed += e["possibly_billed"]
                b.unknown_usage_calls += e.get("unknown_usage", 0)
        return b

    def latest_responses(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in self.events():
            if e["event"] == "response":
                out[e["unit_id"]] = e
        return out


def reuse_key(unit: Unit, digest: str, endpoint: str, study_dir: Path) -> str:
    """The credential *setting* is part of the provider configuration: on a relay the key selects the account /
    channel group, so a sample made under another credential is not reused (the value itself is never hashed)."""
    assist = [[rel, sha256_bytes((study_dir / rel).read_bytes())] for rel in unit.task.assisted_inputs] \
        if unit.mode == "ASSISTED" else []
    p = unit.provider
    return sha256_text({"case": [unit.task.case_id, unit.task.case_version], "task": unit.task.task_id,
                        "task_digest": digest, "provider": [p.provider, p.api, p.api_version, str(p.route), endpoint,
                                                            p.model, p.params, p.api_key_setting],
                        "assistance": [unit.mode, assist], "replicate": unit.replicate})


# ------------------------------------------------------------------------------------------------------------ run
def run_study(study_dir: Path, results_dir: Path | None = None, *, cancel: threading.Event | None = None,
              setting: Any = read_setting, transport: Any = None, timeout_s: float = 180.0,
              after_unit: Any = None, log: Any = print) -> dict[str, Any]:
    study_dir = study_dir.resolve()
    study = load_study(study_dir)
    root = repo_root_of(study_dir)
    results_dir = (results_dir or root / "research" / "results" / study.study_id).resolve()
    ledger = Ledger(results_dir)
    budget = ledger.budget(study)
    latest = ledger.latest_responses()
    units, not_run = plan_units(study)
    adapters: dict[str, tuple[Any, str | None]] = {}
    tally: Counter = Counter()
    for unit in units:
        p = unit.provider
        if p.provider_config_id not in adapters:
            adapters[p.provider_config_id] = research_adapter(p, setting=setting, transport=transport,
                                                              timeout_s=timeout_s)
        adapter, why = adapters[p.provider_config_id]
        digest = task_digest(study_dir, unit.task)
        key = reuse_key(unit, digest, adapter.endpoint if adapter else (p.base_url_setting or p.base_url or ""),
                        study_dir)
        prev = latest.get(unit.unit_id)
        if prev and prev["reuse_key"] == key and prev["outcome"] in REUSABLE:
            tally["reused"] += 1
            continue
        index = prev["sampling_index"] + 1 if prev else 0
        req = render(study_dir, unit.task, unit.mode)
        req.params = cap_params(p, study.limits.max_output_tokens_per_call)
        before = (budget.calls, budget.http_attempts, budget.output_tokens, budget.possibly_billed,
                  budget.unknown_usage_calls)
        res = research_call(adapter, req, provider_config_id=p.provider_config_id, route=str(p.route), budget=budget,
                            cancel=cancel, network_retries=study.limits.network_retries, blocked_reason=why,
                            provider=p.provider, api=p.api, model=p.model)
        sent = {"system": req.system, "user": req.user}
        sent_digest = sha256_text(sent)
        experiment = ExperimentIdentity(
            study_id=study.study_id, unit_id=unit.unit_id, track=unit.task.track, case_id=unit.task.case_id,
            case_version=unit.task.case_version, task_id=unit.task.task_id, task_digest=digest,
            representation_id=unit.task.representation_id, replicate_id=unit.replicate,
            assistance_mode=unit.mode, sampling_id=f"{unit.unit_id}#{index}")
        response = ResearchResponse(experiment=experiment, call=res.call, raw=res.raw, status=res.status,
                                    cost=res.cost, task_input_digest=sent_digest, reuse_key=key, recorded_at=_now())
        rel = f"responses/{unit.unit_id}--{index}.json"
        data = (response.model_dump_json(indent=1) + "\n").encode()
        (results_dir / "responses").mkdir(parents=True, exist_ok=True)
        (results_dir / rel).write_bytes(data)  # the raw record, before anything parses or scores it
        prompt = results_dir / "prompts" / f"{sent_digest[:24]}.json"
        if not prompt.exists():
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text(json.dumps(sent, ensure_ascii=False, indent=1) + "\n")
        after = (budget.calls, budget.http_attempts, budget.output_tokens, budget.possibly_billed,
                 budget.unknown_usage_calls)
        ledger.append({"event": "response", "unit_id": unit.unit_id, "sampling_index": index, "path": rel,
                       "digest": sha256_bytes(data), "outcome": str(res.status.outcome), "reuse_key": key,
                       "calls": after[0] - before[0], "http_attempts": after[1] - before[1],
                       "output_tokens": after[2] - before[2], "possibly_billed": after[3] - before[3],
                       "unknown_usage": after[4] - before[4]})
        tally[str(res.status.outcome)] += 1
        tally["new"] += 1
        log(f"  {unit.unit_id}: {res.status.outcome}"
            + (f" (model {res.call.model_returned})" if res.call.model_returned else ""))
        if after_unit is not None:
            after_unit(unit, res)
    for a, _ in adapters.values():
        if a is not None:
            a.close()
    evaluations = score_study(study_dir, results_dir, log=log)
    report = build_report(study_dir, results_dir)
    return {"study_id": study.study_id, "results": str(results_dir), "units": len(units), "not_run": not_run,
            "tally": dict(tally), "evaluations": len(evaluations), "budget": budget.__dict__,
            "report_outcomes": {t: r["outcomes"] for t, r in report["tracks"].items()}}


# ---------------------------------------------------------------------------------------------------------- score
def _metric(unit_id: str, metric_id: str, value: float | None, status: str = "OK", why: str | None = None
            ) -> MetricResult:
    d = METRIC_BY_ID[metric_id]
    return MetricResult(metric_id=metric_id, metric_version=d.version, subject=unit_id, value=value,
                        status=status if value is not None or status != "OK" else "MISSING",
                        missing_reason=why, unit=d.unit)


def evaluate(study_dir: Path, results_dir: Path, task: StudyTask, response: ResearchResponse, rel: str,
             response_digest: str, rubric: tuple[str, str]) -> ResearchEvaluation:
    scorer = scorer_for(task.scorer_id, task.scorer_version)
    ref_bytes = (study_dir / task.reference).read_bytes()
    reference = json.loads(ref_bytes)
    outcome = str(response.status.outcome)
    status, parsed, note = parse_answer(task.answer_format, task.answer_schema, outcome, response.raw.visible_text)
    finish = str(response.raw.finish_class)
    refusal = "CONTENT_FILTER" if finish == "CONTENT_FILTER" else \
        ("EXPLICIT_REFUSAL" if outcome == "CONTENT_REFUSAL" else "NONE")
    synthetic = str(task.track) == "synthetic_representation"
    model_internal, program = "NOT_EVALUATED", "NOT_APPLICABLE" if synthetic else "NOT_EVALUATED"
    deps: dict[str, str] = {}
    signals: dict[str, Any] = {}
    explanation = note
    if outcome in NOT_SENT:
        behavior, explanation = "NOT_RUN", f"not sent: {response.status.note or outcome}"
    elif outcome not in MODEL_PRODUCED:
        behavior, explanation = "NO_MODEL_ANSWER", f"no model answer: {outcome} {response.status.note or ''}".strip()
    elif outcome == "CONTENT_REFUSAL":
        behavior, explanation = "REFUSED", f"provider-signalled refusal ({finish})"
    elif status == "EMPTY":
        behavior = "EMPTY"
    elif status != "VALID":
        behavior = "INVALID_FORMAT"
    else:
        so = scorer.score(parsed, reference, repo_root=repo_root_of(study_dir), truncated=outcome == "TRUNCATED")
        behavior, model_internal, deps, explanation = so.behavior, so.model_internal, so.dependencies, so.explanation
        signals = so.signals
        program = "NOT_APPLICABLE" if synthetic else so.program_correspondence
        if outcome == "TRUNCATED":
            explanation += " (answer truncated at the output limit)"
    uid = response.experiment.unit_id
    produced = outcome in MODEL_PRODUCED
    has_text = outcome in ("ANSWERED", "TRUNCATED") and bool((response.raw.visible_text or "").strip())
    metrics = [
        _metric(uid, "correct", (1.0 if behavior == "CORRECT" else 0.0) if produced else None,
                why=None if produced else f"no model-produced response ({outcome})"),
        _metric(uid, "format_valid", (1.0 if status == "VALID" else 0.0) if has_text else None,
                why=None if has_text else f"no visible answer ({outcome})"),
        _metric(uid, "refused", (1.0 if outcome == "CONTENT_REFUSAL" else 0.0) if produced else None,
                why=None if produced else f"no model-produced response ({outcome})"),
        _metric(uid, "responded", None if outcome in NOT_SENT else (1.0 if produced else 0.0),
                status="NOT_APPLICABLE" if outcome in NOT_SENT else "OK",
                why=f"not sent ({outcome})" if outcome in NOT_SENT else None),
        _metric(uid, "program_corresponds", None if synthetic or program not in ("CORRESPONDS", "DEVIATES")
                else (1.0 if program == "CORRESPONDS" else 0.0),
                status="NOT_APPLICABLE" if synthetic else "OK",
                why="not applicable to a synthetic task" if synthetic else
                (None if program in ("CORRESPONDS", "DEVIATES") else f"program correspondence {program}")),
        _metric(uid, "output_tokens", float(response.cost.output_tokens) if response.cost.usage_known else None,
                why=None if response.cost.usage_known else "usage not reported"),
        _metric(uid, "latency_ms", response.cost.latency_ms if response.cost.http_attempts else None,
                status="OK" if response.cost.http_attempts else "NOT_APPLICABLE",
                why=None if response.cost.http_attempts else "nothing sent"),
    ]
    key = scoring_key(response_digest, task, sha256_bytes(ref_bytes), rubric)
    return ResearchEvaluation(study_id=response.experiment.study_id, unit_id=uid, response_digest=response_digest,
                              response_path=rel, scorer_id=task.scorer_id, scorer_version=task.scorer_version,
                              reference_sha256=sha256_bytes(ref_bytes), dependency_digests=deps,
                              call_outcome=outcome, answer_status=status, parsed=parsed, behavior_label=behavior,
                              refusal_status=refusal, model_internal=model_internal, program_correspondence=program,
                              metrics=metrics, rubric_signals=signals, explanation=explanation[:2000],
                              scoring_reuse_key=key)


def scoring_key(response_digest: str, task: StudyTask, reference_sha: str, rubric: tuple[str, str]) -> str:
    return sha256_text({"response": response_digest, "scorer": [task.scorer_id, task.scorer_version],
                        "reference": reference_sha, "rubric": list(rubric), "format": task.answer_format,
                        "schema": task.answer_schema})


def score_study(study_dir: Path, results_dir: Path, *, force: bool = False, log: Any = print
                ) -> list[ResearchEvaluation]:
    """Score the latest response of every unit. An evaluation with the same scoring key is reused; no model call."""
    study_dir = study_dir.resolve()
    study = load_study(study_dir)
    tasks = {t.task_id: t for t in study.tasks}
    ledger = Ledger(results_dir)
    done = {e["scoring_reuse_key"]: e for e in ledger.events() if e["event"] == "evaluation"}
    out = []
    for unit_id, ev in sorted(ledger.latest_responses().items()):
        data = (results_dir / ev["path"]).read_bytes()
        if sha256_bytes(data) != ev["digest"]:
            raise InvalidInput(f"response {ev['path']} changed after it was recorded")
        response = ResearchResponse.model_validate_json(data)
        task = tasks[response.experiment.task_id]
        ref_sha = sha256_bytes((study_dir / task.reference).read_bytes())
        key = scoring_key(ev["digest"], task, ref_sha, (study.rubric_id, study.rubric_version))
        path = results_dir / "evaluations" / f"{unit_id}--{ev['sampling_index']}.json"
        if not force and key in done and path.is_file():
            out.append(ResearchEvaluation.model_validate_json(path.read_text()))
            continue
        evaluation = evaluate(study_dir, results_dir, task, response, ev["path"], ev["digest"],
                              (study.rubric_id, study.rubric_version))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(evaluation.model_dump_json(indent=1) + "\n")
        ledger.append({"event": "evaluation", "unit_id": unit_id, "path": str(path.relative_to(results_dir)),
                       "scoring_reuse_key": key, "behavior": str(evaluation.behavior_label)})
        out.append(evaluation)
    return out


# --------------------------------------------------------------------------------------------------------- report
def build_report(study_dir: Path, results_dir: Path) -> dict[str, Any]:
    """Per track (never pooled): outcome and behaviour counts over the planned units, metric aggregates, cost and
    identity per condition; pre-registered paired comparisons along one dimension at a time."""
    study_dir = study_dir.resolve()
    study = load_study(study_dir)
    providers = {p.provider_config_id: p for p in study.providers}
    tasks = {t.task_id: t for t in study.tasks}
    units, not_run = plan_units(study)
    ledger = Ledger(results_dir)
    latest = ledger.latest_responses()
    events = ledger.events()
    evals: dict[str, ResearchEvaluation] = {}
    for unit_id, ev in latest.items():
        p = results_dir / "evaluations" / f"{unit_id}--{ev['sampling_index']}.json"
        if p.is_file():
            evals[unit_id] = ResearchEvaluation.model_validate_json(p.read_text())
    responses = {u: ResearchResponse.model_validate_json((results_dir / ev["path"]).read_text())
                 for u, ev in latest.items()}
    tracks: dict[str, dict[str, Any]] = {}
    for track in sorted({str(t.track) for t in study.tasks}):
        t_units = [u for u in units if str(u.task.track) == track]
        conds: dict[str, list[str]] = defaultdict(list)
        for u in t_units:
            conds[f"{u.provider.provider_config_id} · {u.mode} · {u.task.representation_id}"].append(u.unit_id)
        rows = []
        for cond, ids in sorted(conds.items()):
            outcomes = Counter(str(responses[i].status.outcome) if i in responses else "NOT_RECORDED" for i in ids)
            behaviors = Counter(str(evals[i].behavior_label) if i in evals else "NOT_SCORED" for i in ids)
            metrics = {}
            for m in METRICS:
                res = [r for i in ids if i in evals for r in evals[i].metrics if r.metric_id == m.metric_id]
                agg, notes = aggregate(m, res, cond)
                metrics[m.metric_id] = {"value": agg.value, "status": str(agg.status), "n": notes["n"],
                                        "missing": notes["missing"], "not_applicable": notes["not_applicable"],
                                        "ci": agg.ci.model_dump() if agg.ci else None, "missing_reason":
                                        agg.missing_reason}
            sig_keys = sorted({k for i in ids if i in evals for k in evals[i].rubric_signals})
            signals = {}
            for k in sig_keys:
                vals = [evals[i].rubric_signals[k] for i in ids if i in evals and k in evals[i].rubric_signals
                        and evals[i].rubric_signals[k] is not None]
                signals[k] = {"true": sum(1 for v in vals if v), "n": len(vals)}
            rs = [responses[i] for i in ids if i in responses]
            cost = {"calls_sent": sum(1 for r in rs if r.cost.http_attempts),
                    "http_attempts": sum(r.cost.http_attempts for r in rs),
                    "confirmed_input_tokens": sum(r.cost.input_tokens or 0 for r in rs if r.cost.usage_known),
                    "confirmed_output_tokens": sum(r.cost.output_tokens or 0 for r in rs if r.cost.usage_known),
                    "usage_unknown_calls": sum(1 for r in rs if r.cost.http_attempts and not r.cost.usage_known),
                    "possibly_billed_unconfirmed": sum(r.cost.possibly_billed_unconfirmed for r in rs)}
            identity = Counter(f"{r.call.route}/{r.call.model_identity}: requested {r.call.model_requested}, "
                               f"returned {r.call.model_returned}" for r in rs)
            rows.append({"condition": cond, "planned": len(ids), "outcomes": dict(outcomes),
                         "behaviors": dict(behaviors), "metrics": metrics, "cost": cost,
                         "identity": dict(identity), "rubric_signals": signals})
        comparisons = []
        primary = METRIC_BY_ID[study.primary_metric]
        for c in study.comparisons:
            side: dict[str, dict[Any, MetricResult]] = {c.a: {}, c.b: {}}
            for u in t_units:
                value = {"provider": u.provider.provider_config_id, "assistance": u.mode,
                         "representation": u.task.representation_id}[c.vary]
                if value not in side or u.unit_id not in evals:
                    continue
                key = {"provider": (u.task.task_id, u.mode, u.replicate),
                       "assistance": (u.task.task_id, u.provider.provider_config_id, u.replicate),
                       "representation": (u.task.reference, u.provider.provider_config_id, u.mode, u.replicate)
                       }[c.vary]
                metric = next(r for r in evals[u.unit_id].metrics if r.metric_id == primary.metric_id)
                side[value][key] = metric
            planned = {v: sum(1 for u in t_units if {"provider": u.provider.provider_config_id, "assistance": u.mode,
                                                      "representation": u.task.representation_id}[c.vary] == v)
                       for v in (c.a, c.b)}
            if not planned[c.a] or not planned[c.b]:
                empty = c.a if not planned[c.a] else c.b
                comparisons.append({"vary": c.vary, "a": c.a, "b": c.b, "note": c.note, "not_applicable":
                                    f"this track plans no unit with {c.vary} = {empty}"})
                continue
            cmp = paired_compare(primary, c.a, c.b, side[c.a], side[c.b]).as_dict()
            if c.vary == "provider":
                cmp["comparability"] = {
                    s: {"route": str(providers[s].route), "model": providers[s].model, "params": providers[s].params,
                        "note": providers[s].comparability_note} for s in (c.a, c.b)}
                cmp["comparability_note"] = ("parameters are recorded, not equated: equal names (e.g. two 'high' "
                                             "settings) do not mean equal compute, and a fixed seed on a real API "
                                             "does not reproduce an answer")
            comparisons.append({"vary": c.vary, "note": c.note, **cmp})
        all_out = Counter()
        for row in rows:
            all_out.update(row["outcomes"])
        tracks[track] = {"conditions": rows, "comparisons": comparisons, "outcomes": dict(all_out),
                         "planned": len(t_units)}
    report = {
        "study_id": study.study_id, "title": study.title, "generated_at": _now(), "results_dir": str(results_dir),
        "primary_metric": study.primary_metric, "rubric": [study.rubric_id, study.rubric_version],
        "rubric_digest": load_rubric(repo_root_of(study_dir), study.rubric_id, study.rubric_version)["digest"],
        "replicates": study.replicates, "limits": study.limits.model_dump(), "missing_policy": study.missing_policy,
        "tracks": tracks, "not_run": not_run,
        "ledger": {"responses": sum(1 for e in events if e["event"] == "response"),
                   "evaluations": sum(1 for e in events if e["event"] == "evaluation"),
                   "calls": sum(e.get("calls", 0) for e in events if e["event"] == "response"),
                   "http_attempts": sum(e.get("http_attempts", 0) for e in events if e["event"] == "response"),
                   "possibly_billed": sum(e.get("possibly_billed", 0) for e in events if e["event"] == "response")},
        "notes": ["the two experiment lines are reported apart and never pooled into one success rate",
                  "model scores count only responses the model produced; transport / auth / limit / budget / cancel "
                  "/ blocked units are MISSING (never 0, never 1); refusals and invalid answers count as not correct",
                  "a relay route reports a model name it cannot prove; conclusions about a provider's model need a "
                  "route whose identity is verifiable", "tasks: " + ", ".join(sorted(tasks))],
    }
    (results_dir / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n")
    (results_dir / "report.md").write_text(to_markdown(report))
    return report


def _fmt(v: Any) -> str:
    return "—" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


def to_markdown(report: dict[str, Any]) -> str:
    lines = [f"# {report['title']}", "", f"Study `{report['study_id']}` · primary metric `{report['primary_metric']}` · "
             f"rubric {report['rubric'][0]}@{report['rubric'][1]} · {report['replicates']} replicate(s) per condition",
             "", f"Ledger: {report['ledger']['responses']} response record(s), {report['ledger']['calls']} call(s), "
             f"{report['ledger']['http_attempts']} HTTP attempt(s), {report['ledger']['possibly_billed']} possibly "
             "billed unconfirmed attempt(s).", ""]
    for track, t in report["tracks"].items():
        lines += [f"## Track `{track}` — {t['planned']} planned unit(s)", "",
                  "| condition | planned | call outcomes | behaviour | correct | format valid | refused | "
                  "program corresponds | out tokens | identity |", "|---|---|---|---|---|---|---|---|---|---|"]
        for row in t["conditions"]:
            m = row["metrics"]

            def cell(mid: str, m: dict[str, Any] = m) -> str:
                x = m[mid]
                if x["status"] != "OK":
                    return f"{x['status']} (n={x['n']}, missing {x['missing']}, n/a {x['not_applicable']})"
                return f"{_fmt(x['value'])} (n={x['n']}, missing {x['missing']})"

            lines.append(f"| {row['condition']} | {row['planned']} | "
                         f"{', '.join(f'{k} {v}' for k, v in sorted(row['outcomes'].items()))} | "
                         f"{', '.join(f'{k} {v}' for k, v in sorted(row['behaviors'].items()))} | {cell('correct')} | "
                         f"{cell('format_valid')} | {cell('refused')} | {cell('program_corresponds')} | "
                         f"{cell('output_tokens')} | {'; '.join(row['identity'])} |")
        sig = [row for row in t["conditions"] if row.get("rubric_signals")]
        if sig:
            lines += ["", "Rubric signals (heuristic, recorded only — not adjudicated, no human review):"]
            for row in sig:
                lines.append(f"- {row['condition']}: " + ", ".join(
                    f"{k} {v['true']}/{v['n']}" for k, v in sorted(row["rubric_signals"].items())))
        for c in t["comparisons"]:
            if c.get("not_applicable"):
                lines += ["", f"**Paired ({c['vary']}): {c['a']} vs {c['b']}** — not applicable: {c['not_applicable']}"]
                continue
            lines += ["", f"**Paired ({c['vary']}): {c['a']} vs {c['b']}** — {c['n_pairs']} pair(s), "
                      f"{c['unpaired']} unpaired; mean difference (b − a) {_fmt(c['mean_diff_b_minus_a'])}; "
                      f"{c['reading_note']}"]
            if c.get("comparability_note"):
                lines.append(f"> {c['comparability_note']}")
        lines.append("")
    if report["not_run"]:
        lines += ["## Not run", ""] + [f"- {x['task_id']} · {x['mode']}: {x['reason']}" for x in report["not_run"]]
    lines += ["", "## Notes", ""] + [f"- {n}" for n in report["notes"]]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------------------ CLI
def show_unit(results_dir: Path, unit_id: str) -> dict[str, Any]:
    ev = Ledger(results_dir).latest_responses().get(unit_id)
    if ev is None:
        raise InvalidInput(f"no response recorded for {unit_id}")
    response = json.loads((results_dir / ev["path"]).read_text())
    path = results_dir / "evaluations" / f"{unit_id}--{ev['sampling_index']}.json"
    return {"response": response, "evaluation": json.loads(path.read_text()) if path.is_file() else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="run, rescore, report or show a fal-research-study/v1")
    ap.add_argument("command", choices=["run", "score", "report", "show", "plan"])
    ap.add_argument("study_dir", type=Path)
    ap.add_argument("--results", type=Path, default=None)
    ap.add_argument("--unit", default=None)
    ap.add_argument("--force", action="store_true", help="score: recompute evaluations even when reusable")
    args = ap.parse_args(argv)
    study = load_study(args.study_dir)
    results = (args.results or repo_root_of(args.study_dir) / "research" / "results" / study.study_id).resolve()
    if args.command == "plan":
        units, not_run = plan_units(study)
        print(json.dumps({"study_id": study.study_id, "units": [u.unit_id for u in units], "not_run": not_run,
                          "limits": study.limits.model_dump()}, indent=1, ensure_ascii=False))
    elif args.command == "run":
        cancel = threading.Event()
        with contextlib.suppress(ValueError):  # not in the main thread
            signal.signal(signal.SIGINT, lambda *_: cancel.set())
        print(json.dumps(run_study(args.study_dir, results, cancel=cancel), indent=1, ensure_ascii=False,
                         default=str))
    elif args.command == "score":
        print(f"{len(score_study(args.study_dir, results, force=args.force))} evaluation(s)")
        build_report(args.study_dir, results)
    elif args.command == "report":
        print(to_markdown(build_report(args.study_dir, results)))
    else:
        print(json.dumps(show_unit(results, args.unit or ""), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
