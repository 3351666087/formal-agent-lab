"""A5 release evidence: the release outputs, a clean-directory install online and fully offline, offline replay.

  release        `scripts/release.py --skip-images` → wheels (every workspace member), the web bundle, the local run
                 configurations (compose files, .env.example) and the manifest; its SDK/CLI check installs the built
                 project wheels into a fresh venv (third-party packages from the index / uv cache: the ONLINE install)
                 and replays a bundle with no server;
  offline        a wheelhouse = the built wheels + the third-party closure of formal-lab-sdk[offline] (downloaded once,
                 online); then in an empty directory a fresh venv installs with `--no-index` from that wheelhouse only
                 (the FULLY OFFLINE install) and replays an ordinary-scenario bundle (the order case) with the API
                 unreachable;
  offline stack  the image-based offline bundle (scripts/offline_bundle.py: OCI images + compose) needs 8 GiB above
                 the host's disk reserve; the guard decides — when it refuses, this is recorded BLOCKED, not built.

Writes $FAL_EVIDENCE_DIR/a5-release.json (and the release manifest beside it); reports through check_result.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
OUT = ROOT / "out" / "release"


def sh(*cmd: str, cwd: Path = ROOT, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    if check and res.returncode != 0:
        raise SystemExit(f"$ {' '.join(cmd)}\n{res.stdout[-2000:]}\n{res.stderr[-2000:]}")
    return res


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def members() -> list[str]:
    import tomllib

    return list(tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"])


def order_bundle(dest: Path) -> dict:
    """An ordinary business scenario (order handling, pure backend), run locally and exported as a replay bundle."""
    from formal_lab_example_orders.model import model_package
    from formal_lab_example_orders.scenarios import run
    from formal_lab_runtime.bundles import bundle_from_local

    res = run("normal", backend="pure", seed=0, run_id="run_a5_release_orders")
    dest.write_bytes(bundle_from_local(res, model_package()))
    return {"run_id": res.manifest.run_id, "status": res.status.value, "steps": len(res.steps),
            "events": len(res.events), "sha256": sha256(dest)}


def main() -> int:
    r = CheckResult("p4-a5-release")
    EV.mkdir(parents=True, exist_ok=True)
    env = {"FAL_EVIDENCE_DIR": str(EV.relative_to(ROOT))}
    rel = sh(sys.executable, "scripts/release.py", "--skip-images", "--out", str(OUT),
             "--evidence", str(EV / "release-manifest.json"), env=env)
    manifest = json.loads((OUT / "manifest.json").read_text())
    wheels = [w["file"] for w in manifest["wheels"]]
    expected = members()
    out: dict = {"release": {"stdout_tail": rel.stdout.strip().splitlines()[-1:], "wheels": len(wheels),
                             "has_subprocess_example": any(w.startswith("formal_lab_example_subprocess") for w in wheels),
                             "web": manifest["web"], "local_configs": manifest.get("local_configs", []),
                             "images": manifest.get("images_skipped"), "online_install": manifest["sdk_cli"]["verification"],
                             "license_counts": manifest["license"]["counts"], "revision": manifest["source"]}}
    # ---- fully offline: wheelhouse first (online, once), then an install with --no-index in an empty directory
    work = Path(tempfile.mkdtemp(prefix="a5-release-"))
    house = work / "wheelhouse"
    house.mkdir()
    for w in (OUT / "wheels").glob("*.whl"):
        (house / w.name).write_bytes(w.read_bytes())
    tool = work / "tool"
    sh("uv", "venv", "--python", sys.executable, str(tool))
    sh("uv", "pip", "install", "--python", str(tool / "bin" / "python"), "pip")
    sh(str(tool / "bin" / "python"), "-m", "pip", "download", "--quiet", "--dest", str(house), "--find-links", str(house),
       "--only-binary=:all:", "formal-lab-sdk[offline]")
    bundle = work / "orders.replay.zip"
    scenario = order_bundle(bundle)
    empty = work / "empty"
    empty.mkdir()
    venv = empty / "venv"
    sh("uv", "venv", "--python", sys.executable, str(venv), cwd=empty)
    sh("uv", "pip", "install", "--python", str(venv / "bin" / "python"), "pip", cwd=empty)
    blocked_net = {"PIP_NO_INDEX": "1", "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
                   "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9"}
    inst = sh(str(venv / "bin" / "python"), "-m", "pip", "install", "--no-index", "--find-links", str(house),
              "formal-lab-sdk[offline]", cwd=empty, env=blocked_net, check=False)
    listed = json.loads(sh(str(venv / "bin" / "python"), "-m", "pip", "list", "--format", "json", cwd=empty).stdout)
    fal = venv / "bin" / "fal"
    replays = []
    for args in (["replay", "verify", str(bundle)], ["replay", "view", str(bundle)], ["replay", "step", str(bundle), "1"]):
        res = sh(str(fal), *args, cwd=empty, env={**blocked_net, "FAL_API_URL": "http://127.0.0.1:9/api/v1"},
                 check=False)
        replays.append({"command": "fal " + " ".join(a if not a.startswith(str(work)) else "<bundle>" for a in args),
                        "exit_code": res.returncode, "first_line": (res.stdout.strip().splitlines() or [""])[0][:140]})
    out["offline_install"] = {"wheelhouse": {"files": len(list(house.glob("*.whl"))),
                                             "sha256": sorted(f"{p.name} {sha256(p)[:16]}" for p in house.glob("*.whl"))},
                              "network": "pip --no-index; HTTP(S)_PROXY points at a closed port during install and replay",
                              "install_exit": inst.returncode, "install_tail": (inst.stdout + inst.stderr)[-300:],
                              "installed": {p["name"]: p["version"] for p in listed if p["name"].startswith("formal-lab")},
                              "scenario": scenario, "replay": replays, "prerequisites": [
                                  f"CPython {sys.version.split()[0]} (the wheels are py3-none-any or cp312 builds)",
                                  "pip (bootstrapped into the venv)"]}
    # ---- the image-based offline stack: the disk guard decides
    reserve = float(os.environ.get("FAL_DISK_RESERVE_GIB", "15"))
    need = 8 + reserve  # what the bundle writes (images + tar) and the host reserve kept free after it
    guard = sh(sys.executable, "scripts/disk_guard.py", "--need", f"{need:g}", "--label",
               f"offline bundle (OCI images: 8 GiB + {reserve:g} GiB reserve)", check=False)
    out["offline_stack"] = {"status": "BLOCKED" if guard.returncode else "ALLOWED_NOT_RUN_HERE",
                            "need_gib": need, "guard": (guard.stdout + guard.stderr).strip()[-400:],
                            "note": "scripts/offline_bundle.py --verify builds and saves the four OCI images and starts "
                                    "the stack from the bundle; it is run only when the host keeps the reserve after it"}
    c = r.check
    c("release_outputs", out["release"]["wheels"] >= len(expected) and out["release"]["has_subprocess_example"]
      and out["release"]["web"]["bytes"] > 0 and len(out["release"]["local_configs"]) == 3,
      f"{out['release']['wheels']} wheels for {len(expected)} workspace members, web {out['release']['web']['bytes']} B, "
      f"{len(out['release']['local_configs'])} local configs, manifest {OUT / 'manifest.json'}")
    online = out["release"]["online_install"]
    c("online_clean_install_and_replay", online.get("clean_venv") and all(x["exit_code"] == 0 for x in online["commands"]),
      f"{online.get('project_packages_from')} + {online.get('third_party_from')}: "
      + "; ".join(f"{x['command']} → {x['exit_code']}" for x in online["commands"]))
    off = out["offline_install"]
    c("fully_offline_install_and_replay", off["install_exit"] == 0 and off["installed"].get("formal-lab-sdk")
      and all(x["exit_code"] == 0 for x in off["replay"]) and off["replay"][0]["first_line"].startswith("OK"),
      f"--no-index from {off['wheelhouse']['files']} wheels; " + "; ".join(f"{x['command']} → {x['exit_code']}"
                                                                         for x in off["replay"]))
    c("ordinary_scenario_bundle", off["scenario"]["status"] == "SUCCEEDED", str(off["scenario"]))
    r.note(f"offline stack (OCI images): {out['offline_stack']['status']} — {out['offline_stack']['guard'][-160:]}")
    path = EV / "a5-release.json"
    path.write_text(json.dumps({"deliverable": "phase4A-A5 release", **out,
                                "conclusion": {a["id"]: a["holds"] for a in r.assertions}},
                               indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(path)
    r.evidence(EV / "release-manifest.json")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
