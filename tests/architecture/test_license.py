"""The repository is Apache-2.0 (decision D-014): every distribution declares it and ships the same license text."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LICENSE = (ROOT / "LICENSE").read_bytes()
PYPROJECTS = sorted(p for p in ROOT.glob("**/pyproject.toml")
                    if not {".venv", "node_modules", "out", "var"} & set(p.relative_to(ROOT).parts))


def test_root_license_is_apache_2() -> None:
    text = LICENSE.decode()
    assert text.lstrip().startswith("Apache License") and "Version 2.0, January 2004" in text
    assert "Apache License, Version 2.0" in (ROOT / "NOTICE").read_text()


@pytest.mark.parametrize("pyproject", PYPROJECTS, ids=lambda p: str(p.parent.relative_to(ROOT)) or ".")
def test_python_distribution_declares_and_ships_license(pyproject: Path) -> None:
    project = tomllib.loads(pyproject.read_text())["project"]
    assert project.get("license") == "Apache-2.0"
    assert project.get("license-files") == ["LICENSE"]
    assert (pyproject.parent / "LICENSE").read_bytes() == LICENSE, "copy the root LICENSE into the package"


def test_helm_chart_and_npm_metadata() -> None:
    assert (ROOT / "deploy/helm/formal-agent-lab/LICENSE").read_bytes() == LICENSE
    for f in ("package.json", "web/package.json", "packages/contracts-ts/package.json"):
        assert json.loads((ROOT / f).read_text())["license"] == "Apache-2.0", f


def test_images_are_labelled_and_carry_license() -> None:
    for f in ("deploy/docker/python.Dockerfile", "deploy/docker/web.Dockerfile"):
        text = (ROOT / f).read_text()
        assert 'org.opencontainers.image.licenses="Apache-2.0"' in text, f
        assert "COPY LICENSE NOTICE /usr/share/doc/formal-agent-lab/" in text, f


def test_builtin_plugins_declare_license() -> None:
    from formal_lab_runtime.registry import PluginRegistry

    registry = PluginRegistry().discover()
    assert not registry.load_errors
    descriptors = [e.descriptor for e in registry.entries()]
    assert descriptors
    for d in descriptors:
        assert d.license and d.license.startswith("Apache-2.0"), (d.plugin_id, d.license)
