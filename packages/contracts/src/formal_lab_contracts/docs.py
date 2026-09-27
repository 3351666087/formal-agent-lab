"""Render docs/contracts/v1.md from the contract source (overview + generated field reference).

    python -m formal_lab_contracts.docs --out docs/contracts/v1.md
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import errors, objects
from .common import CONTRACT_VERSION
from .schema_export import FROZEN_OBJECTS, SUPPORTING, build_schemas, contract_digest

OVERVIEW = """\
# 契约 formal-lab-contracts/v1

> 本文件由 `python -m formal_lab_contracts.docs` 生成（`make contracts`），请勿手工编辑。
> 唯一来源：`packages/contracts/src/formal_lab_contracts/`（Pydantic v2）。

| 项 | 值 |
|---|---|
| 契约版本 | `{version}` |
| 契约摘要 | `sha256:{digest}` |
| 摘要方法 | {method} |
| 产物 | `contracts/v1/schemas/*.schema.json`（每个对象一份）、`contracts/v1/bundle.schema.json`（校验视图）、`contracts/v1/bundle.serialization.schema.json`（输出视图）、`contracts/v1/objects.json`、`contracts/v1/DIGEST.json`；TypeScript：`packages/contracts-ts/src/generated.ts` |
| 生成命令 | `make contracts`（= `python -m formal_lab_contracts.schema_export --out contracts/v1` + `pnpm --filter @formal-lab/contracts run generate` + 本文件） |
| 漂移检查 | `make contracts-check` 与 CI（重新生成后 `git diff --exit-code`） |
| 合同测试 | `tests/contracts/`（Pydantic + JSON Schema）与 `packages/contracts-ts/test/`（ajv + tsc），共享 `tests/contracts/fixtures/` |

## 版本与扩展规则

- 本表所列对象名称与语义固定。新增能力通过**带命名空间、版本与 schema 标识**的 `extensions` 槽补充：
  键为反向 DNS 命名空间（`formal-lab.core.*` 保留），值为 `{{version, schema_id, data}}`。核心对象拒绝未知字段（`extra=forbid`）。
- 不兼容修改必须发布新的契约版本（`formal-lab-contracts/v2`），并保留 v1 读取路径；回放包与 RunManifest 都携带契约版本。
- 插件描述符声明 `interface_version`（当前为 `1`）；注册表拒绝不匹配的插件（`VERSION_MISMATCH`）。

## 结果语义

| query_kind | 语义 | 可能结论 |
|---|---|---|
| `GOAL_REACHABILITY` | `EXISTS_PATH`：是否存在 ≤k 步到达目标的路径 | `WITNESS`（最短见证）/ `NO_WITNESS_WITHIN_BOUND`（≤k 步不存在，**有界结论**）/ `UNKNOWN` / `UNSUPPORTED` |
| `INVARIANT_VIOLATION` | `ALL_PATHS`：所有 ≤k 步路径是否满足不变量（以寻找违反路径的方式回答） | `WITNESS`（反例）/ `NO_WITNESS_WITHIN_BOUND`（≤k 步内全部满足）/ `UNKNOWN` / `UNSUPPORTED` |
| `ACTION_PRECONDITION` | `SINGLE_STEP`：给定（可含未知项的）状态下动作是否适用 | `APPLICABLE` / `INAPPLICABLE` / `UNKNOWN`（取决于未知值，证据不足）/ `UNSUPPORTED` |

所有检查结论 `scope = MODEL_INTERNAL`（关于模型，而非真实系统）。`NO_WITNESS_WITHIN_BOUND` 永远携带 `bound`。
超时、求解器未知与未支持分别用 `UNKNOWN`（`stats.reason_unknown`）与 `UNSUPPORTED`（`unsupported.feature/reason/extension_point`）表达，不以异常表达。

## 统一错误

{errors}

## 冻结对象
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


def render() -> str:
    files = build_schemas()
    digest = contract_digest(files)
    err_rows = ["| 代码 | 可重试 | HTTP |", "|---|---|---|"] + [
        f"| `{c.value}` | {'是' if c in errors.RETRYABLE_CODES else '否'} | {errors.HTTP_STATUS[c]} |" for c in errors.ErrorCode]
    parts = [OVERVIEW.format(version=CONTRACT_VERSION, digest=digest["digest"], method=digest["method"],
                             errors="\n".join(err_rows))]
    for model in FROZEN_OBJECTS:
        doc = (model.__doc__ or "").strip().splitlines()[0] if model.__doc__ else ""
        parts.append(f"### {model.__name__}\n\n{doc}\n\n{_fields(model)}\n")
    parts.append("## 支撑类型\n")
    for model in SUPPORTING:
        parts.append(f"### {model.__name__}\n\n{_fields(model)}\n")
    parts.append("## 枚举\n")
    for enum in (objects.RunStatus, objects.EventType, objects.OutcomeStatus, objects.ComparisonVerdict,
                 objects.ProposalSourceKind, objects.MetricStatus, objects.Aggregation, objects.MetricDirection,
                 objects.PluginInterface, objects.RetrySemantics):
        parts.append(f"- **{enum.__name__}**：" + "、".join(f"`{e.value}`" for e in enum))
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("docs/contracts/v1.md"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
