# 从空环境开始

本文件记录**实际验证过**的路径与资源。验证环境：macOS（Apple M4）上的 Colima（Lima vz）虚拟机，**Ubuntu 24.04.4 LTS，aarch64，4 vCPU，5.9 GiB 内存**，Docker 29.5.2 / compose 5.1.4（见 `docs/execution/evidence/P1-001-environment.md`）。另有 GitHub Actions `ubuntu-24.04`（x86_64）上的 CI 运行契约、单元、Web 构建与平台集成测试。其它 OS/架构未验证。

## 0. 前提

- Ubuntu 24.04（或等价 Linux）+ Docker Engine（含 compose 插件），`sudo` 可用（安装 apt 包）。
- 在 macOS 上开发时：`colima start --arch aarch64 --vm-type vz --vz-rosetta --mount-type virtiofs --cpu 4 --memory 6 --disk 30`，源码放在 home 目录下（virtiofs 共享），命令在虚拟机内执行：`scripts/in-vm.sh make <target>`。
- 网络：首次安装需要访问 PyPI、npm、GitHub releases、Docker Hub；之后可用离线包（`make offline-bundle`）。

## 1. 工具链与依赖（锁定版本）

```bash
git clone https://github.com/3351666087/formal-agent-lab.git && cd formal-agent-lab
bash scripts/bootstrap-dev-vm.sh      # uv 0.12.19, node 24.21.0, pnpm 12.6.0, helm 4.3.0, temporal CLI 1.9.1, kubeconform 0.8.0
make bootstrap                        # uv sync --frozen（uv.lock） + pnpm install --frozen-lockfile（pnpm-lock.yaml）
cp .env.example .env                  # 仅示例值；LLM 密钥可留空
```

## 2. 开发栈（本机回环地址，单用户本地开发配置）

```bash
make services-up     # PostgreSQL 16、Temporal dev server、SeaweedFS S3（仅 127.0.0.1），并执行迁移
make dev-up          # 迁移 + 种子数据 + API :8000 + Worker + Web :5173（进程与日志在 var/run、var/log）
make dev-status
```

打开 http://127.0.0.1:5173 → 项目“生产调度示例” → 实验运行台选择场景与策略启动。API 就绪检查：`curl 127.0.0.1:8000/api/v1/health/ready`。

## 3. 验证

```bash
make demo              # 不需要任何服务：独立运行示例的有界检查与策略比较
make test-unit         # 单元 / 契约 / 架构测试
make test-integration  # 需要 make services-up：平台、编排、SDK/CLI、回放、Inspect
make test-ui           # 需要 uv run playwright install --with-deps chromium
make phase1-check      # 全部阶段一验收，写入 docs/handoff/phase1-checks.json
```

## 4. 容器化整栈

```bash
make compose-up        # 构建镜像并在 http://127.0.0.1:8080 启动 Web/API/Worker/PostgreSQL/Temporal/S3
make compose-smoke     # 构建→启动→种子→经 :8080 跑实验与矩阵→检查 S3 产物→导出回放包→拆除
```

## 5. 实测资源（验证环境）

| 项 | 实测 |
|---|---|
| 开发栈运行内存 | 约 1.4 GiB（PostgreSQL 130 MiB、Temporal 176 MiB、SeaweedFS 92 MiB、API+Worker+Vite 约 640 MiB） |
| Python 虚拟环境 | 628 MB；node_modules 108 MB；Playwright Chromium（仅 UI 测试）662 MB |
| 镜像 | api / worker 各 223 MB，web 23 MB（arm64），服务镜像约 350 MB |
| 离线包 | 820 MB（6 个镜像 + 30 个 wheel + Web） |
| 典型耗时 | 单元测试约 2 分钟；平台集成测试约 1.5 分钟；UI 测试约 2.5 分钟；镜像构建约 1 分钟；compose-smoke 约 1.5 分钟 |

镜像构建会累积 Docker 构建缓存，虚拟机磁盘是稀疏文件：需要时 `make reclaim-disk` 可释放并归还给宿主机。

## 6. 可选：真实模型

在 `.env` 设置 `FAL_LLM_BASE_URL`、`FAL_LLM_API_KEY`、`FAL_LLM_MODEL`（OpenAI 兼容 Chat Completions，需支持 JSON Schema 结构化输出），然后 `make test-llm`。未配置时 LLM 策略显示为“未配置”，可用标注为 `LLM_STUB` 的确定性替身。
