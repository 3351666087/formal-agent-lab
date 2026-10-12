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

Phase 4A (A3): every call records what kind of endpoint *answered* — PROVIDER, PROTOCOL_TEST (the loopback test
service identifies itself with `x-formal-lab-endpoint: protocol-test`) or STUB — so provenance is taken from the
answer, not from configuration; the endpoint without credentials (no user-info, no query); a prompt digest and a
configuration digest; whether the provider answered with another model than requested (`model_switched`). A 4xx
other than 408 / 409 / 429 is PROVIDER_REJECTED, a cancellation CANCELLED. Tokens of a call without reported usage are
unknown (None in the record), never zero. `complete_json(max_attempts=…)` caps the retries of one call (budget).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx
import jsonschema
from formal_lab_contracts.errors import InvalidInput, NonRetryableFailure, RetryableFailure, Timeout

ENDPOINT_HEADER = "x-formal-lab-endpoint"


def public_endpoint(url: str) -> str:
    """An endpoint as it may be recorded: no user-info, query or fragment (where credentials could hide)."""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urllib.parse.urlunsplit((parts.scheme, host, parts.path.rstrip("/"), "", ""))


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


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
    endpoint_kind: str = "PROVIDER"


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
    # phase 4A (A3)
    endpoint_kind: str = "PROVIDER"  # what answered: PROVIDER / PROTOCOL_TEST / STUB
    endpoint: str | None = None  # without credentials
    prompt_digest: str | None = None
    config_digest: str | None = None
    business: str | None = None  # set by the decision: VALID / INVALID: reason
    model_switched: bool = False
    sent: bool = True

    def as_record(self) -> dict[str, Any]:
        unknown = not self.usage_reported  # missing usage stays unknown: never recorded as free
        return {"call_id": self.call_id, "model": self.model_returned or self.model_requested,
                "model_requested": self.model_requested, "model_returned": self.model_returned,
                "model_switched": self.model_switched, "outcome": self.outcome, "attempts": self.attempts,
                "sent": self.sent, "endpoint_kind": self.endpoint_kind, "endpoint": self.endpoint,
                "prompt_digest": self.prompt_digest, "config_digest": self.config_digest, "business": self.business,
                "request": self.request, "response": self.raw_text, "error": self.error,
                "input_tokens": None if unknown else self.input_tokens,
                "output_tokens": None if unknown else self.output_tokens, "usage_reported": self.usage_reported,
                "unconfirmed": self.unconfirmed, "latency_ms": self.latency_ms, "http_status": self.http_status}


class FormatError(RetryableFailure):
    """The model answered, but not in the requested structure."""


class ModelClient(Protocol):
    model: str
    is_stub: bool
    calls: list[ModelCall]

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any], max_attempts: int | None = None,
                      prompt_digest: str | None = None) -> ModelResponse: ...


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
                      payload: dict[str, Any], max_attempts: int | None = None,
                      prompt_digest: str | None = None) -> ModelResponse:
        limit = self.max_attempts if max_attempts is None else max(1, min(self.max_attempts, int(max_attempts)))
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
        }
        if self.temperature is not None:
            body["temperature"] = self.temperature
        request_record = {"model": self.model, "messages": body["messages"], "schema_name": schema_name,
                          "temperature": self.temperature, "timeout_s": self.timeout_s, "max_attempts": limit}
        endpoint = public_endpoint(self.base_url)
        call = ModelCall(call_id=f"call_{uuid.uuid4().hex[:12]}", model_requested=self.model,
                         outcome="TRANSPORT_ERROR", attempts=0, request=request_record, endpoint=endpoint,
                         prompt_digest=prompt_digest or _digest({"system": system, "schema": schema}),
                         config_digest=_digest({"model": self.model, "temperature": self.temperature,
                                                "timeout_s": self.timeout_s, "max_attempts": limit,
                                                "endpoint": endpoint}))
        self.calls.append(call)
        deadline = time.perf_counter() + self.timeout_s * limit
        t0 = time.perf_counter()
        delay = self.backoff_s
        resp = None
        while True:
            if self.cancel.is_set():
                call.error, call.outcome = "cancelled before sending", "CANCELLED"
                call.sent = call.attempts > 0
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
                    call.outcome = "PROVIDER_REJECTED"
                    raise NonRetryableFailure(f"model endpoint rejected the request ({resp.status_code}): "
                                              f"{resp.text[:300]}", details={"call": call.as_record()})
            if call.attempts >= limit or time.perf_counter() + delay > deadline:
                call.latency_ms = (time.perf_counter() - t0) * 1000
                if resp is None and "timeout" in (call.error or ""):
                    raise Timeout(f"model call timed out after {call.attempts} attempt(s): {call.error}",
                                  details={"call": call.as_record()})
                raise RetryableFailure(f"model endpoint unavailable after {call.attempts} attempt(s): {call.error}",
                                       details={"call": call.as_record()})
            retry_after = resp.headers.get("retry-after") if resp is not None else None
            wait = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else delay
            try:
                self._sleep(min(wait, self.max_backoff_s))
            except Timeout:
                call.outcome, call.error = "CANCELLED", f"cancelled after {call.attempts} attempt(s): {call.error}"
                raise
            delay = min(delay * 2, self.max_backoff_s)
        call.latency_ms = (time.perf_counter() - t0) * 1000
        if resp.headers.get(ENDPOINT_HEADER) == "protocol-test":
            call.endpoint_kind = "PROTOCOL_TEST"
        data = resp.json()
        usage = data.get("usage") or {}
        call.model_returned = data.get("model")
        call.model_switched = bool(call.model_returned) and call.model_returned != self.model \
            and not str(call.model_returned).startswith(f"{self.model}-")  # a dated variant is the same model
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
                             model_requested=self.model, attempts=call.attempts, endpoint_kind=call.endpoint_kind)


