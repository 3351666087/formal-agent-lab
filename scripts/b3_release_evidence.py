"""B3 release evidence: the security domain from the release outputs, in clean directories (phase 4B, B3).

The task book's three local deliveries, mapped onto the existing profiles (scripts/doctor.py DELIVERY):

  release            `scripts/release.py --skip-images` (reused when out/release was built at this clean revision):
                     every workspace wheel incl. the domain packages, the web bundle, the local configurations, the MAL
                     example envelopes and the manifest. The OCI images are the phase-3 check p3-release-images (and
                     the GHCR publish); they are not rebuilt here.
  install modes      three clean virtual environments, labelled apart: ONLINE (project wheels from the release,
                     third-party from the package index), CACHE (uv --offline: third-party only from the local uv cache)
                     and FULLY OFFLINE (pip --no-index from a wheelhouse = the release wheels + the third-party closure,
                     downloaded once online; HTTP(S) proxies point at a closed port while installing and running).
  local-simulation   in the fully-offline environment, from an empty directory: the MAL attack graph from the released
                     example is compiled by the installed frontend and run as the per-action gated red team (issuer +
                     Broker); exported as a replay bundle.
  local-service-lab  from the ONLINE environment: the platform API + worker start against the local backing services
                     (a dedicated database), `fal model push --frontend` imports the example, the SDK configures the
                     gated scenario, `fal run start --wait` runs it, `fal export` exports it, the API and worker stop,
                     and `fal replay` reads the bundle with nothing listening. The order service starts from its
                     installed wheel (process mode): normal business, a privileged change denied without a receipt
                     (no side effect) and applied with one, then a clean shutdown.
  local-offline      the fully-offline environment verifies and explains both bundles with the network closed.

Native toolchains are prerequisites outside the wheels (CybORG for CAGE 4, mal-toolbox / mal-simulator for live MAL
capture); their presence is recorded, not installed. Writes $FAL_EVIDENCE_DIR/b3-release.json; reports through
scripts/check_result.py (BLOCKED when the backing services are not running).
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
OUT = ROOT / "out" / "release"
DOMAIN_WHEELS = ("formal_lab_domain_mal", "formal_lab_domain_broker", "formal_lab_env_mal", "formal_lab_env_cage")
# what a domain lab installs: the platform (API + worker + SDK/CLI) and the plugins the MAL experiment uses
DISTS = ["formal-lab-platform-api", "formal-lab-orchestrator", "formal-lab-sdk[offline]", "formal-lab-runtime",
         "formal-lab-neutral-env", "formal-lab-evaluation", "formal-lab-domain-mal", "formal-lab-domain-broker",
         "formal-lab-example-orders"]
CLOSED = {"PIP_NO_INDEX": "1", "UV_OFFLINE": "1", "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
          "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9"}
LOOPBACK = {"NO_PROXY": "127.0.0.1,localhost,::1", "no_proxy": "127.0.0.1,localhost,::1"}


def sh(*cmd: str, cwd: Path = ROOT, env: dict | None = None, check: bool = True,
       timeout: int = 1800) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})},
                         timeout=timeout)
    if check and res.returncode != 0:
        raise SystemExit(f"$ {' '.join(cmd)}\n{res.stdout[-2000:]}\n{res.stderr[-2000:]}")
    return res


def clean_env(extra: dict | None = None) -> dict:
    """The environment of a process run from an installed release: no repository venv, no PYTHONPATH."""
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH", "UV_PROJECT_ENVIRONMENT")}
    return {**env, **LOOPBACK, **(extra or {})}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def git_state() -> tuple[str, bool]:
    rev = sh("git", "rev-parse", "HEAD").stdout.strip()
    dirty = bool(sh("git", "status", "--porcelain", "--untracked-files=no", "--", ".", ":!docs/execution/evidence",
                    ":!var", ":!out").stdout.strip())
    return rev, dirty


def build_release() -> dict:
    rev, dirty = git_state()
    manifest_path = OUT / "manifest.json"
    if manifest_path.exists() and not dirty:
        m = json.loads(manifest_path.read_text())
        if m.get("source", {}).get("revision") == rev and not m["source"].get("dirty") and m.get("examples"):
            return {"reused": True, "reason": f"out/release was built at this clean revision {rev[:12]}", "manifest": m}
    sh(sys.executable, "scripts/release.py", "--skip-images", "--out", str(OUT),
       "--evidence", str(EV / "release-manifest.json"), env={"FAL_EVIDENCE_DIR": str(EV.relative_to(ROOT))})
    return {"reused": False, "manifest": json.loads(manifest_path.read_text())}


def venv(path: Path) -> Path:
    sh("uv", "venv", "--python", sys.executable, str(path), cwd=path.parent)
    return path / "bin" / "python"


MAL_DRIVER = r'''
"""Runs from an installed release only: compile the example attack graph, run the per-action gated red team, export."""
import json, os, sys
from pathlib import Path
import formal_lab_domain_mal, formal_lab_runtime
from formal_lab_contracts import ModelSource
from formal_lab_domain_mal.frontend import MalFrontend
from formal_lab_domain_mal.run import red_team_scenario
from formal_lab_runtime import default_registry, make_manifest, run_local
from formal_lab_runtime.bundles import bundle_from_local

example, work = Path(sys.argv[1]), Path(sys.argv[2])
work.mkdir(parents=True, exist_ok=True)
pkg = MalFrontend().compile(ModelSource(format="mal-attack-graph/v1", text=example.read_text()),
                            package_id="mal-net-app-data", version=1)
ks = work / "keys.json"
ks.write_text(json.dumps({"issuer-1": os.urandom(24).hex()}))
rc = str(work / "receipts.json")
tgt = {"property_id": "secret-confidentiality", "reach_forbidden": "secret:read"}
gates = [{"plugin": {"plugin_id": "formal-lab.domain.mal.receipt-issuer", "version": "1.0.0"},
          "config": {"keystore_path": str(ks), "receipts_path": rc, "target_security": tgt}},
         {"plugin": {"plugin_id": "formal-lab.domain.mal.broker-gate", "version": "1.0.0"},
          "config": {"keystore_path": str(ks), "receipts_path": rc, "target_security": tgt,
                     "lab_policy": {"allowed_assets": ["app", "secret", "net"], "max_attack_steps": 40}}}]
reg = default_registry()
scn = red_team_scenario(pkg, execution_gates=gates, strategy="symbolic")
res = run_local(make_manifest(run_id="run_b3_release_mal", project_id="b3-release", scenario=scn, package=pkg,
                              registry=reg), pkg, reg)
bundle = work / "mal.replay.zip"
bundle.write_bytes(bundle_from_local(res, pkg))
decisions = [d for st in res.steps for d in (st.operation.decisions if st.operation else [])]
print(json.dumps({"status": res.status.value, "steps": len(res.steps), "bundle": str(bundle),
                  "decisions": len(decisions), "all_allow_at_revision": all(
                      str(d.verdict) == "ALLOW" and d.checked_at_revision is not None for d in decisions),
                  "gates": sorted({d.gate.plugin_id for d in decisions}),
                  "imported_from": {"domain_mal": formal_lab_domain_mal.__file__, "runtime": formal_lab_runtime.__file__}}))
'''

PROJECT_DRIVER = r'''
"""Runs from an installed release only: create the project through the SDK."""
import json, sys
from formal_lab_sdk import Client

print(json.dumps(Client(sys.argv[1]).create_project(sys.argv[2], "B3: the MAL domain from the release outputs")))
'''

PLATFORM_DRIVER = r'''
"""Runs from an installed release only: configure the gated MAL scenario through the SDK on a running API."""
import json, os, sys
from pathlib import Path
from formal_lab_sdk import Client

api, project, version_id, work = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
from formal_lab_contracts import ModelSource
from formal_lab_domain_mal.frontend import MalFrontend
from formal_lab_domain_mal.run import red_team_scenario

c = Client(api)
ks = work / "platform-keys.json"
ks.write_text(json.dumps({"issuer-1": os.urandom(24).hex()}))
rc = str(work / "platform-receipts.json")
tgt = {"property_id": "secret-confidentiality", "reach_forbidden": "secret:read"}
gates = [{"plugin": {"plugin_id": "formal-lab.domain.mal.receipt-issuer", "version": "1.0.0"},
          "config": {"keystore_path": str(ks), "receipts_path": rc, "target_security": tgt}},
         {"plugin": {"plugin_id": "formal-lab.domain.mal.broker-gate", "version": "1.0.0"},
          "config": {"keystore_path": str(ks), "receipts_path": rc, "target_security": tgt,
                     "lab_policy": {"allowed_assets": ["app", "secret", "net"], "max_attack_steps": 40}}}]
pkg = MalFrontend().compile(ModelSource(format="mal-attack-graph/v1", text=Path(sys.argv[5]).read_text()),
                            package_id="mal-net-app-data", version=1)
m = red_team_scenario(pkg, execution_gates=gates).model_dump(mode="json")
body = {"name": "MAL 红队（发行物）", "model_version_id": version_id,
        **{k: m[k] for k in ("environment", "participants", "objectives", "budget", "seed", "stop_conditions",
                             "execution_gates")}}
print(json.dumps({"scenario_id": c.create_scenario(project, body)["id"]}))
'''

ORDERS_DRIVER = r'''
"""Runs from an installed release only: the order service (process mode) and a Broker-gated privileged change."""
import json, os, sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
import httpx
from formal_lab_domain_broker import HmacSigner, HmacVerifier, KeyStore, VerificationReceipt, digest_params
from formal_lab_domain_broker.receipt import CheckBasis, ReceiptBindings, sign_receipt
from formal_lab_example_orders.domain_lab import SecurityProbe, gated_condition_change, orders_admission_ruleset
from formal_lab_example_orders.lifecycle import ServiceManager

work, tenant = Path(sys.argv[1]), "b3lab"
ks = KeyStore({"ops-key": os.urandom(24)})
signer, verifier, ruleset = HmacSigner(ks, "ops-key"), HmacVerifier(ks), orders_admission_ruleset()
sm = ServiceManager(workdir=work, project="b3-release", mode="process")
out = {}
try:
    sm.create().start()
    out["ready"] = sm.ready(timeout_s=30).get("status")
    ep = sm.endpoint
    sm.reset(tenant, case="normal", seed=1)
    ops = [httpx.post(f"{ep}/t/{tenant}/operations", json={"operation_id": f"op-{i}", "action": "reserve",
                                                           "params": {"o": o}, "actor_id": "ops"}, timeout=15).status_code
           for i, o in enumerate(["o1", "o2", "o3"])]
    out["business"] = ops
    probe = SecurityProbe(ep, tenant)
    rev = httpx.get(f"{ep}/t/{tenant}/state", timeout=10).json().get("revision", 0)
    conds = {"slow_stations": ["p2"]}
    before = httpx.get(f"{ep}/t/{tenant}/admin/conditions", timeout=10).json()
    denied = gated_condition_change(ep, tenant, conds, receipt=None, verifier=verifier, ruleset=ruleset,
                                    current_revision=rev, role_allowed_actions=["set_conditions"])
    after_denied = httpx.get(f"{ep}/t/{tenant}/admin/conditions", timeout=10).json()
    now = datetime.now(UTC)
    receipt = sign_receipt(VerificationReceipt(
        receipt_id="b3-cfg", bindings=ReceiptBindings(
            run_id=tenant, step=0, actor_id="operator", operation_id="cfg", action_type="set_conditions",
            action_params_digest=digest_params({"conditions": conds}), state_revision=rev,
            service_identity="order-service"),
        check_basis=CheckBasis(query_kind="ACTION_PRECONDITION", property_id="privileged-config", verdict="HOLDS",
                               scope="MODEL_INTERNAL", backend="formal-lab.verifier.z3-bmc@1.1.0"),
        guarantee_scope="operator-authorised operating-condition change", issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=300)).isoformat(), issuer="ops-key"), signer)
    allowed = gated_condition_change(ep, tenant, conds, receipt=receipt, verifier=verifier, ruleset=ruleset,
                                     current_revision=rev, role_allowed_actions=["set_conditions"])
    out["broker"] = {"denied_verdict": denied["verdict"], "zero_side_effect": before == after_denied,
                     "allowed_verdict": allowed["verdict"], "applied": allowed.get("applied"),
                     "probe_sees_change": "p2" in ((probe.sample().get("config") or {}).get("slow_stations") or [])}
finally:
    out["close"] = sm.close(remove_data=True)
print(json.dumps(out, default=str))
'''


def run_driver(python: Path, code: str, name: str, work: Path, *args: str, env: dict | None = None,
               cwd: Path | None = None) -> dict:
    script = work / name
    script.write_text(code)
    res = sh(str(python), str(script), *args, cwd=cwd or work, env=clean_env(env), check=False)
    try:
        return {"exit": res.returncode, **json.loads(res.stdout.strip().splitlines()[-1])}
    except (json.JSONDecodeError, IndexError):
        return {"exit": res.returncode, "error": (res.stdout + res.stderr)[-1500:]}


def services_ready() -> str | None:
    try:
        import psycopg

        base = os.environ.get("FAL_DATABASE_URL", "postgresql+psycopg://fal:fal@127.0.0.1:5432/fal")
        with psycopg.connect(base.replace("postgresql+psycopg://", "postgresql://"), connect_timeout=5) as conn:
            conn.execute("select 1")
        with socket.create_connection(("127.0.0.1", 7233), timeout=5):
            pass
    except Exception as exc:
        return f"backing services not reachable (make services-up): {exc}"
    return None


def ensure_db(name: str) -> str:
    import psycopg

    base = os.environ.get("FAL_DATABASE_URL", "postgresql+psycopg://fal:fal@127.0.0.1:5432/fal")
    with psycopg.connect(base.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as conn:
        if not conn.execute("select 1 from pg_database where datname = %s", (name,)).fetchone():
            conn.execute(f"create database {name}")
    return base.rsplit("/", 1)[0] + f"/{name}"


def platform_lab(python: Path, work: Path, example: Path) -> dict:
    """The local-service-lab entry from the clean ONLINE install: API + worker, import, configure, run, export, stop."""
    bindir = python.parent
    port = free_port()
    api = f"http://127.0.0.1:{port}/api/v1"
    empty = work / "platform"
    empty.mkdir()
    env = clean_env({"FAL_DATABASE_URL": ensure_db("fal_b3rel"), "FAL_ARTIFACT_ROOT": str(empty / "artifacts"),
                     "FAL_API_PORT": str(port), "FAL_API_HOST": "127.0.0.1",
                     "FAL_TEMPORAL_TASK_QUEUE": f"b3rel-{uuid.uuid4().hex[:8]}", "FAL_API_URL": api})
    out: dict = {"api": api}
    mig = sh(str(python), "-m", "formal_lab_api.migrate", "upgrade", cwd=empty, env=env, check=False)
    out["migrate_exit"] = mig.returncode
    procs = []
    for name, module in (("api", "formal_lab_api.app"), ("worker", "formal_lab_orchestrator.worker")):
        log = open(empty / f"{name}.log", "ab")  # noqa: SIM115 - closed with the process
        procs.append(subprocess.Popen([str(python), "-m", module], cwd=empty, env=env, stdout=log,
                                      stderr=subprocess.STDOUT, start_new_session=True))
    try:
        import httpx

        for _ in range(160):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1, trust_env=False).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        time.sleep(2.5)  # the worker registers with Temporal
        fal = str(bindir / "fal")
        project = run_driver(python, PROJECT_DRIVER, "project_driver.py", work, api, f"B3 发行物 {uuid.uuid4().hex[:6]}",
                             env=env, cwd=empty)
        pid = project["id"]
        out["project"] = project
        pushed = json.loads(sh(fal, "model", "push", str(example), "--project", pid, "--package-id", "mal-net-app-data",
                               "--frontend", "formal-lab.domain.mal.frontend", "--source-format", "mal-attack-graph/v1",
                               cwd=empty, env=env).stdout)
        out["model_push"] = {"version": pushed.get("version"), "semantic_profile": pushed.get("semantic_profile")}
        cfg = run_driver(python, PLATFORM_DRIVER, "platform_driver.py", work, api, pid, pushed["id"], str(empty),
                         str(example), env=env, cwd=empty)
        out["configure"] = cfg
        started = sh(fal, "run", "start", "--project", pid, "--scenario", cfg["scenario_id"], "--wait", cwd=empty,
                     env=env, check=False, timeout=900)
        run_id = started.stdout.split()[1]
        run = json.loads(sh(fal, "run", "show", run_id, cwd=empty, env=env, check=False).stdout or "{}")
        out["run"] = {"run_id": run_id, "exit": started.returncode, "status": run.get("status"),
                      "first_line": started.stdout.strip().splitlines()[0][:120]}
        bundle = empty / "platform.replay.zip"
        sh(fal, "export", run_id, "-o", str(bundle), cwd=empty, env=env)
        out["bundle"] = {"file": str(bundle), "sha256": sha256(bundle)}
    finally:
        for p in procs:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
    out["stopped"] = all(p.poll() is not None for p in procs)
    try:
        import httpx

        httpx.get(f"http://127.0.0.1:{port}/health", timeout=2, trust_env=False)
        out["api_reachable_after_stop"] = True
    except Exception:
        out["api_reachable_after_stop"] = False
    return out


def offline_replay(python: Path, bundle: Path, cwd: Path) -> list[dict]:
    fal = str(python.parent / "fal")
    rows = []
    for args in (["replay", "verify", str(bundle)], ["replay", "step", str(bundle), "1"]):
        res = sh(fal, *args, cwd=cwd, env=clean_env({**CLOSED, "FAL_API_URL": "http://127.0.0.1:9/api/v1"}),
                 check=False)
        row = {"command": f"fal {args[0]} {args[1]} <bundle>" + (f" {args[3]}" if len(args) > 3 else ""),
               "exit_code": res.returncode, "first_line": (res.stdout.strip().splitlines() or [""])[0][:160]}
        if args[1] == "step" and res.returncode == 0:
            step = json.loads(res.stdout)
            row["gates"] = [d.get("decision", d)["gate"]["plugin_id"] for d in step.get("decisions", [])]
        rows.append(row)
    return rows


def main() -> int:
    r = CheckResult("p4-b3-release")
    EV.mkdir(parents=True, exist_ok=True)
    problem = services_ready()
    if problem:
        sys.exit(r.blocked(problem))
    out: dict = {}
    rel = build_release()
    m = rel["manifest"]
    wheels = [w["file"] for w in m["wheels"]]
    out["release"] = {"reused": rel["reused"], "reason": rel.get("reason"), "version": m["version"],
                      "revision": m["source"], "wheels": len(wheels),
                      "domain_wheels": {d: any(w.startswith(d + "-") for w in wheels) for d in DOMAIN_WHEELS},
                      "examples": m.get("examples", []), "web": m["web"], "local_configs": len(m["local_configs"]),
                      "local_profiles": m.get("local_profiles"), "images": "p3-release-images / GHCR (not rebuilt here)"}
    example = OUT / "examples" / "mal-net-app-data.json"
    work = Path(tempfile.mkdtemp(prefix="b3-release-"))
    found = ["--find-links", str(OUT / "wheels")]
    # ---- install modes
    modes = {}
    py_online = venv(work / "online")
    inst = sh("uv", "pip", "install", "--python", str(py_online), *found, *DISTS, check=False, timeout=1800)
    modes["online"] = {"exit": inst.returncode, "third_party_from": "package index (uv; its cache may serve hits)",
                       "tail": (inst.stdout + inst.stderr)[-300:]}
    py_cache = venv(work / "cache")
    inst = sh("uv", "pip", "install", "--offline", "--python", str(py_cache), *found, *DISTS, check=False,
              env={k: v for k, v in CLOSED.items() if k != "UV_OFFLINE"})
    modes["cache"] = {"exit": inst.returncode, "third_party_from": "the local uv cache only (uv --offline, proxies closed)",
                      "tail": (inst.stdout + inst.stderr)[-300:]}
    house = work / "wheelhouse"
    house.mkdir()
    for w in (OUT / "wheels").glob("*.whl"):
        (house / w.name).write_bytes(w.read_bytes())
    tool = venv(work / "tool")
    sh("uv", "pip", "install", "--python", str(tool), "pip")
    dl = sh(str(tool), "-m", "pip", "download", "--quiet", "--dest", str(house), "--find-links", str(house),
            "--only-binary=:all:", *DISTS, check=False, timeout=1800)
    empty = work / "empty"
    empty.mkdir()
    py_off = venv(empty / "venv")
    sh("uv", "pip", "install", "--python", str(py_off), "pip", cwd=empty)
    inst = sh(str(py_off), "-m", "pip", "install", "--no-index", "--find-links", str(house), *DISTS, cwd=empty,
              env=CLOSED, check=False, timeout=1800)
    listed = json.loads(sh(str(py_off), "-m", "pip", "list", "--format", "json", cwd=empty).stdout)
    modes["offline"] = {"exit": inst.returncode, "wheelhouse_download_exit": dl.returncode,
                        "wheelhouse_files": len(list(house.glob("*.whl"))),
                        "third_party_from": "the wheelhouse only (pip --no-index; HTTP(S) proxies closed)",
                        "installed": {p["name"]: p["version"] for p in listed if p["name"].startswith("formal-lab")},
                        "tail": (inst.stdout + inst.stderr)[-300:]}
    out["install_modes"] = modes
    # ---- local-simulation, fully offline: the domain experiment from the released example
    sim = run_driver(py_off, MAL_DRIVER, "mal_driver.py", empty, str(example), str(empty / "sim"), env=CLOSED)
    out["local_simulation"] = sim
    # ---- local-service-lab from the online install: platform + order service
    out["local_service_lab"] = {"platform": platform_lab(py_online, work, example),
                                "order_service": run_driver(py_online, ORDERS_DRIVER, "orders_driver.py", work,
                                                            str(work / "orders"))}
    # ---- local-offline: replay both bundles with nothing listening and the network closed
    plat_bundle = Path(out["local_service_lab"]["platform"].get("bundle", {}).get("file", "/nonexistent"))
    out["local_offline"] = {"simulation_bundle": offline_replay(py_off, Path(sim.get("bundle", "/nonexistent")), empty),
                            "platform_bundle": offline_replay(py_off, plat_bundle, empty)}
    out["native_toolchains"] = {k: Path(os.environ.get(f"FAL_{k.upper()}_HOME", Path.home() / ".venvs" / f"fal-{k}"))
                                .exists() for k in ("cage", "mal")}
    out["native_note"] = ("CybORG (CAGE 4) and mal-toolbox / mal-simulator are not in the wheels, images or the offline "
                          "bundle: they live in their own venvs and must be installed beforehand for formal-lab.env.cage4 "
                          "and for capturing new attack graphs; committed MAL captures run without them")

    c = r.check
    rr = out["release"]
    c("release_has_domain_packages_and_examples", all(rr["domain_wheels"].values()) and len(rr["examples"]) == 2
      and rr["local_profiles"] and set(rr["local_profiles"]) == {"local-simulation", "local-service-lab", "local-offline"},
      f"{rr['wheels']} wheels, domain {rr['domain_wheels']}, examples {[e['file'] for e in rr['examples']]}")
    c("install_online", modes["online"]["exit"] == 0, modes["online"]["tail"][-160:])
    c("install_cache_only", modes["cache"]["exit"] == 0, modes["cache"]["tail"][-160:])
    c("install_fully_offline", modes["offline"]["exit"] == 0 and "formal-lab-domain-mal" in modes["offline"]["installed"],
      f"--no-index from {modes['offline']['wheelhouse_files']} wheels: {modes['offline']['tail'][-120:]}")
    c("local_simulation_domain_experiment_offline",
      sim.get("exit") == 0 and sim.get("status") == "SUCCEEDED" and sim.get("all_allow_at_revision")
      and sim.get("gates") == ["formal-lab.domain.mal.broker-gate", "formal-lab.domain.mal.receipt-issuer"]
      and str(empty) in sim.get("imported_from", {}).get("domain_mal", ""),
      json.dumps({k: sim.get(k) for k in ("status", "steps", "decisions", "imported_from", "error")})[:400])
    plat = out["local_service_lab"]["platform"]
    c("local_service_lab_platform_from_clean_install",
      plat.get("migrate_exit") == 0 and plat.get("run", {}).get("exit") == 0 and plat.get("stopped")
      and not plat.get("api_reachable_after_stop") and "file" in plat.get("bundle", {}),
      json.dumps({k: plat.get(k) for k in ("migrate_exit", "model_push", "run", "stopped", "api_reachable_after_stop")})[:400])
    orders = out["local_service_lab"]["order_service"]
    br = orders.get("broker", {})
    c("local_service_lab_order_service_broker",
      orders.get("exit") == 0 and orders.get("business") == [200, 200, 200] and br.get("denied_verdict") == "DENY"
      and br.get("zero_side_effect") and br.get("allowed_verdict") == "ALLOW" and br.get("applied")
      and br.get("probe_sees_change"), json.dumps(orders, default=str)[:400])
    off = out["local_offline"]
    c("local_offline_replay_both_bundles",
      all(x["exit_code"] == 0 for rows in off.values() for x in rows)
      and all(rows[0]["first_line"].startswith("OK") for rows in off.values())
      and all(rows[1].get("gates") == ["formal-lab.domain.mal.receipt-issuer", "formal-lab.domain.mal.broker-gate"]
              for rows in off.values()),
      json.dumps(off)[:400])
    r.note(f"native toolchains present: {out['native_toolchains']} (prerequisites, not shipped)")
    path = EV / "b3-release.json"
    path.write_text(json.dumps({"deliverable": "phase4B-B3 release", **out,
                                "conclusion": {a["id"]: a["holds"] for a in r.assertions}},
                               indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(path)
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
