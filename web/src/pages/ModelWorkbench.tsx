import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import type { BoundedCheckResult, ModelIR } from "@formal-lab/contracts";
import {
  get, irOf, post, type CheckRecord, type ModelChange, type ModelSummary, type Validation, type VersionDetail,
} from "../api";
import { ModelGraph } from "../components/ModelGraph";
import { ObjectivesAndReleases } from "../components/ReleasePanel";
import { ProbabilisticPanel } from "../components/ProbabilisticPanel";
import { blankModel, effectLines, exprText, typeText } from "../ir";
import { Icon } from "../icons";
import {
  Empty, ErrorState, fmtTime, InlineError, Json, JsonField, KV, Loading, Modal, QueryState, Tabs, useToast, VerdictBadge, PageHead } from "../ui";

type Tab = "graph" | "form" | "json" | "diff" | "check" | "release" | "prob" | "caps";
const draftKey = (modelId: string) => `fal:model-draft:${modelId}`;

export function ModelWorkbench() {
  const { pid, modelId } = useParams();
  const navigate = useNavigate();
  const models = useQuery({ queryKey: ["models", pid], queryFn: () => get<ModelSummary[]>(`/projects/${pid}/models`) });
  const [creating, setCreating] = useState(false);
  useEffect(() => {
    if (!modelId && models.data?.length) navigate(`/p/${pid}/models/${models.data[0].id}`, { replace: true });
  }, [modelId, models.data, pid, navigate]);
  return (
    <>
      <PageHead area="模型" icon="model" title="模型工作台"
        description="编辑有限状态模型（deterministic_finite_v1）：结构图、表单、类型错误、版本差异、编译与有界检查。每次保存产生不可变的新版本；能力报告说明每个语义驱动与验证器实际能做什么。"
        actions={<button className="btn" onClick={() => setCreating(true)}>新建模型</button>} />
      <div className="split">
        <div className="card">
          <div className="card-head"><h2 className="grow">模型</h2></div>
          <QueryState q={models} empty={<Empty title="项目中还没有模型" action={<button className="btn primary sm" onClick={() => setCreating(true)}>新建模型</button>} />}>
            {(list) => (
              <div className="nav" style={{ padding: 6 }}>
                {list.map((m) => (
                  <Link key={m.id} to={`/p/${pid}/models/${m.id}`} className={m.id === modelId ? "active" : ""}>
                    <span className="ellipsis">{m.name}</span><span className="num">v{m.latest_version}</span>
                  </Link>
                ))}
              </div>
            )}
          </QueryState>
        </div>
        {modelId ? <ModelEditor key={modelId} modelId={modelId} /> : !models.isPending &&
          <div className="card"><Empty title="选择或新建一个模型" /></div>}
      </div>
      {creating && <CreateModel pid={pid!} onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateModel({ pid, onClose }: { pid: string; onClose: () => void }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [packageId, setPackageId] = useState("");
  const [name, setName] = useState("");
  const [ir, setIr] = useState<ModelIR>(blankModel());
  const create = useMutation({
    mutationFn: () => post<ModelSummary>(`/projects/${pid}/models`, { package_id: packageId, name: name || packageId, ir }),
    onSuccess: (m) => { qc.invalidateQueries({ queryKey: ["models", pid] }); onClose(); navigate(`/p/${pid}/models/${m.id}`); },
  });
  return (
    <Modal title="新建模型" onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>取消</button>
      <button className="btn primary" disabled={!/^[A-Za-z0-9][A-Za-z0-9._:@/-]*$/.test(packageId) || create.isPending}
        onClick={() => create.mutate()}>创建 v1</button></>}>
      <div className="form-grid">
        <label className="field"><span>package_id</span><input value={packageId} onChange={(e) => setPackageId(e.target.value)} placeholder="例如 my-model" /></label>
        <label className="field"><span>名称</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
      </div>
      <label className="field"><span>初始 IR（可粘贴已有模型 JSON）</span><JsonField value={ir} onChange={setIr} rows={14} /></label>
      <InlineError error={create.error} />
    </Modal>
  );
}

function ModelEditor({ modelId }: { modelId: string }) {
  const { pid } = useParams();
  const qc = useQueryClient();
  const toast = useToast();
  const model = useQuery({ queryKey: ["model", modelId], queryFn: () => get<ModelSummary>(`/models/${modelId}`) });
  const [version, setVersion] = useState<number | null>(null);
  const current = version ?? model.data?.latest_version ?? null;
  const detail = useQuery({
    queryKey: ["model-version", modelId, current], enabled: current !== null,
    queryFn: () => get<VersionDetail>(`/models/${modelId}/versions/${current}`),
  });
  const [draft, setDraft] = useState<ModelIR | null>(null);
  const [restored, setRestored] = useState(false);
  const [tab, setTab] = useState<Tab>("graph");
  const [note, setNote] = useState("");

  // initialise the working copy from the version (or restore an unsaved local draft after a refresh)
  useEffect(() => {
    if (!detail.data) return;
    const saved = localStorage.getItem(draftKey(modelId));
    if (saved && version === null) {
      try {
        const parsed = JSON.parse(saved) as { base: number; ir: ModelIR };
        if (parsed.base === detail.data.version) { setDraft(parsed.ir); setRestored(true); return; }
      } catch { /* ignore broken drafts */ }
    }
    setDraft(structuredClone(irOf(detail.data.package)!));
  }, [detail.data, modelId, version]);

  const baseIr = irOf(detail.data?.package) ?? undefined;
  const dirty = useMemo(() => draft && baseIr && JSON.stringify(draft) !== JSON.stringify(baseIr), [draft, baseIr]);
  useEffect(() => {
    if (!draft || !detail.data) return;
    if (dirty) localStorage.setItem(draftKey(modelId), JSON.stringify({ base: detail.data.version, ir: draft }));
    else localStorage.removeItem(draftKey(modelId));
  }, [draft, dirty, detail.data, modelId]);

  // debounced live validation of the working copy
  const [validation, setValidation] = useState<Validation | null>(null);
  useEffect(() => {
    if (!draft) return;
    const t = setTimeout(() => { post<Validation>("/models/validate", { ir: draft }).then(setValidation).catch(() => setValidation(null)); }, 350);
    return () => clearTimeout(t);
  }, [draft]);

  const save = useMutation({
    mutationFn: () => post<{ version: number }>(`/models/${modelId}/versions`, { ir: draft, note: note || null, parent_version: current }),
    onSuccess: (v) => {
      localStorage.removeItem(draftKey(modelId));
      qc.invalidateQueries({ queryKey: ["model", modelId] });
      qc.invalidateQueries({ queryKey: ["models"] });
      setVersion(v.version);
      setNote("");
      setRestored(false);
      toast(v.version === current ? "内容未变化，未创建新版本" : `已保存为 v${v.version}`);
    },
  });

  if (model.isPending || detail.isPending) return <div className="card"><Loading /></div>;
  if (model.isError) return <div className="card"><ErrorState error={model.error} retry={() => model.refetch()} /></div>;
  if (detail.isError) return <div className="card"><ErrorState error={detail.error} retry={() => detail.refetch()} /></div>;
  const d = detail.data!;
  const issues = validation?.issues ?? [];
  const schemaErrors = validation?.schema_errors ?? [];
  const invalid = Boolean(validation && !validation.valid);

  return (
    <div className="stack">
      <div className="card">
        <div className="card-head">
          <h2 className="grow">{model.data!.name}</h2>
          <label className="row small">版本
            <select value={current ?? ""} onChange={(e) => { setVersion(Number(e.target.value)); setRestored(false); }}>
              {model.data!.versions?.map((v) => <option key={v.version} value={v.version}>v{v.version}{v.note ? ` · ${v.note}` : ""}</option>)}
            </select>
          </label>
          <span className="badge info">{d.semantic_profile}</span>
        </div>
        <div className="card-body stack">
          <KV items={[
            ["package_id", <code>{model.data!.package_id}</code>],
            ["摘要", <code title={d.digest}>{d.digest.slice(0, 16)}…</code>],
            ["规模", `${d.summary.state_locations} 个状态位置 · ${d.summary.ground_actions} 个基础动作`],
            ["创建", `${fmtTime(d.created_at)}${d.parent_version ? ` · 基于 v${d.parent_version}` : ""}`],
          ]} />
          {restored && <div className="callout warn small">已恢复刷新前未保存的草稿（基于 v{d.version}）。
            <button className="btn sm ghost" onClick={() => { localStorage.removeItem(draftKey(modelId)); setDraft(structuredClone(irOf(d.package)!)); setRestored(false); }}>丢弃草稿</button></div>}
          <div className="row">
            <span className={`badge ${!validation ? "" : validation.valid ? "ok" : "err"}`} role="status">
              {!validation ? "校验中…" : validation.valid ? "类型检查通过" : `${issues.length + schemaErrors.length} 个问题`}
            </span>
            {dirty ? <span className="badge warn">有未保存修改</span> : <span className="badge">与 v{d.version} 一致</span>}
            <input style={{ flex: 1, minWidth: 160 }} placeholder="版本说明（可选）" value={note} onChange={(e) => setNote(e.target.value)} aria-label="版本说明" />
            <button className="btn" disabled={!dirty} onClick={() => setDraft(structuredClone(irOf(d.package)!))}>撤销修改</button>
            <button className="btn primary" disabled={!dirty || invalid || save.isPending} onClick={() => save.mutate()}
              title={invalid ? "存在类型错误，不能保存" : undefined}>{save.isPending ? "保存中…" : "保存为新版本"}</button>
          </div>
          <InlineError error={save.error} />
          {(issues.length > 0 || schemaErrors.length > 0) && (
            <div className="table-wrap" style={{ maxHeight: 180 }}>
              <table className="table" aria-label="类型与引用问题">
                <thead><tr><th>位置</th><th>代码</th><th>说明</th></tr></thead>
                <tbody>
                  {schemaErrors.map((e, i) => <tr key={`s${i}`}><td><code>{e.path}</code></td><td>SCHEMA</td><td>{e.message}</td></tr>)}
                  {issues.map((e, i) => <tr key={i}><td><code>{e.path}</code></td><td><span className="badge err">{e.code}</span></td><td>{e.message}</td></tr>)}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      <div className="card">
        <Tabs label="模型视图" value={tab} onChange={setTab} tabs={[
          { id: "graph", label: "结构图" }, { id: "form", label: "表单编辑" }, { id: "json", label: "JSON" },
          { id: "diff", label: "版本差异" }, { id: "check", label: "编译与检查" }, { id: "release", label: "目标与发布" },
          { id: "prob", label: "概率扩展" }, { id: "caps", label: "能力矩阵" },
        ]} />
        <div className="card-body">
          {draft && tab === "graph" && <ModelGraph ir={draft} />}
          {draft && tab === "form" && <FormEditor ir={draft} onChange={setDraft} issues={issues} />}
          {draft && tab === "json" && <JsonField key={`${d.version}-${restored}`} value={draft} onChange={(v) => setDraft(v)} rows={28} />}
          {tab === "diff" && <DiffView modelId={modelId} versions={model.data!.versions?.map((v) => v.version) ?? []} current={d.version} />}
          {tab === "check" && <CheckPanel detail={d} dirty={Boolean(dirty)} />}
          {tab === "release" && <ObjectivesAndReleases pid={pid!} detail={d} onDiff={() => setTab("diff")} />}
          {tab === "prob" && <ProbabilisticPanel versionId={d.id} />}
          {tab === "caps" && <div className="stack"><CapabilityReportView versionId={d.id} /><CapabilityMatrix rows={d.capability_matrix} /></div>}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ form editor
function FormEditor({ ir, onChange, issues }: { ir: ModelIR; onChange: (ir: ModelIR) => void; issues: { path: string; message: string }[] }) {
  const set = (patch: Partial<ModelIR>) => onChange({ ...ir, ...patch });
  const issuesAt = (prefix: string) => issues.filter((i) => i.path.startsWith(prefix));
  const Row = ({ prefix }: { prefix: string }) => {
    const found = issuesAt(prefix);
    return found.length ? <div className="small" style={{ color: "var(--err)" }}>{found.map((f) => f.message).join("；")}</div> : null;
  };
  const upd = <K extends keyof ModelIR>(key: K, i: number, value: unknown) => {
    const arr = [...(ir[key] as unknown[])];
    arr[i] = { ...(arr[i] as object), ...(value as object) };
    set({ [key]: arr } as Partial<ModelIR>);
  };
  const remove = <K extends keyof ModelIR>(key: K, i: number) => set({ [key]: (ir[key] as unknown[]).filter((_, j) => j !== i) } as Partial<ModelIR>);
  return (
    <div className="stack">
      <div className="form-grid">
        <label className="field"><span>名称</span><input value={ir.name} onChange={(e) => set({ name: e.target.value })} /></label>
        <label className="field" style={{ gridColumn: "span 2" }}><span>说明</span><input value={ir.description ?? ""} onChange={(e) => set({ description: e.target.value })} /></label>
      </div>
      <Section title="实体集合" onAdd={() => set({ entity_sets: [...(ir.entity_sets ?? []), { name: `set${(ir.entity_sets ?? []).length + 1}`, members: ["a"], label: null, description: null }] as unknown as ModelIR["entity_sets"] })}>
        {(ir.entity_sets ?? []).map((e, i) => (
          <div key={i} className="stack">
            <div className="form-grid">
              <label className="field"><span>名称</span><input value={e.name} onChange={(x) => upd("entity_sets", i, { name: x.target.value })} /></label>
              <label className="field"><span>标签</span><input value={e.label ?? ""} onChange={(x) => upd("entity_sets", i, { label: x.target.value || null })} /></label>
              <label className="field" style={{ gridColumn: "span 2" }}><span>成员（逗号分隔）</span>
                <input value={e.members.join(", ")} onChange={(x) => upd("entity_sets", i, { members: x.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} /></label>
            </div>
            <Row prefix={`/entity_sets/${i}`} />
            <button className="btn sm ghost danger" style={{ alignSelf: "flex-start" }} onClick={() => remove("entity_sets", i)}>删除</button>
          </div>
        ))}
      </Section>
      <Section title="状态变量" onAdd={() => set({ state: [...ir.state, { name: `v${ir.state.length + 1}`, type: { kind: "bool" }, index: [], initial: { default: false, cells: [] }, observable: true }] as unknown as ModelIR["state"] })}>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>名称</th><th>标签</th><th>类型</th><th>索引</th><th>初值</th><th>可观测</th><th /></tr></thead>
            <tbody>
              {ir.state.map((s, i) => (
                <tr key={i}>
                  <td><input value={s.name} onChange={(x) => upd("state", i, { name: x.target.value })} style={{ width: 120 }} />
                    <Row prefix={`/state/${i}`} /></td>
                  <td><input value={s.label ?? ""} onChange={(x) => upd("state", i, { label: x.target.value || null })} style={{ width: 110 }} /></td>
                  <td><TypeEditor value={s.type} onChange={(t) => upd("state", i, { type: t })} /></td>
                  <td><input value={(s.index ?? []).join(",")} style={{ width: 110 }} onChange={(x) => upd("state", i, { index: x.target.value.split(",").map((v) => v.trim()).filter(Boolean) })} /></td>
                  <td><input value={String(s.initial.default ?? "")} style={{ width: 90 }} title={`cells: ${JSON.stringify(s.initial.cells ?? [])}`}
                    onChange={(x) => upd("state", i, { initial: { ...s.initial, default: parseScalar(x.target.value, s.type.kind) } })} /></td>
                  <td><input type="checkbox" checked={s.observable !== false} onChange={(x) => upd("state", i, { observable: x.target.checked })} aria-label={`${s.name} 可观测`} /></td>
                  <td><button className="btn sm ghost danger" onClick={() => remove("state", i)} aria-label={`删除 ${s.name}`}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section title="动作" onAdd={() => set({ actions: [...ir.actions, { name: `act${ir.actions.length + 1}`, params: [], precondition: { op: "const", value: true }, effects: [], cost: 1, timeout_seconds: 30, retry: "RECONCILE_THEN_RETRY" }] as unknown as ModelIR["actions"] })}>
        {ir.actions.map((a, i) => (
          <details key={i} className="card pad">
            <summary className="row"><strong>{a.label ? `${a.label} ` : ""}{a.name}</strong>
              <span className="muted small">({(a.params ?? []).map((p) => `${p.name}: ${typeText(p.type)}`).join(", ")})</span></summary>
            <div className="stack" style={{ marginTop: 8 }}>
              <div className="form-grid">
                <label className="field"><span>名称</span><input value={a.name} onChange={(x) => upd("actions", i, { name: x.target.value })} /></label>
                <label className="field"><span>标签</span><input value={a.label ?? ""} onChange={(x) => upd("actions", i, { label: x.target.value || null })} /></label>
                <label className="field"><span>成本</span><input type="number" min={0} value={a.cost} onChange={(x) => upd("actions", i, { cost: Number(x.target.value) })} /></label>
                <label className="field"><span>重试语义</span><select value={a.retry} onChange={(x) => upd("actions", i, { retry: x.target.value })}>
                  {["IDEMPOTENT", "RECONCILE_THEN_RETRY", "NOT_RETRYABLE"].map((r) => <option key={r}>{r}</option>)}</select></label>
              </div>
              <div className="muted small">前提：<code>{exprText(a.precondition)}</code></div>
              <pre className="json" style={{ maxHeight: 140 }}>{effectLines(a.effects ?? []).join("\n") || "（无效果）"}</pre>
              <label className="field"><span>参数 / 前提 / 效果（AST JSON）</span>
                <JsonField value={{ params: a.params, precondition: a.precondition, effects: a.effects }} rows={10}
                  onChange={(v: { params: unknown; precondition: unknown; effects: unknown }) => upd("actions", i, v)} /></label>
              <Row prefix={`/actions/${i}`} />
              <button className="btn sm ghost danger" style={{ alignSelf: "flex-start" }} onClick={() => remove("actions", i)}>删除动作</button>
            </div>
          </details>
        ))}
      </Section>
      <Section title="性质（目标 / 不变量）" onAdd={() => set({ properties: [...(ir.properties ?? []), { id: `p${(ir.properties ?? []).length + 1}`, kind: "invariant", expr: { op: "const", value: true, domain: null }, label: null, description: null }] as unknown as ModelIR["properties"] })}>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>ID</th><th>标签</th><th>类别</th><th>表达式</th><th /></tr></thead>
            <tbody>
              {(ir.properties ?? []).map((p, i) => (
                <tr key={i}>
                  <td><input value={p.id} onChange={(x) => upd("properties", i, { id: x.target.value })} style={{ width: 120 }} /><Row prefix={`/properties/${i}`} /></td>
                  <td><input value={p.label ?? ""} onChange={(x) => upd("properties", i, { label: x.target.value || null })} style={{ width: 110 }} /></td>
                  <td><select value={p.kind} onChange={(x) => upd("properties", i, { kind: x.target.value })}><option value="goal">goal</option><option value="invariant">invariant</option></select></td>
                  <td style={{ minWidth: 260 }}><code className="small">{exprText(p.expr)}</code>
                    <details><summary className="small muted">编辑 AST</summary>
                      <JsonField value={p.expr} rows={6} onChange={(v) => upd("properties", i, { expr: v })} /></details></td>
                  <td><button className="btn sm ghost danger" onClick={() => remove("properties", i)} aria-label={`删除 ${p.id}`}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <details><summary className="muted small">常量与枚举（JSON）</summary>
        <JsonField value={{ enums: ir.enums, constants: ir.constants }} rows={12}
          onChange={(v: { enums: ModelIR["enums"]; constants: ModelIR["constants"] }) => set({ enums: v.enums, constants: v.constants })} /></details>
    </div>
  );
}

function Section({ title, onAdd, children }: { title: string; onAdd: () => void; children: React.ReactNode }) {
  return (
    <section className="stack">
      <div className="row"><h3 className="grow" style={{ flex: 1 }}>{title}</h3><button className="btn sm" onClick={onAdd}>添加</button></div>
      {children}
    </section>
  );
}

function TypeEditor({ value, onChange }: { value: ModelIR["state"][number]["type"]; onChange: (t: unknown) => void }) {
  return (
    <div className="row" style={{ flexWrap: "nowrap" }}>
      <select value={value.kind} onChange={(e) => {
        const k = e.target.value;
        onChange(k === "int" ? { kind: "int", min: 0, max: 9 } : k === "enum" ? { kind: "enum", name: "" } : k === "entity" ? { kind: "entity", set: "" } : { kind: "bool" });
      }} aria-label="类型">
        {["bool", "int", "enum", "entity"].map((k) => <option key={k}>{k}</option>)}
      </select>
      {value.kind === "int" && <>
        <input type="number" value={value.min} style={{ width: 56 }} aria-label="最小值" onChange={(e) => onChange({ ...value, min: Number(e.target.value) })} />
        <input type="number" value={value.max} style={{ width: 56 }} aria-label="最大值" onChange={(e) => onChange({ ...value, max: Number(e.target.value) })} />
      </>}
      {value.kind === "enum" && <input value={value.name} style={{ width: 90 }} aria-label="枚举名" onChange={(e) => onChange({ ...value, name: e.target.value })} />}
      {value.kind === "entity" && <input value={value.set} style={{ width: 90 }} aria-label="实体集合" onChange={(e) => onChange({ ...value, set: e.target.value })} />}
    </div>
  );
}

function parseScalar(v: string, kind: string): unknown {
  if (kind === "bool") return v === "true";
  if (kind === "int") return Number(v);
  return v;
}

// ------------------------------------------------------------------ diff
function DiffView({ modelId, versions, current }: { modelId: string; versions: number[]; current: number }) {
  const [from, setFrom] = useState(Math.max(1, current - 1));
  const [to, setTo] = useState(current);
  const diff = useQuery({ queryKey: ["diff", modelId, from, to], enabled: from !== to,
    queryFn: () => get<ModelChange[]>(`/models/${modelId}/diff?from=${from}&to=${to}`) });
  if (versions.length < 2) return <Empty title="只有一个版本" hint="保存修改后即可比较版本差异。" />;
  return (
    <div className="stack">
      <div className="row">
        <label className="row small">从 <select value={from} onChange={(e) => setFrom(Number(e.target.value))}>{versions.map((v) => <option key={v} value={v}>v{v}</option>)}</select></label>
        <label className="row small">到 <select value={to} onChange={(e) => setTo(Number(e.target.value))}>{versions.map((v) => <option key={v} value={v}>v{v}</option>)}</select></label>
      </div>
      {from === to ? <Empty title="选择两个不同版本" /> : (
        <QueryState q={diff} empty={<Empty title="两个版本内容相同" />}>
          {(changes) => (
            <div className="table-wrap tall">
              <table className="table">
                <thead><tr><th>部分</th><th>名称</th><th>变化</th><th>之前</th><th>之后</th></tr></thead>
                <tbody>{changes.map((c, i) => (
                  <tr key={i}><td>{c.section}</td><td><code>{c.name}</code></td>
                    <td><span className={`badge ${c.kind === "added" ? "ok" : c.kind === "removed" ? "err" : "warn"}`}>{c.kind}</span></td>
                    <td><pre className="json" style={{ maxHeight: 140 }}>{c.before === undefined ? "—" : JSON.stringify(c.before, null, 1)}</pre></td>
                    <td><pre className="json" style={{ maxHeight: 140 }}>{c.after === undefined ? "—" : JSON.stringify(c.after, null, 1)}</pre></td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </QueryState>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ bounded checks
function CheckPanel({ detail, dirty }: { detail: VersionDetail; dirty: boolean }) {
  const qc = useQueryClient();
  const ir = irOf(detail.package)!;
  const props = ir.properties ?? [];
  const [kind, setKind] = useState<"GOAL_REACHABILITY" | "INVARIANT_VIOLATION" | "ACTION_PRECONDITION">("GOAL_REACHABILITY");
  const [prop, setProp] = useState(props.find((p) => p.kind === "goal")?.id ?? props[0]?.id ?? "");
  const [bound, setBound] = useState(12);
  const [timeout, setTimeoutMs] = useState(20000);
  const [action, setAction] = useState(detail.action_specs[0]?.action_type ?? "");
  const spec = detail.action_specs.find((s) => s.action_type === action);
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [shown, setShown] = useState<CheckRecord | null>(null);
  const history = useQuery({ queryKey: ["checks", detail.id], queryFn: () => get<CheckRecord[]>(`/model-versions/${detail.id}/checks`) });
  const run = useMutation({
    mutationFn: () => post<CheckRecord>(`/model-versions/${detail.id}/checks`, {
      query: kind === "ACTION_PRECONDITION"
        ? { kind, action: { action_type: action, params }, bound: { max_steps: 0, timeout_ms: timeout } }
        : { kind, property_id: prop, bound: { max_steps: bound, timeout_ms: timeout } },
    }),
    onSuccess: (c) => { setShown(c); qc.invalidateQueries({ queryKey: ["checks", detail.id] }); },
  });
  return (
    <div className="stack">
      {dirty && <div className="callout warn small">检查针对已保存的 v{detail.version}；未保存的修改不参与检查。</div>}
      <div className="form-grid">
        <label className="field"><span>查询</span><select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
          <option value="GOAL_REACHABILITY">目标可达（存在路径）</option>
          <option value="INVARIANT_VIOLATION">不变量反例（所有路径）</option>
          <option value="ACTION_PRECONDITION">单步前提（初始状态）</option></select></label>
        {kind !== "ACTION_PRECONDITION" ? <>
          <label className="field"><span>性质</span><select value={prop} onChange={(e) => setProp(e.target.value)}>
            {props.map((p) => <option key={p.id} value={p.id}>{p.label ?? p.id} ({p.kind})</option>)}</select></label>
          <label className="field"><span>步数上界 k</span><input type="number" min={0} max={80} value={bound} onChange={(e) => setBound(Number(e.target.value))} /></label>
        </> : <>
          <label className="field"><span>动作</span><select value={action} onChange={(e) => { setAction(e.target.value); setParams({}); }}>
            {detail.action_specs.map((s) => <option key={s.action_type} value={s.action_type}>{s.label ?? s.action_type}</option>)}</select></label>
          {Object.entries(spec?.params_schema.properties ?? {}).map(([k, p]) => (
            <label className="field" key={k}><span>{k}</span>
              {p.enum ? <select value={String(params[k] ?? "")} onChange={(e) => setParams({ ...params, [k]: e.target.value })}>
                <option value="" disabled>选择…</option>{p.enum.map((v) => <option key={v}>{v}</option>)}</select>
                : <input type="number" min={p.minimum} max={p.maximum} onChange={(e) => setParams({ ...params, [k]: Number(e.target.value) })} />}
            </label>
          ))}
        </>}
        <label className="field"><span>超时 ms</span><input type="number" min={1} value={timeout} onChange={(e) => setTimeoutMs(Number(e.target.value))} /></label>
      </div>
      <div className="row"><button className="btn primary" disabled={run.isPending} onClick={() => run.mutate()}>{run.isPending ? "求解中…" : "编译并检查"}</button>
        <span className="muted small">后端：Z3 有界模型检查；见证由参考解释器独立重放。</span></div>
      <InlineError error={run.error} />
      {shown && <CheckResult result={shown.result} />}
      {shown && (shown as CheckRecord & { explanation?: string[]; query_bundle_id?: string }).explanation?.length ? (
        <div className="card pad stack small" data-testid="check-explanation">
          <div className="row"><strong className="grow">解释（与导出的查询包相同）</strong>
            {(shown as CheckRecord & { query_bundle_id?: string }).query_bundle_id &&
              <a className="btn sm" href={`/api/v1/query-bundles/${(shown as CheckRecord & { query_bundle_id?: string }).query_bundle_id}/export`} download><Icon name="export" size="sm" />查询包</a>}</div>
          <ul>{(shown as CheckRecord & { explanation?: string[] }).explanation!.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>) : null}
      <h3>历史检查</h3>
      <QueryState q={history} empty={<Empty title="此版本还没有检查记录" />}>
        {(list) => (
          <div className="table-wrap" style={{ maxHeight: 220 }}>
            <table className="table">
              <thead><tr><th>时间</th><th>查询</th><th>结论</th><th>边界</th></tr></thead>
              <tbody>{list.map((c) => (
                <tr key={c.id} className={`selectable ${shown?.id === c.id ? "selected" : ""}`} onClick={() => setShown(c)} tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter") setShown(c); }}>
                  <td className="nowrap">{fmtTime(c.created_at)}</td>
                  <td>{String(c.query.kind)} {String(c.query.property_id ?? (c.query.action as { action_type?: string })?.action_type ?? "")}</td>
                  <td><VerdictBadge verdict={c.verdict} /></td>
                  <td>≤ {String((c.query.bound as { max_steps: number }).max_steps)} 步</td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
      </QueryState>
    </div>
  );
}

export function CheckResult({ result }: { result: BoundedCheckResult }) {
  const r = result;
  const bounded = r.verdict === "NO_WITNESS_WITHIN_BOUND";
  return (
    <div className="card pad stack" aria-live="polite">
      <div className="row"><VerdictBadge verdict={String(r.verdict)} /><span className="badge outline">{r.semantics}</span>
        <span className="badge outline" title="结论只在模型内成立">模型内结论</span>
        {bounded && <span className="badge ok">有界结论 · ≤{r.bound.max_steps} 步</span>}</div>
      <div>{r.explanation}</div>
      <KV items={[
        ["边界", `max_steps=${r.bound.max_steps}${r.bound.timeout_ms ? ` · timeout ${r.bound.timeout_ms} ms` : ""}`],
        ["假设", r.assumptions.join("；") || "—"],
        ["求解", `${r.stats.solver_status} · 探索 ${r.stats.steps_explored} 步 · ${r.stats.elapsed_ms.toFixed(0)} ms${r.stats.reason_unknown ? ` · 未知原因 ${r.stats.reason_unknown}` : ""}`],
        ["后端", `${r.backend.name} ${r.backend.version}`],
        ...(r.unsupported ? [["未支持", `${r.unsupported.feature}: ${r.unsupported.reason}（扩展入口：${r.unsupported.extension_point ?? "—"}）`] as [string, string]] : []),
      ]} />
      {r.witness && (
        <div className="stack">
          <div className="row"><strong>见证路径（{r.witness.steps.length - 1} 步）</strong>
            <span className={`badge ${r.witness.replay === "CONFIRMED" ? "ok" : "err"}`}>解释器重放：{r.witness.replay}</span></div>
          <div className="table-wrap" style={{ maxHeight: 260 }}>
            <table className="table">
              <thead><tr><th>步</th><th>动作</th><th>变化的状态</th></tr></thead>
              <tbody>{r.witness.steps.map((s, i) => {
                const prev = i > 0 ? r.witness!.steps[i - 1].state : null;
                const changed = prev ? Object.entries(s.state).filter(([k, v]) => prev[k] !== v) : [];
                return <tr key={s.step}><td>{s.step}</td>
                  <td>{s.action ? <code>{s.action.action_type}({Object.entries(s.action.params).map(([k, v]) => `${k}=${v}`).join(", ")})</code> : "初始状态"}</td>
                  <td className="small">{changed.map(([k, v]) => `${k}=${String(v)}`).join("  ") || (i === 0 ? "—" : "（无变化）")}</td></tr>;
              })}</tbody>
            </table>
          </div>
        </div>
      )}
      <details><summary className="small muted">完整 BoundedCheckResult</summary><Json value={r} /></details>
    </div>
  );
}

interface FeatureRow { feature: string; status: string; provider: { plugin_id: string; version: string } | null; requires: string[]; reason: string }

/** What the platform can do with this model version, derived only from the declared driver.* / query.* capabilities
 *  of the installed plugins (phase 3A G3, GET /model-versions/{id}/capabilities). */
function CapabilityReportView({ versionId }: { versionId: string }) {
  const q = useQuery({ queryKey: ["capabilities", versionId],
    queryFn: () => get<{ semantic_profile: string; driver: { plugin_id: string; version: string }; features: FeatureRow[] }>(`/model-versions/${versionId}/capabilities`) });
  return (
    <section className="stack" data-testid="capability-report">
      <div className="row"><h3 className="grow">能力报告</h3>
        {q.data && <span className="small muted">profile <code>{q.data.semantic_profile}</code> · 驱动 <code>{q.data.driver.plugin_id}@{q.data.driver.version}</code></span>}</div>
      <QueryState q={q}>{(r) => (
        <div className="table-wrap">
          <table className="table" aria-label="能力报告">
            <thead><tr><th>功能</th><th>状态</th><th>提供者</th><th>依据 / 原因</th></tr></thead>
            <tbody>{r.features.map((f) => (
              <tr key={f.feature}><td><code className="small">{f.feature}</code></td>
                <td><span className={`badge ${f.status === "SUPPORTED" ? "ok" : f.status === "PARTIAL" ? "warn" : ""}`}>{f.status === "SUPPORTED" ? "✓ " : "· "}{f.status}</span></td>
                <td className="small">{f.provider ? <code>{f.provider.plugin_id}</code> : "—"}</td>
                <td className="small">{f.reason}{f.requires.length ? <div className="muted">需要 {f.requires.join("、")}</div> : null}</td></tr>))}</tbody>
          </table>
        </div>)}</QueryState>
    </section>
  );
}

function CapabilityMatrix({ rows }: { rows: VersionDetail["capability_matrix"] }) {
  const cols = Object.keys(rows[0]?.status ?? {});
  return (
    <div className="stack">
      <p className="muted small" style={{ margin: 0 }}>当前语义 profile 的实际能力范围：SUPPORTED 为已实现且有测试；未支持的语义由引擎返回 UNSUPPORTED 并给出扩展入口。
        部分观测属于实验语义：观测中的“未知项”与“过期事实”由环境产生，模型本身不含部分观测。</p>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>特性</th>{cols.map((c) => <th key={c}>{c}</th>)}<th>扩展入口</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.feature}><td><strong>{r.feature}</strong><div className="small muted">{r.description}</div></td>
              {cols.map((c) => <td key={c}><span className={`badge ${r.status[c] === "SUPPORTED" ? "ok" : r.status[c] === "PARTIAL" ? "warn" : ""}`}>{r.status[c]}</span></td>)}
              <td className="small">{r.extension_point ?? "—"}</td></tr>))}</tbody>
        </table>
      </div>
    </div>
  );
}
