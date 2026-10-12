// Research study results (phase 6A): the two experiment lines apart, call outcome and behaviour per unit over the
// planned denominator, and every unit's raw provider answer — read-only, imported with `fal research study import`.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { researchStudy, researchStudyUnit, type StudyMetric, type StudyUnitSummary } from "../api";
import { Empty, fmtTime, Json, KV, Modal, QueryState, Tabs } from "../ui";

const TRACK: Record<string, string> = {
  implementation_conformance: "实现一致性（软件案例）",
  synthetic_representation: "合成表示（无害合成任务）",
  formal_model_analysis: "形式模型分析（攻击图，验证器判定）",
};
const OUTCOME_TONE: Record<string, string> = {
  ANSWERED: "ok", TRUNCATED: "warn", CONTENT_REFUSAL: "warn", EMPTY_CONTENT: "warn", UNCERTAIN: "warn",
  RATE_LIMITED: "warn", MALFORMED_RESPONSE: "err", AUTH_ERROR: "err", PROVIDER_ERROR: "err", REQUEST_REJECTED: "err",
  MODEL_UNAVAILABLE: "err", TRANSPORT_ERROR: "err",
};
const BEHAVIOR_TONE: Record<string, string> = {
  CORRECT: "ok", PARTIAL: "warn", INCORRECT: "err", INVALID_FORMAT: "warn", REFUSED: "warn", EMPTY: "warn",
};

export const OutcomeBadge = ({ value }: { value?: string | null }) =>
  <span className={`badge ${OUTCOME_TONE[value ?? ""] ?? ""}`} title="调用结果（调用轴）">{value ?? "—"}</span>;
export const BehaviorBadge = ({ value }: { value?: string | null }) =>
  <span className={`badge ${BEHAVIOR_TONE[value ?? ""] ?? ""}`} title="参考判据下的行为标签（回答轴）">{value ?? "—"}</span>;

function metricCell(m?: StudyMetric) {
  if (!m) return "—";
  if (m.status !== "OK") return <span className="muted small" title={m.missing_reason ?? undefined}>{m.status}</span>;
  return <span title={`n=${m.n}, missing ${m.missing}, n/a ${m.not_applicable}`}>
    {m.value === null ? "—" : m.value.toFixed(2)} <span className="muted small">n={m.n}</span></span>;
}

const counts = (r: Record<string, number>) => Object.entries(r).sort().map(([k, v]) => `${k} ${v}`).join(" · ");

