"""Generic LLM strategy: structured observation + candidate schema in, ActionProposal out.

The planner is domain-neutral: it renders the observation, unknowns, goal properties and candidates from
contract objects and plugin/model metadata, and asks the model to pick one candidate index (JSON-Schema
constrained). The model never gets free-form tools; it can only choose among environment candidates.
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
from formal_lab_contracts.errors import InvalidInput, RetryableFailure
from formal_lab_model import check_model, expr_text

from .model_clients import ModelClient, ModelResponse, OpenAICompatibleClient, StubModelClient

PLANNER_ID = "formal-lab.planner.llm"
PLANNER_VERSION = "1.0.0"
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
    },
    "additionalProperties": False,
}

DESCRIPTOR = PluginDescriptor(
    plugin_id=PLANNER_ID,
    version=PLANNER_VERSION,
    interface="PLANNER",
    capabilities=[{"id": caps.PLAN_LLM}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_strategies.llm_planner:create",
    ui={"label": "LLM 策略", "category": "llm",
        "description": "Chooses one candidate action with a language model (JSON-schema output). "
        "client=stub gives a labelled deterministic stand-in."},
    license="UNLICENSED",  # repository owner has not chosen a license yet
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


class LLMPlanner:
    descriptor = DESCRIPTOR

    def __init__(self, package: ModelPackage, client: ModelClient, config: dict[str, Any] | None = None):
        cfg = {"max_candidates": 60, **(config or {})}
        self.package = package
        self.client = client
        self.model = check_model(package.ir)
        self.max_candidates = int(cfg["max_candidates"])
        goals = [p for p in package.ir.properties if p.kind == "goal"]
        self.goal = next((p for p in goals if p.id == cfg.get("goal_property")), goals[0] if goals else None)
        self.action_labels = {a.name: a.label or a.name for a in package.ir.actions}
        self.state_labels = {s.name: s.label or s.name for s in package.ir.state}
        self.last_calls: list[ModelResponse] = []

    def _payload(self, ctx: PlanningContext) -> dict[str, Any]:
        cands = ctx.candidates[: self.max_candidates]
        return {
            "goal": {"id": self.goal.id, "label": self.goal.label, "condition": expr_text(self.goal.expr)}
            if self.goal else None,
            "model": {"name": self.package.ir.name, "description": self.package.ir.description},
            "step": ctx.step,
            "budget": ctx.budget.model_dump(exclude_none=True),
            "usage": ctx.usage.model_dump(),
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
        usage = ModelUsage()
        self.last_calls = []
        last_error = ""
        for attempt in range(MAX_ATTEMPTS):
            prompt = user if attempt == 0 else user + f"\n\nYour previous answer was invalid ({last_error}). " \
                                                      f"Return an index between 0 and {len(payload['candidates']) - 1}."
            resp = self.client.complete_json(system=SYSTEM_PROMPT, user=prompt, schema=RESPONSE_SCHEMA,
                                             schema_name="choose_candidate", payload=payload)
            self.last_calls.append(resp)
            usage.model_calls += 1
            usage.input_tokens += resp.input_tokens
            usage.output_tokens += resp.output_tokens
            index = resp.content.get("index")
            if isinstance(index, int) and 0 <= index < len(payload["candidates"]):
                chosen = context.candidates[index]
                return ActionProposal(
                    proposal_id=f"{context.step_id}:proposal",
                    run_id=context.run_id,
                    step_id=context.step_id,
                    step=context.step,
                    actor_id=context.actor_id,
                    action=chosen.action,
                    based_on_revision=context.observation.state_revision,
                    source=ProposalSource(kind="LLM_STUB" if self.client.is_stub else "LLM",
                                          strategy=self.descriptor.ref(), model=resp.model,
                                          model_call_ids=[c.call_id for c in self.last_calls]),
                    rationale=str(resp.content.get("rationale", ""))[:2000],
                    candidates_considered=len(payload["candidates"]),
                    usage=usage,
                )
            last_error = f"index {index!r} out of range"
        raise RetryableFailure(f"model did not return a valid candidate index after {MAX_ATTEMPTS} attempts: "
                               f"{last_error}", details={"usage": usage.model_dump()})


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
        timeout_s=float(services.get_setting("FAL_LLM_TIMEOUT_SECONDS") or 120),
    )


def create(config: dict[str, Any] | None, services: Any) -> LLMPlanner:
    config = dict(config or {})
    unknown = set(config) - set(CONFIG_SCHEMA["properties"])
    if unknown:
        raise InvalidInput(f"unknown LLM planner config keys {sorted(unknown)}")
    return LLMPlanner(services.pinned_model(), client_from_settings(config, services), config)


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    return [PluginRegistration(DESCRIPTOR, create)]
