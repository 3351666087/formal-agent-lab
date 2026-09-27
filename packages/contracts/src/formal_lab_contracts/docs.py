"""Render docs/contracts/v2.md (and the frozen v1.md) from the contract source.

    python -m formal_lab_contracts.docs --out docs/contracts/v2.md --v1-out docs/contracts/v1.md
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import errors, execution, governance, kernel, objects
from .common import CONTRACT_VERSION
from .schema_export import FROZEN_OBJECTS, SUPPORTING, V2_OBJECTS, build_schemas, contract_digest

OVERVIEW = """\
# 契约 formal-lab-contracts/v2

> 本文件由 `python -m formal_lab_contracts.docs` 生成（`make contracts`），请勿手工编辑。
> 唯一来源：`packages/contracts/src/formal_lab_contracts/`（Pydantic v2）。v1 冻结于 `formal_lab_contracts.v1`，文档见 [v1.md](v1.md)。

| 项 | 值 |
|---|---|
| 契约版本 | `{version}`（同时可读 `formal-lab-contracts/v1`） |
| 契约摘要 | `sha256:{digest}` |
| 摘要方法 | {method} |
| 产物 | `contracts/v2/`（每个对象一份 schema、校验视图 `bundle.schema.json`、输出视图 `bundle.serialization.schema.json`、`objects.json`、`DIGEST.json`）；`contracts/v1/` 保持阶段一原样；TypeScript：`packages/contracts-ts/src/generated.ts`（v2）与 `generated.v1.ts` |
| 生成命令 | `make contracts` |
| 漂移检查 | `make contracts-check`（v1 与 v2 重新生成后 `git diff --exit-code`） |
| 合同测试 | `tests/contracts/`（v1 与 v2 样例、v1→v2 升级）、`tests/compat/`（阶段一回放包与对象）、`packages/contracts-ts/test/` |

## 版本关系与兼容规则

- **为何发布 v2**：v1 的 `ModelPackage.ir` 强制为中性 IR、`PluginInterface` 为封闭枚举。第二个语义驱动（非 IR 载荷）与新的插件接口
  （`SEMANTIC_DRIVER`、`PROBE`）无法在 v1 内兼容表达（封闭枚举与必填 `ir` 会让 v1 消费者拒绝新数据），因此并行发布 v2，并交付 v1 适配器（决策 D-015）。
- **v2 相对 v1**：所有 v1 对象名、字段名与语义不变；`ModelPackage.ir` 改为类型化载荷 `payload`（`fal-ir` | `namespaced`），`ir` 保留为只读访问器；
  新增字段均可选并有默认值；`PluginInterface`、`QueryKind`、`EventType` 扩展了取值。
- **读取 v1**：`formal_lab_contracts.compat.upgrade(kind, json)` 先用冻结的 v1 契约校验，再映射到 v2；数据库、API、回放包与插件目录统一经过它。
  v1 模型的 v2 规范形式逐字节相同，摘要不变（v2 新增的 IR 字段在默认值时不进入规范形式）。
- **插件**：注册表接受 `interface_version` 1 与 2；v1 插件（PLANNER/VERIFIER/ENVIRONMENT/EVALUATOR/MODEL_FRONTEND）照常工作，收到的是 v2 对象；
  `SEMANTIC_DRIVER`、`PROBE` 只能以 v2 声明。
- **回放包**：写出 `formal-lab/replay-bundle@2`；读取 `@1` 时用冻结 v1 读取器校验摘要后升级（`info.upgraded_from`）。
- 扩展仍通过带命名空间、版本与 schema 标识的 `extensions` 槽；不兼容修改发布新的契约版本。

## 结果语义

| query_kind | 语义 | 可能结论 |
|---|---|---|
| `GOAL_REACHABILITY` | `EXISTS_PATH`：是否存在 ≤k 步到达目标的路径 | `WITNESS` / `NO_WITNESS_WITHIN_BOUND`（有界结论）/ `UNKNOWN` / `UNSUPPORTED` |
| `INVARIANT_VIOLATION` | `ALL_PATHS`：所有 ≤k 步路径是否满足不变量 | `WITNESS`（反例）/ `NO_WITNESS_WITHIN_BOUND` / `UNKNOWN` / `UNSUPPORTED` |
| `ACTION_PRECONDITION` | `SINGLE_STEP`：给定（可含未知项的）状态下动作是否适用；未知项取遍所有允许补全 | `APPLICABLE`（所有补全均适用）/ `INAPPLICABLE`（均不适用）/ `UNKNOWN`（补全结论不同，附 `observation_request` 与两侧补全）/ `UNSUPPORTED` |
| `OPTIMIZE_OBJECTIVE` | `OPTIMAL_PATH`：horizon 内到达目标、按字典序最小化目标的路径 | `OPTIMAL`（每层最优已证明）/ `FEASIBLE`（找到方案，最优性未证明，`optimization.levels[].proven_lower/upper` 给出已证实范围）/ `NO_PLAN_WITHIN_HORIZON` / `UNKNOWN` / `UNSUPPORTED` |
| `ROBUST_SEQUENCE` | `ALL_COMPLETIONS`：固定动作序列对未知项的每个补全都可执行（可选：并到达目标） | `ROBUST` / `NOT_ROBUST`（附反例补全与失败位置）/ `UNKNOWN` / `UNSUPPORTED` |

