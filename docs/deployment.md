# 部署与已验证范围

| 方式 | 内容 | 已验证 | 证据 |
|---|---|---|---|
| 开发栈 | `deploy/compose/services.dev.yaml` + 本地进程（`scripts/dev.sh`） | ✅ Ubuntu 24.04 aarch64 虚拟机，长期运行 | `docs/execution/evidence/M5-platform-integration.log`、UI 测试 |
| Compose 整栈 | `deploy/compose/docker-compose.yaml`：postgres、temporal（dev server，SQLite 持久卷）、s3（SeaweedFS）、migrate、api、worker、web（Caddy） | ✅ 完整路径实测：构建、启动、迁移、种子、经 :8080 运行实验与矩阵、S3 产物、SSE 经代理、导出回放包 | `scripts/compose-smoke.sh` → `docs/execution/evidence/compose-smoke.json` |
| 离线包 | `scripts/offline_bundle.py`：镜像、wheel、Web、compose（pull_policy never）、install.sh、manifest | ✅ 解包到空目录、`pip --no-index` 安装 CLI、从包内 compose 启动并跑通实验 | `docs/execution/evidence/offline-manifest.json` |
| Helm Chart（渲染） | `deploy/helm/formal-agent-lab`：API/Worker/Web Deployment、Service、迁移 Hook Job、可选 Ingress（SSE 注解）、外部 PostgreSQL/Temporal/S3 与 LLM 通过现有 Secret 接入 | ✅ `helm lint --strict`（两组取值）、`helm template`、`kubeconform`（Kubernetes 1.31 schema） | `docs/execution/evidence/helm/{lint.log,kubeconform.log,rendered-*.yaml}` |
| Helm Chart（安装） | 同上，装入临时 kind 集群；PostgreSQL/Temporal/S3 为**测试夹具** `deploy/helm/test/backing-services.yaml`（不属于 Chart） | ✅ kind v0.33.0 / Kubernetes v1.37.0 单节点：迁移 Hook、三个 Deployment 就绪、经 web Service 运行实验成功、SSE 完整；未验证：多节点、Ingress 控制器、真实外部数据库/Temporal 集群、升级与回滚 | `scripts/helm-install-check.sh` → `docs/execution/evidence/helm/install.{json,log}` |

## 能力等级

所有配置均为**单用户本地开发配置**（`/api/v1/meta` 的 `capability_level`）：服务只绑定回环地址（Compose 只发布 127.0.0.1:8080），**没有认证与多租户隔离**；Temporal 为单节点 dev server；PostgreSQL 与对象存储为单实例。生产部署需要：外部高可用 PostgreSQL 与 Temporal、对象存储、TLS 与身份认证（在 Ingress/网关层接入）、Secret 管理——Chart 已为这些预留接入点，但本阶段未验证。

## Helm

```bash
make helm-lint
kubectl create secret generic formal-agent-lab-db --from-literal=database-url=postgresql+psycopg://…
kubectl create secret generic formal-agent-lab-s3 --from-literal=access-key-id=… --from-literal=secret-access-key=…
helm install fal deploy/helm/formal-agent-lab \
  --set image.registry=<registry> --set image.api.digest=sha256:… --set image.worker.digest=sha256:… --set image.web.digest=sha256:… \
  --set externalServices.temporal.address=<host:7233> --set externalServices.artifacts.s3.endpoint=<url>
```

镜像摘要来自 `out/release/manifest.json`（`make release`）；Chart 优先使用 digest 固定镜像。安装验证：`scripts/helm-install-check.sh`（kind，测试夹具提供后端服务），状态单独记录在 `docs/handoff/phase1-checks.json` 的 `P1-113-helm-install`。

## 架构与镜像

- 镜像：`deploy/docker/python.Dockerfile`（target `api` / `worker`，`python:3.12-slim-trixie`，`uv sync --frozen --no-dev`，非 root 用户）与 `deploy/docker/web.Dockerfile`（Vite 构建 → `caddy:2.11-alpine`，`/api` 以 `flush_interval -1` 代理 SSE）。
- 已构建与验证的架构：linux/arm64。amd64 镜像未构建（CI 在 x86_64 上验证了 Python/Node 代码与平台集成测试）。
