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
make helm-install-check                     # 临时 kind 集群：安装当前 Chart → 实验 → 删除
bash scripts/helm-upgrade-check.sh          # 临时 kind 集群：阶段一版本 → 升级到当前 → 回滚，每步读旧数据并跑实验
```

种子数据包含三个项目：生产调度示例（单 / 双参与者、成本目标、任务计划策略）、仓储分配示例（第二语义 profile）、订单服务示例（五种案例的业务服务场景与纯数据对照；服务地址取 `FAL_ORDERS_ENDPOINT`，默认 `http://127.0.0.1:8765`，Compose 内为 `http://orders:8765`）。

## 3. 测试与验收

```bash
make test-unit            # 单元 / 契约 / 架构 / 示例（含订单服务进程）
make test-integration     # 平台（API + Worker + Temporal + PostgreSQL）：多参与者、订单服务协调、发布、矩阵 v2、SDK/CLI
make test-ui              # Playwright：六个区域、产品验收路径、界面状态与测量
make test-llm             # 真实模型（需要 .env 中的 FAL_LLM_*；否则 NOT_RUN）
make orders-e2e           # 订单服务从空目录到清理的端到端（进程 + Compose），日志写入 evidence/phase2/orders/
make phase2-check         # 全部阶段二验收检查组，写入 docs/handoff/phase2-checks.json（ARGS="--group g" 只跑一组）
make handoff-phase2       # 由检查结果重新生成 docs/handoff/phase2.manifest.json 与 phase2.md 中的表
make prism-games-check    # 可选：PRISM-games 概率查询，模型内核对（需要本地安装，见第 9 节）
```

验收结果的读法见 [acceptance-phase2.md](acceptance-phase2.md)。

### 阶段三检查（检查引擎）

```bash
make phase3-check                                    # 全部 → docs/execution/evidence/phase3/checks/results.json
make phase3-check ARGS="--group g4-batch"            # 一组；--only id,id；--skip id；--retries N；--list
make phase3-check ARGS="--only p3-matrix-kept-db --out out/checks/matrix"   # 独立输出目录
make checks SUITE=phase2 ARGS="--list"               # 同一引擎加载阶段二的检查（make phase2-check 的输出不变）
make design-check                                    # tokens.css / 演示 SVG 与源一致（等同 p3-design-sources）
```

引擎 `scripts/check_runner.py` 为每次尝试单独写日志（`logs/<id>/<时间>-attempt-<n>.log`），保留首次失败、重试与最终结果，并记录源码提交、工作区摘要、配置摘要（检查定义、`uv.lock`、`pnpm-lock.yaml`、Compose 文件）与运行前后的资源读数；另一提交 / 工作区 / 配置上的结果标为 `inherited`，不算当前通过。完整执行耗时（`timing.last_full_run_s`）与单项重跑（`timing.partial_runs`）分开统计。检查逐个运行（并发 1）；声明 `heavy_gib` 的检查先经 `disk_guard`，空间不足时记为 BLOCKED 并写明读数。`p3-product-flows` 与 `p3-web-flows` 需要运行中的开发栈（`scripts/dev.sh up`，建议用干净数据库 `FAL_DATABASE_URL=…/fal_demo`），否则 NOT_RUN。

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

备份覆盖 PostgreSQL（在 fal-dev 容器内 `pg_dump`）与本地产物目录（`FAL_ARTIFACT_ROOT`）；Temporal 自身的运行态不在其中，请在没有进行中运行时恢复。实际验证：`scripts/backup_restore_check.py` 在独立数据库中跑一次实验、导出回放包、备份 → 重置 → 恢复，确认行数一致且重新导出的回放包内容相同——`bundle.json` 列出的每个文件摘要与来源信息逐项一致；zip 本身带导出时刻，两次导出的字节不同（`docs/execution/evidence/phase2/backup-restore.json`）。Compose / Helm 的 S3 产物用对象存储自身的工具备份。

## 6. 升级、回滚与卸载

- **升级**：`git pull` → `make bootstrap`（锁文件安装）→ `make migrate`（Alembic 升级；旧行保留写入时的契约版本，读取时升级）→ `make dev-down && make dev-up`。迁移 0002 只增加列与表，旧代码可以读取升级后的数据库，因此 Helm 回滚到阶段一版本后应用仍可工作（`scripts/helm-upgrade-check.sh`：证据 `docs/execution/evidence/helm/upgrade.json`，仅单节点开发集群）。
- **回滚代码**：`git checkout <旧提交>` 后 `make bootstrap`；数据库无需降级。需要降级数据库时 `uv run alembic -c packages/platform-api/alembic.ini downgrade 0001`（会删除阶段二新增的表与列）。
- **卸载**：`make dev-down && make services-down`；删除数据卷：`docker compose -p fal-dev -f deploy/compose/services.dev.yaml down -v`；完整栈：`docker compose -f deploy/compose/docker-compose.yaml down -v`；订单服务：`make orders-down ARGS=--purge`。删除 `var/`、虚拟环境 `~/.venvs/formal-agent-lab` 与 `web/node_modules` 即完全移除。

