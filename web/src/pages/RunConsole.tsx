import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import type { PluginDescriptor } from "@formal-lab/contracts";
import { get, post, TERMINAL, type CatalogEntry, type RunDetail, type VersionDetail } from "../api";
import { groupSteps, StateChart, StepDetail, Timeline } from "../components/Steps";
import { makeLabels } from "../labels";
import { useRunEvents } from "../sse";
import { Empty, ErrorState, fmtNum, fmtTime, KV, Loading, StatusBadge, Tabs, useToast } from "../ui";
import { CheckResult } from "./ModelWorkbench";

export function RunConsole() {
  const { pid, runId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const { events, state } = useRunEvents(runId);
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => get<RunDetail>(`/runs/${runId}`) });
  // refresh the run summary whenever new events arrive (status, usage, metrics)
  const lastSeq = events.at(-1)?.seq ?? 0;
  useEffect(() => { if (lastSeq) qc.invalidateQueries({ queryKey: ["run", runId] }); }, [lastSeq, qc, runId]);
  const labels = useRunLabels(run.data);
  const steps = useMemo(() => groupSteps(events).filter((s) => s.step > 0 || s.observation), [events]);
  const [selected, setSelected] = useState<number | null>(null);
  const [follow, setFollow] = useState(true);
  const [tab, setTab] = useState<"timeline" | "state" | "events">("timeline");
  const actionSteps = steps.filter((s) => s.step > 0);
  const lastStep = actionSteps.at(-1)?.step ?? 0;
  useEffect(() => { if (follow && lastStep) setSelected(lastStep); }, [follow, lastStep]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, select, textarea")) return;
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const idx = steps.findIndex((s) => s.step === selected);
      const next = steps[Math.min(steps.length - 1, Math.max(0, idx + (e.key === "ArrowRight" ? 1 : -1)))];
      if (next) { setFollow(false); setSelected(next.step); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps, selected]);

  const control = useMutation({
    mutationFn: (action: "pause" | "resume" | "cancel" | "rerun") => post<{ id: string; status: string }>(`/runs/${runId}/${action}`),
    onSuccess: (r, action) => {
      qc.invalidateQueries({ queryKey: ["run", runId] });
      if (action === "rerun") { toast("已创建重新运行"); navigate(`/p/${pid}/runs/${r.id}`); }
      else toast({ pause: "暂停请求已发送，将在下一个逻辑步边界生效", resume: "已继续", cancel: "取消请求已发送" }[action]);
    },
    onError: (e) => toast(String(e), "err"),
  });

  if (run.isPending) return <Loading />;
  if (run.isError) return <ErrorState error={run.error} retry={() => run.refetch()} />;
  const r = run.data;
  const m = r.manifest;
  const terminal = TERMINAL.has(r.status);
  const dims = (m.config.budget_dimensions as string[] | undefined) ?? ["steps", "wall_seconds"];
  const current = steps.find((s) => s.step === selected) ?? null;
  const initialCheck = steps.find((s) => s.step === 0)?.checks[0];
  return (
    <>
      <div className="page-head">
        <div className="grow">
          <div className="crumbs"><Link to={`/p/${pid}/runs`}>实验</Link><span>/</span><code>{r.id}</code></div>
          <h1 className="row" style={{ marginTop: 4 }}>{r.scenario_name} <StatusBadge status={r.status} /></h1>
          <p className="small">{r.status_reason ?? " "}</p>
        </div>
        <div className="row">
          <span className="small muted" role="status" aria-live="polite">
            <span className={`dot ${state === "live" ? "live" : ""}`} aria-hidden />{" "}
            {{ connecting: "连接中", live: "实时", reconnecting: "重连中…", ended: "已结束", error: "连接错误" }[state]} · {events.length} 事件
          </span>
          <button className="btn" disabled={r.status !== "RUNNING" || control.isPending} onClick={() => control.mutate("pause")}>⏸ 暂停</button>
          <button className="btn" disabled={!["PAUSED", "PAUSING"].includes(r.status) || control.isPending} onClick={() => control.mutate("resume")}>▶ 继续</button>
          <button className="btn danger" disabled={terminal || r.status === "CANCELLING" || control.isPending}
            onClick={() => { if (confirm("取消该实验？将保留已产生的证据。")) control.mutate("cancel"); }}>■ 取消</button>
          <button className="btn" disabled={!terminal || control.isPending} onClick={() => control.mutate("rerun")}>↻ 重新运行</button>
          <a className="btn" href={`/api/v1/runs/${r.id}/export`} download>⤓ 导出</a>
          <Link className="btn" to={`/p/${pid}/evidence/${r.id}`}>证据与回放</Link>
        </div>
      </div>
      {r.error && <div className="callout err small" role="alert"><strong>{r.error.code}</strong> {r.error.message}</div>}

      <div className="grid cols-3">
        <div className="card pad stack">
          <h3>配置（运行时固定）</h3>
          <KV items={[
            ["策略", <code className="small">{m.participants[0].strategy.plugin.plugin_id}@{m.participants[0].strategy.plugin.version}</code>],
            ["模型", <code className="small">{m.model.package_id}@v{m.model.version} · {m.model.digest.value.slice(0, 8)}</code>],
            ["场景", `r${m.scenario.revision} · ${m.scenario_digest.value.slice(0, 8)}`],
            ["种子", String(m.seed)],
            ["来源", r.source_run_id ? <Link to={`/p/${pid}/runs/${r.source_run_id}`}>重跑自 {r.source_run_id.slice(0, 12)}</Link> : r.imported ? "导入" : "—"],
            ["平台", `${m.platform.version}${m.platform.source_revision ? ` · ${m.platform.source_revision.slice(0, 8)}` : ""}`],
          ]} />
        </div>
        <div className="card pad stack">
          <h3>预算</h3>
          <Budget label="步数" used={r.usage.steps ?? 0} max={m.budget.max_steps} applies={dims.includes("steps")} />
          <Budget label="墙钟秒" used={r.usage.wall_seconds ?? 0} max={m.budget.max_wall_seconds} applies={dims.includes("wall_seconds")} />
          <Budget label="模型调用" used={r.usage.model_calls ?? 0} max={m.budget.max_model_calls} applies={dims.includes("model_calls")} />
          <Budget label="Tokens" used={r.usage.tokens ?? 0} max={m.budget.max_tokens} applies={dims.includes("tokens")} />
        </div>
        <div className="card pad stack">
          <h3>初始检查与结果</h3>
          {initialCheck ? <div className="small"><CheckSummary result={initialCheck.result} /></div> : <span className="muted small">无</span>}
          <div className="sep" />
          {Object.keys(r.metrics).length ? (
            <KV items={Object.entries(r.metrics).map(([k, v]) => [labels.metric(k),
              v.value !== null ? <span>{fmtNum(v.value)} {v.unit ? <span className="muted small">{v.unit}</span> : null}</span>
                : <span className="badge" title={v.status}>{v.status === "NOT_APPLICABLE" ? "不适用" : "缺失"}</span>])} />
          ) : <span className="muted small">{terminal ? "无指标" : "实验结束后计算指标"}</span>}
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <Tabs label="轨迹视图" value={tab} onChange={setTab} tabs={[{ id: "timeline", label: "时间线" }, { id: "state", label: "状态图表" }, { id: "events", label: "事件" }]} />
          <span className="grow" />
          <label className="row small"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />跟随最新步</label>
          <span className="small muted">键盘 <span className="kbd">←</span> <span className="kbd">→</span> 切换步骤</span>
        </div>
        <div className="card-body">
          {steps.length === 0 ? <Empty title={terminal ? "该实验没有步骤" : "等待第一步…"} /> : tab === "timeline"
            ? <Timeline steps={actionSteps} selected={selected} onSelect={(n) => { setFollow(false); setSelected(n); }} />
            : tab === "state" ? <StateChart steps={steps} labels={labels} selected={selected} onSelect={(n) => { setFollow(false); setSelected(n); }} />
            : <EventTable events={events} selected={selected} onSelect={(n) => { setFollow(false); setSelected(n); }} />}
        </div>
      </div>

      <div className="split">
        <div className="card">
          <div className="card-head"><h3 className="grow">步骤</h3></div>
          <div className="table-wrap" style={{ maxHeight: 560 }}>
            <table className="table" aria-label="步骤列表">
              <thead><tr><th className="num">步</th><th>动作</th><th>结果</th></tr></thead>
              <tbody>{steps.map((s) => (
                <tr key={s.step} className={`selectable ${selected === s.step ? "selected" : ""}`} tabIndex={0}
                  onClick={() => { setFollow(false); setSelected(s.step); }} onKeyDown={(e) => { if (e.key === "Enter") { setFollow(false); setSelected(s.step); } }}>
                  <td className="num">{s.step}</td>
                  <td className="small">{s.proposal ? labels.actionText(s.proposal.action as never) : s.step === 0 ? "初始观测" : "…"}</td>
                  <td className="nowrap">{s.outcome ? <span className={`badge ${s.outcome.status === "APPLIED" ? "ok" : "err"}`}>{s.outcome.status === "APPLIED" ? "施加" : "拒绝"}</span> : null}
                    {s.comparison?.verdict === "DIFFERENT" && <span className="badge err" title="效果与预期不符">≠</span>}</td>
                </tr>))}</tbody>
            </table>
          </div>
        </div>
        <div>{current ? <StepDetail data={current} labels={labels} /> : <div className="card"><Empty title="选择一个步骤查看输入、前提、判断与效果" /></div>}</div>
      </div>
      <div className="muted small">创建 {fmtTime(r.created_at)} · 开始 {fmtTime(r.started_at)} · 结束 {fmtTime(r.finished_at)}</div>
    </>
  );
}

