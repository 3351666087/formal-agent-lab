#!/usr/bin/env python3
"""Local environment doctor (P2-004 / P2-100): what this machine can run right now.

    python3 scripts/doctor.py                    # human summary
    python3 scripts/doctor.py --json             # machine-readable report on stdout
    python3 scripts/doctor.py --record PATH      # also write the JSON report to PATH

Reports OS/architecture, the CPU and memory actually available to this VM/container (cgroup limits win over the
host view), disk space of the repository and Docker data roots, the Docker daemon and Compose, port owners, the
pinned toolchain, local dependency state, reachable backing services and — from all of that — which local
profiles (local-lite, local-services, local-kind) are available, their estimated resource needs and port
conflicts. Standard library only, so it runs before `make bootstrap`.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = Path(os.environ.get("UV_PROJECT_ENVIRONMENT", str(Path.home() / ".venvs" / "formal-agent-lab")))

# port → what the project expects there (dev profile unless noted)
PORTS = {
    5432: "PostgreSQL (local-services)",
    7233: "Temporal frontend (local-services)",
    8233: "Temporal UI (local-services)",
    8333: "S3 store / SeaweedFS (local-services)",
    8000: "platform API (dev)",
    5173: "web dev server (dev)",
    8080: "full Compose stack web (local-services, compose profile)",
    8090: "local order service (local-services)",
}

PROFILES = {
    "local-lite": {
        "description": "pure-data examples, local runner, offline replay; no containers",
        "requires": ["python3", "uv", "venv"],
        "ports": [],
        "estimate": {"cpus": 1, "memory_mib": 600, "disk_gib": 1.5},
    },
    "local-services": {
        "description": "PostgreSQL + Temporal + S3 + API + worker + web + local order service",
        "requires": ["python3", "uv", "venv", "docker", "compose", "node", "pnpm"],
        "ports": [5432, 7233, 8233, 8333, 8000, 5173, 8090],
        "estimate": {"cpus": 2, "memory_mib": 2600, "disk_gib": 6},
    },
    "local-kind": {
        "description": "single-node kind cluster for Helm install / upgrade / rollback checks",
        "requires": ["docker", "kind", "helm", "kubectl_or_kind"],
        "ports": [],
        "estimate": {"cpus": 2, "memory_mib": 3000, "disk_gib": 5},
    },
}

TOOLS = {
    "python3": ["python3", "--version"],
    "uv": ["uv", "--version"],
    "node": ["node", "--version"],
    "pnpm": ["pnpm", "--version"],
    "docker": ["docker", "version", "--format", "{{.Server.Version}}"],
    "compose": ["docker", "compose", "version", "--short"],
    "helm": ["helm", "version", "--short"],
    "kind": ["kind", "version"],
    "kubeconform": ["kubeconform", "-v"],
    "temporal": ["temporal", "--version"],
    "java": ["java", "-version"],
    "git": ["git", "--version"],
}


def sh(cmd: list[str], timeout: float = 10, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, **env} if env else None)
        return p.returncode, (p.stdout.strip() or p.stderr.strip())
    except FileNotFoundError:
        return 127, "not installed"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def os_info() -> dict:
    info = {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "python": platform.python_version()}
    osr = read("/etc/os-release") or ""
    m = re.search(r'^PRETTY_NAME="?([^"\n]+)', osr, re.M)
    info["distribution"] = m.group(1) if m else None
    virt = sh(["systemd-detect-virt"])[1] if shutil.which("systemd-detect-virt") else None
    info["virtualization"] = virt
    info["rosetta_binfmt"] = Path("/proc/sys/fs/binfmt_misc/rosetta").exists()
    info["qemu_x86_64_binfmt"] = Path("/proc/sys/fs/binfmt_misc/qemu-x86_64").exists()
    return info


def cpu_memory() -> dict:
    online = os.cpu_count() or 0
    quota = None
    cpu_max = read("/sys/fs/cgroup/cpu.max")
    if cpu_max and not cpu_max.startswith("max"):
        q, period = cpu_max.split()
        quota = round(int(q) / int(period), 2)
    mem_total = None
    meminfo = read("/proc/meminfo") or ""
    m = re.search(r"MemTotal:\s+(\d+) kB", meminfo)
    if m:
        mem_total = int(m.group(1)) // 1024
    m = re.search(r"MemAvailable:\s+(\d+) kB", meminfo)
    mem_avail = int(m.group(1)) // 1024 if m else None
    limit = read("/sys/fs/cgroup/memory.max")
    mem_limit = None if limit in (None, "max") else int(limit) // (1024 * 1024)
    usable_mem = min(x for x in (mem_total, mem_limit) if x is not None) if (mem_total or mem_limit) else None
    load = os.getloadavg() if hasattr(os, "getloadavg") else None
    return {"cpus_online": online, "cgroup_cpu_quota": quota,
            "cpus_usable": quota if quota is not None else online,
            "memory_total_mib": mem_total, "memory_available_mib": mem_avail, "cgroup_memory_limit_mib": mem_limit,
            "memory_usable_mib": usable_mem, "loadavg": [round(x, 2) for x in load] if load else None}


def disk(path: Path) -> dict | None:
    try:
        u = shutil.disk_usage(path)
    except OSError:
        return None
    return {"path": str(path), "total_gib": round(u.total / 2**30, 1), "free_gib": round(u.free / 2**30, 1)}


def docker_info() -> dict:
    code, out = sh(["docker", "info", "--format", "{{json .}}"], timeout=20)
    if code != 0:
        return {"available": False, "error": out[:300]}
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        return {"available": False, "error": "unparseable docker info"}
    root = d.get("DockerRootDir")
    df_code, df_out = sh(["docker", "system", "df", "--format", "{{json .}}"], timeout=30)
    usage = [json.loads(line) for line in df_out.splitlines() if line.startswith("{")] if df_code == 0 else []
    return {"available": True, "server_version": d.get("ServerVersion"), "os": d.get("OperatingSystem"),
            "architecture": d.get("Architecture"), "cpus": d.get("NCPU"),
            "memory_mib": (d.get("MemTotal") or 0) // (1024 * 1024), "root_dir": root,
            "root_disk": disk(Path(root)) if root and Path(root).exists() else None,
            "cgroup_driver": d.get("CgroupDriver"), "cgroup_version": d.get("CgroupVersion"),
            "containers_running": d.get("ContainersRunning"), "images": d.get("Images"),
            "usage": [{"type": u.get("Type"), "size": u.get("Size"), "reclaimable": u.get("Reclaimable")}
                      for u in usage],
            "buildx": sh(["docker", "buildx", "version"])[1][:120]}


def listening() -> dict[int, str]:
    """port → owner for listening TCP sockets: Docker-published ports name their container, processes started by
    scripts/dev.sh are recognised by their pid files, the rest comes from `ss` (best effort without root)."""
    owners: dict[int, str] = {}
    code, out = sh(["ss", "-ltnpH"])
    if code == 0:
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            port = parts[3].rsplit(":", 1)[-1]
            if port.isdigit():
                proc = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                owners[int(port)] = f"pid {proc.group(2)} ({proc.group(1)})" if proc else "unknown process"
    ours = {}
    for pidfile in (ROOT / "var" / "run").glob("*.pid"):
        pid = (read(str(pidfile)) or "").strip()
        if pid:
            ours[pid] = pidfile.stem
    for port, owner in list(owners.items()):
        m = re.match(r"pid (\d+)", owner)
        if m and m.group(1) in ours:
            owners[port] = f"project:{ours[m.group(1)]} (scripts/dev.sh)"
        elif m:  # in the session of a dev.sh process (setsid)?
            code, pgid = sh(["ps", "-o", "sid=", "-p", m.group(1)])
            if code == 0 and pgid.strip() in ours:
                owners[port] = f"project:{ours[pgid.strip()]} (scripts/dev.sh)"
    code, out = sh(["docker", "ps", "--format", "{{.Names}}|{{.Ports}}|{{.Label \"com.docker.compose.project\"}}"],
                   timeout=20)
    if code == 0:
        for line in out.splitlines():
            name, ports, project = (line.split("|") + ["", ""])[:3]
            for m in re.finditer(r":(\d+)->", ports):
                tag = "project" if name.startswith("fal") or project.startswith("fal") else "container"
                owners[int(m.group(1))] = f"{tag}:{name}"
    return owners


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def project_owned() -> dict:
    """Docker resources carrying this project's ownership labels / compose projects."""
    out: dict[str, list[str]] = {}
    for kind, cmd in {
        "containers": ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Label \"com.docker.compose.project\"}}"],
        "volumes": ["docker", "volume", "ls", "--format", "{{.Name}}\t{{.Label \"com.docker.compose.project\"}}"],
    }.items():
        code, text = sh(cmd, timeout=20)
        rows = [line.split("\t") for line in text.splitlines()] if code == 0 else []
        out[kind] = sorted(r[0] for r in rows if len(r) > 1 and (r[1].startswith("fal") or r[0].startswith("fal")))
    code, text = sh(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], timeout=20)
    out["images"] = sorted(i for i in text.splitlines() if i.startswith("formal-agent-lab/")) if code == 0 else []
    code, text = sh(["kind", "get", "clusters"])
    out["kind_clusters"] = [c for c in text.splitlines() if c.startswith("fal")] if code == 0 else []
    return out


