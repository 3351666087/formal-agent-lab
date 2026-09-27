#!/usr/bin/env python3
"""Dependency and license inventory (P2-006 / P2-109).

Python: every distribution installed in the project environment, with its version and license as declared in its
metadata (License-Expression, else the License field, else the trove classifiers), and whether it belongs to the
runtime closure (`uv export --no-dev`) or only to development / test tooling. Node: the web app's production
dependencies from `pnpm licenses list --prod`. Entries whose license needs attention (copyleft, or not declared)
are listed separately with where they are used.

Writes docs/execution/evidence/phase2/licenses.json and docs/licenses.md.

    scripts/in-vm.sh 'uv run --frozen python scripts/license_inventory.py'
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs/execution/evidence/phase2/licenses.json"
OUT_MD = ROOT / "docs/licenses.md"
ATTENTION = re.compile(r"\b(A?GPL|LGPL|MPL|EPL|CDDL|SSPL|EUPL)\b", re.I)
PROJECT = re.compile(r"^(formal-lab-|formal-agent-lab|fal-example-)")
NOTES = {  # how the entries that need attention are used (reviewed by hand)
    "psycopg": "LGPL-3.0: used unmodified as a separately installed library (PostgreSQL driver of the platform "
               "API / worker); not vendored or statically linked; replaceable by the user",
    "psycopg-binary": "LGPL-3.0: binary wheel of psycopg, same arrangement (installed, not vendored)",
    "certifi": "MPL-2.0 (file-level copyleft): the CA bundle used unmodified via httpx; no files changed",
}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def license_of(dist: metadata.Distribution) -> str:
    md = dist.metadata
    expr = md.get("License-Expression")
    if expr:
        return expr.strip()
    lic = (md.get("License") or "").strip()
    if lic and lic.upper() != "UNKNOWN" and len(lic) < 80 and "\n" not in lic:
        return lic
    classifiers = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
    if classifiers:
        return " OR ".join(sorted(set(classifiers)))
    if lic:
        return lic.splitlines()[0][:80] + (" …" if len(lic) > 80 else "")
    for f in dist.files or []:  # metadata silent: read the license file the distribution ships
        if "LICENSE" in f.name.upper() or "COPYING" in f.name.upper():
            try:
                head = f.locate().read_text(errors="replace")[:400]
            except OSError:
                continue
            for pattern, spdx in (("Apache License", "Apache-2.0"), ("MIT License", "MIT"),
                                  ("Permission is hereby granted, free of charge", "MIT"),
                                  ("Redistribution and use in source and binary forms", "BSD")):
                if pattern in head:
                    return f"{spdx} (from the bundled {f.name})"
    return "UNDECLARED"


def runtime_closure() -> set[str]:
    res = subprocess.run(["uv", "export", "--frozen", "--no-dev", "--all-packages", "--format", "requirements-txt",
                          "--no-hashes"], cwd=ROOT, capture_output=True, text=True, check=True)
    names = set()
    for line in res.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-e", ".")) and "==" in line:
            names.add(norm(line.split("==")[0].split("[")[0]))
    return names


def node() -> list[dict]:
    res = subprocess.run(["pnpm", "--dir", "web", "licenses", "list", "--prod", "--json"], cwd=ROOT,
                         capture_output=True, text=True)
    if res.returncode != 0:
        return [{"name": "(pnpm licenses failed)", "version": "", "license": res.stderr.strip()[:200]}]
    data = json.loads(res.stdout or "{}")
    out = []
    for lic, pkgs in data.items():
        for p in pkgs:
            for v in p.get("versions") or [p.get("version", "")]:
                out.append({"name": p["name"], "version": v, "license": lic, "scope": "web (production)"})
    return sorted(out, key=lambda x: x["name"])


def main() -> int:
    runtime = runtime_closure()
    py = []
    for dist in sorted(metadata.distributions(), key=lambda d: norm(d.metadata["Name"])):
        name = dist.metadata["Name"]
        if PROJECT.match(norm(name)):
            continue
        py.append({"name": name, "version": dist.version, "license": license_of(dist),
                   "scope": "runtime" if norm(name) in runtime else "development / test"})
    js = node()
    everything = [*py, *js]
    attention = [{**e, "note": NOTES.get(e["name"], "to be reviewed")} for e in everything
                 if e["license"] == "UNDECLARED" or ATTENTION.search(e["license"])]
    by_license: dict[str, int] = {}
    for e in everything:
        by_license[e["license"]] = by_license.get(e["license"], 0) + 1
    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "project_license": "Apache-2.0", "python": py, "node": js,
              "counts": {"python_runtime": sum(1 for e in py if e["scope"] == "runtime"),
                         "python_development": sum(1 for e in py if e["scope"] != "runtime"), "node": len(js)},
              "by_license": dict(sorted(by_license.items(), key=lambda kv: -kv[1])), "attention": attention}
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    lines = ["# 第三方依赖与许可证清单", "",
             f"由 `scripts/license_inventory.py` 生成（{report['generated_at']}）：Python 环境中实际安装的发行包（区分运行时闭包与开发/测试工具）与 Web 生产依赖。"
             "许可证取自包元数据；逐项清单见 `docs/execution/evidence/phase2/licenses.json`。项目本身：Apache-2.0（`LICENSE`、`NOTICE`）。"
             "上游复用与调用位置见 [reuse-ledger.md](reuse-ledger.md)。", "",
             f"- Python 运行时依赖 {report['counts']['python_runtime']} 个，开发/测试工具 {report['counts']['python_development']} 个；"
             f"Web 生产依赖 {report['counts']['node']} 个。", "", "## 按许可证", "", "| 许可证 | 包数 |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in report["by_license"].items()]
    lines += ["", "## 需要留意的条目（copyleft 或未声明）", ""]
    if attention:
        lines += ["| 包 | 版本 | 许可证 | 范围 | 使用方式 |", "|---|---|---|---|---|"]
        lines += [f"| {e['name']} | {e['version']} | {e['license']} | {e['scope']} | {e['note']} |" for e in attention]
    else:
        lines.append("无。")
    lines += ["", "## Python 运行时依赖", "", "| 包 | 版本 | 许可证 |", "|---|---|---|"]
    lines += [f"| {e['name']} | {e['version']} | {e['license']} |" for e in py if e["scope"] == "runtime"]
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({**report["counts"], "attention": [(e["name"], e["license"], e["scope"]) for e in attention]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