所有检查结论 `scope = MODEL_INTERNAL`；有界结论永远携带 `bound`。`ROBUST_SEQUENCE` 是开环序列的稳健性检查，不是可随观测分支的策略综合（后者返回 `UNSUPPORTED`）。
基于 last-known 或模型初值的规划标记为 `ASSUMPTION_BASED`，其假设集合（`AssumptionSet`：每个位置的 `KNOWN / STALE / UNKNOWN / ASSUMED_INITIAL`）随结果保存。

## 执行阶段

每个逻辑步按 `ExecutionStage` 顺序执行：`TURN → OBSERVE → PROPOSE → CHECK → EXECUTE → (RECONCILE) → PROBE → COMPARE → TERMINATE`，
每段写出 `StageRecord`（输入/输出摘要、重试语义、错误与证据）。操作状态机：`PREPARED → DISPATCHED → COMPLETED | FAILED | OUTCOME_UNKNOWN → RECONCILED`。

## 统一错误

{errors}

## 对象（阶段一命名的对象，v2 内容）
"""


def _type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema:
        return " \\| ".join(_type(s) for s in schema["anyOf"])
    if "oneOf" in schema:
        return " \\| ".join(_type(s) for s in schema["oneOf"])
    if "const" in schema:
        return f"`{schema['const']}`"
    if "enum" in schema:
        return " \\| ".join(f"`{v}`" for v in schema["enum"])
    t = schema.get("type", "any")
    if t == "array":
        return f"{_type(schema.get('items', {}))}[]"
    if t == "object" and "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
        return f"map<string, {_type(schema['additionalProperties'])}>"
    return str(t)


def _fields(model) -> str:
    schema = model.model_json_schema(mode="validation")
    required = set(schema.get("required", []))
    rows = ["| 字段 | 类型 | 必填 | 说明 |", "|---|---|---|---|"]
    for name, prop in schema.get("properties", {}).items():
        desc = (prop.get("description") or "").replace("|", "\\|").replace("\n", " ")
        rows.append(f"| `{name}` | {_type(prop)} | {'是' if name in required else ''} | {desc} |")
    return "\n".join(rows)


def _doc(model) -> str:
    return " ".join((model.__doc__ or "").strip().split()) if model.__doc__ else ""


def render() -> str:
    files = build_schemas()
    digest = contract_digest(files)
    err_rows = ["| 代码 | 可重试 | HTTP |", "|---|---|---|"] + [
        f"| `{c.value}` | {'是' if c in errors.RETRYABLE_CODES else '否'} | {errors.HTTP_STATUS[c]} |" for c in errors.ErrorCode]
    parts = [OVERVIEW.format(version=CONTRACT_VERSION, digest=digest["digest"], method=digest["method"],
                             errors="\n".join(err_rows))]
    for model in FROZEN_OBJECTS:
        parts.append(f"### {model.__name__}\n\n{_doc(model)}\n\n{_fields(model)}\n")
    parts.append("## 阶段二新增对象\n")
    for model in V2_OBJECTS:
        parts.append(f"### {model.__name__}\n\n{_doc(model)}\n\n{_fields(model)}\n")
    parts.append("## 支撑类型\n")
    for model in SUPPORTING:
        parts.append(f"### {model.__name__}\n\n{_fields(model)}\n")
    parts.append("## 枚举\n")
    for enum in (objects.RunStatus, objects.EventType, objects.OutcomeStatus, objects.ComparisonVerdict,
                 objects.ProposalSourceKind, objects.MetricStatus, objects.Aggregation, objects.MetricDirection,
                 objects.PluginInterface, objects.RetrySemantics, objects.QueryKind, kernel.TurnMode,
                 kernel.ObservationTiming, kernel.ConflictPolicy, kernel.NoActionPolicy, kernel.ActorGoalMode,
                 kernel.TerminationReason, kernel.OptimizationStatus, kernel.Provenance, kernel.PlanBasis,
                 kernel.RobustnessVerdict, kernel.ExecutionStage, kernel.StageStatus, kernel.OperationState,
                 kernel.RuleOutcome, execution.TaskStatus, execution.PlanTrigger, execution.RecoveryMode,
                 execution.SessionStatus, governance.RuleResult):
        parts.append(f"- **{enum.__name__}**：" + "、".join(f"`{e.value}`" for e in enum))
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("docs/contracts/v2.md"))
    parser.add_argument("--v1-out", type=Path, default=None, help="also render the frozen v1 document here")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(), encoding="utf-8")
    print(f"wrote {args.out}")
    if args.v1_out is not None:
        from .v1 import docs as v1docs

        args.v1_out.write_text(v1docs.render(), encoding="utf-8")
        print(f"wrote {args.v1_out}")


if __name__ == "__main__":
    main()
