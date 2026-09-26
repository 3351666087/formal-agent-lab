// Structure graph of a model: domains → state (indexed by) → actions (read/write) → properties (read).
import { useMemo, useState } from "react";
import type { ModelIR } from "@formal-lab/contracts";
import { effectLines, effectVars, exprText, typeText, varsRead } from "../ir";

type Node = { id: string; col: number; label: string; sub: string; kind: string; detail: string[] };
type Edge = { from: string; to: string; kind: "index" | "write" | "read" };

const COLS = ["领域（实体/枚举）", "状态与常量", "动作", "性质"];
const W = 200, H = 34, GAPX = 56, GAPY = 10, TOP = 30;

export function ModelGraph({ ir, onSelect }: { ir: ModelIR; onSelect?: (id: string) => void }) {
  const [sel, setSel] = useState<string | null>(null);
  const { nodes, edges } = useMemo(() => build(ir), [ir]);
  const pos = useMemo(() => {
    const byCol: Record<number, Node[]> = {};
    nodes.forEach((n) => (byCol[n.col] ??= []).push(n));
    const p: Record<string, { x: number; y: number }> = {};
    Object.entries(byCol).forEach(([c, ns]) => ns.forEach((n, i) => (p[n.id] = { x: Number(c) * (W + GAPX), y: TOP + i * (H + GAPY) })));
    return p;
  }, [nodes]);
  const height = Math.max(...Object.values(pos).map((p) => p.y + H), 120) + 10;
  const width = 4 * W + 3 * GAPX;
  const related = useMemo(() => {
    if (!sel) return null;
    const s = new Set([sel]);
    edges.forEach((e) => { if (e.from === sel) s.add(e.to); if (e.to === sel) s.add(e.from); });
    return s;
  }, [sel, edges]);
  const selected = nodes.find((n) => n.id === sel);
  return (
    <div className="stack">
      <div className="legend" aria-hidden>
        <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="var(--muted)" strokeDasharray="3 3" /></svg>索引域</span>
        <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="var(--err)" strokeWidth="1.6" /></svg>写入</span>
        <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="var(--accent)" /></svg>读取</span>
        <span className="muted">点击节点查看定义并高亮关联</span>
      </div>
      <div className="svg-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="模型结构图"
          style={{ display: "block", minWidth: 760, maxWidth: width }}>
          {COLS.map((c, i) => <text key={c} x={i * (W + GAPX)} y={14} fontSize="12" fill="var(--muted)">{c}</text>)}
          {edges.map((e, i) => {
            const a = pos[e.from], b = pos[e.to];
            if (!a || !b) return null;
            const dim = related && !(related.has(e.from) && related.has(e.to));
            const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
            const stroke = e.kind === "write" ? "var(--err)" : e.kind === "read" ? "var(--accent)" : "var(--muted)";
            return <path key={i} d={`M${x1},${y1} C${x1 + 35},${y1} ${x2 - 35},${y2} ${x2},${y2}`} fill="none"
              stroke={stroke} strokeWidth={e.kind === "write" ? 1.6 : 1} strokeDasharray={e.kind === "index" ? "3 3" : undefined}
              opacity={dim ? 0.08 : 0.55} />;
          })}
          {nodes.map((n) => {
            const p = pos[n.id];
            const dim = related && !related.has(n.id);
            const active = sel === n.id;
            return (
              <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.3 : 1} style={{ cursor: "pointer" }}
                tabIndex={0} role="button" aria-label={`${n.kind} ${n.label}`} aria-pressed={active}
                onClick={() => { setSel(active ? null : n.id); onSelect?.(n.id); }}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSel(active ? null : n.id); } }}>
                <rect width={W} height={H} rx={6} fill={active ? "var(--accent-soft)" : "var(--surface)"}
                  stroke={active ? "var(--accent)" : "var(--border-strong)"} />
                <text x={10} y={14} fontSize="12.5" fontWeight={600} fill="var(--text)">{clip(n.label, 26)}</text>
                <text x={10} y={27} fontSize="11" fill="var(--muted)">{clip(n.sub, 32)}</text>
              </g>
            );
          })}
        </svg>
      </div>
      {selected && (
        <div className="card pad stack" aria-live="polite">
          <div className="row"><span className="badge">{selected.kind}</span><strong>{selected.label}</strong><span className="muted small">{selected.sub}</span></div>
          <pre className="json" style={{ maxHeight: 240 }}>{selected.detail.join("\n")}</pre>
        </div>
      )}
    </div>
  );
}

