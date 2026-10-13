#!/usr/bin/env python3
"""Seed the Log4Shell (CVE-2021-44228) attack/defence formal model into the security project on the running platform:
the vulnerable Log4j 2.14.1 (a red-team run reaches RCE) and the fixed 2.16.0 (the same red-team cannot — the fix
holds). So Model Workbench / Scenarios / Runs show a real-CVE attack model and its before/after. Idempotent by
package_id; needs the dev platform up.

    uv run --frozen python scripts/seed_cve_log4shell.py [--project prj_...]
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx
from formal_lab_domain_mal.cve_2021_44228 import log4shell_model
from formal_lab_domain_mal.run import red_team_scenario

API = "http://127.0.0.1:8000/api/v1"


def seed_one(c: httpx.Client, pid: str, *, package_id: str, name: str, version: str, mitigations=frozenset(),
             scen_name: str, scen_desc: str) -> str:
    am = log4shell_model(version=version, mitigations=mitigations, name=package_id)
    pkg = am.package()
    models = c.get(f"{API}/projects/{pid}/models").json()
    existing = next((m for m in models if m.get("package_id") == package_id), None)
    if existing:
        version_id = (c.get(f"{API}/models/{existing['id']}").json().get("versions") or [{}])[-1].get("id")
    else:
        r = c.post(f"{API}/projects/{pid}/models", json={"package_id": package_id, "name": name,
                   "ir": pkg.ir.model_dump(mode="json"), "origin": "seed-cve-log4shell"})
        r.raise_for_status()
        version_id = (c.get(f"{API}/models/{r.json()['id']}").json().get("versions") or [{}])[-1].get("id")
    manifest = red_team_scenario(pkg, goal_property="rce_achieved", strategy="symbolic", horizon=20,
                                 name=scen_name, description=scen_desc)
    m = manifest.model_dump(mode="json")
    body = {"name": m["name"], "description": m["description"], "model_version_id": version_id,
            "environment": m["environment"], "participants": m["participants"], "objectives": m["objectives"],
            "budget": m["budget"], "seed": m["seed"], "execution_gates": m.get("execution_gates", []),
            "stop_conditions": m["stop_conditions"]}
    scens = c.get(f"{API}/projects/{pid}/scenarios").json()
    scen = next((x for x in scens if x.get("name") == scen_name), None)
    sid = scen["id"] if scen else c.post(f"{API}/projects/{pid}/scenarios", json=body).json()["id"]
    run = c.post(f"{API}/projects/{pid}/runs", json={"scenario_id": sid}).json()
    rid = run.get("run", run)["id"]
    t0 = time.time()
    while time.time() - t0 < 120:
        st = c.get(f"{API}/runs/{rid}").json()
        status = st.get("status")
        if status in ("SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"):
            goal = st.get("goal_reached")
            print(f"  {name}: run {status} (goal_reached={goal})")
            return status
        time.sleep(2)
    return "TIMEOUT"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="prj_8874ef7acdad4e5d9f86")
    args = ap.parse_args()
    with httpx.Client(timeout=120) as c:
        seed_one(c, args.project, package_id="cve-2021-44228-vulnerable",
                 name="CVE-2021-44228 Log4Shell（易受攻击 · Log4j 2.14.1）", version="2.14.1",
                 scen_name="Log4Shell 红队：规划到 RCE（2.14.1）",
                 scen_desc="攻击者在易受攻击的 Log4j 2.14.1 上规划 JNDI 注入到远程代码执行的最短攻击链。")
        seed_one(c, args.project, package_id="cve-2021-44228-fixed",
                 name="CVE-2021-44228 Log4Shell（已修复 · Log4j 2.16.0）", version="2.16.0",
                 scen_name="Log4Shell 红队：对已修复版本（2.16.0）",
                 scen_desc="同一攻击者对已修复的 Log4j 2.16.0（移除消息查找、默认禁用 JNDI）无法达成 RCE——修复成立。")
    print("seeded Log4Shell vulnerable + fixed into", args.project)
    return 0


if __name__ == "__main__":
    sys.exit(main())
