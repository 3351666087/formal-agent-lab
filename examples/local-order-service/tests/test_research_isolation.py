"""Phase 5B regression for the tenant-isolation research fixture: the defect variant lets a subject reach another
tenant, the fix variant denies it, and an ordinary same-tenant request keeps working in both. The authorization layer
is exercised on the real app over real SQLite files; the derivation is checked on crafted observations."""

from __future__ import annotations

from formal_lab_contracts.research import ConformanceItem
from formal_lab_example_orders.research_isolation import (
    GRANTS,
    create_isolation_app,
    derive_items,
    isolation_model_package,
)
from formal_lab_runtime.research import decide_correspondence
from starlette.testclient import TestClient


def _corr(derived):
    return decide_correspondence([ConformanceItem(**i) for i in derived], has_observation=True)[0]

ALPHA = {"Authorization": "Bearer fixt-alpha"}  # granted acme
BRAVO = {"Authorization": "Bearer fixt-bravo"}  # granted globex
UNKNOWN = {"Authorization": "Bearer nope"}


def _client(tmp_path, mode):
    app = create_isolation_app(tmp_path / mode, mode=mode)
    c = TestClient(app)
    c.post("/t/acme/admin/reset", json={"case": "normal", "seed": 1}, headers=ALPHA)
    c.post("/t/globex/admin/reset", json={"case": "normal", "seed": 1}, headers=BRAVO)
    return c


def test_unknown_principal_is_refused_in_both_variants(tmp_path):
    for mode in ("authenticate_only", "per_tenant"):
        c = _client(tmp_path, mode)
        assert c.get("/t/acme/state", headers=UNKNOWN).status_code == 401
        assert c.get("/t/acme/state").status_code == 401  # missing token too


def test_same_tenant_access_works_in_both_variants(tmp_path):
    for mode in ("authenticate_only", "per_tenant"):
        c = _client(tmp_path, mode)
        assert c.get("/t/acme/state", headers=ALPHA).status_code == 200
        r = c.post("/t/acme/operations", json={"operation_id": "o", "action": "reserve", "params": {"o": "o1"}},
                   headers=ALPHA)
        assert r.status_code == 200 and r.json()["status"] == "APPLIED"


def test_defect_variant_allows_cross_tenant_access(tmp_path):
    c = _client(tmp_path, "authenticate_only")
    assert c.get("/t/globex/state", headers=ALPHA).status_code == 200  # read leak
    r = c.post("/t/globex/operations", json={"operation_id": "x", "action": "reserve", "params": {"o": "o1"}},
               headers=ALPHA)
    assert r.status_code == 200 and r.json()["status"] == "APPLIED"  # write landed cross-tenant
    # independent oracle: the owner sees the foreign write in its own state
    assert c.get("/t/globex/state", headers=BRAVO).json()["operations"] >= 1


def test_fix_variant_denies_cross_tenant_access(tmp_path):
    c = _client(tmp_path, "per_tenant")
    assert c.get("/t/globex/state", headers=ALPHA).status_code == 403
    r = c.post("/t/globex/operations", json={"operation_id": "x", "action": "reserve", "params": {"o": "o1"}},
               headers=ALPHA)
    assert r.status_code == 403
    assert c.get("/t/globex/state", headers=BRAVO).json()["operations"] == 0  # nothing landed


def test_secure_model_isolation_property_exists():
    pkg = isolation_model_package()
    prop = next(p for p in pkg.ir.properties if p.id == "tenant_isolation")
    assert prop.kind == "invariant" and {"alpha": {"acme"}, "bravo": {"globex"}} == GRANTS


def test_derive_items_and_correspondence_branches():
    def obs(attempts):
        return {"mode": "x", "scenario": "x", "attempts": attempts}

    allowed = {"id": "alpha->globex:read", "subject": "alpha", "tenant": "globex", "access": "read",
               "granted": False, "status": 200, "observed_allowed": True, "oracle": "leaked"}
    denied = {**allowed, "observed_allowed": False, "status": 403, "oracle": "denied"}
    ok = {"id": "alpha->acme:read", "subject": "alpha", "tenant": "acme", "access": "read", "granted": True,
          "status": 200, "observed_allowed": True, "oracle": "ok"}
    unknown = {**allowed, "observed_allowed": None, "oracle": "not classifiable"}

    deviates = derive_items(obs([ok, allowed]))
    assert {i["status"] for i in deviates} == {"MATCH", "DIFFERENT"} and _corr(deviates) == "DEVIATES"

    corresponds = derive_items(obs([ok, denied]))
    assert {i["status"] for i in corresponds} == {"MATCH"} and _corr(corresponds) == "CORRESPONDS"

    partial = derive_items(obs([ok, unknown]))
    assert {i["status"] for i in partial} == {"MATCH", "UNKNOWN"} and _corr(partial) == "UNKNOWN"
