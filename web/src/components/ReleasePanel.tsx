// Model workbench: cost objectives, releases (pre-release checks and their record), query bundles and the
// assumptions every result holds under (P2-090 / P2-072 / P2-073 / P2-077).
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { irOf, get, post, type CheckRecord, type VersionDetail } from "../api";
import { Icon } from "../icons";
import { Empty, fmtTime, InlineError, KV, QueryState, useToast, VerdictBadge } from "../ui";

export interface ReleaseRow {
  release_id: string; model_version_id: string; status: string; digest: string; created_at: string;
  record: {
    model: { package_id: string; version: number }; ruleset: { ruleset_id: string; version: number } | null;
    checks: { kind: string; subject: string; verdict: string; passed: boolean; detail?: string | null;
      bound?: { max_steps: number } | null }[];
    regression: { case_id: string; status: string; detail: string }[]; bounds: string[]; assumptions: string[];
    reasons: string[]; log: { digest: { value: string } } | null; compiled: { backend: string; stats: Record<string, number> }[];
  };
}

export function ObjectivesAndReleases({ pid, detail, onDiff }: { pid: string; detail: VersionDetail; onDiff: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const ir = irOf(detail.package);
  const objectives = ir?.objectives ?? [];
  const releases = useQuery({ queryKey: ["releases", pid], queryFn: () => get<ReleaseRow[]>(`/projects/${pid}/releases`) });
  const checks = useQuery({ queryKey: ["checks", detail.id], queryFn: () => get<(CheckRecord & { query_bundle_id?: string; explanation?: string[] })[]>(`/model-versions/${detail.id}/checks`) });
  const [horizon, setHorizon] = useState(6);
  const [shown, setShown] = useState<string | null>(null);
  const release = useMutation({
    mutationFn: () => post<ReleaseRow>(`/model-versions/${detail.id}/releases`, { regression: "model", horizon }),
    onSuccess: (r) => { setShown(r.release_id); qc.invalidateQueries({ queryKey: ["releases", pid] });
      toast(r.status === "RELEASED" ? `已发布 ${r.release_id}` : `未通过发布检查：${r.record.reasons[0] ?? ""}`, r.status === "RELEASED" ? undefined : "err"); },
  });
  const optimize = useMutation({
    mutationFn: (objectiveId: string) => post<CheckRecord>(`/model-versions/${detail.id}/checks`, { query: {
      kind: "OPTIMIZE_OBJECTIVE", objective: { objective_id: objectiveId, goal_property: ir?.properties?.find((p) => p.kind === "goal")?.id,
        horizon: 12, levels: [{ id: objectiveId, model_objective: objectiveId }] }, bound: { max_steps: 12, timeout_ms: 30000 } } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["checks", detail.id] }); toast("成本目标查询已完成"); },
  });
  const mine = (releases.data ?? []).filter((r) => r.model_version_id === detail.id);
  const current = mine.find((r) => r.release_id === shown) ?? mine.at(-1);
  return (
    <div className="stack" data-testid="release-panel">
      <h3>成本目标</h3>
      {objectives.length === 0 ? <div className="small muted">该版本没有声明成本目标（可在 JSON 中添加 `objectives`，场景的成本目标按 id 引用）。</div> :
        <table className="table" aria-label="成本目标"><thead><tr><th>id</th><th>名称</th><th>单位</th><th>组成</th><th /></tr></thead>
          <tbody>{objectives.map((o) => <tr key={o.id}><td><code>{o.id}</code></td><td>{o.label ?? "—"}</td><td>{o.unit ?? "—"}</td>
            <td className="small">{o.terms.map((t) => t.kind).join(" + ")}{o.description ? <div className="muted">{o.description}</div> : null}</td>
            <td><button className="btn sm" disabled={optimize.isPending} onClick={() => optimize.mutate(o.id)}>求最优（≤12 步）</button></td></tr>)}</tbody></table>}
      <InlineError error={optimize.error} />

      <div className="row"><h3 className="grow">发布</h3>
        <label className="row small">查询上界 <input type="number" min={1} max={20} value={horizon} style={{ width: 64 }}
          onChange={(e) => setHorizon(Number(e.target.value))} /></label>
        <button className="btn primary" disabled={release.isPending} onClick={() => release.mutate()}>
          {release.isPending ? "检查中…" : `发布检查 v${detail.version}`}</button>
        <button className="btn" onClick={onDiff}>版本差异</button></div>
      <div className="small muted">发布前完成：驱动编译、类型检查、规则检查、有界查询（目标可达 / 不变量），并重放本模型的全部回归案例；
        结论与边界、假设一起记录，运行可固定引用已发布的版本。</div>
      <InlineError error={release.error} />
      {mine.length > 0 && <div className="chip-list">{mine.map((r) => <button key={r.release_id}
        className={`badge ${r.status === "RELEASED" ? "ok" : "err"} ${current?.release_id === r.release_id ? "accent" : ""}`}
        onClick={() => setShown(r.release_id)}>{r.release_id} · {r.status}</button>)}</div>}
      {current ? <ReleaseRecord r={current} /> : <Empty title="此版本还没有发布记录" />}

      <h3>查询包与假设</h3>
      <QueryState q={checks} empty={<Empty title="此版本还没有检查记录" />}>
        {(list) => <div className="table-wrap" style={{ maxHeight: 260 }}><table className="table" aria-label="查询包">
          <thead><tr><th>时间</th><th>查询</th><th>结论</th><th>假设与解释</th><th>查询包</th></tr></thead>
          <tbody>{list.map((c) => <tr key={c.id}><td className="nowrap small">{fmtTime(c.created_at)}</td>
            <td className="small">{String(c.query.kind)} {String(c.query.property_id ?? (c.query.objective as { objective_id?: string })?.objective_id ?? "")}</td>
            <td><VerdictBadge verdict={c.verdict} /></td>
            <td className="small">{(c.explanation ?? []).slice(0, 2).join("；") || "—"}</td>
            <td>{c.query_bundle_id ? <a className="btn sm" href={`/api/v1/query-bundles/${c.query_bundle_id}/export`} download><Icon name="export" size="sm" />{c.query_bundle_id.slice(0, 10)}</a> : "—"}</td>
          </tr>)}</tbody></table></div>}
      </QueryState>
    </div>
  );
}

