"""Model clients used by model-assisted strategies (P2-044 / P2-045).

`OpenAICompatibleClient` calls a Chat Completions endpoint with JSON-Schema structured output. Every request is
recorded as a `ModelCall` whose `outcome` keeps three kinds of failure apart:

- TRANSPORT_ERROR  — no usable HTTP answer (timeout, connection error, 5xx, 429 after the retries, cancelled);
- FORMAT_ERROR     — an answer arrived but is not valid JSON or does not satisfy the response schema;
- OK               — a schema-valid answer (whether the *business* content is acceptable — e.g. a candidate index
                     in range — is judged by the strategy and recorded separately).

Rate limits (429) and transient 5xx are retried with exponential backoff (honouring `Retry-After`) within the
request deadline; a cancellation event aborts between attempts. Every call records the model the provider says it
answered with (`model_returned`) next to the configured model label (`model_requested`), the request configuration
and the usage exactly as reported (`usage_reported=False` when the provider sent none; a lost response counts as
`unconfirmed`).

`StubModelClient` is a deterministic stand-in: proposals made with it are labelled LLM_STUB and must be reported
separately from real-model results.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import jsonschema
from formal_lab_contracts.errors import InvalidInput, NonRetryableFailure, RetryableFailure, Timeout


@dataclass
class ModelResponse:
    content: dict[str, Any]
    raw_text: str
    model: str
    call_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    request: dict[str, Any] = field(default_factory=dict)
    usage_reported: bool = True
    model_requested: str | None = None
    attempts: int = 1


@dataclass
class ModelCall:
    """One logical model call (possibly several HTTP attempts) and how it ended."""

    call_id: str
    model_requested: str
    outcome: str  # OK | TRANSPORT_ERROR | FORMAT_ERROR
    attempts: int
    model_returned: str | None = None
    request: dict[str, Any] = field(default_factory=dict)
    raw_text: str | None = None
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    usage_reported: bool = False
    unconfirmed: bool = False  # sent, but no answer arrived (it may still be billed)
    latency_ms: float = 0.0
    http_status: int | None = None

    def as_record(self) -> dict[str, Any]:
        return {"call_id": self.call_id, "model": self.model_returned or self.model_requested,
                "model_requested": self.model_requested, "model_returned": self.model_returned,
                "outcome": self.outcome, "attempts": self.attempts, "request": self.request,
                "response": self.raw_text, "error": self.error, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "usage_reported": self.usage_reported,
                "unconfirmed": self.unconfirmed, "latency_ms": self.latency_ms, "http_status": self.http_status}


class FormatError(RetryableFailure):
    """The model answered, but not in the requested structure."""


class ModelClient(Protocol):
    model: str
    is_stub: bool
    calls: list[ModelCall]

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any]) -> ModelResponse: ...


class OpenAICompatibleClient:
    is_stub = False

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_s: float = 120.0,
                 transport: httpx.BaseTransport | None = None, max_attempts: int = 4, backoff_s: float = 1.0,
                 max_backoff_s: float = 20.0, cancel: threading.Event | None = None, temperature: float | None = None):
        if not api_key:
            raise InvalidInput("FAL_LLM_API_KEY is not configured")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.max_backoff_s = max_backoff_s
        self.cancel = cancel or threading.Event()
        self.temperature = temperature
        self.calls: list[ModelCall] = []
        self._client = httpx.Client(timeout=timeout_s, transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"})

    def _sleep(self, seconds: float) -> None:
        if self.cancel.wait(seconds):
            raise Timeout("model call cancelled")

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any]) -> ModelResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
        }
        if self.temperature is not None:
            body["temperature"] = self.temperature
        request_record = {"model": self.model, "messages": body["messages"], "schema_name": schema_name,
                          "temperature": self.temperature, "timeout_s": self.timeout_s,
                          "max_attempts": self.max_attempts}
        call = ModelCall(call_id=f"call_{uuid.uuid4().hex[:12]}", model_requested=self.model,
                         outcome="TRANSPORT_ERROR", attempts=0, request=request_record)
        self.calls.append(call)
        deadline = time.perf_counter() + self.timeout_s * self.max_attempts
        t0 = time.perf_counter()
        delay = self.backoff_s
        resp = None
        while True:
            if self.cancel.is_set():
                call.error = "cancelled before sending"
                raise Timeout("model call cancelled")
            call.attempts += 1
            try:
                resp = self._client.post(f"{self.base_url}/chat/completions", json=body)
            except httpx.TimeoutException as exc:
                call.unconfirmed, call.error = True, f"timeout: {exc}"
                resp = None
            except httpx.HTTPError as exc:
                call.error = f"unreachable: {exc}"
                resp = None
            if resp is not None:
                call.http_status = resp.status_code
                if resp.status_code < 400:
                    call.unconfirmed = False
                    break
                call.error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                if resp.status_code not in (408, 409, 429) and resp.status_code < 500:
                    call.latency_ms = (time.perf_counter() - t0) * 1000
                    raise NonRetryableFailure(f"model endpoint rejected the request ({resp.status_code}): "
                                              f"{resp.text[:300]}", details={"call": call.as_record()})
            if call.attempts >= self.max_attempts or time.perf_counter() + delay > deadline:
                call.latency_ms = (time.perf_counter() - t0) * 1000
                if resp is None and "timeout" in (call.error or ""):
                    raise Timeout(f"model call timed out after {call.attempts} attempt(s): {call.error}",
                                  details={"call": call.as_record()})
                raise RetryableFailure(f"model endpoint unavailable after {call.attempts} attempt(s): {call.error}",
                                       details={"call": call.as_record()})
            retry_after = resp.headers.get("retry-after") if resp is not None else None
            wait = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else delay
            self._sleep(min(wait, self.max_backoff_s))
            delay = min(delay * 2, self.max_backoff_s)
        call.latency_ms = (time.perf_counter() - t0) * 1000
        data = resp.json()
        usage = data.get("usage") or {}
        call.model_returned = data.get("model")
        call.usage_reported = bool(usage)
        call.input_tokens = int(usage.get("prompt_tokens") or 0)
        call.output_tokens = int(usage.get("completion_tokens") or 0)
        if data.get("id"):
            call.call_id = data["id"]
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            call.outcome, call.error = "FORMAT_ERROR", f"no message content: {str(data)[:300]}"
            raise FormatError(call.error, details={"call": call.as_record()}) from exc
        call.raw_text = text
        try:
            content = json.loads(text)
            jsonschema.validate(content, schema)
        except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
            call.outcome = "FORMAT_ERROR"
            call.error = f"answer is not valid {schema_name} JSON: {getattr(exc, 'message', str(exc))}"
            raise FormatError(call.error, details={"call": call.as_record()}) from exc
        call.outcome, call.error = "OK", None
        return ModelResponse(content=content, raw_text=text, model=call.model_returned or self.model,
                             call_id=call.call_id, input_tokens=call.input_tokens, output_tokens=call.output_tokens,
                             latency_ms=call.latency_ms, request=request_record, usage_reported=call.usage_reported,
                             model_requested=self.model, attempts=call.attempts)


class StubModelClient:
    """Deterministic stand-in: among APPLICABLE/UNKNOWN candidates, the first by declared action-type preference
    (APPLICABLE before UNKNOWN within a type, then candidate index). Never presented as a real model.
    For task ordering (`payload["tasks"]`) it returns the tasks in the given order."""

    is_stub = True

    def __init__(self, model: str = "stub-deterministic-v1", preference: list[str] | None = None):
        self.model = model
        self.preference = list(preference or [])
        self.calls: list[ModelCall] = []

    def _rank(self, cand: dict[str, Any]) -> tuple[int, int, int]:
        t = cand["action_type"]
        pref = self.preference.index(t) if t in self.preference else len(self.preference)
        return (pref, 0 if cand["applicability"] == "APPLICABLE" else 1, cand["index"])

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any]) -> ModelResponse:
        if "tasks" in payload:
            content: dict[str, Any] = {"order": [t["id"] for t in payload["tasks"]],
                                       "rationale": "stub: tasks in the given order (deterministic stand-in)"}
        else:
            pool = sorted((c for c in payload["candidates"] if c["applicability"] in ("APPLICABLE", "UNKNOWN")),
                          key=self._rank)
            content = {"index": pool[0]["index"] if pool else 0,
                       "rationale": "stub: first candidate by declared preference (deterministic stand-in)"}
        call = ModelCall(call_id=f"stub_{uuid.uuid4().hex[:12]}", model_requested=self.model, outcome="OK",
                         attempts=1, model_returned=self.model, raw_text=json.dumps(content),
                         request={"schema_name": schema_name}, usage_reported=False)
        self.calls.append(call)
        return ModelResponse(content=content, raw_text=call.raw_text or "", model=self.model, call_id=call.call_id,
                             usage_reported=False, model_requested=self.model)
