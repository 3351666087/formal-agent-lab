// Benchmarks for v2 matrices (P2-094 / P2-080 … P2-085): configuration filters, paired sample counts, the
// distribution of failures / goals not reached / missing metrics with the real denominators, cost and task effect
// side by side, comparisons along one dimension at a time, the cell queue, and an export of exactly the current view.
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { get, post } from "../api";
import { Empty, fmtNum, InlineError, Loading, StatusBadge, useToast } from "../ui";

type M = Record<string, any>;
export interface MatrixReportV2 {
  splits: Record<string, { cells: number; outcomes: M; per_scenario: M[]; pooled: M[]; comparisons: M[] }>;
  definitions: { metric_id: string; label: string; unit: string; direction: string }[];
  metric_sources: Record<string, string>; conclusions: string[]; complete: boolean;
  matrix: { id: string; name: string; spec: M; statuses: Record<string, number> };
  cells: { cell_id: string; status: string; run_id: string | null; attempts: number; error: string | null; split: string;
    seed: number; labels: Record<string, string>; run_status: string | null }[];
}

const COST = ["delay_cost", "steps_used", "model_calls", "tokens", "wall_seconds", "makespan", "late_orders", "mean_latency"];
const EFFECT = ["goal_reached", "orders_completed", "effect_mismatches", "invalid_actions", "mean_tardiness"];

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

