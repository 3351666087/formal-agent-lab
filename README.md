# formal-agent-lab

通用实验平台与有限状态建模引擎（阶段二：本地平台）。在中性的有限状态模型上：编辑模型、做有界检查与成本优化（Z3），让一个或多个参与者（规则 / 符号 / 任务计划 / LLM 策略）轮流在纯数据模拟器或持久的本地业务服务中行动；实验由 Temporal 持久编排，暂停、Worker 重启与响应丢失后按操作 id 对账恢复；规则集与模型发布把效果差异接回模型修订；矩阵队列做配对比较与消融，回放可按轮次、计划、操作与模型版本定位并离线出报告。

- **交接与状态**：[docs/handoff/phase2.md](docs/handoff/phase2.md)（[manifest](docs/handoff/phase2.manifest.json)，[验收结果](docs/handoff/phase2-checks.json)）；阶段一：[phase1.md](docs/handoff/phase1.md)
- **验收**：[docs/acceptance-phase2.md](docs/acceptance-phase2.md) · **本地开发与运维**：[docs/local-development.md](docs/local-development.md) · **入门**：[docs/getting-started.md](docs/getting-started.md) · **部署**：[docs/deployment.md](docs/deployment.md)
- **契约**：[v2](docs/contracts/v2.md)（[v1](docs/contracts/v1.md) 冻结）· **插件接入**：[docs/architecture/plugin-integration.md](docs/architecture/plugin-integration.md) · **能力矩阵**：[docs/architecture/capability-matrix.md](docs/architecture/capability-matrix.md) · **观测语义**：[docs/architecture/observation-semantics.md](docs/architecture/observation-semantics.md)
- **任务书与证据**：[阶段二](docs/execution/phase-2.md)、[阶段一](docs/execution/phase-1.md) · **决策**：[docs/execution/decisions.md](docs/execution/decisions.md) · **复用记录**：[docs/reuse-ledger.md](docs/reuse-ledger.md) · **第三方许可**：[docs/licenses.md](docs/licenses.md)

## 快速开始（Ubuntu 24.04）

```bash
bash scripts/bootstrap-dev-vm.sh && make bootstrap
make doctor                        # 三个本地 profile 是否可用、资源与端口
make demo                          # 无需任何服务：有界检查 + 策略比较
make services-up && make dev-up    # 开发栈 → http://127.0.0.1:5173
make orders-up                     # 本地订单服务（持久业务环境）→ 127.0.0.1:8765
make compose-up                    # 或容器化整栈 → http://127.0.0.1:8080
make phase2-check                  # 全部阶段二验收（本地）
```

## 结构

```
Web (React) ─┐
fal CLI ─────┼─► FastAPI /api/v1 (REST + SSE) ─► PostgreSQL（模型版本、场景、运行、事件、操作账本、规则、发布、矩阵单元）
Python SDK ──┘            │                   └► 产物存储（本地 / S3 兼容）
                          ▼
     Temporal ExperimentWorkflow / MatrixWorkflow ─► Worker 活动 ─► 轮次内核（runtime）
                                                                   ├─ 语义驱动：IR 有限状态 / 仓储分配
                                                                   ├─ 环境：IR 世界（纯数据）/ 本地订单服务（HTTP，按 id 对账）
                                                                   ├─ 策略：规则 / Z3 规划与成本最优 / 任务计划（检查点）/ LLM
                                                                   ├─ 验证器：Z3 有界检查；规则集与发布检查
                                                                   └─ 评分器与独立探针
契约 formal-lab-contracts/v2（v1 冻结，经适配器读取；Pydantic → JSON Schema → TypeScript）贯穿所有层；插件经 entry point 注册。
可选：PRISM-games 概率查询作为独立进程扩展（不随平台分发，见 docs/local-development.md 第 9 节）。
```

许可：[Apache License 2.0](LICENSE)（另见 [NOTICE](NOTICE)；选择理由见决策 D-014）。第三方组件以未修改的官方发行物使用，各自的许可见[复用记录](docs/reuse-ledger.md)与[许可证清单](docs/licenses.md)。
