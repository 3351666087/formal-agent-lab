import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import { del, get, post, type Meta, type Project } from "../api";
import { Empty, fmtTime, InlineError, Modal, QueryState, useToast } from "../ui";

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
      <div className="page-head">
        <div className="grow">
          <h1>项目</h1>
          <p>项目组织模型、场景、策略和实验；分组仅用于组织，不影响权限。</p>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>新建项目</button>
      </div>
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
                <h2 className="muted" style={{ fontSize: 13 }}>{group}</h2>
                <div className="grid cols-3">
                  {items.map((p) => (
                    <article key={p.id} className="card pad stack">
                      <div className="row">
                        <Link to={`/p/${p.id}/models`} className="grow"><h2>{p.name}</h2></Link>
                        <button className="btn sm ghost danger" aria-label={`删除 ${p.name}`}
                          onClick={() => { if (confirm(`删除项目「${p.name}」及其全部数据？`)) remove.mutate(p.id); }}>删除</button>
                      </div>
                      <div className="muted small">{p.description || "—"}</div>
                      <div className="row small">
                        <span className="badge">模型 {p.counts?.models ?? 0}</span>
                        <span className="badge">场景 {p.counts?.scenarios ?? 0}</span>
                        <Link to={`/p/${p.id}/runs`} className="badge accent">实验 {p.counts?.runs ?? 0}</Link>
                        <span className="muted" style={{ marginLeft: "auto" }}>{fmtTime(p.created_at)}</span>
                      </div>
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
