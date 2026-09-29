import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import { get, post, type MatrixReport, type MatrixSummary, type Scenario, type Strategy } from "../api";
import { Icon } from "../icons";
import { Empty, fmtNum, fmtTime, InlineError, KV, Loading, Modal, QueryState, StatusBadge, PageHead } from "../ui";
import { ReportV2, V2Fields } from "../components/MatrixV2";

export function BenchmarksPage() {
  const { pid, mid } = useParams();
  const navigate = useNavigate();
  const matrices = useQuery({ queryKey: ["matrices", pid], queryFn: () => get<MatrixSummary[]>(`/projects/${pid}/matrices`),
    refetchInterval: 4000 });
  const [creating, setCreating] = useState(false);
  return (
    <>
      <PageHead area="基准" icon="benchmark" title="基准对比"
        description="同场景 / 预算 / 种子下比较策略：指标带单位、方向、样本数、缺失值与区间方法；显著性只在统计条件满足时报告。同一完整配置的单元格被复用并标明来源。"
        actions={<button className="btn primary" onClick={() => setCreating(true)}>新建矩阵</button>} />
      <div className="split">
        <div className="card">
          <div className="card-head"><h2 className="grow">矩阵</h2></div>
          <QueryState q={matrices} empty={<Empty title="还没有矩阵" hint="新建一个场景 × 策略 × 种子矩阵，或用 fal matrix run / Inspect 导入。" />}>
            {(list) => (
              <div className="nav" style={{ padding: 6 }}>
                {list.map((m) => (
                  <Link key={m.id} to={`/p/${pid}/benchmarks/${m.id}`} className={m.id === mid ? "active" : ""}>
                    <span className="ellipsis" style={{ flex: 1 }}>{m.name}</span>
                    {m.spec.source === "inspect" && <span className="badge info">Inspect</span>}
                    <span className="num">{m.runs}</span>
                  </Link>
                ))}
              </div>
            )}
          </QueryState>
        </div>
        {mid ? (matrices.data?.find((m) => m.id === mid)?.spec.version === 2
          ? <ReportV2 key={mid} mid={mid} pid={pid!} /> : <Report key={mid} mid={mid} pid={pid!} />)
          : <div className="card"><Empty title="选择一个矩阵查看对比报告" /></div>}
      </div>
      {creating && <CreateMatrix pid={pid!} onClose={() => setCreating(false)} onCreated={(id) => { setCreating(false); navigate(`/p/${pid}/benchmarks/${id}`); }} />}
    </>
  );
}

