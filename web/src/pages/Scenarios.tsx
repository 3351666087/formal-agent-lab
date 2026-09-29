import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import type { ScenarioManifest } from "@formal-lab/contracts";
import { irOf, del, get, post, put, type CatalogEntry, type ModelSummary, type RunSummary, type Scenario, type VersionDetail } from "../api";
import { Icon } from "../icons";
import { Empty, fmtTime, InlineError, Loading, QueryState, SchemaForm, useToast, PageHead } from "../ui";

type Termination = { joint_goal: string | null; actor_goals: "IGNORE" | "ALL" | "ANY"; invariants: string[];
  on_no_action: "FAIL" | "SKIP_ACTOR" | "END"; no_progress_limit: number | null };
type Turns = { mode: "ROUND_ROBIN" | "FIXED_TABLE" | "JOINT_BATCH"; table: string[]; observation_timing: "TURN_START" | "ROUND_START";
  conflict_policy: "REVALIDATE" | "REJECT_STALE"; batch_timeout_s?: number | null };
type View = { include: string[]; exclude: string[]; settings: Record<string, string>; label: string | null };
const csv = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);
type Draft = {
  name: string; description: string; model_version_id: string;
  environment: ScenarioManifest["environment"]; participants: ScenarioManifest["participants"];
  objectives: ScenarioManifest["objectives"]; budget: ScenarioManifest["budget"]; seed: number;
  stop_conditions: ScenarioManifest["stop_conditions"];
  // v2 (P2-091): turn order, joint termination; v1 stop conditions stay usable for single-participant scenarios
  turns: Turns; termination: Termination | null;
};
const DEFAULT_TURNS: Turns = { mode: "ROUND_ROBIN", table: [], observation_timing: "TURN_START", conflict_policy: "REVALIDATE" };