def dependencies() -> dict:
    py = VENV / "bin" / "python"
    out = {"venv": str(VENV), "venv_present": py.exists(),
           "node_modules_present": (ROOT / "node_modules").exists() and (ROOT / "web" / "node_modules").exists()}
    if py.exists():
        code, _ = sh(["uv", "sync", "--frozen", "--all-packages", "--check"], timeout=60,
                     env={"UV_PROJECT_ENVIRONMENT": str(VENV)})
        out["python_lock_in_sync"] = code == 0
        code, text = sh([str(py), "-c", "import z3, temporalio, inspect_ai, fastapi; print(z3.get_version_string())"])
        out["python_imports"] = code == 0
        out["z3"] = text if code == 0 else None
    pw = list((Path.home() / ".cache" / "ms-playwright").glob("chromium*"))
    out["playwright_chromium"] = bool(pw)
    env = ROOT / ".env"
    keys = {}
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                keys[k.strip()] = bool(v.strip())
    out["llm_configured"] = bool(os.environ.get("FAL_LLM_API_KEY") or keys.get("FAL_LLM_API_KEY"))
    return out


def services(owners: dict[int, str]) -> dict:
    return {
        "postgres": port_open(5432),
        "temporal": port_open(7233),
        "s3": port_open(8333),
        "api": http_ok("http://127.0.0.1:8000/health"),
        "web_dev": port_open(5173),
        "compose_web": http_ok("http://127.0.0.1:8080/health") or port_open(8080),
        "order_service": http_ok("http://127.0.0.1:8090/health"),
    }


