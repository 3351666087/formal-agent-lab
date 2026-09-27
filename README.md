# formal-agent-lab

通用实验平台与有限状态建模引擎（阶段一）。在一个中性的有限离散状态 IR 上：编辑模型、做有界检查（Z3），用纯数据模拟器作为环境，让规则 / 符号（Z3）/ LLM 策略在同一预算与评分下运行实验；实验由 Temporal 持久编排，事件可实时查看、导出、离线回放与重跑，策略可在场景 × 种子 × 预算矩阵上比较。

- **交接与状态**：[docs/handoff/phase1.md](docs/handoff/phase1.md)（[manifest](docs/handoff/phase1.manifest.json)，[验收结果](docs/handoff/phase1-checks.json)）
- **入门**：[docs/getting-started.md](docs/getting-started.md) · **部署**：[docs/deployment.md](docs/deployment.md)
- **契约**：[docs/contracts/v1.md](docs/contracts/v1.md) · **插件接入**：[docs/architecture/plugin-integration.md](docs/architecture/plugin-integration.md) · **能力矩阵**：[docs/architecture/capability-matrix.md](docs/architecture/capability-matrix.md) · **观测语义**：[docs/architecture/observation-semantics.md](docs/architecture/observation-semantics.md)
- **任务书与证据**：[docs/execution/phase-1.md](docs/execution/phase-1.md) · **决策**：[docs/execution/decisions.md](docs/execution/decisions.md) · **复用记录**：[docs/reuse-ledger.md](docs/reuse-ledger.md)

## 快速开始（Ubuntu 24.04）

```bash
bash scripts/bootstrap-dev-vm.sh && make bootstrap
make demo                          # 无需任何服务：有界检查 + 策略比较
make services-up && make dev-up    # 开发栈 → http://127.0.0.1:5173
make compose-up                    # 或容器化整栈 → http://127.0.0.1:8080
make phase1-check                  # 全部验收
```

## 结构

```
Web (React) ─┐
fal CLI ─────┼─► FastAPI /api/v1 (REST + SSE) ─► PostgreSQL（模型版本、场景、运行、事件、指标）
Python SDK ──┘            │                   └► 产物存储（本地 / S3 兼容）
                          ▼
                 Temporal ExperimentWorkflow ─► Worker 活动 ─► 步骤引擎（runtime）
                                                              ├─ 环境插件：IR 世界（纯数据模拟器）
                                                              ├─ 策略插件：规则 / Z3 规划 / LLM
                                                              ├─ 验证器插件：Z3 有界检查
                                                              └─ 评分器插件：通用 / 调度
契约 formal-lab-contracts/v1（Pydantic → JSON Schema → TypeScript）贯穿所有层；插件经 entry point 注册。
```

许可：仓库所有者尚未为本仓库代码选择许可证（插件元数据标为 `UNLICENSED`）；第三方组件的许可见复用记录。
