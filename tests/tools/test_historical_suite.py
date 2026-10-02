"""The historical phase-2 suite under the shared runner (phase 4A): its disk-heavy checks keep their declared size, so
strict acceptance asks the disk guard for size + reserve before starting them (the 2026-09-28 full-disk incident)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_runner import RESERVE_GIB, load_suite  # noqa: E402


def test_phase2_heavy_checks_keep_their_disk_size():
    suite = load_suite("phase2")
    heavy = {c.id: c.heavy_gib for c in suite.checks if c.heavy_gib}
    assert heavy == {"compose-smoke": 8, "orders-compose": 4, "offline-install": 12, "release-manifest": 8,
                     "kind-install-upgrade": 12}
    assert RESERVE_GIB >= 15
    assert all(c.heavy_gib == 0 for c in suite.checks if c.id not in heavy)
