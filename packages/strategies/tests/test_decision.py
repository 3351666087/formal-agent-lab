"""Reusable model decision (phase 4A, A3) against the loopback protocol test service and scripted transports:
the decision follows the answer, invalid answers take the declared path, failures are classified and kept, the
source comes from what answered (never from the `client` string), and the budget stops requests before they are sent."""

from __future__ import annotations

import json
import socket

import httpx
import pytest
from formal_lab_contracts import BudgetUsage, CandidateAction, Observation, PlanningContext
from formal_lab_example_scheduling.scenarios import model_package
from formal_lab_model import action_specs, check_model
from formal_lab_strategies import LLMPlanner, OpenAICompatibleClient, StubModelClient
from formal_lab_strategies.decision import ModelDecider, choose_request, order_request
from formal_lab_strategies.protocol_server import MODEL, ProtocolTestServer

KEY = "a3-test-key-never-recorded"


@pytest.fixture(scope="module")
def pkg():
    return model_package()


def ctx(pkg, *, budget=None, usage=None, actor_budget=None, actor_usage=None) -> PlanningContext:
    cands = [
        CandidateAction(action={"action_type": "pause", "params": {"m": "m1"}}, belief_applicability="APPLICABLE"),
        CandidateAction(action={"action_type": "assign", "params": {"op": "o1_cut", "m": "m1"}},
                        belief_applicability="APPLICABLE"),
        CandidateAction(action={"action_type": "assign", "params": {"op": "o2_cut", "m": "m2"}},
                        belief_applicability="APPLICABLE"),
    ]
    obs = Observation(run_id="r", actor_id="dispatcher", step=1, state_revision=0,
                      facts=[{"path": "clock", "value": 0, "observed_at_step": 1}])
    return PlanningContext(run_id="r", step=1, step_id="r:s1", actor_id="dispatcher", observation=obs,
                           action_specs=action_specs(check_model(pkg.ir)), candidates=cands, model=pkg.ref(),
                           budget=budget or {"max_steps": 10}, usage=usage or BudgetUsage(), seed=0,
                           actor_budget=actor_budget, actor_usage=actor_usage)


@pytest.fixture
def server():
    srv = ProtocolTestServer().start()
    yield srv
    srv.stop()


def client_for(url: str, **kw) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(base_url=url, api_key=KEY, model=kw.pop("model", "gpt-test"), backoff_s=0.01,
                                  timeout_s=kw.pop("timeout_s", 5), **kw)


def test_decision_follows_the_answer_and_is_labelled_by_what_answered(pkg, server):
    picks = []
    for i in (0, 2, 1):
        server.script.append(f"pick:{i}")
        p = LLMPlanner(pkg, client_for(server.base_url)).propose(ctx(pkg))
        picks.append(p.action.params)
        # configured as "openai_compatible", answered by the protocol test service: labelled by the answer
        assert p.source.kind == "LLM_PROTOCOL_TEST" and p.source.decided_by == "MODEL_RESPONSE"
        assert p.source.model == MODEL
    assert picks == [{"m": "m1"}, {"op": "o2_cut", "m": "m2"}, {"op": "o1_cut", "m": "m1"}]


def test_a_provider_answer_is_labelled_llm_and_the_stub_stays_a_stub(pkg):
    answer = {"id": "chatcmpl-1", "model": "gpt-test", "usage": {"prompt_tokens": 5, "completion_tokens": 2},
              "choices": [{"message": {"content": json.dumps({"index": 1, "rationale": "r"})}}]}
    client = OpenAICompatibleClient(base_url="https://relay.example/v1", api_key=KEY, model="gpt-test",
                                    transport=httpx.MockTransport(lambda r: httpx.Response(200, json=answer)))
    p = LLMPlanner(pkg, client).propose(ctx(pkg))
    assert p.source.kind == "LLM" and p.source.model_call_ids == ["chatcmpl-1"]
    stub = LLMPlanner(pkg, StubModelClient(preference=["assign"])).propose(ctx(pkg))
    assert stub.source.kind == "LLM_STUB" and stub.source.decided_by == "MODEL_RESPONSE"


def test_invalid_answers_take_the_declared_path(pkg, server):
    server.script.extend(["out_of_range", "pick:2"])
    p = LLMPlanner(pkg, client_for(server.base_url)).propose(ctx(pkg))
    assert p.action.params == {"op": "o2_cut", "m": "m2"} and len(p.source.model_call_ids) == 2
    server.script.extend(["out_of_range", "schema_violation"])
    fb = LLMPlanner(pkg, client_for(server.base_url), {"fallback_preference": ["pause"]}).propose(ctx(pkg))
    assert fb.source.kind == "RULE" and fb.source.decided_by == "RULE_FALLBACK"
    assert len(fb.source.model_call_ids) == 2 and fb.action.action_type == "pause"
    server.script.extend(["out_of_range", "out_of_range"])
    from formal_lab_contracts.errors import RetryableFailure

    with pytest.raises(RetryableFailure, match="BUSINESS_INVALID"):
        LLMPlanner(pkg, client_for(server.base_url), {"on_model_failure": "fail"}).propose(ctx(pkg))


