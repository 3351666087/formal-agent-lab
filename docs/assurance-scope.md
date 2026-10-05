# 保证范围（Phase 3B 领域集成；Phase 4A 补充 §6；Phase 4B 补充 §7）

本文件区分不同强度的结论，避免把其中一类当作另一类。配套：[acceptance-phase3.md](acceptance-phase3.md)、[research-readout.md](research-readout.md)、[reuse-ledger.md](reuse-ledger.md)、[handoff/phase3.md](handoff/phase3.md)。

## 1. 模型内结论（formal, model-internal）

在明确声明的 profile、假设、量词、horizon、动作顺序与成本下，由形式化引擎给出的结论。它们是关于**模型**的,不是关于真实系统的。

- **MAL 确定性可达性**（D1）：在 `deterministic_finite_v1` profile 下，攻击步骤的布尔可达性。原生 mal-simulator 的可达集（TTC 禁用、无 Bernoulli）作为降低的 fold 预言；IR 闭包精确复现原生对目标步骤的可达性；参考解释器与 Z3 有界验证器独立复核，三者一致。见证=到目标的攻击路径；无见证=目标在界内不可达。
- **准入判定**（D2）：Broker 的放行当且仅当凭据签名有效、绑定本次请求、状态修订为当前、未过期、检查基础授权动作、且通过发布规则。数学保证**等于**凭据记录的 `check_basis` / `scope`，不多不少。
- **红蓝博弈与割**（D3）：最小代价割由最大流在建模攻击图上给出的最小顶点割；加固该割集后 Z3 确认目标不可达（模型内）。

## 2. 实测结论（measured, observed）

在真实运行的组件上观测到的事实。

- **拒绝零副作用**（D2/D4）：Broker 门控 DENY 时动作从不发送——在 local runner 真实运行与真实订单服务进程上观测（订单服务 `conditions` 前后一致、目标从不被攻陷）。
- **本地服务生命周期**（D4）：真实订单服务进程的创建→就绪→业务→探针→导出→复位→二次运行→异常终止→清理，逐步观测；探针从服务自身读取。
- **CAGE 原生分数**（D5）：CybORG 4.0 Scenario4 脚本基线的每队奖励、活跃计数、终止，按世界步观测；成对种子的均值/方差。

## 3. 预测与模型偏差（predicted vs. observed）

- **模型修订**（D3）：belief 模型的预测与真值在可比较状态上的差异才构成模型偏差，触发回归案例与修订；陈旧观测差异归类 STALE，不入回归库（沿用 D-022）。预测来自模型，真值来自环境/原生后端。

## 4. 信息假设（assumptions）

- 角色可见性由内核按 `ParticipantView` 过滤并记录输入摘要；真值保留给独立裁判（D3）。
- 隔离强度：Broker 门控边界 + 签名密钥与环境凭据分离 + 角色视图。**进程内 Python 对象不是代码沙箱**；真正的进程/容器/网络隔离由 D4 的生命周期组件（进程模式=回环子进程；compose 模式=带项目标签的容器）提供，依实际配置说明（D-029/D-031）。
- CAGE 为纯仿真消融，LabPolicy 边界保留（实验不出模拟器）（D-032）。

## 5. 不可比与未覆盖（incomparable / uncovered）

- **量纲不可比**：MAL 可达性（布尔）、CAGE 每队奖励（CybORG 量纲）、订单服务成功率（业务）在各自语义范围内方向一致，但量级不可互换、不合并（D5）。
- **UNSUPPORTED**：时间到攻陷（TTC）、概率可达性、部分观测、数量奖励超出 `deterministic_finite_v1`，需独立声明的 profile 或概率后端（PRISM，外部前提，D-023）（D1）。
- **UNKNOWN / 超时**：Z3 求解超时返回 UNKNOWN，如实记录（D1）。
- **条件项（未在本环境执行，不冒充交付）**：真实 LLM 端点（混合策略，D3，未配置则标注替身）；CAGE RL 训练智能体（需 torch/ray，未安装，D5）；PRISM-games 领域概率绑定（备选清单）。
- **发行重型项**：带 OCI 镜像的发行与去重离线包在宿主盘低于 15 GiB 保留量时记 BLOCKED（见 acceptance-phase3.md），非代码缺陷。

## 6. 执行依据与参与者边界（Phase 4A，A2）

