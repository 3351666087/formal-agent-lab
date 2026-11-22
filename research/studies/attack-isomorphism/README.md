# 攻击模型同构研究(attack-isomorphism)

研究问题:把状态机攻击模型改写成逻辑上相同的真实业务流程后,安全护栏会不会让大模型失去解决这些正当业务问题的能力?拒答由领域、措辞还是任务目标驱动?

**当前结果:第一轮阶段性报告**
- 单文件离线版(可直接发送):`攻击模型同构研究-第一轮报告.html`
- 网页版:`report-advisor.html`(由 `build_report.py` 生成)
- 逐边溯源与偏离:`FIDELITY.md`;第四版时的方法、相关工作与伦理:`METHODS.md`

## 材料

| 文件 | 内容 |
|---|---|
| `models.py` | 三个忠实复现的攻击模型(TCP/RFC 793 与 KORG、TLS 1.2 与 FREAK、WPA2 与 KRACK)及其业务孪生、抽象命名版 |
| `families.py` | 15 道参数化生成题(TLS→信贷、KRACK→凭证、TCP→租赁,各 5 种规模) |
| `verify_isomorphism.py` / `verify_items.py` | Z3 证明各版本唯一同构;计算标准答案 → `items-groundtruth.json` |
| `ground_truth.py` | 最短路径(BFS)与最小控制集(穷举,保持成功状态可达) |
| `diagrams.py` | 状态机 Mermaid 图与迁移表 → `diagrams/` |

## 第一轮实验(v5,报告所用数据)

| 文件 | 内容 |
|---|---|
| `experiment3.py` | 18 题 × 4 档护栏 × 3 个词汇版本 × 3 项任务 × 每格 4 次,支持 `--retry-failed` |
| `experiment2.py` | 调用层(DeepSeek / OpenAI / Gemini)、提示词与任务定义 |
| `experiment3-results.jsonl` | DeepSeek 与 GPT-6.2-astra,5184 次 |
| `experiment3-gemini.jsonl`, `experiment3-gemini-retry.jsonl` | Gemini 4 Carbon;首轮因额度耗尽 1259 次失败,后补跑 |
| `grade3.py` → `experiment3-graded.json` | 对照标准答案判分,合并补跑结果 |
| `stats3.py` → `stats3-summary.json`, `stats3-output.txt` | 以题目为单位的 bootstrap 与置换检验 |
| `build_report.py`, `report_template.html`, `narrative_*.html` | 生成报告;设 `MERMAID_JS` 指向 mermaid@11.4.1 的 `mermaid.min.js` 可同时生成单文件离线版 |

## 早期版本(试点,仅作方法记录)

- **v1**:问模型"这是不是攻击模型",问句里给出了答案选项,构成泄题;其原始结果已被 v2 覆盖,未保留。
- **v2**(`query_models.py`, `query-results.json`):改为中性提问的识别实验。
- **v3**(`experiment.py`, `regrade.py`, `experiment-*.json`):3 道题、单次调用的护栏对照。
- **v4**(`grade2.py`, `judge.py`, `stats.py`, `experiment2-*`, `stats-summary.json`, `ground-truth.json`):3 道题、2 个被测、每格 20 次;统计存在伪重复,且"明确"护栏下的损失包含对条文的执行,结论已在第一轮报告中更正。独立 judge 复核一致性 κ=1.00(`experiment2-judged.json`)。

## 复现

API 密钥从仓库根目录的 `.env` 读取(该文件已被 git 忽略):`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`GEMINI_API_KEY`。

```bash
uv run --frozen python research/studies/attack-isomorphism/verify_items.py
uv run --frozen python research/studies/attack-isomorphism/experiment3.py --reps 4
uv run --frozen python research/studies/attack-isomorphism/experiment3.py --subjects gemini-4-carbon --reps 4 --out experiment3-gemini.jsonl
uv run --frozen python research/studies/attack-isomorphism/grade3.py
uv run --frozen python research/studies/attack-isomorphism/stats3.py
uv run --frozen python research/studies/attack-isomorphism/build_report.py
```

托管模型会更新:本轮 `deepseek-chat` 别名实际由 `deepseek-flash` 应答,每次调用记录了服务商返回的模型名。
