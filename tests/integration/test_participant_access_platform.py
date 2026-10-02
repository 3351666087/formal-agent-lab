"""Participant read channel on the platform (phase 4A, A2): a token issued by the operator binds one run and one
actor; the participant endpoints take the identity from it, an `actor` parameter outside it is refused, and the
download is the participant's projection of the run — a valid bundle for the same offline reader."""

from __future__ import annotations

import base64

import httpx
import pytest
from formal_lab_contracts.bundle import read_bundle

pytestmark = pytest.mark.integration


def _finished_two_actor_run(stack) -> dict:
    demo = next(p for p in stack.get("/projects") if p["name"] == "生产调度示例")
    sc = next(s for s in stack.get(f"/projects/{demo['id']}/scenarios") if s["name"] == "两名调度员（轮流）")
    run = stack.post(f"/projects/{demo['id']}/runs", {"scenario_id": sc["id"], "seed": 2})
    return stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)


def test_participant_token_binds_run_and_actor(stack):
    run = _finished_two_actor_run(stack)
    rid = run["id"]
    assert stack.client.post(f"/runs/{rid}/participants/nobody/access").status_code == 404
    grant = stack.post(f"/runs/{rid}/participants/dispatcher_a/access", expect=201)
    assert grant["actor_id"] == "dispatcher_a" and grant["run_id"] == rid and grant["scope"] == "participant:read"
    auth = {"Authorization": f"Bearer {grant['token']}"}

    me = stack.client.get("/participant/whoami", headers=auth)
    assert me.status_code == 200 and me.json() == {"run_id": rid, "actor_id": "dispatcher_a",
                                                   "scope": "participant:read"}
    assert stack.client.get("/participant/whoami").status_code == 401
    assert stack.client.get("/participant/whoami", headers={"Authorization": "Bearer x.y"}).status_code == 401
    body, sig = grant["token"].split(".", 1)
    forged = base64.urlsafe_b64encode(base64.urlsafe_b64decode(body + "==").replace(b"dispatcher_a", b"dispatcher_b"))
    bad = {"Authorization": f"Bearer {forged.decode().rstrip('=')}.{sig}"}
    assert stack.client.get("/participant/whoami", headers=bad).status_code == 401
    other = stack.client.get("/participant/export", headers=auth, params={"actor": "dispatcher_b"})
    assert other.status_code == 403 and "ACTOR_OUT_OF_SCOPE" in other.text
    expired = stack.post(f"/runs/{rid}/participants/dispatcher_a/access?ttl_s=-5", expect=201)
    gone = stack.client.get("/participant/whoami", headers={"Authorization": f"Bearer {expired['token']}"})
    assert gone.status_code == 401 and "EXPIRED" in gone.text

    dl = stack.client.get("/participant/export", headers=auth, params={"actor": "dispatcher_a"}, timeout=60)
    assert dl.status_code == 200 and "participant.replay.zip" in dl.headers["content-disposition"]
    mine = read_bundle(dl.content)  # contiguous sequence and causal order hold, or this raises
    full = read_bundle(httpx.get(f"{stack.base}/runs/{rid}/export", timeout=60).content)
    assert {e.actor_id for e in mine.events} <= {None, "dispatcher_a"}
    assert any(e.actor_id == "dispatcher_b" for e in full.events)
    assert len(mine.events) < len(full.events) and mine.info["provenance"]["participant"] == "dispatcher_a"
    assert mine.manifest.scenario.environment.config == {} and full.manifest.scenario.environment.config
    b = next(p for p in mine.manifest.participants if p.actor_id == "dispatcher_b")
    assert b.strategy.config == {} and b.view is None
    assert all(o.actor_id == "dispatcher_a" for o in mine.operations) and not mine.metrics
