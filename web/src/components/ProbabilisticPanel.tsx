// Optional PRISM-games extension (P2-X04): probabilistic conclusions of a turn-based stochastic game, shown apart
// from the deterministic Z3 checks — a number with a numerical tolerance and its assumptions, not a verdict.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post } from "../api";
import { Empty, fmtNum, fmtTime, InlineError, JsonField, KV, QueryState } from "../ui";

interface PropertyResult {
  property: string; coalition: string[]; value: number; reference_value: number; agrees: boolean;
  method: string | null; iterations: number | null; seconds: number | null;
}
interface ProbRecord {
  schema_id: string; profile: string; game: Record<string, unknown> & { game_id: string }; verified: boolean;
  backend: { name: string; version: string; license: string; arch: string; java: string };
  assumptions: string[]; properties: PropertyResult[]; size: Record<string, number>; reference_states: number;
  strategy: Record<string, string>; strategy_value: number; tolerance: number; model_sha256: string;
  model_text: string; seconds: number; notes: string[];
}
interface ProbCheck { check_id: string; query: { game_id: string; source: string }; record: ProbRecord; created_at: string }
interface Availability {
  available: boolean; reason?: string; backend?: ProbRecord["backend"]; pinned: { version: string; license: string; source: string };
  assumptions: string[]; example: Record<string, unknown>; distribution: string;
  capabilities: { feature: string; query: string; status: string; check: string }[];
}

export function ProbabilisticPanel({ versionId }: { versionId: string }) {
  const qc = useQueryClient();
  const avail = useQuery({ queryKey: ["prism-games"], queryFn: () => get<Availability>("/extensions/prism-games") });
  const checks = useQuery({ queryKey: ["prob-checks", versionId],
    queryFn: () => get<ProbCheck[]>(`/model-versions/${versionId}/probabilistic-checks`) });
  const [game, setGame] = useState<Record<string, unknown> | null>(null);
  const run = useMutation({
    mutationFn: () => post<ProbCheck>(`/model-versions/${versionId}/probabilistic-checks`, { game: game ?? avail.data?.example }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prob-checks", versionId] }),
  });
  return (
    <div className="stack" data-testid="probabilistic-panel">
      <div className="callout small">
        扩展轨道：PRISM-games 对有限、轮流行动、完全观测的随机博弈给出<strong>概率数值</strong>（容差 1e-6，附假设与策略），
        与“编译与检查”中 Z3 的<strong>确定性结论</strong>（可达 / 不可达 / 未知，带步数界）分开呈现，二者不可互换。
      </div>
      <QueryState q={avail}>{(a) => (
        <>
          <KV items={[
            ["后端", a.available ? `${a.backend!.name} ${a.backend!.version}（${a.backend!.arch}，${a.backend!.java}）`
              : <span className="badge err">未安装：{a.reason}</span>],
            ["固定版本 / 许可", `${a.pinned.version} · ${a.pinned.license}`],
            ["分发", a.distribution],
          ]} />
          <details><summary>模型假设与能力</summary>
            <ul className="small">{a.assumptions.map((x) => <li key={x}>{x}</li>)}</ul>
            <table className="table" aria-label="PRISM-games 能力"><thead><tr><th>能力</th><th>查询</th><th>状态</th><th>核对</th></tr></thead>
              <tbody>{a.capabilities.map((c) => <tr key={c.feature}><td>{c.feature}</td><td><code>{c.query}</code></td>
                <td>{c.status}</td><td className="small">{c.check}</td></tr>)}</tbody></table>
          </details>
          <h3>资源分配博弈</h3>
          <JsonField value={game ?? a.example} onChange={setGame} rows={10} />
          <div className="row">
            <button className="btn primary" disabled={!a.available || run.isPending} onClick={() => run.mutate()}>
              {run.isPending ? "求解中…" : "运行概率查询"}</button>
            {game && <button className="btn" onClick={() => setGame(null)}>恢复示例</button>}
          </div>
          <InlineError error={run.error} />
        </>
      )}</QueryState>
      <h3>概率结论</h3>
      <QueryState q={checks} isEmpty={(d) => d.length === 0}
        empty={<Empty title="还没有概率查询" hint="编辑上面的博弈并运行；结果按模型版本保存。" />}>
        {(rows) => <div className="stack">{rows.map((c) => <ProbResult key={c.check_id} c={c} />)}</div>}
      </QueryState>
    </div>
  );
}

function ProbResult({ c }: { c: ProbCheck }) {
  const r = c.record;
  return (
    <div className="card" data-testid="prob-result">
      <div className="card-body stack">
        <div className="row">
          <strong>{r.game.game_id}</strong>
          <span className={r.verified ? "badge ok" : "badge err"}>{r.verified ? "模型内核对通过" : "核对未通过"}</span>
          <span className="small muted">{fmtTime(c.created_at)} · {r.backend.name} {r.backend.version} · {fmtNum(r.seconds, 1)} s · 来源 {c.query.source}</span>
        </div>
        <table className="table" aria-label="概率结论">
          <thead><tr><th>性质</th><th>联盟</th><th>PRISM-games</th><th>独立参照</th><th>一致</th><th>方法</th></tr></thead>
          <tbody>{r.properties.map((p) => <tr key={p.property}>
            <td><code>{p.property}</code></td><td>{p.coalition.join(", ")}</td>
            <td><strong>{p.value.toFixed(6)}</strong></td><td>{p.reference_value.toFixed(6)}</td>
            <td>{p.agrees ? "是" : "否"}</td><td className="small">{p.method ?? "—"}{p.iterations != null ? `，${p.iterations} 次迭代` : ""}</td>
          </tr>)}</tbody>
        </table>
        <KV items={[
          ["状态规模", `${r.size.states} 状态 / ${r.size.choices} 选择 / ${r.size.transitions} 转移（参照图 ${r.reference_states} 状态）`],
          ["导出策略的值", `${r.strategy_value.toFixed(6)}（对最坏环境评估；容差 ${r.tolerance}）`],
          ["模型摘要", <code key="d">{r.model_sha256.slice(0, 16)}…</code>],
        ]} />
        <details><summary>调度方策略（PRISM-games 导出）</summary>
          <table className="table" aria-label="策略"><tbody>{Object.entries(r.strategy).map(([k, v]) =>
            <tr key={k}><td>{k}</td><td><code>{v}</code></td></tr>)}</tbody></table></details>
        <details><summary>生成的 PRISM 模型</summary><pre className="small">{r.model_text}</pre></details>
        {r.notes.length > 0 && <ul className="small muted">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      </div>
    </div>
  );
}
