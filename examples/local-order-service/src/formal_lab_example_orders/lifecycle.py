"""Lifecycle of a local order service: create → start → ready → reset → close, with ownership labels (P2-062,
P2-063, P2-068).

Two modes, both driven by definitions that ship with this example:

- process  (local-lite)     — `python -m formal_lab_example_orders.service` on a loopback port; an optional
                              supervisor restarts it when it exits unexpectedly (the "process restart" case);
- compose  (local-services) — `docker compose -p <project>` on examples/local-order-service/compose.yaml; the
                              container carries `dev.formal-lab.project=<project>` and restarts unless stopped.

Every resource this manager creates is marked with the project label (a manifest file next to the data for
processes, Docker labels for containers and volumes). Cleanup removes exactly those — never another project's
containers, volumes or processes (the VM is shared).

Resource guard: `precheck()` refuses to start below the CPU / memory / disk floor; `stats()` reports RSS, CPU time
and data size (process) or `docker stats` (compose); `run_with_timeout()` bounds a whole experiment's wall time.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

LABEL = "dev.formal-lab.project"
COMPONENT = "dev.formal-lab.component"
COMPONENT_NAME = "local-order-service"
EXAMPLE_DIR = Path(__file__).resolve().parents[2]
COMPOSE_FILE = EXAMPLE_DIR / "compose.yaml"
STATE_DIR = ".fal-orders"


class LifecycleError(RuntimeError):
    pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def precheck(workdir: Path, *, min_cpus: int = 1, min_mem_mb: int = 256, min_disk_mb: int = 200) -> dict[str, Any]:
    """CPU / memory / disk floor for running a service and an experiment next to it."""
    workdir.mkdir(parents=True, exist_ok=True)
    cpus = os.cpu_count() or 1
    mem_mb = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                mem_mb = int(line.split()[1]) // 1024
    except OSError:
        pass
    disk_mb = shutil.disk_usage(workdir).free // (1024 * 1024)
    problems = []
    if cpus < min_cpus:
        problems.append(f"{cpus} CPU(s) < {min_cpus}")
    if mem_mb is not None and mem_mb < min_mem_mb:
        problems.append(f"{mem_mb} MB available memory < {min_mem_mb} MB")
    if disk_mb < min_disk_mb:
        problems.append(f"{disk_mb} MB free disk in {workdir} < {min_disk_mb} MB")
    report = {"cpus": cpus, "mem_available_mb": mem_mb, "disk_free_mb": disk_mb,
              "floor": {"cpus": min_cpus, "mem_mb": min_mem_mb, "disk_mb": min_disk_mb}, "ok": not problems,
              "problems": problems}
    if problems:
        raise LifecycleError("resource precheck failed: " + "; ".join(problems))
    return report


@dataclass
class ServiceManager:
    workdir: Path
    project: str
    mode: str = "process"  # process | compose
    port: int | None = None
    host: str = "127.0.0.1"
    supervise: bool = False
    status: str = "NEW"
    transitions: list[dict[str, Any]] = field(default_factory=list)
    restarts: list[dict[str, Any]] = field(default_factory=list)
    _proc: subprocess.Popen | None = None
    _closing: bool = False
    _watch: threading.Thread | None = None

    # ------------------------------------------------------------------ paths / state
    @property
    def home(self) -> Path:
        return self.workdir / STATE_DIR / self.project

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def endpoint(self) -> str:
        if self.port is None:
            raise LifecycleError("service has no port yet (start it first)")
        return f"http://{self.host}:{self.port}"

    @property
    def compose_project(self) -> str:
        return f"fal-orders-{self.project}"

    def _to(self, status: str, note: str = "") -> None:
        self.status = status
        self.transitions.append({"status": status, "at": datetime.now(UTC).isoformat(), "note": note})
        self._write_manifest()

    def _write_manifest(self) -> None:
        if not self.home.exists():
            return
        (self.home / "manifest.json").write_text(json.dumps({
            "labels": {LABEL: self.project, COMPONENT: COMPONENT_NAME}, "mode": self.mode, "port": self.port,
            "pid": self._proc.pid if self._proc else None, "status": self.status, "transitions": self.transitions,
            "restarts": self.restarts, "compose_project": self.compose_project if self.mode == "compose" else None,
        }, indent=2))

    # ------------------------------------------------------------------ lifecycle
    def create(self) -> ServiceManager:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._to("CREATED", f"work directory {self.home}")
        return self

    def start(self) -> ServiceManager:
        if self.status == "NEW":
            self.create()
        self._closing = False
        self._to("STARTING")
        if self.mode == "process":
            self.port = self.port or free_port()
            self._spawn()
            if self.supervise:
                self._watch = threading.Thread(target=self._supervisor, name=f"orders-{self.project}", daemon=True)
                self._watch.start()
        elif self.mode == "compose":
            self.port = self.port or free_port()
            self._compose("up", "-d", "--wait")
        else:
            raise LifecycleError(f"unknown mode {self.mode!r}")
        return self

    def _spawn(self) -> None:
        log = open(self.home / "service.log", "a")  # noqa: SIM115 - handed to the child process
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "formal_lab_example_orders.service", "--data", str(self.data_dir),
             "--host", self.host, "--port", str(self.port), "--project", self.project],
            stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        self._write_manifest()

    def _supervisor(self) -> None:
        while not self._closing:
            proc = self._proc
            if proc is None:
                return
            code = proc.wait()
            if self._closing:
                return
            died = time.time()
            self.restarts.append({"exit_code": code, "died_at": died})
            self._spawn()
            try:
                self.ready(timeout_s=30)
                self.restarts[-1]["ready_after_s"] = round(time.time() - died, 3)
            except LifecycleError as exc:
                self.restarts[-1]["error"] = str(exc)
            self._write_manifest()

    def _compose(self, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "FAL_ORDERS_PROJECT": self.project, "FAL_ORDERS_PORT": str(self.port)}
        cmd = ["docker", "compose", "-p", self.compose_project, "-f", str(COMPOSE_FILE), *args]
        res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=EXAMPLE_DIR.parents[1])
        if res.returncode != 0:
            raise LifecycleError(f"{' '.join(cmd)} failed: {res.stderr.strip()[-800:]}")
        return res

    def ready(self, timeout_s: float = 30.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        last = ""
        while time.monotonic() < deadline:
            try:
                resp = httpx.get(f"{self.endpoint}/health", timeout=2)
                if resp.status_code == 200 and resp.json().get("project") == self.project:
                    if self.status != "READY":
                        self._to("READY", f"health ok at {self.endpoint}")
                    return resp.json()
                last = f"HTTP {resp.status_code}"
            except httpx.HTTPError as exc:
                last = type(exc).__name__
            if self.mode == "process" and self._proc is not None and self._proc.poll() is not None \
                    and not self.supervise:
                break
            time.sleep(0.2)
        self._to("FAILED", f"not ready after {timeout_s}s ({last})")
        raise LifecycleError(f"order service {self.project} not ready after {timeout_s}s ({last}); "
                             f"log: {self.home / 'service.log'}")

    def reset(self, tenant: str, *, case: str = "normal", seed: int = 0) -> dict[str, Any]:
        self._to("RESETTING", f"tenant {tenant} → {case}/{seed}")
        resp = httpx.post(f"{self.endpoint}/t/{tenant}/admin/reset", json={"case": case, "seed": seed}, timeout=30)
        resp.raise_for_status()
        self._to("READY", f"tenant {tenant} reset")
        return resp.json()

    def kill(self) -> int:
        """SIGKILL the service process (the supervisor, if any, restarts it)."""
        if self.mode != "process" or self._proc is None:
            raise LifecycleError("kill() is for process mode")
        pid = self._proc.pid
        os.kill(pid, signal.SIGKILL)
        return pid

    def stats(self) -> dict[str, Any]:
        if self.mode == "compose":
            res = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], capture_output=True,
                                 text=True)
            rows = [json.loads(line) for line in res.stdout.splitlines() if line.strip()]
            mine = self._containers()
            return {"mode": "compose", "containers": [r for r in rows if r.get("ID", "")[:12] in
                                                      {c[:12] for c in mine}]}
        out: dict[str, Any] = {"mode": "process", "pid": self._proc.pid if self._proc else None,
                               "data_bytes": sum(p.stat().st_size for p in self.data_dir.glob("*") if p.is_file())
                               if self.data_dir.exists() else 0, "restarts": len(self.restarts)}
        if self._proc is not None and Path(f"/proc/{self._proc.pid}").exists():
            status = Path(f"/proc/{self._proc.pid}/status").read_text()
            rss = next((int(line.split()[1]) for line in status.splitlines() if line.startswith("VmRSS:")), None)
            fields = Path(f"/proc/{self._proc.pid}/stat").read_text().rsplit(")", 1)[1].split()
            ticks = os.sysconf("SC_CLK_TCK")
            out.update({"rss_kb": rss, "cpu_seconds": (int(fields[11]) + int(fields[12])) / ticks})
        return out

    def _containers(self) -> list[str]:
        res = subprocess.run(["docker", "ps", "-aq", "--no-trunc", "--filter", f"label={LABEL}={self.project}",
                              "--filter", f"label={COMPONENT}={COMPONENT_NAME}"], capture_output=True, text=True)
        return [c for c in res.stdout.split() if c]

    def close(self, *, remove_data: bool = True) -> dict[str, Any]:
        """Stop the service and remove what this project created (and only that)."""
        self._closing = True
        removed: dict[str, Any] = {"processes": [], "containers": [], "paths": []}
        if self.mode == "process" and self._proc is not None:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=10)
            removed["processes"].append(self._proc.pid)
        if self.mode == "compose":
            removed["containers"] = self._containers()
            self._compose("down", "-v", "--remove-orphans")
        if self._watch is not None:
            self._watch.join(timeout=5)
        self._to("CLOSED", "service stopped")
        if remove_data and self.home.exists():
            shutil.rmtree(self.home)
            removed["paths"].append(str(self.home))
            parent = self.home.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        return removed

    def __enter__(self) -> ServiceManager:
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.close()


def cleanup_project(workdir: Path, project: str) -> dict[str, Any]:
    """After a failure: remove the processes, containers, volumes and files labelled with `project` — nothing else."""
    removed: dict[str, Any] = {"processes": [], "containers": [], "volumes": [], "paths": []}
    home = workdir / STATE_DIR / project
    manifest = home / "manifest.json"
    if manifest.exists():
        info = json.loads(manifest.read_text())
        pid = info.get("pid")
        if pid and Path(f"/proc/{pid}/cmdline").exists():
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            if "formal_lab_example_orders.service" in cmdline and f"--project {project}" in cmdline:
                os.kill(pid, signal.SIGKILL)
                removed["processes"].append(pid)
    if shutil.which("docker"):
        flt = ["--filter", f"label={LABEL}={project}", "--filter", f"label={COMPONENT}={COMPONENT_NAME}"]
        ids = subprocess.run(["docker", "ps", "-aq", *flt], capture_output=True, text=True).stdout.split()
        if ids:
            subprocess.run(["docker", "rm", "-f", *ids], capture_output=True)
            removed["containers"] = ids
        vols = subprocess.run(["docker", "volume", "ls", "-q", "--filter", f"label={LABEL}={project}"],
                              capture_output=True, text=True).stdout.split()
        if vols:
            subprocess.run(["docker", "volume", "rm", "-f", *vols], capture_output=True)
            removed["volumes"] = vols
    if home.exists():
        shutil.rmtree(home)
        removed["paths"].append(str(home))
    return removed


def run_with_timeout(fn: Any, timeout_s: float, *args: Any, **kw: Any) -> Any:
    """Run `fn` in a thread; raise LifecycleError when it exceeds `timeout_s` (the caller then cleans up)."""
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["result"] = fn(*args, **kw)
        except BaseException as exc:
            box["error"] = exc

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        raise LifecycleError(f"experiment exceeded its {timeout_s}s runtime limit")
    if "error" in box:
        raise box["error"]
    return box.get("result")


def _manifest(workdir: Path, project: str) -> dict[str, Any] | None:
    path = workdir / STATE_DIR / project / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else None


def main(argv: list[str] | None = None) -> int:
    """Dev-script entry: `up | status | reset | down | cleanup` for one project's service (P2-062)."""
    import argparse

    ap = argparse.ArgumentParser(prog="python -m formal_lab_example_orders.lifecycle")
    ap.add_argument("command", choices=["up", "status", "reset", "down", "cleanup"])
    ap.add_argument("--workdir", default="var")
    ap.add_argument("--project", default="dev")
    ap.add_argument("--mode", choices=["process", "compose"], default="process")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--tenant", default="demo")
    ap.add_argument("--case", default="normal")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--purge", action="store_true", help="down: also remove the service data")
    args = ap.parse_args(argv)
    work = Path(args.workdir).resolve()
    info = _manifest(work, args.project)
    if args.command == "up":
        if info and info.get("status") == "READY":
            try:
                if httpx.get(f"http://127.0.0.1:{info['port']}/health", timeout=2).status_code == 200:
                    print(json.dumps({"status": "already running", **info}))
                    return 0
            except httpx.HTTPError:
                pass
        precheck(work)
        mgr = ServiceManager(work, project=args.project, mode=args.mode, port=args.port).start()
        mgr.ready()
        print(json.dumps({"status": "READY", "endpoint": mgr.endpoint, "project": args.project, "mode": args.mode,
                          "pid": mgr._proc.pid if mgr._proc else None, "log": str(mgr.home / "service.log")}))
        return 0
    if info is None:
        print(json.dumps({"status": "absent", "project": args.project}))
        return 0 if args.command in ("status", "down", "cleanup") else 1
    endpoint = f"http://127.0.0.1:{info['port']}"
    if args.command == "status":
        try:
            health = httpx.get(f"{endpoint}/health", timeout=2).json()
        except httpx.HTTPError as exc:
            health = {"status": "unreachable", "error": type(exc).__name__}
        print(json.dumps({**info, "health": health}, default=str))
        return 0
    if args.command == "reset":
        r = httpx.post(f"{endpoint}/t/{args.tenant}/admin/reset", json={"case": args.case, "seed": args.seed},
                       timeout=30)
        r.raise_for_status()
        print(json.dumps({"tenant": args.tenant, "revision": r.json()["revision"]}))
        return 0
    if args.command == "down" and info["mode"] == "process" and info.get("pid"):
        try:
            os.kill(info["pid"], signal.SIGTERM)  # graceful: the service marks a clean shutdown
            for _ in range(50):
                os.kill(info["pid"], 0)
                time.sleep(0.2)
        except ProcessLookupError:
            pass
    if args.command == "down" and info["mode"] == "compose":
        mgr = ServiceManager(work, project=args.project, mode="compose", port=info["port"])
        mgr._compose("down", *(["-v"] if args.purge else []))
    if args.command == "cleanup" or args.purge:
        print(json.dumps(cleanup_project(work, args.project)))
    else:
        print(json.dumps({"status": "stopped", "project": args.project, "data_kept": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
