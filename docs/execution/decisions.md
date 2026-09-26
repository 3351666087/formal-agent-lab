# 决策记录（Phase 1）

每条记录：决策、理由、被放弃的替代方案、对后续扩展的影响。新决策追加到末尾，编号不复用。

## D-001 仓库组织：uv workspace + pnpm workspace 的单仓

- **决策**：Python 模块按职责拆为独立 workspace 包（`packages/*`、`examples/*`），用 uv 统一锁定（`uv.lock`）；Web 与生成的 TypeScript 契约用 pnpm 锁定（`pnpm-lock.yaml`）。
- **理由**：模块边界（contracts / model-core / solver-adapters / neutral-environment / strategies / evaluation / orchestrator / platform-api / sdk）在包层面强制依赖方向；单一锁文件保证 API、Worker、CLI 使用同一依赖闭包。
- **替代方案**：单个 Python 包 + 子模块（边界靠约定，易被跨层导入破坏）；Poetry / Hatch 多项目（无跨包统一锁）。
- **扩展影响**：后续阶段新增领域能力 = 新增 workspace 包或包外插件，不修改核心包。

## D-002 单一契约来源：Pydantic v2 模型 → JSON Schema → TypeScript

- **决策**：`packages/contracts` 中的 Pydantic 模型是 formal-lab-contracts/v1 的唯一来源；`contracts/v1/*.schema.json` 与 `packages/contracts-ts` 的 TypeScript 类型均由 `make contracts` 生成，CI 与 `make phase1-check` 通过重新生成 + `git diff --exit-code` 检查漂移。
- **理由**：后端主语言为 Python，运行时校验与契约定义同源；JSON Schema 是跨语言交换格式。
- **替代方案**：手写 JSON Schema 为源（Python 侧失去类型与校验便利）；Protobuf / TypeSpec（引入额外工具链，且 JSON 负载为主）。
- **扩展影响**：扩展字段只能通过带命名空间、版本与 schema 标识的 `extensions` 槽追加，核心对象保持强类型。

## D-003 开发运行环境：Colima Ubuntu 24.04 arm64 虚拟机

- **决策**：所有构建、测试、服务运行在 Colima（Lima vz）Ubuntu 24.04 aarch64 虚拟机内执行；源码位于宿主机 home 目录并通过 virtiofs 共享；工具链由 `scripts/bootstrap-dev-vm.sh` 固定版本安装；Python 虚拟环境放在虚拟机本地磁盘（`UV_PROJECT_ENVIRONMENT`），避免宿主机与虚拟机二进制混用。
- **理由**：交付目标是 Linux；arm64 原生虚拟化性能接近宿主机，Rosetta 可运行 amd64 镜像。
- **替代方案**：直接在 macOS 开发（与 Linux 目标不一致）；x86_64 QEMU 虚拟机（实测慢约 35 倍，已弃用）。
- **扩展影响**：实际验证的 OS/架构以 `docs/execution/evidence/P1-001-environment.md` 为准；amd64 镜像构建留作发行阶段扩展。

## D-004 LLM 接入：OpenAI 兼容 Chat Completions 适配器

- **决策**：LLM 策略通过平台自有 `ModelClient` 接口调用模型；首个实现为 OpenAI 兼容 Chat Completions（`FAL_LLM_BASE_URL` / `FAL_LLM_API_KEY` / `FAL_LLM_MODEL`，当前指向用户提供的中转站，默认模型 `gpt-5.6-sol`），使用 JSON Schema 结构化输出；另有确定性替身 `StubModelClient`，其结果标注来源 `LLM_STUB` 并与真实模型结果分开统计。
- **理由**：用户指定 OpenAI 兼容中转站；自有接口让策略与具体供应商解耦。
- **替代方案**：直接依赖某家 SDK（策略代码与供应商耦合）。
- **扩展影响**：新增供应商 = 新增 `ModelClient` 实现；密钥只存在于未纳入版本控制的 `.env`。