export function ReportV2({ mid, pid }: { mid: string; pid: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const report = useQuery({ queryKey: ["matrix-report", mid], queryFn: () => get<MatrixReportV2>(`/matrices/${mid}/report`),
    refetchInterval: (q) => (q.state.data && !q.state.data.complete ? 3000 : false) });
  const [split, setSplit] = useState("acceptance");
  const [f, setF] = useState<Record<string, string>>({});
  const control = useMutation({
    mutationFn: (a: "resume" | "rerun-failed" | "cancel") => post(`/matrices/${mid}/${a}`),
    onSuccess: (_r, a) => { toast({ resume: "队列已继续", "rerun-failed": "失败单元已重新排队", cancel: "矩阵已取消" }[a]);
      qc.invalidateQueries({ queryKey: ["matrix-report", mid] }); },
    onError: (e) => toast(String(e), "err"),
  });
  const r = report.data;
  const sec = r?.splits[split] ?? (r ? Object.values(r.splits)[0] : undefined);
  const dims = ["scenario", "participants", "backend", "rules", "model", "ablation"];
  const values = useMemo(() => Object.fromEntries(dims.map((d) => [d, [...new Set((sec?.per_scenario ?? []).map((x) => String(x[d])))]])), [sec]);
  const keep = (row: M) => dims.every((d) => !f[d] || String(row[d] ?? "") === f[d] || row[d] === undefined);
  const rows = (sec?.per_scenario ?? []).filter(keep);
  const pooled = (sec?.pooled ?? []).filter(keep);
  const defs = r?.definitions ?? [];
  const cost = defs.filter((d) => COST.includes(d.metric_id));
  const effect = defs.filter((d) => EFFECT.includes(d.metric_id) || d.metric_id.startsWith("probe."));
  const [costMetric, setCostMetric] = useState("");
  const [effectMetric, setEffectMetric] = useState("");
  const cm = costMetric || cost[0]?.metric_id;
  const em = effectMetric || effect[0]?.metric_id;
  const comps = (sec?.comparisons ?? []).filter((c) => [cm, em].includes(c.metric_id));
  if (report.isPending) return <div className="card"><Loading label="生成报告…" /></div>;
  if (report.isError || !r || !sec) return <div className="card"><Empty title="报告不可用" hint={String(report.error ?? "")} /></div>;
  const view = { matrix: r.matrix.id, split, filters: f, metrics: { cost: cm, effect: em }, outcomes: sec.outcomes,
    per_scenario: rows.map((x) => ({ ...x, metrics: { [cm]: x.metrics[cm], [em]: x.metrics[em] } })), pooled, comparisons: comps };
  const csvView = () => ["scenario,participants,backend,rules,model,ablation,metric,value,ci_low,ci_high,n,missing,source",
    ...rows.flatMap((x) => [cm, em].filter(Boolean).map((mid2) => { const m = x.metrics[mid2] ?? {};
      return [x.scenario, x.participants, x.backend, x.rules, x.model, x.ablation, mid2, m.value ?? "", m.ci?.low ?? "", m.ci?.high ?? "",
        m.n ?? 0, m.missing ?? 0, JSON.stringify(m.source ?? "")].join(","); }))].join("\n");
  const o = sec.outcomes;
  return (
    <div className="stack" data-testid="matrix-v2">
      <div className="card">
        <div className="card-head"><h2 className="grow">{r.matrix.name}</h2>
          {r.complete ? <span className="badge ok">全部完成</span> : <span className="badge warn"><span className="dot live" />队列运行中</span>}
          <button className="btn sm" onClick={() => control.mutate("resume")}>继续队列</button>
          <button className="btn sm" onClick={() => control.mutate("rerun-failed")}>重跑失败单元</button>
          <button className="btn sm danger" onClick={() => { if (confirm("取消矩阵？排队单元不再运行，运行中的实验在步边界结束。")) control.mutate("cancel"); }}>取消</button></div>
        <div className="card-body stack">
          <div className="row small">
            <label className="row">划分<select value={split} onChange={(e) => setSplit(e.target.value)} aria-label="划分">
              {Object.keys(r.splits).map((s) => <option key={s} value={s}>{s === "dev" ? "开发（dev）" : s === "acceptance" ? "验收（acceptance）" : s}</option>)}</select></label>
            {dims.map((d) => values[d]?.length > 1 && <label key={d} className="row">{d}<select value={f[d] ?? ""} aria-label={`筛选 ${d}`}
              onChange={(e) => setF({ ...f, [d]: e.target.value })}><option value="">全部</option>
              {values[d].map((v) => <option key={v} value={v}>{v}</option>)}</select></label>)}
          </div>
          <div className="row small">
            <label className="row">成本指标<select value={cm} onChange={(e) => setCostMetric(e.target.value)}>{cost.map((d) => <option key={d.metric_id} value={d.metric_id}>{d.label}</option>)}</select></label>
            <label className="row">任务效果<select value={em} onChange={(e) => setEffectMetric(e.target.value)}>{effect.map((d) => <option key={d.metric_id} value={d.metric_id}>{d.label}</option>)}</select></label>
            <span className="grow" />
            <button className="btn sm" onClick={() => download(`matrix-${mid}-view.json`, JSON.stringify(view, null, 2), "application/json")}>⤓ 当前视图 JSON</button>
            <button className="btn sm" onClick={() => download(`matrix-${mid}-view.csv`, csvView(), "text/csv")}>⤓ 当前视图 CSV</button>
            <a className="btn sm" href={`/api/v1/matrices/${mid}/report?format=md`} download>⤓ 完整报告 MD</a>
          </div>
        </div>
      </div>
      <div className="card pad stack" data-testid="outcome-distribution">
        <h3>结果分布（分母 {o.denominator_cells} 个单元）</h3>
        <div className="row small">{Object.entries(o.run_status as Record<string, number>).map(([s, n]) => <span key={s}><StatusBadge status={s} /> ×{n}</span>)}</div>
        <div className="small">已结束 {o.finished} · 运行失败/取消 {o.run_failed} · 未运行 {o.not_run} · 目标达成 {o.goal_reached} · 目标未达成 {o.goal_not_reached.length}
          · 指标缺失 {Object.entries(o.metric_missing as Record<string, number>).filter(([, n]) => n).map(([k, n]) => `${k} ${n}`).join("，") || "无"}</div>
        <ul className="small">{r.conclusions.filter((c) => c.startsWith(`[${split}]`)).map((c, i) => <li key={i}>{c}</li>)}</ul>
      </div>
      <div className="card">
        <div className="card-head"><h3 className="grow">逐场景（独立单位：场景内的一个种子）</h3></div>
        <div className="table-wrap"><table className="table wide" aria-label="逐场景汇总">
          <thead><tr><th>场景</th><th>方法</th><th>后端</th><th>规则</th><th>消融</th><th className="num">{cm}</th><th>区间</th><th className="num">{em}</th><th>区间</th><th className="num">n</th><th className="num">缺失</th></tr></thead>
          <tbody>{rows.map((x, i) => { const a = x.metrics[cm] ?? {}; const b = x.metrics[em] ?? {};
            return <tr key={i}><td className="small">{x.labels?.scenario ?? x.scenario}</td><td className="small">{x.participants}</td><td className="small">{x.backend}</td>
              <td className="small">{x.rules}</td><td className="small">{x.ablation}</td>
              <td className="num">{fmtNum(a.value, 3)}</td><td className="small">{a.ci ? `[${fmtNum(a.ci.low)}, ${fmtNum(a.ci.high)}]` : "—"}</td>
              <td className="num">{fmtNum(b.value, 3)}</td><td className="small">{b.ci ? `[${fmtNum(b.ci.low)}, ${fmtNum(b.ci.high)}]` : "—"}</td>
              <td className="num">{a.n ?? 0}</td><td className="num">{a.missing ?? 0}</td></tr>; })}</tbody></table></div>
      </div>
      <div className="card">
        <div className="card-head"><h3 className="grow">跨场景（场景为聚类单位的重采样区间）</h3></div>
        <div className="table-wrap"><table className="table wide" aria-label="跨场景汇总">
          <thead><tr><th>方法</th><th>后端</th><th>消融</th><th className="num">{cm}</th><th>区间</th><th className="num">{em}</th><th>区间</th><th className="num">场景数</th></tr></thead>
          <tbody>{pooled.map((x, i) => { const a = x.metrics[cm] ?? {}; const b = x.metrics[em] ?? {};
            return <tr key={i}><td className="small">{x.participants}</td><td className="small">{x.backend}</td><td className="small">{x.ablation}</td>
              <td className="num">{fmtNum(a.value, 3)}</td><td className="small">{a.ci ? `[${fmtNum(a.ci.low)}, ${fmtNum(a.ci.high)}]` : <span title={a.ci_note}>—</span>}</td>
              <td className="num">{fmtNum(b.value, 3)}</td><td className="small">{b.ci ? `[${fmtNum(b.ci.low)}, ${fmtNum(b.ci.high)}]` : "—"}</td>
              <td className="num">{a.clusters ?? 0}</td></tr>; })}</tbody></table></div>
      </div>
      <div className="card">
        <div className="card-head"><h3 className="grow">配对比较（每次只改变一个维度）</h3></div>
        <div className="table-wrap"><table className="table wide" aria-label="配对比较">
          <thead><tr><th>维度</th><th>指标</th><th>A</th><th>B</th><th className="num">配对数</th><th className="num">未配对</th><th className="num">B−A</th><th>区间</th><th>更优</th></tr></thead>
          <tbody>{comps.map((c, i) => <tr key={i}><td className="small">{c.kind}</td><td className="small">{c.metric_id}</td><td className="small">{c.a}</td><td className="small">{c.b}</td>
            <td className="num">{c.n_pairs}</td><td className="num">{c.unpaired}</td><td className="num">{fmtNum(c.mean_diff_b_minus_a, 3)}</td>
            <td className="small">{c.ci ? `[${fmtNum(c.ci.low)}, ${fmtNum(c.ci.high)}]` : "—"}</td><td className="small">{c.better ?? "—"}</td></tr>)}</tbody></table></div>
        <div className="card-body small muted">指标来源：{Object.entries(r.metric_sources).filter(([k]) => [cm, em].includes(k)).map(([k, v]) => `${k} ← ${v}`).join("；")}</div>
      </div>
      <details className="card pad"><summary><strong>单元队列（{r.cells.length}）</strong></summary>
        <div className="table-wrap tall" style={{ marginTop: 8 }}><table className="table wide" aria-label="单元">
          <thead><tr><th>单元</th><th>状态</th><th>划分</th><th className="num">种子</th><th>配置</th><th className="num">尝试</th><th>实验</th></tr></thead>
          <tbody>{r.cells.map((c) => <tr key={c.cell_id}><td><code className="small">{c.cell_id}</code></td>
            <td><span className={`badge ${c.status === "DONE" ? "ok" : c.status === "FAILED" ? "err" : ""}`} title={c.error ?? ""}>{c.status}</span></td>
            <td className="small">{c.split}</td><td className="num">{c.seed}</td>
            <td className="small">{c.labels.scenario} × {c.labels.participants} · {c.labels.backend} · {c.labels.ablation}</td>
            <td className="num">{c.attempts}</td>
            <td>{c.run_id ? <Link to={`/p/${pid}/runs/${c.run_id}`}><code className="small">{c.run_id.slice(0, 14)}</code></Link> : "—"}</td></tr>)}</tbody></table></div>
      </details>
      <InlineError error={control.error} />
    </div>
  );
}

export function V2Fields({ value, onChange }: { value: M; onChange: (v: M) => void }) {
  return (
    <div className="form-grid" data-testid="v2-fields">
      <label className="field"><span>开发种子（dev）</span><input value={value.dev} onChange={(e) => onChange({ ...value, dev: e.target.value })} /></label>
      <label className="field"><span>验收种子（acceptance）</span><input value={value.acceptance} onChange={(e) => onChange({ ...value, acceptance: e.target.value })} /></label>
      <label className="field"><span>并发</span><input type="number" min={1} max={8} value={value.max_parallel} onChange={(e) => onChange({ ...value, max_parallel: Number(e.target.value) })} /></label>
      <label className="field" style={{ gridColumn: "span 3" }}><span>消融（JSON 列表，可选；例：{'[{"label":"no-delay","env":{"observation":{"delay_steps":null}}}]'}）</span>
        <input value={value.ablations} onChange={(e) => onChange({ ...value, ablations: e.target.value })} /></label>
    </div>
  );
}
