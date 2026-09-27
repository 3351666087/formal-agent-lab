"""Generic LLM strategy: structured observation + candidate schema in, ActionProposal out.

The planner is domain-neutral: it renders the observation, unknowns, goal and candidates from contract objects and
the model's semantic driver (any profile), and asks the model to pick one candidate index (JSON-Schema
constrained). The model never gets free-form tools; it can only choose among environment candidates.

Accounting (P2-036 / P2-044 / P2-055): `usage.model_calls` counts schema-valid answers, `usage.attempts` every HTTP
attempt, `unreported_calls` answers without usage data and `unconfirmed_calls` requests whose answer was lost.
Transport failures, format failures (not the requested JSON) and business rejections (index out of range) are
recorded separately in the call records. When the model stays unavailable, `on_model_failure: fallback` (default)
proposes the first applicable candidate by `fallback_preference`, labelled as a RULE fallback with the failed
call ids, so the attempted usage is still committed with the step; `fail` raises instead.
"""

from __future__ import annotations

import json
from typing import Any

from formal_lab_contracts import (
    ActionProposal,
    ModelPackage,
    ModelUsage,
    PlanningContext,
    PluginDescriptor,
    ProposalSource,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import FormalLabError, InvalidInput, NonRetryableFailure, RetryableFailure

from .model_clients import FormatError, ModelCall, ModelClient, OpenAICompatibleClient, StubModelClient

PLANNER_ID = "formal-lab.planner.llm"
PLANNER_VERSION = "1.1.0"
MAX_ATTEMPTS = 2

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "client": {"type": "string", "enum": ["openai_compatible", "stub"], "default": "openai_compatible"},
        "model": {"type": "string", "description": "override FAL_LLM_MODEL"},
        "max_candidates": {"type": "integer", "minimum": 1, "maximum": 200, "default": 60},
        "goal_property": {"type": "string"},
        "stub_preference": {"type": "array", "items": {"type": "string"},
                            "description": "client=stub only: action types in preference order"},
        "on_model_failure": {"type": "string", "enum": ["fallback", "fail"], "default": "fallback"},
        "fallback_preference": {"type": "array", "items": {"type": "string"},
                                "description": "action types preferred by the fallback (in order)"},
        "timeout_s": {"type": "number", "exclusiveMinimum": 0, "description": "per-attempt timeout"},
        "max_attempts": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4},
        "temperature": {"type": "number", "minimum": 0, "maximum": 2},
    },
    "additionalProperties": False,
}

DESCRIPTOR = PluginDescriptor(
    plugin_id=PLANNER_ID,
    version=PLANNER_VERSION,
    interface="PLANNER",
    capabilities=[{"id": caps.PLAN_LLM}],
    requires=[{"id": caps.DRIVER_CANDIDATES, "params": {"of": "driver"}}],
    semantic_profiles=[],
    config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_strategies.llm_planner:create",
    ui={"label": "LLM 策略", "category": "llm",
        "description": "Chooses one candidate action with a language model (JSON-schema output), for any model "
        "profile. client=stub gives a labelled deterministic stand-in."},
    license="Apache-2.0",
    source="formal-lab-strategies",
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "index": {"type": "integer", "description": "index of the chosen candidate"},
        "rationale": {"type": "string", "description": "one or two sentences"},
    },
    "required": ["index", "rationale"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are the decision policy of an agent inside a simulated, finite-state experiment. Each turn you receive "
    "the agent's observation (facts it knows, some possibly stale, and locations whose current value is unknown), "
    "the goal, and a numbered list of candidate actions with their applicability judged on the agent's belief "
    "(APPLICABLE, INAPPLICABLE or UNKNOWN when it depends on unknown facts). Choose exactly one candidate by its "
    "index. Prefer actions that make progress towards the goal and the stated objectives; avoid INAPPLICABLE "
    "candidates (they will be rejected). Respond only with the JSON object requested."
)