function CreateMatrix({ pid, onClose, onCreated }: { pid: string; onClose: () => void; onCreated: (id: string) => void }) {
  const scenarios = useQuery({ queryKey: ["scenarios", pid], queryFn: () => get<Scenario[]>(`/projects/${pid}/scenarios`) });
  const strategies = useQuery({ queryKey: ["strategies", pid], queryFn: () => get<Strategy[]>(`/projects/${pid}/strategies`) });
  const [sc, setSc] = useState<string[]>([]);
  const [st, setSt] = useState<string[]>([]);
  const [seeds, setSeeds] = useState("1,2,3");
  const [budgets, setBudgets] = useState("");
  const [name, setName] = useState("矩阵");
  const [queued, setQueued] = useState(true);
  const [v2, setV2] = useState<Record<string, any>>({ dev: "1", acceptance: "2,3,4", max_parallel: 2, ablations: "" });
  const csv = (x: string) => String(x).split(",").map((s) => s.trim()).filter(Boolean).map(Number);
  const toggle = (xs: string[], x: string) => (xs.includes(x) ? xs.filter((y) => y !== x) : [...xs, x]);
  const seedList = seeds.split(",").map((s) => s.trim()).filter(Boolean).map(Number);
  const budgetList = budgets.split(",").map((s) => s.trim()).filter(Boolean).map((b) => ({ max_steps: Number(b) }));
  let ablations: unknown[] = [{}];
  try { if (v2.ablations.trim()) ablations = [{}, ...JSON.parse(v2.ablations)]; } catch { ablations = [{}]; }
  const v2Seeds = csv(v2.dev).length + csv(v2.acceptance).length;
  const total = queued ? sc.length * st.length * v2Seeds * Math.max(1, budgetList.length) * ablations.length
    : sc.length * st.length * seedList.length * Math.max(1, budgetList.length);
  const create = useMutation({
    mutationFn: () => post<{ matrix: MatrixSummary }>(`/projects/${pid}/matrices`, queued
      ? { version: 2, name, scenarios: sc, participants: st.map((id) => ({ "*": id })),
          seeds: { dev: csv(v2.dev), acceptance: csv(v2.acceptance) }, budgets: budgetList.length ? budgetList : null,
          ablations, max_parallel: v2.max_parallel }
      : { name, scenarios: sc, strategies: st, seeds: seedList, budgets: budgetList.length ? budgetList : null }),
    onSuccess: (r) => onCreated(r.matrix.id),
  });
  return (
    <Modal title="新建实验矩阵" onClose={onClose} footer={<>
      <span className="muted small" style={{ marginRight: "auto" }}>将创建 {total} 个实验</span>
      <button className="btn" onClick={onClose}>取消</button>
      <button className="btn primary" disabled={!total || total > 600 || create.isPending} onClick={() => create.mutate()}><Icon name="play" />创建并运行</button></>}>
      <label className="field"><span>名称</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
      <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}><legend className="small muted">场景</legend>
        <div className="chip-list">{scenarios.data?.map((s) => (
          <label key={s.id} className="badge" style={{ cursor: "pointer" }}><input type="checkbox" checked={sc.includes(s.id)} onChange={() => setSc(toggle(sc, s.id))} />{s.name}</label>))}</div></fieldset>
      <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}><legend className="small muted">策略</legend>
        <div className="chip-list">{strategies.data?.map((s) => (
          <label key={s.id} className={`badge ${s.config.client === "stub" ? "warn" : ""}`} style={{ cursor: "pointer" }}>
            <input type="checkbox" checked={st.includes(s.id)} onChange={() => setSt(toggle(st, s.id))} />{s.name}</label>))}</div></fieldset>
      <label className="row small"><input type="checkbox" checked={queued} onChange={(e) => setQueued(e.target.checked)} />
        单元队列（v2）：固定开发 / 验收种子划分、并发上限、可中断续跑、失败重跑与增量合并</label>
      {queued && <V2Fields value={v2} onChange={setV2} />}
      <div className="form-grid">
        {!queued && <label className="field"><span>种子（逗号分隔）</span><input value={seeds} onChange={(e) => setSeeds(e.target.value)} /></label>}
        <label className="field"><span>步数预算变体（可选，逗号分隔）</span><input value={budgets} placeholder="场景默认" onChange={(e) => setBudgets(e.target.value)} /></label>
      </div>
      <InlineError error={create.error} />
    </Modal>
  );
}

