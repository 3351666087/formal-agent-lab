#!/usr/bin/env python3
"""Tick a task item in the phase task book (docs/execution/phase-<n>.md, chosen by the id prefix) with evidence.

Usage:
  scripts/tick.py P2-004 "make doctor → docs/execution/evidence/phase2/doctor.json" --files scripts/doctor.py
  scripts/tick.py --status BLOCKED P2-107 "原因 / 已完成部分 / 解除条件"
  scripts/tick.py --status NOT_SELECTED P2-X01 "reason"      (annotate without ticking)
  scripts/tick.py --note P2-074 "partial progress"             (annotate, keep state)
  scripts/tick.py --untick P2-010 "evidence incomplete"

Every tick records the evidence text and, with --files, the implementation files it is bound to (P2-007).
Statuses: PASS (ticked), FAIL, BLOCKED, NOT_RUN, NOT_SELECTED (annotations; the item stays unticked).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUSES = ("FAIL", "BLOCKED", "NOT_RUN", "NOT_SELECTED")


def taskbook(task_id: str) -> Path:
    m = re.match(r"^P(\d+)-", task_id)
    if not m:
        raise SystemExit(f"unrecognised task id {task_id!r}")
    return ROOT / "docs" / "execution" / f"phase-{m.group(1)}.md"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("evidence")
    parser.add_argument("--files", default="", help="comma-separated implementation files bound to this tick")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", choices=STATUSES, help="annotate with a non-PASS status, keep unticked")
    mode.add_argument("--block", action="store_true", help="alias of --status BLOCKED")
    mode.add_argument("--note", action="store_true", help="annotate only, keep current state")
    mode.add_argument("--untick", action="store_true", help="revert to unticked (evidence incomplete)")
    args = parser.parse_args()
    status = "BLOCKED" if args.block else args.status

    book = taskbook(args.task_id)
    lines = book.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf"^- \[( |x)\] \*\*{re.escape(args.task_id)}\*\*")
    for i, line in enumerate(lines):
        if not pattern.match(line):
            continue
        if args.untick or status:
            lines[i] = line.replace("- [x]", "- [ ]", 1)
        elif not args.note:
            lines[i] = line.replace("- [ ]", "- [x]", 1)
        # drop previous annotations of this item, then add the new one
        j = i + 1
        while j < len(lines) and lines[j].startswith("  - "):
            j += 1
        if status:
            text = f"{status}：{args.evidence}"
        elif args.evidence.startswith(("BLOCKED", "NOT_RUN", "NOT_SELECTED", "FAIL")):
            text = args.evidence
        else:
            text = f"{'进展' if (args.note or args.untick) else '证据'}：{args.evidence}"
        new = [f"  - {text}"]
        if args.files:
            new.append("  - 实现：" + "、".join(f"`{f.strip()}`" for f in args.files.split(",") if f.strip()))
        lines[i + 1 : j] = new
        book.write_text("\n".join(lines) + "\n", encoding="utf-8")
        state = status.lower() if status else "noted" if args.note else "unticked" if args.untick else "ticked"
        print(f"{args.task_id}: {state}")
        return
    raise SystemExit(f"task {args.task_id} not found in {book}")


if __name__ == "__main__":
    main()