- **执行依据**：每次发送（首发、重发、纯数据重放）前内核构造 `ExecutionContext`：身份取自内核的 turn（提案自称的 actor / run / step 不一致即 `IDENTITY_MISMATCH`，不发送）；当前版本由环境的权威读取给出——实时服务 `env.current_revision`（FRESH），纯数据环境即本运行的世界且步骤串行（SERIALIZED），其它为 UNKNOWN；提案版本单独保留。门控只从 `GateRequest.execution` 取版本。
- **准入**：凭据绑定 `execution_binding`（run、step、turn、actor、operation、动作与参数摘要、环境@版本、session、服务身份、版本集合、当前版本），签发与校验用同一规范化定义；`ReceiptIssuerGate` 在发送前按当时的执行依据签发。逐字段不一致各给一条拒绝原因。
- **检查与写入之间**：声明 `env.conditional_step` 的环境（订单服务）随发送携带 `expected_revision`，由服务在写入自身的事务内核对（EXACT：版本必须相同；LOCATIONS：操作读取的位置未被写过），不符则拒绝且零业务写入；此时读不到当前版本即阻止写入（`BASIS_UNKNOWN`）。未声明该能力的实时环境，检查与写入之间的窗口**不由平台关闭**：需要版本的门控须在 UNKNOWN 时自行拒绝。
- **参与者数据**：同一投影规则（`Projection`）作用于规划器观测、观测请求、候选（在投影后的信念上计算）、`last_outcome`（结果、冲突、错误文本）、发往模型的载荷与调用记录、检查点，以及参与者下载（只含本人与运行级事件、重新编号、环境/门控配置与地址清除、其他参与者的配置与视图清除）。运营方导出保持完整。`ParticipantServices.get_setting` 不交出环境写凭据、签名密钥与参与者令牌密钥。
- **保证范围**：受信的进程内 Python 插件**不是沙箱**——它们与环境适配器同进程，技术上可读进程内一切；视图约束的是平台交给它们的输入，不是它们的能力。对**独立进程**：写入边界由服务进程强制（无凭据 401，凭据只在 0600 文件中、只有适配器读取，清单与参与者下载中只有路径或没有），参与者通道是令牌绑定的只读 API（`/participant/whoami`、`/participant/export`，actor 参数越权 403）。订单服务只监听回环；其**读接口在回环上不鉴权**，因此“视图对同机进程保密”只在该进程无法访问服务端口时成立（例如服务在独立主机或容器网络中）——这是部署条件，不由平台代码保证。

## 7. Phase 4B 证据索引与证据状态

| 结论 | 检查（`scripts/phase4_domain_checks.py`） | 证据（`docs/execution/evidence/phase4/`） |
|---|---|---|
| B1 领域闭环（模型内结论与实测） | `p4-b1-unit`、`p4-b1-mal-loop`、`p4-b1-service` | `b1-mal.json`、`b1-service.json` |
| B1 真实模型调用 | `p4-b1-real-endpoint` | `b1-real-endpoint.json`（端点与模型名；凭据不在证据中） |
| B2 原生与平台逐世界步一致、配对比较 | `p4-b2-unit`、`p4-b2-native-platform`、`p4-b2-platform` | `b2-cage.json`、`b2-platform-run.json`、`b2-paired-report.md` |
| B3 四个入口的产品流程 | `p4-b3-product-flow` | `b3-product-flow.json`、`screens/b3-*.png` |
| B3 发行与本地交付 | `p4-b3-release` | `b3-release.json`、`release-manifest.json` |

- **证据状态由实际检查产生**：领域证据脚本的结论只含计算得出的布尔值；`offline_readable` 是写出后从磁盘回读的结果；每份证据记录生成时的修订（`scripts/evidence_io.py`）。“文件存在”“检查通过”“属于当前干净修订”三者分别判定（D6 与 `assess()`），任一不满足即不计为通过。
- **安装方式分开标记**：在线（第三方来自包仓库）、仅本机缓存（`uv --offline`）、完全离线（`pip --no-index`，wheelhouse 一次性在线下载，安装与运行期间代理指向关闭端口）。外部原生工具链（CybORG、mal-toolbox / mal-simulator）不进入 wheel、镜像与离线包。
- **工程检查与研究结论分开**：检查通过表示机制按声明工作；比较结果为小样本工程读数，置信区间跨 0 的项不下结论（见 [research-readout.md](research-readout.md) §5）。

## 8. 来源可追溯

每条结论都绑定到证据文件（`docs/execution/evidence/phase3/d*.json`）、测试与检查组（`scripts/phase3_check.py` 的 `d1-mal`…`d6-domain`），以及固定的上游版本/摘要（reuse-ledger.md）。每次 attempt 独立记录，失败/重试保留，旧 PASS 不充当新结果。