def assess(report: dict) -> dict:
    tools = report["tools"]
    have = {name: info["available"] for name, info in tools.items()}
    have["venv"] = report["dependencies"]["venv_present"]
    have["kubectl_or_kind"] = have.get("kind", False)
    cm = report["cpu_memory"]
    free_disk = min(d["free_gib"] for d in [report["disk"]["repository"], report["docker"].get("root_disk")]
                    if d) if report["disk"]["repository"] else 0
    owners = report["ports"]["owners"]
    out = {}
    for name, p in PROFILES.items():
        missing = [r for r in p["requires"] if not have.get(r)]
        conflicts = [{"port": port, "owner": owners[port]} for port in p["ports"]
                     if port in owners and not owners[port].startswith("project:")]
        est = p["estimate"]
        problems = []
        if cm["memory_usable_mib"] and cm["memory_usable_mib"] < est["memory_mib"]:
            problems.append(f"needs ~{est['memory_mib']} MiB, {cm['memory_usable_mib']} MiB usable")
        if cm["cpus_usable"] and cm["cpus_usable"] < est["cpus"]:
            problems.append(f"needs {est['cpus']} CPU(s), {cm['cpus_usable']} usable")
        if free_disk < est["disk_gib"]:
            problems.append(f"needs ~{est['disk_gib']} GiB free disk, {free_disk} GiB free")
        if "docker" in p["requires"] and not report["docker"]["available"]:
            problems.append("Docker daemon not reachable")
        status = "AVAILABLE" if not (missing or problems or conflicts) else (
            "UNAVAILABLE" if missing or "Docker daemon not reachable" in problems else "DEGRADED")
        out[name] = {"status": status, "description": p["description"], "estimate": est, "missing_tools": missing,
                     "resource_problems": problems, "port_conflicts": conflicts, "ports": p["ports"]}
    return out


