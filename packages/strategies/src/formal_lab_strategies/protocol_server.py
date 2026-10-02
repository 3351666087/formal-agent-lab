"""Protocol test service (phase 4A): a loopback endpoint that speaks the OpenAI-compatible Chat Completions protocol.

It is **not a model**. It exists so the real client and the real planner factory can be exercised end to end — HTTP,
JSON-Schema structured output, retries, usage accounting, call records — without a provider, and so tests can read
exactly what left the planner (every request body is recorded; the Authorization header only as present / a short
digest, never its value). Its answers are deterministic and schema-valid: for a decision payload, the first APPLICABLE
candidate (else UNKNOWN, else index 0); for a task-ordering payload, the given order. It reports the model name
`protocol-test-v1` and answers with the header `x-formal-lab-endpoint: protocol-test`, so a client can tell its
answers apart from a provider's by the answer itself (not by configuration); results made with it are never counted
as real-model results.

Answers and faults can be scripted per request (`script`): "ok", "pick:<index>", "429", "500", "401",
"bad_json", "schema_violation", "out_of_range", "no_usage", "switch_model", "hang:<seconds>".

    python -m formal_lab_strategies.protocol_server --port 8799     # base URL http://127.0.0.1:8799/v1
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MODEL = "protocol-test-v1"
LABEL = "PROTOCOL_TEST"  # not a model: how results made with this service are labelled
ENDPOINT_HEADER = "x-formal-lab-endpoint"
ENDPOINT_KIND = "protocol-test"


def _decision(payload: dict[str, Any]) -> dict[str, Any]:
    if "tasks" in payload:
        return {"order": [t["id"] for t in payload["tasks"]], "rationale": "protocol test service: given order"}
    cands = payload.get("candidates") or []
    for wanted in ("APPLICABLE", "UNKNOWN"):
        hit = next((c for c in cands if c.get("applicability") == wanted), None)
        if hit is not None:
            return {"index": hit["index"], "rationale": f"protocol test service: first {wanted} candidate"}
    return {"index": 0, "rationale": "protocol test service: no applicable candidate, index 0"}


def _payload_of(body: dict[str, Any]) -> dict[str, Any]:
    user = next((m["content"] for m in body.get("messages", []) if m.get("role") == "user"), "")
    text = user.split("\n", 1)[1] if user.startswith("Decision input (JSON):") else user
    text = text.split("\n\nYour previous answer was invalid", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


class ProtocolTestServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, script: list[str] | None = None):
        self.requests: list[dict[str, Any]] = []
        self.script: deque[str] = deque(script or [])
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):  # quiet
                return

            def _send(self, code: int, obj: Any, raw: bytes | None = None) -> None:
                data = raw if raw is not None else json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.send_header(ENDPOINT_HEADER, ENDPOINT_KIND)  # how a client tells it apart from a provider
                if code == 429:
                    self.send_header("retry-after", "0")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    return self._send(200, {"object": "list", "data": [{"id": MODEL, "object": "model"}]})
                return self._send(404, {"error": "not found"})

            def do_POST(self):
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw or b"{}")
                except json.JSONDecodeError:
                    return self._send(400, {"error": "body is not JSON"})
                auth = self.headers.get("authorization") or ""
                with outer._lock:
                    behaviour = outer.script.popleft() if outer.script else "ok"
                    outer.requests.append({"path": self.path, "body": body, "behaviour": behaviour,
                                           "authorization": {"present": bool(auth), "sha256_12": hashlib.sha256(
                                               auth.encode()).hexdigest()[:12] if auth else None},
                                           "at": time.time()})
                if not self.path.rstrip("/").endswith("/chat/completions"):
                    return self._send(404, {"error": "not found"})
                if behaviour.startswith("hang:"):
                    time.sleep(float(behaviour.split(":", 1)[1]))
                    behaviour = "ok"
                if behaviour in ("429", "500", "401"):
                    return self._send(int(behaviour), {"error": {"message": f"scripted {behaviour}"}})
                content = _decision(_payload_of(body))
                if behaviour.startswith("pick:") and "index" in content:  # a scripted, different legal choice
                    content = {"index": int(behaviour.split(":", 1)[1]),
                               "rationale": f"protocol test service: scripted {behaviour}"}
                if behaviour == "out_of_range" and "index" in content:
                    content["index"] = 10_000
                text = json.dumps(content)
                if behaviour == "bad_json":
                    text = "not json {"
                elif behaviour == "schema_violation":
                    text = json.dumps({"choice": "first"})
                prompt = sum(len(m.get("content", "")) for m in body.get("messages", [])) // 4
                model = MODEL + "-switched" if behaviour == "switch_model" else MODEL
                answer = {"id": f"ptest_{len(outer.requests):05d}", "object": "chat.completion", "model": model,
                          "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                       "finish_reason": "stop"}]}
                if behaviour != "no_usage":
                    answer["usage"] = {"prompt_tokens": prompt, "completion_tokens": len(text) // 4,
                                       "total_tokens": prompt + len(text) // 4}
                return self._send(200, answer)

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> ProtocolTestServer:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> ProtocolTestServer:
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def bodies_text(self) -> str:
        """Every recorded request body as one JSON text (to search for what must never leave the planner)."""
        return "\n".join(json.dumps(r["body"], ensure_ascii=False, sort_keys=True) for r in self.requests)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args(argv)
    srv = ProtocolTestServer(args.host, args.port)
    print(f"protocol test service (not a model) on http://{args.host}:{srv.port}/v1 model={MODEL}", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        srv._server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