def usage_of(calls: list[ModelCall]) -> ModelUsage:
    ok = [c for c in calls if c.outcome == "OK"]
    return ModelUsage(model_calls=len(ok), attempts=sum(c.attempts for c in calls),
                      input_tokens=sum(c.input_tokens for c in calls), output_tokens=sum(c.output_tokens for c in calls),
                      unreported_calls=sum(1 for c in ok if not c.usage_reported),
                      unconfirmed_calls=sum(1 for c in calls if c.unconfirmed))


class LLMPlanner:
    descriptor = DESCRIPTOR

    def __init__(self, package: ModelPackage, client: ModelClient, config: dict[str, Any] | None = None,
                 loaded: Any = None):
        cfg = {"max_candidates": 60, "on_model_failure": "fallback", **(config or {})}
        self.package = package
        self.client = client
        self.loaded = loaded
        self.max_candidates = int(cfg["max_candidates"])
        self.on_failure = cfg["on_model_failure"]
        self.fallback_preference = list(cfg.get("fallback_preference") or cfg.get("stub_preference") or [])
        self.goal_override = cfg.get("goal_property")
        specs = loaded.action_specs() if loaded is not None else []
        self.action_labels = {s.action_type: s.label or s.action_type for s in specs}
        self.state_labels: dict[str, str] = {}
        self.goal_text: dict[str, str] = {}
        if package.is_ir:
            from formal_lab_model import expr_text

            self.state_labels = {s.name: s.label or s.name for s in package.ir.state}
            self.goal_text = {p.id: expr_text(p.expr) for p in package.ir.properties}
            self.goal_labels = {p.id: p.label for p in package.ir.properties}
        else:
            self.goal_labels = {}
        self.kinds = loaded.property_kinds() if loaded is not None else {}
        self.last_calls: list[Any] = []
        self.call_records: list[dict[str, Any]] = []

    def _goal(self, ctx: PlanningContext) -> str | None:
        return self.goal_override or ctx.goal or next((p for p, k in self.kinds.items() if k == "goal"), None)

    def _payload(self, ctx: PlanningContext) -> dict[str, Any]:
        cands = ctx.candidates[: self.max_candidates]
        goal = self._goal(ctx)
        return {
            "goal": {"id": goal, "label": self.goal_labels.get(goal), "condition": self.goal_text.get(goal)}
            if goal else None,
            "model": {"name": self.package.package_id, "profile": self.package.semantic_profile,
                      "description": self.package.ir.description if self.package.is_ir else None},
            "actor": ctx.actor_id,
            "participants": ctx.participants,
            "step": ctx.step,
            "budget": ctx.budget.model_dump(exclude_none=True),
            "usage": ctx.usage.model_dump(),
            "objective": ctx.objective.model_dump(mode="json") if ctx.objective else None,
            "facts": {f.path: f.value for f in ctx.observation.facts},
            "unknown": [{"path": u.path, "reason": u.reason,
                         "last_known": u.last_known.value if u.last_known else None,
                         "as_of_step": u.last_known.observed_at_step if u.last_known else None}
                        for u in ctx.observation.unknowns],
            "state_labels": self.state_labels,
            "candidates": [
                {"index": i, "action_type": c.action.action_type, "label": self.action_labels.get(c.action.action_type),
                 "params": c.action.params, "applicability": str(c.belief_applicability)}
                for i, c in enumerate(cands)
            ],
        }

    def propose(self, context: PlanningContext) -> ActionProposal:
        if not context.candidates:
            raise InvalidInput("LLM planner needs at least one candidate")
        payload = self._payload(context)
        user = "Decision input (JSON):\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        start = len(self.client.calls)
        self.last_calls = []
        last_error = ""
        failure: FormalLabError | None = None
        for attempt in range(MAX_ATTEMPTS):
            prompt = user if attempt == 0 else user + f"\n\nYour previous answer was invalid ({last_error}). " \
                                                      f"Return an index between 0 and {len(payload['candidates']) - 1}."
            try:
                resp = self.client.complete_json(system=SYSTEM_PROMPT, user=prompt, schema=RESPONSE_SCHEMA,
                                                 schema_name="choose_candidate", payload=payload)
            except FormatError as exc:
                last_error, failure = exc.message, exc
                continue
            except (RetryableFailure, NonRetryableFailure) as exc:  # transport: no point asking again now
                failure = exc
                break
            self.last_calls.append(resp)
            index = resp.content.get("index")
            if isinstance(index, int) and 0 <= index < len(payload["candidates"]):
                calls = self.client.calls[start:]
                self.call_records = [c.as_record() for c in calls]
                chosen = context.candidates[index]
                return self._proposal(context, chosen.action, ProposalSource(
                    kind="LLM_STUB" if self.client.is_stub else "LLM", strategy=self.descriptor.ref(),
                    model=resp.model, model_call_ids=[c.call_id for c in calls]),
                    str(resp.content.get("rationale", ""))[:2000], usage_of(calls))
            last_error = f"index {index!r} out of range (business rejection of a schema-valid answer)"
        calls = self.client.calls[start:]
        self.call_records = [c.as_record() for c in calls]
        usage = usage_of(calls)
        reason = failure.message if failure is not None else last_error
        if self.on_failure == "fail":
            raise RetryableFailure(f"model did not return a usable choice after {len(calls)} call(s): {reason}",
                                   details={"usage": usage.model_dump(), "calls": self.call_records})
        pref = {t: i for i, t in enumerate(self.fallback_preference)}
        applicable = [c for c in context.candidates if str(c.belief_applicability) == "APPLICABLE"] or \
            [c for c in context.candidates if str(c.belief_applicability) == "UNKNOWN"]
        if not applicable:
            raise NonRetryableFailure("model unavailable and no applicable candidate for the fallback")
        chosen = min(applicable, key=lambda c: (pref.get(c.action.action_type, len(pref)),
                                                context.candidates.index(c)))
        return self._proposal(context, chosen.action, ProposalSource(
            kind="RULE", strategy=self.descriptor.ref(), model=None, model_call_ids=[c.call_id for c in calls]),
            f"model unavailable ({reason[:300]}); fallback to the first applicable candidate by preference", usage)

    def _proposal(self, context: PlanningContext, action, source: ProposalSource, rationale: str,
                  usage: ModelUsage) -> ActionProposal:
        return ActionProposal(proposal_id=f"{context.step_id}:proposal", run_id=context.run_id,
                              step_id=context.step_id, step=context.step, actor_id=context.actor_id, action=action,
                              based_on_revision=context.observation.state_revision, source=source,
                              rationale=rationale, candidates_considered=min(len(context.candidates),
                                                                            self.max_candidates), usage=usage)


