import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import type { ScenarioManifest } from "@formal-lab/contracts";
import { del, get, post, put, type CatalogEntry, type ModelSummary, type RunSummary, type Scenario, type VersionDetail } from "../api";
import { Empty, fmtTime, InlineError, Loading, QueryState, SchemaForm, useToast } from "../ui";

type Draft = {
  name: string; description: string; model_version_id: string;
  environment: ScenarioManifest["environment"]; participants: ScenarioManifest["participants"];
  objectives: ScenarioManifest["objectives"]; budget: ScenarioManifest["budget"]; seed: number;
  stop_conditions: ScenarioManifest["stop_conditions"];
};

export function ScenariosPage() {
  const { pid, sid } = useParams();
  const navigate = useNavigate();
  const scenarios = useQuery({ queryKey: ["scenarios", pid], queryFn: () => get<Scenario[]>(`/projects/${pid}/scenarios`) });
  return (
    <>
      <div className="page-head">
        <div className="grow"><h1>场景管理</h1>
          <p>场景固定模型版本、环境配置、参与者与策略、预算、种子和停止条件；每次保存修订号 +1，运行时固定当时的场景快照。</p></div>
        <button className="btn" onClick={() => navigate(`/p/${pid}/scenarios/new`)}>新建场景</button>
      </div>
      <div className="split">
        <div className="card">
          <div className="card-head"><h2 className="grow">场景</h2></div>
          <QueryState q={scenarios} empty={<Empty title="还没有场景" hint="先在模型工作台创建模型，再新建场景。" />}>
            {(list) => (
              <div className="nav" style={{ padding: 6 }}>
                {list.map((s) => (
                  <Link key={s.id} to={`/p/${pid}/scenarios/${s.id}`} className={s.id === sid ? "active" : ""}>
                    <span className="ellipsis">{s.name}</span><span className="num">r{s.revision}</span>
                  </Link>
                ))}
              </div>
            )}
          </QueryState>
        </div>
        {sid ? <ScenarioEditor key={sid} pid={pid!} sid={sid} /> : <div className="card"><Empty title="选择一个场景" /></div>}
      </div>
    </>
  );
}