function CheckSummary({ result }: { result: import("@formal-lab/contracts").BoundedCheckResult }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="stack">
      <div className="row"><span className="small">目标可达（≤{result.bound.max_steps} 步）</span>
        <button className="btn sm ghost" onClick={() => setOpen(!open)}>{open ? "收起" : "详情"}</button></div>
      <div className="small">{result.explanation}</div>
      {open && <CheckResult result={result} />}
    </div>
  );
}

function Budget({ label, used, max, applies }: { label: string; used: number; max?: number | null; applies: boolean }) {
  if (!applies) return <div className="row small"><span style={{ width: 70 }}>{label}</span><span className="badge" title="该运行类型不消耗此预算维度">不适用</span></div>;
  const pct = max ? Math.min(100, (used / max) * 100) : 0;
  return (
    <div className="stack" style={{ gap: 3 }}>
      <div className="row small"><span style={{ width: 70 }}>{label}</span><span className="mono">{fmtNum(used, 1)}{max ? ` / ${max}` : " / 不限"}</span></div>
      {max ? <div className={`meter ${pct > 90 ? "err" : pct > 70 ? "warn" : ""}`} role="meter" aria-valuemin={0} aria-valuemax={max} aria-valuenow={used} aria-label={label}><div style={{ width: `${pct}%` }} /></div> : null}
    </div>
  );
}