class StubModelClient:
    """Deterministic stand-in: among APPLICABLE/UNKNOWN candidates, the first by declared action-type preference
    (APPLICABLE before UNKNOWN within a type, then candidate index). Never presented as a real model.
    For task ordering (`payload["tasks"]`) it returns the tasks in the given order."""

    is_stub = True

    def __init__(self, model: str = "stub-deterministic-v1", preference: list[str] | None = None):
        self.model = model
        self.preference = list(preference or [])
        self.calls: list[ModelCall] = []
        self._seen: dict[str, int] = {}

    def _rank(self, cand: dict[str, Any]) -> tuple[int, int, int]:
        t = cand["action_type"]
        pref = self.preference.index(t) if t in self.preference else len(self.preference)
        return (pref, 0 if cand["applicability"] == "APPLICABLE" else 1, cand["index"])

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any], max_attempts: int | None = None,
                      prompt_digest: str | None = None) -> ModelResponse:
        if "tasks" in payload:
            content: dict[str, Any] = {"order": [t["id"] for t in payload["tasks"]],
                                       "rationale": "stub: tasks in the given order (deterministic stand-in)"}
        else:
            pool = sorted((c for c in payload["candidates"] if c["applicability"] in ("APPLICABLE", "UNKNOWN")),
                          key=self._rank)
            content = {"index": pool[0]["index"] if pool else 0,
                       "rationale": "stub: first candidate by declared preference (deterministic stand-in)"}
        # deterministic ids too (phase 4A): the same prompt gives the same id, so a resumed run equals the
        # uninterrupted one even where a plan carries the ids of the calls that generated it
        key = _digest({"model": self.model, "system": system, "user": user, "schema": schema_name})
        self._seen[key] = self._seen.get(key, 0) + 1
        call = ModelCall(call_id=f"stub_{key[:12]}_{self._seen[key]}", model_requested=self.model, outcome="OK",
                         attempts=1, model_returned=self.model, raw_text=json.dumps(content),
                         request={"schema_name": schema_name}, usage_reported=False, endpoint_kind="STUB",
                         endpoint="stub:", prompt_digest=prompt_digest or _digest({"system": system, "schema": schema}),
                         config_digest=_digest({"model": self.model, "preference": self.preference}))
        self.calls.append(call)
        return ModelResponse(content=content, raw_text=call.raw_text or "", model=self.model, call_id=call.call_id,
                             usage_reported=False, model_requested=self.model, endpoint_kind="STUB")


# ===================================================================================== phase 6A: research calls
# A research call is not a decision: one request (plus a fixed number of network retries), the provider's answer
# saved as returned, and its outcome classified on the call axis only — no JSON forcing, no re-asking, no rule
# fallback. Parsing and scoring happen later, on the saved record (formal_lab_eval.research).

