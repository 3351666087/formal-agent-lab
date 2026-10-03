"""Regression suites never overwrite history (phase 4A): every script that the phase-2 / phase-3 suites run writes its
evidence under $FAL_EVIDENCE_DIR (strict acceptance points it at evidence/phase4/regression/<suite>), defaulting to
the historical directory only when run on its own."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_runner import load_suite  # noqa: E402

HISTORY = re.compile(r"""evidence["'/ ]+(?:/\s*)?["']?(?:phase[23]|helm)\b""")
CONSTANT = re.compile(r"^\s*[A-Z_][A-Z0-9_]*\s*=")  # where these scripts define their output paths (Python and sh)


def _scripts_run_by(suite: str) -> set[Path]:
    out = set()
    for c in load_suite(suite).checks:
        for m in re.finditer(r"scripts/[A-Za-z0-9_\-]+\.(?:py|sh)", c.command):
            out.add(ROOT / m.group(0))
    return out


def test_regression_scripts_write_under_fal_evidence_dir():
    offenders = []
    for path in sorted(_scripts_run_by("phase2") | _scripts_run_by("phase3")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if CONSTANT.match(code) and HISTORY.search(code) and not re.search(r"FAL_\w*EVIDENCE_DIR", code):
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:120]}")
    assert not offenders, "\n".join(offenders)


def test_helm_checks_follow_the_regression_directory():
    """The kind install / upgrade check (phase 2) writes beside the regression's other evidence, not to evidence/helm."""
    probe = ("import sys; sys.path.insert(0, 'scripts'); from check_runner import load_suite; "
             "c = next(c for c in load_suite('phase2').checks if c.id == 'kind-install-upgrade'); print(c.command, c.evidence)")
    env = {**os.environ, "FAL_EVIDENCE_DIR": "docs/execution/evidence/phase4/regression/phase2"}
    out = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, env=env, capture_output=True, text=True, check=True).stdout
    assert out.count("FAL_HELM_EVIDENCE_DIR=docs/execution/evidence/phase4/regression/phase2/helm") == 2
    assert "evidence/helm" not in out.replace("phase2/helm", "")