const clip = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

function build(ir: ModelIR) {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  for (const e of ir.entity_sets ?? []) nodes.push({ id: `d:${e.name}`, col: 0, label: e.label ? `${e.label} ${e.name}` : e.name,
    sub: `实体 ×${e.members.length}`, kind: "entity set", detail: [`members: ${e.members.join(", ")}`] });
  for (const e of ir.enums ?? []) nodes.push({ id: `d:${e.name}`, col: 0, label: e.name, sub: `枚举 ${e.values.join("/")}`,
    kind: "enum", detail: [`values: ${e.values.join(", ")}`] });
  for (const s of ir.state) {
    nodes.push({ id: `v:${s.name}`, col: 1, label: s.label ? `${s.label} ${s.name}` : s.name,
      sub: `${typeText(s.type)}${s.index?.length ? ` [${s.index.join(",")}]` : ""}${s.observable === false ? " · 不可观测" : ""}`,
      kind: "state", detail: [`type: ${typeText(s.type)}`, `index: ${(s.index ?? []).join(", ") || "—"}`,
        `initial default: ${String(s.initial.default)}`, `cells: ${JSON.stringify(s.initial.cells ?? [])}`, s.description ?? ""] });
    (s.index ?? []).forEach((d) => edges.push({ from: `d:${d}`, to: `v:${s.name}`, kind: "index" }));
  }
  for (const c of ir.constants ?? []) {
    nodes.push({ id: `v:${c.name}`, col: 1, label: c.name, sub: `常量 ${typeText(c.type)}${c.index?.length ? ` [${c.index.join(",")}]` : ""}`,
      kind: "constant", detail: [`type: ${typeText(c.type)}`, `default: ${String(c.value.default)}`, `cells: ${JSON.stringify(c.value.cells)}`, c.description ?? ""] });
    (c.index ?? []).forEach((d) => edges.push({ from: `d:${d}`, to: `v:${c.name}`, kind: "index" }));
  }
  for (const a of ir.actions) {
    const { writes, reads } = effectVars(a.effects ?? []);
    varsRead(a.precondition, reads);
    nodes.push({ id: `a:${a.name}`, col: 2, label: a.label ? `${a.label} ${a.name}` : a.name,
      sub: `(${(a.params ?? []).map((p) => p.name).join(", ")}) 写 ${writes.size} 读 ${reads.size}`, kind: "action",
      detail: [`params: ${(a.params ?? []).map((p) => `${p.name}: ${typeText(p.type)}`).join(", ") || "—"}`,
        `pre: ${exprText(a.precondition)}`, "effects:", ...effectLines(a.effects ?? [], "  "), `cost: ${a.cost} · retry: ${a.retry}`] });
    reads.forEach((v) => edges.push({ from: `v:${v}`, to: `a:${a.name}`, kind: "read" }));
    writes.forEach((v) => edges.push({ from: `a:${a.name}`, to: `v:${v}`, kind: "write" }));
  }
  for (const p of ir.properties ?? []) {
    nodes.push({ id: `p:${p.id}`, col: 3, label: p.label ? `${p.label} ${p.id}` : p.id, sub: p.kind === "goal" ? "目标" : "不变量",
      kind: p.kind, detail: [exprText(p.expr), p.description ?? ""] });
    varsRead(p.expr).forEach((v) => edges.push({ from: `v:${v}`, to: `p:${p.id}`, kind: "read" }));
  }
  // writes go backwards (action → state); draw them from the action column to the state column
  return { nodes, edges: edges.map((e) => (e.kind === "write" ? { from: e.to, to: e.from, kind: e.kind } : e)) };
}
