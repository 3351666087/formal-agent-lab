import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import { del, get, post, type Meta, type Project } from "../api";
import { Icon, type IconName } from "../icons";
import { Empty, fmtTime, InlineError, Modal, PageHead, QueryState, useToast } from "../ui";

// the product loop every area serves: model → plan → run → deviation → evidence
const LOOP: { icon: IconName; title: string; text: string }[] = [
  { icon: "model", title: "模型", text: "状态、动作、性质；类型检查与有界查询" },
  { icon: "strategy", title: "计划", text: "规则 / Z3 / LLM 策略只从模型候选中选择" },
  { icon: "run", title: "运行", text: "参与者轮流或同步批次，操作有账本可对账" },
  { icon: "alert", title: "偏差", text: "效果与预测逐字段比较，差异生成修订建议" },
  { icon: "evidence", title: "证据", text: "事件因果链、回放包与指标，离线可读" },
];

export function ProjectsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => get<Project[]>("/projects") });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => get<Meta>("/meta") });
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", group: "" });
  const create = useMutation({
    mutationFn: () => post<Project>("/projects", form),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      setCreating(false);
      navigate(`/p/${p.id}/models`);
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => del(`/projects/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); toast("项目已删除"); },
  });
  const groups = new Map<string, Project[]>();
  for (const p of projects.data ?? []) {
    const g = p.group || "未分组";
    groups.set(g, [...(groups.get(g) ?? []), p]);
  }
  return (
    <>
      <PageHead area="工作区" icon="projects" title="项目"
        description="项目组织模型、场景、策略和实验；分组仅用于组织，不影响权限。"
        actions={<button className="btn primary" onClick={() => setCreating(true)}>新建项目</button>} />
      <section className="card pad" aria-label="工作流程">
        <ol className="loop">
          {LOOP.map((x, i) => (
            <li key={x.title}><span className="loop-icon"><Icon name={x.icon} /></span>
              <span><strong>{i + 1}. {x.title}</strong><span className="small muted">{x.text}</span></span></li>))}
        </ol>
      </section>
      {meta.data && (
        <div className="callout small">
          <strong>运行配置：</strong>{meta.data.deployment_profile} — {meta.data.capability_level}。
          契约 <code>{meta.data.contract_version}</code>（{meta.data.contract_digest.slice(0, 12)}），平台 {meta.data.platform_version}
          {meta.data.source_revision ? <> · <code>{meta.data.source_revision.slice(0, 10)}</code></> : null}
        </div>
      )}
      <QueryState q={projects} empty={<div className="card"><Empty title="还没有项目" hint="新建项目，或运行 make seed 创建生产调度示例。"
        action={<button className="btn primary" onClick={() => setCreating(true)}>新建项目</button>} /></div>}>
        {() => (
          <div className="stack">
            {[...groups.entries()].map(([group, items]) => (
              <section key={group} className="stack" aria-label={group}>
                <div className="eyebrow">{group}</div>
                <div className="grid cols-3">
                  {items.map((p) => (
                    <article key={p.id} className="card pad stack">
                      <div className="row">
                        <Link to={`/p/${p.id}/models`} className="grow"><h2>{p.name}</h2></Link>
                        <button className="btn sm ghost quiet-danger" aria-label={`删除 ${p.name}`}
                          onClick={() => { if (confirm(`删除项目「${p.name}」及其全部数据？`)) remove.mutate(p.id); }}>删除</button>
                      </div>
                      <div className="muted small">{p.description || "—"}</div>
                      <div className="project-counts">
                        <Link to={`/p/${p.id}/models`}><Icon name="model" size="sm" /><b>{p.counts?.models ?? 0}</b> 模型</Link>
                        <Link to={`/p/${p.id}/scenarios`}><Icon name="scenario" size="sm" /><b>{p.counts?.scenarios ?? 0}</b> 场景</Link>
                        <Link to={`/p/${p.id}/runs`}><Icon name="run" size="sm" /><b>{p.counts?.runs ?? 0}</b> 实验</Link>
                      </div>
                      <div className="muted small">创建于 {fmtTime(p.created_at)}</div>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </QueryState>
      {creating && (
        <Modal title="新建项目" onClose={() => setCreating(false)} footer={<>
          <button className="btn" onClick={() => setCreating(false)}>取消</button>
          <button className="btn primary" disabled={!form.name.trim() || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? "创建中…" : "创建"}</button>
        </>}>
          <label className="field"><span>名称</span>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label className="field"><span>分组</span>
            <input value={form.group} placeholder="例如 examples" onChange={(e) => setForm({ ...form, group: e.target.value })} /></label>
          <label className="field"><span>说明</span>
            <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <InlineError error={create.error} />
        </Modal>
      )}
    </>
  );
}
