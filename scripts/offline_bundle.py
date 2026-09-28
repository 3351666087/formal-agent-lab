"""Build an offline package for air-gapped installation of the containerised stack and the SDK/CLI.

    uv run --frozen python scripts/offline_bundle.py [--verify]

Output: out/offline/formal-agent-lab-offline-<rev>.tar (+ .manifest.json beside it; the directory it is built
from is removed once the tar is written, to keep host disk use down) containing
    images/platform.tar.gz one `docker save` of api, worker, web and orders: layers shared by the images (the
                           Python runtime and dependency closure) are stored once; the manifest records each image id
                           and the size the separate saves would have taken
    images/*.tar.gz        the pinned service images (PostgreSQL, Temporal, SeaweedFS)
    wheels/                project wheels + the third-party wheel closure of formal-lab-sdk[offline] and of the
                           standalone scheduling example (rule / Z3 demo without any server)
    web/                   static web bundle (also inside the web image)
    compose.yaml           compose file that uses only the bundled image tags (pull_policy: never)
    install.sh             load images, install the SDK/CLI with --no-index, start the stack
    manifest.json          every included file with sha256/size, image ids, external prerequisites, exclusions

--verify extracts the tarball into an empty directory, installs the CLI with --no-index into a fresh venv,
starts the stack from the bundle's compose file under a separate project name/port with pull_policy never,
runs an experiment through it and tears it down.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_IMAGES = ["postgres:16-alpine", "temporalio/temporal:1.9.1", "chrislusf/seaweedfs:4.47"]
PLATFORM = ("api", "worker", "web", "orders")


def sh(*cmd: str, cwd: Path = ROOT, env: dict | None = None, check: bool = True) -> str:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    if check and res.returncode != 0:
        raise SystemExit(f"$ {' '.join(cmd)}\n{res.stdout[-2000:]}\n{res.stderr[-2000:]}")
    return res.stdout


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


COMPOSE = """\
# Offline compose file (generated): uses only images loaded from ./images, never pulls.
name: ${{FAL_PROJECT:-formal-agent-lab-offline}}
x-platform-env: &platform-env
  FAL_DATABASE_URL: postgresql+psycopg://fal:fal@postgres:5432/fal
  FAL_TEMPORAL_ADDRESS: temporal:7233
  FAL_ARTIFACT_BACKEND: s3
  FAL_S3_ENDPOINT_URL: http://s3:8333
  FAL_S3_BUCKET: formal-lab-artifacts
  FAL_S3_ACCESS_KEY_ID: fal-offline-access
  FAL_S3_SECRET_ACCESS_KEY: fal-offline-secret-key
  FAL_DEPLOYMENT_PROFILE: offline-compose
  FAL_ORDERS_ENDPOINT: http://orders:8765
services:
  postgres:
    image: postgres:16-alpine
    pull_policy: never
    environment: {{ POSTGRES_USER: fal, POSTGRES_PASSWORD: fal, POSTGRES_DB: fal }}
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: {{ test: ["CMD-SHELL", "pg_isready -U fal -d fal"], interval: 2s, retries: 30 }}
  temporal:
    image: temporalio/temporal:1.9.1
    pull_policy: never
    command: ["server", "start-dev", "--ip", "0.0.0.0", "--db-filename", "/data/temporal.db"]
    user: "0:0"
    volumes: [temporaldata:/data]
    healthcheck: {{ test: ["CMD", "temporal", "operator", "cluster", "health", "--address", "127.0.0.1:7233"], interval: 3s, retries: 40 }}
  s3:
    image: chrislusf/seaweedfs:4.47
    pull_policy: never
    command: ["mini", "-dir=/data", "-s3.port=8333"]
    environment: {{ AWS_ACCESS_KEY_ID: fal-offline-access, AWS_SECRET_ACCESS_KEY: fal-offline-secret-key, S3_BUCKET: formal-lab-artifacts }}
    volumes: [s3data:/data]
  migrate:
    image: formal-agent-lab/api:{tag}
    pull_policy: never
    environment: *platform-env
    command: ["fal-migrate", "upgrade"]
    depends_on: {{ postgres: {{ condition: service_healthy }} }}
  api:
    image: formal-agent-lab/api:{tag}
    pull_policy: never
    environment: *platform-env
    depends_on: {{ migrate: {{ condition: service_completed_successfully }}, temporal: {{ condition: service_healthy }} }}
  worker:
    image: formal-agent-lab/worker:{tag}
    pull_policy: never
    environment: *platform-env
    depends_on: {{ migrate: {{ condition: service_completed_successfully }}, temporal: {{ condition: service_healthy }} }}
  orders:
    image: formal-agent-lab/orders:{tag}
    pull_policy: never
    command: ["python", "-m", "formal_lab_example_orders.service", "--data", "/data", "--host", "0.0.0.0", "--port", "8765", "--project", "offline"]
    volumes: [ordersdata:/data]
  web:
    image: formal-agent-lab/web:{tag}
    pull_policy: never
    environment: {{ FAL_API_UPSTREAM: "api:8000" }}
    ports: ["127.0.0.1:${{FAL_WEB_PORT:-8080}}:8080"]
    depends_on: {{ api: {{ condition: service_healthy }} }}
    healthcheck: {{ test: ["CMD", "wget", "-qO-", "http://127.0.0.1:8080/health"], interval: 5s, retries: 20 }}