function Report({ mid, pid }: { mid: string; pid: string }) {
  const report = useQuery({ queryKey: ["matrix-report", mid], queryFn: () => get<MatrixReport>(`/matrices/${mid}/report`),
    refetchInterval: (q) => (q.state.data && !q.state.data.complete ? 3000 : false) });
  const [metric, setMetric] = useState<string>("");
  if (report.isPending) return <div className="card"><Loading label="生成报告…" /></div>;
  if (report.isError) return <div className="card"><Empty title="报告不可用" hint={String(report.error)} /></div>;
  // a v2 matrix report (the matrix list may not know the new matrix yet): the report's own shape decides
  if ("splits" in (report.data as object)) return <ReportV2 mid={mid} pid={pid} />;
  const r = report.data;
  const defs = r.definitions;
  const chosen = metric || (defs.find((d) => d.metric_id === "delay_cost") ?? defs[0])?.metric_id;
  const def = defs.find((d) => d.metric_id === chosen);
  const inspect = r.matrix.spec.inspect as Record<string, unknown> | undefined;
  const stub = r.aggregates.some((a) => a.source_kinds.includes("LLM_STUB"));
  return (
    <div className="stack">
      <div className="card">
        <div className="card-head"><h2 className="grow">{r.matrix.name}</h2>
          {r.complete ? <span className="badge ok">全部完成</span> : <span className="badge warn"><span className="dot live" />运行中</span>}
          {Object.entries(r.matrix.statuses).map(([s, n]) => <span key={s}><StatusBadge status={s} /> ×{n}</span>)}</div>
        <div className="card-body stack">
          <KV items={[["来源", r.matrix.spec.source === "inspect" ? "Inspect 评测导入" : "平台矩阵"], ["创建", fmtTime(r.matrix.created_at)],
            ["实验数", String(r.cells.length)],
            ...(inspect ? [["Inspect", `${String(inspect.task)} · model ${String(inspect.model)}（${String(inspect.note ?? "")}）`] as [string, string]] : [])]} />
          {stub && <div className="callout warn small">包含 LLM 替身（LLM_STUB）结果：它们不是真实模型输出，请与真实模型结果分开解读。</div>}
          <label className="row small">指标<select value={chosen} onChange={(e) => setMetric(e.target.value)}>
            {defs.map((d) => <option key={d.metric_id} value={d.metric_id}>{d.label}（{d.unit}，{d.direction === "LOWER_IS_BETTER" ? "越低越好" : d.direction === "HIGHER_IS_BETTER" ? "越高越好" : "无方向"}）</option>)}</select></label>
        </div>
      </div>
      {def && <MetricChart report={r} metric={def.metric_id} unit={def.unit} />}
      <div className="card">
        <div className="card-head"><h3 className="grow">聚合（{def?.label}）</h3><span className="small muted">{def?.aggregation}</span></div>
        <div className="table-wrap">
          <table className="table wide">
            <thead><tr><th>场景</th><th>策略</th><th>预算</th><th className="num">值</th><th>区间</th><th className="num">n</th><th className="num">缺失</th><th className="num">不适用</th><th>来源</th></tr></thead>
            <tbody>{r.aggregates.map((a, i) => {
              const m = a.metrics[chosen!];
              return <tr key={i}><td>{a.scenario_label}</td><td>{a.strategy_label}</td><td className="small">{a.budget}</td>
                <td className="num">{m?.result.value !== null && m?.result.value !== undefined ? fmtNum(m.result.value, 3) : <span className="badge" title={m?.result.missing_reason ?? ""}>缺失</span>}</td>
                <td className="small tight">{m?.result.ci ? `[${fmtNum(m.result.ci.low)}, ${fmtNum(m.result.ci.high)}]` : <span className="muted" title={m?.notes.ci_note}>—</span>}</td>
                <td className="num">{m?.result.sample_size ?? 0}</td><td className="num">{m?.notes.missing ?? 0}</td><td className="num">{m?.notes.not_applicable ?? 0}</td>
                <td>{a.source_kinds.map((k) => <span key={k} className={`badge ${k === "LLM_STUB" ? "warn" : ""}`}>{k}</span>)}</td></tr>;
            })}</tbody>
          </table>
        </div>
        <div className="card-body small muted">{Object.values(r.methods).join("；")}</div>
      </div>
      <div className="card">
        <div className="card-head"><h3 className="grow">配对比较（{def?.label}）</h3></div>
        <div className="table-wrap">
          <table className="table wide">
            <thead><tr><th>A</th><th>B</th><th className="num">配对数</th><th className="num">未配对</th><th className="num">B−A 均值</th><th>区间</th><th>更优</th><th>显著性</th></tr></thead>
            <tbody>{r.comparisons.filter((c) => c.metric_id === chosen).map((c, i) => (
              <tr key={i}><td className="tight">{c.a}</td><td className="tight">{c.b}</td><td className="num">{c.n_pairs}</td><td className="num">{c.unpaired}</td>
                <td className="num">{fmtNum(c.mean_diff_b_minus_a, 3)}</td>
                <td className="small tight">{c.ci ? `[${fmtNum(c.ci.low)}, ${fmtNum(c.ci.high)}]` : "—"}</td>
                <td className="tight">{c.better ?? <span className="muted">持平</span>}</td>
                <td className="small">{c.test.reported ? <span className={`badge ${c.test.significant ? "ok" : ""}`} title={c.test.method}>p={fmtNum(c.test.p_value, 4)}</span>
                  : <span className="muted">{c.test.reason ?? "未报告"}</span>}</td></tr>))}</tbody>
          </table>
        </div>
      </div>
      <details className="card pad"><summary><strong>全部实验（{r.cells.length}）</strong></summary>
        <div className="table-wrap tall" style={{ marginTop: 8 }}>
          <table className="table wide"><thead><tr><th>场景</th><th>策略</th><th className="num">种子</th><th>预算</th><th>状态</th><th>实验</th></tr></thead>
            <tbody>{r.cells.map((c) => (
              <tr key={c.run_id}><td className="small">{c.scenario}</td><td className="small">{c.strategy}</td><td className="num">{c.seed}</td>
                <td className="small">{c.budget}</td><td><StatusBadge status={c.status} /></td>
                <td><Link to={`/p/${pid}/runs/${c.run_id}`}><code className="small">{c.run_id.slice(0, 14)}</code></Link></td></tr>))}</tbody></table>
        </div>
      </details>
    </div>
  );
}

