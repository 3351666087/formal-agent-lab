// Compile-time check that the generated types express the contract (run by `tsc --noEmit`).
import type { BoundedCheckResult, Expr, RunManifest, TraceEvent } from "../src/index.ts";
import { CONTRACT_VERSION, RUN_STATUSES } from "../src/index.ts";

const expr: Expr = { op: "and", args: [{ op: "var", name: "on", index: [] }, { op: "const", value: true, domain: null }] };

export function isTerminal(m: Pick<RunManifest, "status">): boolean {
  return ["SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"].includes(m.status);
}

export function describeCheck(r: BoundedCheckResult): string {
  const bound = `≤${r.bound.max_steps} steps`;
  switch (r.verdict) {
    case "WITNESS":
      return `witness found (${r.witness?.steps.length ?? 0} states)`;
    case "NO_WITNESS_WITHIN_BOUND":
      return `no witness within bound ${bound}`;
    default:
      return String(r.verdict);
  }
}

export function lastSeq(events: TraceEvent[]): number {
  return events.reduce((m, e) => Math.max(m, e.seq), 0);
}

export const sample = { expr, version: CONTRACT_VERSION, statuses: RUN_STATUSES.length };