export function StudyView({ sid }: { sid: string }) {
  const q = useQuery({ queryKey: ["research-study", sid], queryFn: () => researchStudy(sid) });
  const [track, setTrack] = useState<string | null>(null);
  const [unit, setUnit] = useState<string | null>(null);
  return (
    <QueryState q={q}>
      {(d) => {
        const tracks = Object.keys(d.report.tracks);
        const cur = track ?? tracks[0];
        const t = d.report.tracks[cur];
        const units: StudyUnitSummary[] = d.unit_summaries.filter((u) => u.track === cur);
        const l = d.report.ledger;
        return (
          <div className="stack" data-testid="research-study">
            <div className="card">
              <div className="card-head">
                <h2 className="grow">{d.title}</h2>
                <span className="badge info">{d.study_id}</span>
              </div>
              <div className="card-body stack">
                <KV items={[
                  ["主要指标", <code>{d.report.primary_metric}</code>],
                  ["评分标准", <code>{d.report.rubric.join("@")}</code>],
                  ["每条件独立重复", String(d.report.replicates)],
                  ["记录", `${l.responses} 条回答记录 · ${l.calls} 次调用 · ${l.http_attempts} 次 HTTP 尝试 · ${l.possibly_billed} 次已发出未确认（可能计费）`],
                  ["导入", fmtTime(d.imported_at)],
                ]} />
                <div className="callout small">两条实验线分开统计，不合并成一个总体成功率。模型成绩只计模型实际产生的回答；传输、鉴权、限流、预算、取消与阻塞单元记为缺失（不是 0，也不是 1）；拒绝与格式无效计为未答对。中转路由返回的模型名只是中转方报告，不可核实。</div>
              </div>
            </div>
            <div className="card">
              <Tabs label="实验线" value={cur} onChange={(x) => { setTrack(x); setUnit(null); }}
                tabs={tracks.map((x) => ({ id: x, label: `${TRACK[x] ?? x} · ${d.report.tracks[x].planned}` }))} />
              <div className="card-body stack">
                <div className="table-wrap">
                  <table className="table" aria-label="条件汇总">
                    <thead><tr><th>条件（提供方 · 辅助 · 表示）</th><th>计划</th><th>调用结果</th><th>行为标签</th>
                      <th>正确</th><th>格式有效</th><th>拒绝</th><th>程序对应</th><th>身份</th></tr></thead>
                    <tbody>
                      {t.conditions.map((r) => (
                        <tr key={r.condition}>
                          <td><code className="small">{r.condition}</code></td><td className="num">{r.planned}</td>
                          <td className="small">{counts(r.outcomes)}</td><td className="small">{counts(r.behaviors)}</td>
                          <td>{metricCell(r.metrics.correct)}</td><td>{metricCell(r.metrics.format_valid)}</td>
                          <td>{metricCell(r.metrics.refused)}</td><td>{metricCell(r.metrics.program_corresponds)}</td>
                          <td className="small muted">{Object.keys(r.identity).join("; ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {t.comparisons.map((c, i) => (
                  <div key={i} className="small">
                    <strong>配对（{c.vary}）：{c.a} vs {c.b}</strong>{" "}
                    {c.not_applicable ? <span className="muted">不适用：{c.not_applicable}</span>
                      : <span>{c.n_pairs} 对 · {c.unpaired} 未配对 · 均差（b − a）{c.mean_diff_b_minus_a ?? "—"} · <span className="muted">{c.reading_note}</span></span>}
                    {c.comparability_note && <div className="muted">{c.comparability_note}</div>}
                  </div>
                ))}
                <div className="table-wrap" style={{ maxHeight: 420 }}>
                  <table className="table" aria-label="单元">
                    <thead><tr><th>单元</th><th>调用结果</th><th>回答</th><th>行为</th><th>程序对应</th>
                      <th>返回模型 / 身份</th><th className="num">输出 token</th><th /></tr></thead>
                    <tbody>
                      {units.map((u) => (
                        <tr key={u.unit_id}>
                          <td><code className="small">{u.unit_id}</code>{u.sampling_index > 0 &&
                            <span className="badge" title="重新采样的序号（早先的记录保留在账本里）">#{u.sampling_index}</span>}</td>
                          <td><OutcomeBadge value={u.outcome} />{u.http_status ? <span className="muted small"> {u.http_status}</span> : null}</td>
                          <td className="small">{u.answer_status ?? "—"}</td>
                          <td><BehaviorBadge value={u.behavior} /></td>
                          <td className="small">{u.program_correspondence ?? "—"}</td>
                          <td className="small">{u.model_returned ?? "—"} <span className="muted">{u.route}/{u.model_identity}</span>
                            {u.model_switched && <span className="badge warn">模型变化</span>}</td>
                          <td className="num">{u.usage_known ? u.output_tokens : "未知"}</td>
                          <td><button className="btn sm ghost" onClick={() => setUnit(u.unit_id)}>原始回答</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            {d.report.not_run.length > 0 && (
              <div className="card"><div className="card-head"><h3 className="grow">未运行</h3></div>
                <div className="card-body small">{d.report.not_run.map((n) => (
                  <div key={`${n.task_id}-${n.mode}`}><code>{n.task_id}</code> · {n.mode}：{n.reason}</div>))}</div></div>
            )}
            {unit && <UnitModal sid={sid} unit={unit} onClose={() => setUnit(null)} />}
          </div>
        );
      }}
    </QueryState>
  );
}

function UnitModal({ sid, unit, onClose }: { sid: string; unit: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["research-study-unit", sid, unit], queryFn: () => researchStudyUnit(sid, unit) });
  return (
    <Modal title={unit} onClose={onClose}>
      <QueryState q={q}>
        {(u) => {
          const call = u.response.call as Record<string, string | boolean | null>;
          const raw = u.response.raw as Record<string, unknown>;
          const status = u.response.status as Record<string, unknown>;
          const cost = u.response.cost as Record<string, unknown>;
          const ev = u.evaluation as Record<string, unknown> | null;
          const s = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : String(v));
          return (
            <div className="stack" data-testid="study-unit">
              <KV items={[
                ["调用结果", <span><OutcomeBadge value={u.outcome} /> HTTP {s(status.http_status)} · {s(status.note)}</span>],
                ["提供方 / 协议", `${s(call.provider)} · ${s(call.api)} ${s(call.api_version)}`],
                ["路由 / 端点", `${s(call.route)} · ${s(call.endpoint)}`],
                ["模型（请求 → 返回）", `${s(call.model_requested)} → ${s(call.model_returned)} [${s(call.model_identity)}]`],
                ["响应 / 请求 ID", `${s(call.response_id)} / ${s(call.request_id)}`],
                ["结束原因", `${s(raw.finish_reason)} (${s(raw.finish_class)}) · 拒绝字段 ${s(raw.refusal)} · 截断 ${s(raw.truncated)} · 推理 ${s(raw.reasoning)}`],
                ["用量", `${cost.usage_known ? `${s(cost.input_tokens)} 入 / ${s(cost.output_tokens)} 出` : "提供方未报告"} · ${s(cost.http_attempts)} 次尝试 · ${s(cost.possibly_billed_unconfirmed)} 次未确认 · ${s(cost.latency_ms)} ms`],
              ]} />
              <div><div className="small muted">可见回答</div>
                <pre className="mono small" style={{ whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto" }}>{s(raw.visible_text)}</pre></div>
              {ev ? <KV items={[
                ["回答轴", s(ev.answer_status)], ["行为标签", <BehaviorBadge value={String(ev.behavior_label)} />],
                ["模型内 / 程序对应", `${s(ev.model_internal)} / ${s(ev.program_correspondence)}`],
                ["评分器", `${s(ev.scorer_id)}@${s(ev.scorer_version)}`], ["说明", s(ev.explanation)],
              ]} /> : <Empty title="尚未评分" />}
              {u.history.length > 0 && <div className="small">更早的采样：{u.history.map((h) =>
                `#${h.sampling_index} ${h.outcome} (${h.at})`).join(" · ")}</div>}
              <div><div className="small muted">提供方原始响应体</div><Json value={raw.body ?? raw.body_text ?? null} maxHeight={260} /></div>
            </div>
          );
        }}
      </QueryState>
    </Modal>
  );
}
