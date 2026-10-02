# 设计系统：Evidence Workbench

阶段三 G5 定稿的视觉基线。方向：**专业研究工作台**——清楚呈现模型结构、运行过程与证据，信息密度高但层次分明；中性画布、墨色文字、克制的品牌色，颜色永远不是唯一的信息来源。后续集成主要增加插件数据、字段、标签和必要的组件状态；全局品牌、字体、导航结构、间距体系与动效语言以本文件与基准截图为准，确需调整时在基准截图上说明原因。

- Figma：[formal-agent-lab · Evidence Workbench (Phase 3A)](https://www.figma.com/design/uuV6JeilZQkhnIQcJYEUET)（节点索引 [design/figma.json](../design/figma.json)）
- 样式源：[design/tokens.json](../design/tokens.json) → [scripts/design_tokens.py](../scripts/design_tokens.py) → [web/src/tokens.css](../web/src/tokens.css)（生成，勿手改）；组件样式 [web/src/styles.css](../web/src/styles.css)；组件 [web/src/ui.tsx](../web/src/ui.tsx)、[web/src/icons.tsx](../web/src/icons.tsx)
- 媒体源：[design/animation/](../design/animation/)（分镜与真实数据）、[design/brand/mark.svg](../design/brand/mark.svg)

## 1. 原则

1. **结论先于装饰**：页面先回答“发生了什么、依据是什么”（状态、结论、证据等级），再给细节。
2. **三类颜色各司其职**：品牌色只用于主要操作、当前导航、焦点与选中；状态色只表示状态并总与图标或文字同时出现；分类色（p1…p8）只表示参与者与图表系列。
3. **证据等级可辨**：观测 ● 实线 · 范围内核实 ◆ 实线 · 预测 ◌ 虚线 · 未知 ○ 点线——颜色、符号、描边三重编码，灰度打印仍可区分（含义见 `formal_lab_model/compare.py`）。
4. **真实数据**：界面、截图、动画只展示真实运行的结果；规范示意中的占位数值写明“占位”。
5. **键盘与减少动态**：所有操作可用键盘完成；`prefers-reduced-motion` 下所有时长为 0，循环停止，状态变化仍然可见。

## 2. Tokens

全部以 CSS 变量提供（Figma 变量的 Web 代码语法就是同名 CSS 变量）。深色模式：`prefers-color-scheme: dark`，或 `<html data-theme="dark|light">` 覆盖（侧栏底部“外观”切换，存 `localStorage.fal-theme`）。

### 颜色（`--color-*`，Light / Dark）

| 组 | 变量 | 用途 |
|---|---|---|
| 画布与表面 | `canvas` `surface` `surface-sunken` `surface-raised` | 页面底色、卡片、凹陷区（表头、代码、未选中格）、浮层 |
| 边框 | `border` `border-strong` `focus` | 分隔线、输入框与按钮描边、焦点环 |
| 文字 | `text` `text-secondary` `text-muted` `text-inverse` | 正文、次要说明、标签与元信息、深色底上的文字 |
| 品牌 | `brand` `brand-strong` `brand-soft` `brand-contrast` | 主按钮、当前导航（左侧 2 px 条）、选中行、焦点；`brand-contrast` 是品牌底上的文字 |
| 状态 | `success` `warning` `danger` `info` `neutral` 及各自 `*-soft` | 标签文字 / 底色：成功与“符合预期”、暂停与“信息不足”、失败与“存在差异”、排队与“存在未知项”、中性 |
| 图表 | `chart-grid` `chart-axis` | 网格线、坐标文字 |

参与者 / 系列：`--p1 … --p8`（按参与者在运行中的顺序，`participantSlot()`；图表系列按顺序取）。证据：`--ev-observed` `--ev-verified` `--ev-predicted` `--ev-unknown`。

**对比度**（2026-09-30 复核，WCAG 相对亮度）：正文与次要文字 ≥ 8.5:1；`text-muted` 在画布 / 表面上 ≥ 4.7:1（浅）/ ≥ 5.5:1（深）；状态文字在其 soft 底色上 ≥ 4.6:1；证据标签在表面上 ≥ 4.7:1；参与者色块上的首字母用 `text-inverse`（浅色 ≥ 4.66:1，深色 ≥ 7.3:1）。复核时下调了浅色 `text-muted`、两种模式的 `ev-unknown` 与 p2、p6（tokens 1.0.1）。

### 字体、间距、圆角、阴影、动效、布局

| 类别 | 值 |
|---|---|
| 字体 | `--font-sans`：Inter → IBM Plex Sans → 系统 UI → PingFang SC / Hiragino / Noto Sans CJK SC；`--font-mono`：JetBrains Mono → SF Mono → ui-monospace（id、摘要、动作文本）。Figma 中文用 Noto Sans SC |
| 字号 / 行高 | `xs` 11/16 · `sm` 12.5/18 · `md` 14/21（正文）· `lg` 16/24 · `xl` 20/28（页标题）· `2xl` 26/34 · `display` 34/40；字重 400 / 540 / 620 / 700 |
| 间距 | 4 px 网格：`--space-1` 4 · 2 8 · 3 12 · 4 16 · 5 20 · 6 24 · 8 32 · 10 40 · 12 48 |
| 圆角 | `sm` 4（色块、小元素）· `md` 6（按钮、输入框、单元格）· `lg` 10（卡片）· `xl` 14（模态）· `pill`（标签） |
| 阴影 | `--shadow-1` 卡片 · `-2` 浮层 · `-3` 模态、提示、窄屏侧栏 |
| 动效 | `--dur-fast` 120 ms（悬停、焦点）· `base` 180 ms（淡入）· `slow` 280 ms（侧栏滑入、提示上升、进度条）· `narrative` 480 ms（演示动画）；`--ease-standard` cubic-bezier(0.2, 0, 0, 1)，`enter` / `exit` 用于出现与消失 |
| 布局 | 侧栏 248 px；内容最大 1480 px；边距 24 px（窄屏 14 px）；断点 860 px（单列、抽屉侧栏）与 1100 px（三列 → 两列） |

## 3. 组件

| 组件 | 代码 | 用法 |
|---|---|---|
| 页头 `PageHead` | `ui.tsx` · `.page-head` `.eyebrow` | 每个功能区的第一块：区名（带图标）· 标题 · 一句话说明 · 右侧操作；详情页用面包屑代替区名 |
| 按钮 | `.btn` `.primary` `.danger` `.ghost` `.sm` `.quiet-danger` + `<Icon>` | 一个视图只有一个主按钮；危险操作用描边红色；图标在文字前且 `aria-hidden`，可访问名称只含文字 |
| 状态标签 `StatusBadge` | `ui.tsx` · `.badge.{ok,warn,err,info,accent}` | 运行状态：符号 + 文字（✓ 成功、✕ 失败、‖ 暂停、运行中带脉冲点）；其他结论标签（`VerdictBadge`、`ComparisonBadge`、`SourceBadge`）同一形态 |
| 证据标签 `EvidenceTag` / `EvidenceLegend` | `ui.tsx` · `.ev.*` | 字段级比较的“预测 / 观测 / 核实 / 未知”；步骤详情顶部放图例 |
| 参与者芯片 `ParticipantChip` | `ui.tsx` · `.pchip`，`participantSlot()` `participantColor()` | 参与者名称前的色块与首字母；参与者面板、步骤表、批次单元格用同一颜色（`--pc`） |
| 统计块 `Stat` | `ui.tsx` · `.stat` | 标签在上、数字在下（等宽数字）；用于关键数值 |
| 卡片 / 面板 | `.card` `.card-head` `.card-body` `.pad` `.panel-title` | 内容分组；卡片头 44 px 高，可放标签页、筛选与小按钮 |
| 表格 | `.table` `.table-wrap` `.tall` `.wide` `.selectable` `.selected` `VirtualTable` | 表头小写大写字母、粘性；数值列右对齐等宽数字；可选中行有左侧品牌条；大日志用窗口化表格 |
| 表单 | `.field` `.form-grid` `SchemaForm` `JsonField` | 标签在上；错误显示在字段下并标 `aria-invalid`；插件配置由其 JSON Schema 生成 |
| 标签页 `Tabs` | `ui.tsx` · `.tabs` | 键盘 ← → 在标签间移动（roving tabindex） |
| 模态 `Modal` | `ui.tsx` · `.modal` | 打开时焦点进入第一个输入，Esc 关闭并把焦点还给触发者 |
| 空态 / 错误 / 加载 | `Empty` `ErrorState` `Loading` `QueryState` `InlineError` · `.state` `.state-icon` | 空态说明下一步；错误显示错误码、信息与字段错误并可重试；路由级错误在外壳内显示（`RouteError`） |
| 提示与横幅 | `.callout.{ok,warn,err,info}`、`ControlBanner`、toast | 说明性提示；运行控制状态；操作反馈（4.5 s） |
| 批次行 `BatchPanel` | `components/RunKernel.tsx` · `.batch-row` `.batch-cell` | 同步批次：一轮一行，成员单元格左边框为参与者色，右侧是世界步与环境自动参与者；≤ 640 px 逐轮堆叠（轮次 → 每名成员整宽一格 → 世界步），单元格内容换行、动作全文在 `title`；轮次列表可键盘聚焦滚动（`tabIndex=0`） |
| 图标 `Icon` / `BrandMark` | `icons.tsx` | 16 px 网格、1.6 描边、圆角端点；20 个图标与标志，Figma 组件使用同一路径 |

## 4. 图表与模型图

| 图 | 代码 | 规则 |
|---|---|---|
| 模型结构图 | `components/ModelGraph.tsx` | 四列：领域 → 状态与常量 → 动作 → 性质；节点 220 × 40、`radius-md`；写入边 `danger` 1.6 px，读取边 `brand` 1 px，索引域 `text-muted` 虚线 3/3；选中节点 `brand-soft` 并高亮关联边 |
| 步骤时间线 | `components/Steps.tsx` `Timeline` | 通道：动作结果、前提检查、效果比较、未知项；success / danger / warning / info 表示结论；未选中列 45% 不透明，选中列 `brand` 1.5 px 外框 |
| 状态图表 | `components/Steps.tsx` `StateChart` | 每个位置一行，随步骤变化；未知（上次已知值）用 `warning` |
| 指标柱状图 | `pages/Benchmarks.tsx` | 系列按顺序取 `--p1…`（不用状态色）；网格 `chart-grid`，坐标 `chart-axis`；缺失值画虚线空框并标“缺失”；置信区间用须线 |
| 批次行 | `components/RunKernel.tsx` | 见组件表；PASSED / ABSENT / TIMED_OUT / CANCELLED 单元格用 `surface-sunken` 底色，悬停显示原因 |

## 5. 页面布局

外壳（`main.tsx Shell`）：左侧 248 px 侧栏（标志与项目选择、功能区导航、服务状态 / 配置 / 契约摘要 / LLM / 外观），右侧内容区；窄屏为顶栏 + 抽屉侧栏。首个 Tab 是“跳到主要内容”。

| 区域 | 路由 | 布局 |
|---|---|---|
| 项目 | `/` | 页头 + 产品流程（模型 → 计划 → 运行 → 偏差 → 证据）+ 配置提示 + 按分组的项目卡片 |
| 模型工作台 | `/p/:pid/models/:modelId` | 左列模型列表，右侧模型概要 + 标签页（结构图、表单、JSON、版本差异、编译与检查、目标与发布、概率扩展、能力矩阵与能力报告） |
| 场景管理 | `/p/:pid/scenarios/:sid` | 左列场景，右侧基本信息、参与者（策略、范围、**视图**）、轮次（含**同步批次**与期限）与联合终止条件 |
| 策略注册表 | `/p/:pid/strategies` | 项目策略配置表 + 插件目录（能力、配置 schema、兼容性） |
| 实验运行台 | `/p/:pid/runs`、`/p/:pid/runs/:runId` | 列表 + 启动表单；运行台：页头操作条 → 控制横幅 → 同步批次（JOINT_BATCH 时）→ 参与者 / 环境 / 操作 / 恢复四面板 → 配置 / 预算 / 结果 → 轨迹（时间线、状态、事件）→ 步骤列表与步骤详情 |
| 证据与回放 | `/p/:pid/evidence/:runId` | 左列运行，右侧按步回放、关联定位、因果时间线、差异报告、同步批次、产物、来源与清单 |
| 基准对比 | `/p/:pid/benchmarks/:mid` | 左列矩阵，右侧报告（结果分布、逐场景 / 合并、配对比较、指标柱状图、单元队列与复用标记） |

## 6. 可访问性

- 键盘：跳到主要内容；侧栏导航与所有控件可 Tab 访问；标签页 ← →；运行台与回放中 ← → 切换步骤、空格播放 / 暂停；模态 Esc 关闭并归还焦点。
- 焦点：`:focus-visible` 2 px 品牌色描边（偏移 2 px）；输入框聚焦时加 `brand-soft` 光晕。
- 减少动态：tokens 中所有时长为 0，另有全局规则停止动画与过渡；演示 SVG 改为显示静态总结。
- 不以颜色为唯一信息：状态有符号与文字、证据有符号与描边、参与者有首字母与名称。
- 验证：`scripts/capture_screens.py` 检查跳转链接、减少动态、390 px 无横向滚动、无页面错误与错误界面。

## 7. 媒体与生成命令

| 产物 | 命令 | 源 |
|---|---|---|
| `web/src/tokens.css` | `python3 scripts/design_tokens.py`（`--check` 检查漂移） | `design/tokens.json` |
| 基准截图 `docs/assets/screens/*.png` 与 Web 流程证据 `g5-web.json` | `scripts/dev.sh up`（建议用干净库：`FAL_DATABASE_URL=…/fal_demo`）后 `scripts/in-vm.sh 'uv run --frozen python scripts/capture_screens.py'` | 真实运行（仓储同步批次、订单延迟响应恢复、矩阵复用） |
| SDK / CLI 流程证据 `g5-flows.json` | `scripts/in-vm.sh 'FAL_API_URL=http://127.0.0.1:8000/api/v1 uv run --frozen python scripts/product_flow_evidence.py'` | 同上两个场景 |
| `demo.svg` `demo-cover.svg` `demo.html` `architecture.svg` | `python3 scripts/render_demo.py svg`（只需标准库） | `design/animation/storyboard.json`、`demo-data.json`、`design/tokens.json` |
| 视频帧 → `demo.mp4`、`demo-cover.png` | `scripts/in-vm.sh 'uv run --frozen python scripts/render_demo.py frames'`，再在宿主机 `python3 scripts/render_demo.py encode`（ffmpeg、rsvg-convert） | `demo.svg`（Chromium 按 Web Animations API 逐帧定位，30 fps，1920×1080） |

动画的数值来自订单服务示例 deviation 案例的真实运行与 `docs/execution/evidence/phase3/g3-release.json`，`demo-data.json` 记录来源与采集提交；修改分镜只改 `storyboard.json`，再重新生成全部产物。GitHub README 直接嵌入动画 SVG（`<img>` 中 CSS 动画可播放，系统设置减少动态时显示静态总结），并链接 MP4 与网页预览。

## 8. 基准截图

1440 × 900 @1.5×（窄屏 390 × 844 @2×），浅色为主，另附深色与窄屏各一：

| 文件 | 内容 |
|---|---|
| `landing.png` / `landing-dark.png` | 项目首页（浅 / 深） |
| `models.png` | 模型工作台：订单处理模型结构图 |
| `scenarios.png` | 场景：仓储同步批次（参与者视图、轮次） |
| `strategies.png` | 策略注册表 |
| `runs.png` | 实验列表与启动表单 |
| `run-batch.png` / `run-batch-dark.png` / `run-narrow.png` | 运行台：同步批次（浅 / 深 / 390 px） |
| `run-batch-step.png` | 运行台整页：步骤详情（规划器输入、证据等级、执行前决策位置） |
| `run-orders.png` | 运行台：订单延迟响应的对账 |
| `evidence-orders.png` | 证据与回放：会话环境的快照说明 |
| `benchmarks.png` / `benchmarks-reused.png` | 基准对比与复用单元格 |

视觉微调流程：改 tokens 或样式 → 重新生成 CSS → 重新截图 → 在本表对应行说明原因（例如 1.0.1 的对比度修正）→ 用新截图替换 Figma Screens 页的图片（`upload_assets` 指定原节点）。

## 9. Figma 同步状态（2026-09-30）

| 页面 | 内容 | 与代码的关系 |
|---|---|---|
| Cover | 标志、定位、同步状态 | — |
| Foundations | 颜色 / 字体 / 间距 / 圆角 / 阴影与动效，浅色与深色各一帧（色块绑定变量） | 变量 = tokens.json 1.0.1 |
| Components | Icon/*（20）、Button、StatusBadge、EvidenceTag、ParticipantChip、NavItem（变体绑定变量，描述写明代码组件） | 组件描述 ↔ `ui.tsx` / `styles.css` / `icons.tsx` |
| Screens | 14 张已实现界面的真实截图，标注路由与构成组件 | 由 `capture_screens.py` 生成 |
| Charts & model graph | 模型结构图、步骤时间线、指标柱状图、批次行、比较中的证据等级 | 与第 4 节一致 |
| Motion storyboard | 5 个场景的真实帧、时序、字幕与动效说明，封面 | 与 `storyboard.json` 一致 |

同步方向是代码 → Figma。视频由本地 Chromium + ffmpeg 从同一 SVG 导出（Figma 的视频导出只接受 Figma 时间线，不能渲染这份 SVG，因此不使用），SVG 与视频不会分叉。

## 10. 后续集成如何扩展

- 新插件的标签、值、指标名写在插件描述符 `ui`（`state_labels`、`action_labels`、`action_display`、`metric_labels`、`value_labels`、`condition_labels`）；平台负责渲染，不在核心 UI 写领域词。
- 新结论或状态：复用 `.badge` 的五种语气与符号，不新增颜色；新证据来源：映射到四个证据等级之一。
- 新参与者、系列：自动取 `p1…p8`；超过 8 个时循环并以名称区分。
- 新组件：先用已有 tokens 与组件组合；确需新组件时沿用 16 px 图标、`radius-md` / `lg`、4 px 间距与 `--dur-*` 动效，并在 Figma Components 页补一个同名组件与代码描述。
