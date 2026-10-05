"""Phase 4B (B3): the domain evidence helper — a conclusion's offline_readable comes from reading the written file
back; present, passed and produced-at-the-current-revision are separate verdicts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("evidence_io", ROOT / "scripts" / "evidence_io.py")
evidence_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence_io)
CLEAN = {"commit": "abc123", "dirty": False}


def test_write_reads_back_and_records_the_revision(tmp_path):
    out = tmp_path / "d.json"
    ev = {"conclusion": {"works": True}}
    assert evidence_io.write(out, ev)
    back = json.loads(out.read_text())
    assert back["conclusion"] == {"works": True, "offline_readable": True} and "commit" in back["produced_at"]


def test_blocked_evidence_gets_no_conclusion(tmp_path):
    out = tmp_path / "d.json"
    evidence_io.write(out, {"status": "BLOCKED", "reason": "no toolchain"})
    assert "conclusion" not in json.loads(out.read_text())  # a lone read-back flag never looks like a pass


def test_assess_keeps_present_passed_and_current_apart(tmp_path):
    def put(name, doc):
        (tmp_path / name).write_text(json.dumps(doc))
        return evidence_io.assess(tmp_path / name, CLEAN)

    missing = evidence_io.assess(tmp_path / "none.json", CLEAN)
    assert (missing["present"], missing["passed"], missing["current_revision"]) == (False, False, False)
    old = put("old.json", {"conclusion": {"a": True}, "produced_at": {"commit": "zzz999", "dirty": False}})
    assert (old["present"], old["passed"], old["current_revision"]) == (True, True, False)
    failed = put("failed.json", {"conclusion": {"a": True, "b": False}, "produced_at": CLEAN})
    assert (failed["passed"], failed["current_revision"], failed["failed"]) == (False, True, ["b"])
    blocked = put("blocked.json", {"status": "BLOCKED", "produced_at": CLEAN})
    assert not blocked["passed"]
    dirty = put("dirty.json", {"conclusion": {"a": True}, "produced_at": {"commit": "abc123", "dirty": True}})
    assert dirty["passed"] and not dirty["current_revision"]
    ok = put("ok.json", {"conclusion": {"a": True}, "produced_at": CLEAN})
    assert ok["passed"] and ok["current_revision"]
