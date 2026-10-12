"""Research fixture (phase 5B): a per-tenant access-isolation layer over the business order service.

This is a project-owned research fixture, kept apart from the default startup path (`service.py` is unchanged; the
ordinary examples keep running). It exists to make one software safety property — tenant/object access isolation —
observable on the real local service, and to carry a self-contained defect/fix variant for regression. It does not
reproduce any upstream CVE, vendor advisory or user behaviour; the subjects, grants and data are fixed synthetic
fixture values that only ever address local test tenants.

The base service (`service.py`) has only a single coarse write token and open reads: a tenant is a path segment and a
SQLite file, not an authenticated principal. This fixture adds the missing component — an authorization layer that
binds a principal (a bearer token) to the tenants it may use, and checks it on every `/t/{tenant}/…` request. The
defect/fix variant is one configuration flag on that one component:

  mode = "authenticate_only"  (DEFECT) — the layer checks the token is a known principal but NOT that the principal is
                                         granted the requested tenant: a classic missing object-level authorization.
  mode = "per_tenant"         (FIX)    — the layer also checks the grant covers the requested tenant.

The property under test is whether this authorization component isolates tenants; the oracle reads the real HTTP
result and the real stored state through the tenant's own authorized principal — never a self-reported "success".
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

# ---- fixed research dataset (local test tenants only; these are fixture identifiers, not real credentials) ----
MODES = ("authenticate_only", "per_tenant")
PRINCIPALS: dict[str, dict[str, Any]] = {
    "fixt-alpha": {"principal": "alpha", "tenants": ["acme"]},
    "fixt-bravo": {"principal": "bravo", "tenants": ["globex"]},
}
SUBJECTS = {v["principal"]: {"token": tok, "tenants": v["tenants"]} for tok, v in PRINCIPALS.items()}
TENANTS = sorted({t for v in PRINCIPALS.values() for t in v["tenants"]})  # model scope: acme, globex
GRANTS = {v["principal"]: set(v["tenants"]) for v in PRINCIPALS.values()}
_TENANT_PATH = re.compile(r"^/t/(?P<tenant>[^/]+)")

MECHANISM = """\
# Mechanism: tenant/object access isolation on the order service

One page, written before modelling. Scope: the local order service (examples/local-order-service) with the phase-5B
authorization research fixture (`research_isolation.py`), on local test tenants only.

- **Subject.** A client identified by a bearer token. The fixture knows two principals: `alpha` (token fixt-alpha,
  granted tenant `acme`) and `bravo` (token fixt-bravo, granted tenant `globex`). The program identifies the subject
  by looking the bearer token up in the authorization layer; an unknown or missing token is 401. Initial permission =
  the principal's grant set. Known information = its own token and the tenant ids in the URL space.
- **Resource.** A tenant's business state (orders, stock, operations), one SQLite file per tenant, owned by the tenant.
  Fixed synthetic instances (the `normal` case, seed 1). Relevant state: whether a request reads or changes a tenant's
  stored values.
- **Capability.** The subject can issue the local HTTP API (`/t/{tenant}/state`, `/operations`, `/admin/*`, …) with any
  tenant id and body it chooses — the tenant id and request body are controllable input. It cannot forge another
  tenant's server-side grant record, cannot read the SQLite files directly, and cannot change the authorization layer:
  those are uncontrollable program facts.
- **Trust boundary.** The tenant id and bearer token in each request need server-side validation. The judgement is made
  by the authorization layer (`research_isolation.create_isolation_app`'s middleware) before the request reaches the
  business route. The business layer itself does not re-check tenant ownership.
- **Action.** `access(subject, tenant)` maps to one HTTP request to `/t/{tenant}/…`. Precondition (secure): the subject
  is granted that tenant. Failure result: 401 (unknown principal) or 403 (not granted). Success: the business route
  runs and the tenant's state/observation may change (write) or be returned (read).
- **Property.** `tenant_isolation` (invariant): no access by a subject to a tenant succeeds unless the subject is
  granted that tenant — `forall s,t: accessed[s][t] -> grant[s][t]`. Machine-checkable on the finite model; the expr
  digest is recorded in the case.
- **Oracle.** Independent of the subject under test: the real HTTP status, and the tenant's stored state read back
  through that tenant's own authorized principal (did a cross-tenant write actually land? did a cross-tenant read
  actually return the other tenant's values?). A request the oracle cannot classify (e.g. the authorization layer let
  it through but the business layer rejected it for an unrelated precondition, so no state changed) stays UNKNOWN.
