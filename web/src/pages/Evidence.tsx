import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import type { TraceEvent } from "@formal-lab/contracts";
import { fetchAllEvents, get, researchCase, runResearch, type ResearchCaseDetail, type ResearchLink,
  type RunDetail, type RunSummary } from "../api";
import { groupSteps, StepDetail } from "../components/Steps";
import { BatchPanel } from "../components/RunKernel";
import { Icon } from "../icons";
import { CorrespondenceBadge, Empty, fmtTime, fmtValue, Json, KV, Loading, QueryState, shortId, StatusBadge, Tabs,
  VerdictBadge, PageHead } from "../ui";
import { useRunLabels } from "./RunConsole";

type Tab = "replay" | "navigate" | "causal" | "diff" | "artifacts" | "lineage" | "batches" | "research";

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
      <PageHead area="证据" icon="evidence" title="证据与回放"
        description="回放查看原始轨迹（只读，不重新执行）；重新运行会创建新实验并记录来源。真值快照是环境证据，参与者在运行时不可见。" />
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
  const events = useQuery({ queryKey: ["events-all", runId], queryFn: () => fetchAllEvents(runId!) });
  const labels = useRunLabels(run.data);
  const [tab, setTab] = useState<Tab>("replay");
  const [focus, setFocus] = useState<number | null>(null);
  const goto = (step: number | null | undefined) => { if (step === null || step === undefined) return; setFocus(step); setTab("replay"); };
  if (run.isPending || events.isPending) return <div className="card"><Loading /></div>;
  if (!run.data || !events.data) return <div className="card"><Empty title="无法加载实验" /></div>;
  const stored = (run.data as RunDetail & { stored_contract_version?: string }).stored_contract_version;
  const joint = run.data.manifest.turns.mode === "JOINT_BATCH";
  return (
    <div className="stack">
      <div className="card">
        <div className="card-head">
          <h2 className="grow">{run.data.scenario_name} <code className="small">{run.data.id}</code></h2>
          <StatusBadge status={run.data.status} />
          <a className="btn sm" href={`/api/v1/runs/${runId}/export`} download><Icon name="export" size="sm" />导出回放包</a>
          <Link className="btn sm" to={`/p/${pid}/runs/${runId}`}><Icon name="run" size="sm" />运行台</Link>
        </div>
        {stored && stored !== "formal-lab-contracts/v2" && <div className="callout small" data-testid="schema-note">
          该运行按 <code>{stored}</code> 记录：展示时逐字段升级，原始记录保持写入时的内容与含义。</div>}
        <Tabs label="证据视图" value={tab} onChange={setTab} tabs={[
          { id: "replay", label: "按步回放" }, { id: "navigate", label: "关联定位" }, { id: "causal", label: "因果时间线" },
          { id: "diff", label: "差异报告" }, ...(joint ? [{ id: "batches" as Tab, label: "同步批次" }] : []),
          { id: "artifacts", label: "产物" }, { id: "lineage", label: "来源与清单" },
          { id: "research", label: "对应验证" }]} />
        <div className="card-body">
          {tab === "replay" && <Replay events={events.data} runId={runId} labels={labels} focus={focus} />}
          {tab === "navigate" && <Navigator pid={pid} run={run.data} events={events.data} goto={goto} />}
          {tab === "causal" && <Causal events={events.data} goto={goto} />}
          {tab === "diff" && <DiffReport events={events.data} labels={labels} />}
          {tab === "batches" && <BatchPanel run={run.data} events={events.data} labels={labels} />}
          {tab === "artifacts" && <Artifacts runId={runId} />}
          {tab === "lineage" && <Lineage run={run.data} pid={pid} />}
          {tab === "research" && <RunResearch pid={pid} runId={runId} />}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ model–program correspondence (phase 5A)
function RunResearch({ pid, runId }: { pid: string; runId: string }) {
  const q = useQuery({ queryKey: ["run-research", runId], queryFn: () => runResearch(runId) });
  return (
    <QueryState q={q} empty={<Empty title="该实验不是任何研究案例的记录观测"
      hint="把研究案例导入项目后，以此实验为记录观测的模型—程序对应验证会出现在这里。" />}>
      {(links: ResearchLink[]) => (
        <div className="stack">
          {links.map((l) => <ResearchCaseCard key={l.id} pid={pid} link={l} />)}
        </div>
      )}
    </QueryState>
  );
}

function ResearchCaseCard({ pid, link }: { pid: string; link: ResearchLink }) {
  const q = useQuery({ queryKey: ["research-case", link.id], queryFn: () => researchCase(link.id) });
  return (
    <QueryState q={q}>
      {(c: ResearchCaseDetail) => (
        <div className="card pad stack" data-testid="run-research-case">
          <div className="row">
            <strong className="grow">{c.title}</strong>
            <span className="badge">{c.track === "implementation_conformance" ? "实现一致性" : "合成表示"}</span>
            <span className="badge info" title="机制族">{c.mechanism_family}</span>
            <a className="btn sm" href={`/api/v1/research/cases/${c.id}/export`} download>
              <Icon name="export" size="sm" />导出案例</a>
          </div>
          <div className="muted small">{c.purpose}</div>

          <h3 className="small" style={{ margin: "4px 0 0" }}>软件来源</h3>
          <KV items={[
            ["仓库 / 许可", <span><code>{c.software.repository}</code> · {c.software.license}</span>],
            ["修订", <code title={c.software.revision}>{c.software.revision.slice(0, 12)}…</code>],
            ["变体", <span><span className="badge">{c.software.variant}</span> <span className="muted small">{c.software.variant_note}</span></span>],
            ["目录树摘要", <span className="stack" style={{ gap: 2 }}>{c.software.trees.map((t) => (
              <span key={t.path} className="small"><code>{t.path}</code> · <code title={t.git_tree}>{t.git_tree.slice(0, 12)}…</code></span>))}</span>],
            ...(c.software.config_sha256 ? [["运行配置摘要", <code title={c.software.config_sha256}>{c.software.config_sha256.slice(0, 12)}…</code>] as [string, React.ReactNode]] : []),
          ]} />

          <h3 className="small" style={{ margin: "4px 0 0" }}>模型、性质、界限与假设</h3>
          {c.models.map((m) => (
            <div key={m.label} className="card pad stack" style={{ gap: 4 }}>
              <div className="row">
                <span className="badge">{m.role === "belief" ? "信念" : m.role === "revised" ? "修订" : "参考"}</span>
                <code className="grow">{m.model_ref.package_id}@{m.model_ref.version}</code>
                <span className="badge info">{m.semantic_profile}</span>
                <code className="small" title={m.model_ref.digest.value}>{m.model_ref.digest.value.slice(0, 12)}…</code>
              </div>
              <div className="small">界限：最多 {m.bounds.max_steps} 步{m.bounds.timeout_ms ? ` · ${m.bounds.timeout_ms} ms` : ""} · {m.bounds.inputs}</div>
              <table className="table" aria-label={`${m.label} 性质`}>
                <thead><tr><th>性质</th><th>种类</th><th>说明</th><th>表达式摘要</th></tr></thead>
                <tbody>{m.properties.map((p) => (
                  <tr key={p.property_id}><td><code>{p.property_id}</code></td><td>{p.kind === "goal" ? "目标" : "不变式"}</td>
                    <td>{p.summary}</td><td><code title={p.digest}>{p.digest.slice(0, 12)}…</code></td></tr>))}</tbody>
              </table>
              {m.assumptions.length > 0 && <div className="small muted">抽象假设：{m.assumptions.join("；")}</div>}
              {m.uncovered_semantics.length > 0 && <div className="small muted">未覆盖语义：{m.uncovered_semantics.join("；")}</div>}
            </div>
          ))}

          <h3 className="small" style={{ margin: "4px 0 0" }}>模型内结论 · 程序回归 · 对应（三层分开）</h3>
          <table className="table" aria-label="对应结果">
            <thead><tr><th>结果</th><th>性质</th><th>模型结论</th><th>程序回归</th><th>对应</th></tr></thead>
            <tbody>
              {c.conformance.map((r) => (
                <tr key={r.id}>
                  <td><code className="small">{r.label}</code></td>
                  <td><code>{r.property_id}</code></td>
                  <td><VerdictBadge verdict={r.model_verdict} /></td>
                  <td><span className={`badge ${r.regression_status === "PASS" ? "ok" : r.regression_status === "FAIL" ? "err" : ""}`}>{r.regression_status}</span></td>
                  <td><CorrespondenceBadge status={r.correspondence} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="small muted">对应仅覆盖记录运行的已执行步骤内声明范围内的字段，不等于模型与程序的语义等价。</div>

          {c.correspondence.length > 0 && (
            <details>
              <summary className="small">程序组件 ↔ 模型元素对应（{c.correspondence.length}）</summary>
              <table className="table" aria-label="组件对应">
                <thead><tr><th>程序组件</th><th>模型元素</th><th>关系</th></tr></thead>
                <tbody>{c.correspondence.map((x, i) => (
                  <tr key={i}>
                    <td><code className="small">{x.program.component}</code>{x.program.symbol ? <span className="muted small"> · {x.program.symbol}</span> : null}</td>
                    <td>{x.model.kind} <code>{x.model.name}</code></td>
                    <td><span className="badge" title={x.note ?? undefined}>{x.relation === "MANUAL_REVIEW" ? "人工审阅" : x.relation === "MEASURED" ? "实测对应" : "形式证明"}</span></td>
                  </tr>))}</tbody>
              </table>
            </details>
          )}

          <div className="small muted">记录观测：此实验 · 案例摘要 <code title={c.case_digest}>{c.case_digest.slice(0, 12)}…</code>
            {c.models[0]?.model_ref && <> · <Link to={`/p/${pid}/models`}>模型工作台</Link></>}</div>
        </div>
      )}
    </QueryState>
  );
}

function Replay({ events, runId, labels, focus }: { events: TraceEvent[]; runId: string; labels: ReturnType<typeof useRunLabels>; focus?: number | null }) {
  const steps = useMemo(() => groupSteps(events), [events]);
  const [i, setI] = useState(0);
  useEffect(() => { if (focus !== null && focus !== undefined) { const k = steps.findIndex((x) => x.step === focus); if (k >= 0) setI(k); } }, [focus, steps]);
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
    queryFn: () => get<{ kind?: string; data: { data?: { state?: Record<string, unknown>; step: number } } & Record<string, unknown> }>(`/artifacts/${snapArtifact!.digest}`) });
  // a live session (e.g. the order service) keeps its state outside: its snapshot is a marker, not the full state
  const truth = snapshot.data?.data?.data?.state;
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
            : snapshot.isPending ? <Loading /> : snapshot.data && !truth ? (
              <div className="small stack" data-testid="session-snapshot">
                <div className="callout info">该环境是持久会话（{snapshot.data.kind ?? "SESSION_MARKER"}）：状态保存在外部业务服务中，快照只记录会话与修订。
                  这一步的证据见左侧的操作状态路径与效果比较，以及“关联定位”中的独立探针。</div>
                <Json value={snapshot.data} maxHeight={220} />
              </div>) : snapshot.data && truth ? (
              <div className="table-wrap tall">
                <table className="table"><thead><tr><th>位置</th><th>真值</th><th>观测</th></tr></thead>
                  <tbody>{Object.entries(truth).map(([k, v]) => {
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

function Causal({ events, goto }: { events: TraceEvent[]; goto: (step: number | null | undefined) => void }) {
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
            <div className="row"><code>{sel.event_type}</code><span className="muted small">seq {sel.seq} · {fmtTime(sel.wall_time)}</span>
              <span className="grow" />{sel.logical_step !== null && sel.logical_step !== undefined &&
                <button className="btn sm" onClick={() => goto(sel.logical_step)}>回放第 {sel.logical_step} 步</button>}</div>
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
          <table className="table wide">
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

type P = Record<string, any>;

/** Cross-references (P2-093): task plans, the model version / release / revision suggestions, business metrics and
 *  independent probe samples — each row jumps to the replay step it belongs to. */
function Navigator({ pid, run, events, goto }: { pid: string; run: RunDetail; events: TraceEvent[]; goto: (s: number | null | undefined) => void }) {
  const m = run.manifest;
  const plans = events.filter((e) => e.event_type === "PLAN_UPDATED");
  const suggestions = events.filter((e) => e.event_type === "MODEL_REVISION_SUGGESTED");
  const cases = events.filter((e) => e.event_type === "REGRESSION_CASE_CREATED");
  const probes = events.filter((e) => e.event_type === "PROBE_SAMPLED");
  const models = useQuery({ queryKey: ["models", pid], queryFn: () => get<{ id: string; package_id: string }[]>(`/projects/${pid}/models`) });
  const modelId = models.data?.find((x) => x.package_id === m.model.package_id)?.id;
  const [probeMetric, setProbeMetric] = useState("throughput");
  const probeMetrics = [...new Set(probes.flatMap((e) => ((e.payload as P).results ?? []).map((r: P) => r.metric)))];
  return (
    <div className="stack" data-testid="navigator">
      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <div className="card pad stack">
          <h3>模型版本</h3>
          <KV items={[
            ["模型", modelId ? <Link to={`/p/${pid}/models/${modelId}`}>{m.model.package_id}@v{m.model.version}</Link> : `${m.model.package_id}@v${m.model.version}`],
            ["摘要", <code className="small">{m.model.digest.value.slice(0, 16)}</code>],
            ["发布", (m as P).release ? <code className="small">{(m as P).release.release_id}</code> : "未固定发布"],
            ["规则集", (m as P).rules ? `${(m as P).rules.ruleset_id}@${(m as P).rules.version}` : "—"],
          ]} />
          <h4>模型修订建议</h4>
          {suggestions.length === 0 ? <div className="small muted">没有效果差异</div> :
            <table className="table" aria-label="修订建议"><thead><tr><th className="num">步</th><th>动作</th><th>不符字段</th><th>读取的常量</th><th /></tr></thead>
              <tbody>{suggestions.map((e) => { const p = e.payload as P; return <tr key={e.seq}><td className="num">{e.logical_step}</td>
                <td className="small">{p.action?.action_type}</td>
                <td className="small">{(p.different_fields ?? []).slice(0, 3).map((d: P) => `${d.path}: ${fmtValue(d.expected)}→${fmtValue(d.observed)}`).join("；")}</td>
                <td className="small">{(p.constants_read ?? []).join(", ") || "—"}</td>
                <td><button className="btn sm" onClick={() => goto(e.logical_step)}>定位</button></td></tr>; })}</tbody></table>}
          {cases.length > 0 && <div className="small">回归案例：{cases.map((e) => <code key={e.seq} className="small">{(e.payload as P).case?.case_id} </code>)}</div>}
        </div>
        <div className="card pad stack">
          <h3>任务计划</h3>
          {plans.length === 0 ? <div className="small muted">该运行的策略没有任务计划</div> :
            <table className="table" aria-label="计划版本"><thead><tr><th>参与者</th><th className="num">版本</th><th>触发</th><th>生成</th><th className="num">步</th><th /></tr></thead>
              <tbody>{plans.map((e) => { const p = (e.payload as P).plan; return <tr key={e.seq}><td className="small">{e.actor_id}</td>
                <td className="num">v{p.version}</td><td className="small" title={p.revision?.detail}>{p.revision?.trigger}</td>
                <td className="small">{p.generator?.kind}</td><td className="num">{e.logical_step}</td>
                <td><button className="btn sm" onClick={() => goto(e.logical_step)}>定位</button></td></tr>; })}</tbody></table>}
        </div>
      </div>
      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <div className="card pad stack">
          <h3>业务指标（评分器）</h3>
          <KV items={Object.entries(run.metrics).map(([k, v]) => [k, v.value !== null ? `${fmtValue(v.value)} ${v.unit ?? ""}` : v.status])} />
        </div>
        <div className="card pad stack">
          <div className="row"><h3 className="grow">独立探针（按步）</h3>
            {probeMetrics.length > 0 && <select value={probeMetric} onChange={(e) => setProbeMetric(e.target.value)} aria-label="探针指标">
              {probeMetrics.map((x) => <option key={x}>{x}</option>)}</select>}</div>
          {probes.length === 0 ? <div className="small muted">该环境没有探针</div> :
            <div className="table-wrap" style={{ maxHeight: 260 }}><table className="table" aria-label="探针样本">
              <thead><tr><th className="num">步</th><th className="num">值</th><th>来源</th><th /></tr></thead>
              <tbody>{probes.map((e) => { const r = ((e.payload as P).results ?? []).find((x: P) => x.metric === probeMetric);
                return r ? <tr key={e.seq}><td className="num">{e.logical_step}</td>
                  <td className="num">{r.status === "OK" ? `${fmtValue(r.value)} ${r.unit}` : r.status}</td><td className="small muted">{r.source}</td>
                  <td><button className="btn sm" onClick={() => goto(e.logical_step)}>定位</button></td></tr> : null; })}</tbody></table></div>}
        </div>
      </div>
    </div>
  );
}
