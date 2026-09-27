// Run-console panels for the phase-2 kernel (P2-092): participants and whose turn it is, each participant's task
// plan progress, environment operations (with review of abnormal ones), the environment session and independent
// probes, and every recovery / coordination event. Everything is read from the run's persisted events and records.
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { TraceEvent } from "@formal-lab/contracts";
import { get, post, type RunDetail } from "../api";
import { fmtNum, fmtTime, StatusBadge, useToast } from "../ui";

type Payload = Record<string, any>;
const RECOVERY_TYPES = new Set(["RECOVERY", "OPERATION_RECONCILED", "OPERATION_REVIEW", "RUN_PAUSING", "RUN_PAUSED",
  "RUN_RESUMED", "RUN_CANCELLING", "OBSERVATION_REQUESTED", "MODEL_REVISION_SUGGESTED", "REGRESSION_CASE_CREATED"]);

export interface OperationRow {
  operation_id: string; step: number; actor_id: string | null; state: string; needs_review: boolean;
  attempts: number; action: { action_type: string; params: Record<string, unknown> };
  transitions: { state: string; reason: string; at: string }[]; review: { status: string; note: string; by: string } | null;
  reconciliation: { method: string; found: boolean; note: string } | null;
}

export function ControlBanner({ run }: { run: RunDetail }) {
  const text: Record<string, string> = {
    PAUSING: "正在暂停：当前逻辑步完成后生效，已产生的事件与计划进度都会保留。",
    PAUSED: "已暂停：点击“继续”从下一步恢复（轮次、计划检查点与操作账本都已持久化）。",
    CANCELLING: "正在取消：当前步完成后结束，不会中断正在执行的环境操作。",
    QUEUED: "已排队：等待 Worker 接手。",
  };
  if (!text[run.status]) return null;
  return <div className="callout small" role="status" aria-live="polite" data-testid="control-banner">
    <StatusBadge status={run.status} /> {text[run.status]} {run.status_reason ? <span className="muted">（{run.status_reason}）</span> : null}
  </div>;
}

export function ParticipantsPanel({ run, events }: { run: RunDetail & { participants?: Payload[]; turn?: Payload; actor_usage?: Payload }; events: TraceEvent[] }) {
  const lastTurn = useMemo(() => [...events].reverse().find((e) => e.event_type === "TURN_STARTED"), [events]);
  const current = lastTurn?.actor_id ?? null;
  const plans = useMemo(() => {
    const out: Record<string, Payload> = {};
    for (const e of events) {
      if (e.event_type === "PLANNER_CHECKPOINT" && e.actor_id) out[e.actor_id] = { ...(out[e.actor_id] ?? {}), cp: e.payload };
      if (e.event_type === "PLAN_UPDATED" && e.actor_id) out[e.actor_id] = { ...(out[e.actor_id] ?? {}), plan: (e.payload as Payload).plan };
    }
    return out;
  }, [events]);
  const participants = run.participants ?? run.manifest.participants.map((p) => ({ actor_id: p.actor_id, strategy: p.strategy.plugin }));
  const turn = (lastTurn?.payload as Payload | undefined)?.turn ?? run.turn;
  return (
    <div className="card pad stack" data-testid="participants-panel">
      <div className="row"><h3 className="grow">参与者与计划</h3>
        {turn && <span className="small muted">全局步 {turn.global_step ?? "—"} · 第 {turn.round ?? "—"} 轮</span>}</div>
      {participants.map((p: Payload) => {
        const usage = run.actor_usage?.[p.actor_id] ?? {};
        const plan = plans[p.actor_id]?.plan;
        const progress: Record<string, number> = plans[p.actor_id]?.cp?.progress ?? {};
        const total = Object.values(progress).reduce((a, b) => a + (typeof b === "number" ? b : 0), 0);
        const done = typeof progress.DONE === "number" ? progress.DONE : 0;
        return (
          <div key={p.actor_id} className={`stack participant ${p.actor_id === current ? "current" : ""}`} style={{ gap: 4 }}>
            <div className="row small">
              <strong>{p.actor_id}</strong>{p.actor_id === current && <span className="badge accent">当前轮次</span>}
              <code className="small muted">{p.strategy?.plugin_id}</code>
              <span className="grow" /><span className="mono">{usage.steps ?? 0} 步 · 模型 {usage.model_calls ?? 0}/{usage.model_attempts ?? 0} 次</span>
            </div>
            {plan ? <>
              <div className="small">计划 v{plan.version}（{plan.generator?.kind}）· 修订原因 {plan.revision?.trigger ?? "—"}
                {plan.revision?.detail ? <span className="muted"> — {String(plan.revision.detail).slice(0, 80)}</span> : null}</div>
              {total > 0 && <div className="meter" role="meter" aria-label={`${p.actor_id} 计划进度`} aria-valuemin={0}
                aria-valuemax={total} aria-valuenow={done}><div style={{ width: `${(done / total) * 100}%` }} /></div>}
              <div className="small muted">{Object.entries(progress).map(([k, v]) => `${k} ${v}`).join(" · ")}</div>
            </> : <div className="small muted">该策略没有任务计划</div>}
          </div>);
      })}
    </div>
  );
}

