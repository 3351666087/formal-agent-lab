# 本地开发与运维（阶段二）

本文件说明本地平台的安装、启动、测试、恢复、清理、备份与结果解释。所有命令都在验证环境中实际执行过：Colima 虚拟机（Ubuntu 24.04 aarch64，4 vCPU，5.9 GiB），源码在 home 目录共享；在 macOS 上用 `scripts/in-vm.sh '<命令>'` 在虚拟机里执行。首次安装步骤见 [getting-started.md](getting-started.md)。

## 1. 三个本地 profile

| profile | 内容 | 需要 | 预计资源 | 用途 |
|---|---|---|---|---|
| `local-lite` | 纯数据示例、本地运行器、离线回放；可选本地订单服务进程 | Python + uv | 1 CPU · 600 MiB · 1.5 GiB | 策略开发、离线报告、`make demo` |
| `local-services` | PostgreSQL + Temporal + S3 + API + Worker + Web（+ 订单服务） | Docker + compose + Node/pnpm | 2 CPU · 2.6 GiB · 6 GiB | 平台验收、持久业务服务、UI |
| `local-kind` | 单节点 kind 集群，Helm 安装 / 升级 / 回滚 | Docker + kind + helm | 2 CPU · 3 GiB · 5 GiB | Chart 检查（仅单节点开发集群） |

`make doctor` 读取虚拟机实际可用的 CPU / 内存（cgroup 限制优先）、磁盘、Docker、端口占用（含占用者）与本项目资源，给出每个 profile 是否可用、预计资源和端口冲突；`python3 scripts/doctor.py --require local-services` 在不可用时以退出码 1 结束。订单服务默认端口 8765，平台开发端口 8000 / 5173，完整 Compose 栈 8080。

## 2. 启动

```bash
# local-lite
make demo                                   # 独立运行调度示例（无服务）
make orders-up                              # 订单服务进程 127.0.0.1:8765（项目 dev，数据在 var/.fal-orders/dev）
make orders-status && make orders-down      # ARGS=--purge 同时删除数据

# local-services
make services-up && make dev-up             # 后端服务 + API :8000 + Worker + Web :5173（迁移与种子自动执行）
make compose-up                             # 或：完整容器栈 http://127.0.0.1:8080（含订单服务 `orders`）

# local-kind
make helm-install-check                     # 临时 kind 集群：安装 → 实验 → 升级 → 回滚 → 删除
```

种子数据包含三个项目：生产调度示例（单 / 双参与者、成本目标、任务计划策略）、仓储分配示例（第二语义 profile）、订单服务示例（五种案例的业务服务场景与纯数据对照；服务地址取 `FAL_ORDERS_ENDPOINT`，默认 `http://127.0.0.1:8765`，Compose 内为 `http://orders:8765`）。

## 3. 测试与验收

```bash
make test-unit            # 单元 / 契约 / 架构 / 示例（含订单服务进程）
make test-integration     # 平台（API + Worker + Temporal + PostgreSQL）：多参与者、订单服务协调、发布、矩阵 v2、SDK/CLI
make test-ui              # Playwright：六个区域、产品验收路径、界面状态与测量
make test-llm             # 真实模型（需要 .env 中的 FAL_LLM_*；否则 NOT_RUN）
make orders-e2e           # 订单服务从空目录到清理的端到端（进程 + Compose），日志写入 evidence/phase2/orders/
make phase2-check         # 全部阶段二验收检查组，写入 docs/handoff/phase2-checks.json
```

## 4. 中断与恢复

- **Worker 退出 / 重启**：运行在 Temporal 中持久化；新 Worker 从数据库中的提案、检查点、轮次和操作账本继续（事件 `RECOVERY`）。操作结果未知时按操作 id 向服务查询后对账（`OPERATION_RECONCILED`），不会重复产生业务效果。
- **结果无法确认**：连查询也失败时操作标记 NEEDS_REVIEW，运行以 `OPERATION_UNRESOLVED` 结束。人工复核：运行台“环境操作”面板或 `fal ops list <run> --abnormal`、`fal ops review <op> --status CONFIRMED_APPLIED --note "…"`。
- **可解释终止**：`fal run cancel <run> --reason "…"`（运行台“取消”同样可填写原因）在步边界结束并记录原因。
- **矩阵队列**：队列状态在数据库中；`fal matrix resume <id>` 继续被中断的队列，`fal matrix rerun-failed <id>` 重跑失败单元，`fal matrix merge <id> spec.json` 增量加入单元（已完成的相同配置直接复用）。
- **订单服务进程**：`ServiceManager(supervise=True)` 在进程意外退出时重启它；服务端事务与操作 id 保证每个操作至多生效一次。