## 7. 磁盘空间与整理（共享虚拟机）

**宿主机余量**：Colima 的虚拟机磁盘是宿主机上的稀疏文件，只增不减——VM 里写入的镜像、kind 节点、构建缓存都占用 Mac 的磁盘，删除后要 `fstrim` 才会归还。2026-09-28 宿主机磁盘写满，VM 的 Docker 数据盘写入失败、ext4 日志中止，正在构建的镜像层丢失（`e2fsck` 修复；PostgreSQL 崩溃恢复后 `pg_amcheck` 无错）。因此：

- `make disk-guard`（`python3 scripts/disk_guard.py --need 0 --trim`）报告宿主机（经共享仓库目录读取）与 `/var/lib/docker` 的剩余空间，并归还 VM 内已释放的块；
- 重型脚本开始前自行检查余量，不足即拒绝：Compose 冒烟 6 GiB、发行构建 6 GiB、离线包 8 GiB、kind 安装 8 GiB、kind 升级 10 GiB（实测峰值约 7 GiB 加余量）；`make phase2-check` 在每个 Docker 检查后执行一次回收；
- 建议宿主机保持 ≥ 15 GiB 空闲。

虚拟机中的 Docker 守护进程与其它项目共享。`make reclaim-disk` 只删除带本仓库 OCI 标签的悬空镜像与按提交号标记的本项目镜像，然后 `fstrim` 归还空闲块；全局构建缓存和共享镜像（如 `kindest/node`）不动。**不要**使用 `docker system prune`、`docker image prune -a` 或卷清理：它们会删除其它项目的镜像与数据。构建缓存可以清理——`docker builder prune -af` 只删除 BuildKit 构建缓存，不动任何镜像或卷（先用 `docker buildx du --verbose` 看一眼条目来自哪些 Dockerfile）；本项目每次版本变化都会重建约 1 GiB 的虚拟环境层，缓存累积到 10 GiB 以上时清理一次，再 `make disk-guard` 归还给宿主机。清理本项目某次临时环境：`python -m formal_lab_example_orders.lifecycle cleanup --project <name>`（只删除带 `dev.formal-lab.project=<name>` 标签的容器、卷与进程）。

### 网络代理

宿主机设置了 HTTP 代理时，Lima 会把它写入虚拟机的 `/etc/environment`（`HTTP_PROXY=http://192.168.5.2:<端口>`），但不写 `NO_PROXY`。本机回环地址的请求若走这个代理，只能经 Colima 的端口转发绕回，服务刚启动时得到 502 或连接超时。平台自己的客户端（SDK、订单服务适配器 / 探针 / 生命周期）对回环地址不使用代理；`scripts/in-vm.sh`、Makefile 与测试夹具把 `127.0.0.1,localhost,::1` 加入 `NO_PROXY`；`make doctor` 在缺少时给出警告。直接登录虚拟机操作时：`export NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1`。

## 8. 结果解释

- **运行状态与终止原因分开看**：`SUCCEEDED / JOINT_GOAL_REACHED` 是目标达成；`FAILED / NO_PROGRESS` 表示连续无状态变化超过上限（停止文本给出停滞长度）；`BUDGET_EXHAUSTED` 是预算用尽；`OPERATION_UNRESOLVED` 需要人工复核。
- **效果证据**：`observed`（本步新鲜观测）、`verified-within-scope`（服务操作查询等独立来源）、`unknown`（过时或缺失，不参与匹配）、`predicted`（模型预测）。
- **矩阵报告**：先看分母（单元数、失败 / 未运行 / 目标未达成 / 指标缺失），再看逐场景（独立单位：场景内的一个种子）与跨场景（按场景聚类重采样）汇总；配对比较每次只改变一个维度，方法效果（participants）、机制消融（ablation）与环境后端（backend）分别列出。只有区间不含 0 的差异才进入结论。
- **真实模型**：结果与请求记录在调用记录中（请求配置、返回型号、用量、是否报告）；重跑只保证请求与证据可复现，不保证回答相同。替身（`LLM_STUB`）永远单独标注。

## 9. 可选：PRISM-games（深化轨道）

概率查询不属于默认安装，平台也不分发 PRISM-games（GPL-2.0）：它作为本地安装的独立程序运行，平台只写入输入文件、读取输出文件（决策 D-023）。在虚拟机中安装（用户目录，不改系统包）：

