import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { ApiError } from "./api";

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

// ------------------------------------------------------------------ badges
const STATUS_TONE: Record<string, string> = {
  SUCCEEDED: "ok", RUNNING: "accent", QUEUED: "info", CREATED: "", PAUSING: "warn", PAUSED: "warn",
  CANCELLING: "warn", CANCELLED: "", FAILED: "err", BUDGET_EXHAUSTED: "warn",
};
const STATUS_LABEL: Record<string, string> = {
  CREATED: "已创建", QUEUED: "排队", RUNNING: "运行中", PAUSING: "暂停中", PAUSED: "已暂停", CANCELLING: "取消中",
  CANCELLED: "已取消", SUCCEEDED: "成功", FAILED: "失败", BUDGET_EXHAUSTED: "预算结束",
};
export function StatusBadge({ status }: { status: string }) {
  const live = status === "RUNNING" || status === "QUEUED" || status === "PAUSING" || status === "CANCELLING";
  return (
    <span className={`badge ${STATUS_TONE[status] ?? ""}`} title={status}>
      {live && <span className="dot live" aria-hidden />}
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

export function SchemaForm({ schema, value, onChange }: {
  schema: Schema; value: Record<string, unknown>; onChange: (v: Record<string, unknown>) => void;
}) {
  const props = schema.properties ?? {};
  const keys = Object.keys(props);
  const [raw, setRaw] = useState<string | null>(null);
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
          <label className="field" key={k}>
            <span>{k}</span>
            {input}
            {p.description && <span className="hint">{p.description}</span>}
          </label>
        );
      })}
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