function ReleaseRecord({ r }: { r: ReleaseRow }) {
  const rec = r.record;
  return (
    <div className="card pad stack" data-testid="release-record">
      <KV items={[
        ["发布", <span><code>{r.release_id}</code> <span className={`badge ${r.status === "RELEASED" ? "ok" : "err"}`}>{r.status}</span></span>],
        ["模型", `${rec.model.package_id}@v${rec.model.version}`],
        ["规则集", rec.ruleset ? `${rec.ruleset.ruleset_id}@${rec.ruleset.version}` : "—"],
        ["编译", rec.compiled.map((c) => `${c.backend}: ${Object.entries(c.stats).map(([k, v]) => `${k} ${v}`).join(", ")}`).join("；") || "—"],
        ["边界", rec.bounds.join("；")],
        ["假设", rec.assumptions.join("；")],
        ["时间", fmtTime(r.created_at)],
      ]} />
      {rec.reasons.length > 0 && <div className="callout err small">{rec.reasons.join("；")}</div>}
      <table className="table" aria-label="发布检查"><thead><tr><th>检查</th><th>对象</th><th>结论</th><th>说明</th></tr></thead>
        <tbody>{rec.checks.map((c, i) => <tr key={i}><td className="small">{c.kind}</td><td><code className="small">{c.subject}</code></td>
          <td><span className={`badge ${c.passed ? "ok" : "err"}`}>{c.verdict}</span></td>
          <td className="small">{c.detail ?? ""}{c.bound ? ` （≤${c.bound.max_steps} 步）` : ""}</td></tr>)}</tbody></table>
      {rec.regression.length > 0 && <table className="table" aria-label="回归案例"><thead><tr><th>回归案例</th><th>结果</th><th>说明</th></tr></thead>
        <tbody>{rec.regression.map((x) => <tr key={x.case_id}><td><code className="small">{x.case_id}</code></td>
          <td><span className={`badge ${x.status === "PASS" ? "ok" : "err"}`}>{x.status}</span></td><td className="small">{x.detail}</td></tr>)}</tbody></table>}
      {rec.log && <a className="small" href={`/api/v1/artifacts/${rec.log.digest.value}`}>检查日志</a>}
    </div>
  );
}