def test_unreachable_endpoint_is_a_recorded_failure_never_a_model_decision(pkg):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # closed again: nothing listens there
    client = client_for(f"http://127.0.0.1:{port}/v1", max_attempts=2)
    planner = LLMPlanner(pkg, client)
    p = planner.propose(ctx(pkg))
    rec = planner.call_records[0]
    assert p.source.kind == "RULE" and p.source.decided_by == "RULE_FALLBACK"
    assert rec["outcome"] == "TRANSPORT_ERROR" and rec["attempts"] == 2 and "unreachable" in rec["error"]
    assert rec["input_tokens"] is None and rec["usage_reported"] is False  # unknown, not free


def test_failures_are_classified(pkg, server):
    decider = ModelDecider(client_for(server.base_url, max_attempts=2))
    req = choose_request([{"a": 1}, {"a": 2}], system="pick one")
    server.script.extend(["401"])
    assert decider.decide(req).failure == "PROVIDER_REJECTED"
    server.script.extend(["bad_json", "bad_json"])
    assert decider.decide(req).failure == "FORMAT_ERROR"
    server.script.extend(["500", "500"])
    d = decider.decide(req)
    assert d.failure == "TRANSPORT_ERROR" and d.calls[-1]["http_status"] == 500 and d.calls[-1]["attempts"] == 2
    server.script.extend(["switch_model"])
    d = decider.decide(req)
    assert d.decided_by_model and d.calls[-1]["model_switched"] is True
    assert d.calls[-1]["model_returned"] == MODEL + "-switched"


def test_budget_stops_requests_before_they_are_sent(pkg, server):
    spent = BudgetUsage(model_calls=3, model_attempts=3)
    planner = LLMPlanner(pkg, client_for(server.base_url), {"fallback_preference": ["pause"]})
    p = planner.propose(ctx(pkg, budget={"max_steps": 10, "max_model_calls": 3}, usage=spent))
    assert server.requests == [] and p.source.decided_by == "RULE_FALLBACK"
    assert planner.call_records[0]["outcome"] == "BUDGET_EXHAUSTED" and planner.call_records[0]["sent"] is False
    # the participant's own budget binds too
    p = planner.propose(ctx(pkg, actor_budget={"max_model_calls": 1}, actor_usage=BudgetUsage(model_calls=1)))
    assert server.requests == [] and p.source.decided_by == "RULE_FALLBACK"
    # attempts (retries and failures included) are budgeted: 2 attempts left → at most 2 requests
    server.script.extend(["500"] * 5)
    planner = LLMPlanner(pkg, client_for(server.base_url, max_attempts=4), {"fallback_preference": ["pause"]})
    planner.propose(ctx(pkg, budget={"max_model_attempts": 5}, usage=BudgetUsage(model_attempts=3)))
    assert len(server.requests) == 2


def test_records_carry_digests_and_never_the_credential(pkg, server):
    from formal_lab_strategies.model_clients import public_endpoint

    assert public_endpoint(f"https://user:{KEY}@relay.example/v1?key={KEY}") == "https://relay.example/v1"
    planner = LLMPlanner(pkg, client_for(server.base_url))
    planner.propose(ctx(pkg))
    rec = planner.call_records[0]
    text = json.dumps(planner.call_records)
    assert KEY not in text
    assert rec["prompt_digest"] and rec["config_digest"] and rec["endpoint_kind"] == "PROTOCOL_TEST"
    assert rec["endpoint"] == server.base_url
    assert rec["model_requested"] == "gpt-test" and rec["model_returned"] == MODEL and rec["latency_ms"] >= 0
    assert rec["business"] == "VALID" and rec["usage_reported"] is True and rec["input_tokens"] > 0


def test_order_request_validates_dependencies(server):
    tasks = [{"id": "a", "depends_on": []}, {"id": "b", "depends_on": ["a"]}]
    req = order_request(tasks, system="order")
    assert req.validate({"order": ["a", "b"]}) is None
    assert "before a task it depends on" in req.validate({"order": ["b", "a"]})
    assert "permutation" in req.validate({"order": ["a"]})
    d = ModelDecider(client_for(server.base_url)).decide(req)
    assert d.content["order"] == ["a", "b"] and d.source == "LLM_PROTOCOL_TEST"
