from __future__ import annotations

import json

import httpx
import pytest
from formal_lab_contracts import BudgetUsage, CandidateAction, Observation, PlanningContext
from formal_lab_contracts.errors import InvalidInput, NonRetryableFailure, RetryableFailure
from formal_lab_example_scheduling.scenarios import model_package
from formal_lab_model import action_specs, check_model
from formal_lab_strategies import LLMPlanner, OpenAICompatibleClient, StubModelClient
from formal_lab_strategies.llm_planner import create


@pytest.fixture(scope="module")
def pkg():
    return model_package()


def ctx(pkg) -> PlanningContext:
    cands = [
        CandidateAction(action={"action_type": "pause", "params": {"m": "m1"}}, belief_applicability="APPLICABLE"),
        CandidateAction(action={"action_type": "assign", "params": {"op": "o1_cut", "m": "m1"}},
                        belief_applicability="APPLICABLE"),
        CandidateAction(action={"action_type": "advance", "params": {}}, belief_applicability="INAPPLICABLE"),
    ]
    obs = Observation(run_id="r", actor_id="dispatcher", step=1, state_revision=0,
                      facts=[{"path": "clock", "value": 0, "observed_at_step": 1}],
                      unknowns=[{"path": "phase[o1_cut]", "reason": "OBSERVATION_DELAY"}])
    return PlanningContext(run_id="r", step=1, step_id="r:s1", actor_id="dispatcher", observation=obs,
                           action_specs=action_specs(check_model(pkg.ir)), candidates=cands, model=pkg.ref(),
                           budget={"max_steps": 10}, usage=BudgetUsage(), seed=0)


def test_stub_is_labelled_and_deterministic(pkg):
    planner = LLMPlanner(pkg, StubModelClient(preference=["assign", "advance"]))
    p1, p2 = planner.propose(ctx(pkg)), planner.propose(ctx(pkg))
    assert p1.action == p2.action and p1.action.action_type == "assign"
    assert p1.source.kind == "LLM_STUB" and p1.source.model == "stub-deterministic-v1"
    assert p1.usage.model_calls == 1 and p1.usage.input_tokens == 0


def _transport(responses: list[dict]):
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        assert request.headers["authorization"] == "Bearer test-key"
        assert body["response_format"]["type"] == "json_schema"
        return httpx.Response(200, json=responses[len(seen) - 1])

    return httpx.MockTransport(handler), seen


def _completion(index: int, rationale: str = "ok") -> dict:
    return {"id": f"chatcmpl-{index}", "model": "gpt-test", "usage": {"prompt_tokens": 100, "completion_tokens": 10},
            "choices": [{"message": {"content": json.dumps({"index": index, "rationale": rationale})}}]}


def test_openai_compatible_request_usage_and_retry_on_invalid_index(pkg):
    transport, seen = _transport([_completion(7), _completion(1, "assign progresses the goal")])
    client = OpenAICompatibleClient(base_url="https://relay.example/v1", api_key="test-key", model="gpt-test",
                                    transport=transport)
    proposal = LLMPlanner(pkg, client).propose(ctx(pkg))
    assert proposal.action.params == {"op": "o1_cut", "m": "m1"}
    assert proposal.source.kind == "LLM" and proposal.source.model_call_ids == ["chatcmpl-7", "chatcmpl-1"]
    assert proposal.usage.model_calls == 2 and proposal.usage.input_tokens == 200 and proposal.usage.output_tokens == 20
    payload = json.loads(seen[0]["messages"][1]["content"].split("\n", 1)[1])
    assert [c["applicability"] for c in payload["candidates"]] == ["APPLICABLE", "APPLICABLE", "INAPPLICABLE"]
    assert payload["unknown"][0]["path"] == "phase[o1_cut]"
    assert "invalid" in seen[1]["messages"][1]["content"]


def test_invalid_twice_is_retryable_failure(pkg):
    transport, _ = _transport([_completion(9), _completion(-1)])
    client = OpenAICompatibleClient(base_url="https://relay.example/v1", api_key="test-key", model="m",
                                    transport=transport)
    with pytest.raises(RetryableFailure):
        LLMPlanner(pkg, client).propose(ctx(pkg))


def test_http_errors_are_classified(pkg):
    for status, exc in ((429, RetryableFailure), (503, RetryableFailure), (400, NonRetryableFailure)):
        client = OpenAICompatibleClient(base_url="https://relay.example/v1", api_key="k", model="m",
                                        transport=httpx.MockTransport(lambda r, s=status: httpx.Response(s, text="x")))
        with pytest.raises(exc):
            client.complete_json(system="s", user="u", schema={}, schema_name="n", payload={})


def test_unconfigured_llm_is_explicit(pkg):
    class Services:
        def pinned_model(self):
            return pkg

        def get_setting(self, key):
            return None

    with pytest.raises(InvalidInput, match="not configured"):
        create({}, Services())
    assert create({"client": "stub"}, Services()).client.is_stub
