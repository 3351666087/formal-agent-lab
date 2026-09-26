// Typed client for the platform API. Contract objects come from @formal-lab/contracts (generated from the
// single Python source); the view models below are the API's list/detail shapes.
import type {
  BoundedCheckResult,
  ErrorInfo,
  ModelIR,
  PluginDescriptor,
  RunManifest,
  ScenarioManifest,
  TraceEvent,
} from "@formal-lab/contracts";

export const API = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public info: ErrorInfo) {
    super(info.message);
  }
}

async function request<T>(method: string, path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API}${path}`, {
      method,
      headers: body instanceof Blob ? headers : { "content-type": "application/json", ...headers },
      body: body === undefined ? undefined : body instanceof Blob ? body : JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError(0, { code: "RETRYABLE_FAILURE", message: `API unreachable: ${String(e)}`, retryable: true,
      details: {}, field_errors: [] } as ErrorInfo);
  }
  if (resp.status === 204) return undefined as T;
  const text = await resp.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!resp.ok) {
    const info: ErrorInfo = data?.error ?? { code: "NON_RETRYABLE_FAILURE", message: `HTTP ${resp.status}`,
      retryable: false, details: {}, field_errors: [] };
    throw new ApiError(resp.status, info);
  }
  return data as T;
}

export const get = <T>(path: string) => request<T>("GET", path);
export const post = <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
  request<T>("POST", path, body ?? {}, headers);
export const put = <T>(path: string, body: unknown) => request<T>("PUT", path, body);
export const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
export const del = (path: string) => request<void>("DELETE", path);

// ------------------------------------------------------------------ view models
export interface Project {
  id: string; name: string; description: string | null; group: string | null;
  created_at: string; updated_at: string; counts?: { models: number; scenarios: number; runs: number };
}
export interface ModelSummary {
  id: string; project_id: string; package_id: string; name: string; description: string | null;
  latest_version: number; created_at: string; updated_at: string;
  versions?: VersionSummary[];
}
export interface VersionSummary {
  id: string; model_id: string; version: number; digest: string; semantic_profile: string;
  parent_version: number | null; note: string | null; created_at: string;
}
export interface VersionDetail extends VersionSummary {
  package: { ir: ModelIR; digest: { value: string }; package_id: string; version: number };
  action_specs: { action_type: string; label?: string | null; preconditions: string[]; expected_effects: string[];
    params_schema: { properties: Record<string, { enum?: string[]; minimum?: number; maximum?: number; type: string }> } }[];
  summary: { state_locations: number; ground_actions: number };
  capability_matrix: { feature: string; description: string; status: Record<string, string>;
    unsupported_answer?: string | null; extension_point?: string | null }[];
}
export interface ModelIssue { path: string; code: string; message: string }
export interface Validation {
  valid: boolean; issues: ModelIssue[]; schema_errors: { path: string; message: string }[]; digest?: string;
  summary?: { state_locations: number; ground_actions: number; properties: Record<string, string> };
}
export interface ModelChange { section: string; name: string; kind: "added" | "removed" | "changed"; before?: unknown; after?: unknown }
export interface CheckRecord { id: string; model_version_id: string; query: Record<string, unknown>; verdict: string;
  result: BoundedCheckResult; created_at: string }
export interface Scenario {
  id: string; project_id: string; name: string; revision: number; model_version_id: string;
  model_id: string | null; model_name: string | null; model_version: number | null;
  manifest: ScenarioManifest; copied_from: string | null; created_at: string; updated_at: string;
}
export interface CatalogEntry {
  descriptor: PluginDescriptor; source: string; descriptor_digest: string; available: boolean;
  availability_note?: string;
}
export interface Strategy {
  id: string; project_id: string; name: string; plugin_id: string; plugin_version: string;
  config: Record<string, unknown>; descriptor: PluginDescriptor; source_kind: string | null;
  created_at: string; updated_at: string;
}
export interface MetricCell { value: number | null; status: string; unit?: string | null }
export interface RunSummary {
  id: string; project_id: string; scenario_id: string | null; status: string; status_reason: string | null;
  source_run_id: string | null; matrix_id: string | null; strategy: { plugin_id: string; version: string } | null;
  strategy_config_id: string | null; seed: number; scenario_name: string; model: RunManifest["model"];
  budget: RunManifest["budget"]; usage: Record<string, number>; event_seq: number; last_step: number;
  imported: boolean; created_at: string; started_at: string | null; finished_at: string | null;
  error: { code: string; message: string } | null; metrics: Record<string, MetricCell>;
}
export interface RunDetail extends RunSummary {
  manifest: RunManifest; final_state: { truth_state: Record<string, unknown>; properties: Record<string, boolean> } | null;
  lineage: { source_run_id: string | null; reruns: string[] };
}
export interface StepDetail {
  run_id: string; step: number; events: { seq: number; event_id: string; event_type: string }[];
  observation?: import("@formal-lab/contracts").Observation;
  belief?: { unknown_paths: string[]; stale_paths: string[] };
  candidates?: import("@formal-lab/contracts").CandidateAction[];
  proposal?: import("@formal-lab/contracts").ActionProposal;
  model_call_artifacts?: import("@formal-lab/contracts").ArtifactRef[];
  checks?: { purpose: string; result: BoundedCheckResult }[];
  outcome?: import("@formal-lab/contracts").ActionOutcome;
  comparison?: import("@formal-lab/contracts").EffectComparison;
  observation_after?: import("@formal-lab/contracts").Observation;
}
export interface Meta {
  platform_version: string; source_revision: string | null; contract_version: string; contract_digest: string;
  deployment_profile: string; capability_level: string; llm: { configured: boolean; model: string | null };
  capability_matrix: VersionDetail["capability_matrix"]; plugin_load_errors: unknown[];
}
export interface MatrixSummary {
  id: string; project_id: string; name: string; spec: Record<string, unknown> & { source?: string };
  created_at: string; runs: number; statuses: Record<string, number>;
}
export interface MetricAggregate {
  result: { value: number | null; status: string; unit?: string | null; sample_size?: number | null;
    missing_count?: number | null; missing_reason?: string | null; aggregation?: string | null;
    ci?: { low: number; high: number; level: number; method: string; n: number } | null };
  notes: { n: number; missing: number; not_applicable: number; direction: string; ci_note?: string };
}
export interface MatrixReport {
  matrix: MatrixSummary; complete: boolean;
  cells: { scenario: string; strategy: string; seed: number; budget: string; run_id: string; status: string }[];
  aggregates: { scenario: string; scenario_label: string; strategy: string; strategy_label: string; budget: string;
    runs: number; statuses: Record<string, number>; source_kinds: string[]; metrics: Record<string, MetricAggregate> }[];
  comparisons: { strategy_a: string; strategy_b: string; metric_id: string; a: string; b: string; n_pairs: number;
    mean_diff_b_minus_a: number | null; ci: MetricAggregate["result"]["ci"]; better: string | null;
    unpaired: number; test: { reported: boolean; p_value?: number; significant?: boolean; reason?: string; method?: string;
      n_nonzero?: number } }[];
  definitions: { metric_id: string; label: string; unit: string; direction: string; aggregation: string }[];
  methods: Record<string, string>;
}
export type { TraceEvent };

export const TERMINAL = new Set(["SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"]);
