#!/usr/bin/env python3
"""Tick a task item in docs/execution/phase-1.md and attach evidence.

Usage:
  scripts/tick.py P1-001 "evidence: docs/execution/evidence/P1-001-environment.md"
  scripts/tick.py --block P1-113 "BLOCKED：原因 / 已完成部分 / 解除条件"
  scripts/tick.py --note P1-074 "NOT_RUN: ..."   (annotate without ticking)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TASKBOOK = Path(__file__).resolve().parent.parent / "docs" / "execution" / "phase-1.md"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("evidence")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--block", action="store_true", help="annotate as blocked, keep unticked")
    mode.add_argument("--note", action="store_true", help="annotate only, keep current state")
    args = parser.parse_args()

    lines = TASKBOOK.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf"^- \[( |x)\] \*\*{re.escape(args.task_id)}\*\*")
    for i, line in enumerate(lines):
        if not pattern.match(line):
            continue
        if not (args.block or args.note):
            lines[i] = line.replace("- [ ]", "- [x]", 1)
        # drop previous annotations of this item, then add the new one
        j = i + 1
        while j < len(lines) and lines[j].startswith("  - "):
            j += 1
        prefix = "BLOCKED" if args.block else ("备注" if args.note else "证据")
        text = args.evidence if args.evidence.startswith(("BLOCKED", "NOT_RUN")) else f"{prefix}：{args.evidence}"
        lines[i + 1 : j] = [f"  - {text}"]
        TASKBOOK.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{args.task_id}: {'blocked' if args.block else 'noted' if args.note else 'ticked'}")
        return
    raise SystemExit(f"task {args.task_id} not found in {TASKBOOK}")


if __name__ == "__main__":
    main()