function EventTable({ events, selected, onSelect }: { events: import("@formal-lab/contracts").TraceEvent[]; selected: number | null; onSelect: (n: number) => void }) {
  return (
    <div className="table-wrap tall">
      <table className="table" aria-label="事件">
        <thead><tr><th className="num">seq</th><th>类型</th><th className="num">步</th><th>时间</th><th>因果父事件</th></tr></thead>
        <tbody>{events.map((e) => (
          <tr key={e.seq} className={`selectable ${e.logical_step === selected ? "selected" : ""}`} tabIndex={0}
            onClick={() => e.logical_step !== null && e.logical_step !== undefined && onSelect(e.logical_step)}>
            <td className="num">{e.seq}</td><td><code className="small">{e.event_type}</code></td><td className="num">{e.logical_step ?? "—"}</td>
            <td className="small nowrap">{new Date(e.wall_time).toLocaleTimeString()}</td>
            <td className="small mono">{e.causal_parents.map((p) => p.slice(4, 12)).join(", ") || "—"}</td></tr>))}</tbody>
      </table>
    </div>
  );
}

export function useRunLabels(run?: RunDetail) {
  const version = useQuery({
    queryKey: ["run-model", run?.manifest.model.digest.value], enabled: Boolean(run),
    queryFn: async () => {
      const models = await get<{ id: string; package_id: string }[]>(`/projects/${run!.project_id}/models`);
      for (const m of models) {
        try { const v = await get<VersionDetail>(`/models/${m.id}/versions/${run!.manifest.model.version}`);
          if (v.digest === run!.manifest.model.digest.value) return v; } catch { /* try next */ }
      }
      return null;
    },
    staleTime: 600_000,
  });
  const plugins = useQuery({ queryKey: ["plugins-all"], queryFn: () => get<CatalogEntry[]>("/plugins"), staleTime: 600_000 });
  return useMemo(() => {
    const pinned = new Set(run?.manifest.plugins.map((p) => `${p.plugin_id}@${p.version}`));
    const descs: PluginDescriptor[] = (plugins.data ?? []).map((p) => p.descriptor).filter((d) => pinned.has(`${d.plugin_id}@${d.version}`));
    return makeLabels(version.data?.package.ir ?? null, descs);
  }, [version.data, plugins.data, run]);
}