export function OperationsPanel({ runId }: { runId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const ops = useQuery({ queryKey: ["operations", runId], queryFn: () => get<OperationRow[]>(`/runs/${runId}/operations`),
    refetchInterval: 5000 });
  const [open, setOpen] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("CONFIRMED_APPLIED");
  const review = useMutation({
    mutationFn: (opId: string) => post(`/operations/${encodeURIComponent(opId)}/review`, { status, note, by: "web" }),
    onSuccess: () => { toast("复核已记录（写入运行事件）"); setOpen(null); setNote(""); qc.invalidateQueries({ queryKey: ["operations", runId] }); },
    onError: (e) => toast(String(e), "err"),
  });
  const rows = ops.data ?? [];
  const counts: Record<string, number> = {};
  rows.forEach((o) => { counts[o.state] = (counts[o.state] ?? 0) + 1; });
  const abnormal = rows.filter((o) => o.needs_review || o.state === "FAILED" || o.transitions.some((t) => t.state === "OUTCOME_UNKNOWN"));
  return (
    <div className="card pad stack" data-testid="operations-panel">
      <div className="row"><h3 className="grow">环境操作</h3>
        <span className="small mono">{Object.entries(counts).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}</span></div>
      {abnormal.length === 0 ? <div className="small muted">没有结果未知、失败或待复核的操作</div> :
        <div className="table-wrap" style={{ maxHeight: 220 }}>
          <table className="table" aria-label="异常操作"><thead><tr><th className="num">步</th><th>动作</th><th>状态路径</th><th>复核</th></tr></thead>
            <tbody>{abnormal.map((o) => <tr key={o.operation_id}>
              <td className="num">{o.step}</td><td className="small">{o.action.action_type}</td>
              <td className="small" title={o.transitions.map((t) => `${t.state}: ${t.reason}`).join("\n")}>
                {o.transitions.map((t) => t.state).join(" → ")}</td>
              <td>{o.review ? <span className={`badge ${o.review.status === "NEEDS_REVIEW" ? "warn" : "ok"}`} title={o.review.note}>{o.review.status}</span>
                : <button className="btn sm" onClick={() => setOpen(o.operation_id)}>复核</button>}</td></tr>)}</tbody></table></div>}
      {open && <div className="stack small" role="group" aria-label="操作复核">
        <div>复核 <code>{open}</code></div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="复核结论">
          <option value="CONFIRMED_APPLIED">已确认生效</option><option value="CONFIRMED_NOT_APPLIED">已确认未生效</option>
          <option value="TERMINATED">因此终止</option></select>
        <textarea rows={2} value={note} placeholder="检查了什么（必填）" onChange={(e) => setNote(e.target.value)} aria-label="复核说明" />
        <div className="row"><button className="btn primary sm" disabled={!note.trim() || review.isPending} onClick={() => review.mutate(open)}>记录复核</button>
          <button className="btn sm" onClick={() => setOpen(null)}>取消</button></div></div>}
    </div>
  );
}

export function EnvironmentPanel({ run, events }: { run: RunDetail; events: TraceEvent[] }) {
  const session = useMemo(() => (events.find((e) => e.event_type === "SESSION_STATE")?.payload as Payload | undefined)?.session, [events]);
  const probes = useMemo(() => {
    const last: Record<string, Payload> = {};
    for (const e of events) if (e.event_type === "PROBE_SAMPLED") for (const p of (e.payload as Payload).results ?? []) last[p.metric] = p;
    return Object.values(last);
  }, [events]);
  const u = run.usage;
  return (
    <div className="card pad stack" data-testid="environment-panel">
      <h3>环境与资源</h3>
      <div className="small">{session ? <>会话 <code>{session.session_id}</code> · {session.backend} · <StatusBadge status={session.status} />
        {session.endpoint ? <span className="muted"> · {session.endpoint}</span> : null}</> : <span className="muted">纯数据模拟器（无外部会话）</span>}</div>
      <div className="small mono">墙钟 {fmtNum(u.wall_seconds ?? 0, 1)} s · 模型成功/尝试 {u.model_calls ?? 0}/{u.model_attempts ?? 0}
        · 未确认 {u.unconfirmed_calls ?? 0} · 未报告用量 {u.unreported_calls ?? 0} · 补充观测 {u.observation_requests ?? 0}</div>
      {probes.length > 0 && <table className="table" aria-label="探针"><thead><tr><th>探针指标</th><th className="num">值</th><th>窗口</th></tr></thead>
        <tbody>{probes.map((p) => <tr key={p.metric}><td className="small">{p.metric}</td>
          <td className="num">{p.status === "OK" ? `${fmtNum(p.value)} ${p.unit}` : <span className="badge" title={p.missing_reason}>{p.status}</span>}</td>
          <td className="small muted">{p.window?.kind === "LOGICAL_STEPS" ? `最近 ${p.window.size} 逻辑步` : "墙钟"}</td></tr>)}</tbody></table>}
    </div>
  );
}

export function RecoveryLog({ events }: { events: TraceEvent[] }) {
  const rows = events.filter((e) => RECOVERY_TYPES.has(e.event_type));
  return (
    <div className="card pad stack" data-testid="recovery-log">
      <h3>恢复与协调事件</h3>
      {rows.length === 0 ? <div className="small muted">没有恢复、对账、暂停或复核事件</div> :
        <div className="table-wrap" style={{ maxHeight: 220 }}><table className="table" aria-label="恢复事件">
          <thead><tr><th className="num">seq</th><th>类型</th><th className="num">步</th><th>说明</th><th>时间</th></tr></thead>
          <tbody>{rows.map((e) => <tr key={e.seq}><td className="num">{e.seq}</td><td><code className="small">{e.event_type}</code></td>
            <td className="num">{e.logical_step ?? "—"}</td><td className="small">{describe(e)}</td>
            <td className="small nowrap">{fmtTime(e.wall_time)}</td></tr>)}</tbody></table></div>}
    </div>
  );
}

function describe(e: TraceEvent): string {
  const p = e.payload as Payload;
  switch (e.event_type) {
    case "RECOVERY": return p.note ?? p.kind ?? "";
    case "OPERATION_RECONCILED": return `${p.operation_id}: ${p.reconciliation?.note ?? ""}`;
    case "OPERATION_REVIEW": return p.review ? `${p.operation_id ?? p.operation?.operation_id}: ${p.review.status} — ${p.review.note ?? ""}` : (p.action ?? "");
    case "OBSERVATION_REQUESTED": return p.served === false ? `未服务：${p.declined}` : `补充观测 ${(p.paths ?? []).length} 个位置`;
    case "MODEL_REVISION_SUGGESTED": return `模型修订建议：${p.action?.action_type} 的效果与观测不符`;
    case "REGRESSION_CASE_CREATED": return `回归案例 ${p.case?.case_id}`;
    case "RUN_CANCELLING": return p.reason ?? "取消请求";
    default: return p.reason ?? "";
  }
}