OFFICIAL_HOSTS = {"openai": "api.openai.com", "anthropic": "api.anthropic.com"}
OFFICIAL_BASE = {"openai": "https://api.openai.com/v1", "anthropic": "https://api.anthropic.com"}
ANTHROPIC_VERSION = "2023-06-01"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
SETTING_PREFIX = "FAL_"
_MODEL_GONE = ("model_not_found", "not found", "does not exist", "not exist", "unavailable", "not available",
               "no available", "not supported", "no such model")


def read_setting(name: str, *, env_file: Path | None = None) -> str | None:
    """A setting for the model-call adapters, by name — the only place research credentials are read. Only `FAL_*`
    names are accepted, so a provider's own environment variable (e.g. ANTHROPIC_API_KEY) is never used."""
    if not name.startswith(SETTING_PREFIX):
        raise InvalidInput(f"setting {name!r} is not a {SETTING_PREFIX}* setting; research adapters read no other names")
    if os.environ.get(name):
        return os.environ[name]
    candidates = [env_file] if env_file else [p / ".env" for p in (Path.cwd(), *Path.cwd().parents[:3])]
    for path in candidates:
        if path is not None and path.is_file():
            for line in path.read_text().splitlines():
                m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
                if m and m.group(1) == name:
                    return m.group(2).strip().strip('"').strip("'") or None
            return None
    return None


def route_of(provider: str, url: str) -> str:
    host = urllib.parse.urlsplit(url).hostname or ""
    if host in LOOPBACK_HOSTS:
        return "LOOPBACK_TEST"
    if host == OFFICIAL_HOSTS.get(provider):
        return "OFFICIAL_NATIVE"
    return "COMPATIBLE_RELAY"


def sha256_text(obj: Any) -> str:
    data = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class ResearchRequest:
    user: str
    system: str | None = None
    params: dict[str, Any] = field(default_factory=dict)  # sampling parameters, sent verbatim
    response_schema: dict[str, Any] | None = None  # optional structured output (OpenAI); research default: none


@dataclass
class ResearchBudget:
    """Study-wide limits, checked before every call and every HTTP attempt. Counters are rebuilt from the study's
    ledger on resume, so a resumed study never regains what it already spent."""

    max_calls: int
    max_http_attempts: int
    max_total_output_tokens: int | None = None
    calls: int = 0
    http_attempts: int = 0
    output_tokens: int = 0
    possibly_billed: int = 0
    unknown_usage_calls: int = 0

    def check_call(self) -> str | None:
        if self.calls >= self.max_calls:
            return f"call budget exhausted ({self.calls}/{self.max_calls})"
        if self.max_total_output_tokens is not None and self.output_tokens >= self.max_total_output_tokens:
            return f"output-token budget exhausted ({self.output_tokens}/{self.max_total_output_tokens})"
        return None

    def check_attempt(self) -> str | None:
        if self.http_attempts >= self.max_http_attempts:
            return f"HTTP-attempt budget exhausted ({self.http_attempts}/{self.max_http_attempts})"
        return None


class _Malformed(ValueError):
    pass


@dataclass
class _Parsed:
    visible_text: str | None
    finish_reason: str | None
    finish_class: str
    refusal: str | None
    tool_calls: list[dict[str, Any]]
    reasoning: str
    model: str | None
    response_id: str | None
    usage: dict[str, int | None]
    usage_known: bool


class _ResearchAdapter:
    provider = ""
    api = ""
    api_version = ""

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_s: float = 120.0,
                 transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.secret = api_key
        loopback = (urllib.parse.urlsplit(self.base_url).hostname or "") in LOOPBACK_HOSTS
        self._client = httpx.Client(timeout=httpx.Timeout(timeout_s, connect=10.0), transport=transport,
                                    headers=self.auth_headers(api_key), trust_env=not loopback)

    url = ""

    @property
    def endpoint(self) -> str:
        return public_endpoint(self.url)

    def auth_headers(self, key: str) -> dict[str, str]:
        raise NotImplementedError

    def body(self, req: ResearchRequest) -> dict[str, Any]:
        raise NotImplementedError

    def parse(self, data: dict[str, Any]) -> _Parsed:
        raise NotImplementedError

    def error_type(self, data: Any) -> str | None:
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            return str(err.get("type") or err.get("code") or "") or None
        return None

    def send(self, body: dict[str, Any]) -> httpx.Response:
        return self._client.post(self.url, json=body)

    def close(self) -> None:
        self._client.close()