"""


def principal_for(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    return PRINCIPALS.get(token.removeprefix("Bearer ").strip())


def create_isolation_app(data_dir: Path, *, mode: str, project: str = "isolation") -> Any:
    """The business app wrapped in the authorization layer. `mode` selects the defect/fix variant."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, not {mode!r}")
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    from .service import create_app

    app = create_app(data_dir, project=project, write_token=None)  # the isolation layer is the sole authorization

    class Authorization(BaseHTTPMiddleware):
        async def dispatch(self, request: Any, call_next: Any) -> Any:
            m = _TENANT_PATH.match(request.url.path)
            if m is None:  # /health and other non-tenant routes are not tenant-scoped
                return await call_next(request)
            who = principal_for(request.headers.get("authorization"))
            if who is None:
                return JSONResponse(status_code=401, content={"error": "UNKNOWN_PRINCIPAL",
                                    "detail": "a known bearer token is required"})
            if mode == "per_tenant" and m.group("tenant") not in who["tenants"]:
                return JSONResponse(status_code=403, content={"error": "TENANT_NOT_GRANTED",
                                    "principal": who["principal"], "tenant": m.group("tenant")})
            return await call_next(request)

    app.add_middleware(Authorization)
    return app


# ------------------------------------------------------------------------------------------ the secure-spec model
def isolation_model_ir() -> Any:
    from formal_lab_contracts import ModelIR
    from formal_lab_model.samples import ap, assign, c, r, v

    subjects = sorted(GRANTS)
    grant_cells = [{"index": [s, t], "value": (t in GRANTS[s])} for s in subjects for t in TENANTS]
    ir = {
        "name": "orders-tenant-isolation",
        "description": "Secure specification of tenant/object access isolation: an access succeeds only when the "
                       "subject is granted the tenant.",
        "entity_sets": [{"name": "subjects", "members": subjects, "label": "主体"},
                        {"name": "tenants", "members": TENANTS, "label": "租户"}],
        "constants": [{"name": "grant", "type": {"kind": "bool"}, "index": ["subjects", "tenants"],
                       "value": {"cells": grant_cells, "default": False},
                       "description": "the fixed grant table: which subject may use which tenant"}],
        "state": [{"name": "accessed", "type": {"kind": "bool"}, "index": ["subjects", "tenants"],
                   "initial": {"default": False}, "label": "已成功访问",
                   "description": "set when an access by the subject to the tenant succeeds"}],
        "actions": [{"name": "access", "label": "访问租户",
                     "params": [{"name": "s", "type": {"kind": "entity", "set": "subjects"}},
                                {"name": "t", "type": {"kind": "entity", "set": "tenants"}}],
                     "precondition": v("grant", r("s"), r("t")),  # secure: only a granted access succeeds
                     "effects": [assign("accessed", c(True), r("s"), r("t"))],
                     "retry": "RECONCILE_THEN_RETRY"}],
        "properties": [{"id": "tenant_isolation", "kind": "invariant", "label": "租户隔离",
                        "expr": {"op": "forall", "var": "s", "domain": "subjects",
                                 "body": {"op": "forall", "var": "t", "domain": "tenants",
                                          "body": ap("implies", v("accessed", r("s"), r("t")),
                                                     v("grant", r("s"), r("t")))}}}],
    }
    return ModelIR.model_validate(ir)


def isolation_model_package(version: int = 1) -> Any:
    from formal_lab_contracts import ModelSource
    from formal_lab_model import build_package

    ir = isolation_model_ir()
    return build_package(ir, package_id="orders-tenant-isolation", version=version,
                         source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(indent=2),
                                            origin="examples/local-order-service/research_isolation.py"))


# --------------------------------------------------------------------------- probes and oracle (real observation)
def _op_body(op_id: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"operation_id": op_id, "action": action, "params": params, "actor_id": "p5b-probe"}