export function ScenariosPage() {
  const { pid, sid } = useParams();
  const navigate = useNavigate();
  const scenarios = useQuery({ queryKey: ["scenarios", pid], queryFn: () => get<Scenario[]>(`/projects/${pid}/scenarios`) });
  return (
    <>
      <PageHead area="场景" icon="scenario" title="场景管理"
        description="场景固定模型版本、环境配置、参与者（策略、范围、视图）、轮次、预算、种子和停止条件；每次保存修订号 +1，运行时固定当时的场景快照。"
        actions={<button className="btn" onClick={() => navigate(`/p/${pid}/scenarios/new`)}>新建场景</button>} />
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

  // new scenario: build a default draft once the project's models are known
  useEffect(() => {
    if (!isNew || draft || !models.data?.length) return;
    const m = models.data[0];
    setModelId(m.id);
    get<ModelSummary>(`/models/${m.id}`).then((md) => setDraft({
      name: "新场景", description: "", model_version_id: md.versions!.at(-1)!.id,
      environment: { plugin: { plugin_id: "formal-lab.env.ir-world", version: "1.1.0" }, config: {} },
      participants: [{ actor_id: "agent", role: "operator", strategy: { plugin: { plugin_id: "formal-lab.planner.z3-bounded", version: "1.0.0" }, config: {} } }],
      objectives: [], budget: { max_steps: 60, max_wall_seconds: 600, max_model_calls: null, max_tokens: null }, seed: 0,
      stop_conditions: [{ kind: "NO_APPLICABLE_ACTION", property_id: null }], turns: DEFAULT_TURNS, termination: null,
    } as unknown as Draft));
  }, [isNew, draft, models.data]);

  // existing scenario: (re)initialise the draft only when the server copy changes — never on local edits
  useEffect(() => {
    if (isNew || !scenario.data) return;
    const m = scenario.data.manifest;
    setModelId(scenario.data.model_id ?? "");
    setDraft({ name: m.name, description: m.description ?? "", model_version_id: scenario.data.model_version_id,
      environment: m.environment, participants: m.participants, objectives: m.objectives, budget: m.budget, seed: m.seed,
      stop_conditions: m.stop_conditions, turns: { ...DEFAULT_TURNS, ...((m as never as { turns?: Turns }).turns ?? {}) },
      termination: ((m as never as { termination?: Termination | null }).termination ?? null) });
  }, [isNew, scenario.data]);

  const save = useMutation({
    mutationFn: () => {
      // v2 termination replaces the v1 stop conditions (the contract accepts one or the other)
      const body = draft!.termination ? { ...draft, stop_conditions: [] } : { ...draft, termination: null };
      return isNew ? post<Scenario>(`/projects/${pid}/scenarios`, body)
        : put<Scenario>(`/scenarios/${sid}`, { ...body, expected_revision: scenario.data?.revision });
    },
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
  const ir = irOf(versionDetail.data?.package) ?? undefined;
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
              error={save.error} basePath="/environment/config"
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

      <div className="card" data-testid="participants-editor">
        <div className="card-head"><h3 className="grow">参与者与默认策略</h3>
          <button className="btn sm" onClick={() => setDraft({ ...draft, participants: [...draft.participants, {
            ...draft.participants[draft.participants.length - 1], actor_id: `agent_${draft.participants.length + 1}`,
            label: null, goal: null, budget: null } as never] })}>＋ 参与者</button></div>
        <div className="card-body stack">
          {draft.participants.map((p, i) => {
            const entry = planners.data?.find((x) => x.descriptor.plugin_id === p.strategy.plugin.plugin_id);
            const pb = (p as never as { budget?: Record<string, number | null> | null }).budget ?? null;
            return (
              <div key={i} className="stack participant-edit" role="group" aria-label={`参与者 ${p.actor_id}`}>
                <div className="form-grid">
                  <label className="field"><span>参与者 ID</span><input value={p.actor_id} onChange={(e) => setP(i, { actor_id: e.target.value })} /></label>
                  <label className="field"><span>显示名</span><input value={(p as never as { label?: string }).label ?? ""} onChange={(e) => setP(i, { label: e.target.value || null } as never)} /></label>
                  <label className="field"><span>角色</span><input value={p.role} onChange={(e) => setP(i, { role: e.target.value })} /></label>
                  <label className="field"><span>自身目标</span>
                    <select value={(p as never as { goal?: string }).goal ?? ""} onChange={(e) => setP(i, { goal: e.target.value || null } as never)}>
                      <option value="">— 无（只看联合目标）—</option>
                      {props.filter((x) => x.kind === "goal").map((x) => <option key={x.id} value={x.id}>{x.label ?? x.id}</option>)}</select></label>
                  <label className="field" style={{ gridColumn: "span 2" }}><span>策略插件</span>
                    <select value={`${p.strategy.plugin.plugin_id}@${p.strategy.plugin.version}`} onChange={(e) => {
                      const [plugin_id, version] = e.target.value.split("@");
                      setP(i, { strategy: { plugin: { plugin_id, version }, config: {} } });
                    }}>{planners.data?.map((x) => <option key={`${x.descriptor.plugin_id}@${x.descriptor.version}`} value={`${x.descriptor.plugin_id}@${x.descriptor.version}`} disabled={!x.available && x.descriptor.plugin_id !== p.strategy.plugin.plugin_id}>
                      {x.descriptor.ui.label} ({x.descriptor.version}){x.available ? "" : " — 未配置"}</option>)}</select></label>
                  <label className="field"><span>独立预算：步数</span><input type="number" min={1} placeholder="共享" value={pb?.max_steps ?? ""}
                    onChange={(e) => setP(i, { budget: e.target.value === "" ? null : { ...(pb ?? {}), max_steps: Number(e.target.value) } } as never)} /></label>
                  <label className="field"><span>独立预算：模型调用</span><input type="number" min={0} placeholder="共享" value={pb?.max_model_calls ?? ""}
                    onChange={(e) => setP(i, { budget: e.target.value === "" && !pb?.max_steps ? null : { max_steps: pb?.max_steps ?? draft.budget.max_steps, ...(pb ?? {}), max_model_calls: e.target.value === "" ? null : Number(e.target.value) } } as never)} /></label>
                </div>
                <ViewFields value={(p as never as { view?: View | null }).view ?? null} onChange={(view) => setP(i, { view } as never)} />
                {entry && <SchemaForm schema={entry.descriptor.config_schema as never} value={p.strategy.config}
                  error={save.error} basePath={`/participants/${i}/strategy/config`}
                  onChange={(config) => setP(i, { strategy: { ...p.strategy, config } })} />}
                {draft.participants.length > 1 && <div className="row end"><button className="btn sm danger" onClick={() => setDraft({
                  ...draft, participants: draft.participants.filter((_, j) => j !== i) as Draft["participants"],
                  turns: { ...draft.turns, table: draft.turns.table.filter((a) => a !== p.actor_id) } })}>移除该参与者</button></div>}
              </div>
            );
          })}
          <div className="small muted">运行时可在实验运行台选择项目中的其它策略配置覆盖默认策略（可逐个参与者指定）。</div>
        </div>
      </div>

      {(draft.participants.length > 1 || draft.termination) && <div className="grid cols-2">
        <div className="card" data-testid="turns-editor">
          <div className="card-head"><h3 className="grow">轮次</h3></div>
          <div className="card-body stack">
            <label className="field"><span>轮次方式</span>
              <select value={draft.turns.mode} onChange={(e) => setDraft({ ...draft, turns: { ...draft.turns, mode: e.target.value as Turns["mode"],
                table: e.target.value === "FIXED_TABLE" ? draft.participants.map((x) => x.actor_id) : [],
                observation_timing: e.target.value === "JOINT_BATCH" ? "ROUND_START" : draft.turns.observation_timing,
                batch_timeout_s: e.target.value === "JOINT_BATCH" ? draft.turns.batch_timeout_s ?? null : null } })}>
                <option value="ROUND_ROBIN">轮流（按参与者顺序）</option><option value="FIXED_TABLE">固定轮次表</option>
                <option value="JOINT_BATCH">同步批次（每轮一次提交）</option></select></label>
            {draft.turns.mode === "JOINT_BATCH" && <>
              <div className="callout info small">每轮成员在轮初观测上各自提案，最后一名成员的那一步把整批一次提交给环境（环境需声明 env.batch_step）。</div>
              <label className="field"><span>批次期限（秒，可选）</span><input type="number" min={0.1} step={0.1} placeholder="不限"
                value={draft.turns.batch_timeout_s ?? ""} onChange={(e) => setDraft({ ...draft, turns: { ...draft.turns,
                  batch_timeout_s: e.target.value === "" ? null : Number(e.target.value) } })} />
                <span className="hint">超过期限仍未完成提案的成员记为 TIMED_OUT，其提案不提交</span></label></>}
            {draft.turns.mode === "FIXED_TABLE" && <label className="field"><span>轮次表（参与者 ID，逗号分隔，可重复）</span>
              <input value={draft.turns.table.join(",")} onChange={(e) => setDraft({ ...draft, turns: { ...draft.turns,
                table: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) } })} /></label>}
            <label className="field"><span>观测时点</span>
              <select value={draft.turns.observation_timing} disabled={draft.turns.mode === "JOINT_BATCH"} onChange={(e) => setDraft({ ...draft, turns: { ...draft.turns, observation_timing: e.target.value as Turns["observation_timing"] } })}>
                <option value="TURN_START">轮到时观测</option><option value="ROUND_START">每轮开始时统一观测（可能过时）</option></select></label>
            <label className="field"><span>共享资源冲突</span>
              <select value={draft.turns.conflict_policy} onChange={(e) => setDraft({ ...draft, turns: { ...draft.turns, conflict_policy: e.target.value as Turns["conflict_policy"] } })}>
                <option value="REVALIDATE">重新校验前提（仍成立则执行）</option><option value="REJECT_STALE">依赖位置已变化则拒绝</option></select></label>
          </div>
        </div>
        <div className="card" data-testid="termination-editor">
          <div className="card-head"><h3 className="grow">联合终止条件</h3></div>
          <div className="card-body stack">
            {draft.termination ? <>
              <label className="field"><span>联合目标</span>
                <select value={draft.termination.joint_goal ?? ""} onChange={(e) => setDraft({ ...draft, termination: { ...draft.termination!, joint_goal: e.target.value || null } })}>
                  <option value="">— 无 —</option>{props.filter((x) => x.kind === "goal").map((x) => <option key={x.id} value={x.id}>{x.label ?? x.id}</option>)}</select></label>
              <label className="field"><span>参与者目标</span>
                <select value={draft.termination.actor_goals} onChange={(e) => setDraft({ ...draft, termination: { ...draft.termination!, actor_goals: e.target.value as Termination["actor_goals"] } })}>
                  <option value="IGNORE">只报告，不结束运行</option><option value="ALL">全部达成即成功</option><option value="ANY">任一达成即成功</option></select></label>
              <label className="field"><span>无可选动作时</span>
                <select value={draft.termination.on_no_action} onChange={(e) => setDraft({ ...draft, termination: { ...draft.termination!, on_no_action: e.target.value as Termination["on_no_action"] } })}>
                  <option value="FAIL">运行失败</option><option value="SKIP_ACTOR">该参与者跳过本轮</option><option value="END">结束（目标成立则成功）</option></select></label>
              <label className="field"><span>无进展上限（连续轮次）</span><input type="number" min={1} placeholder="不限" value={draft.termination.no_progress_limit ?? ""}
                onChange={(e) => setDraft({ ...draft, termination: { ...draft.termination!, no_progress_limit: e.target.value === "" ? null : Number(e.target.value) } })} /></label>
              <button className="btn sm" onClick={() => setDraft({ ...draft, termination: null })}>改用 v1 停止条件</button>
            </> : <button className="btn sm" onClick={() => setDraft({ ...draft, termination: {
              joint_goal: draft.stop_conditions.find((x) => x.kind === "GOAL_REACHED")?.property_id ?? props.find((x) => x.kind === "goal")?.id ?? null,
              actor_goals: "IGNORE", invariants: [], on_no_action: "SKIP_ACTOR", no_progress_limit: 12 } })}>启用 v2 联合终止条件</button>}
          </div>
        </div>
      </div>}

      <InlineError error={save.error ?? start.error ?? copy.error ?? remove.error} />
      <div className="row end">
        {!isNew && <button className="btn danger" onClick={() => { if (confirm("删除该场景？已完成的实验保留其场景快照。")) remove.mutate(); }}>删除</button>}
        {!isNew && <button className="btn" onClick={() => copy.mutate()} disabled={copy.isPending}>复制</button>}
        <button className="btn primary" onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "保存中…" : isNew ? "创建场景" : "保存（新修订）"}</button>
        {!isNew && <button className="btn primary" onClick={() => start.mutate()} disabled={start.isPending}><Icon name="play" />运行实验</button>}
      </div>
      {!isNew && <div className="muted small">更新于 {fmtTime(scenario.data!.updated_at)}</div>}
    </div>
  );
}

/** What this participant's planner receives (phase 3A): location families or paths; empty include = everything. */
function ViewFields({ value, onChange }: { value: View | null; onChange: (v: View | null) => void }) {
  const v: View = value ?? { include: [], exclude: [], settings: {}, label: null };
  const set = (patch: Partial<View>) => {
    const next = { ...v, ...patch };
    onChange(!next.include.length && !next.exclude.length && !Object.keys(next.settings).length && !next.label ? null : next);
  };
  return (
    <div className="form-grid" role="group" aria-label="参与者视图">
      <label className="field"><span>视图：只含位置族</span><input value={v.include.join(", ")} placeholder="全部（留空）"
        onChange={(e) => set({ include: csv(e.target.value) })} /><span className="hint">逗号分隔，如 clock, dock, stock</span></label>
      <label className="field"><span>视图：隐藏位置族</span><input value={v.exclude.join(", ")} placeholder="无"
        onChange={(e) => set({ exclude: csv(e.target.value) })} /><span className="hint">规划器把隐藏位置当作从未观测</span></label>
      <label className="field"><span>视图名称</span><input value={v.label ?? ""} onChange={(e) => set({ label: e.target.value || null })} /></label>
    </div>
  );
}
