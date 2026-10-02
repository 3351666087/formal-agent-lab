# 检查状态协议（Phase 4A · A1）

本文件说明本地检查引擎 `scripts/check_runner.py`（报告格式 `checks@3`，向后兼容 `checks@2` 的键）如何判定每个检查的状态，以及严格总验收 `scripts/acceptance_local.py` 如何汇总。原则：**退出码不能单独产生 PASS**；状态由命令结果、结构化证据与声明的验收条件共同决定；汇总只采纳本次调用实际产生并验证过的结果。

## 1. 状态

| 状态 | 含义 | 是否满足必做 |
|---|---|---|
| `PASS` | 命令成功，且结构化结果 / 产出证据 / 必需断言全部成立 | 是 |
| `FAIL` | 命令失败、超时、证据缺失 / 过期 / 格式错误、必需断言为 false 或未定 | 否 |
| `BLOCKED` | 声明的环境前提缺失（磁盘低于保留量、工具链未装、全部测试被跳过等），未验证任何东西 | 否 |
| `NOT_RUN` | 检查需要的服务 / 开发栈未就绪 | 否 |
| `NOT_SELECTED` | 本次调用未选中 | 否（部分运行） |
| `NOT_APPLICABLE` | 条件项的触发条件在执行前判定为不成立 | 不计入 |

环境依赖缺失属于执行阻塞：必做检查 BLOCKED / NOT_RUN 时组状态为 `INCOMPLETE`，不能通过把检查改成条件项来消除——条件项的触发探针在套件定义中固定（属于配置摘要），执行前评估并记录在结果的 `condition` 字段。

## 2. 单个检查如何判定

引擎为每次 attempt 设置 `FAL_CHECK_ID`、`FAL_CHECK_ATTEMPT`、一次性 `FAL_CHECK_NONCE` 和 `FAL_CHECK_RESULT`（结构化结果的写入位置），按下列顺序判定（`decide()`，逐条有单元测试）：

1. 超时 → `FAIL`。
2. 结构化结果带本次 nonce 且状态为 `BLOCKED` / `NOT_RUN` → 该状态（脚本可用退出码 3）。
3. 退出码非 0 → `FAIL`。
4. 结构化结果：nonce 不符 → `FAIL`（过期）；格式错误 → `FAIL`；`protocol=True` 却未写 → `FAIL`；任一必需断言非 `true` → `FAIL`；没有任何必需断言 → `FAIL`（什么也没验证）。
5. `produces` 声明的每个文件：不存在 → `FAIL`；修改时间早于本次 attempt（旧运行残留）→ `FAIL`；JSON 无法解析 → `FAIL`；顶层 `status` 为 `BLOCKED` / `NOT_RUN` / `FAIL` → 采纳；`assertions_from` 指定节中任一布尔为 `false` → `FAIL`。
6. pytest 命令摘要中 0 个通过：有跳过 → `BLOCKED`（附跳过原因），全无 → `FAIL`。
7. 否则 `PASS`。

失败后按 `retries` 重试；`BLOCKED` / `NOT_RUN` 不重试（环境不会因重试而出现）。每个结果记录原因（`reason`）、检查 ID、每次 attempt（日志、退出码、nonce、结构化结果位置、断言、产出文件的摘要与新鲜度、pytest 计数）、`evidence_files`（引用文件与产出文件的 sha256）。

## 3. 证据脚本如何上报

```python
from check_result import CheckResult      # scripts/check_result.py，仅标准库
r = CheckResult("p4-a2-binding")
if not service_up:
    sys.exit(r.blocked("order service not reachable"))       # BLOCKED，退出码 3
r.check("stale_version_rejected", writes == 0, f"writes={writes}")   # 必需断言
r.check("p50_latency", p50 < 50, "informational", required=False)    # 只记录
r.evidence("docs/execution/evidence/phase4/a2-binding.json")
sys.exit(r.finish())                                          # PASS 0 / FAIL 1 / BLOCKED 3
```

