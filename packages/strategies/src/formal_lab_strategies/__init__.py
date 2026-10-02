"""Generic strategy adapters: the LLM planner, model clients and the reusable model decision (phase 4A)."""

from .decision import Decision, DecisionRequest, ModelDecider, choose_request, order_request
from .llm_planner import DESCRIPTOR as LLM_DESCRIPTOR
from .llm_planner import LLMPlanner
from .model_clients import ModelClient, ModelResponse, OpenAICompatibleClient, StubModelClient

__all__ = ["LLM_DESCRIPTOR", "Decision", "DecisionRequest", "LLMPlanner", "ModelClient", "ModelDecider",
           "ModelResponse", "OpenAICompatibleClient", "StubModelClient", "choose_request", "order_request"]
