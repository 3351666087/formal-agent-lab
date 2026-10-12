"""Phase 6A research calls: both provider protocols against the loopback protocol test service, over real HTTP.

Covers the classes the task book names — a legal answer, a visible refusal inside an HTTP success, empty content,
truncation, a malformed body, a model change / an unnamed model, 401/403/429/5xx, budget, cancellation, a lost
response (possibly billed) — and that nothing is retried to obtain acceptance, no provider env var is read, the
declared route must match the host, and a credential echoed by a gateway never reaches the record."""

from __future__ import annotations

import json
import socket
import threading

import pytest
from formal_lab_contracts.errors import InvalidInput
from formal_lab_contracts.research import ProviderConfig
from formal_lab_strategies.model_clients import (
    ResearchBudget,
    ResearchRequest,
    read_setting,
    research_adapter,
    research_call,
)
from formal_lab_strategies.protocol_server import ProtocolTestServer

REQ = ResearchRequest(user="Which constant explains the deviation? Answer in JSON.", system="You are a careful analyst.",
                      params={"max_tokens": 256})


def cfg(srv: ProtocolTestServer, api: str = "openai.chat.completions", **kw) -> ProviderConfig:
    base = srv.base_url  # .../v1 → /v1/chat/completions or /v1/messages
    return ProviderConfig(provider_config_id=f"ptest-{api.split('.')[0]}", provider="protocol-test", api=api,
                          api_version="v1" if api.startswith("openai") else "2023-06-01", route="LOOPBACK_TEST",
                          base_url=base, model="protocol-test-v1", **kw)


def call(srv, script, *, api="openai.chat.completions", budget=None, cancel=None, retries=2, **kw):
    srv.script.extend(script)
    adapter, why = research_adapter(cfg(srv, api, **kw), timeout_s=30.0)
    return research_call(adapter, REQ, provider_config_id="p", route="LOOPBACK_TEST", blocked_reason=why,
                         budget=budget or ResearchBudget(max_calls=10, max_http_attempts=20), cancel=cancel,
                         network_retries=retries, backoff_s=0.01, max_backoff_s=0.05)


@pytest.fixture()
def srv():
    with ProtocolTestServer() as s:
        yield s


@pytest.mark.parametrize("api", ["openai.chat.completions", "anthropic.messages"])
def test_legal_answer_is_saved_raw_with_identity_and_usage(srv, api):
    r = call(srv, ['answer:{"constant": "slow", "station": "p2"}'], api=api)
    assert r.status.outcome == "ANSWERED" and r.raw.visible_text == '{"constant": "slow", "station": "p2"}'
    assert r.raw.body is not None and r.raw.finish_class == "STOP"  # the provider body as returned
    assert r.call.endpoint_kind == "PROTOCOL_TEST" and r.call.model_identity == "TEST_SERVICE"
    assert r.cost.usage_known and r.cost.output_tokens is not None and r.cost.http_attempts == 1
    assert r.call.api == api and r.call.response_id


@pytest.mark.parametrize("api", ["openai.chat.completions", "anthropic.messages"])
def test_visible_refusal_in_an_http_success_is_a_content_refusal_and_not_retried(srv, api):
    r = call(srv, ["refusal", "answer:accepted on retry?"], api=api)
    assert r.status.outcome == "CONTENT_REFUSAL" and r.status.http_status == 200
    assert r.raw.refusal and r.raw.finish_class == "REFUSAL"
    assert len(srv.requests) == 1  # a refusal never triggers a retry to obtain an acceptable answer


def test_content_filter_empty_truncated_and_thinking_summary(srv):
    assert call(srv, ["content_filter"]).status.outcome == "CONTENT_REFUSAL"
    assert call(srv, ["empty"]).status.outcome == "EMPTY_CONTENT"
    t = call(srv, ["truncate:partial ans"])
    assert t.status.outcome == "TRUNCATED" and t.raw.truncated and t.raw.visible_text == "partial ans"
    a = call(srv, ["truncate:half"], api="anthropic.messages")
    assert a.status.outcome == "TRUNCATED" and a.raw.finish_reason == "max_tokens"
    th = call(srv, ["thinking:final text"], api="anthropic.messages")
    assert th.status.outcome == "ANSWERED" and th.raw.reasoning == "SUMMARY_ONLY"  # never claimed as raw reasoning
    assert th.cost.reasoning_tokens == 7 and th.cost.cache_write_tokens == 3  # thinking + cache writes are counted
    assert th.raw.visible_text == "final text"


