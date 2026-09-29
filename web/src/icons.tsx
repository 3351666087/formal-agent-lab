// Icon set and brand mark of the evidence workbench (phase 3A, G5): 16px grid, 1.6 stroke, round caps. The same
// path data is used by the README / animation assets (design/brand/). Icons are decorative (aria-hidden) unless a
// label is given.
import type { ReactNode } from "react";

const PATHS: Record<string, ReactNode> = {
  projects: <><rect x="2" y="2" width="5" height="5" rx="1" /><rect x="9" y="2" width="5" height="5" rx="1" /><rect x="2" y="9" width="5" height="5" rx="1" /><rect x="9" y="9" width="5" height="5" rx="1" /></>,
  model: <><circle cx="3.5" cy="8" r="1.8" /><circle cx="12.5" cy="3.5" r="1.8" /><circle cx="12.5" cy="12.5" r="1.8" /><path d="M5.2 7.2 10.8 4.3M5.2 8.8l5.6 2.9" /></>,
  scenario: <><path d="M8 1.8 14.2 5 8 8.2 1.8 5z" /><path d="m1.8 8 6.2 3.2L14.2 8" /><path d="m1.8 11 6.2 3.2 6.2-3.2" /></>,
  strategy: <><path d="M2.5 4h7M12.5 4h1M2.5 8h2M7.5 8h6M2.5 12h5M10.5 12h3" /><circle cx="11" cy="4" r="1.5" /><circle cx="6" cy="8" r="1.5" /><circle cx="9" cy="12" r="1.5" /></>,
  run: <><circle cx="8" cy="8" r="6.2" /><path d="M6.6 5.4v5.2L10.8 8z" /></>,
  evidence: <><path d="M2.4 8a5.6 5.6 0 1 0 1.7-4" /><path d="M2.2 2.4v2.8H5" /><path d="M8 5v3.2l2.2 1.4" /></>,
  benchmark: <><path d="M2 14h12" /><rect x="3" y="8" width="2.4" height="6" /><rect x="6.8" y="4" width="2.4" height="10" /><rect x="10.6" y="6.5" width="2.4" height="7.5" /></>,
  pause: <><path d="M5.5 3.5v9M10.5 3.5v9" /></>,
  play: <><path d="M4.5 3v10l8-5z" /></>,
  stop: <><rect x="3.5" y="3.5" width="9" height="9" rx="1.5" /></>,
  rerun: <><path d="M13.3 8A5.3 5.3 0 1 1 11.7 4.2" /><path d="M13.6 2.2V5h-2.8" /></>,
  export: <><path d="M8 2.2v8M4.8 7 8 10.2 11.2 7" /><path d="M2.8 11.5v2.3h10.4v-2.3" /></>,
  check: <><path d="m3.2 8.4 3 3 6.6-6.8" /></>,
  alert: <><path d="M8 1.8 14.6 13.6H1.4z" /><path d="M8 6.2v3.4M8 11.6v.2" /></>,
  info: <><circle cx="8" cy="8" r="6.2" /><path d="M8 7.4v3.8M8 4.9v.2" /></>,
  batch: <><rect x="2" y="3" width="12" height="10" rx="1.5" /><path d="M6 3v10M10 3v10" /></>,
  gate: <><path d="M3 14V5.5a5 5 0 0 1 10 0V14" /><path d="M3 14h10M8 9v5" /></>,
  menu: <><path d="M2.5 4h11M2.5 8h11M2.5 12h11" /></>,
  close: <><path d="m3.5 3.5 9 9M12.5 3.5l-9 9" /></>,
  empty: <><rect x="2.5" y="3.5" width="11" height="9" rx="1.5" /><path d="M2.5 9h3l1 1.5h3l1-1.5h3" /></>,
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, label, size }: { name: IconName; label?: string; size?: "sm" }) {
  return (
    <svg className={`icon ${size ?? ""}`} viewBox="0 0 16 16" role={label ? "img" : undefined} aria-label={label}
      aria-hidden={label ? undefined : true}>{PATHS[name]}</svg>
  );
}

/** The mark: a model path whose last segment is still a prediction (dashed) — model → plan → evidence. */
export function BrandMark() {
  return (
    <svg viewBox="0 0 28 28" aria-hidden>
      <rect width="28" height="28" rx="7" fill="var(--color-brand)" />
      <path d="M6.5 19.5 11.5 10.5 16.5 16" stroke="var(--color-brand-contrast)" strokeWidth="2" fill="none"
        strokeLinecap="round" strokeLinejoin="round" />
      <path d="M16.5 16 21.5 8" stroke="var(--color-brand-contrast)" strokeWidth="2" fill="none" strokeLinecap="round"
        strokeDasharray="2 2.6" />
      <circle cx="6.5" cy="19.5" r="2.2" fill="var(--color-brand-contrast)" />
      <circle cx="11.5" cy="10.5" r="2.2" fill="var(--color-brand-contrast)" />
      <circle cx="16.5" cy="16" r="2.2" fill="var(--color-brand-contrast)" />
      <circle cx="21.5" cy="8" r="2.2" fill="none" stroke="var(--color-brand-contrast)" strokeWidth="1.6" />
    </svg>
  );
}