结构化结果格式 `fal-check-result@1`：`protocol`、`check`、`nonce`、`attempt`、`commit`、`started_at`/`finished_at`、`status`、`reason`、`assertions[{id, required, holds, detail}]`、`evidence[]`、`notes[]`。脚本自报的状态只是参考，引擎按第 2 节重新推导，只可能更严。

## 4. 汇总

- **只采纳本次调用**：组状态与 `summary` 只计本次调用产生的结果（`this_run`）；早先调用（即便同一 commit / 工作树 / 配置）的结果保留在历史中但不参与汇总。
- **代码或配置变化后旧 PASS 失效**：记录的 commit、工作树摘要或配置摘要（检查定义 + uv.lock + pnpm-lock.yaml + Compose 文件）任一不同 → `inherited: true`，永不计为当前 PASS。
- **组状态**：`PASS`（计入的检查本次全部通过）/ `FAIL` / `INCOMPLETE`（有阻塞、未运行或未选中）/ `NOT_SELECTED` / `NO_CHECKS`（必需组尚未登记检查，例如 4A 期间的 b1—b3）/ `OPTIONAL`。
- **`complete`（= `mandatory_passed`）**：完整运行（无 `--group` / `--only` / `--skip`）且每个必需组 `PASS`。部分运行给出 `selection_status`，永不 `complete`。
- **退出码**：`--strict` 时仅 `complete` 返回 0；默认（开发用）有 FAIL 才返回 1。
- **摘要排除范围**：套件的 `outputs`（证据目录、交接文档、`out/`）不进入工作树摘要；引擎拒绝运行任何会把可执行代码（`.py .ts .tsx .js .sh …`）排除在外的配置（退出 2）。

## 5. 严格总验收

`make acceptance-local`（`scripts/acceptance_local.py`）依次运行阶段二、阶段三、阶段四套件，每个写入 `out/acceptance/<suite>/`，环境带一次性 `FAL_ACCEPTANCE_NONCE`；复跑的阶段二 / 三证据写入 `docs/execution/evidence/phase4/regression/<suite>/`，历史记录不被覆盖。每个套件的裁决：

| 裁决 | 条件 |
|---|---|
| `COMPLETE` | 报告带本次 nonce、完整运行、`complete=true` |
| `INCOMPLETE` | 完整运行但有未满足的必需组 |
| `PARTIAL` | 只选了部分组 / 检查 |
| `REPORT_MISSING` | 运行器退出后没有报告 |
| `STALE_REPORT` | 磁盘上的报告不是本次写的（nonce 不符） |
| `MALFORMED_REPORT` | 报告无法解析或格式不对 |
| `RUNNER_CRASHED` | 运行器异常退出（非 0/1） |

总验收 `complete` 只在全部套件 `COMPLETE` 时为真；严格模式（默认）否则退出 1，`--no-strict` 只生成报告并退出 0。报告：`docs/execution/evidence/phase4/acceptance-local.json`。

## 6. 给 B1—B3 的登记接口

领域检查登记在 `scripts/phase4_domain_checks.py` 的 `DOMAIN_CHECKS`，只能用组 `b1` / `b2` / `b3`（套件加载时校验）；证据脚本使用 `protocol=True` 并经 `CheckResult` 上报业务断言；真实端点、可选后端用 `kind="conditional"` 与固定的 `trigger` 探针。未登记时这三组为 `NO_CHECKS`，整体 `complete` 保持为假。

## 7. 回归测试

`tests/tools/test_check_status.py`（六种不得通过的情形 + 完整通过 + pytest 全跳过 + 条件触发 + 环境缺失 + 空必需组 + 摘要排除守卫 + `decide()` 逐条）、`tests/tools/test_acceptance_local.py`（完整 / 阻塞 / 部分 / 报告丢失 / 旧报告残留 / 非严格）、`tests/tools/test_check_runner.py`（attempt、重试、历史、计时）。对真实引擎的故障注入证据：`scripts/a1_status_evidence.py` → `docs/execution/evidence/phase4/a1-status-protocol.json`。
