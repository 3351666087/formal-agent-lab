import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { del, get, post, put, type CatalogEntry, type Scenario, type Strategy } from "../api";
import { Empty, InlineError, Json, Modal, QueryState, SchemaForm, Tabs, useToast } from "../ui";
import { useParams } from "react-router";

type Iface = "PLANNER" | "ENVIRONMENT" | "VERIFIER" | "EVALUATOR" | "MODEL_FRONTEND";

export function StrategiesPage() {
  const { pid } = useParams();
  const qc = useQueryClient();
  const toast = useToast();
  const [iface, setIface] = useState<Iface>("PLANNER");
  const catalog = useQuery({ queryKey: ["plugins", iface], queryFn: () => get<CatalogEntry[]>(`/plugins?interface=${iface}`) });
  const strategies = useQuery({ queryKey: ["strategies", pid], queryFn: () => get<Strategy[]>(`/projects/${pid}/strategies`) });
  const scenarios = useQuery({ queryKey: ["scenarios", pid], queryFn: () => get<Scenario[]>(`/projects/${pid}/scenarios`) });
  const [editing, setEditing] = useState<Strategy | "new" | null>(null);
  const [compatScenario, setCompatScenario] = useState("");
  const remove = useMutation({
    mutationFn: (id: string) => del(`/strategies/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["strategies", pid] }); toast("已删除策略配置"); },
  });
  return (
    <>
      <div className="page-head">
        <div className="grow"><h1>策略注册表</h1>
          <p>插件通过 entry point 注册；能力、配置 schema、版本与兼容性全部来自插件描述符。项目中的策略配置固定插件版本与参数。</p></div>
        <button className="btn primary" onClick={() => setEditing("new")}>新建策略配置</button>
      </div>

      <div className="card">
        <div className="card-head"><h2 className="grow">项目策略配置</h2>
          <label className="row small">兼容性检查场景
            <select value={compatScenario} onChange={(e) => setCompatScenario(e.target.value)}>
              <option value="">—</option>{scenarios.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        </div>
        <QueryState q={strategies} empty={<Empty title="还没有策略配置" action={<button className="btn sm primary" onClick={() => setEditing("new")}>新建</button>} />}>
          {(list) => (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>名称</th><th>插件</th><th>类别</th><th>配置</th>{compatScenario && <th>兼容性</th>}<th /></tr></thead>
                <tbody>{list.map((s) => (
                  <tr key={s.id}>
                    <td><strong>{s.name}</strong></td>
                    <td><code className="small">{s.plugin_id}@{s.plugin_version}</code></td>
                    <td><span className="badge">{s.descriptor.ui.category ?? s.descriptor.interface}</span></td>
                    <td className="small mono">{Object.keys(s.config).length ? JSON.stringify(s.config) : "默认"}</td>
                    {compatScenario && <td><Compat strategy={s.id} scenario={compatScenario} /></td>}
                    <td className="nowrap"><button className="btn sm" onClick={() => setEditing(s)}>编辑</button>{" "}
                      <button className="btn sm ghost danger" onClick={() => { if (confirm(`删除「${s.name}」？`)) remove.mutate(s.id); }}>删除</button></td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
        </QueryState>
      </div>

      <div className="card">
        <Tabs label="插件接口" value={iface} onChange={setIface} tabs={[
          { id: "PLANNER", label: "策略（Planner）" }, { id: "ENVIRONMENT", label: "环境" }, { id: "VERIFIER", label: "验证器" },
          { id: "EVALUATOR", label: "评分器" }, { id: "MODEL_FRONTEND", label: "模型前端" }]} />
        <div className="card-body">
          <QueryState q={catalog} empty={<Empty title="没有已安装的此类插件" />}>
            {(list) => (
              <div className="grid cols-2">
                {list.map((e) => <PluginCard key={`${e.descriptor.plugin_id}@${e.descriptor.version}`} entry={e} />)}
              </div>
            )}
          </QueryState>
        </div>
      </div>
      {editing && <StrategyEditor pid={pid!} strategy={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function Compat({ strategy, scenario }: { strategy: string; scenario: string }) {
  const q = useQuery({ queryKey: ["compat", strategy, scenario],
    queryFn: () => get<{ compatible: boolean; problems: string[] }>(`/strategies/${strategy}/compatibility?scenario_id=${scenario}`) });
  if (q.isPending) return <span className="muted small">…</span>;
  if (q.isError) return <span className="badge err">错误</span>;
  return q.data.compatible ? <span className="badge ok">兼容</span>
    : <span className="badge err" title={q.data.problems.join("；")}>不兼容：{q.data.problems[0]}</span>;
}

function PluginCard({ entry }: { entry: CatalogEntry }) {
  const d = entry.descriptor;
  return (
    <article className="card pad stack">
      <div className="row"><h3 style={{ flex: 1 }}>{d.ui.label}</h3>
        {entry.available ? <span className="badge ok">可用</span> : <span className="badge warn" title={entry.availability_note}>未配置</span>}</div>
      <div className="small"><code>{d.plugin_id}@{d.version}</code> · 接口 {d.interface} v{d.interface_version}</div>
      {d.ui.description && <div className="small muted">{d.ui.description}</div>}
      <div className="chip-list">{d.capabilities.map((c) => <span key={c.id} className="badge accent" title={JSON.stringify(c.params)}>{c.id}</span>)}</div>
      <div className="small muted">profile：{d.semantic_profiles.join(", ") || "—"} · 许可：{d.license ?? "—"} · 来源：{entry.source}</div>
      {entry.availability_note && <div className="small">{entry.availability_note}</div>}
      <details><summary className="small muted">配置 schema 与描述符摘要</summary>
        <Json value={{ config_schema: d.config_schema, descriptor_digest: entry.descriptor_digest }} maxHeight={220} /></details>
    </article>
  );
}

function StrategyEditor({ pid, strategy, onClose }: { pid: string; strategy: Strategy | null; onClose: () => void }) {
  const qc = useQueryClient();
  const planners = useQuery({ queryKey: ["plugins", "PLANNER"], queryFn: () => get<CatalogEntry[]>("/plugins?interface=PLANNER") });
  const [name, setName] = useState(strategy?.name ?? "");
  const [plugin, setPlugin] = useState(strategy ? `${strategy.plugin_id}@${strategy.plugin_version}` : "");
  const [config, setConfig] = useState<Record<string, unknown>>(strategy?.config ?? {});
  const entry = planners.data?.find((p) => `${p.descriptor.plugin_id}@${p.descriptor.version}` === plugin);
  const save = useMutation({
    mutationFn: () => {
      const [plugin_id, plugin_version] = plugin.split("@");
      const body = { name, plugin_id, plugin_version, config };
      return strategy ? put(`/strategies/${strategy.id}`, body) : post(`/projects/${pid}/strategies`, body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["strategies", pid] }); onClose(); },
  });
  return (
    <Modal title={strategy ? "编辑策略配置" : "新建策略配置"} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>取消</button>
      <button className="btn primary" disabled={!name || !plugin || save.isPending} onClick={() => save.mutate()}>保存</button></>}>
      <div className="form-grid">
        <label className="field"><span>名称</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="field" style={{ gridColumn: "span 2" }}><span>策略插件</span>
          <select value={plugin} onChange={(e) => { setPlugin(e.target.value); setConfig({}); }}>
            <option value="" disabled>选择…</option>
            {planners.data?.map((p) => <option key={p.descriptor.plugin_id} value={`${p.descriptor.plugin_id}@${p.descriptor.version}`}>
              {p.descriptor.ui.label} ({p.descriptor.version}){p.available ? "" : " — 未配置"}</option>)}</select></label>
      </div>
      {entry && <>
        {!entry.available && <div className="callout warn small">{entry.availability_note}</div>}
        <SchemaForm schema={entry.descriptor.config_schema as never} value={config} onChange={setConfig} />
      </>}
      <InlineError error={save.error} />
    </Modal>
  );
}
