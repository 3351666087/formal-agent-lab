"""Build the phase-1 release: wheels (SDK, CLI, platform packages), web bundle, OCI images, manifest.

    uv run --frozen python scripts/release.py            → out/release/{wheels/, web-dist.tar.gz, manifest.json}

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
VERSION = "0.1.0"
IMAGES = ("api", "worker", "web")


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
    t0 = time.time()
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

    print("==> web bundle")
    sh("pnpm", "--dir", "web", "exec", "tsc", "--noEmit", "-p", "tsconfig.json")
    sh("pnpm", "--dir", "web", "exec", "vite", "build")
    web_tar = OUT / f"formal-agent-lab-web-{VERSION}.tar.gz"
    with tarfile.open(web_tar, "w:gz") as tar:
        tar.add(ROOT / "web" / "dist", arcname="web")

    print("==> images")
    env = {"FAL_SOURCE_REVISION": rev}
    sh("docker", "compose", "-f", "deploy/compose/docker-compose.yaml", "build", "--quiet", env=env)
    images = []
    for name in IMAGES:
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

    contracts = json.loads((ROOT / "contracts" / "v1" / "DIGEST.json").read_text())
    from formal_lab_example_scheduling.scenarios import SCENARIO_CONFIGS, model_package

    pkg = model_package()
    manifest = {
        "format": "formal-agent-lab/release-manifest@1",
        "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": {"repository": "https://github.com/3351666087/formal-agent-lab", "revision": rev, "dirty": dirty},
        "contract": {"version": contracts["contract_version"], "digest": contracts["digest"]},
        "license": {"spdx": "Apache-2.0", "files": ["LICENSE", "NOTICE"],
                    "third_party": "docs/reuse-ledger.md"},
        "dependencies": {
            "python": {"lock": "uv.lock", "sha256": sha256(ROOT / "uv.lock"), "python": sys.version.split()[0]},
            "node": {"lock": "pnpm-lock.yaml", "sha256": sha256(ROOT / "pnpm-lock.yaml")},
        },
        "wheels": wheel_info,
        "sdk_cli": {"distributions": ["formal-lab-sdk", "formal-lab-contracts", "formal-lab-model-core (extra: offline)"],
                    "entry_point": "fal = formal_lab_sdk.cli:main", "verification": sdk_check},
        "web": {"file": web_tar.name, "sha256": sha256(web_tar), "bytes": web_tar.stat().st_size},
        "images": images,
        "scenarios": {"model": {"package_id": pkg.package_id, "version": pkg.version, "digest": pkg.digest.value},
                      "scenario_ids": [f"sched-{k}" for k in SCENARIO_CONFIGS]},
        "docs": ["README.md", "docs/getting-started.md", "docs/deployment.md", "docs/contracts/v1.md",
                 "docs/architecture/plugin-integration.md", "docs/architecture/capability-matrix.md",
                 "docs/architecture/observation-semantics.md", "docs/reuse-ledger.md", "docs/handoff/phase1.md"],
        "deployment": {"compose": "deploy/compose/docker-compose.yaml", "helm_chart": "deploy/helm/formal-agent-lab"},
        "duration_s": round(time.time() - t0, 1),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    evidence = ROOT / "docs" / "execution" / "evidence" / "release-manifest.json"
    evidence.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"==> {OUT / 'manifest.json'} ({len(wheel_info)} wheels, {len(images)} images) in {manifest['duration_s']} s")


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
        # only the built project wheels + their third-party deps from the local uv cache (no project sources)
        sh("uv", "pip", "install", "--python", str(py), "--find-links", str(wheels),
           "formal-lab-sdk[offline]", env={"UV_NO_INDEX": "0"})
        installed = sh("uv", "pip", "list", "--python", str(py), "--format", "json")
        names = {p["name"]: p["version"] for p in json.loads(installed)}
        fal = venv / "bin" / "fal"
        commands = []
        for args in (["--help"], ["replay", "verify", str(bundle)], ["replay", "view", str(bundle)]):
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