@pytest.mark.parametrize("api", ["openai.chat.completions", "anthropic.messages"])
def test_malformed_bodies_keep_what_arrived(srv, api):
    m = call(srv, ["malformed"], api=api)
    assert m.status.outcome == "MALFORMED_RESPONSE" and "gateway" in (m.raw.body_text or "")
    w = call(srv, ["wrong_shape"], api=api)
    assert w.status.outcome == "MALFORMED_RESPONSE" and w.raw.body is not None


@pytest.mark.parametrize("api", ["openai.chat.completions", "anthropic.messages"])
def test_model_change_and_unnamed_model_are_recorded(srv, api):
    r = call(srv, ["other_model"], api=api)
    assert r.status.outcome == "ANSWERED" and r.call.model_switched and r.call.model_returned == "protocol-test-other"
    u = call(srv, ["no_model"], api=api)
    assert u.call.model_returned is None and u.call.model_identity == "UNKNOWN"


@pytest.mark.parametrize("api", ["openai.chat.completions", "anthropic.messages"])
def test_auth_errors_are_never_content_refusals_and_not_retried(srv, api):
    for code in ("401", "403"):
        n = len(srv.requests)
        r = call(srv, [code], api=api)
        assert r.status.outcome == "AUTH_ERROR" and r.status.http_status == int(code)
        assert len(srv.requests) == n + 1


def test_rate_limit_and_server_errors_use_the_fixed_retries(srv):
    ok = call(srv, ["429", 'answer:{"ok": true}'])
    assert ok.status.outcome == "ANSWERED" and ok.cost.http_attempts == 2
    rl = call(srv, ["429", "429", "429"], retries=2)
    assert rl.status.outcome == "RATE_LIMITED" and rl.cost.http_attempts == 3
    for code in ("500", "503"):
        pe = call(srv, [code] * 3, retries=2)
        assert pe.status.outcome == "PROVIDER_ERROR" and pe.cost.http_attempts == 3
    ov = call(srv, ["529"] * 2, api="anthropic.messages", retries=1)
    assert ov.status.outcome == "PROVIDER_ERROR" and ov.status.provider_error_type == "overloaded_error"


def test_model_unavailable_and_rejected_requests_are_not_retried(srv):
    gone = call(srv, ["404_model"])
    assert gone.status.outcome == "MODEL_UNAVAILABLE" and gone.cost.http_attempts == 1
    bad = call(srv, ["400"], api="anthropic.messages")
    assert bad.status.outcome == "REQUEST_REJECTED" and bad.status.provider_error_type == "invalid_request_error"


def test_lost_response_is_uncertain_and_possibly_billed(srv):
    b = ResearchBudget(max_calls=10, max_http_attempts=20)
    lost = call(srv, ["drop", "drop"], retries=1, budget=b)
    assert lost.status.outcome == "UNCERTAIN" and lost.cost.possibly_billed_unconfirmed == 2
    assert all(a.sent and not a.confirmed for a in lost.status.attempts) and b.possibly_billed == 2
    resampled = call(srv, ["drop", 'answer:{"ok": true}'], retries=1, budget=b)
    assert resampled.status.outcome == "ANSWERED" and resampled.cost.possibly_billed_unconfirmed == 1
    assert resampled.status.attempts[0].attempt_id != resampled.status.attempts[1].attempt_id


def test_timeout_after_sending_is_uncertain(srv):
    srv.script.append("hang:2")
    adapter, _ = research_adapter(cfg(srv), timeout_s=0.3)
    r = research_call(adapter, REQ, provider_config_id="p", route="LOOPBACK_TEST", network_retries=0,
                      budget=ResearchBudget(max_calls=1, max_http_attempts=1))
    assert r.status.outcome == "UNCERTAIN" and r.cost.possibly_billed_unconfirmed == 1


