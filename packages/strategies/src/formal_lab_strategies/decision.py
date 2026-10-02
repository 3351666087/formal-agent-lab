"""Reusable model decision (phase 4A, A3): one structured model choice with call records, budget and provenance.

A domain strategy describes *what may be chosen* and gets back a decision it can turn into a standard ActionProposal
or TaskPlan — no client handling, no accounting of its own:

    decider = ModelDecider(client_from_settings(config, services))
    decision = decider.decide(choose_request(options, goal=..., explanation=...), context=planning_context)
    proposal = decision.proposal(context, chosen_action, strategy_ref, fallback=...)

What a strategy passes and where it comes from:

  options      the allowed candidates / tasks — from the kernel (`PlanningContext.candidates`, already computed on the
               participant's projected belief) or the strategy's own task decomposition; nothing else is offered;
  goal         `PlanningContext.goal` / objective, rendered by the strategy;
  explanation  the facts the strategy wants the model to consider — from `PlanningContext.observation` (projected);
  schema       the structured answer (built in for `choose` / `order`; any JSON Schema for a custom task);
  validate     the business check of a schema-valid answer (index in range, dependency-respecting permutation …).

Provenance is taken from the answer, never from configuration: the client records what kind of endpoint answered
(`PROVIDER`, `PROTOCOL_TEST` — the loopback test service identifies itself — or `STUB`), and only a decision that maps
to such an answer is a model decision (LLM / LLM_PROTOCOL_TEST / LLM_STUB). When no usable answer arrives, the
decision says why — TRANSPORT_ERROR, FORMAT_ERROR, BUSINESS_INVALID, PROVIDER_REJECTED, CANCELLED, BUDGET_EXHAUSTED —
and keeps every failed call; a strategy that then falls back labels the result a RULE fallback with those call ids.

Budget: before each call the remaining model-call and model-attempt budget of the run and of the participant
(`PlanningContext.budget` / `usage`, `actor_budget` / `actor_usage`, plus what this decision already spent) is
checked; an exhausted budget sends nothing and is recorded as a BUDGET_EXHAUSTED call record. Retries inside a call
are capped to the remaining attempts. Recovery and fallback therefore count against the same budget.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import ActionProposal, ModelUsage, PlanningContext, ProposalSource
from formal_lab_contracts.errors import FormalLabError

from .model_clients import FormatError, ModelCall, ModelClient

SOURCE_OF_ENDPOINT = {"PROVIDER": "LLM", "PROTOCOL_TEST": "LLM_PROTOCOL_TEST", "STUB": "LLM_STUB"}

CHOOSE_SCHEMA = {
    "type": "object",
    "properties": {"index": {"type": "integer", "description": "index of the chosen option"},
                   "rationale": {"type": "string", "description": "one or two sentences"}},
    "required": ["index", "rationale"], "additionalProperties": False,
}
ORDER_SCHEMA = {
    "type": "object",
    "properties": {"order": {"type": "array", "items": {"type": "string"}, "description": "task ids, first first"},
                   "rationale": {"type": "string"}},
    "required": ["order", "rationale"], "additionalProperties": False,
}


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


@dataclass
class DecisionRequest:
    task: str  # "choose" | "order" | a strategy's own name
    system: str
    payload: dict[str, Any]
    schema: dict[str, Any]
    schema_name: str
    validate: Callable[[dict[str, Any]], str | None]
    max_calls: int = 2  # a schema-valid but business-invalid answer is asked again once
    prompt_version: str = "1"

    def render(self, retry_reason: str | None = None) -> str:
        user = f"Decision input (JSON):\n{json.dumps(self.payload, ensure_ascii=False, sort_keys=True)}"
        if retry_reason:
            user += f"\n\nYour previous answer was invalid ({retry_reason}). Answer again."
        return user

    @property
    def prompt_digest(self) -> str:
        return digest({"system": self.system, "schema": self.schema, "task": self.task,
                       "version": self.prompt_version})


def choose_request(options: list[dict[str, Any]], *, system: str, goal: Any = None,
                   explanation: dict[str, Any] | None = None, prompt_version: str = "1") -> DecisionRequest:
    """Pick exactly one of `options` (each a dict; its position is its index)."""
    payload = {"goal": goal, **(explanation or {}),
               "candidates": [{"index": i, **o} for i, o in enumerate(options)]}

    def valid(content: dict[str, Any]) -> str | None:
        i = content.get("index")
        return None if isinstance(i, int) and 0 <= i < len(options) else \
            f"index {i!r} out of range 0..{len(options) - 1} (business rejection of a schema-valid answer)"

    return DecisionRequest("choose", system, payload, CHOOSE_SCHEMA, "choose_candidate", valid,
                           prompt_version=prompt_version)


def order_request(tasks: list[dict[str, Any]], *, system: str, goal: Any = None,
                  explanation: dict[str, Any] | None = None, prompt_version: str = "1") -> DecisionRequest:
    """Order every task in `tasks` (each with an `id` and `depends_on`); dependencies must come first."""
    payload = {"goal": goal, **(explanation or {}), "tasks": tasks}
    ids = [t["id"] for t in tasks]

    def valid(content: dict[str, Any]) -> str | None:
        order = content.get("order")
        if not isinstance(order, list) or sorted(order) != sorted(ids):
            return "not a permutation of the open tasks"
        pos = {t: i for i, t in enumerate(order)}
        for t in tasks:
            if any(d in pos and pos[d] > pos[t["id"]] for d in t.get("depends_on", [])):
                return f"{t['id']} is placed before a task it depends on"
        return None

    return DecisionRequest("order", system, payload, ORDER_SCHEMA, "order_tasks", valid,
                           prompt_version=prompt_version)


@dataclass
class Decision:
    content: dict[str, Any] | None
    source: str  # LLM / LLM_PROTOCOL_TEST / LLM_STUB when `content` is a model answer, else "NONE"
    model: str | None
    calls: list[dict[str, Any]] = field(default_factory=list)
    usage: ModelUsage = field(default_factory=ModelUsage)
    failure: str | None = None  # TRANSPORT_ERROR / FORMAT_ERROR / BUSINESS_INVALID / PROVIDER_REJECTED / ...
    failure_detail: str = ""

    @property
    def decided_by_model(self) -> bool:
        return self.content is not None

    @property
    def call_ids(self) -> list[str]:
        return [c["call_id"] for c in self.calls]

    def source_of(self, strategy: Any) -> ProposalSource:
        """The proposal source of an action this decision chose — or of a rule fallback after it failed."""
        if self.decided_by_model:
            return ProposalSource(kind=self.source, strategy=strategy, model=self.model,
                                  model_call_ids=self.call_ids, decided_by="MODEL_RESPONSE")
        return ProposalSource(kind="RULE", strategy=strategy, model=None, model_call_ids=self.call_ids,
                              decided_by="RULE_FALLBACK")

    def proposal(self, context: PlanningContext, action: Any, strategy: Any, *, rationale: str | None = None,
                 candidates_considered: int | None = None) -> ActionProposal:
        why = rationale if rationale is not None else (
            str((self.content or {}).get("rationale", ""))[:2000] if self.decided_by_model else
            f"model decision unavailable ({self.failure}: {self.failure_detail[:300]}); rule fallback")
        return ActionProposal(proposal_id=f"{context.step_id}:proposal", run_id=context.run_id,
                              step_id=context.step_id, step=context.step, actor_id=context.actor_id, action=action,
                              based_on_revision=context.observation.state_revision, source=self.source_of(strategy),
                              rationale=why, candidates_considered=candidates_considered, usage=self.usage)


def usage_of(calls: list[ModelCall]) -> ModelUsage:
    ok = [c for c in calls if c.outcome == "OK"]
    return ModelUsage(model_calls=len(ok), attempts=sum(c.attempts for c in calls),
                      input_tokens=sum(c.input_tokens for c in calls), output_tokens=sum(c.output_tokens for c in calls),
                      unreported_calls=sum(1 for c in ok if not c.usage_reported),
                      unconfirmed_calls=sum(1 for c in calls if c.unconfirmed))


def remaining(context: PlanningContext | None, spent: ModelUsage) -> tuple[int | None, int | None, str]:
    """(model calls, model attempts) still allowed by the run's and the participant's budget, and which binds."""
    if context is None:
        return None, None, ""
    calls: int | None = None
    attempts: int | None = None
    why = ""
    for label, budget, usage in (("run", context.budget, context.usage),
                                 ("participant", context.actor_budget, context.actor_usage)):
        if budget is None or usage is None:
            continue
        if budget.max_model_calls is not None:
            left = budget.max_model_calls - usage.model_calls - spent.model_calls
            if calls is None or left < calls:
                calls, why = left, f"{label} model-call budget {budget.max_model_calls}"
        cap = getattr(budget, "max_model_attempts", None)
        if cap is not None:
            left = cap - usage.model_attempts - spent.attempts
            if attempts is None or left < attempts:
                attempts = left
                if left <= 0:
                    why = f"{label} model-attempt budget {cap}"
    return calls, attempts, why


class ModelDecider:
    """Runs a DecisionRequest against a ModelClient (see module docstring)."""

    def __init__(self, client: ModelClient):
        self.client = client

    def decide(self, request: DecisionRequest, *, context: PlanningContext | None = None) -> Decision:
        start = len(self.client.calls)
        retry_reason: str | None = None
        failure, detail = None, ""
        budget_records: list[dict[str, Any]] = []
        for _ in range(request.max_calls):
            spent = usage_of(self.client.calls[start:])
            calls_left, attempts_left, why = remaining(context, spent)
            if (calls_left is not None and calls_left <= 0) or (attempts_left is not None and attempts_left <= 0):
                failure, detail = "BUDGET_EXHAUSTED", f"{why} reached: no request sent"
                budget_records.append({"call_id": f"budget_{context.step_id if context else 'x'}_{len(budget_records)}",
                                       "outcome": "BUDGET_EXHAUSTED", "attempts": 0, "sent": False,
                                       "model_requested": getattr(self.client, "model", None), "error": detail,
                                       "prompt_digest": request.prompt_digest, "task": request.task})
                break
            try:
                resp = self.client.complete_json(system=request.system, user=request.render(retry_reason),
                                                 schema=request.schema, schema_name=request.schema_name,
                                                 payload=request.payload, max_attempts=attempts_left,
                                                 prompt_digest=request.prompt_digest)
            except FormatError as exc:
                failure, detail, retry_reason = "FORMAT_ERROR", exc.message, exc.message
                continue
            except FormalLabError as exc:  # the client recorded how the call ended (transport / rejected / cancelled)
                last = self.client.calls[-1] if len(self.client.calls) > start else None
                failure = last.outcome if last is not None and last.outcome != "OK" else "TRANSPORT_ERROR"
                detail = exc.message
                break
            problem = request.validate(resp.content)
            call = self.client.calls[-1]
            call.business = "VALID" if problem is None else f"INVALID: {problem}"
            if problem is None:
                calls = self.client.calls[start:]
                return Decision(content=resp.content, source=SOURCE_OF_ENDPOINT.get(call.endpoint_kind, "LLM"),
                                model=resp.model, calls=[c.as_record() for c in calls] + budget_records,
                                usage=usage_of(calls))
            failure, detail, retry_reason = "BUSINESS_INVALID", problem, problem
        calls = self.client.calls[start:]
        return Decision(content=None, source="NONE", model=None, calls=[c.as_record() for c in calls] + budget_records,
                        usage=usage_of(calls), failure=failure, failure_detail=detail)
