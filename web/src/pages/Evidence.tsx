import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import type { TraceEvent } from "@formal-lab/contracts";
import { get, type RunDetail, type RunSummary } from "../api";
import { groupSteps, StepDetail } from "../components/Steps";
import { Empty, fmtTime, fmtValue, Json, KV, Loading, QueryState, shortId, StatusBadge, Tabs } from "../ui";
import { useRunLabels } from "./RunConsole";

type Tab = "replay" | "causal" | "diff" | "artifacts" | "lineage";

export function EvidencePage() {
  const { pid, runId } = useParams();
  const navigate = useNavigate();
  const runs = useQuery({ queryKey: ["runs", pid, ""], queryFn: () => get<RunSummary[]>(`/projects/${pid}/runs`) });
  useEffect(() => {
    const first = runs.data?.find((r) => r.event_seq > 0);
    if (!runId && first) navigate(`/p/${pid}/evidence/${first.id}`, { replace: true });
  }, [runId, runs.data, pid, navigate]);
  return (
    <>
      <div className="page-head"><div className="grow"><h1>证据与回放</h1>
        <p>回放查看原始轨迹（只读，不重新执行）；重新运行会创建新实验并记录来源。真值快照是环境证据，参与者在运行时不可见。</p></div></div>
      <div className="split">
        <div className="card">
          <div className="card-head"><h2 className="grow">实验</h2></div>
          <QueryState q={runs} empty={<Empty title="还没有实验" />}>
            {(list) => (
              <div className="nav" style={{ padding: 6, maxHeight: 640, overflowY: "auto" }}>
                {list.map((r) => (
                  <Link key={r.id} to={`/p/${pid}/evidence/${r.id}`} className={r.id === runId ? "active" : ""}>
                    <span className="ellipsis" style={{ flex: 1 }}>{r.scenario_name} · <code>{shortId(r.id)}</code></span>
                    <StatusBadge status={r.status} />
                  </Link>
                ))}
              </div>
            )}
          </QueryState>
        </div>
        {runId ? <RunEvidence key={runId} pid={pid!} runId={runId} /> : <div className="card"><Empty title="选择一个实验" /></div>}
      </div>
    </>
  );
}

function RunEvidence({ pid, runId }: { pid: string; runId: string }) {
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => get<RunDetail>(`/runs/${runId}`) });
  const events = useQuery({ queryKey: ["events-all", runId], queryFn: () => get<TraceEvent[]>(`/runs/${runId}/events?limit=5000`) });
  const labels = useRunLabels(run.data);
  const [tab, setTab] = useState<Tab>("replay");
  if (run.isPending || events.isPending) return <div className="card"><Loading /></div>;
  if (!run.data || !events.data) return <div className="card"><Empty title="无法加载实验" /></div>;
  return (
    <div className="stack">
      <div className="card">
        <div className="card-head">
          <h2 className="grow">{run.data.scenario_name} <code className="small">{run.data.id}</code></h2>
          <StatusBadge status={run.data.status} />
          <a className="btn sm" href={`/api/v1/runs/${runId}/export`} download>⤓ 导出回放包</a>
          <Link className="btn sm" to={`/p/${pid}/runs/${runId}`}>运行台</Link>
        </div>
        <Tabs label="证据视图" value={tab} onChange={setTab} tabs={[
          { id: "replay", label: "按步回放" }, { id: "causal", label: "因果时间线" }, { id: "diff", label: "差异报告" },
          { id: "artifacts", label: "产物" }, { id: "lineage", label: "来源与清单" }]} />
        <div className="card-body">
          {tab === "replay" && <Replay events={events.data} runId={runId} labels={labels} />}
          {tab === "causal" && <Causal events={events.data} />}
          {tab === "diff" && <DiffReport events={events.data} labels={labels} />}
          {tab === "artifacts" && <Artifacts runId={runId} />}
          {tab === "lineage" && <Lineage run={run.data} pid={pid} />}
        </div>
      </div>
    </div>
  );
}

