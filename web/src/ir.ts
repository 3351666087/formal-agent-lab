// Client-side helpers over the IR contract types (rendering only; semantics live in the backend engines).
import type { Effect, Expr, ModelIR } from "@formal-lab/contracts";

const INFIX: Record<string, string> = {
  and: " ∧ ", or: " ∨ ", implies: " → ", eq: " = ", ne: " ≠ ", lt: " < ", le: " ≤ ", gt: " > ", ge: " ≥ ",
  add: " + ", sub: " − ", mul: " × ",
};

export function exprText(e: Expr | null | undefined): string {
  if (!e) return "—";
  switch (e.op) {
    case "const": return typeof e.value === "boolean" ? String(e.value) : String(e.value);
    case "ref": return e.name;
    case "var": return e.index?.length ? `${e.name}[${e.index.map(exprText).join(", ")}]` : e.name;
    case "forall": case "exists": case "count": case "sum": {
      const q = e as Extract<Expr, { var: string }>;
      const sym = { forall: "∀", exists: "∃", count: "#", sum: "Σ" }[e.op];
      return `${sym}${q.var} ∈ ${q.domain}${q.where ? ` | ${exprText(q.where)}` : ""}: ${exprText(q.body)}`;
    }
    default: {
      const a = (e as { args: Expr[] }).args.map(exprText);
      if (e.op === "not") return `¬(${a[0]})`;
      if (e.op === "neg") return `−(${a[0]})`;
      if (e.op === "min" || e.op === "max") return `${e.op}(${a.join(", ")})`;
      if (e.op === "ite") return `(if ${a[0]} then ${a[1]} else ${a[2]})`;
      return a.length === 1 ? a[0] : `(${a.join(INFIX[e.op] ?? ` ${e.op} `)})`;
    }
  }
}

export function effectLines(effects: Effect[], indent = ""): string[] {
  const out: string[] = [];
  for (const f of effects) {
    if (f.kind === "assign") {
      const idx = f.target.index?.length ? `[${f.target.index.map(exprText).join(", ")}]` : "";
      out.push(`${indent}${f.target.var}${idx} := ${exprText(f.value)}`);
    } else if (f.kind === "when") {
      out.push(`${indent}when ${exprText(f.condition)}:`, ...effectLines(f.then ?? [], indent + "  "));
      if (f.otherwise?.length) out.push(`${indent}otherwise:`, ...effectLines(f.otherwise, indent + "  "));
    } else {
      out.push(`${indent}for each ${f.var} ∈ ${f.domain}${f.where ? ` | ${exprText(f.where)}` : ""}:`,
        ...effectLines(f.effects, indent + "  "));
    }
  }
  return out;
}

export function varsRead(e: Expr | null | undefined, out = new Set<string>()): Set<string> {
  if (!e) return out;
  if (e.op === "var") { out.add(e.name); e.index?.forEach((i) => varsRead(i, out)); }
  else if ("args" in e) e.args.forEach((x) => varsRead(x, out));
  else if ("body" in e) { varsRead(e.body, out); if (e.where) varsRead(e.where, out); }
  return out;
}

export function effectVars(effects: Effect[], writes = new Set<string>(), reads = new Set<string>()) {
  for (const f of effects) {
    if (f.kind === "assign") { writes.add(f.target.var); varsRead(f.value, reads); f.target.index?.forEach((i) => varsRead(i, reads)); }
    else if (f.kind === "when") { varsRead(f.condition, reads); effectVars(f.then ?? [], writes, reads); effectVars(f.otherwise ?? [], writes, reads); }
    else { if (f.where) varsRead(f.where, reads); effectVars(f.effects, writes, reads); }
  }
  return { writes, reads };
}

export function typeText(t: ModelIR["state"][number]["type"]): string {
  switch (t.kind) {
    case "bool": return "bool";
    case "int": return `int[${t.min}..${t.max}]`;
    case "enum": return t.name;
    default: return t.set;
  }
}

export const blankModel = (): ModelIR => ({
  semantic_profile: "deterministic_finite_v1",
  name: "new-model",
  description: "",
  enums: [],
  entity_sets: [],
  constants: [],
  features: [],
  state: [{ name: "done", type: { kind: "bool" }, index: [], initial: { default: false, cells: [] }, observable: true }],
  actions: [{ name: "finish", params: [], precondition: { op: "const", value: true }, cost: 1, timeout_seconds: 30,
    retry: "RECONCILE_THEN_RETRY", effects: [{ kind: "assign", target: { var: "done", index: [] }, value: { op: "const", value: true } }] }],
  properties: [{ id: "goal", kind: "goal", expr: { op: "var", name: "done", index: [] } }],
} as unknown as ModelIR);