function MetricChart({ report, metric, unit }: { report: MatrixReport; metric: string; unit: string }) {
  const groups = useMemo(() => {
    const byScenario = new Map<string, MatrixReport["aggregates"]>();
    report.aggregates.forEach((a) => byScenario.set(a.scenario_label, [...(byScenario.get(a.scenario_label) ?? []), a]));
    return [...byScenario.entries()];
  }, [report]);
  const strategies = [...new Set(report.aggregates.map((a) => a.strategy_label))];
  // series use the categorical palette (design/tokens.json participant): status colours are reserved for states
  const palette = ["var(--p1)", "var(--p2)", "var(--p3)", "var(--p4)", "var(--p5)", "var(--p6)", "var(--p7)", "var(--p8)"];
  const vals = report.aggregates.flatMap((a) => { const m = a.metrics[metric]?.result; return m ? [m.value ?? 0, m.ci?.high ?? 0] : []; });
  const max = Math.max(1e-9, ...vals);
  const BW = 28, GAP = 28, H = 180, LEFT = 44, MIN_GROUP = 120;
  const groupWidth = (n: number) => Math.max(n * BW, MIN_GROUP);
  const width = LEFT + groups.reduce((w, [, xs]) => w + groupWidth(xs.length) + GAP, 0) + 10;
  const fit = (label: string, px: number) => { const n = Math.floor(px / 12); return label.length > n ? label.slice(0, n - 1) + "…" : label; };
  let x = LEFT;
  return (
    <div className="card">
      <div className="card-head"><h3 className="grow">按场景 × 策略（{unit}；须线为区间）</h3>
        <div className="legend">{strategies.map((s, i) => <span key={s}><i className="dot" style={{ background: palette[i % palette.length] }} />{s}</span>)}</div></div>
      <div className="card-body svg-wrap">
        <svg width={width} height={H + 50} role="img" aria-label="指标柱状图">
          {[0, 0.5, 1].map((t) => <g key={t}><line x1={LEFT - 4} x2={width} y1={10 + H * (1 - t)} y2={10 + H * (1 - t)} stroke="var(--border)" />
            <text x={LEFT - 8} y={14 + H * (1 - t)} textAnchor="end" fontSize="10" fill="var(--muted)">{fmtNum(max * t, 1)}</text></g>)}
          {groups.map(([label, xs]) => {
            const start = x;
            const gw = groupWidth(xs.length);
            x += (gw - xs.length * BW) / 2; // centre the bars in the group slot
            const bars = xs.map((a) => {
              const m = a.metrics[metric]?.result;
              const i = strategies.indexOf(a.strategy_label);
              const bx = x; x += BW;
              if (!m || m.value === null) return <g key={a.strategy + a.budget}><rect x={bx + 3} y={10 + H - 14} width={BW - 6} height={14} fill="none" stroke="var(--border-strong)" strokeDasharray="3 2" />
                <text x={bx + BW / 2} y={10 + H - 18} fontSize="9" textAnchor="middle" fill="var(--muted)">缺失</text></g>;
              const h = (m.value / max) * H;
              return <g key={a.strategy + a.budget}><rect x={bx + 3} y={10 + H - h} width={BW - 6} height={h} fill={palette[i % palette.length]} opacity={0.85}>
                <title>{`${a.strategy_label}: ${fmtNum(m.value, 3)} (n=${m.sample_size})`}</title></rect>
                {m.ci && <><line x1={bx + BW / 2} x2={bx + BW / 2} y1={10 + H - (m.ci.high / max) * H} y2={10 + H - (m.ci.low / max) * H} stroke="var(--text)" />
                  <line x1={bx + BW / 2 - 4} x2={bx + BW / 2 + 4} y1={10 + H - (m.ci.high / max) * H} y2={10 + H - (m.ci.high / max) * H} stroke="var(--text)" />
                  <line x1={bx + BW / 2 - 4} x2={bx + BW / 2 + 4} y1={10 + H - (m.ci.low / max) * H} y2={10 + H - (m.ci.low / max) * H} stroke="var(--text)" /></>}</g>;
            });
            x = start + gw + GAP;
            return <g key={label}>{bars}<text x={start + gw / 2} y={H + 28} fontSize="11" textAnchor="middle" fill="var(--text-2)">
              {fit(label, gw)}<title>{label}</title></text></g>;
          })}
        </svg>
      </div>
    </div>
  );
}
