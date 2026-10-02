"""Build the release: wheels (SDK, CLI, platform packages), web bundle, OCI images, manifest (phase 2: 0.2.0).

    uv run --frozen python scripts/release.py            → out/release/{wheels/, web-dist.tar.gz, manifest.json}
    … --skip-images [--out DIR] [--evidence PATH]        wheels + web + SDK/CLI check + licenses, no OCI images
                                                          (phase 3 check under a disk limit; images: SKIPPED + reason)

Packaging slot for new packages: every uv workspace member (pyproject.toml [tool.uv.workspace]) is built as a wheel
(`uv build --all-packages`) and listed in the manifest; plugins register through the `formal_lab.plugins` entry
point, so a new plugin package needs no change here. Images come from deploy/compose/docker-compose.yaml.

The SDK/CLI wheels are verified by installing them into a fresh virtual environment (project packages from the
built wheels via --find-links; third-party dependencies from the package index / local cache) and running `fal`
against a replay bundle without any server. Fully offline installation is covered by scripts/offline_bundle.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "release"
VERSION = "0.3.0"
IMAGES = ("api", "worker", "web", "orders")
LOCAL_CONFIGS = ("deploy/compose/docker-compose.yaml", "deploy/compose/services.dev.yaml", ".env.example")


def sh(*cmd: str, cwd: Path = ROOT, env: dict | None = None) -> str:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    if res.returncode != 0:
        raise SystemExit(f"$ {' '.join(cmd)}\n{res.stdout}\n{res.stderr}")
    return res.stdout


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    import argparse

    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-images", action="store_true", help="no OCI image builds (wheels, web, SDK/CLI, licenses)")
    ap.add_argument("--out", default=str(OUT))
    evidence_dir = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3")  # phase 2: phase2/
    ap.add_argument("--evidence", default=str(evidence_dir / "release-manifest.json"))
    args = ap.parse_args()
    OUT = Path(args.out).resolve()
    t0 = time.time()
    need = "2" if args.skip_images else "6"
    print(sh(sys.executable, "scripts/disk_guard.py", "--need", need, "--label", "release build", "--trim").strip())
    rev = sh("git", "rev-parse", "HEAD").strip()
    dirty = bool(sh("git", "status", "--porcelain").strip())
    if OUT.exists():
        shutil.rmtree(OUT)
    wheels = OUT / "wheels"
    wheels.mkdir(parents=True)

    print("==> wheels")
    sh("uv", "build", "--all-packages", "--wheel", "--out-dir", str(wheels))
    wheel_info = [{"file": p.name, "sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(wheels.glob("*.whl"))]

    for name in ("LICENSE", "NOTICE"):
        shutil.copyfile(ROOT / name, OUT / name)
    # the local run configurations (phase 4A): what a clean directory needs to start the platform locally
    configs = OUT / "config"
    configs.mkdir()
    config_info = []
    for src in LOCAL_CONFIGS:
        dst = configs / Path(src).name
        shutil.copyfile(ROOT / src, dst)
        config_info.append({"file": f"config/{dst.name}", "source": src, "sha256": sha256(dst), "bytes": dst.stat().st_size})

    print("==> web bundle")
    sh("pnpm", "--dir", "web", "exec", "tsc", "--noEmit", "-p", "tsconfig.json")
    sh("pnpm", "--dir", "web", "exec", "vite", "build")
    web_tar = OUT / f"formal-agent-lab-web-{VERSION}.tar.gz"
    with tarfile.open(web_tar, "w:gz") as tar:
        tar.add(ROOT / "web" / "dist", arcname="web")

    images: list[dict] = []
    skipped = "--skip-images: OCI images not built by this run (make release builds them)" if args.skip_images else None
    print("==> images" + (" (skipped)" if skipped else ""))
    if not skipped:
        sh("docker", "compose", "-f", "deploy/compose/docker-compose.yaml", "build", "--quiet",
           env={"FAL_SOURCE_REVISION": rev})
    for name in () if skipped else IMAGES:
        local = f"formal-agent-lab/{name}:local"
        for tag in (VERSION, rev[:12]):
            sh("docker", "tag", local, f"formal-agent-lab/{name}:{tag}")
        info = json.loads(sh("docker", "image", "inspect", local))[0]
        images.append({"name": name, "refs": [f"formal-agent-lab/{name}:{VERSION}", f"formal-agent-lab/{name}:{rev[:12]}"],
                       "image_id": info["Id"], "architecture": info["Architecture"], "os": info["Os"],
                       "size_bytes": info["Size"], "created": info["Created"],
                       "revision_label": info["Config"]["Labels"].get("org.opencontainers.image.revision"),
                       "licenses_label": info["Config"]["Labels"].get("org.opencontainers.image.licenses")})

    print("==> SDK/CLI wheel check in a clean venv (no server)")
    sdk_check = verify_sdk(wheels)

    print("==> amd64 (other architecture): build with the available builder, run under emulation if possible")
    other_arch = {"build": "NOT_RUN", "reason": skipped} if skipped else cross_arch(rev)
    print("==> license inventory")
    sh(sys.executable, "scripts/license_inventory.py")
    licenses = json.loads((evidence_dir / "licenses.json").read_text())
    import importlib.util

    spec = importlib.util.spec_from_file_location("doctor", ROOT / "scripts" / "doctor.py")
    doctor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doctor)  # type: ignore[union-attr]
    contracts = {v: json.loads((ROOT / "contracts" / v / "DIGEST.json").read_text()) for v in ("v1", "v2")}
    from formal_lab_example_scheduling.scenarios import SCENARIO_CONFIGS, model_package

    pkg = model_package()
    manifest = {
        "format": "formal-agent-lab/release-manifest@1",
        "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": {"repository": "https://github.com/3351666087/formal-agent-lab", "revision": rev, "dirty": dirty},
        "contract": {"version": contracts["v2"]["contract_version"], "digest": contracts["v2"]["digest"]},
        "contracts": {c["contract_version"]: c["digest"] for c in contracts.values()},
        "license": {"spdx": "Apache-2.0", "files": ["LICENSE", "NOTICE"], "third_party": "docs/reuse-ledger.md",
                    "inventory": "docs/licenses.md", "counts": licenses["counts"],
                    "attention": [{k: e[k] for k in ("name", "version", "license", "note")} for e in licenses["attention"]]},
        "architectures": {"native": {"arch": os.uname().machine, "build": "PASS", "run": "PASS (this host)"},
                          "other": other_arch},
        "resources": {"host": doctor.cpu_memory(), "disk": doctor.disk(ROOT)},
        "dependencies": {
            "python": {"lock": "uv.lock", "sha256": sha256(ROOT / "uv.lock"), "python": sys.version.split()[0]},
            "node": {"lock": "pnpm-lock.yaml", "sha256": sha256(ROOT / "pnpm-lock.yaml")},
        },
        "wheels": wheel_info,
        "sdk_cli": {"distributions": ["formal-lab-sdk", "formal-lab-contracts", "formal-lab-model-core (extra: offline)"],
                    "entry_point": "fal = formal_lab_sdk.cli:main", "verification": sdk_check},
        "web": {"file": web_tar.name, "sha256": sha256(web_tar), "bytes": web_tar.stat().st_size},
        "images": images,
        **({"images_skipped": skipped} if skipped else {}),
        "scenarios": {"model": {"package_id": pkg.package_id, "version": pkg.version, "digest": pkg.digest.value},
                      "scenario_ids": [f"sched-{k}" for k in SCENARIO_CONFIGS]},
        "docs": ["README.md", "docs/getting-started.md", "docs/local-development.md", "docs/deployment.md",
                 "docs/acceptance-phase2.md", "docs/contracts/v2.md", "docs/contracts/v1.md",
                 "docs/architecture/plugin-integration.md", "docs/architecture/capability-matrix.md",
                 "docs/architecture/observation-semantics.md", "docs/reuse-ledger.md", "docs/licenses.md",
                 "docs/handoff/phase1.md", "docs/handoff/phase2.md"],
        "follow_up_deployment": FOLLOW_UP,
        "deployment": {"compose": "deploy/compose/docker-compose.yaml", "helm_chart": "deploy/helm/formal-agent-lab"},
        "local_configs": config_info,
        "duration_s": round(time.time() - t0, 1),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    evidence = Path(args.evidence)  # phase 2's copy by default (the phase-1 file stays)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"==> {OUT / 'manifest.json'} ({len(wheel_info)} wheels, {len(images)} images) in {manifest['duration_s']} s")


FOLLOW_UP = [  # deployment work outside this phase: when it becomes necessary and what it depends on
    {"item": "publish images to a registry", "trigger": "use on another machine than the builder",
     "depends_on": "registry and credentials (not configured); digests already pinned in the manifest"},
    {"item": "native amd64 image run", "trigger": "an amd64 host becomes available",
     "depends_on": "the amd64 build of this manifest; CI already runs the Python code natively on x86_64"},
    {"item": "authentication, TLS and multi-user isolation", "trigger": "any access beyond the loopback interface",
     "depends_on": "an identity provider / gateway; the chart exposes the ingress hook"},
    {"item": "production Temporal and PostgreSQL", "trigger": "more than one worker host or durability beyond one disk",
     "depends_on": "external HA services; chart values already point at external endpoints"},
    {"item": "multi-node Kubernetes upgrade / rollback", "trigger": "deployment on a real cluster",
     "depends_on": "cluster access; the kind check covers a single-node development cluster only"},
]


def cross_arch(rev: str) -> dict:
    """Build the api image for the other architecture with the available builder and try it under emulation."""
    other = "amd64" if os.uname().machine in ("aarch64", "arm64") else "arm64"
    tag = f"formal-agent-lab/api:{rev[:12]}-{other}"
    out: dict = {"arch": other, "image": tag}
    builders = subprocess.run(["docker", "buildx", "ls"], capture_output=True, text=True).stdout
    out["builder_platforms"] = sorted({p.strip().rstrip("*") for line in builders.splitlines()
                                       for p in line.split() if p.startswith("linux/")})
    t0 = time.time()
    res = subprocess.run(["docker", "buildx", "build", "--platform", f"linux/{other}", "-f",
                          "deploy/docker/python.Dockerfile", "--target", "api", "-t", tag, "--load",
                          "--build-arg", f"FAL_SOURCE_REVISION={rev}", "."], cwd=ROOT, capture_output=True, text=True)
    out["build"] = "PASS" if res.returncode == 0 else "FAIL"
    out["build_seconds"] = round(time.time() - t0, 1)
    if res.returncode != 0:
        out["build_error"] = res.stderr.strip()[-600:]
        out["run_emulated"] = "NOT_RUN: build failed"
    else:
        run = subprocess.run(["docker", "run", "--rm", "--platform", f"linux/{other}", tag, "python", "-c",
                              "import platform, formal_lab_api, formal_lab_runtime; print(platform.machine())"],
                             capture_output=True, text=True, timeout=600)
        out["run_emulated"] = "PASS" if run.returncode == 0 else "FAIL"
        out["run_emulated_output"] = (run.stdout.strip() or run.stderr.strip())[-300:]
        info = json.loads(subprocess.run(["docker", "image", "inspect", tag], capture_output=True, text=True).stdout)[0]
        out.update({"image_id": info["Id"], "size_bytes": info["Size"], "architecture": info["Architecture"]})
        # recorded above; the image itself is not part of the release and costs ~1 GiB of (host) disk
        subprocess.run(["docker", "rmi", tag], capture_output=True)
        out["image_removed_after_check"] = True
    out["run_native"] = f"NOT_RUN: no {other} host available locally (release built on {os.uname().machine})"
    return out


def verify_sdk(wheels: Path) -> dict:
    from formal_lab_example_scheduling.scenarios import model_package, scenario
    from formal_lab_runtime import default_registry, make_manifest, new_run_id, run_local
    from formal_lab_runtime.bundles import bundle_from_local

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pkg = model_package()
        res = run_local(make_manifest(run_id=new_run_id(), project_id="release-check",
                                      scenario=scenario("normal", pkg, seed=1), package=pkg,
                                      registry=default_registry()), pkg)
        bundle = tmp_path / "bundle.zip"
        bundle.write_bytes(bundle_from_local(res, pkg))
        venv = tmp_path / "venv"
        sh("uv", "venv", "--python", sys.executable, str(venv))
        py = venv / "bin" / "python"
        # exactly the wheel files just built (by path, so no cached wheel of the same name can stand in for them) +
        # their third-party dependencies from the index / uv cache; no project sources
        built = {p.name.split("-")[0]: p for p in wheels.glob("formal_lab_*.whl")}
        sh("uv", "pip", "install", "--python", str(py), "--find-links", str(wheels),
           f"{built['formal_lab_sdk']}[offline]", str(built["formal_lab_contracts"]), str(built["formal_lab_model_core"]),
           env={"UV_NO_INDEX": "0"})
        installed = sh("uv", "pip", "list", "--python", str(py), "--format", "json")
        names = {p["name"]: p["version"] for p in json.loads(installed)}
        if names.get("formal-lab-sdk") != VERSION:
            raise SystemExit(f"SDK/CLI check: installed formal-lab-sdk {names.get('formal-lab-sdk')}, built {VERSION}")
        fal = venv / "bin" / "fal"
        commands = []
        for args in (["--help"], ["replay", "verify", str(bundle)], ["replay", "view", str(bundle)],
                     ["replay", "batches", str(bundle)]):
            r = subprocess.run([str(fal), *args], capture_output=True, text=True,
                               env={**os.environ, "FAL_API_URL": "http://127.0.0.1:9/api/v1"}, cwd=tmp)
            commands.append({"command": "fal " + " ".join(a if not a.startswith(tmp) else "<bundle>" for a in args),
                             "exit_code": r.returncode, "first_line": (r.stdout.strip().splitlines() or [""])[0][:120]})
        ok = all(c["exit_code"] == 0 for c in commands)
        if not ok:
            raise SystemExit(f"SDK/CLI check failed: {commands}")
        return {"clean_venv": True, "project_packages_from": "built wheels (--find-links)",
                "third_party_from": "package index / uv cache", "installed": {k: v for k, v in names.items() if k.startswith("formal-lab")},
                "commands": commands, "server": "none (FAL_API_URL points to an unreachable port)"}


if __name__ == "__main__":
    main()
