#!/usr/bin/env python3
"""PRISM-games extension check (P2-X01 … P2-X04): real runs of the locally installed binary, verified in-model.

For the example game and a larger one (3 jobs × 3 machines × 4 rounds, for the state-size row of the capability
table) this runs the robust and cooperative reachability queries with strategy export, keeps every raw file PRISM
read or wrote (model, properties, logs, exported strategy and explicit model), and checks the numbers against the
independent solver. Evidence: docs/execution/evidence/phase2/prism-games/. Exit 2 = BLOCKED (not installed).

    scripts/in-vm.sh 'uv run --frozen python scripts/prism_games_check.py'
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

from formal_lab_solver_prism import (
    ASSUMPTIONS,
    CAPABILITIES,
    EXAMPLE,
    GAME_SCHEMA,
    PINNED,
    PROFILE,
    RESULT_SCHEMA,
    AllocationGame,
    Machine,
    Unavailable,
    check,
    version,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase2") / "prism-games"
LARGER = AllocationGame(game_id="three-jobs-three-machines", jobs=["a", "b", "c"],
                        machines=[Machine(id="m1", success=0.9), Machine(id="m2", success=0.7),
                                  Machine(id="m3", success=0.5)], rounds=4, slowdown=0.4,
                        description="state-size probe for the capability table")


def main() -> int:
    try:
        backend = version()
    except Unavailable as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "backend": backend,
               "pinned": PINNED, "profile": PROFILE, "game_schema": GAME_SCHEMA, "result_schema": RESULT_SCHEMA,
               "assumptions": ASSUMPTIONS, "distribution": "not redistributed: user-installed binary, separate process",
               "games": []}
    for game in (EXAMPLE, LARGER):
        work = OUT / game.game_id
        shutil.rmtree(work, ignore_errors=True)
        rec = check(game, keep=work)
        for f in ("model.srew", "model.trew"):  # empty reward exports
            (work / f).unlink(missing_ok=True)
        for i, p in enumerate(rec.properties, start=1):
            (work / f"prism-prop{i}.log").write_text(p.log)
        (work / "result.json").write_text(rec.model_dump_json(indent=2, exclude={"properties": {"__all__": {"log"}}}))
        summary["games"].append({
            "game_id": game.game_id, "verified": rec.verified, "size": rec.size, "reference_states": rec.reference_states,
            "properties": [{k: p.model_dump()[k] for k in ("property", "value", "reference_value", "agrees", "method",
                                                              "iterations", "seconds")} for p in rec.properties],
            "strategy_value": rec.strategy_value, "strategy_decisions": len(rec.strategy), "seconds": rec.seconds,
            "files": sorted(str(p.relative_to(ROOT)) for p in work.iterdir())})
        print(f"{game.game_id}: states {rec.size['states']} (reference {rec.reference_states}), "
              f"robust {rec.properties[0].value:.6f} / cooperative {rec.properties[1].value:.6f}, "
              f"strategy value {rec.strategy_value:.6f}, verified={rec.verified}")
    summary["capabilities"] = [dict(c, measured=None) for c in CAPABILITIES]
    summary["capabilities"][0]["measured"] = {g["game_id"]: g["size"] for g in summary["games"]}
    summary["ok"] = all(g["verified"] for g in summary["games"])
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    write_doc(summary)
    return 0 if summary["ok"] else 1


def write_doc(summary: dict) -> None:
    """docs/architecture/probabilistic-extension.md: the extension's capability table with the measured sizes."""
    b = summary["backend"]
    lines = ["# 概率扩展：PRISM-games（深化轨道）", "",
             f"由 `scripts/prism_games_check.py` 于 {summary['checked_at']} 生成，勿手工编辑。决策 D-023；安装见 "
             "[local-development.md](../local-development.md) 第 9 节。确定性 profile `deterministic_finite_v1` 本身仍不支持随机"
             "转移（[能力矩阵](capability-matrix.md) 的 probabilistic_effects 行）；本扩展以独立的类型化载荷与 profile "
             f"`{summary['profile']}` 表达随机博弈。", "",
             f"- 后端：{b['name']} {b['version']}（{b['arch']}，{b['java']}），许可 {b['license']}，不随平台分发；"
             f"固定发行 {summary['pinned']['source']}",
             f"- 载荷 `{summary['game_schema']}` → 结果 `{summary['result_schema']}`", "", "## 假设", ""]
    lines += [f"- {a}" for a in summary["assumptions"]]
    lines += ["", "## 能力与核对", "", "| 能力 | 查询 | 状态 | 核对方式 |", "|---|---|---|---|"]
    lines += [f"| {c['feature']} | `{c['query']}` | {c['status']} | {c['check']} |" for c in summary["capabilities"]]
    lines += ["", "## 实测规模与误差", "", "| 博弈 | 状态 / 选择 / 转移 | 参照状态数 | 鲁棒值（PRISM / 参照） | 合作值 | 导出策略的值 | "
              "耗时 s | 核对 |", "|---|---|---|---|---|---|---|---|"]
    for g in summary["games"]:
        rob, coop = g["properties"]
        sz = g["size"]
        lines.append(f"| {g['game_id']} | {sz['states']} / {sz['choices']} / {sz['transitions']} | {g['reference_states']} | "
                     f"{rob['value']:.6f} / {rob['reference_value']:.6f} | {coop['value']:.6f} | {g['strategy_value']:.6f} | "
                     f"{g['seconds']} | {'通过' if g['verified'] else '未通过'} |")
    worst = max(abs(p["value"] - p["reference_value"]) for g in summary["games"] for p in g["properties"])
    lines += ["", f"误差：判定容差 1e-6（PRISM 值迭代的默认终止容差）；实测 PRISM 数值与独立求解器（逐轮倒推）的最大差 "
              f"{worst:.1e}（博弈无环）。原始模型、性质、日志、导出策略与显式模型：`docs/execution/evidence/phase2/prism-games/`。", ""]
    (ROOT / "docs" / "architecture" / "probabilistic-extension.md").write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