function Replay({ events, runId, labels }: { events: TraceEvent[]; runId: string; labels: ReturnType<typeof useRunLabels> }) {
  const steps = useMemo(() => groupSteps(events), [events]);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => setI((x) => { if (x >= steps.length - 1) { setPlaying(false); return x; } return x + 1; }), 900);
    return () => clearInterval(t);
  }, [playing, steps.length]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, select, textarea")) return;
      if (e.key === "ArrowRight") setI((x) => Math.min(steps.length - 1, x + 1));
      if (e.key === "ArrowLeft") setI((x) => Math.max(0, x - 1));
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps.length]);
  const cur = steps[i];
  const snapDigest = (cur?.events.find((e) => e.event_type === "ACTION_OUTCOME")?.payload as { snapshot_digest?: string })?.snapshot_digest;
  const artifacts = useQuery({ queryKey: ["artifacts", runId], queryFn: () => get<{ kind: string; digest: string; step: number | null }[]>(`/runs/${runId}/artifacts`) });
  const snapArtifact = artifacts.data?.find((a) => a.kind === "snapshot" && a.step === cur?.step);
  const snapshot = useQuery({ queryKey: ["snapshot", snapArtifact?.digest], enabled: Boolean(snapArtifact),
    queryFn: () => get<{ data: { data: { state: Record<string, unknown>; step: number } } }>(`/artifacts/${snapArtifact!.digest}`) });
  if (!steps.length) return <Empty title="没有步骤可回放" />;
  return (
    <div className="stack">
      <div className="row">
        <button className="btn sm" onClick={() => setI(0)} aria-label="第一步">⏮</button>
        <button className="btn sm" onClick={() => setI(Math.max(0, i - 1))} aria-label="上一步">◀</button>
        <button className="btn sm" onClick={() => setPlaying(!playing)}>{playing ? "⏸ 暂停" : "▶ 播放"}</button>
        <button className="btn sm" onClick={() => setI(Math.min(steps.length - 1, i + 1))} aria-label="下一步">▶</button>
        <input type="range" min={0} max={steps.length - 1} value={i} onChange={(e) => setI(Number(e.target.value))} style={{ flex: 1, minWidth: 120 }} aria-label="步骤" />
        <span className="mono small">步 {cur.step} / {steps.at(-1)!.step}</span>
        <span className="small muted"><span className="kbd">←</span><span className="kbd">→</span> <span className="kbd">空格</span></span>
      </div>
      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <StepDetail data={cur} labels={labels} />
        <div className="card pad stack">
          <div className="row"><h3 style={{ flex: 1 }}>真值快照（证据）</h3><span className="badge outline">参与者不可见</span></div>
          {!snapArtifact ? <div className="muted small">{snapDigest ? "该步快照未单独存档" : "该步没有快照"}</div>
            : snapshot.isPending ? <Loading /> : snapshot.data ? (
              <div className="table-wrap tall">
                <table className="table"><thead><tr><th>位置</th><th>真值</th><th>观测</th></tr></thead>
                  <tbody>{Object.entries(snapshot.data.data.data.state).map(([k, v]) => {
                    const after = cur.observationAfter ?? cur.observation;
                    const fact = after?.facts.find((f) => f.path === k);
                    const unknown = after?.unknowns?.find((u) => u.path === k);
                    const differs = fact && fact.value !== v;
                    return <tr key={k}><td className="small">{labels.state(k)}</td><td>{labels.value(v)}</td>
                      <td>{fact ? <span className={differs ? "badge warn" : ""}>{labels.value(fact.value)}</span> : unknown ? <span className="badge info">未知</span> : "—"}</td></tr>;
                  })}</tbody></table>
              </div>) : <span className="muted small">快照不可用</span>}
        </div>
      </div>
    </div>
  );
}

const LANE_OF: Record<string, number> = {
  RUN_CREATED: 0, RUN_QUEUED: 0, RUN_STARTED: 0, RUN_PAUSING: 0, RUN_PAUSED: 0, RUN_RESUMED: 0, RUN_CANCELLING: 0,
  RUN_CANCELLED: 0, RUN_SUCCEEDED: 0, RUN_FAILED: 0, BUDGET_EXHAUSTED: 0, METRICS_COMPUTED: 0, STATE_SNAPSHOT: 0,
  OBSERVATION: 1, CANDIDATES: 2, ACTION_PROPOSED: 3, CHECK_COMPLETED: 4, ACTION_OUTCOME: 5, EFFECT_COMPARED: 6, LOG: 0,
};
const LANE_NAMES = ["运行", "观测", "候选", "提案", "检查", "结果", "效果"];