function ScenarioEditor({ pid, sid }: { pid: string; sid: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const isNew = sid === "new";
  const scenario = useQuery({ queryKey: ["scenario", sid], enabled: !isNew, queryFn: () => get<Scenario>(`/scenarios/${sid}`) });
  const models = useQuery({ queryKey: ["models", pid], queryFn: () => get<ModelSummary[]>(`/projects/${pid}/models`) });
  const envs = useQuery({ queryKey: ["plugins", "ENVIRONMENT"], queryFn: () => get<CatalogEntry[]>("/plugins?interface=ENVIRONMENT") });
  const planners = useQuery({ queryKey: ["plugins", "PLANNER"], queryFn: () => get<CatalogEntry[]>("/plugins?interface=PLANNER") });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [modelId, setModelId] = useState<string>("");
  const versionDetail = useQuery({
    queryKey: ["model-version-by-id", draft?.model_version_id, modelId], enabled: Boolean(modelId && draft?.model_version_id),
    queryFn: async () => {
      const m = await get<ModelSummary>(`/models/${modelId}`);
      const v = m.versions?.find((x) => x.id === draft!.model_version_id);
      return v ? get<VersionDetail>(`/models/${modelId}/versions/${v.version}`) : null;
    },
  });
  const modelDetail = useQuery({ queryKey: ["model", modelId], enabled: Boolean(modelId), queryFn: () => get<ModelSummary>(`/models/${modelId}`) });

  useEffect(() => {
    if (isNew) {
      if (!draft && models.data?.length) {
        const m = models.data[0];
        setModelId(m.id);
        get<ModelSummary>(`/models/${m.id}`).then((md) => setDraft({
          name: "新场景", description: "", model_version_id: md.versions!.at(-1)!.id,
          environment: { plugin: { plugin_id: "formal-lab.env.ir-world", version: "1.0.0" }, config: {} },
          participants: [{ actor_id: "agent", role: "operator", strategy: { plugin: { plugin_id: "formal-lab.planner.z3-bounded", version: "1.0.0" }, config: {} } }],
          objectives: [], budget: { max_steps: 60, max_wall_seconds: 600, max_model_calls: null, max_tokens: null }, seed: 0,
          stop_conditions: [{ kind: "NO_APPLICABLE_ACTION", property_id: null }],
        } as unknown as Draft));
      }
      return;
    }
    if (scenario.data) {
      const m = scenario.data.manifest;
      setModelId(scenario.data.model_id ?? "");
      setDraft({ name: m.name, description: m.description ?? "", model_version_id: scenario.data.model_version_id,
        environment: m.environment, participants: m.participants, objectives: m.objectives, budget: m.budget, seed: m.seed,
        stop_conditions: m.stop_conditions });
    }
  }, [scenario.data, isNew, models.data, draft]);

  const save = useMutation({
    mutationFn: () => isNew ? post<Scenario>(`/projects/${pid}/scenarios`, draft)
      : put<Scenario>(`/scenarios/${sid}`, { ...draft, expected_revision: scenario.data?.revision }),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["scenarios", pid] });
      qc.invalidateQueries({ queryKey: ["scenario", s.id] });
      toast(`已保存（修订 r${s.revision}）`);
      if (isNew) navigate(`/p/${pid}/scenarios/${s.id}`);
    },
  });
  const copy = useMutation({
    mutationFn: () => post<Scenario>(`/scenarios/${sid}/copy`, {}),
    onSuccess: (s) => { qc.invalidateQueries({ queryKey: ["scenarios", pid] }); navigate(`/p/${pid}/scenarios/${s.id}`); },
  });
  const remove = useMutation({
    mutationFn: () => del(`/scenarios/${sid}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["scenarios", pid] }); navigate(`/p/${pid}/scenarios`); },
  });
  const start = useMutation({
    mutationFn: () => post<RunSummary>(`/projects/${pid}/runs`, { scenario_id: sid }),
    onSuccess: (r) => navigate(`/p/${pid}/runs/${r.id}`),
  });

  if (!isNew && scenario.isPending) return <div className="card"><Loading /></div>;
  if (!draft) return <div className="card">{isNew && models.data?.length === 0 ? <Empty title="项目中没有模型" hint="先在模型工作台创建模型。" /> : <Loading />}</div>;
  const ir = versionDetail.data?.package.ir;
  const props = ir?.properties ?? [];
  const envEntry = envs.data?.find((e) => e.descriptor.plugin_id === draft.environment.plugin.plugin_id);
  const setP = (i: number, patch: Partial<Draft["participants"][number]>) =>
    setDraft({ ...draft, participants: draft.participants.map((p, j) => (j === i ? { ...p, ...patch } : p)) as Draft["participants"] });
  const stop = (kind: string) => draft.stop_conditions.find((s) => s.kind === kind);
  const toggleStop = (kind: string, on: boolean, property_id?: string) => setDraft({
    ...draft, stop_conditions: on ? [...draft.stop_conditions.filter((s) => s.kind !== kind), { kind, property_id } as never]
      : draft.stop_conditions.filter((s) => s.kind !== kind) });
  return (
    <div className="stack">
      <div className="card">
        <div className="card-head">
          <h2 className="grow">{isNew ? "新建场景" : draft.name}</h2>
          {!isNew && <span className="badge">修订 r{scenario.data!.revision}</span>}
          {!isNew && scenario.data!.copied_from && <span className="badge outline">复制自 {scenario.data!.copied_from.slice(0, 10)}</span>}
        </div>
        <div className="card-body stack">
          <div className="form-grid">
            <label className="field"><span>名称</span><input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
            <label className="field"><span>模型</span>
              <select value={modelId} onChange={async (e) => {
                const m = await get<ModelSummary>(`/models/${e.target.value}`);
                setModelId(m.id); setDraft({ ...draft, model_version_id: m.versions!.at(-1)!.id });
              }}>{models.data?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
            <label className="field"><span>固定模型版本</span>
              <select value={draft.model_version_id} onChange={(e) => setDraft({ ...draft, model_version_id: e.target.value })}>
                {modelDetail.data?.versions?.map((v) => <option key={v.id} value={v.id}>v{v.version} · {v.digest.slice(0, 8)}</option>)}</select></label>
            <label className="field"><span>种子</span><input type="number" value={draft.seed} onChange={(e) => setDraft({ ...draft, seed: Number(e.target.value) })} /></label>
          </div>
          <label className="field"><span>说明</span><input value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></label>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <div className="card-head"><h3 className="grow">环境</h3><span className="badge">{envEntry?.descriptor.ui.label}</span></div>
          <div className="card-body stack">
            <label className="field"><span>环境插件</span>
              <select value={`${draft.environment.plugin.plugin_id}@${draft.environment.plugin.version}`} onChange={(e) => {
                const [plugin_id, version] = e.target.value.split("@");
                setDraft({ ...draft, environment: { plugin: { plugin_id, version }, config: {} } });
              }}>{envs.data?.map((e) => <option key={e.descriptor.plugin_id} value={`${e.descriptor.plugin_id}@${e.descriptor.version}`}>{e.descriptor.ui.label} ({e.descriptor.version})</option>)}</select></label>
            {envEntry && <SchemaForm schema={envEntry.descriptor.config_schema as never} value={draft.environment.config}
              onChange={(config) => setDraft({ ...draft, environment: { ...draft.environment, config } })} />}
            <div className="small muted">observation.delay_steps 使参与者看到延迟的事实：当前值为“未知”，并附带上次已知值（实验语义，不改变模型）。</div>
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h3 className="grow">预算与停止条件</h3></div>
          <div className="card-body stack">
            <div className="form-grid">
              {(["max_steps", "max_wall_seconds", "max_model_calls", "max_tokens"] as const).map((k) => (
                <label className="field" key={k}><span>{{ max_steps: "步数", max_wall_seconds: "墙钟秒数", max_model_calls: "模型调用", max_tokens: "Tokens" }[k]}</span>
                  <input type="number" min={0} value={draft.budget[k] ?? ""} placeholder="不限"
                    onChange={(e) => setDraft({ ...draft, budget: { ...draft.budget, [k]: e.target.value === "" ? null : Number(e.target.value) } })} /></label>
              ))}
            </div>
            <label className="row small"><input type="checkbox" checked={Boolean(stop("GOAL_REACHED"))}
              onChange={(e) => toggleStop("GOAL_REACHED", e.target.checked, props.find((p) => p.kind === "goal")?.id)} />达到目标即成功
              {stop("GOAL_REACHED") && <select value={stop("GOAL_REACHED")!.property_id ?? ""} onChange={(e) => toggleStop("GOAL_REACHED", true, e.target.value)}>
                {props.filter((p) => p.kind === "goal").map((p) => <option key={p.id} value={p.id}>{p.label ?? p.id}</option>)}</select>}</label>
            <label className="row small"><input type="checkbox" checked={Boolean(stop("INVARIANT_VIOLATED"))}
              onChange={(e) => toggleStop("INVARIANT_VIOLATED", e.target.checked, props.find((p) => p.kind === "invariant")?.id)} />不变量被违反即失败
              {stop("INVARIANT_VIOLATED") && <select value={stop("INVARIANT_VIOLATED")!.property_id ?? ""} onChange={(e) => toggleStop("INVARIANT_VIOLATED", true, e.target.value)}>
                {props.filter((p) => p.kind === "invariant").map((p) => <option key={p.id} value={p.id}>{p.label ?? p.id}</option>)}</select>}</label>
            <label className="row small"><input type="checkbox" checked={Boolean(stop("NO_APPLICABLE_ACTION"))}
              onChange={(e) => toggleStop("NO_APPLICABLE_ACTION", e.target.checked)} />无可用动作即失败</label>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h3 className="grow">参与者与默认策略</h3></div>
        <div className="card-body stack">
          {draft.participants.map((p, i) => {
            const entry = planners.data?.find((x) => x.descriptor.plugin_id === p.strategy.plugin.plugin_id);
            return (
              <div key={i} className="stack">
                <div className="form-grid">
                  <label className="field"><span>参与者 ID</span><input value={p.actor_id} onChange={(e) => setP(i, { actor_id: e.target.value })} /></label>
                  <label className="field"><span>角色</span><input value={p.role} onChange={(e) => setP(i, { role: e.target.value })} /></label>
                  <label className="field" style={{ gridColumn: "span 2" }}><span>策略插件</span>
                    <select value={`${p.strategy.plugin.plugin_id}@${p.strategy.plugin.version}`} onChange={(e) => {
                      const [plugin_id, version] = e.target.value.split("@");
                      setP(i, { strategy: { plugin: { plugin_id, version }, config: {} } });
                    }}>{planners.data?.map((x) => <option key={x.descriptor.plugin_id} value={`${x.descriptor.plugin_id}@${x.descriptor.version}`} disabled={!x.available && x.descriptor.plugin_id !== p.strategy.plugin.plugin_id}>
                      {x.descriptor.ui.label} ({x.descriptor.version}){x.available ? "" : " — 未配置"}</option>)}</select></label>
                </div>
                {entry && <SchemaForm schema={entry.descriptor.config_schema as never} value={p.strategy.config}
                  onChange={(config) => setP(i, { strategy: { ...p.strategy, config } })} />}
              </div>
            );
          })}
          <div className="small muted">运行时可在实验运行台选择项目中的其它策略配置覆盖默认策略。</div>
        </div>
      </div>

      <InlineError error={save.error ?? start.error ?? copy.error ?? remove.error} />
      <div className="row end">
        {!isNew && <button className="btn danger" onClick={() => { if (confirm("删除该场景？已完成的实验保留其场景快照。")) remove.mutate(); }}>删除</button>}
        {!isNew && <button className="btn" onClick={() => copy.mutate()} disabled={copy.isPending}>复制</button>}
        <button className="btn primary" onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "保存中…" : isNew ? "创建场景" : "保存（新修订）"}</button>
        {!isNew && <button className="btn primary" onClick={() => start.mutate()} disabled={start.isPending}>▶ 运行实验</button>}
      </div>
      {!isNew && <div className="muted small">更新于 {fmtTime(scenario.data!.updated_at)}</div>}
    </div>
  );
}
