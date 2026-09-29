import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { ApiError } from "./api";
import { Icon, type IconName } from "./icons";

// ------------------------------------------------------------------ states
export function Loading({ label = "加载中…" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const info = error instanceof ApiError ? error.info : null;
  return (
    <div className="state error" role="alert">
      <div className="state-icon"><Icon name="alert" /></div>
      <div className="title">{info ? `${info.code}` : "出错了"}</div>
      <div>{info ? info.message : String(error)}</div>
      {info?.field_errors?.length ? (
        <ul className="small" style={{ textAlign: "left", margin: 0 }}>
          {info.field_errors.map((f, i) => <li key={i}><code>{f.path}</code> {f.message}</li>)}
        </ul>
      ) : null}
      {retry && <button className="btn sm" onClick={retry}>重试</button>}
    </div>
  );
}

export function Empty({ title, hint, action }: { title: string; hint?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state">
      <div className="state-icon"><Icon name="empty" /></div>
      <div className="title">{title}</div>
      {hint && <div className="small">{hint}</div>}
      {action}
    </div>
  );
}

export function QueryState<T>({ q, children, empty, isEmpty }: {
  q: UseQueryResult<T>; children: (data: T) => ReactNode; empty?: ReactNode; isEmpty?: (d: T) => boolean;
}) {
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const data = q.data as T;
  if (empty && (isEmpty ? isEmpty(data) : Array.isArray(data) && data.length === 0)) return <>{empty}</>;
  return <>{children(data)}</>;
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  const info = error instanceof ApiError ? error.info : null;
  return (
    <div className="callout err small" role="alert">
      <strong>{info?.code ?? "ERROR"}</strong> {info?.message ?? String(error)}
      {info?.field_errors?.map((f, i) => <div key={i}><code>{f.path}</code> {f.message}</div>)}
    </div>
  );
}

// ------------------------------------------------------------------ page structure
/** Page header of every area: eyebrow (area, with its icon) · title · description · actions. */
export function PageHead({ area, icon, title, description, actions, crumbs }: {
  area?: string; icon?: IconName; title: ReactNode; description?: ReactNode; actions?: ReactNode; crumbs?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div className="grow">
        {crumbs ? <div className="crumbs">{crumbs}</div>
          : area && <div className="eyebrow">{icon && <Icon name={icon} size="sm" />}{area}</div>}
        <h1 className="row" style={{ marginTop: 4 }}>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  );
}

export function Stat({ label, value, note }: { label: ReactNode; value: ReactNode; note?: ReactNode }) {
  return <div className="stat"><span className="label">{label}</span><span className="value">{value}</span>{note && <span className="note">{note}</span>}</div>;
}

// ------------------------------------------------------------------ participants: categorical colour + initial
/** Participant colour slot (1…8) by position in the run's participant list: stable within a run, never the only cue. */
export function participantSlot(order: string[], actorId: string): number {
  const i = order.indexOf(actorId);
  return (i < 0 ? 0 : i) % 8 + 1;
}
export function ParticipantChip({ actorId, order, label }: { actorId: string; order: string[]; label?: string }) {
  const slot = participantSlot(order, actorId);
  return (
    <span className="pchip" style={{ ["--pc" as string]: `var(--p${slot})` }}>
      <span className="swatch" aria-hidden>{(label ?? actorId).slice(0, 1).toUpperCase()}</span>{label ?? actorId}
    </span>
  );
}
export const participantColor = (order: string[], actorId: string) => `var(--p${participantSlot(order, actorId)})`;

// ------------------------------------------------------------------ evidence levels (compare.py, P2-074)
const EVIDENCE: Record<string, [string, string, string, string]> = {
  observed: ["observed", "●", "观测", "observed fresh by the participant at this step"],
  "verified-within-scope": ["verified", "◆", "范围内核实", "established by an independent source within its stated scope (probe or operation query)"],
  predicted: ["predicted", "◌", "预测", "what the model predicts — not an observation"],
  unknown: ["unknown", "○", "未知", "neither observed nor verified: not comparable"],
};
export function EvidenceTag({ level }: { level: string }) {
  const [cls, glyph, label, title] = EVIDENCE[level] ?? ["unknown", "○", level, level];
  return <span className={`ev ${cls}`} title={`${level}: ${title}`}><span aria-hidden>{glyph}</span>{label}</span>;
}
export function EvidenceLegend() {
  return <div className="legend" aria-label="证据等级">{Object.keys(EVIDENCE).map((k) => <EvidenceTag key={k} level={k} />)}</div>;
}

// ------------------------------------------------------------------ badges
const STATUS_TONE: Record<string, string> = {
  SUCCEEDED: "ok", RUNNING: "accent", QUEUED: "info", CREATED: "", PAUSING: "warn", PAUSED: "warn",
  CANCELLING: "warn", CANCELLED: "", FAILED: "err", BUDGET_EXHAUSTED: "warn",
};
const STATUS_LABEL: Record<string, string> = {
  CREATED: "已创建", QUEUED: "排队", RUNNING: "运行中", PAUSING: "暂停中", PAUSED: "已暂停", CANCELLING: "取消中",
  CANCELLED: "已取消", SUCCEEDED: "成功", FAILED: "失败", BUDGET_EXHAUSTED: "预算结束",
};
const STATUS_GLYPH: Record<string, string> = { ok: "✓", err: "✕", warn: "‖", info: "…", accent: "", "": "·" };
export function StatusBadge({ status }: { status: string }) {
  const live = status === "RUNNING" || status === "QUEUED" || status === "PAUSING" || status === "CANCELLING";
  const tone = STATUS_TONE[status] ?? "";
  return (
    <span className={`badge ${tone}`} title={status}>
      {live ? <span className="dot live" aria-hidden /> : <span className="glyph" aria-hidden>{STATUS_GLYPH[tone]}</span>}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

const VERDICT: Record<string, [string, string, string]> = {
  WITNESS: ["info", "存在见证", "found a path within the bound"],
  NO_WITNESS_WITHIN_BOUND: ["ok", "边界内无见证", "bounded conclusion: nothing found up to the bound"],
  UNKNOWN: ["warn", "未知", "solver could not decide (e.g. timeout) or evidence is insufficient"],
  UNSUPPORTED: ["", "未支持", "outside the supported semantic profile"],
  APPLICABLE: ["ok", "适用", "applicable in every completion of unknown facts"],
  INAPPLICABLE: ["err", "不适用", "inapplicable in every completion"],
};
export function VerdictBadge({ verdict }: { verdict: string }) {
  const [tone, label, title] = VERDICT[verdict] ?? ["", verdict, verdict];
  return <span className={`badge ${tone}`} title={`${verdict}: ${title}`}>{label}</span>;
}

const CMP: Record<string, [string, string]> = {
  MATCH: ["ok", "符合预期"], DIFFERENT: ["err", "存在差异"], INSUFFICIENT_INFORMATION: ["warn", "信息不足"],
};
export function ComparisonBadge({ verdict }: { verdict?: string | null }) {
  if (!verdict) return <span className="badge">—</span>;
  const [tone, label] = CMP[verdict] ?? ["", verdict];
  return <span className={`badge ${tone}`} title={verdict}>{label}</span>;
}

const SOURCE: Record<string, [string, string]> = {
  RULE: ["", "规则"], SYMBOLIC: ["info", "符号/Z3"], LLM: ["accent", "LLM"], LLM_STUB: ["warn", "LLM 替身"],
  HUMAN: ["", "人工"], EXTERNAL: ["", "外部插件"],
};
export function SourceBadge({ kind }: { kind: string }) {
  const [tone, label] = SOURCE[kind] ?? ["", kind];
  return <span className={`badge ${tone}`} title={kind === "LLM_STUB" ? "deterministic stand-in, not a real model" : kind}>{label}</span>;
}

// ------------------------------------------------------------------ tabs (roving focus, ← → keys)
export function Tabs<T extends string>({ tabs, value, onChange, label }: {
  tabs: { id: T; label: ReactNode }[]; value: T; onChange: (id: T) => void; label: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const n = tabs.length;
    const next = e.key === "ArrowRight" ? (i + 1) % n : e.key === "ArrowLeft" ? (i - 1 + n) % n : -1;
    if (next >= 0) {
      e.preventDefault();
      onChange(tabs[next].id);
      refs.current[next]?.focus();
    }
  };
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((t, i) => (
        <button key={t.id} role="tab" aria-selected={t.id === value} tabIndex={t.id === value ? 0 : -1}
          ref={(el) => { refs.current[i] = el; }} onClick={() => onChange(t.id)} onKeyDown={(e) => onKey(e, i)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ modal
export function Modal({ title, onClose, children, footer }: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode;
}) {
  const id = useId();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); prev?.focus(); };
  }, [onClose]);
  return (
    <div className="modal-scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={id} ref={ref}>
        <header><h2 id={id}>{title}</h2><button className="icon-btn" aria-label="关闭" onClick={onClose}>✕</button></header>
        <div className="body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ toasts
type Toast = { id: number; text: string; tone?: "err" };
const ToastCtx = createContext<(text: string, tone?: "err") => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone?: "err") => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs, { id, text, tone }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-area" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.tone ?? ""}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);
export const errorText = (e: unknown) => (e instanceof ApiError ? `${e.info.code}: ${e.info.message}` : String(e));

// ------------------------------------------------------------------ JSON / key-value
export function Json({ value, maxHeight }: { value: unknown; maxHeight?: number }) {
  return <pre className="json" style={maxHeight ? { maxHeight } : undefined}>{JSON.stringify(value, null, 2)}</pre>;
}
export function KV({ items }: { items: [ReactNode, ReactNode][] }) {
  return <dl className="kv">{items.map(([k, v], i) => <FragmentKV key={i} k={k} v={v} />)}</dl>;
}
function FragmentKV({ k, v }: { k: ReactNode; v: ReactNode }) {
  return <><dt>{k}</dt><dd>{v}</dd></>;
}

// ------------------------------------------------------------------ JSON-Schema driven form (plugin configs)
type Schema = { type?: string | string[]; properties?: Record<string, Schema>; items?: Schema; enum?: unknown[];
  minimum?: number; maximum?: number; description?: string; default?: unknown; additionalProperties?: unknown };

/** Field errors of an API error under `basePath` (e.g. "/participants/0/strategy/config"), keyed by property. */
export function fieldErrorsAt(error: unknown, basePath: string): Record<string, string> {
  const info = error instanceof ApiError ? error.info : null;
  const out: Record<string, string> = {};
  for (const f of info?.field_errors ?? []) {
    if (f.path === basePath) out[""] = f.message;
    else if (f.path.startsWith(`${basePath}/`)) out[f.path.slice(basePath.length + 1).split("/")[0]] = f.message;
  }
  return out;
}

/** Example configuration from a schema: `examples[0]`, else every property's example / default. */
export function exampleOf(schema: Schema): Record<string, unknown> {
  const s = schema as Schema & { examples?: Record<string, unknown>[] };
  if (s.examples?.length) return { ...s.examples[0] };
  const out: Record<string, unknown> = {};
  for (const [k, p] of Object.entries(schema.properties ?? {})) {
    const q = p as { examples?: unknown[]; default?: unknown };
    if (q.examples?.length) out[k] = q.examples[0];
    else if (q.default !== undefined) out[k] = q.default;
  }
  return out;
}

export function SchemaForm({ schema, value, onChange, error, basePath }: {
  schema: Schema; value: Record<string, unknown>; onChange: (v: Record<string, unknown>) => void;
  error?: unknown; basePath?: string;
}) {
  const props = schema.properties ?? {};
  const keys = Object.keys(props);
  const [raw, setRaw] = useState<string | null>(null);
  const errs = basePath ? fieldErrorsAt(error, basePath) : {};
  if (!keys.length && schema.additionalProperties !== false) {
    return <JsonField value={value} onChange={onChange} />;
  }
  if (!keys.length) return <div className="muted small">此插件没有配置项</div>;
  const set = (k: string, v: unknown) => {
    const next = { ...value };
    if (v === undefined || v === "") delete next[k]; else next[k] = v;
    onChange(next);
  };
  return (
    <div className="stack" style={{ gap: 6 }}>
    <div className="row small"><span className="muted grow">配置项由插件的 JSON Schema 生成</span>
      <button type="button" className="btn sm ghost" onClick={() => onChange({ ...exampleOf(schema), ...value })}>填入示例</button></div>
    {errs[""] && <span className="small" role="alert" style={{ color: "var(--err)" }}>{errs[""]}</span>}
    <div className="form-grid">
      {keys.map((k) => {
        const p = props[k];
        const cur = value[k];
        const t = Array.isArray(p.type) ? p.type[0] : p.type;
        let input: ReactNode;
        if (p.enum) {
          input = <select value={cur === undefined ? "" : String(cur)} onChange={(e) => set(k, e.target.value || undefined)}>
            <option value="">（默认{p.default !== undefined ? `: ${String(p.default)}` : ""}）</option>
            {p.enum.map((x) => <option key={String(x)} value={String(x)}>{String(x)}</option>)}
          </select>;
        } else if (t === "integer" || t === "number") {
          input = <input type="number" min={p.minimum} max={p.maximum} value={cur === undefined ? "" : String(cur)}
            placeholder={p.default !== undefined ? String(p.default) : ""}
            onChange={(e) => set(k, e.target.value === "" ? undefined : Number(e.target.value))} />;
        } else if (t === "boolean") {
          input = <input type="checkbox" checked={Boolean(cur)} onChange={(e) => set(k, e.target.checked)} />;
        } else if (t === "array" && p.items?.type === "string") {
          input = <input value={Array.isArray(cur) ? cur.join(", ") : ""} placeholder="逗号分隔"
            onChange={(e) => set(k, e.target.value ? e.target.value.split(",").map((s) => s.trim()).filter(Boolean) : undefined)} />;
        } else if (t === "string") {
          input = <input value={cur === undefined ? "" : String(cur)} onChange={(e) => set(k, e.target.value || undefined)} />;
        } else {
          input = <textarea rows={3} value={raw ?? JSON.stringify(cur ?? null, null, 1)}
            onChange={(e) => { setRaw(e.target.value); try { set(k, JSON.parse(e.target.value)); setRaw(null); } catch { /* keep typing */ } }} />;
        }
        return (
          <label className={`field ${errs[k] ? "invalid" : ""}`} key={k} aria-invalid={Boolean(errs[k])}>
            <span>{k}</span>
            {input}
            {errs[k] ? <span className="hint" role="alert" style={{ color: "var(--err)" }}>{errs[k]}</span>
              : p.description && <span className="hint">{p.description}</span>}
          </label>
        );
      })}
    </div>
    </div>
  );
}

export function JsonField({ value, onChange, rows = 8 }: { value: unknown; onChange: (v: any) => void; rows?: number }) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="stack">
      <textarea rows={rows} value={text} spellCheck={false} aria-invalid={Boolean(err)}
        onChange={(e) => {
          setText(e.target.value);
          try { onChange(JSON.parse(e.target.value)); setErr(null); } catch (x) { setErr(String(x)); }
        }} />
      {err && <span className="small" style={{ color: "var(--err)" }}>JSON 无效：{err}</span>}
    </div>
  );
}

// ------------------------------------------------------------------ formatting
export const fmtTime = (s?: string | null) => (s ? new Date(s).toLocaleString() : "—");
export const fmtNum = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : Number.isInteger(v) ? String(v) : v.toFixed(digits);
export const shortId = (s: string) => (s.length > 14 ? `${s.slice(0, 10)}…` : s);
export function fmtValue(v: unknown): string {
  if (typeof v === "boolean") return v ? "true" : "false";
  if (v === null || v === undefined) return "—";
  return String(v);
}


/** Windowed table for large logs (P2-095): only the rows in view (plus a margin) are in the DOM; row height is
 *  fixed so the scroll position maps directly to a row index. */
export function VirtualTable<T>({ rows, header, render, label, rowHeight = 30, height = 520 }: {
  rows: T[]; header: ReactNode; render: (row: T, index: number) => ReactNode; label: string;
  rowHeight?: number; height?: number;
}) {
  const [top, setTop] = useState(0);
  const overscan = 12;
  const start = Math.max(0, Math.floor(top / rowHeight) - overscan);
  const end = Math.min(rows.length, Math.ceil((top + height) / rowHeight) + overscan);
  return (
    <div className="table-wrap virtual" style={{ maxHeight: height, overflowY: "auto" }} data-testid="virtual-table"
      data-rows={rows.length} data-rendered={end - start} onScroll={(e) => setTop(e.currentTarget.scrollTop)}>
      <table className="table wide" aria-label={label} aria-rowcount={rows.length + 1}>
        <thead>{header}</thead>
        <tbody>
          {start > 0 && <tr aria-hidden style={{ height: start * rowHeight }}><td colSpan={99} /></tr>}
          {rows.slice(start, end).map((r, i) => render(r, start + i))}
          {end < rows.length && <tr aria-hidden style={{ height: (rows.length - end) * rowHeight }}><td colSpan={99} /></tr>}
        </tbody>
      </table>
    </div>
  );
}