function Causal({ events }: { events: TraceEvent[] }) {
  const [sel, setSel] = useState<TraceEvent | null>(null);
  const [page, setPage] = useState(0);
  const PER = 120;
  const slice = events.slice(page * PER, (page + 1) * PER);
  const idx = new Map(slice.map((e, i) => [e.event_id, i]));
  const LW = 96, RH = 18, TOP = 22;
  const color = (t: string) => (t.includes("FAILED") || t.includes("CANCELLED") ? "var(--err)" : t === "EFFECT_COMPARED" ? "var(--warn)" : t.startsWith("RUN") ? "var(--info)" : "var(--accent)");
  return (
    <div className="stack">
      <div className="row small"><span className="muted">每个点是一个事件（按 seq 纵向排列），连线指向其因果父事件。点击查看负载。</span>
        {events.length > PER && <><button className="btn sm" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button>
          <span>{page * PER + 1}–{Math.min(events.length, (page + 1) * PER)} / {events.length}</span>
          <button className="btn sm" disabled={(page + 1) * PER >= events.length} onClick={() => setPage(page + 1)}>下一页</button></>}</div>
      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <div className="svg-wrap" style={{ maxHeight: 620, overflowY: "auto" }}>
          <svg width={LANE_NAMES.length * LW + 20} height={TOP + slice.length * RH + 10} role="img" aria-label="因果时间线">
            {LANE_NAMES.map((n, i) => <text key={n} x={i * LW + 10} y={14} fontSize="11" fill="var(--muted)">{n}</text>)}
            {slice.map((e, i) => e.causal_parents.map((p) => {
              const j = idx.get(p);
              if (j === undefined) return null;
              const x1 = (LANE_OF[slice[j].event_type] ?? 0) * LW + 16, y1 = TOP + j * RH + 6;
              const x2 = (LANE_OF[e.event_type] ?? 0) * LW + 16, y2 = TOP + i * RH + 6;
              return <path key={`${e.seq}-${p}`} d={`M${x1},${y1} C${x1 + 30},${y1} ${x2 - 30},${y2} ${x2},${y2}`} fill="none" stroke="var(--border-strong)" />;
            }))}
            {slice.map((e, i) => (
              <g key={e.seq} transform={`translate(${(LANE_OF[e.event_type] ?? 0) * LW + 10},${TOP + i * RH})`} style={{ cursor: "pointer" }}
                onClick={() => setSel(e)} tabIndex={0} role="button" aria-label={`${e.seq} ${e.event_type}`}
                onKeyDown={(k) => { if (k.key === "Enter") setSel(e); }}>
                <circle cx={6} cy={6} r={sel?.seq === e.seq ? 6 : 4.5} fill={color(e.event_type)} />
                <text x={14} y={10} fontSize="10.5" fill="var(--text-2)">{e.seq} {e.logical_step !== null && e.logical_step !== undefined ? `s${e.logical_step}` : ""}</text>
              </g>
            ))}
          </svg>
        </div>
        <div className="card pad stack">
          {sel ? <>
            <div className="row"><code>{sel.event_type}</code><span className="muted small">seq {sel.seq} · {fmtTime(sel.wall_time)}</span></div>
            <KV items={[["event_id", <code className="small">{sel.event_id}</code>], ["schema", sel.payload_schema],
              ["父事件", sel.causal_parents.join(", ") || "—"], ["幂等键", <code className="small">{sel.idempotency_key}</code>]]} />
            <Json value={sel.payload} maxHeight={420} />
          </> : <Empty title="点击事件查看负载" />}
        </div>
      </div>
    </div>
  );
}

