#!/usr/bin/env python3
"""Local check engine (phase 3A, G6): runs a suite of checks and keeps every attempt.

    uv run --frozen python scripts/check_runner.py --suite phase3 [--out DIR] [--group G,G] [--only ID,ID]
                                                   [--skip ID,ID] [--retries N] [--list]

A suite is a module that exports `SUITE` (name, groups, checks, default output directory, outputs excluded from the
work-tree digest). `phase3` is scripts/phase3_check.py; `phase2` loads the historical checks of
scripts/phase2_check.py (its own `make phase2-check` keeps writing docs/handoff/phase2-checks.json unchanged).

What is recorded (DIR/results.json, format `checks@2`):
- the source: commit, a digest of the work tree (uncommitted and untracked changes, the suite's own outputs
  excluded) and a digest of the configuration (the check definitions, uv.lock, pnpm-lock.yaml, the Compose files);
- the environment (tool versions) and the resources probed before the run (CPU, memory, host / Docker disk);
- per check: every attempt of this invocation (own log file DIR/logs/<id>/<stamp>-attempt-<n>.log, exit code,
  timing), the first failure, whether it passed only after a retry (`flaky`), and a short history of earlier
  invocations; a result recorded on another commit, tree or configuration is `inherited` and never counts as a
  current PASS;
- timing: the invocation's wall time, each check's total and per-attempt time, the last full run's duration and
  every partial re-run (with its selection) separately.

Checks run one at a time (concurrency 1); a check that declares `heavy_gib` first asks scripts/disk_guard.py and is
BLOCKED (not FAIL) when the host or Docker disk is short. Loopback never goes through a proxy (NO_PROXY), the proxy
variables themselves are kept for checks that reach a real model endpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = "uv run --frozen python"
CONFIG_FILES = ("uv.lock", "pnpm-lock.yaml", "deploy/compose/services.dev.yaml", "deploy/compose/docker-compose.yaml")
HISTORY = 20


@dataclass
class Check:
    id: str
    group: str
    title: str
    command: str
    tasks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    requires: str | None = None  # services | docker | devstack | llm | prism
    profile: str = "local-lite"
    kind: str = "mandatory"  # mandatory | conditional | extension
    retries: int = 0  # extra attempts after a failure (durable-path checks that kill workers mid-step)
    heavy_gib: float = 0.0  # disk the check may write; checked with disk_guard before it runs
    timeout_s: int | None = None


@dataclass
class Suite:
    name: str
    groups: list[str]
    checks: list[Check]
    out: Path
    outputs: tuple[str, ...] = ()  # paths the checks themselves write: excluded from the work-tree digest


# ------------------------------------------------------------------ source and environment
def worktree_digest(outputs: tuple[str, ...]) -> dict[str, Any]:
    excludes = [f":(exclude){p}" for p in outputs]
    diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--", ".", *excludes], cwd=ROOT, capture_output=True).stdout
    untracked = [u for u in subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
                                           capture_output=True, text=True).stdout.split() if not u.startswith(outputs)]
    h = hashlib.sha256(diff)
    for path in sorted(untracked):
        p = ROOT / path
        if p.is_file():
            h.update(path.encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return {"sha256": h.hexdigest(), "clean": not diff and not untracked, "changed_bytes": len(diff),
            "untracked_files": len(untracked), "excluded_outputs": list(outputs)}


def config_digest(suite: Suite) -> dict[str, Any]:
    parts = {"checks": hashlib.sha256(json.dumps([asdict(c) for c in suite.checks], sort_keys=True).encode()).hexdigest()}
    for name in CONFIG_FILES:
        p = ROOT / name
        parts[name] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return {"sha256": hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest(), "parts": parts}


def versions() -> dict[str, str]:
    def out(cmd: str) -> str:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT)
        text = (r.stdout or r.stderr).strip()
        return text.splitlines()[0] if text else "?"

    return {"os": out(". /etc/os-release && echo $PRETTY_NAME"), "arch": platform.machine(),
            "kernel": platform.release(), "python": platform.python_version(), "uv": out("uv --version"),
            "node": out("node --version"), "pnpm": out("pnpm --version"),
            "docker": out("docker version --format '{{.Server.Version}}'"),
            "z3": out(f"{PY} -c 'import z3;print(z3.get_version_string())'"),
            "temporalio": out(f"{PY} -c 'import importlib.metadata as m;print(m.version(\"temporalio\"))'")}


def resources() -> dict[str, Any]:
    """Probed before every run: the numbers the concurrency and the heavy steps are decided on."""
    def free_gib(path: str | Path) -> float | None:
        try:
            st = os.statvfs(path)
        except OSError:
            return None
        return round(st.f_bavail * st.f_frsize / 2**30, 1)

    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                mem[k] = round(int(v.split()[0]) / 2**20, 2)
    except OSError:
        pass
    return {"cpus": os.cpu_count(), "memory_gib": mem, "load_avg": [round(x, 2) for x in os.getloadavg()],
            "disk_free_gib": {"host (repository filesystem)": free_gib(ROOT), "docker (/var/lib/docker)": free_gib("/var/lib/docker")},
            "concurrency": 1, "note": "checks run one at a time; heavy checks ask disk_guard first"}


def probe(name: str) -> str | None:
    """None when the precondition holds, else why the check cannot run (NOT_RUN, or BLOCKED: …)."""
    if name == "services":
        r = subprocess.run("docker compose -f deploy/compose/services.dev.yaml -p fal-dev up -d --wait && "
                           f"{PY} -m formal_lab_api.migrate upgrade", shell=True, cwd=ROOT, capture_output=True, text=True)
        return None if r.returncode == 0 else f"backing services could not start: {r.stderr[-300:]}"
    if name == "docker":
        return None if subprocess.run(["docker", "info"], capture_output=True).returncode == 0 else "no Docker daemon"
    if name == "devstack":  # a running API (+ web dev server) with the seeded examples, e.g. `scripts/dev.sh up`
        api = os.environ.get("FAL_API_URL", "http://127.0.0.1:8000/api/v1").rsplit("/api/", 1)[0]
        r = subprocess.run(["curl", "-fsS", "--noproxy", "*", "-m", "5", f"{api}/health"], capture_output=True)
        web = subprocess.run(["curl", "-fsS", "--noproxy", "*", "-m", "5", "http://127.0.0.1:5173/"], capture_output=True)
        if r.returncode != 0:
            return f"no running platform API at {api} (start it with scripts/dev.sh up)"
        return None if web.returncode == 0 else "no web dev server on 127.0.0.1:5173 (scripts/dev.sh up)"
    if name == "llm":
        sys.path.insert(0, str(ROOT / "packages" / "runtime" / "src"))
        from formal_lab_runtime.settings import llm_configured

        return None if llm_configured() else "FAL_LLM_API_KEY not configured"
    if name == "prism":
        sys.path.insert(0, str(ROOT / "packages" / "solver-adapters" / "prism-games" / "src"))
        from formal_lab_solver_prism import Unavailable, locate

        try:
            locate()
        except Unavailable as exc:
            return f"BLOCKED: {exc}"
        return probe("services")
    return None


# ------------------------------------------------------------------ running
def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_attempt(check: Check, n: int, logdir: Path, env: dict[str, str], header: str) -> dict[str, Any]:
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-attempt-{n}.log"
    started, t0 = stamp(), time.time()
    with log.open("w") as fh:
        fh.write(f"$ {check.command}\n# {header} · attempt {n} · started {started}\n\n")
        fh.flush()
        try:
            proc = subprocess.run(check.command, shell=True, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT,
                                  timeout=check.timeout_s)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            fh.write(f"\n# TIMEOUT after {check.timeout_s} s\n")
            code = 124
    tail = [ln for ln in log.read_text(errors="replace").strip().splitlines() if ln.strip() and not ln.startswith("make[")]
    return {"attempt": n, "started_at": started, "finished_at": stamp(), "duration_s": round(time.time() - t0, 1),
            "exit_code": code, "result": "PASS" if code == 0 else "FAIL", "log": rel(log),
            "summary": tail[-1][:300] if tail else ""}


def load_suite(name: str) -> Suite:
    """`phase3` → scripts/phase3_check.py; a path to a .py file is loaded as is (tests, later phases)."""
    path = Path(name) if name.endswith(".py") else ROOT / "scripts" / f"{name}_check.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses in the suite module look themselves up there
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if hasattr(mod, "SUITE"):
        return mod.SUITE
    # a historical suite (scripts/phase2_check.py): same check fields, its own output file stays untouched
    checks = [Check(id=c.id, group=c.group, title=c.title, command=c.command, tasks=c.tasks, evidence=c.evidence,
                    requires=c.requires, profile=c.profile, kind=c.kind) for c in mod.CHECKS]
    return Suite(name=name, groups=list(mod.GROUPS), checks=checks, out=ROOT / "out" / "checks" / name,
                 outputs=tuple(mod.OUTPUTS))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--suite", default="phase3")
    ap.add_argument("--out", default=None, help="output directory (results.json + logs/)")
    ap.add_argument("--group", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--retries", type=int, default=None, help="override every check's retry count")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    suite = load_suite(args.suite)
    out = Path(args.out).resolve() if args.out else suite.out
    only = {x for x in args.only.split(",") if x}
    skip = {x for x in args.skip.split(",") if x}
    groups = {x for x in args.group.split(",") if x}
    unknown = (only | skip) - {c.id for c in suite.checks} | groups - set(suite.groups)
    if unknown:
        print(f"unknown check ids / groups: {sorted(unknown)}", file=sys.stderr)
        return 2
    selected = [c for c in suite.checks if not ((only and c.id not in only) or c.id in skip
                                                  or (groups and c.group not in groups))]
    if args.list:
        for c in suite.checks:
            print(f"{'*' if c in selected else ' '} {c.group:<16} {c.id:<28} {c.kind:<10} {c.requires or '-':<9} {c.title}")
        return 0
    full = not (only or skip or groups)
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": os.environ.get("UV_PROJECT_ENVIRONMENT",
                                                                    str(Path.home() / ".venvs" / "formal-agent-lab"))}
    for key in ("NO_PROXY", "no_proxy"):
        env[key] = ",".join(x for x in (env.get(key), "127.0.0.1,localhost,::1") if x)
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    outputs = tuple(dict.fromkeys((*suite.outputs, str(out.relative_to(ROOT)) + "/" if out.is_relative_to(ROOT) else "")))
    outputs = tuple(o for o in outputs if o)
    tree, config = worktree_digest(outputs), config_digest(suite)
    results_path = out / "results.json"
    previous = json.loads(results_path.read_text()) if results_path.exists() else {}
    results = {r["id"]: r for r in previous.get("checks", [])}
    for r in results.values():
        r["inherited"] = not (r.get("checked_commit") == rev and r.get("worktree_sha256") == tree["sha256"]
                              and r.get("config_sha256") == config["sha256"])
    res_before = resources()
    print(f"==> {suite.name}: {len(selected)} check(s) at {rev[:12]} (tree {tree['sha256'][:12]}, "
          f"config {config['sha256'][:12]}); resources {res_before['disk_free_gib']} → {out}", flush=True)
    probes: dict[str, str | None] = {}
    started_run, t_all = stamp(), time.time()
    for check in selected:
        header = f"{suite.name}/{check.id} at {rev[:12]} (tree {tree['sha256'][:12]}, profile {check.profile})"
        reason = None
        if check.requires:
            if check.requires not in probes:
                probes[check.requires] = probe(check.requires)
            reason = probes[check.requires]
        if not reason and check.heavy_gib:
            g = subprocess.run([sys.executable, "scripts/disk_guard.py", "--need", str(check.heavy_gib), "--label",
                                check.id, "--trim"], cwd=ROOT, capture_output=True, text=True)
            if g.returncode != 0:
                reason = f"BLOCKED: {(g.stderr or g.stdout).strip()[-300:]}"
        attempts: list[dict[str, Any]] = []
        if reason:
            result = next((k for k in ("NOT_SELECTED", "BLOCKED") if reason.startswith(k)), "NOT_RUN")
            note = reason
            print(f"--> [{check.group}] {check.id}: {result} — {reason}", flush=True)
        else:
            tries = 1 + (check.retries if args.retries is None else args.retries)
            print(f"==> [{check.group}] {check.id}: {check.command}", flush=True)
            for n in range(1, tries + 1):
                a = run_attempt(check, n, out / "logs" / check.id, env, header)
                attempts.append(a)
                print(f"    attempt {n}: {a['result']} ({a['duration_s']} s) {a['summary']}", flush=True)
                if a["result"] == "PASS":
                    break
            result, note = attempts[-1]["result"], attempts[-1]["summary"]
            if check.requires in ("docker", "services"):  # give the host back what the check freed in the VM
                subprocess.run([sys.executable, "scripts/disk_guard.py", "--need", "0", "--trim", "--label",
                                f"after {check.id}"], cwd=ROOT, capture_output=True)
        prior = results.get(check.id)
        history = ([{k: prior.get(k) for k in ("result", "checked_commit", "finished_at", "duration_s")}
                    | {"attempts": len(prior.get("attempts", []))}] if prior else []) + (prior or {}).get("history", [])
        first_fail = next((a for a in attempts if a["result"] == "FAIL"), None)
        results[check.id] = {
            **{k: v for k, v in asdict(check).items() if k not in ("timeout_s",)},
            "result": result, "summary": note, "checked_commit": rev, "worktree_sha256": tree["sha256"],
            "worktree_clean": tree["clean"], "config_sha256": config["sha256"],
            "started_at": attempts[0]["started_at"] if attempts else stamp(), "finished_at": stamp(),
            "duration_s": round(sum(a["duration_s"] for a in attempts), 1), "attempts": attempts,
            "first_failure": first_fail and {k: first_fail[k] for k in ("attempt", "summary", "log", "exit_code")},
            "flaky": bool(first_fail) and result == "PASS", "inherited": False, "history": history[:HISTORY]}
    ordered = [results[c.id] for c in suite.checks if c.id in results]
    group_status = {}
    for g in suite.groups:
        declared = [c for c in suite.checks if c.group == g and c.kind == "mandatory"]
        current = [results[c.id] for c in declared if c.id in results and not results[c.id].get("inherited")]
        if declared and len(current) == len(declared) and all(r["result"] == "PASS" for r in current):
            group_status[g] = "PASS"
        elif any(r["result"] == "FAIL" for r in current):
            group_status[g] = "FAIL"
        elif not declared:
            group_status[g] = "OPTIONAL"
        else:
            group_status[g] = "INCOMPLETE"
    summary = {k: sum(1 for r in ordered if r["result"] == k and not r.get("inherited"))
               for k in ("PASS", "FAIL", "NOT_RUN", "NOT_SELECTED", "BLOCKED")}
    this_run = {"started_at": started_run, "finished_at": stamp(), "duration_s": round(time.time() - t_all, 1),
                "full": full, "selection": {"group": sorted(groups), "only": sorted(only), "skip": sorted(skip)},
                "checks": [c.id for c in selected], "commit": rev, "worktree_sha256": tree["sha256"],
                "results": {c.id: results[c.id]["result"] for c in selected}}
    runs = [*previous.get("runs", []), this_run][-HISTORY:]
    last_full = next((r for r in reversed(runs) if r["full"]), None)
    doc = {
        "format": "checks@2", "suite": suite.name, "generated_at": stamp(),
        "source_revision": {"commit": rev, "worktree": tree}, "config": config,
        "command": "python scripts/check_runner.py " + " ".join(argv if argv is not None else sys.argv[1:]),
        "environment": versions(), "resources_before": res_before, "resources_after": resources(),
        "summary": summary, "groups": group_status,
        "mandatory_passed": all(v in ("PASS", "OPTIONAL") for v in group_status.values()),
        "timing": {"this_run_s": this_run["duration_s"], "last_full_run_s": last_full["duration_s"] if last_full else None,
                   "last_full_run_at": last_full["started_at"] if last_full else None,
                   "partial_runs": [{k: r[k] for k in ("started_at", "duration_s", "selection", "results")}
                                    for r in runs if not r["full"]][-10:]},
        "runs": runs, "checks": ordered,
    }
    out.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"==> groups {group_status} · {summary} → {rel(results_path)}")
    return 0 if all(r["result"] != "FAIL" for r in ordered if not r.get("inherited")) else 1


if __name__ == "__main__":
    sys.exit(main())
