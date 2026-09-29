import { useMemo, useState } from "react";
import type {
  ActionOutcome, ActionProposal, BoundedCheckResult, CandidateAction, EffectComparison, Observation, TraceEvent,
} from "@formal-lab/contracts";
import type { Labels } from "../labels";
import { ComparisonBadge, EvidenceLegend, EvidenceTag, fmtValue, Json, KV, SourceBadge, VerdictBadge } from "../ui";

export interface StepData {
  step: number;
  events: TraceEvent[];
  observation?: Observation;
  belief?: { unknown_paths: string[]; stale_paths: string[] };
  candidates?: CandidateAction[];
  proposal?: ActionProposal;
  modelCalls?: { digest: { value: string }; name?: string | null }[];
  checks: { purpose: string; result: BoundedCheckResult }[];
  outcome?: ActionOutcome;
  comparison?: EffectComparison;
  observationAfter?: Observation;
  plannerInput?: { withheld: string[]; digest: string; view?: { label?: string | null } | null };
  decisions?: Record<string, any>[];
  batch?: Record<string, any>;
}

export function groupSteps(events: TraceEvent[]): StepData[] {
  const map = new Map<number, StepData>();
  const at = (n: number) => map.get(n) ?? { step: n, events: [], checks: [] };
  for (const e of events) {
    if (e.logical_step === null || e.logical_step === undefined) continue;
    const p = e.payload as Record<string, any>;
    if (e.event_type === "EXECUTION_DECIDED") {  // decisions belong to the step of the proposal they judged
      const n = p.decision?.step ?? e.logical_step;
      const d = at(n);
      d.decisions = [...(d.decisions ?? []), p.decision];
      map.set(n, d);
      continue;
    }
    const s = at(e.logical_step);
    s.events.push(e);
    switch (e.event_type) {
      case "OBSERVATION": s.observation = p.observation; s.belief = p.belief; s.plannerInput = p.planner_input; break;
      case "BATCH_SUBMITTED": s.batch = p.batch; break;
      case "CANDIDATES": s.candidates = p.candidates; break;
      case "ACTION_PROPOSED": s.proposal = p.proposal; s.modelCalls = p.model_call_artifacts; break;
      case "CHECK_COMPLETED": s.checks.push({ purpose: p.purpose, result: p.result }); break;
      case "ACTION_OUTCOME": s.outcome = p.outcome; break;
      case "EFFECT_COMPARED": s.comparison = p.comparison; s.observationAfter = p.observation_after; break;
    }
    map.set(e.logical_step, s);
  }
  return [...map.values()].sort((a, b) => a.step - b.step);
}

// ------------------------------------------------------------------ timeline (click → select step)
const CW = 22, LANE = 22, LEFT = 96;
const LANES: { key: string; label: string; color: (s: StepData) => string | null; title: (s: StepData) => string }[] = [
  { key: "outcome", label: "动作结果", color: (s) => !s.outcome ? null : s.outcome.status === "APPLIED" ? "var(--ok)" : "var(--err)",
    title: (s) => `结果 ${s.outcome?.status ?? "—"}` },
  { key: "check", label: "前提检查", color: (s) => {
      const v = s.checks.find((c) => c.purpose.startsWith("precondition"))?.result.verdict;
      return v === "APPLICABLE" ? "var(--ok)" : v === "INAPPLICABLE" ? "var(--err)" : v ? "var(--warn)" : null; },
    title: (s) => `检查 ${s.checks.map((c) => c.result.verdict).join(",") || "—"}` },
  { key: "effect", label: "效果比较", color: (s) => {
      const v = s.comparison?.verdict;
      return v === "MATCH" ? "var(--ok)" : v === "DIFFERENT" ? "var(--err)" : v ? "var(--warn)" : null; },
    title: (s) => `效果 ${s.comparison?.verdict ?? "—"}` },
  { key: "unknown", label: "未知项", color: (s) => (s.observation?.unknowns?.length ? "var(--info)" : null),
    title: (s) => `未知项 ${s.observation?.unknowns?.length ?? 0}` },
];

