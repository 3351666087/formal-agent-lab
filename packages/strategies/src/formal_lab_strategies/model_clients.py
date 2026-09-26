"""Model clients used by LLM strategies.

`OpenAICompatibleClient` calls a Chat Completions endpoint with JSON-Schema structured output.
`StubModelClient` is a deterministic stand-in: proposals made with it are labelled LLM_STUB and must be
reported separately from real-model results.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
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


class ModelClient(Protocol):
    model: str
    is_stub: bool

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any]) -> ModelResponse: ...


class OpenAICompatibleClient:
    is_stub = False

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_s: float = 120.0,
                 transport: httpx.BaseTransport | None = None):
        if not api_key:
            raise InvalidInput("FAL_LLM_API_KEY is not configured")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=timeout_s, transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"})

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any]) -> ModelResponse:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
        }
        t0 = time.perf_counter()
        try:
            resp = self._client.post(f"{self.base_url}/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise Timeout(f"model call timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RetryableFailure(f"model endpoint unreachable: {exc}") from exc
        latency = (time.perf_counter() - t0) * 1000
        if resp.status_code == 429 or resp.status_code >= 500:
            raise RetryableFailure(f"model endpoint returned {resp.status_code}: {resp.text[:300]}")
        if resp.status_code >= 400:
            raise NonRetryableFailure(f"model endpoint rejected the request ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
            content = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RetryableFailure(f"model returned no parseable JSON: {str(data)[:300]}") from exc
        usage = data.get("usage") or {}
        return ModelResponse(
            content=content,
            raw_text=text,
            model=data.get("model") or self.model,
            call_id=data.get("id") or f"call_{uuid.uuid4().hex[:12]}",
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency,
            request={"model": self.model, "messages": body["messages"], "schema_name": schema_name},
        )


class StubModelClient:
    """Deterministic stand-in: among APPLICABLE/UNKNOWN candidates, the first by declared action-type preference
    (APPLICABLE before UNKNOWN within a type, then candidate index). Never presented as a real model."""

    is_stub = True

    def __init__(self, model: str = "stub-deterministic-v1", preference: list[str] | None = None):
        self.model = model
        self.preference = list(preference or [])

    def _rank(self, cand: dict[str, Any]) -> tuple[int, int, int]:
        t = cand["action_type"]
        pref = self.preference.index(t) if t in self.preference else len(self.preference)
        return (pref, 0 if cand["applicability"] == "APPLICABLE" else 1, cand["index"])

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any]) -> ModelResponse:
        pool = sorted((c for c in payload["candidates"] if c["applicability"] in ("APPLICABLE", "UNKNOWN")),
                      key=self._rank)
        pick = pool[0]["index"] if pool else 0
        content = {"index": pick, "rationale": "stub: first candidate by declared preference (deterministic stand-in)"}
        return ModelResponse(content=content, raw_text=json.dumps(content), model=self.model,
                             call_id=f"stub_{uuid.uuid4().hex[:12]}")