def run_access_probes(base_url: str, *, mode: str, scenario: str = "standard") -> dict[str, Any]:
    """Issue a fixed set of access attempts against a running fixture and record the independently-read outcome.

    scenario "standard": same-tenant read/write (granted) and cross-tenant read/write (not granted);
    scenario "partial":  a cross-tenant write the business layer rejects for an unrelated precondition — the
                         authorization layer let it through but no state changed, so the outcome is not classifiable.
    """
    import httpx

    hdr = {p: {"Authorization": f"Bearer {d['token']}"} for p, d in SUBJECTS.items()}
    attempts: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url, timeout=30, trust_env=False) as c:
        # each tenant reset by its own authorized principal (the oracle's trusted channel)
        for sub, tenants in GRANTS.items():
            for t in tenants:
                c.post(f"/t/{t}/admin/reset", json={"case": "normal", "seed": 1}, headers=hdr[sub])

        def observed_write(resp: httpx.Response, tenant: str, owner: str) -> tuple[bool | None, str]:
            if resp.status_code in (401, 403):
                return False, f"authorization denied ({resp.status_code})"
            if resp.status_code >= 400:
                return None, f"request failed for another reason ({resp.status_code})"
            body = resp.json()
            if body.get("status") == "APPLIED":
                # independent oracle: the owner reads its own state back and sees the write landed
                after = c.get(f"/t/{tenant}/state", headers=hdr[owner]).json()
                return True, f"operation APPLIED, owner-read revision {after.get('revision')}"
            return None, f"authorization allowed the request through but business status={body.get('status')}; " \
                         "no state change observed → not classifiable"

        def observed_read(resp: httpx.Response) -> tuple[bool | None, str]:
            if resp.status_code in (401, 403):
                return False, f"authorization denied ({resp.status_code})"
            if resp.status_code == 200 and "values" in resp.json():
                return True, "200 with the tenant's stored values returned"
            return None, f"status {resp.status_code}, not classifiable"

        order = "o1"
        if scenario == "partial":
            # alpha (granted acme) attempts a WRITE on globex; reserve an order that is not in 'submitted' state after a
            # tick, so the business layer rejects it regardless of authorization → outcome not classifiable
            c.post("/t/globex/operations", json=_op_body("pre-tick", "tick", {}), headers=hdr["bravo"])
            resp = c.post("/t/globex/operations", json=_op_body("x-write", "reserve", {"o": order}),
                          headers=hdr["alpha"])
            allowed, note = observed_write(resp, "globex", "bravo")
            attempts.append({"id": "alpha->globex:write(rejected)", "subject": "alpha", "tenant": "globex",
                             "access": "write", "granted": False, "status": resp.status_code,
                             "observed_allowed": allowed, "oracle": note})
            return {"mode": mode, "scenario": scenario, "attempts": attempts}

        plan = [("alpha", "acme", "read"), ("alpha", "acme", "write"),
                ("bravo", "globex", "read"), ("bravo", "globex", "write"),
                ("alpha", "globex", "read"), ("alpha", "globex", "write"),
                ("bravo", "acme", "read"), ("bravo", "acme", "write")]
        for i, (sub, tenant, access) in enumerate(plan):
            owner = next(p for p, ts in GRANTS.items() if tenant in ts)
            if access == "read":
                resp = c.get(f"/t/{tenant}/state", headers=hdr[sub])
                allowed, note = observed_read(resp)
            else:
                resp = c.post(f"/t/{tenant}/operations", json=_op_body(f"w{i}", "reserve", {"o": order}),
                              headers=hdr[sub])
                allowed, note = observed_write(resp, tenant, owner)
            attempts.append({"id": f"{sub}->{tenant}:{access}", "subject": sub, "tenant": tenant, "access": access,
                             "granted": tenant in GRANTS[sub], "status": resp.status_code,
                             "observed_allowed": allowed, "oracle": note})
    return {"mode": mode, "scenario": scenario, "attempts": attempts}


def derive_items(observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure: the secure model predicts a subject may access a tenant iff it is granted; compare with what was
    observed. Returns ConformanceItem-shaped dicts (element/predicted/observed/status/evidence)."""
    items = []
    for a in observation["attempts"]:
        predicted = bool(a["granted"])  # the secure specification
        observed = a["observed_allowed"]
        if a["tenant"] not in TENANTS:
            status, obs = "NOT_COMPARABLE", None
        elif observed is None:
            status, obs = "UNKNOWN", None
        elif predicted == observed:
            status, obs = "MATCH", observed
        else:
            status, obs = "DIFFERENT", observed
        items.append({"element": f"accessed[{a['subject']}][{a['tenant']}]", "action": f"{a['access']} {a['id']}",
                      "predicted": predicted, "observed": obs, "status": status, "evidence": a["oracle"]})
    return items


def main(argv: list[str] | None = None) -> int:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser(description="run the tenant-isolation research fixture")
    ap.add_argument("--data", default=os.environ.get("ISOLATION_DATA", "./var/isolation"))
    ap.add_argument("--host", default=os.environ.get("ISOLATION_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("ISOLATION_PORT", "8766")))
    ap.add_argument("--mode", default=os.environ.get("ISOLATION_MODE", "per_tenant"), choices=MODES)
    args = ap.parse_args(argv)
    uvicorn.run(create_isolation_app(Path(args.data), mode=args.mode), host=args.host, port=args.port,
                log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