class OpenAIChatAdapter(_ResearchAdapter):
    """Chat Completions (official api.openai.com or an OpenAI-compatible relay): the message content, the explicit
    `message.refusal` field, `finish_reason` (stop / length / content_filter / tool_calls) and usage as reported."""

    provider, api, api_version = "openai", "openai.chat.completions", "v1"

    @property
    def url(self) -> str:  # type: ignore[override]
        return f"{self.base_url}/chat/completions"

    def auth_headers(self, key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {key}"}

    def body(self, req: ResearchRequest) -> dict[str, Any]:
        messages = ([{"role": "system", "content": req.system}] if req.system else []) + \
            [{"role": "user", "content": req.user}]
        body: dict[str, Any] = {"model": self.model, "messages": messages, **req.params}
        if req.response_schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "answer", "strict": True, "schema": req.response_schema}}
        return body

    def parse(self, data: dict[str, Any]) -> _Parsed:
        try:
            choice = data["choices"][0]
            msg = choice.get("message") or {}
        except (KeyError, IndexError, TypeError) as exc:
            raise _Malformed("no choices[0].message in the body") from exc
        content = msg.get("content")
        if isinstance(content, list):  # some relays return content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        finish = choice.get("finish_reason")
        refusal = msg.get("refusal") or None
        fclass = {"stop": "STOP", "length": "LENGTH", "content_filter": "CONTENT_FILTER", "tool_calls": "TOOL_USE",
                  "function_call": "TOOL_USE"}.get(str(finish), "OTHER" if finish else "UNKNOWN")
        if refusal:
            fclass = "REFUSAL"
        tools = [{"name": (t.get("function") or {}).get("name"), "arguments_chars":
                  len((t.get("function") or {}).get("arguments") or "")} for t in msg.get("tool_calls") or []]
        reasoning = "SUMMARY_ONLY" if (msg.get("reasoning_content") or msg.get("reasoning")) else "NOT_EXPOSED"
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        known = isinstance(usage.get("prompt_tokens"), int) and isinstance(usage.get("completion_tokens"), int)
        return _Parsed(visible_text=content if isinstance(content, str) else None, finish_reason=finish,
                       finish_class=fclass, refusal=refusal, tool_calls=tools, reasoning=reasoning,
                       model=data.get("model"), response_id=data.get("id"),
                       usage={"input": usage.get("prompt_tokens"), "output": usage.get("completion_tokens"),
                              "reasoning": details.get("reasoning_tokens"), "cache_read": cached, "cache_write": None},
                       usage_known=known)


