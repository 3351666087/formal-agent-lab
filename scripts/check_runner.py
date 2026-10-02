#!/usr/bin/env python3
"""Local check engine (phase 3A G6, hardened in phase 4A A1): runs a suite of checks and keeps every attempt.

    uv run --frozen python scripts/check_runner.py --suite phase4 [--out DIR] [--group G,G] [--only ID,ID]
                                                   [--skip ID,ID] [--retries N] [--strict] [--list]

A suite is a module that exports `SUITE` (name, groups, checks, default output directory, outputs excluded from the
work-tree digest). `phase3` / `phase4` are scripts/phase{3,4}_check.py; `phase2` loads the historical checks of
scripts/phase2_check.py. The status protocol is documented in docs/execution/check-protocol.md.

How a check's status is decided (an exit code alone never makes a PASS):
- the command runs with `FAL_CHECK_ID`, `FAL_CHECK_ATTEMPT`, a fresh `FAL_CHECK_NONCE` and `FAL_CHECK_RESULT` (where a
  structured `fal-check-result@1` document goes, see scripts/check_result.py);
- a structured result is required when the check declares `protocol=True`; when present it must echo the nonce
  (else it is stale), parse, and its required assertions must all hold;
- every file a check declares in `produces` must exist after the attempt, have been written during it (no leftover
  from an earlier run), parse when it is JSON, and its top-level `status` / the booleans under `assertions_from`
  are honoured (an evidence script that exits 0 but records BLOCKED is BLOCKED);
- a pytest command whose summary shows no passed test (everything skipped / deselected) did not verify anything:
  BLOCKED when tests were skipped, FAIL when none ran;
- conditional checks evaluate their declared `trigger` before anything runs: not met → NOT_APPLICABLE, met → treated
  as mandatory. A missing environment dependency of a counted check is BLOCKED / NOT_RUN and stays unmet.

What is aggregated: only results produced and verified by THIS invocation. A partial selection yields a selection
status, never `complete`; `complete` (= `mandatory_passed`) needs a full run in which every required group passed.
A result recorded on another commit, work tree or configuration is `inherited` and never counts. `--strict` exits
non-zero unless complete.

Also recorded (DIR/results.json, format `checks@3`, a superset of `checks@2`): commit, work-tree digest (the suite's
declared outputs excluded — the engine refuses exclusions that would hide executable code), configuration digest,
tool versions, resources, per-check attempts with logs and evidence digests, history and timing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = "uv run --frozen python"
# free space every heavy check must leave on the host and Docker disks (GiB): the Mac shares its disk with the VM's
# sparse disk images, and a full host disk once aborted the VM's journal (2026-09-28)
RESERVE_GIB = float(os.environ.get("FAL_DISK_RESERVE_GIB", "15"))
CONFIG_FILES = ("uv.lock", "pnpm-lock.yaml", "deploy/compose/services.dev.yaml", "deploy/compose/docker-compose.yaml")
CODE_SUFFIXES = (".py", ".pyi", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".sh", ".bash")
HISTORY = 20
PROTOCOL = "fal-check-result@1"
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_SELECTED", "NOT_APPLICABLE")
ENV_BLOCKERS = ("BLOCKED", "NOT_RUN")


@dataclass
class Check:
    id: str
    group: str
    title: str
    command: str
    tasks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # reference files: digested, not required to be rewritten
    requires: str | None = None  # services | docker | devstack | llm | prism
    profile: str = "local-lite"
    kind: str = "mandatory"  # mandatory | conditional | extension
    retries: int = 0  # extra attempts after a FAIL (durable-path checks that kill workers mid-step)
    heavy_gib: float = 0.0  # disk the check may write; checked with disk_guard before it runs
    timeout_s: int | None = None
    produces: list[str] = field(default_factory=list)  # files the command must (re)write during the attempt
    protocol: bool = False  # a fal-check-result@1 document is required
    assertions_from: str | None = None  # JSON key of a produced file whose booleans are required assertions
    trigger: str | None = None  # conditional checks: probe deciding applicability, evaluated before running


@dataclass
class Suite:
    name: str
    groups: list[str]
    checks: list[Check]
    out: Path
    outputs: tuple[str, ...] = ()  # paths the checks themselves write: excluded from the work-tree digest
    required_groups: list[str] | None = None  # groups that must pass for `complete` (default: all)


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


def code_hidden_by(outputs: tuple[str, ...]) -> list[str]:
    """Tracked or untracked executable files under an excluded output path — exclusions may only cover evidence."""
    hidden: list[str] = []
    for prefix in outputs:
        files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", prefix],
                               cwd=ROOT, capture_output=True, text=True).stdout.split()
        hidden += [f for f in files if f.endswith(CODE_SUFFIXES)]
    return sorted(set(hidden))


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
    if name.startswith("env:"):  # test hook: a precondition decided by an environment variable
        return None if os.environ.get(name[4:]) else f"{name[4:]} not set"
    return None


# ------------------------------------------------------------------ evaluating one attempt
def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_of(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


_PYTEST_LINE = re.compile(r"\b(\d+) (passed|failed|skipped|deselected|errors?|xfailed|xpassed)\b")


def pytest_summary(text: str) -> dict[str, Any] | None:
    """Counts from the last pytest summary line in a log (None when the log holds none)."""
    lines = [ln for ln in text.splitlines() if re.search(r"\bin [\d.]+s\b", ln)
             and (_PYTEST_LINE.search(ln) or "no tests ran" in ln)]
    if not lines:
        return None
    last = lines[-1]
    counts = {k: 0 for k in ("passed", "failed", "skipped", "deselected", "errors")}
    for n, kind in _PYTEST_LINE.findall(last):
        counts["errors" if kind.startswith("error") else kind] = counts.get(kind, 0) + int(n)
    counts["skip_reasons"] = [ln.strip()[:200] for ln in text.splitlines() if ln.startswith("SKIPPED")][:3]
    counts["line"] = last.strip()[:200]
    return counts


def read_structured(path: Path, nonce: str) -> dict[str, Any]:
    if not path.exists():
        return {"present": False}
    try:
        doc = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"present": True, "error": f"malformed result: {exc}"}
    if not isinstance(doc, dict) or doc.get("protocol") != PROTOCOL:
        return {"present": True, "error": f"not a {PROTOCOL} document"}
    if doc.get("nonce") != nonce:
        return {"present": True, "error": f"stale result (nonce {doc.get('nonce')!r} is not this attempt's)"}
    if doc.get("status") not in ("PASS", "FAIL", "BLOCKED", "NOT_RUN"):
        return {"present": True, "error": f"unknown result status {doc.get('status')!r}"}
    return {"present": True, "doc": doc}


def read_produced(path: Path, started: float, assertions_from: str | None) -> dict[str, Any]:
    info: dict[str, Any] = {"path": rel(path), "exists": path.is_file()}
    if not info["exists"]:
        return info | {"error": f"evidence missing: {rel(path)}"}
    info["sha256"] = sha256_of(path)
    info["fresh"] = path.stat().st_mtime >= started - 1.0
    if not info["fresh"]:
        return info | {"error": f"stale evidence: {rel(path)} was not written by this attempt"}
    if path.suffix == ".json":
        try:
            doc = json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return info | {"error": f"malformed evidence {rel(path)}: {exc}"}
        if isinstance(doc, dict):
            status = doc.get("status")
            if status in ("BLOCKED", "NOT_RUN", "FAIL"):
                info["status"] = status
                info["status_reason"] = str(doc.get("reason") or doc.get("note") or f"{rel(path)} records {status}")[:300]
            if assertions_from and status not in ("BLOCKED", "NOT_RUN"):  # a blocked run computed no conclusion
                section = doc.get(assertions_from)
                if not isinstance(section, dict):
                    return info | {"error": f"{rel(path)} has no `{assertions_from}` section"}
                info["false_assertions"] = sorted(k for k, v in section.items() if v is False)
    return info


def decide(*, exit_code: int, timed_out: bool, structured: dict[str, Any], produced: list[dict[str, Any]],
           pytest: dict[str, Any] | None, protocol: bool, summary: str) -> tuple[str, str, list[dict[str, Any]]]:
    """(status, reason, assertions) for one attempt — pure, so every rule is unit-tested on its own."""
    doc = structured.get("doc")
    assertions = (doc or {}).get("assertions", [])
    if timed_out:
        return "FAIL", "timeout", assertions
    if doc and doc["status"] in ENV_BLOCKERS:  # a fresh, nonce-checked result naming a missing prerequisite
        return doc["status"], doc.get("reason") or doc["status"], assertions
    if exit_code != 0:
        return "FAIL", f"exit {exit_code}: {summary}"[:300], assertions
    if structured.get("error"):
        return "FAIL", structured["error"], assertions
    if protocol and not structured.get("present"):
        return "FAIL", "structured result missing (the command did not report through FAL_CHECK_RESULT)", assertions
    if doc:
        bad = [a for a in doc.get("assertions", []) if a.get("required", True) and a.get("holds") is not True]
        if bad:
            return "FAIL", f"required assertion {bad[0].get('id')} = {bad[0].get('holds')}", assertions
        if doc["status"] != "PASS":
            return "FAIL", doc.get("reason") or "result FAIL", assertions
        if not [a for a in doc.get("assertions", []) if a.get("required", True)]:
            return "FAIL", "no required assertion recorded (nothing verified)", assertions
    for p in produced:
        if p.get("error"):
            return "FAIL", p["error"], assertions
    for p in produced:
        if p.get("status") in ENV_BLOCKERS:
            return p["status"], p["status_reason"], assertions
        if p.get("status") == "FAIL":
            return "FAIL", p["status_reason"], assertions
        if p.get("false_assertions"):
            return "FAIL", f"{p['path']}: required assertion(s) false: {', '.join(p['false_assertions'])}", assertions
    if pytest is not None and pytest["passed"] == 0:
        if pytest["skipped"]:
            reasons = "; ".join(pytest["skip_reasons"]) or "see log"
            return "BLOCKED", f"no test passed — {pytest['skipped']} skipped ({reasons})"[:300], assertions
        return "FAIL", f"no test passed ({pytest['line']})", assertions
    return "PASS", summary, assertions


def run_attempt(check: Check, n: int, logdir: Path, env: dict[str, str], header: str) -> dict[str, Any]:
    logdir.mkdir(parents=True, exist_ok=True)
    tag = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-attempt-{n}"
    log, result_path = logdir / f"{tag}.log", logdir / f"{tag}.result.json"
    nonce = uuid.uuid4().hex
    attempt_env = {**env, "FAL_CHECK_ID": check.id, "FAL_CHECK_ATTEMPT": str(n), "FAL_CHECK_NONCE": nonce,
                   "FAL_CHECK_RESULT": str(result_path)}
    started, t0 = stamp(), time.time()
    timed_out = False
    with log.open("w") as fh:
        fh.write(f"$ {check.command}\n# {header} · attempt {n} · started {started}\n\n")
        fh.flush()
        try:
            proc = subprocess.run(check.command, shell=True, cwd=ROOT, env=attempt_env, stdout=fh,
                                  stderr=subprocess.STDOUT, timeout=check.timeout_s)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            fh.write(f"\n# TIMEOUT after {check.timeout_s} s\n")
            code, timed_out = 124, True
    text = log.read_text(errors="replace")
    tail = [ln for ln in text.strip().splitlines() if ln.strip() and not ln.startswith("make[")]
    summary = tail[-1][:300] if tail else ""
    structured = read_structured(result_path, nonce)
    produced = [read_produced(ROOT / p, t0, check.assertions_from) for p in check.produces]
    pytest = pytest_summary(text) if "pytest" in check.command else None
    result, reason, assertions = decide(exit_code=code, timed_out=timed_out, structured=structured,
                                        produced=produced, pytest=pytest, protocol=check.protocol, summary=summary)
    return {"attempt": n, "started_at": started, "finished_at": stamp(), "duration_s": round(time.time() - t0, 1),
            "exit_code": code, "result": result, "reason": reason, "log": rel(log), "summary": summary,
            "nonce": nonce, "structured_result": rel(result_path) if structured.get("present") else None,
            "assertions": assertions, "produced": produced, "pytest": pytest}


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


# ------------------------------------------------------------------ aggregation
def counted(check: Check, results: dict[str, Any]) -> bool:
    """Does this check decide its group? Mandatory always; conditional only when its trigger was met."""
    if check.kind == "mandatory":
        return True
    if check.kind == "conditional":
        r = results.get(check.id) or {}
        return bool((r.get("condition") or {}).get("met"))
    return False


def group_status(suite: Suite, g: str, results: dict[str, Any], selected_ids: set[str]) -> str:
    in_group = [c for c in suite.checks if c.group == g]
    if not in_group:  # a declared group nothing is registered in yet (e.g. a later executor's package)
        return "NO_CHECKS" if g in (suite.required_groups or suite.groups) else "OPTIONAL"
    if not any(c.id in selected_ids for c in in_group):
        return "NOT_SELECTED"
    decisive = [c for c in in_group if counted(c, results)]
    if not decisive:
        undecided = [c for c in in_group if c.kind == "conditional" and c.id in selected_ids
                     and not (results.get(c.id) or {}).get("this_run")]
        if undecided:
            return "INCOMPLETE"
        return "NO_CHECKS" if g in (suite.required_groups or suite.groups) else "OPTIONAL"
    current = [results[c.id] for c in decisive if c.id in results and results[c.id].get("this_run")]
    if any(r["result"] == "FAIL" for r in current):
        return "FAIL"
    if len(current) == len(decisive) and all(r["result"] == "PASS" for r in current):
        return "PASS"
    return "INCOMPLETE"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--suite", default="phase3")
    ap.add_argument("--out", default=None, help="output directory (results.json + logs/)")
    ap.add_argument("--group", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--retries", type=int, default=None, help="override every check's retry count")
    ap.add_argument("--strict", action="store_true", help="exit non-zero unless the run is complete")
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
    strays = [c.id for c in suite.checks if c.group not in suite.groups]
    if strays:
        print(f"checks registered in undeclared groups: {strays}", file=sys.stderr)
        return 2
    selected = [c for c in suite.checks if not ((only and c.id not in only) or c.id in skip
                                                  or (groups and c.group not in groups))]
    if args.list:
        for c in suite.checks:
            print(f"{'*' if c in selected else ' '} {c.group:<16} {c.id:<28} {c.kind:<11} {c.requires or '-':<9} {c.title}")
        return 0
    full = not (only or skip or groups)
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": os.environ.get("UV_PROJECT_ENVIRONMENT",
                                                                    str(Path.home() / ".venvs" / "formal-agent-lab"))}
    for key in ("NO_PROXY", "no_proxy"):
        env[key] = ",".join(x for x in (env.get(key), "127.0.0.1,localhost,::1") if x)
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    outputs = tuple(dict.fromkeys((*suite.outputs, str(out.relative_to(ROOT)) + "/" if out.is_relative_to(ROOT) else "")))
    outputs = tuple(o for o in outputs if o)
    hidden = code_hidden_by(outputs)
    if hidden:
        print(f"refusing to run: excluded output paths would hide executable code from the digest: {hidden[:10]}",
              file=sys.stderr)
        return 2
    tree, config = worktree_digest(outputs), config_digest(suite)
    results_path = out / "results.json"
    previous = json.loads(results_path.read_text()) if results_path.exists() else {}
    results = {r["id"]: r for r in previous.get("checks", [])}
    for r in results.values():
        r["inherited"] = not (r.get("checked_commit") == rev and r.get("worktree_sha256") == tree["sha256"]
                              and r.get("config_sha256") == config["sha256"])
        r["this_run"] = False
    run_nonce = uuid.uuid4().hex
    res_before = resources()
    print(f"==> {suite.name}: {len(selected)} check(s) at {rev[:12]} (tree {tree['sha256'][:12]}, "
          f"config {config['sha256'][:12]}); resources {res_before['disk_free_gib']} → {out}", flush=True)
    probes: dict[str, str | None] = {}
    started_run, t_all = stamp(), time.time()

    def cached_probe(name: str) -> str | None:
        if name not in probes:
            probes[name] = probe(name)
        return probes[name]

    for check in selected:
        header = f"{suite.name}/{check.id} at {rev[:12]} (tree {tree['sha256'][:12]}, profile {check.profile})"
        condition = None
        if check.kind == "conditional":  # applicability is fixed before anything runs
            why_not = cached_probe(check.trigger) if check.trigger else "no trigger declared"
            condition = {"trigger": check.trigger, "met": why_not is None, "detail": why_not or "trigger holds"}
        reason = None
        if condition is not None and not condition["met"]:
            reason = f"NOT_APPLICABLE: {condition['detail']}"
        elif check.requires:
            reason = cached_probe(check.requires)
        if not reason and check.heavy_gib:
            need = check.heavy_gib + RESERVE_GIB  # what it writes + what must stay free
            g = subprocess.run([sys.executable, "scripts/disk_guard.py", "--need", str(need), "--label",
                                f"{check.id} ({check.heavy_gib} GiB + {RESERVE_GIB} GiB reserve)", "--trim"],
                               cwd=ROOT, capture_output=True, text=True)
            if g.returncode != 0:
                reason = f"BLOCKED: {(g.stderr or g.stdout).strip()[-300:]}"
        attempts: list[dict[str, Any]] = []
        if reason:
            result = next((k for k in ("NOT_APPLICABLE", "NOT_SELECTED", "BLOCKED") if reason.startswith(k)),
                          "NOT_RUN")
            note = reason
            print(f"--> [{check.group}] {check.id}: {result} — {reason}", flush=True)
        else:
            tries = 1 + (check.retries if args.retries is None else args.retries)
            print(f"==> [{check.group}] {check.id}: {check.command}", flush=True)
            for n in range(1, tries + 1):
                a = run_attempt(check, n, out / "logs" / check.id, env, header)
                attempts.append(a)
                print(f"    attempt {n}: {a['result']} ({a['duration_s']} s) {a['reason']}", flush=True)
                if a["result"] != "FAIL":  # environment blockers are not retried
                    break
            result, note = attempts[-1]["result"], attempts[-1]["reason"]
            if check.requires in ("docker", "services"):  # give the host back what the check freed in the VM
                subprocess.run([sys.executable, "scripts/disk_guard.py", "--need", "0", "--trim", "--label",
                                f"after {check.id}"], cwd=ROOT, capture_output=True)
        prior = results.get(check.id)
        history = ([{k: prior.get(k) for k in ("result", "checked_commit", "finished_at", "duration_s")}
                    | {"attempts": len(prior.get("attempts", []))}] if prior else []) + (prior or {}).get("history", [])
        first_fail = next((a for a in attempts if a["result"] == "FAIL"), None)
        references = [{"path": p, "sha256": sha256_of(ROOT / p)} for p in check.evidence]
        results[check.id] = {
            **{k: v for k, v in asdict(check).items() if k not in ("timeout_s",)},
            "result": result, "reason": note, "summary": note, "condition": condition,
            "checked_commit": rev, "worktree_sha256": tree["sha256"],
            "worktree_clean": tree["clean"], "config_sha256": config["sha256"], "run_nonce": run_nonce,
            "started_at": attempts[0]["started_at"] if attempts else stamp(), "finished_at": stamp(),
            "duration_s": round(sum(a["duration_s"] for a in attempts), 1), "attempts": attempts,
            "evidence_files": references + (attempts[-1]["produced"] if attempts else []),
            "first_failure": first_fail and {k: first_fail[k] for k in ("attempt", "reason", "summary", "log",
                                                                        "exit_code")},
            "flaky": bool(first_fail) and result == "PASS", "inherited": False, "this_run": True,
            "history": history[:HISTORY]}
    ordered = [results[c.id] for c in suite.checks if c.id in results]
    selected_ids = {c.id for c in selected}
    status_by_group = {g: group_status(suite, g, results, selected_ids) for g in suite.groups}
    required = suite.required_groups or suite.groups
    complete = full and all(status_by_group[g] == "PASS" for g in required)
    this_run = [r for r in ordered if r.get("this_run")]
    decisive_now = [r for r in this_run if counted(next(c for c in suite.checks if c.id == r["id"]), results)]
    if any(r["result"] == "FAIL" for r in decisive_now):
        selection_status = "FAIL"
    elif decisive_now and all(r["result"] == "PASS" for r in decisive_now):
        selection_status = "PASS"
    else:
        selection_status = "INCOMPLETE"
    unmet = [f"{g}={status_by_group[g]}" for g in required if status_by_group[g] != "PASS"]
    summary = {k: sum(1 for r in this_run if r["result"] == k) for k in STATUSES}
    this_inv = {"started_at": started_run, "finished_at": stamp(), "duration_s": round(time.time() - t_all, 1),
                "full": full, "selection": {"group": sorted(groups), "only": sorted(only), "skip": sorted(skip)},
                "checks": [c.id for c in selected], "commit": rev, "worktree_sha256": tree["sha256"],
                "nonce": run_nonce, "acceptance_nonce": os.environ.get("FAL_ACCEPTANCE_NONCE"),
                "results": {c.id: results[c.id]["result"] for c in selected}}
    runs = [*previous.get("runs", []), this_inv][-HISTORY:]
    last_full = next((r for r in reversed(runs) if r["full"]), None)
    doc = {
        "format": "checks@3", "compatible_with": "checks@2", "suite": suite.name, "generated_at": stamp(),
        "source_revision": {"commit": rev, "worktree": tree}, "config": config,
        "command": "python scripts/check_runner.py " + " ".join(argv if argv is not None else sys.argv[1:]),
        "environment": versions(), "resources_before": res_before, "resources_after": resources(),
        "run": this_inv, "summary": summary, "groups": status_by_group, "required_groups": list(required),
        "selection_status": selection_status, "complete": complete, "mandatory_passed": complete,
        "unmet": unmet if not complete else [],
        "aggregation": "only results produced and verified by this invocation count; a partial selection is never "
                       "complete; results from another commit, work tree or configuration are inherited and ignored",
        "timing": {"this_run_s": this_inv["duration_s"], "last_full_run_s": last_full["duration_s"] if last_full else None,
                   "last_full_run_at": last_full["started_at"] if last_full else None,
                   "partial_runs": [{k: r[k] for k in ("started_at", "duration_s", "selection", "results")}
                                    for r in runs if not r["full"]][-10:]},
        "runs": runs, "checks": ordered,
    }
    out.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    scope = "full run" if full else "partial run (never complete)"
    print(f"==> groups {status_by_group} · {summary}")
    print(f"==> {scope}: selection {selection_status} · complete={complete}"
          + (f" · unmet {unmet}" if unmet and full else "") + f" → {rel(results_path)}")
    if args.strict:
        return 0 if complete else 1
    return 0 if all(r["result"] != "FAIL" for r in this_run) else 1


if __name__ == "__main__":
    sys.exit(main())
