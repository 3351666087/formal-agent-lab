"""disk_guard keeps the host reserve on the host: the VM's Docker disk (a 30 GiB filesystem of its own) only needs what
the step writes plus a margin — one need for both made every 8 / 12 GiB check unrunnable on it."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import disk_guard  # noqa: E402
from check_runner import DOCKER_MARGIN_GIB, RESERVE_GIB  # noqa: E402


@pytest.fixture
def free(monkeypatch):
    values: dict[str, float] = {}
    monkeypatch.setattr(disk_guard, "free_gib", lambda p: values["docker" if str(p) == "/var/lib/docker" else "host"])
    return values


def guard(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["disk_guard.py", *args])
    return disk_guard.main()


def test_the_host_reserve_does_not_apply_to_the_docker_disk(monkeypatch, free):
    free.update(host=28.7, docker=21.1)  # 2026-10-03: the Mac had room, the VM disk is 30 GiB in all
    heavy = 12
    assert guard(monkeypatch, "--need", str(heavy + RESERVE_GIB), "--docker-need", str(heavy + DOCKER_MARGIN_GIB)) == 0
    assert guard(monkeypatch, "--need", str(heavy + RESERVE_GIB)) == 1  # the old single need: never satisfiable


def test_each_filesystem_is_held_to_its_own_need(monkeypatch, free, capsys):
    free.update(host=20.0, docker=40.0)
    assert guard(monkeypatch, "--need", "27", "--docker-need", "14") == 1
    assert "needs host 27 GiB, docker data 14 GiB" in capsys.readouterr().err
    free.update(host=40.0, docker=10.0)
    assert guard(monkeypatch, "--need", "27", "--docker-need", "14") == 1
    free.update(host=27.0, docker=14.0)
    assert guard(monkeypatch, "--need", "27", "--docker-need", "14") == 0