function DiffReport({ events, labels }: { events: TraceEvent[]; labels: ReturnType<typeof useRunLabels> }) {
  const rows = useMemo(() => groupSteps(events).flatMap((s) => (s.comparison?.diffs ?? []).filter((d) => d.status !== "MATCH")
    .map((d) => ({ step: s.step, verdict: s.comparison!.verdict, action: s.proposal?.action, ...d }))), [events]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    groupSteps(events).forEach((s) => { if (s.comparison) c[s.comparison.verdict] = (c[s.comparison.verdict] ?? 0) + 1; });
    return c;
  }, [events]);
  return (
    <div className="stack">
      <div className="row"><span className="badge ok">符合 {counts.MATCH ?? 0}</span><span className="badge err">差异 {counts.DIFFERENT ?? 0}</span>
        <span className="badge warn">信息不足 {counts.INSUFFICIENT_INFORMATION ?? 0}</span>
        <span className="muted small">预测来自运行固定的信念模型；观测来自环境。</span></div>
      {rows.length === 0 ? <Empty title="所有可比较字段均符合预期" /> : (
        <div className="table-wrap tall">
          <table className="table">
            <thead><tr><th className="num">步</th><th>动作</th><th>位置</th><th>预测</th><th>观测</th><th>结论</th></tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={i}><td className="num">{r.step}</td><td className="small">{r.action ? labels.actionText(r.action as never) : "—"}</td>
                <td className="small">{labels.state(r.path)}</td><td>{fmtValue(r.expected)}</td>
                <td>{r.status === "UNKNOWN" ? <span className="badge info">未知</span> : fmtValue(r.observed)}</td>
                <td><span className={`badge ${r.status === "DIFFERENT" ? "err" : "warn"}`}>{r.status}</span></td></tr>))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Artifacts({ runId }: { runId: string }) {
  const list = useQuery({ queryKey: ["artifacts", runId], queryFn: () => get<{ kind: string; digest: string; step: number | null;
    ref: { name?: string; size_bytes: number; media_type: string; format_version: string; uri: string } }[]>(`/runs/${runId}/artifacts`) });
  const [open, setOpen] = useState<string | null>(null);
  const preview = useQuery({ queryKey: ["artifact", open], enabled: Boolean(open), queryFn: () => get<unknown>(`/artifacts/${open}`) });
  return (
    <QueryState q={list} empty={<Empty title="没有产物" />}>
      {(items) => (
        <div className="grid cols-2" style={{ alignItems: "start" }}>
          <div className="table-wrap tall">
            <table className="table">
              <thead><tr><th>类别</th><th className="num">步</th><th>名称</th><th className="num">字节</th><th>格式</th></tr></thead>
              <tbody>{items.map((a) => (
                <tr key={a.digest + a.kind} className={`selectable ${open === a.digest ? "selected" : ""}`} tabIndex={0}
                  onClick={() => setOpen(a.digest)} onKeyDown={(e) => { if (e.key === "Enter") setOpen(a.digest); }}>
                  <td><span className="badge">{a.kind}</span></td><td className="num">{a.step ?? "—"}</td>
                  <td className="small ellipsis" style={{ maxWidth: 220 }}>{a.ref.name}</td><td className="num">{a.ref.size_bytes}</td>
                  <td className="small">{a.ref.format_version}</td></tr>))}</tbody>
            </table>
          </div>
          <div className="card pad stack">{open ? (preview.isPending ? <Loading /> : <>
            <div className="small muted">sha256 <code>{open}</code> · <a href={`/api/v1/artifacts/${open}`} target="_blank" rel="noreferrer">下载</a></div>
            <Json value={preview.data} maxHeight={520} /></>) : <Empty title="选择产物预览" />}</div>
        </div>
      )}
    </QueryState>
  );
}

function Lineage({ run, pid }: { run: RunDetail; pid: string }) {
  return (
    <div className="stack">
      <KV items={[
        ["来源实验", run.source_run_id ? <Link to={`/p/${pid}/evidence/${run.source_run_id}`}>{run.source_run_id}</Link> : "—（原始运行）"],
        ["重新运行", run.lineage.reruns.length ? run.lineage.reruns.map((r) => <div key={r}><Link to={`/p/${pid}/evidence/${r}`}>{r}</Link></div>) : "—"],
        ["导入", run.imported ? "是（来自回放包）" : "否"],
        ["契约", run.manifest.contract_version],
      ]} />
      <h3>RunManifest</h3>
      <Json value={run.manifest} maxHeight={520} />
    </div>
  );
}