volumes: {{ pgdata: {{}}, temporaldata: {{}}, s3data: {{}}, ordersdata: {{}} }}
"""

INSTALL = """\
#!/usr/bin/env bash
# Offline installation: no network access is needed (images and wheels are in this directory).
set -euo pipefail
cd "$(dirname "$0")"
for f in images/*.tar.gz; do echo "loading $f"; gunzip -c "$f" | docker load; done
python3 -m venv .venv
.venv/bin/pip install --no-index --find-links wheels "formal-lab-sdk[offline]" formal-lab-example-scheduling
docker compose -f compose.yaml up -d --wait
docker compose -f compose.yaml run --rm api python -m formal_lab_api.seed
echo "web: http://127.0.0.1:${FAL_WEB_PORT:-8080}   CLI: .venv/bin/fal --help"
"""


def build(verify: bool) -> Path:
    t0 = time.time()
    print(sh(sys.executable, "scripts/disk_guard.py", "--need", "8", "--label", "offline bundle", "--trim").strip())
    rev = sh("git", "rev-parse", "HEAD").strip()
    tag = rev[:12]
    out = ROOT / "out" / "offline" / f"formal-agent-lab-offline-{tag}"
    if out.exists():
        shutil.rmtree(out)
    (out / "images").mkdir(parents=True)
    (out / "wheels").mkdir()

    print("==> images")
    sh("docker", "compose", "-f", "deploy/compose/docker-compose.yaml", "build", "--quiet",
       env={"FAL_SOURCE_REVISION": rev})
    images = []
    platform_refs = [f"formal-agent-lab/{n}:{tag}" for n in PLATFORM]
    for name in PLATFORM:
        sh("docker", "tag", f"formal-agent-lab/{name}:local", f"formal-agent-lab/{name}:{tag}")
    combined = out / "images" / "platform.tar.gz"
    with combined.open("wb") as fh:
        save = subprocess.Popen(["docker", "save", *platform_refs], stdout=subprocess.PIPE)
        subprocess.run(["gzip", "-1"], stdin=save.stdout, stdout=fh, check=True)
        save.wait()
        assert save.returncode == 0
    separate = {}
    with tempfile.TemporaryDirectory() as tmp:  # what one file per image would take (for the comparison only)
        for ref in platform_refs:
            f = Path(tmp) / "x.tar.gz"
            subprocess.run(f"docker save {ref} | gzip -1 > {f}", shell=True, check=True)
            separate[ref] = f.stat().st_size
    for ref in platform_refs:
        info = json.loads(sh("docker", "image", "inspect", ref))[0]
        images.append({"ref": ref, "image_id": info["Id"], "architecture": info["Architecture"], "os": info["Os"],
                       "file": f"images/{combined.name}", "layers": len(info["RootFS"]["Layers"])})
    dedupe = {"combined_file": f"images/{combined.name}", "combined_bytes": combined.stat().st_size,
              "combined_sha256": sha256(combined), "separate_bytes": separate,
              "separate_total_bytes": sum(separate.values()),
              "saved_bytes": sum(separate.values()) - combined.stat().st_size}
    for ref in SERVICE_IMAGES:
        if sh("docker", "image", "inspect", ref, check=False).strip() in ("", "[]"):
            sh("docker", "pull", ref)
        info = json.loads(sh("docker", "image", "inspect", ref))[0]
        file = out / "images" / (ref.replace("/", "_").replace(":", "__") + ".tar.gz")
        with file.open("wb") as fh:
            save = subprocess.Popen(["docker", "save", ref], stdout=subprocess.PIPE)
            gz = subprocess.run(["gzip", "-1"], stdin=save.stdout, stdout=fh, check=True)
            save.wait()
            assert save.returncode == 0 and gz.returncode == 0
        images.append({"ref": ref, "image_id": info["Id"], "architecture": info["Architecture"], "os": info["Os"],
                       "file": f"images/{file.name}", "sha256": sha256(file), "bytes": file.stat().st_size})

    print("==> wheels (project + third-party closure of formal-lab-sdk[offline])")
    sh("uv", "build", "--all-packages", "--wheel", "--out-dir", str(out / "wheels"))
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "v"
        sh("uv", "venv", "--python", sys.executable, str(venv))
        pip = [str(venv / "bin" / "python"), "-m", "pip"]
        sh("uv", "pip", "install", "--python", str(venv / "bin" / "python"), "pip")
        sh(*pip, "download", "--quiet", "--dest", str(out / "wheels"), "--find-links", str(out / "wheels"),
           "--only-binary=:all:", "formal-lab-sdk[offline]", "formal-lab-example-scheduling")

    print("==> web, compose, install script")
    sh("pnpm", "--dir", "web", "exec", "vite", "build")
    shutil.copytree(ROOT / "web" / "dist", out / "web")
    (out / "compose.yaml").write_text(COMPOSE.format(tag=tag))
    (out / "install.sh").write_text(INSTALL)
    (out / "install.sh").chmod(0o755)
    for name in ("LICENSE", "NOTICE"):
        shutil.copyfile(ROOT / name, out / name)

    files = sorted(p for p in out.rglob("*") if p.is_file())
    contracts = json.loads((ROOT / "contracts" / "v2" / "DIGEST.json").read_text())
    manifest = {
        "format": "formal-agent-lab/offline-manifest@2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": {"revision": rev, "dirty": bool(sh("git", "status", "--porcelain").strip())},
        "contract": {"version": contracts["contract_version"], "digest": contracts["digest"]},
        "platform": {"architecture": platform.machine(), "python_tag": "cp312 / py3", "os": "linux"},
        "included": {
            "images": images,
            "image_dedupe": dedupe,
            "wheels": [{"file": f"wheels/{p.name}", "sha256": sha256(p), "bytes": p.stat().st_size}
                       for p in sorted((out / "wheels").glob("*.whl"))],
            "web": {"dir": "web", "files": len(list((out / "web").rglob("*")))},
            "compose": "compose.yaml (pull_policy: never)",
            "install": "install.sh",
            "license": {"spdx": "Apache-2.0", "files": ["LICENSE", "NOTICE"]},
            "model_weights": [],
        },
        "not_included": {
            "model_weights": "none needed: LLM strategies call a remote OpenAI-compatible endpoint; rule and Z3 "
                             "strategies need no model. Without FAL_LLM_API_KEY the LLM strategy is unavailable "
                             "(the labelled stub still works).",
            "secrets": "no API keys, passwords or TLS certificates are bundled",
            "kubernetes": "the Helm chart is in the source repository; no cluster images for PostgreSQL/Temporal/S3",
        },
        "external_prerequisites": [
            f"Linux host, {platform.machine()} (images are single-architecture)",
            "Docker Engine with the compose plugin (verified: Docker 29.5.2, compose 5.1.4)",
            "python3 >= 3.12 with venv (for the offline SDK/CLI install)",
            "free loopback port 8080 (FAL_WEB_PORT), ~2 GiB RAM, ~3 GiB disk after loading images",
        ],
        "file_count": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    tar_path = out.with_suffix(".tar")
    with tarfile.open(tar_path, "w") as tar:
        tar.add(out, arcname=out.name)
    shutil.rmtree(out)  # the .tar is the artifact; keeping the unpacked copy doubles its size on the host disk
    side = out.with_suffix(".manifest.json")
    side.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"==> {tar_path} ({tar_path.stat().st_size / 1e6:.0f} MB, {len(files)} files) in {time.time() - t0:.0f} s")
    if verify:
        manifest["verification"] = verify_bundle(tar_path, tag)
        side.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    evidence = ROOT / "docs" / "execution" / "evidence" / "phase2" / "offline-manifest.json"  # phase-1 file stays
    evidence.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return tar_path


def verify_bundle(tar_path: Path, tag: str) -> dict:
    """Extract into an empty directory, install the CLI with --no-index, run the stack from the bundle."""
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(tar_path) as tar:
            tar.extractall(tmp, filter="data")
        root = next(Path(tmp).iterdir())
        manifest = json.loads((root / "manifest.json").read_text())
        for f in sorted((root / "images").glob("*.tar.gz")):
            subprocess.run(f"gunzip -c '{f}' | docker load -q", shell=True, check=True, capture_output=True)
        ids = {i["ref"]: json.loads(sh("docker", "image", "inspect", i["ref"]))[0]["Id"]
               for i in manifest["included"]["images"]}
        ids_match = all(ids[i["ref"]] == i["image_id"] for i in manifest["included"]["images"])
        venv = root / ".venv"
        sh(shutil.which("python3") or "/usr/bin/python3", "-m", "venv", str(venv))  # same as install.sh
        sh(str(venv / "bin" / "pip"), "install", "--quiet", "--no-index", "--find-links", str(root / "wheels"),
           "formal-lab-sdk[offline]", "formal-lab-example-scheduling")
        demo = {}
        for strategy in ("rule", "z3"):  # the standalone example: no server, no package index, no model API
            r = subprocess.run([str(venv / "bin" / "python"), "-m", "formal_lab_example_scheduling", "run",
                                "--scenario", "normal", "--strategy", strategy, "--seed", "1"], capture_output=True,
                               text=True, timeout=900, cwd=root)
            demo[strategy] = {"exit_code": r.returncode, "succeeded": "SUCCEEDED" in r.stdout,
                              "tail": r.stdout.strip().splitlines()[-3:]}
        env = {"FAL_PROJECT": "fal-offline-verify", "FAL_WEB_PORT": "18080"}
        compose = ["docker", "compose", "-f", str(root / "compose.yaml")]
        try:
            sh(*compose, "up", "-d", "--wait", cwd=root, env=env)
            sh(*compose, "run", "--rm", "api", "python", "-m", "formal_lab_api.seed", cwd=root, env=env)
            fal = str(venv / "bin" / "fal")
            api = {"FAL_API_URL": "http://127.0.0.1:18080/api/v1"}
            run = subprocess.run([fal, "run", "start", "--project", "生产调度示例", "--scenario", "正常调度",
                                  "--strategy", "EDD 规则", "--wait"], capture_output=True, text=True,
                                 env={**os.environ, **api}, timeout=600)
            ok = run.returncode == 0 and "SUCCEEDED" in run.stdout and ids_match and \
                all(d["succeeded"] for d in demo.values())
            return {"extracted_to_empty_dir": True, "cli_install": "pip --no-index from bundled wheels",
                    "image_ids_match_manifest": ids_match, "standalone_demo": demo,
                    "model_api": "not needed: rule and Z3 strategies; an LLM strategy needs FAL_LLM_* (not bundled)",
                    "compose_pull_policy": "never", "experiment": run.stdout.strip().splitlines()[-12:],
                    "exit_code": run.returncode, "passed": ok, "duration_s": round(time.time() - t0, 1)}
        finally:
            subprocess.run([*compose, "down", "-v"], cwd=root, env={**os.environ, **env}, capture_output=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    build(ap.parse_args().verify)