```bash
mkdir -p ~/.local/opt/dl && cd ~/.local/opt/dl
curl -fsSLO https://github.com/prismmodelchecker/prism-games/releases/download/v3.2.4/prism-games-3.2.4-linux64-arm.tar.gz
sha256sum prism-games-3.2.4-linux64-arm.tar.gz   # 366f5fedf6d8be8b089372f64714edebda3fab26001bf38323905b8fcb62ce52
curl -fsSL -o jre21.tar.gz "https://api.adoptium.net/v3/binary/latest/21/ga/linux/aarch64/jre/hotspot/normal/eclipse"
cd .. && tar xzf dl/prism-games-3.2.4-linux64-arm.tar.gz && tar xzf dl/jre21.tar.gz
cd prism-games-3.2.4-linux64-arm && ./install.sh
```

适配器默认在 `~/.local/opt/prism-games-*` 与 `~/.local/opt/jdk-*` 查找，也可设置 `FAL_PRISM_GAMES_HOME`、`FAL_PRISM_JAVA_HOME`。x86_64 使用同一发行的 `linux64-x86` 包（未在本环境运行）。安装后：`make prism-games-check`（证据写入 `docs/execution/evidence/phase2/prism-games/`），Web 模型工作台“概率扩展”页、`GET /api/v1/extensions/prism-games`、`POST /api/v1/model-versions/{id}/probabilistic-checks`。未安装时这些入口明确报告不可用及原因（UNSUPPORTED），不给替代答案。

**结果解读**：`<<dispatcher>> Pmax=? [F "done"]` 是调度方在最坏环境下能保证的完成概率，`<<dispatcher,environment>>` 是双方合作时的上界；每个数值都与独立求解器（逐轮倒推）比较（容差 1e-6），状态数与参照图一致，导出的调度策略在最坏环境下的值等于报告值时才标为“模型内核对通过”。这些是数值结论，与 Z3 的确定性可达性结论不能互换。

## 10. 可选：MAL 工具链（领域轨道 D1）

MAL 领域（coreLang 攻击图）需要 mal-toolbox 与 mal-simulator。它们的依赖（antlr、tree-sitter、pettingzoo 等）与冻结的平台锁冲突，因此和 PRISM 一样放在**独立虚拟环境**里，通过类型化子进程（`packages/environment-mal/src/formal_lab_env_mal/_worker.py`）调用，绝不进入平台环境（决策 D-023 的同一模式）。三个上游包都是 Apache-2.0，可再分发；隔离只为解决依赖冲突，不是许可原因。固定版本：mal-toolbox 2.11.0、mal-simulator 3.2.1、coreLang v1.0.0。

在虚拟机中安装（用户目录）：

```bash
python3 -m venv ~/.venvs/fal-mal
~/.venvs/fal-mal/bin/pip install "mal-toolbox==2.11.0" "mal-simulator==3.2.1"
git clone --depth 1 --branch v1.0.0 https://github.com/mal-lang/coreLang ~/.venvs/fal-mal/src/coreLang
mkdir -p ~/.venvs/fal-mal/corelang
~/.venvs/fal-mal/bin/python - <<'PY'
from pathlib import Path
from maltoolbox.language import LanguageGraph
spec = Path.home() / ".venvs/fal-mal/src/coreLang/src/main/mal/coreLang.mal"
LanguageGraph.from_mal_spec(str(spec)).to_mar_archive(
    str(Path.home() / ".venvs/fal-mal/corelang/corelang-1.0.0.mar"))
PY
sha256sum ~/.venvs/fal-mal/corelang/corelang-1.0.0.mar
# 9aabc828b5174ebe202cf8120a8e13a989c2f6e03d5908d8c65a4cc8adb3b150
```

桥默认在 `~/.venvs/fal-mal` 找 venv、在其 `corelang/*.mar` 找语言归档，也可设置 `FAL_MAL_HOME`、`FAL_MAL_MAR`。安装后：`packages/environment-mal/tests` 的桥往返测试实际运行（否则按 `mal` 标记自动跳过），`scripts/d1_mal_evidence.py` 从原生工具链实时导入（证据 `import.source="live"` 且与提交的夹具摘要一致）。未安装时领域包仍可离线运行——降低、参考解释器、Z3 验证与 ir-world 平台运行都只用平台环境和提交的 `packages/domain-mal/tests/fixtures/`，证据脚本回退为 `import.source="fixture"`。

**结果解读**：场景包 `packages/domain-mal/scenarios/*.scenario.json` 固定语言/工具链版本与摘要、模型、入口点、目标，以及 LabPolicy（实验边界）/ TargetSecurity（目标性质）/ BusinessSLO（业务目标）。首个闭环把目标相关子集降低到 `deterministic_finite_v1` IR：原生模拟器的可达集是 fold 预言，参考解释器与 Z3 有界验证器独立复核，三者必须一致。见证=攻击路径；无见证=目标在界内成立；未知=求解器超时；概率 / 到达时间查询超出该 profile（UNSUPPORTED）；原生 TTC 已禁用，与 IR 单位步数不可比。这些结论与 CAGE、本地探针在各自语义范围内交叉检查，不能互换。
