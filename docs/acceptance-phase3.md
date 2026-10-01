# 阶段三本地验收（Phase 3）

源修订：`6cbda09fda22` · 生成：2026-10-01T01:23:06Z · 引擎 `scripts/check_runner.py`（format checks@2）。配套 [phase3.md](handoff/phase3.md) · [assurance-scope.md](assurance-scope.md)。

命令：`make phase3-check`（阶段三全部组）、`make acceptance-local`（阶段二必做 + 阶段三 D1–D6）。带服务的检查未起栈时记 NOT_RUN，磁盘低于保留量的发行检查记 BLOCKED，均非代码缺陷。

**必做全部通过：False** · 汇总 PASS=30 · FAIL=0 · NOT_RUN=2 · NOT_SELECTED=0 · BLOCKED=3

## 检查组

| 组 | 结果 |
|---|---|
| g1-contracts | PASS |
| g2-operations | PASS |
| g3-release | PASS |
| g4-batch | PASS |
| g5-product | INCOMPLETE |
| g6-release | INCOMPLETE |
| d1-mal | PASS |
| d2-broker | PASS |
| d3-strategies | PASS |
| d4-service | PASS |
| d5-cage | PASS |
| d6-domain | PASS |
| regression | PASS |

## 非 PASS 项（原因）

| 检查 | 结果 | 组 | 说明 |
|---|---|---|---|
| p3-product-flows | NOT_RUN | g5-product |  |
| p3-web-flows | NOT_RUN | g5-product |  |
| p3-release-light | BLOCKED | g6-release |  |
| p3-release-images | BLOCKED | g6-release |  |
| p3-offline-bundle | BLOCKED | g6-release |  |

## 条件项 / 备选（未在本环境执行，不冒充交付）

- 真实 LLM 端点（D3 混合策略；未配置则以标注替身运行，不冒充交付）
- CAGE RL 训练智能体（需 torch/ray，本环境未安装；交付的是官方脚本基线）
- PRISM-games 领域概率绑定（备选清单；通用任务分配扩展已完成，不作为领域绑定）
- 带 OCI 镜像的发行与去重离线包（宿主盘低于 15 GiB 保留量时 BLOCKED，非代码缺陷）