def client_from_settings(config: dict[str, Any], services: Any) -> ModelClient:
    kind = config.get("client", "openai_compatible")
    if kind == "stub":
        return StubModelClient(preference=config.get("stub_preference"))
    api_key = services.get_setting("FAL_LLM_API_KEY") or ""
    if not api_key:
        raise InvalidInput("LLM strategy is not configured (FAL_LLM_API_KEY is empty); "
                           "use rule/symbolic strategies or client='stub' for a labelled stand-in")
    return OpenAICompatibleClient(
        base_url=services.get_setting("FAL_LLM_BASE_URL") or "https://api.openai.com/v1",
        api_key=api_key,
        model=config.get("model") or services.get_setting("FAL_LLM_MODEL") or "gpt-5.6-sol",
        timeout_s=float(config.get("timeout_s") or services.get_setting("FAL_LLM_TIMEOUT_SECONDS") or 120),
        max_attempts=int(config.get("max_attempts", 4)),
        temperature=config.get("temperature"),
    )


def create(config: dict[str, Any] | None, services: Any) -> LLMPlanner:
    config = dict(config or {})
    unknown = set(config) - set(CONFIG_SCHEMA["properties"])
    if unknown:
        raise InvalidInput(f"unknown LLM planner config keys {sorted(unknown)}")
    loaded = services.loaded_model() if hasattr(services, "loaded_model") else None
    return LLMPlanner(services.pinned_model(), client_from_settings(config, services), config, loaded)


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    return [PluginRegistration(DESCRIPTOR, create)]
