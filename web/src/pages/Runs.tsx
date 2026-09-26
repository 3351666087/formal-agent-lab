import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import { get, post, TERMINAL, type RunSummary, type Scenario, type Strategy } from "../api";
import { Empty, fmtNum, fmtTime, InlineError, QueryState, shortId, StatusBadge } from "../ui";

const STATUSES = ["", "RUNNING", "PAUSED", "SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"];

export function RunsPage() {
  const { pid } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const runs = useQuery({
    queryKey: ["runs", pid, status], queryFn: () => get<RunSummary[]>(`/projects/${pid}/runs${status ? `?status=${status}` : ""}`),
    refetchInterval: (q) => (q.state.data?.some((r) => !TERMINAL.has(r.status)) ? 2000 : false),
  });
  const scenarios = useQuery({ queryKey: ["scenarios", pid], queryFn: () => get<Scenario[]>(`/projects/${pid}/scenarios`) });
  const strategies = useQuery({ queryKey: ["strategies", pid], queryFn: () => get<Strategy[]>(`/projects/${pid}/strategies`) });
  const [form, setForm] = useState({ scenario_id: "", strategy_config_id: "", seed: "", max_steps: "" });
  const start = useMutation({
    mutationFn: () => post<RunSummary>(`/projects/${pid}/runs`, {
      scenario_id: form.scenario_id, strategy_config_id: form.strategy_config_id || null,
      seed: form.seed === "" ? null : Number(form.seed), budget: form.max_steps ? { max_steps: Number(form.max_steps) } : null,
    }, { "Idempotency-Key": `ui-${crypto.randomUUID()}` }),
    onSuccess: (r) => navigate(`/p/${pid}/runs/${r.id}`),
  });
  return (
    <>
      <div className="page-head"><div className="grow"><h1>实验运行台</h1>
        <p>启动实验并实时查看事件、候选、检查与效果；运行由 Temporal 持久编排，刷新页面或断线后从最后一个事件继续。</p></div></div>
      <div className="card">
        <div className="card-head"><h2 className="grow">启动实验</h2></div>
        <div className="card-body stack">
          <div className="form-grid">
            <label className="field"><span>场景</span><select value={form.scenario_id} onChange={(e) => setForm({ ...form, scenario_id: e.target.value })}>
              <option value="">选择场景…</option>{scenarios.data?.map((s) => <option key={s.id} value={s.id}>{s.name} (r{s.revision})</option>)}</select></label>
            <label className="field"><span>策略</span><select value={form.strategy_config_id} onChange={(e) => setForm({ ...form, strategy_config_id: e.target.value })}>
              <option value="">场景默认策略</option>{strategies.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
            <label className="field"><span>种子</span><input type="number" placeholder="场景默认" value={form.seed} onChange={(e) => setForm({ ...form, seed: e.target.value })} /></label>
            <label className="field"><span>步数预算</span><input type="number" min={1} placeholder="场景默认" value={form.max_steps} onChange={(e) => setForm({ ...form, max_steps: e.target.value })} /></label>
          </div>
          <div className="row"><button className="btn primary" disabled={!form.scenario_id || start.isPending} onClick={() => start.mutate()}>
            {start.isPending ? "启动中…" : "▶ 启动"}</button>{scenarios.data?.length === 0 && <span className="muted small">项目中还没有场景。</span>}</div>
          <InlineError error={start.error} />
        </div>
      </div>
      <div className="card">
        <div className="card-head"><h2 className="grow">实验</h2>
          <label className="row small">状态<select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => <option key={s} value={s}>{s || "全部"}</option>)}</select></label></div>
        <QueryState q={runs} empty={<Empty title="没有符合条件的实验" />}>
          {(list) => (
            <div className="table-wrap">
              <table className="table wide">
                <thead><tr><th>实验</th><th>状态</th><th>场景</th><th>策略</th><th className="num">种子</th><th className="num">步</th>
                  <th className="num">延期成本</th><th className="num">目标</th><th>来源</th><th>创建</th></tr></thead>
                <tbody>{list.map((r) => (
                  <tr key={r.id} className="selectable" tabIndex={0} onClick={() => navigate(`/p/${pid}/runs/${r.id}`)}
                    onKeyDown={(e) => { if (e.key === "Enter") navigate(`/p/${pid}/runs/${r.id}`); }}>
                    <td><Link to={`/p/${pid}/runs/${r.id}`} onClick={(e) => e.stopPropagation()}><code>{shortId(r.id)}</code></Link></td>
                    <td><StatusBadge status={r.status} /></td>
                    <td className="tight">{r.scenario_name}</td>
                    <td className="small"><code>{r.strategy?.plugin_id.replace("formal-lab.", "")}</code></td>
                    <td className="num">{r.seed}</td>
                    <td className="num">{r.last_step}</td>
                    <td className="num">{fmtNum(r.metrics.delay_cost?.value)}</td>
                    <td className="num">{r.metrics.goal_reached ? fmtNum(r.metrics.goal_reached.value) : "—"}</td>
                    <td className="small">{r.imported ? <span className="badge outline">导入</span> : r.source_run_id ? <span className="badge outline">重跑</span> : r.matrix_id ? <span className="badge outline">矩阵</span> : ""}</td>
                    <td className="nowrap small">{fmtTime(r.created_at)}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
        </QueryState>
      </div>
    </>
  );
}