## 5. 备份、恢复、重置

```bash
python scripts/local_data.py status                                     # 行数、迁移版本、产物数量
python scripts/local_data.py backup --out var/backups/$(date +%F)        # database.sql + artifacts.tar.gz + backup.json
python scripts/local_data.py restore --from var/backups/2026-09-27 --yes
python scripts/local_data.py reset --yes                                 # 清空数据库与产物并重新迁移
```

备份覆盖 PostgreSQL（在 fal-dev 容器内 `pg_dump`）与本地产物目录（`FAL_ARTIFACT_ROOT`）；Temporal 自身的运行态不在其中，请在没有进行中运行时恢复。实际验证：`scripts/backup_restore_check.py` 在独立数据库中跑一次实验、导出回放包、备份 → 重置 → 恢复，确认行数一致且重新导出的回放包字节相同（`docs/execution/evidence/phase2/backup-restore.json`）。Compose / Helm 的 S3 产物用对象存储自身的工具备份。

## 6. 升级、回滚与卸载

- **升级**：`git pull` → `make bootstrap`（锁文件安装）→ `make migrate`（Alembic 升级；旧行保留写入时的契约版本，读取时升级）→ `make dev-down && make dev-up`。迁移 0002 只增加列与表，旧代码可以读取升级后的数据库，因此 Helm 回滚到阶段一版本后应用仍可工作（`make helm-install-check` 的升级 / 回滚检查）。
- **回滚代码**：`git checkout <旧提交>` 后 `make bootstrap`；数据库无需降级。需要降级数据库时 `uv run alembic -c packages/platform-api/alembic.ini downgrade 0001`（会删除阶段二新增的表与列）。
- **卸载**：`make dev-down && make services-down`；删除数据卷：`docker compose -p fal-dev -f deploy/compose/services.dev.yaml down -v`；完整栈：`docker compose -f deploy/compose/docker-compose.yaml down -v`；订单服务：`make orders-down ARGS=--purge`。删除 `var/`、虚拟环境 `~/.venvs/formal-agent-lab` 与 `web/node_modules` 即完全移除。

## 7. 磁盘整理（共享虚拟机）

虚拟机中的 Docker 守护进程与其它项目共享。`make reclaim-disk` 只删除带本仓库 OCI 标签的悬空镜像与按提交号标记的本项目镜像，然后 `fstrim` 归还空闲块；全局构建缓存和共享镜像（如 `kindest/node`）不动。**不要**使用 `docker system prune`、`docker image prune -a` 或无过滤的 `docker builder prune`。清理本项目某次临时环境：`python -m formal_lab_example_orders.lifecycle cleanup --project <name>`（只删除带 `dev.formal-lab.project=<name>` 标签的容器、卷与进程）。

## 8. 结果解释

- **运行状态与终止原因分开看**：`SUCCEEDED / JOINT_GOAL_REACHED` 是目标达成；`FAILED / NO_PROGRESS` 表示连续无状态变化超过上限（停止文本给出停滞长度）；`BUDGET_EXHAUSTED` 是预算用尽；`OPERATION_UNRESOLVED` 需要人工复核。
- **效果证据**：`observed`（本步新鲜观测）、`verified-within-scope`（服务操作查询等独立来源）、`unknown`（过时或缺失，不参与匹配）、`predicted`（模型预测）。
- **矩阵报告**：先看分母（单元数、失败 / 未运行 / 目标未达成 / 指标缺失），再看逐场景（独立单位：场景内的一个种子）与跨场景（按场景聚类重采样）汇总；配对比较每次只改变一个维度，方法效果（participants）、机制消融（ablation）与环境后端（backend）分别列出。只有区间不含 0 的差异才进入结论。
- **真实模型**：结果与请求记录在调用记录中（请求配置、返回型号、用量、是否报告）；重跑只保证请求与证据可复现，不保证回答相同。替身（`LLM_STUB`）永远单独标注。
