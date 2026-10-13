#!/usr/bin/env python3
"""Seed the bigger, realistic enterprise attack-graph model into the security project on the running platform, with a
red-team scenario and an executed run — so Model Workbench, Scenarios and Runs/Evidence show the improved model, not
only the Benchmarks studies. Idempotent by model package_id. Needs the dev platform up (scripts/dev.sh up).

    uv run --frozen python scripts/seed_security_enterprise.py [--project prj_...] [--seed 2026] [--scale 3]
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx
from formal_lab_domain_mal.analysis import generate_enterprise, package
from formal_lab_domain_mal.run import red_team_scenario

API = "http://127.0.0.1:8000/api/v1"
PKG_ID = "mal-enterprise-attack"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="prj_c6180815d7784668b2ef")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()
    pid = args.project

    ag = generate_enterprise(args.seed, scale=args.scale)
    pkg = package(ag)  # include_defense=True; a plain red-team run ignores the harden action
    nodes = len(ag.nodes)
    name = f"企业攻击面攻击图（{nodes} 节点 · 多层 · AND/OR · 防御）"
    with httpx.Client(timeout=120) as c:
        models = c.get(f"{API}/projects/{pid}/models").json()
        existing = next((m for m in models if m.get("package_id") == PKG_ID), None)
        if existing:
            mv = c.get(f"{API}/models/{existing['id']}").json()
            version_id = (mv.get("versions") or [{}])[-1].get("id") or mv.get("latest_version_id")
            print(f"model already present ({existing['id']}); version {version_id}")
        else:
            r = c.post(f"{API}/projects/{pid}/models", json={
                "package_id": PKG_ID, "name": name, "ir": pkg.ir.model_dump(mode="json"),
                "origin": "seed-security-enterprise"})
            r.raise_for_status()
            body = r.json()
            version_id = body.get("version_id") or (body.get("versions") or [{}])[0].get("id") \
                or body.get("latest_version_id")
            print(f"created model {body.get('id')} version {version_id}: {name}")
        if not version_id:
            print("could not resolve a model version id", file=sys.stderr)
            return 1

        manifest = red_team_scenario(pkg, strategy="symbolic", horizon=60,
                                     name="企业红队：Z3 有界规划到王冠数据",
                                     description="攻击者在 37 节点多层企业攻击图上，用 Z3 有界规划找到到达王冠数据的最短路径。")
        m = manifest.model_dump(mode="json")
        scen_body = {"name": m["name"], "description": m["description"], "model_version_id": version_id,
                     "environment": m["environment"], "participants": m["participants"],
                     "objectives": m["objectives"], "budget": m["budget"], "seed": m["seed"],
                     "execution_gates": m.get("execution_gates", []), "stop_conditions": m["stop_conditions"]}
        scens = c.get(f"{API}/projects/{pid}/scenarios").json()
        scen = next((x for x in scens if x.get("name") == scen_body["name"]), None)
        if scen:
            sid = scen["id"]
            print(f"scenario already present: {sid}")
        else:
            r = c.post(f"{API}/projects/{pid}/scenarios", json=scen_body)
            r.raise_for_status()
            sid = r.json()["id"]
            print(f"created scenario {sid}")

        r = c.post(f"{API}/projects/{pid}/runs", json={"scenario_id": sid})
        r.raise_for_status()
        run = r.json().get("run", r.json())
        rid = run["id"]
        print(f"run {rid} started; polling…")
        t0 = time.time()
        while time.time() - t0 < 300:
            st = c.get(f"{API}/runs/{rid}").json()
            status = st.get("status")
            if status in ("SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"):
                print(f"run {rid}: {status} after {time.time() - t0:.0f}s")
                print(f"  model nodes={nodes}, scenario={sid}")
                return 0 if status in ("SUCCEEDED", "BUDGET_EXHAUSTED") else 1
            time.sleep(3)
        print(f"run {rid} did not finish within 300s (last status {status})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