export function Timeline({ steps, selected, onSelect }: { steps: StepData[]; selected: number | null; onSelect: (n: number) => void }) {
  const width = LEFT + Math.max(steps.length, 10) * CW + 10;
  return (
    <div className="svg-wrap">
      <svg width={width} height={LANES.length * LANE + 26} role="img" aria-label="步骤时间线：点击选择步骤">
        {LANES.map((l, li) => (
          <g key={l.key} transform={`translate(0,${li * LANE + 4})`}>
            <text x={0} y={14} fontSize="12" fill="var(--text-2)">{l.label}</text>
            {steps.map((s, i) => {
              const c = l.color(s);
              return <rect key={s.step} x={LEFT + i * CW} y={2} width={CW - 4} height={LANE - 6} rx={3}
                fill={c ?? "var(--surface-2)"} opacity={selected === null || selected === s.step ? 1 : 0.45}
                style={{ cursor: "pointer" }} onClick={() => onSelect(s.step)}><title>{`步 ${s.step}：${l.title(s)}`}</title></rect>;
            })}
          </g>
        ))}
        {steps.map((s, i) => (
          <text key={s.step} x={LEFT + i * CW + (CW - 4) / 2} y={LANES.length * LANE + 18} fontSize="10" textAnchor="middle"
            fill={selected === s.step ? "var(--accent)" : "var(--muted)"} fontWeight={selected === s.step ? 700 : 400}
            style={{ cursor: "pointer" }} onClick={() => onSelect(s.step)}>{s.step}</text>
        ))}
        {selected !== null && steps.findIndex((s) => s.step === selected) >= 0 && (
          <rect x={LEFT + steps.findIndex((s) => s.step === selected) * CW - 2} y={2} width={CW} height={LANES.length * LANE + 4}
            fill="none" stroke="var(--accent)" strokeWidth={1.5} rx={4} pointerEvents="none" />
        )}
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------ state-over-steps chart (observed values)
export function StateChart({ steps, labels, selected, onSelect }: {
  steps: StepData[]; labels: Labels; selected: number | null; onSelect: (n: number) => void;
}) {
  const families = useMemo(() => {
    const names = new Set<string>();
    steps.forEach((s) => s.observation?.facts.forEach((f) => { if (typeof f.value === "number") names.add(f.path.split("[")[0]); }));
    steps.forEach((s) => s.observation?.unknowns?.forEach((u) => { if (typeof u.last_known?.value === "number") names.add(u.path.split("[")[0]); }));
    return [...names];
  }, [steps]);
  const [family, setFamily] = useState<string>("");
  const fam = family || families[0] || "";
  const rows = useMemo(() => {
    const paths = new Set<string>();
    steps.forEach((s) => {
      s.observation?.facts.forEach((f) => { if (f.path.split("[")[0] === fam) paths.add(f.path); });
      s.observation?.unknowns?.forEach((u) => { if (u.path.split("[")[0] === fam) paths.add(u.path); });
    });
    return [...paths].sort();
  }, [steps, fam]);
  if (!families.length) return <div className="muted small">观测中没有数值状态可绘制。</div>;
  const cell = (s: StepData, path: string) => {
    const fact = s.observation?.facts.find((f) => f.path === path);
    if (fact) return { v: fact.value as number, kind: fact.observed_at_step < (s.observation?.step ?? 0) ? "stale" : "fresh" };
    const u = s.observation?.unknowns?.find((x) => x.path === path);
    return u ? { v: (u.last_known?.value as number | undefined) ?? null, kind: "unknown" } : null;
  };
  const max = Math.max(1, ...steps.flatMap((s) => rows.map((p) => Number(cell(s, p)?.v ?? 0))));
  return (
    <div className="stack">
      <div className="row">
        <label className="row small">状态变量<select value={fam} onChange={(e) => setFamily(e.target.value)}>
          {families.map((f) => <option key={f} value={f}>{labels.state(f)}</option>)}</select></label>
        <div className="legend"><span><i className="dot" style={{ background: "var(--accent)" }} />已观测</span>
          <span><i className="dot" style={{ background: "var(--warn)" }} />未知（上次已知值）</span></div>
      </div>
      <div className="table-wrap tall">
        <table className="table" aria-label="状态随步骤变化">
          <thead><tr><th>位置</th>{steps.map((s) => <th key={s.step} className={`num ${selected === s.step ? "selected" : ""}`}
            style={{ cursor: "pointer" }} onClick={() => onSelect(s.step)}>{s.step}</th>)}</tr></thead>
          <tbody>{rows.map((p) => (
            <tr key={p}><td className="nowrap small">{labels.state(p)}</td>
              {steps.map((s) => {
                const c = cell(s, p);
                const alpha = c && c.v !== null ? 0.12 + 0.6 * (Number(c.v) / max) : 0;
                const base = c?.kind === "unknown" ? "var(--warn)" : "var(--accent)";
                return <td key={s.step} className="num small" onClick={() => onSelect(s.step)}
                  style={{ cursor: "pointer", background: c ? `color-mix(in srgb, ${base} ${Math.round(alpha * 100)}%, transparent)` : undefined,
                    outline: selected === s.step ? "1px solid var(--accent)" : undefined }}
                  title={c ? `${c.kind === "unknown" ? "未知，上次已知" : "已观测"} ${String(c.v)}` : "无"}>
                  {c ? (c.kind === "unknown" ? `?${c.v ?? ""}` : String(c.v)) : ""}</td>;
              })}</tr>))}</tbody>
        </table>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ step detail
export function StepDetail({ data, labels }: { data: StepData; labels: Labels }) {
  const obs = data.observation;
  const counts = data.candidates?.reduce((acc, c) => ({ ...acc, [c.belief_applicability]: (acc[c.belief_applicability] ?? 0) + 1 }), {} as Record<string, number>);
  const pre = data.checks.find((c) => c.purpose.startsWith("precondition"));
  const other = data.checks.filter((c) => c !== pre);
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <EvidenceLegend />
        <div className="legend"><span><span className="badge warn">过期</span>来自更早步骤</span>
          <span><span className="badge ok">有界结论</span>仅在边界内成立</span></div>
      </div>
      {data.plannerInput && data.plannerInput.withheld.length > 0 && (
        <div className="callout info small" data-testid="planner-input">
          <strong>规划器输入</strong>（参与者视图{data.plannerInput.view?.label ? `：${data.plannerInput.view.label}` : ""}）
          · 隐藏 {data.plannerInput.withheld.length} 个位置（{[...new Set(data.plannerInput.withheld.map((w) => w.split("[")[0]))].map((f) => labels.state(f)).join("、")}），
          规划器把它们当作从未观测；内核检查与比较仍使用完整观测 · 输入摘要 <code>{data.plannerInput.digest.slice(0, 10)}</code>
        </div>)}
      {data.proposal && (
        <section className="card pad stack">
          <div className="row"><h3 style={{ flex: 1 }}>决策</h3><SourceBadge kind={String(data.proposal.source.kind)} />
            {data.proposal.source.model && <span className="badge outline">{data.proposal.source.model}</span>}</div>
          <div><strong>{labels.actionText(data.proposal.action as never)}</strong></div>
          {data.proposal.rationale && <div className="small">{data.proposal.rationale}</div>}
          <KV items={[
            ["依据观测修订", String(data.proposal.based_on_revision)],
            ["候选", `${data.proposal.candidates_considered ?? "—"} 个（适用 ${counts?.APPLICABLE ?? 0} / 未知 ${counts?.UNKNOWN ?? 0} / 不适用 ${counts?.INAPPLICABLE ?? 0}）`],
            ...(data.proposal.usage.model_calls ? [["模型用量", `${data.proposal.usage.model_calls} 次 · ${data.proposal.usage.input_tokens + data.proposal.usage.output_tokens} tokens`] as [string, string]] : []),
            ...(data.modelCalls?.length ? [["调用记录", data.modelCalls.map((m) => <a key={m.digest.value} href={`/api/v1/artifacts/${m.digest.value}`} target="_blank" rel="noreferrer">{m.name ?? m.digest.value.slice(0, 10)}</a>)] as [string, React.ReactNode]] : []),
          ]} />
        </section>
      )}
      {data.decisions?.length ? (
        <section className="card pad stack" data-testid="execution-decisions">
          <div className="row"><h3 style={{ flex: 1 }}>执行前决策</h3>
            {data.decisions.map((d) => <span key={d.decision_id} className={`badge ${d.verdict === "ALLOW" ? "ok" : "err"}`}>{d.verdict}</span>)}</div>
          {data.decisions.map((d) => (
            <div key={d.decision_id} className="small stack" style={{ gap: 2 }}>
              <div><code>{d.gate.plugin_id}@{d.gate.version}</code> · {d.phase} · 取值 {d.values_source}{d.checked_at_revision !== null ? `（修订 ${d.checked_at_revision}）` : ""}</div>
              <div>{d.reason}</div>
              {d.conditions?.map((c: Record<string, any>) => <div key={c.name} className="muted">{c.holds ? "✓" : "✕"} {c.name}：观测 {fmtValue(c.observed)}，要求 {c.required}</div>)}
            </div>))}
        </section>) : null}
      {pre && (
        <section className="card pad stack">
          <div className="row"><h3 style={{ flex: 1 }}>前提检查（信念状态）</h3><VerdictBadge verdict={String(pre.result.verdict)} />
            <span className="badge outline">模型内结论</span></div>
          <div className="small">{pre.result.explanation}</div>
          <LongText text={pre.result.assumptions.join("；")} />
        </section>
      )}
      {other.map((c, i) => (
        <section key={i} className="card pad stack">
          <div className="row"><h3 style={{ flex: 1 }}>{c.purpose}</h3><VerdictBadge verdict={String(c.result.verdict)} />
            {c.result.verdict === "NO_WITNESS_WITHIN_BOUND" && <span className="badge ok">有界结论 ≤{c.result.bound.max_steps} 步</span>}</div>
          <div className="small">{c.result.explanation}</div>
        </section>
      ))}
      {data.outcome && (
        <section className="card pad stack">
          <div className="row"><h3 style={{ flex: 1 }}>动作结果与效果</h3>
            <span className={`badge ${data.outcome.status === "APPLIED" ? "ok" : "err"}`}>{data.outcome.status}</span>
            <ComparisonBadge verdict={data.comparison?.verdict} /></div>
          <KV items={[
            ["operation", <code className="small">{data.outcome.operation_id}</code>],
            ...(data.outcome.turn?.batch_id ? [["批次", <span><code className="small">{data.outcome.turn.batch_id}</code> · 环境步 {data.outcome.turn.env_step ?? "—"}</span>] as [string, React.ReactNode]] : []),
            ["状态修订", `${data.outcome.revision_before} → ${data.outcome.revision_after ?? "?"}`],
            ...(data.outcome.result.reason ? [["原因", String(data.outcome.result.reason)] as [string, string]] : []),
            ["预期来源", data.comparison?.expected_by ?? "—"],
          ]} />
          {data.comparison?.diffs.length ? (
            <div className="table-wrap" style={{ maxHeight: 240 }}>
              <table className="table" aria-label="字段级效果比较">
                <thead><tr><th>位置</th><th>预测</th><th>观测 / 核实</th><th>结论</th></tr></thead>
                <tbody>{data.comparison.diffs.map((d) => (
                  <tr key={d.path}><td className="small">{labels.state(d.path)}</td>
                    <td><span className="row" style={{ gap: 6 }}><EvidenceTag level="predicted" />{fmtValue(d.expected)}</span></td>
                    <td><span className="row" style={{ gap: 6 }}><EvidenceTag level={d.evidence ?? (d.status === "UNKNOWN" ? "unknown" : "observed")} />
                      {d.status === "UNKNOWN" ? null : fmtValue(d.observed)}</span></td>
                    <td><span className={`badge ${d.status === "MATCH" ? "ok" : d.status === "DIFFERENT" ? "err" : "warn"}`}>{d.status}</span></td></tr>))}</tbody>
              </table>
            </div>
          ) : <div className="muted small">无字段变化需要比较。</div>}
        </section>
      )}
      {obs && (
        <section className="card pad stack">
          <div className="row"><h3 style={{ flex: 1 }}>观测（步 {obs.step}，修订 {obs.state_revision}）</h3>
            <span className="badge">{obs.facts.length} 事实</span>{obs.unknowns?.length ? <span className="badge info">{obs.unknowns.length} 未知</span> : null}</div>
          <div className="table-wrap" style={{ maxHeight: 280 }}>
            <table className="table">
              <thead><tr><th>位置</th><th>值</th><th>依据</th></tr></thead>
              <tbody>
                {obs.unknowns?.map((u) => (
                  <tr key={`u-${u.path}`}><td className="small">{labels.state(u.path)}</td>
                    <td>{u.last_known ? <span className="muted">上次 {labels.value(u.last_known.value)}</span> : "—"}</td>
                    <td><EvidenceTag level="unknown" />{u.last_known && <span className="small muted"> 截至步 {u.last_known.observed_at_step}</span>}</td></tr>))}
                {obs.facts.map((f) => (
                  <tr key={f.path}><td className="small">{labels.state(f.path)}</td><td>{labels.value(f.value)}</td>
                    <td>{f.observed_at_step < obs.step ? <span className="badge warn">过期 · 步 {f.observed_at_step}</span> : <EvidenceTag level="observed" />}</td></tr>))}
              </tbody>
            </table>
          </div>
          <div className="small muted">{obs.semantics}</div>
        </section>
      )}
      {data.candidates && (
        <details className="card pad"><summary><strong>候选动作（{data.candidates.length}）</strong></summary>
          <div className="table-wrap" style={{ maxHeight: 260, marginTop: 8 }}>
            <table className="table"><thead><tr><th>动作</th><th>信念上的适用性</th></tr></thead>
              <tbody>{data.candidates.map((c, i) => (
                <tr key={i} className={data.proposal && JSON.stringify(data.proposal.action) === JSON.stringify(c.action) ? "selected" : ""}>
                  <td className="small">{labels.actionText(c.action as never)}</td><td><VerdictBadge verdict={String(c.belief_applicability)} /></td></tr>))}</tbody>
            </table>
          </div>
        </details>
      )}
      <details><summary className="small muted">本步事件（{data.events.length}）</summary>
        <Json value={data.events.map((e) => ({ seq: e.seq, type: e.event_type, id: e.event_id, parents: e.causal_parents }))} maxHeight={200} /></details>
    </div>
  );
}

function LongText({ text, limit = 180 }: { text: string; limit?: number }) {
  if (text.length <= limit) return <div className="small muted">{text}</div>;
  return (
    <details className="small muted"><summary>{text.slice(0, limit)}… <span className="badge">展开</span></summary>
      <div style={{ overflowWrap: "anywhere" }}>{text}</div></details>
  );
}
