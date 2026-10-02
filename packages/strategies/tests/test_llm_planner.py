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


def test_invalid_twice_falls_back_or_fails_as_configured(pkg):
    transport, _ = _transport([_completion(9), _completion(-1)])
    client = OpenAICompatibleClient(base_url="https://relay.example/v1", api_key="test-key", model="m",
                                    transport=transport)
    fallback = LLMPlanner(pkg, client, {"fallback_preference": ["assign"]}).propose(ctx(pkg))
    # two schema-valid answers, both rejected by the business rule (index out of range): a labelled RULE fallback
    # that still carries the attempted calls and their usage
    assert fallback.source.kind == "RULE" and fallback.source.model_call_ids == ["chatcmpl-9", "chatcmpl--1"]
    assert fallback.usage.model_calls == 2 and fallback.usage.attempts == 2 and "fallback" in fallback.rationale
    assert fallback.action.action_type == "assign"
    transport, _ = _transport([_completion(9), _completion(-1)])
    client = OpenAICompatibleClient(base_url="https://relay.example/v1", api_key="test-key", model="m",
                                    transport=transport)
    with pytest.raises(RetryableFailure):
        LLMPlanner(pkg, client, {"on_model_failure": "fail"}).propose(ctx(pkg))


def _client(handler, **kw):
    return OpenAICompatibleClient(base_url="https://relay.example/v1", api_key="k", model="m",
                                  transport=httpx.MockTransport(handler), backoff_s=0.01, **kw)


def test_http_errors_are_classified_and_retried(pkg):
    for status, exc in ((429, RetryableFailure), (503, RetryableFailure), (400, NonRetryableFailure)):
        hits = []
        client = _client(lambda r, s=status, h=hits: h.append(1) or httpx.Response(s, text="x"), max_attempts=3)
        with pytest.raises(exc):
            client.complete_json(system="s", user="u", schema={}, schema_name="n", payload={})
        assert len(hits) == (1 if status == 400 else 3)  # 4xx is not retried; 429 / 5xx are
        # phase 4A: a provider's refusal (4xx) is kept apart from transport failures
        want = "PROVIDER_REJECTED" if status == 400 else "TRANSPORT_ERROR"
        assert client.calls[-1].outcome == want and client.calls[-1].http_status == status


def test_rate_limit_then_success_honours_retry_after():
    answers = [httpx.Response(429, headers={"retry-after": "0.05"}, text="slow down"),
               httpx.Response(200, json=_completion(0))]
    client = _client(lambda r: answers.pop(0), max_attempts=3)
    resp = client.complete_json(system="s", user="u", schema={"type": "object"}, schema_name="n", payload={})
    call = client.calls[-1]
    assert resp.content["index"] == 0 and call.attempts == 2 and call.outcome == "OK"
    assert call.model_returned == "gpt-test" and call.model_requested == "m" and call.usage_reported


def test_format_errors_are_separate_from_transport_errors():
    bad_json = {"id": "x", "model": "gpt-test", "choices": [{"message": {"content": "not json"}}]}
    client = _client(lambda r: httpx.Response(200, json=bad_json))
    from formal_lab_strategies.model_clients import FormatError

    with pytest.raises(FormatError):
        client.complete_json(system="s", user="u", schema={"type": "object"}, schema_name="n", payload={})
    wrong_shape = {"id": "y", "model": "gpt-test", "choices": [{"message": {"content": json.dumps({"idx": 1})}}]}
    client2 = _client(lambda r: httpx.Response(200, json=wrong_shape))
    with pytest.raises(FormatError):
        client2.complete_json(system="s", user="u", schema=json.loads(json.dumps(
            {"type": "object", "properties": {"index": {"type": "integer"}}, "required": ["index"]})),
            schema_name="n", payload={})
    assert client.calls[-1].outcome == client2.calls[-1].outcome == "FORMAT_ERROR"
    assert client.calls[-1].raw_text == "not json"


def test_unreported_usage_timeouts_and_cancellation():
    import threading

    no_usage = {"id": "z", "model": "gpt-test", "choices": [{"message": {"content": json.dumps({"a": 1})}}]}
    client = _client(lambda r: httpx.Response(200, json=no_usage))
    resp = client.complete_json(system="s", user="u", schema={"type": "object"}, schema_name="n", payload={})
    assert not resp.usage_reported and client.calls[-1].input_tokens == 0

    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    slow = _client(timeout, max_attempts=2)
    from formal_lab_contracts.errors import Timeout

    with pytest.raises(Timeout):
        slow.complete_json(system="s", user="u", schema={}, schema_name="n", payload={})
    assert slow.calls[-1].unconfirmed and slow.calls[-1].attempts == 2
    cancel = threading.Event()
    cancel.set()
    stopped = _client(lambda r: httpx.Response(200, json=no_usage), cancel=cancel)
    with pytest.raises(Timeout, match="cancelled"):
        stopped.complete_json(system="s", user="u", schema={}, schema_name="n", payload={})


def test_unconfigured_llm_is_explicit(pkg):
    class Services:
        def pinned_model(self):
            return pkg

        def get_setting(self, key):
            return None

    with pytest.raises(InvalidInput, match="not configured"):
        create({}, Services())
    assert create({"client": "stub"}, Services()).client.is_stub