def concurrency_defaults(cm: dict) -> dict:
    """Default local resource policy (phase-2 task book §0.2): one experiment at a time, one solver; a second
    concurrent experiment only when the measured headroom allows it."""
    mem = cm.get("memory_usable_mib") or 0
    cpus = cm.get("cpus_usable") or 1
    return {"experiments": 1, "solver_threads": 1, "matrix": "queued",
            "second_experiment_allowed": bool(mem >= 5000 and cpus >= 4),
            "basis": f"{cpus} usable CPU(s), {mem} MiB usable memory"}


def collect() -> dict:
    t0 = time.time()
    tools = {}
    for name, cmd in TOOLS.items():
        code, out = sh(cmd)
        tools[name] = {"available": code == 0, "version": out.splitlines()[0][:120] if out else None}
    owners = listening()
    report = {
        "format": "formal-agent-lab/doctor@1",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hostname": socket.gethostname(),
        "os": os_info(),
        "cpu_memory": cpu_memory(),
        "disk": {"repository": disk(ROOT), "home": disk(Path.home()), "tmp": disk(Path("/tmp"))},
        "docker": docker_info(),
        "tools": tools,
        "dependencies": dependencies(),
        "ports": {"expected": {str(k): v for k, v in PORTS.items()},
                  "owners": {p: owners[p] for p in sorted(owners) if p in PORTS},
                  "in_use": sorted(p for p in PORTS if p in owners or port_open(p))},
        "project_resources": project_owned(),
    }
    report["services"] = services(owners)
    report["profiles"] = assess(report)
    report["concurrency"] = concurrency_defaults(report["cpu_memory"])
    report["repository"] = {
        "revision": sh(["git", "-C", str(ROOT), "rev-parse", "HEAD"])[1],
        "dirty_files": len([x for x in sh(["git", "-C", str(ROOT), "status", "--porcelain"])[1].splitlines() if x]),
    }
    report["duration_s"] = round(time.time() - t0, 2)
    return report


def summary(r: dict) -> str:
    cm, d = r["cpu_memory"], r["docker"]
    lines = [
        f"os        {r['os']['distribution']} {r['os']['machine']} (virt: {r['os']['virtualization']})",
        f"cpu/mem   {cm['cpus_usable']} usable CPU(s), {cm['memory_usable_mib']} MiB usable, "
        f"{cm['memory_available_mib']} MiB available now",
        f"disk      repo {r['disk']['repository']['free_gib']} GiB free"
        + (f", docker {d['root_disk']['free_gib']} GiB free" if d.get("root_disk") else ""),
        f"docker    {d.get('server_version') or 'unavailable'} ({d.get('architecture')}), compose "
        f"{r['tools']['compose']['version']}",
        "tools     " + ", ".join(f"{k}={'ok' if v['available'] else 'missing'}" for k, v in r["tools"].items()),
        "deps      " + ", ".join(f"{k}={v}" for k, v in r["dependencies"].items() if k != "venv"),
        "services  " + ", ".join(f"{k}={'up' if v else 'down'}" for k, v in r["services"].items()),
        "ports     in use: " + (", ".join(f"{p}" for p in r["ports"]["in_use"]) or "none"),
        f"policy    {r['concurrency']['experiments']} experiment, {r['concurrency']['solver_threads']} solver "
        f"thread, matrix {r['concurrency']['matrix']} ({r['concurrency']['basis']})",
    ]
    for name, p in r["profiles"].items():
        extra = "; ".join(p["missing_tools"] and [f"missing {p['missing_tools']}"] or [] + p["resource_problems"]
                          + [f"port {c['port']} used by {c['owner']}" for c in p["port_conflicts"]])
        lines.append(f"profile   {name:15s} {p['status']:12s} ~{p['estimate']['memory_mib']} MiB "
                     f"{p['estimate']['cpus']} CPU {p['estimate']['disk_gib']} GiB" + (f"  ({extra})" if extra else ""))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--record", type=Path)
    ap.add_argument("--require", choices=sorted(PROFILES), help="exit 1 unless this profile is AVAILABLE")
    args = ap.parse_args()
    report = collect()
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else summary(report))
    if args.require and report["profiles"][args.require]["status"] != "AVAILABLE":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
