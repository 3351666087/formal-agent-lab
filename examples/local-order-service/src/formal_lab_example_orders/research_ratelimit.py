"""Research fixture (phase 7, P7-01): a token-bucket capacity limiter — a *different* mechanism from the order
service and the tenant-isolation fixture, used as a new held-out case to check whether the method generalises beyond
the first sample.

A project-owned, finite, in-process program (no network): a bucket holds between 0 and 2·capacity tokens; `take`
spends one when any remain; `refill` adds the refill amount. The safety property is `within_capacity`: the bucket is
never above its capacity. The defect/fix variant is one line of the refill:

  mode = "uncapped"  (DEFECT) — refill adds the amount with no cap, so repeated refills push the bucket above capacity
  mode = "capped"    (FIX)    — refill caps at capacity

The oracle reads the real program's token count after each operation; the secure specification (the capped bucket) is
the model. This is held out: its reference answers are fixed from the program run before any model sees the task.
"""

from __future__ import annotations

from typing import Any

CAPACITY = 3
REFILL = 2
PACKAGE_ID = "ratelimit-token-bucket"
MODES = ("uncapped", "capped")


class TokenBucket:
    """The program under study. `capped=False` is the defect (refill ignores the capacity)."""

    def __init__(self, *, capacity: int = CAPACITY, refill: int = REFILL, capped: bool = True):
        self.capacity = capacity
        self.refill_amount = refill
        self.capped = capped
        self.tokens = 0
        self.granted = 0
        self.denied = 0

    def take(self) -> bool:
        if self.tokens > 0:
            self.tokens -= 1
            self.granted += 1
            return True
        self.denied += 1
        return False

    def refill(self) -> None:
        total = self.tokens + self.refill_amount
        self.tokens = min(self.capacity, total) if self.capped else total


# the fixed operation sequence the oracle drives (held out; the same for both variants)
PROBE = ["refill", "refill", "take", "take", "refill", "take", "take", "take"]


def run_capacity_probes(*, mode: str) -> dict[str, Any]:
    """Drive the program through the fixed sequence and record the real token count after each operation."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, not {mode!r}")
    bucket = TokenBucket(capped=(mode == "capped"))
    steps = []
    for i, op in enumerate(PROBE):
        result = None
        if op == "take":
            result = "granted" if bucket.take() else "denied"
        else:
            bucket.refill()
        steps.append({"index": i, "op": op, "result": result, "observed_tokens": bucket.tokens})
    return {"mode": mode, "capacity": CAPACITY, "refill": REFILL, "sequence": list(PROBE), "steps": steps}


def _secure_tokens() -> list[int]:
    """The capacity-respecting specification stepped over the same sequence: the predicted token count after each op."""
    tokens, out = 0, []
    for op in PROBE:
        if op == "take":
            tokens = max(0, tokens - 1)
        else:
            tokens = min(CAPACITY, tokens + REFILL)
        out.append(tokens)
    return out


def derive_items(observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure: the secure specification caps at capacity; compare its predicted token count with what the program did.
    Returns ConformanceItem-shaped dicts (element/predicted/observed/status/evidence)."""
    predicted = _secure_tokens()
    items = []
    for step, pred in zip(observation["steps"], predicted, strict=True):
        obs = step["observed_tokens"]
        status = "MATCH" if obs == pred else "DIFFERENT"
        over = obs > observation["capacity"]
        items.append({"step": step["index"], "action": f"{step['op']}()",
                      "element": "tokens", "predicted": pred, "observed": obs, "status": status,
                      "evidence": f"after {step['op']}: tokens={obs}" + (" (over capacity)" if over else "")})
    return items


def capacity_model_ir() -> Any:
    from formal_lab_contracts import ModelIR
    from formal_lab_model.samples import ap, assign, c, v

    ir = {
        "name": PACKAGE_ID,
        "description": "Secure specification of a token-bucket capacity limiter: refill never raises the bucket "
                       "above its capacity.",
        "constants": [{"name": "cap", "type": {"kind": "int", "min": 0, "max": 2 * CAPACITY}, "value": {"default": CAPACITY}},
                      {"name": "refill_amt", "type": {"kind": "int", "min": 0, "max": 2 * CAPACITY}, "value": {"default": REFILL}}],
        "state": [{"name": "tokens", "type": {"kind": "int", "min": 0, "max": 2 * CAPACITY}, "initial": {"default": 0},
                   "label": "令牌数"}],
        "actions": [
            {"name": "take", "label": "取令牌", "precondition": ap("gt", v("tokens"), c(0)),
             "effects": [assign("tokens", ap("sub", v("tokens"), c(1)))], "retry": "RECONCILE_THEN_RETRY"},
            {"name": "refill", "label": "补充（封顶）",
             "effects": [
                 {"kind": "when", "condition": ap("le", ap("add", v("tokens"), v("refill_amt")), v("cap")),
                  "then": [assign("tokens", ap("add", v("tokens"), v("refill_amt")))]},
                 {"kind": "when", "condition": ap("gt", ap("add", v("tokens"), v("refill_amt")), v("cap")),
                  "then": [assign("tokens", v("cap"))]},
             ], "retry": "RECONCILE_THEN_RETRY"},
        ],
        "properties": [{"id": "within_capacity", "kind": "invariant", "label": "不超容量",
                        "expr": ap("le", v("tokens"), v("cap"))}],
    }
    return ModelIR.model_validate(ir)


def capacity_model_package(version: int = 1) -> Any:
    from formal_lab_contracts import ModelSource
    from formal_lab_model import build_package

    ir = capacity_model_ir()
    return build_package(ir, package_id=PACKAGE_ID, version=version,
                         source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(indent=2),
                                            origin="examples/local-order-service/research_ratelimit.py"))
