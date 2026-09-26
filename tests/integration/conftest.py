"""Integration fixtures: real PostgreSQL + Temporal (make services-up), API and worker as subprocesses.

Each session uses its own Temporal task queue and API port so it never interferes with a running dev
stack; the worker can be SIGKILLed and restarted to test recovery.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "var" / "log" / "integration"

# Integration tests use their own database and artifact root so they never touch development data.
# (Set before any formal_lab_api import: settings are cached per process.)
BASE_DB = os.environ.get("FAL_DATABASE_URL", "postgresql+psycopg://fal:fal@127.0.0.1:5432/fal")
TEST_DB = BASE_DB.rsplit("/", 1)[0] + "/fal_it"
os.environ["FAL_DATABASE_URL"] = TEST_DB
os.environ["FAL_ARTIFACT_ROOT"] = str(ROOT / "var" / "it-artifacts")


def _ensure_test_database() -> None:
    import psycopg

    admin = BASE_DB.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(admin, autocommit=True) as conn:
        exists = conn.execute("select 1 from pg_database where datname = 'fal_it'").fetchone()
        if not exists:
            conn.execute("create database fal_it")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Stack:
    def __init__(self) -> None:
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}/api/v1"
        self.env = {**os.environ, "FAL_TEMPORAL_TASK_QUEUE": f"it-{uuid.uuid4().hex[:8]}",
                    "FAL_API_PORT": str(self.port), "FAL_API_HOST": "127.0.0.1", "FAL_LOG_LEVEL": "INFO"}
        self.api: subprocess.Popen | None = None
        self.worker: subprocess.Popen | None = None
        self.worker_starts = 0
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(base_url=self.base, timeout=30)

    def _spawn(self, name: str, module: str) -> subprocess.Popen:
        log = open(LOG_DIR / f"{name}.log", "ab")  # noqa: SIM115 - closed with the process
        return subprocess.Popen([sys.executable, "-m", module], cwd=ROOT, env=self.env, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)

    def start_api(self) -> None:
        self.api = self._spawn("api", "formal_lab_api.app")
        for _ in range(120):
            try:
                if httpx.get(f"http://127.0.0.1:{self.port}/health", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        raise RuntimeError("API did not start (see var/log/integration/api.log)")

    def start_worker(self) -> None:
        self.worker_starts += 1
        self.worker = self._spawn(f"worker-{self.worker_starts}", "formal_lab_orchestrator.worker")
        time.sleep(2.5)

    def kill_worker(self) -> None:
        assert self.worker is not None
        os.killpg(self.worker.pid, signal.SIGKILL)
        self.worker.wait(timeout=10)
        self.worker = None

    def stop(self) -> None:
        for proc in (self.worker, self.api):
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)

    # ------------------------------------------------------------------ helpers
    def get(self, path: str, **kw):
        r = self.client.get(path, **kw)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json=None, expect: int | tuple = (200, 201), **kw):
        r = self.client.post(path, json=json, **kw)
        codes = expect if isinstance(expect, tuple) else (expect,)
        assert r.status_code in codes, (r.status_code, r.text)
        return r.json() if r.content else None

    def wait_status(self, run_id: str, statuses: set[str], timeout: float = 180) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            run = self.get(f"/runs/{run_id}")
            if run["status"] in statuses:
                return run
            time.sleep(0.3)
        raise AssertionError(f"run {run_id} did not reach {statuses}; last={run['status']}")

    def wait_step(self, run_id: str, step: int, timeout: float = 120) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            run = self.get(f"/runs/{run_id}")
            if run["last_step"] >= step:
                return run
            time.sleep(0.1)
        raise AssertionError(f"run {run_id} did not reach step {step}")

    def events(self, run_id: str) -> list[dict]:
        return self.get(f"/runs/{run_id}/events", params={"limit": 5000})


def _services_ready() -> str | None:
    try:
        from formal_lab_api.db import session_scope
        from sqlalchemy import text

        with session_scope() as s:
            s.execute(text("select 1"))
        with socket.create_connection(("127.0.0.1", 7233), timeout=2):
            pass
    except Exception as exc:
        return str(exc)
    return None


@pytest.fixture(scope="session")
def stack() -> Iterator[Stack]:
    try:
        _ensure_test_database()
    except Exception as exc:
        pytest.skip(f"backing services not running (make services-up): {exc}")
    problem = _services_ready()
    if problem:
        pytest.skip(f"backing services not running (make services-up): {problem}")
    subprocess.run([sys.executable, "-m", "formal_lab_api.migrate", "upgrade"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "formal_lab_api.seed"], cwd=ROOT, check=True, capture_output=True)
    st = Stack()
    st.start_api()
    st.start_worker()
    try:
        yield st
    finally:
        st.stop()


@pytest.fixture(scope="session")
def demo(stack: Stack) -> dict:
    projects = stack.get("/projects")
    project = next(p for p in projects if p["name"] == "生产调度示例")
    scenarios = {s["name"]: s for s in stack.get(f"/projects/{project['id']}/scenarios")}
    seeded = {"EDD 规则": "formal-lab.example.scheduling.edd-dispatch", "Z3 有界规划": "formal-lab.planner.z3-bounded",
              "LLM（真实模型）": "formal-lab.planner.llm", "LLM 替身（stub）": "formal-lab.planner.llm:stub"}
    strategies = {seeded[s["name"]]: s for s in stack.get(f"/projects/{project['id']}/strategies")
                  if s["name"] in seeded}
    return {"project": project["id"], "scenarios": scenarios, "strategies": strategies}