def test_unreachable_endpoint_is_a_transport_error_never_sent():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    c = ProviderConfig(provider_config_id="dead", provider="protocol-test", api="openai.chat.completions",
                       api_version="v1", route="LOOPBACK_TEST", base_url=f"http://127.0.0.1:{port}/v1",
                       model="protocol-test-v1")
    adapter, _ = research_adapter(c, timeout_s=2)
    r = research_call(adapter, REQ, provider_config_id="dead", route="LOOPBACK_TEST", network_retries=1,
                      backoff_s=0.01, budget=ResearchBudget(max_calls=1, max_http_attempts=5))
    assert r.status.outcome == "TRANSPORT_ERROR" and not any(a.sent for a in r.status.attempts)
    assert r.cost.possibly_billed_unconfirmed == 0


def test_budget_and_cancel_are_checked_before_sending(srv):
    nothing = call(srv, ["answer:x"], budget=ResearchBudget(max_calls=0, max_http_attempts=5))
    assert nothing.status.outcome == "BUDGET_EXHAUSTED" and len(srv.requests) == 0
    srv.script.clear()
    mid = call(srv, ["500", "500", "500"], budget=ResearchBudget(max_calls=5, max_http_attempts=2), retries=2)
    assert mid.status.outcome == "BUDGET_EXHAUSTED" and mid.cost.http_attempts == 2  # attempts so far are kept
    srv.script.clear()
    stop = threading.Event()
    stop.set()
    n = len(srv.requests)
    c = call(srv, ["answer:x"], cancel=stop)
    assert c.status.outcome == "CANCELLED" and len(srv.requests) == n


def test_no_credential_is_blocked_and_provider_env_vars_are_never_read(srv, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-never-be-used")
    with pytest.raises(InvalidInput):
        read_setting("ANTHROPIC_API_KEY")
    official = ProviderConfig(provider_config_id="claude", provider="anthropic", api="anthropic.messages",
                              api_version="2023-06-01", route="OFFICIAL_NATIVE", api_key_setting="FAL_ANTHROPIC_API_KEY",
                              model="claude-opus-5-5")
    monkeypatch.delenv("FAL_ANTHROPIC_API_KEY", raising=False)
    adapter, why = research_adapter(official, setting=lambda name: None)
    assert adapter is None and "FAL_ANTHROPIC_API_KEY" in why
    r = research_call(adapter, REQ, provider_config_id="claude", route="OFFICIAL_NATIVE", blocked_reason=why,
                      budget=ResearchBudget(max_calls=1, max_http_attempts=1), provider="anthropic",
                      api="anthropic.messages", model="claude-opus-5-5")
    assert r.status.outcome == "BLOCKED_NO_CREDENTIAL" and r.cost.http_attempts == 0
    assert r.call.model_requested == "claude-opus-5-5"


def test_declared_route_must_match_the_host(srv):
    lie = ProviderConfig(provider_config_id="lie", provider="openai", api="openai.chat.completions", api_version="v1",
                         route="OFFICIAL_NATIVE", base_url="https://relay.example.com/v1", api_key_setting="FAL_X",
                         model="gpt-6-astra")
    with pytest.raises(InvalidInput, match="COMPATIBLE_RELAY"):
        research_adapter(lie, setting=lambda name: "k")


def test_a_credential_echoed_by_a_gateway_never_reaches_the_record(srv, monkeypatch):
    monkeypatch.setenv("FAL_TEST_RESEARCH_KEY", "sk-test-UNIQUE-4242")
    srv.script.append("echo_auth")
    adapter, _ = research_adapter(cfg(srv, api_key_setting="FAL_TEST_RESEARCH_KEY"))
    r = research_call(adapter, REQ, provider_config_id="p", route="LOOPBACK_TEST",
                      budget=ResearchBudget(max_calls=1, max_http_attempts=1))
    blob = json.dumps([r.call.model_dump(), r.raw.model_dump(), r.status.model_dump(), r.cost.model_dump()])
    assert r.status.outcome == "REQUEST_REJECTED" and "sk-test-UNIQUE-4242" not in blob and "[REDACTED]" in blob