class AnthropicMessagesAdapter(_ResearchAdapter):
    """The native Messages API: text blocks, `stop_reason` (end_turn / max_tokens / refusal / tool_use / pause_turn),
    thinking blocks recorded only as a provider summary (never as raw reasoning), usage as reported."""

    provider, api, api_version = "anthropic", "anthropic.messages", ANTHROPIC_VERSION

    @property
    def url(self) -> str:  # type: ignore[override]
        return f"{self.base_url}/messages" if self.base_url.endswith("/v1") else f"{self.base_url}/v1/messages"

    def auth_headers(self, key: str) -> dict[str, str]:
        return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}

    def body(self, req: ResearchRequest) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "messages": [{"role": "user", "content": req.user}],
                                **req.params}
        body.setdefault("max_tokens", 1024)  # required by the Messages API
        if req.system:
            body["system"] = req.system
        return body

    def parse(self, data: dict[str, Any]) -> _Parsed:
        blocks = data.get("content")
        if data.get("type") != "message" or not isinstance(blocks, list):
            raise _Malformed("not a Messages API message")
        texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
        thinking = any(isinstance(b, dict) and b.get("type") in ("thinking", "redacted_thinking") for b in blocks)
        tools = [{"name": b.get("name"), "input_chars": len(json.dumps(b.get("input") or {}))}
                 for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"]
        stop = data.get("stop_reason")
        fclass = {"end_turn": "STOP", "stop_sequence": "STOP", "max_tokens": "LENGTH", "refusal": "REFUSAL",
                  "tool_use": "TOOL_USE", "pause_turn": "PAUSE"}.get(str(stop), "OTHER" if stop else "UNKNOWN")
        usage = data.get("usage") or {}
        known = isinstance(usage.get("input_tokens"), int) and isinstance(usage.get("output_tokens"), int)
        return _Parsed(visible_text="".join(texts) if texts else None, finish_reason=stop, finish_class=fclass,
                       refusal="stop_reason=refusal" if stop == "refusal" else None, tool_calls=tools,
                       reasoning="SUMMARY_ONLY" if thinking else "NOT_EXPOSED", model=data.get("model"),
                       response_id=data.get("id"),
                       usage={"input": usage.get("input_tokens"), "output": usage.get("output_tokens"),
                              "reasoning": (usage.get("output_tokens_details") or {}).get("thinking_tokens"),
                              "cache_read": usage.get("cache_read_input_tokens"),
                              "cache_write": usage.get("cache_creation_input_tokens")},
                       usage_known=known)


def research_adapter(cfg: Any, *, transport: httpx.BaseTransport | None = None, timeout_s: float = 120.0,
                     setting: Any = read_setting) -> tuple[_ResearchAdapter | None, str | None]:
    """The adapter for a study's ProviderConfig, or (None, why) when no authorized endpoint / credential is set.
    The declared route must be what the endpoint host is — a relay is never recorded as an official endpoint."""
    family = cfg.provider if cfg.provider in OFFICIAL_HOSTS else ("openai" if cfg.api.startswith("openai") else "anthropic")
    base = cfg.base_url or (setting(cfg.base_url_setting) if cfg.base_url_setting else None)
    if not base and str(cfg.route) == "OFFICIAL_NATIVE":
        base = OFFICIAL_BASE[family]
    if not base:
        return None, f"no endpoint configured ({cfg.base_url_setting or 'base_url'} is empty)"
    actual = route_of(family, base)
    if actual != str(cfg.route):
        raise InvalidInput(f"provider {cfg.provider_config_id}: declared route {cfg.route} but {public_endpoint(base)} "
                           f"is {actual}")
    key = setting(cfg.api_key_setting) if cfg.api_key_setting else ("loopback-test" if actual == "LOOPBACK_TEST"
                                                                     else None)
    if not key:
        return None, f"no authorized credential configured ({cfg.api_key_setting or 'api_key_setting'} is empty)"
    cls = OpenAIChatAdapter if cfg.api == "openai.chat.completions" else AnthropicMessagesAdapter
    return cls(base_url=base, api_key=key, model=cfg.model, timeout_s=timeout_s, transport=transport), None


@dataclass
class ResearchCallResult:
    call: Any  # CallIdentity
    raw: Any  # RawAnswer
    status: Any  # CallStatus
    cost: Any  # CostRecord


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def research_call(adapter: _ResearchAdapter | None, req: ResearchRequest, *, provider_config_id: str, route: str,
                  budget: ResearchBudget, cancel: threading.Event | None = None, network_retries: int = 2,
                  backoff_s: float = 0.5, max_backoff_s: float = 8.0, blocked_reason: str | None = None,
                  provider: str | None = None, api: str | None = None, model: str | None = None) -> ResearchCallResult:
    """One research call. Cancellation and the budget are checked before anything is sent; only transport faults,
    lost responses, 429 and 5xx are retried (a fixed number of times); a refusal or any other answer is returned as
    it came. Every HTTP attempt is recorded; an attempt that was sent but got no response counts as possibly billed."""
    from formal_lab_contracts.research import (
        AttemptRecord,
        CallIdentity,
        CallStatus,
        CostRecord,
        RawAnswer,
    )

    secret = adapter.secret if adapter is not None else ""

    def redact(text: Any, limit: int = 500) -> str:
        s = str(text)
        if secret:
            s = s.replace(secret, "[REDACTED]")
        return s[:limit]

    params = dict(req.params)
    started = _now()
    prompt_digest = sha256_text({"system": req.system, "user": req.user})
    identity = {"provider": adapter.provider if adapter else (provider or "unknown"),
                "provider_config_id": provider_config_id,
                "api": adapter.api if adapter else (api or "unknown"),
                "api_version": adapter.api_version if adapter else "n/a",
                "endpoint": adapter.endpoint if adapter else "n/a", "route": route, "endpoint_kind": "PROVIDER",
                "model_requested": adapter.model if adapter else (model or "unknown"), "started_at": started,
                "params": params, "params_digest": sha256_text(params)[:16]}
    config_digest = sha256_text({k: identity[k] for k in ("provider", "api", "api_version", "endpoint", "route",
                                                          "model_requested", "params")})[:16]
    attempts: list[AttemptRecord] = []
    t_all = time.perf_counter()

    def finish(outcome: str, *, raw: dict[str, Any] | None = None, parsed: _Parsed | None = None,
               http_status: int | None = None, etype: str | None = None, error: str | None = None,
               note: str | None = None, endpoint_kind: str = "PROVIDER", request_id: str | None = None
               ) -> ResearchCallResult:
        model_returned = parsed.model if parsed else None
        switched = bool(model_returned) and model_returned != identity["model_requested"] \
            and not str(model_returned).startswith(f"{identity['model_requested']}-")
        if not model_returned:
            mid = "UNKNOWN"  # the response named no model: unknown, wherever it came from
        elif endpoint_kind == "PROTOCOL_TEST" or route == "LOOPBACK_TEST":
            mid = "TEST_SERVICE"
        else:
            mid = "CONFIRMED_BY_PROVIDER" if route == "OFFICIAL_NATIVE" else "RELAY_REPORTED"
        call = CallIdentity(**{**identity, "endpoint_kind": endpoint_kind, "model_returned": model_returned,
                               "model_switched": switched, "model_identity": mid,
                               "response_id": parsed.response_id if parsed else None, "request_id": request_id,
                               "finished_at": _now()})
        rawans = RawAnswer(**(raw or {}))
        usage = parsed.usage if parsed else {}
        known = bool(parsed and parsed.usage_known)
        if parsed is not None:
            if known:
                budget.output_tokens += int(usage.get("output") or 0)
            else:
                budget.unknown_usage_calls += 1
        sent_unconfirmed = sum(1 for a in attempts if a.sent and not a.confirmed)
        status = CallStatus(outcome=outcome, transport_ok=any(a.confirmed for a in attempts),
                            http_status=http_status, provider_error_type=etype, provider_error=error,
                            model_switched=switched, attempts=attempts, network_retries=network_retries, note=note)
        cost = CostRecord(usage_known=known, input_tokens=usage.get("input") if known else None,
                          output_tokens=usage.get("output") if known else None,
                          reasoning_tokens=usage.get("reasoning") if known else None,
                          cache_read_tokens=usage.get("cache_read") if known else None,
                          cache_write_tokens=usage.get("cache_write") if known else None,
                          latency_ms=round((time.perf_counter() - t_all) * 1000, 1), http_attempts=len(attempts),
                          possibly_billed_unconfirmed=sent_unconfirmed, prompt_digest=prompt_digest[:16],
                          config_digest=config_digest)
        return ResearchCallResult(call=call, raw=rawans, status=status, cost=cost)

    if adapter is None:
        return finish("BLOCKED_NO_CREDENTIAL", note=blocked_reason or "no authorized endpoint", endpoint_kind="NONE")
    if cancel is not None and cancel.is_set():
        return finish("CANCELLED", note="cancelled before sending")
    reason = budget.check_call()
    if reason:
        return finish("BUDGET_EXHAUSTED", note=reason)
    budget.calls += 1
    body = adapter.body(req)
    delay, last = backoff_s, ("TRANSPORT_ERROR", None, None, None)
    for n in range(1, network_retries + 2):
        if n > 1:
            wait = min(last[3] if last[3] is not None else delay, max_backoff_s)
            if cancel is not None and cancel.wait(wait):
                return finish("CANCELLED", note=f"cancelled after {n - 1} attempt(s); last {last[0]}",
                              http_status=last[1])
            if cancel is None:
                time.sleep(wait)
            delay = min(delay * 2, max_backoff_s)
        reason = budget.check_attempt()
        if reason:
            return finish("BUDGET_EXHAUSTED", note=f"{reason}; last {last[0]}" if n > 1 else reason,
                          http_status=last[1])
        budget.http_attempts += 1
        aid, t0 = f"att_{uuid.uuid4().hex[:12]}", time.perf_counter()

        def record(sent: bool, confirmed: bool, cls: str | None, err: str | None = None, code: int | None = None,
                   aid: str = aid, t0: float = t0, n: int = n) -> None:
            attempts.append(AttemptRecord(attempt_no=n, attempt_id=aid, sent=sent, confirmed=confirmed,
                                          http_status=code, error_class=cls, error=redact(err) if err else None,
                                          latency_ms=round((time.perf_counter() - t0) * 1000, 1)))

        try:
            resp = adapter.send(body)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            record(False, False, "TRANSPORT_ERROR", f"{type(exc).__name__}: {exc}")
            last = ("TRANSPORT_ERROR", None, None, None)
            continue
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError, httpx.ReadError,
                httpx.WriteError) as exc:
            record(True, False, "UNCERTAIN", f"{type(exc).__name__}: {exc}")
            budget.possibly_billed += 1
            last = ("UNCERTAIN", None, None, None)
            continue
        except httpx.HTTPError as exc:
            record(False, False, "TRANSPORT_ERROR", f"{type(exc).__name__}: {exc}")
            last = ("TRANSPORT_ERROR", None, None, None)
            continue
        code = resp.status_code
        kind = "PROTOCOL_TEST" if resp.headers.get(ENDPOINT_HEADER) == "protocol-test" else "PROVIDER"
        request_id = resp.headers.get("request-id") or resp.headers.get("x-request-id")
        text = redact(resp.text, 20000)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if code < 400:
            record(True, True, None, code=code)
            if not isinstance(data, dict):
                return finish("MALFORMED_RESPONSE", raw={"body_text": text}, http_status=code, endpoint_kind=kind,
                              request_id=request_id, note="HTTP success, but the body is not JSON")
            try:
                parsed = adapter.parse(data)
            except _Malformed as exc:
                return finish("MALFORMED_RESPONSE", raw={"body": data}, http_status=code, endpoint_kind=kind,
                              request_id=request_id, note=f"HTTP success, not the {adapter.api} protocol: {exc}")
            visible = parsed.visible_text
            raw = {"body": data, "visible_text": visible, "finish_reason": parsed.finish_reason,
                   "finish_class": parsed.finish_class, "refusal": parsed.refusal,
                   "truncated": parsed.finish_class == "LENGTH", "tool_calls": parsed.tool_calls,
                   "reasoning": parsed.reasoning}
            if parsed.refusal or parsed.finish_class in ("REFUSAL", "CONTENT_FILTER"):
                outcome = "CONTENT_REFUSAL"
            elif parsed.finish_class == "LENGTH":
                outcome = "TRUNCATED"
            elif not (visible or "").strip():
                outcome = "EMPTY_CONTENT"
            else:
                outcome = "ANSWERED"
            return finish(outcome, raw=raw, parsed=parsed, http_status=code, endpoint_kind=kind,
                          request_id=request_id)
        etype = adapter.error_type(data)
        gone = code not in (401, 403, 429) and any(g in text.lower() for g in _MODEL_GONE) and "model" in text.lower()
        record(True, True, f"HTTP_{code}", text, code)
        if code in (401, 403):
            return finish("AUTH_ERROR", http_status=code, etype=etype, error=redact(text), endpoint_kind=kind,
                          request_id=request_id, note="authentication / permission — not a content refusal")
        if code == 429 or code >= 500 or code in (408, 409, 425):
            if gone and code >= 500:
                return finish("MODEL_UNAVAILABLE", http_status=code, etype=etype, error=redact(text),
                              endpoint_kind=kind, request_id=request_id)
            ra = resp.headers.get("retry-after")
            retry_after = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
            last = ("RATE_LIMITED" if code == 429 else "PROVIDER_ERROR", code, (etype, redact(text), kind, request_id),
                    retry_after)
            continue
        return finish("MODEL_UNAVAILABLE" if gone else "REQUEST_REJECTED", http_status=code, etype=etype,
                      error=redact(text), endpoint_kind=kind, request_id=request_id)
    outcome, code, extra = last[0], last[1], last[2]
    if extra is not None:
        etype, err, kind, request_id = extra
        return finish(outcome, http_status=code, etype=etype, error=err, endpoint_kind=kind, request_id=request_id,
                      note=f"after {len(attempts)} attempt(s) with {network_retries} fixed retries")
    return finish(outcome, note=f"after {len(attempts)} attempt(s) with {network_retries} fixed retries")
