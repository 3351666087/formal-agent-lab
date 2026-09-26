// Label resolution driven by model metadata (IR labels) and plugin metadata (PluginDescriptor.ui).
// The core UI never hard-codes a domain: every label, action template and metric name comes from here.
import type { ModelIR, PluginDescriptor } from "@formal-lab/contracts";

export interface Labels {
  state(path: string): string;
  action(type: string): string;
  actionText(a: { action_type: string; params: Record<string, unknown> }): string;
  metric(id: string): string;
  entity(name: string): string;
  value(v: unknown): string;
}

export function makeLabels(ir?: ModelIR | null, plugins: PluginDescriptor[] = []): Labels {
  const stateLabels: Record<string, string> = {};
  const actionLabels: Record<string, string> = {};
  const actionDisplay: Record<string, string> = {};
  const metricLabels: Record<string, string> = {};
  const entityLabels: Record<string, string> = {};
  const valueLabels: Record<string, string> = {};
  const paramOrder: Record<string, string[]> = {};
  for (const p of plugins) {
    Object.assign(stateLabels, p.ui.state_labels ?? {});
    Object.assign(actionLabels, p.ui.action_labels ?? {});
    Object.assign(actionDisplay, p.ui.action_display ?? {});
    Object.assign(metricLabels, p.ui.metric_labels ?? {});
    Object.assign(entityLabels, p.ui.entity_labels ?? {});
    Object.assign(valueLabels, p.ui.value_labels ?? {});
  }
  for (const s of ir?.state ?? []) if (s.label) stateLabels[s.name] ??= s.label;
  for (const a of ir?.actions ?? []) {
    if (a.label) actionLabels[a.name] ??= a.label;
    paramOrder[a.name] = (a.params ?? []).map((p) => p.name); // JSON stores may reorder keys; declared order wins
  }
  for (const e of ir?.entity_sets ?? []) if (e.label) entityLabels[e.name] ??= e.label;
  return {
    state(path) {
      const [name, rest] = path.split("[");
      const label = stateLabels[name];
      return label ? `${label}${rest ? `[${rest}` : ""}` : path;
    },
    action: (t) => actionLabels[t] ?? t,
    actionText(a) {
      const tpl = actionDisplay[a.action_type];
      if (tpl) return tpl.replace(/\{(\w+)\}/g, (_, k) => String(a.params[k] ?? `{${k}}`));
      const order = paramOrder[a.action_type] ?? Object.keys(a.params).sort();
      const keys = [...order.filter((k) => k in a.params), ...Object.keys(a.params).filter((k) => !order.includes(k))];
      const params = keys.map((k) => `${k}=${String(a.params[k])}`).join(", ");
      return `${actionLabels[a.action_type] ?? a.action_type}(${params})`;
    },
    metric: (id) => metricLabels[id] ?? id,
    entity: (n) => entityLabels[n] ?? n,
    value: (v) => (typeof v === "string" ? valueLabels[v] ?? v : typeof v === "boolean" ? (v ? "是" : "否") : String(v)),
  };
}
