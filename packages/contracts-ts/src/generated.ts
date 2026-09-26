/* eslint-disable */
// GENERATED from contracts/v1/bundle.schema.json by scripts/generate.mjs — do not edit.

export type ActionType = string;
/**
 * null when it is unknown whether the effect took place
 */
export type EffectApplied = boolean | null;
export type Expected = boolean | number | string | null;
export type Observed = boolean | number | string | null;
export type Path = string;
export type Status = "MATCH" | "DIFFERENT" | "UNKNOWN";
export type Diffs = FieldDiff[];
export type Algorithm = "sha256";
export type Value = string;
export type FormatVersion = string;
export type MediaType = string;
export type Name = string | null;
export type SizeBytes = number;
/**
 * object location, e.g. file://… or s3://bucket/key
 */
export type Uri = string;
export type Id = string;
export type Kind = "event" | "artifact" | "check" | "snapshot" | "operation" | "model_call";
export type Note = string | null;
export type Evidence = EvidenceRef[];
/**
 * what produced the expectation, e.g. model:<package>@<version>
 */
export type ExpectedBy = string;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ComparisonVerdict".
 */
export type ComparisonVerdict = "MATCH" | "DIFFERENT" | "INSUFFICIENT_INFORMATION";
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ErrorCode".
 */
export type ErrorCode =
  | "INVALID_INPUT"
  | "VERSION_MISMATCH"
  | "UNSUPPORTED"
  | "TIMEOUT"
  | "RESULT_UNKNOWN"
  | "CANCELLED"
  | "RETRYABLE_FAILURE"
  | "NON_RETRYABLE_FAILURE"
  | "NOT_FOUND"
  | "CONFLICT";
export type Message = string;
export type Path1 = string;
export type FieldErrors = FieldError[];
export type Message1 = string;
export type Retryable = boolean;
export type Evidence1 = EvidenceRef[];
export type OperationId = string;
export type ProposalId = string | null;
export type RevisionAfter = number | null;
export type RevisionBefore = number;
export type RunId = string;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "OutcomeStatus".
 */
export type OutcomeStatus =
  | "APPLIED"
  | "REJECTED"
  | "FAILED_RETRYABLE"
  | "FAILED_NON_RETRYABLE"
  | "TIMED_OUT"
  | "UNKNOWN"
  | "CANCELLED";
export type StepId = string;
export type ActorId = string;
/**
 * observation state_revision the proposal relied on
 */
export type BasedOnRevision = number;
export type CandidatesConsidered = number | null;
export type ProposalId1 = string;
export type Rationale = string | null;
export type RunId1 = string;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ProposalSourceKind".
 */
export type ProposalSourceKind = "RULE" | "SYMBOLIC" | "LLM" | "LLM_STUB" | "HUMAN" | "EXTERNAL";
/**
 * model identifier for LLM / LLM_STUB sources
 */
export type Model = string | null;
export type ModelCallIds = string[];
export type PluginId = string;
export type Version = string;
export type Step = number;
export type StepId1 = string;
export type InputTokens = number;
export type ModelCalls = number;
export type OutputTokens = number;
export type ActionType1 = string;
export type Cost = number;
export type Description = string | null;
export type Kind1 = "assign";
/**
 * enum or entity set of a symbolic value; required when ambiguous
 */
export type Domain = string | null;
export type Op = "const";
export type Value1 = boolean | number | string;
export type Name1 = string;
export type Op1 = "ref";
/**
 * @minItems 1
 */
export type Args = [
  ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr,
  ...(ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr)[]
];
export type Body = ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr;
/**
 * entity set or enum to range over
 */
export type Domain1 = string;
export type Op2 = "forall" | "exists" | "count" | "sum";
export type Var = string;
export type Where = (ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr) | null;
export type Op3 =
  | "not"
  | "and"
  | "or"
  | "implies"
  | "eq"
  | "ne"
  | "lt"
  | "le"
  | "gt"
  | "ge"
  | "add"
  | "sub"
  | "mul"
  | "neg"
  | "min"
  | "max"
  | "ite";
export type Index1 = (ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr)[];
export type Name2 = string;
export type Op4 = "var";
export type Index = (ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr)[];
export type Var1 = string;
export type Value2 = ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr;
export type Condition = ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr;
export type Kind2 = "when";
export type Domain2 = string;
/**
 * @minItems 1
 */
export type Effects1 = [
  AssignEffect | WhenEffect | ForallEffect,
  ...(AssignEffect | WhenEffect | ForallEffect)[]
];
export type Kind3 = "forall";
export type Var2 = string;
export type Where1 = (ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr) | null;
export type Otherwise = (AssignEffect | WhenEffect | ForallEffect)[];
export type Then = (AssignEffect | WhenEffect | ForallEffect)[];
export type Effects = (AssignEffect | WhenEffect | ForallEffect)[];
/**
 * human-readable expected effects
 */
export type ExpectedEffects = string[];
export type Label = string | null;
export type PreconditionExpr = (ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr) | null;
/**
 * human-readable preconditions
 */
export type Preconditions = string[];
export type RetrySemantics = "IDEMPOTENT" | "RECONCILE_THEN_RETRY" | "NOT_RETRYABLE";
export type TimeoutSeconds = number;
export type Assumptions = string[];
export type Name3 = string;
export type Version1 = string;
/**
 * maximum path length explored (0 for single-step queries)
 */
export type MaxSteps = number;
export type TimeoutMs = number | null;
export type CheckId = string;
export type ContractVersion = "formal-lab-contracts/v1";
export type Explanation = string | null;
export type SchemaId = string;
export type Version2 = string;
export type InitialState = "MODEL_INITIAL" | "GIVEN_STATE";
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "QueryKind".
 */
export type QueryKind = "GOAL_REACHABILITY" | "INVARIANT_VIOLATION" | "ACTION_PRECONDITION";
/**
 * goal / invariant property to query
 */
export type PropertyId = string | null;
/**
 * conclusion holds for the model, not for the real system
 */
export type Scope = "MODEL_INTERNAL";
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "QuerySemantics".
 */
export type QuerySemantics = "EXISTS_PATH" | "ALL_PATHS" | "SINGLE_STEP";
export type ElapsedMs = number;
export type ReasonUnknown = string | null;
/**
 * raw backend status, e.g. sat / unsat / unknown / not-run
 */
export type SolverStatus = string;
export type StepsExplored = number;
export type TimeoutMs1 = number | null;
/**
 * interface through which support can be added
 */
export type ExtensionPoint = string | null;
export type Feature = string;
export type Reason = string;
export type Verdict = SearchVerdict | PreconditionVerdict;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "SearchVerdict".
 */
export type SearchVerdict = "WITNESS" | "NO_WITNESS_WITHIN_BOUND" | "UNKNOWN" | "UNSUPPORTED";
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PreconditionVerdict".
 */
export type PreconditionVerdict = "APPLICABLE" | "INAPPLICABLE" | "UNKNOWN" | "UNSUPPORTED";
export type Replay = "CONFIRMED" | "REFUTED" | "NOT_REPLAYED";
export type ReplayNote = string | null;
export type Step1 = number;
export type Steps = WitnessStep[];
export type InputTokens1 = number;
export type ModelCalls1 = number;
export type OutputTokens1 = number;
export type Steps1 = number;
export type WallSeconds = number;
/**
 * applicability judged on the actor's observation (unknown facts stay UNKNOWN)
 */
export type PreconditionVerdict1 = "APPLICABLE" | "INAPPLICABLE" | "UNKNOWN" | "UNSUPPORTED";
export type Label1 = string | null;
export type Compatible = boolean;
export type Granted = string[];
export type MissingOptional = string[];
export type MissingRequired = string[];
export type PluginId1 = string;
export type PluginVersion = string;
export type Id1 = string;
export type MinVersion = string;
export type Optional = boolean;
export type StateRevision = number;
export type Step2 = number;
export type FinalStep = number;
export type RunId2 = string;
export type MaxModelCalls = number | null;
export type MaxSteps1 = number | null;
export type MaxTokens = number | null;
export type MaxWallSeconds = number | null;
export type ContractVersion1 = "formal-lab-contracts/v1";
export type Description1 = string | null;
export type PackageId = string;
export type Version3 = number;
export type Name4 = string;
export type Description2 = string | null;
export type MetricId = string | null;
export type PropertyId1 = string | null;
export type Objectives = Objective[];
/**
 * @minItems 1
 */
export type Participants = [Participant, ...Participant[]];
export type ActorId1 = string;
export type Role = string;
export type Revision = number;
export type ScenarioId = string;
export type Seed = number;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "StopConditionKind".
 */
export type StopConditionKind = "GOAL_REACHED" | "INVARIANT_VIOLATED" | "NO_APPLICABLE_ACTION";
export type PropertyId2 = string | null;
export type StopConditions = StopCondition[];
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "RunStatus".
 */
export type RunStatus =
  | "CREATED"
  | "QUEUED"
  | "RUNNING"
  | "PAUSING"
  | "PAUSED"
  | "CANCELLING"
  | "CANCELLED"
  | "SUCCEEDED"
  | "FAILED"
  | "BUDGET_EXHAUSTED";
export type Checks = BoundedCheckResult[];
export type ActorId2 = string;
export type Evidence2 = EvidenceRef[];
export type ObservedAtStep = number;
/**
 * state location path, e.g. op_status[o1_cut]
 */
export type Path2 = string;
export type Source = "DIRECT" | "DELAYED";
export type Value3 = boolean | number | string;
export type Facts = Fact[];
export type RunId3 = string;
export type Semantics = string;
export type StateRevision1 = number;
/**
 * logical step at which the observation is taken
 */
export type Step3 = number;
export type Path3 = string;
export type Reason1 = "OBSERVATION_DELAY" | "NOT_OBSERVABLE" | "NOT_YET_OBSERVED";
export type Unknowns = UnknownItem[];
export type Step4 = number;
export type Steps2 = StepRecord[];
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Aggregation".
 */
export type Aggregation = "MEAN" | "SUM" | "MEDIAN" | "MIN" | "MAX" | "RATE";
export type Description3 = string | null;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "MetricDirection".
 */
export type MetricDirection = "HIGHER_IS_BETTER" | "LOWER_IS_BETTER" | "NONE";
export type Label2 = string;
export type MetricId1 = string;
export type Unit = string;
export type ValueType = "float" | "int" | "bool";
export type Version4 = string;
export type High = number;
export type Level = number;
export type Low = number;
export type Method = string;
export type N = number;
export type Evidence3 = EvidenceRef[];
export type MetricId2 = string;
export type MetricVersion = string;
export type MissingCount = number | null;
export type MissingReason = string | null;
/**
 * number of runs aggregated (aggregates only)
 */
export type SampleSize = number | null;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "MetricStatus".
 */
export type MetricStatus = "OK" | "MISSING" | "NOT_APPLICABLE" | "ERROR";
/**
 * run id, or matrix-cell key for aggregates
 */
export type Subject = string;
export type Unit1 = string | null;
export type Value4 = number | null;
/**
 * @minItems 1
 */
export type Actions = [ActionDecl, ...ActionDecl[]];
export type Cost1 = number;
export type Description4 = string | null;
export type Effects2 = (AssignEffect | WhenEffect | ForallEffect)[];
export type Label3 = string | null;
export type Name5 = string;
export type Name6 = string;
export type Type = BoolType | IntType | EnumType | EntityType;
export type Kind4 = "bool";
export type Kind5 = "int";
export type Max = number;
export type Min = number;
export type Kind6 = "enum";
/**
 * name of a declared enum
 */
export type Name7 = string;
export type Kind7 = "entity";
/**
 * name of a declared entity set
 */
export type Set = string;
export type Params1 = ParamDecl[];
export type Precondition = ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr;
export type Retry = "IDEMPOTENT" | "RECONCILE_THEN_RETRY" | "NOT_RETRYABLE";
export type TimeoutSeconds1 = number;
export type Description5 = string | null;
/**
 * entity sets / enums indexing the table
 */
export type Index2 = string[];
export type Name8 = string;
export type Type1 = BoolType | IntType | EnumType | EntityType;
export type Index3 = string[];
export type Value5 = boolean | number | string;
export type Cells = CellValue[];
export type Default = boolean | number | string | null;
export type Constants = ConstantDecl[];
export type Description6 = string | null;
export type Description7 = string | null;
export type Label4 = string | null;
/**
 * @minItems 1
 */
export type Members = [string, ...string[]];
export type Name9 = string;
export type EntitySets = EntitySetDecl[];
export type Description8 = string | null;
export type Name10 = string;
/**
 * @minItems 1
 */
export type Values = [string, ...string[]];
export type Enums = EnumDecl[];
/**
 * semantic features the model relies on beyond the profile (e.g. 'probabilistic_effects'); unsupported features make engines answer UNSUPPORTED
 */
export type Features = string[];
export type Name11 = string;
export type Description9 = string | null;
export type Expr = ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr;
export type Id2 = string;
export type Kind8 = "goal" | "invariant";
export type Label5 = string | null;
export type Properties = PropertyDecl[];
export type SemanticProfile = string;
/**
 * @minItems 1
 */
export type State1 = [StateVarDecl, ...StateVarDecl[]];
export type Description10 = string | null;
export type Index4 = string[];
export type Label6 = string | null;
export type Name12 = string;
/**
 * false: never revealed to agents directly
 */
export type Observable = boolean;
export type Type2 = BoolType | IntType | EnumType | EntityType;
export type Backend = string;
export type BackendVersion = string;
export type Compiled = CompiledArtifact[];
export type ContractVersion2 = "formal-lab-contracts/v1";
export type CreatedAt = string;
export type PackageId1 = string;
export type SemanticProfile1 = string;
export type Author = string | null;
/**
 * source format, e.g. fal-ir-json/v1
 */
export type Format = string;
/**
 * where the source came from (path, editor, import)
 */
export type Origin = string | null;
/**
 * version this one was edited from
 */
export type ParentVersion = number | null;
export type Text = string | null;
export type Version5 = number;
export type ActionSpecs = ActionSpec[];
export type ActorId3 = string;
export type Candidates = CandidateAction[];
export type RunId4 = string;
export type Seed1 = number;
export type Step5 = number;
export type StepId2 = string;
/**
 * e.g. query.goal_reachability, profile.deterministic_finite_v1
 */
export type Id3 = string;
export type Version6 = string;
export type Capabilities = Capability[];
export type ContractVersion3 = "formal-lab-contracts/v1";
/**
 * python import path 'module:attr' of the factory
 */
export type Entrypoint = string;
export type InputSchema = {
  [k: string]: unknown | undefined;
} | null;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PluginInterface".
 */
export type PluginInterface =
  "MODEL_FRONTEND" | "PLANNER" | "VERIFIER" | "ENVIRONMENT" | "EVALUATOR" | "ARTIFACT_STORE";
export type InterfaceVersion = string;
export type License = string | null;
export type OutputSchema = {
  [k: string]: unknown | undefined;
} | null;
export type PluginId2 = string;
export type SemanticProfiles = string[];
/**
 * package name / URL providing the plugin
 */
export type Source1 = string | null;
export type Category = string | null;
export type Description11 = string | null;
export type Label7 = string;
export type Version7 = string;
export type Artifacts = ArtifactRef[];
export type ContractVersion4 = "formal-lab-contracts/v1";
export type CreatedAt1 = string;
export type MatrixId = string | null;
/**
 * effective per-actor strategy (after overrides)
 */
export type Participants1 = Participant[];
export type SourceRevision = string | null;
export type Version8 = string;
export type InterfaceVersion1 = string;
export type PluginId3 = string;
/**
 * environment / strategy:<actor> / verifier / evaluator / model_frontend
 */
export type Role1 = string;
export type Version9 = string;
export type Plugins = PluginPin[];
export type ProjectId = string;
export type RunId5 = string;
export type Seed2 = number;
/**
 * run this one re-runs (lineage)
 */
export type SourceRunId = string | null;
export type StatusReason = string | null;
export type ActorId4 = string | null;
/**
 * event ids this event was caused by
 */
export type CausalParents = string[];
export type EventId = string;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EventType".
 */
export type EventType =
  | "RUN_CREATED"
  | "RUN_QUEUED"
  | "RUN_STARTED"
  | "OBSERVATION"
  | "CANDIDATES"
  | "ACTION_PROPOSED"
  | "CHECK_COMPLETED"
  | "ACTION_OUTCOME"
  | "EFFECT_COMPARED"
  | "STATE_SNAPSHOT"
  | "RUN_PAUSING"
  | "RUN_PAUSED"
  | "RUN_RESUMED"
  | "RUN_CANCELLING"
  | "RUN_CANCELLED"
  | "BUDGET_EXHAUSTED"
  | "RUN_SUCCEEDED"
  | "RUN_FAILED"
  | "METRICS_COMPUTED"
  | "LOG";
export type IdempotencyKey = string | null;
export type LogicalStep = number | null;
/**
 * schema id of payload, e.g. formal-lab/events/ACTION_PROPOSED@1
 */
export type PayloadSchema = string;
export type RunId6 = string;
/**
 * monotonic per-run sequence number, gap-free
 */
export type Seq = number;
export type WallTime = string;
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "RetrySemantics".
 */
export type RetrySemantics1 = "IDEMPOTENT" | "RECONCILE_THEN_RETRY" | "NOT_RETRYABLE";

/**
 * formal-lab-contracts/v1: all contract types (generated, do not edit)
 */
export interface FormalLabContractsV1 {
  ActionOutcome?: ActionOutcome;
  ActionProposal?: ActionProposal;
  ActionSpec?: ActionSpec;
  ArtifactRef?: ArtifactRef;
  BoundedCheckResult?: BoundedCheckResult;
  BudgetUsage?: BudgetUsage;
  CandidateAction?: CandidateAction;
  CapabilityNegotiation?: CapabilityNegotiation;
  CapabilityRequirement?: CapabilityRequirement;
  CheckQuery?: CheckQuery;
  EnvironmentSnapshot?: EnvironmentSnapshot;
  EpisodeRecord?: EpisodeRecord;
  ErrorInfo?: ErrorInfo;
  EvidenceRef?: EvidenceRef;
  Extension?: Extension;
  MetricDefinition?: MetricDefinition;
  MetricResult?: MetricResult;
  ModelIR?: ModelIR;
  ModelPackage?: ModelPackage;
  Observation?: Observation;
  PlanningContext?: PlanningContext;
  PluginDescriptor?: PluginDescriptor;
  RunManifest?: RunManifest;
  ScenarioManifest?: ScenarioManifest;
  TraceEvent?: TraceEvent;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ActionOutcome".
 */
export interface ActionOutcome {
  action: GroundAction;
  effect_applied: EffectApplied;
  effect_comparison?: EffectComparison | null;
  error?: ErrorInfo | null;
  evidence?: Evidence1;
  operation_id: OperationId;
  proposal_id?: ProposalId;
  result?: Result;
  revision_after?: RevisionAfter;
  revision_before: RevisionBefore;
  run_id: RunId;
  status: OutcomeStatus;
  step_id: StepId;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "GroundAction".
 */
export interface GroundAction {
  action_type: ActionType;
  params?: Params;
}
export interface Params {
  [k: string]: boolean | number | string | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EffectComparison".
 */
export interface EffectComparison {
  diffs?: Diffs;
  evidence?: Evidence;
  expected_by: ExpectedBy;
  verdict: ComparisonVerdict;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "FieldDiff".
 */
export interface FieldDiff {
  expected: Expected;
  observed: Observed;
  path: Path;
  status: Status;
}
/**
 * Reference to something that supports a claim: an event, artifact, check or snapshot.
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EvidenceRef".
 */
export interface EvidenceRef {
  artifact?: ArtifactRef | null;
  id: Id;
  kind: Kind;
  note?: Note;
}
/**
 * Pointer to a large object held by an ArtifactStore (never inlined into events).
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ArtifactRef".
 */
export interface ArtifactRef {
  digest: Digest;
  format_version: FormatVersion;
  media_type: MediaType;
  name?: Name;
  size_bytes: SizeBytes;
  uri: Uri;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Digest".
 */
export interface Digest {
  algorithm?: Algorithm;
  value: Value;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ErrorInfo".
 */
export interface ErrorInfo {
  code: ErrorCode;
  details?: Details;
  field_errors?: FieldErrors;
  message: Message1;
  retryable: Retryable;
}
export interface Details {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "FieldError".
 */
export interface FieldError {
  message: Message;
  path: Path1;
}
export interface Result {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ActionProposal".
 */
export interface ActionProposal {
  action: GroundAction;
  actor_id: ActorId;
  based_on_revision: BasedOnRevision;
  candidates_considered?: CandidatesConsidered;
  proposal_id: ProposalId1;
  rationale?: Rationale;
  run_id: RunId1;
  source: ProposalSource;
  step: Step;
  step_id: StepId1;
  usage?: ModelUsage;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ProposalSource".
 */
export interface ProposalSource {
  kind: ProposalSourceKind;
  model?: Model;
  model_call_ids?: ModelCallIds;
  strategy: PluginRef;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PluginRef".
 */
export interface PluginRef {
  plugin_id: PluginId;
  version: Version;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ModelUsage".
 */
export interface ModelUsage {
  input_tokens?: InputTokens;
  model_calls?: ModelCalls;
  output_tokens?: OutputTokens;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ActionSpec".
 */
export interface ActionSpec {
  action_type: ActionType1;
  cost?: Cost;
  description?: Description;
  effects?: Effects;
  expected_effects?: ExpectedEffects;
  label?: Label;
  params_schema: ParamsSchema;
  precondition_expr?: PreconditionExpr;
  preconditions?: Preconditions;
  retry?: RetrySemantics;
  timeout_seconds?: TimeoutSeconds;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "AssignEffect".
 */
export interface AssignEffect {
  kind?: Kind1;
  target: AssignTarget;
  value: Value2;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "AssignTarget".
 */
export interface AssignTarget {
  index?: Index;
  var: Var1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ConstExpr".
 */
export interface ConstExpr {
  domain?: Domain;
  op?: Op;
  value: Value1;
}
/**
 * Reads a state variable or a constant table at the given index.
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "VarExpr".
 */
export interface VarExpr {
  index?: Index1;
  name: Name2;
  op?: Op4;
}
/**
 * Reads an action parameter or a quantifier-bound variable.
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "RefExpr".
 */
export interface RefExpr {
  name: Name1;
  op?: Op1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ApplyExpr".
 */
export interface ApplyExpr {
  args: Args;
  op: Op3;
}
/**
 * forall/exists → bool, count → number of satisfying members, sum → sum of an int body.
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "QuantExpr".
 */
export interface QuantExpr {
  body: Body;
  domain: Domain1;
  op: Op2;
  var: Var;
  where?: Where;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "WhenEffect".
 */
export interface WhenEffect {
  condition: Condition;
  kind?: Kind2;
  otherwise?: Otherwise;
  then?: Then;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ForallEffect".
 */
export interface ForallEffect {
  domain: Domain2;
  effects: Effects1;
  kind?: Kind3;
  var: Var2;
  where?: Where1;
}
/**
 * JSON Schema of the parameter object
 */
export interface ParamsSchema {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "BoundedCheckResult".
 */
export interface BoundedCheckResult {
  action_digest?: Digest | null;
  assumptions?: Assumptions;
  backend: BackendInfo;
  bound: CheckBound;
  check_id: CheckId;
  contract_version?: ContractVersion;
  explanation?: Explanation;
  extensions?: Extensions;
  model_digest: Digest;
  query: CheckQuery;
  scope?: Scope;
  semantics: QuerySemantics;
  state_digest?: Digest | null;
  stats: SolverStats;
  unsupported?: UnsupportedInfo | null;
  variable_mapping?: VariableMapping;
  verdict: Verdict;
  witness?: Witness | null;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "BackendInfo".
 */
export interface BackendInfo {
  name: Name3;
  version: Version1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "CheckBound".
 */
export interface CheckBound {
  max_steps: MaxSteps;
  timeout_ms?: TimeoutMs;
}
/**
 * namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved
 */
export interface Extensions {
  [k: string]: Extension | undefined;
}
/**
 * Namespaced, versioned extension payload. `schema_id` names the JSON Schema that validates `data`.
 *
 * This interface was referenced by `Extensions`'s JSON-Schema definition
 * via the `patternProperty` "^[a-z0-9][a-z0-9-]*(\.[a-z0-9_-]+)+$".
 *
 * This interface was referenced by `Extensions1`'s JSON-Schema definition
 * via the `patternProperty` "^[a-z0-9][a-z0-9-]*(\.[a-z0-9_-]+)+$".
 *
 * This interface was referenced by `Extensions2`'s JSON-Schema definition
 * via the `patternProperty` "^[a-z0-9][a-z0-9-]*(\.[a-z0-9_-]+)+$".
 *
 * This interface was referenced by `Extensions3`'s JSON-Schema definition
 * via the `patternProperty` "^[a-z0-9][a-z0-9-]*(\.[a-z0-9_-]+)+$".
 *
 * This interface was referenced by `Extensions4`'s JSON-Schema definition
 * via the `patternProperty` "^[a-z0-9][a-z0-9-]*(\.[a-z0-9_-]+)+$".
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Extension".
 */
export interface Extension {
  data: Data;
  schema_id: SchemaId;
  version: Version2;
}
export interface Data {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "CheckQuery".
 */
export interface CheckQuery {
  /**
   * action for ACTION_PRECONDITION
   */
  action?: GroundAction | null;
  bound: CheckBound;
  initial_state?: InitialState;
  kind: QueryKind;
  property_id?: PropertyId;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "SolverStats".
 */
export interface SolverStats {
  elapsed_ms?: ElapsedMs;
  reason_unknown?: ReasonUnknown;
  solver_status: SolverStatus;
  steps_explored?: StepsExplored;
  timeout_ms?: TimeoutMs1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "UnsupportedInfo".
 */
export interface UnsupportedInfo {
  extension_point?: ExtensionPoint;
  feature: Feature;
  reason: Reason;
}
/**
 * solver symbol → state path
 */
export interface VariableMapping {
  [k: string]: string | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Witness".
 */
export interface Witness {
  replay?: Replay;
  replay_note?: ReplayNote;
  steps: Steps;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "WitnessStep".
 */
export interface WitnessStep {
  /**
   * action leading into this state (null for step 0)
   */
  action: GroundAction | null;
  state: State;
  step: Step1;
}
export interface State {
  [k: string]: boolean | number | string | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "BudgetUsage".
 */
export interface BudgetUsage {
  input_tokens?: InputTokens1;
  model_calls?: ModelCalls1;
  output_tokens?: OutputTokens1;
  steps?: Steps1;
  wall_seconds?: WallSeconds;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "CandidateAction".
 */
export interface CandidateAction {
  action: GroundAction;
  belief_applicability: PreconditionVerdict1;
  label?: Label1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "CapabilityNegotiation".
 */
export interface CapabilityNegotiation {
  compatible: Compatible;
  granted?: Granted;
  missing_optional?: MissingOptional;
  missing_required?: MissingRequired;
  plugin_id: PluginId1;
  plugin_version: PluginVersion;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "CapabilityRequirement".
 */
export interface CapabilityRequirement {
  id: Id1;
  min_version?: MinVersion;
  optional?: Optional;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EnvironmentSnapshot".
 */
export interface EnvironmentSnapshot {
  data: Data1;
  digest: Digest;
  environment: PluginRef;
  state_revision: StateRevision;
  step: Step2;
}
export interface Data1 {
  [k: string]: unknown | undefined;
}
/**
 * Input to Evaluator.score: everything needed to compute metrics deterministically.
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EpisodeRecord".
 */
export interface EpisodeRecord {
  environment_summary?: EnvironmentSummary;
  final_step: FinalStep;
  final_truth_state: FinalTruthState;
  run_id: RunId2;
  scenario: ScenarioManifest;
  status: RunStatus;
  steps: Steps2;
  usage: BudgetUsage;
}
export interface EnvironmentSummary {
  [k: string]: unknown | undefined;
}
export interface FinalTruthState {
  [k: string]: boolean | number | string | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ScenarioManifest".
 */
export interface ScenarioManifest {
  budget: Budget;
  contract_version?: ContractVersion1;
  description?: Description1;
  environment: EnvironmentSpec;
  extensions?: Extensions1;
  model: ModelRef;
  name: Name4;
  objectives?: Objectives;
  participants: Participants;
  revision?: Revision;
  scenario_id: ScenarioId;
  seed?: Seed;
  stop_conditions?: StopConditions;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Budget".
 */
export interface Budget {
  max_model_calls?: MaxModelCalls;
  max_steps?: MaxSteps1;
  max_tokens?: MaxTokens;
  max_wall_seconds?: MaxWallSeconds;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EnvironmentSpec".
 */
export interface EnvironmentSpec {
  config?: Config;
  plugin: PluginRef;
}
export interface Config {
  [k: string]: unknown | undefined;
}
/**
 * namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved
 */
export interface Extensions1 {
  [k: string]: Extension | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ModelRef".
 */
export interface ModelRef {
  digest: Digest;
  package_id: PackageId;
  version: Version3;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Objective".
 */
export interface Objective {
  description?: Description2;
  metric_id?: MetricId;
  property_id?: PropertyId1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Participant".
 */
export interface Participant {
  actor_id: ActorId1;
  role?: Role;
  strategy: StrategySpec;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "StrategySpec".
 */
export interface StrategySpec {
  config?: Config1;
  plugin: PluginRef;
}
export interface Config1 {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "StopCondition".
 */
export interface StopCondition {
  kind: StopConditionKind;
  property_id?: PropertyId2;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "StepRecord".
 */
export interface StepRecord {
  checks?: Checks;
  observation: Observation;
  outcome: ActionOutcome | null;
  proposal: ActionProposal | null;
  step: Step4;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Observation".
 */
export interface Observation {
  actor_id: ActorId2;
  evidence?: Evidence2;
  facts: Facts;
  run_id: RunId3;
  semantics?: Semantics;
  state_revision: StateRevision1;
  step: Step3;
  unknowns?: Unknowns;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Fact".
 */
export interface Fact {
  observed_at_step: ObservedAtStep;
  path: Path2;
  source?: Source;
  value: Value3;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "UnknownItem".
 */
export interface UnknownItem {
  last_known?: Fact | null;
  path: Path3;
  reason: Reason1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "MetricDefinition".
 */
export interface MetricDefinition {
  aggregation: Aggregation;
  description?: Description3;
  direction: MetricDirection;
  label: Label2;
  metric_id: MetricId1;
  unit: Unit;
  value_type?: ValueType;
  version?: Version4;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "MetricResult".
 */
export interface MetricResult {
  aggregation?: Aggregation | null;
  ci?: ConfidenceInterval | null;
  evidence?: Evidence3;
  metric_id: MetricId2;
  metric_version: MetricVersion;
  missing_count?: MissingCount;
  missing_reason?: MissingReason;
  sample_size?: SampleSize;
  status: MetricStatus;
  subject: Subject;
  unit?: Unit1;
  value: Value4;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ConfidenceInterval".
 */
export interface ConfidenceInterval {
  high: High;
  level: Level;
  low: Low;
  method: Method;
  n: N;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ModelIR".
 */
export interface ModelIR {
  actions: Actions;
  constants?: Constants;
  description?: Description6;
  entity_sets?: EntitySets;
  enums?: Enums;
  features?: Features;
  name: Name11;
  properties?: Properties;
  semantic_profile?: SemanticProfile;
  state: State1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ActionDecl".
 */
export interface ActionDecl {
  cost?: Cost1;
  description?: Description4;
  effects?: Effects2;
  label?: Label3;
  name: Name5;
  params?: Params1;
  precondition?: Precondition;
  retry?: Retry;
  timeout_seconds?: TimeoutSeconds1;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ParamDecl".
 */
export interface ParamDecl {
  name: Name6;
  type: Type;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "BoolType".
 */
export interface BoolType {
  kind?: Kind4;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "IntType".
 */
export interface IntType {
  kind?: Kind5;
  max: Max;
  min: Min;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EnumType".
 */
export interface EnumType {
  kind?: Kind6;
  name: Name7;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EntityType".
 */
export interface EntityType {
  kind?: Kind7;
  set: Set;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ConstantDecl".
 */
export interface ConstantDecl {
  description?: Description5;
  index?: Index2;
  name: Name8;
  type: Type1;
  value: ValueTable;
}
/**
 * Values of an indexed location family: `default` everywhere, overridden by `cells`.
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ValueTable".
 */
export interface ValueTable {
  cells?: Cells;
  default?: Default;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "CellValue".
 */
export interface CellValue {
  index: Index3;
  value: Value5;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EntitySetDecl".
 */
export interface EntitySetDecl {
  description?: Description7;
  label?: Label4;
  members: Members;
  name: Name9;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "EnumDecl".
 */
export interface EnumDecl {
  description?: Description8;
  name: Name10;
  values: Values;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PropertyDecl".
 */
export interface PropertyDecl {
  description?: Description9;
  expr: Expr;
  id: Id2;
  kind: Kind8;
  label?: Label5;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "StateVarDecl".
 */
export interface StateVarDecl {
  description?: Description10;
  index?: Index4;
  initial: ValueTable;
  label?: Label6;
  name: Name12;
  observable?: Observable;
  type: Type2;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ModelPackage".
 */
export interface ModelPackage {
  compiled?: Compiled;
  contract_version?: ContractVersion2;
  created_at: CreatedAt;
  digest: Digest1;
  extensions?: Extensions2;
  frontend: PluginRef1;
  ir: ModelIR;
  package_id: PackageId1;
  semantic_profile: SemanticProfile1;
  source: ModelSource;
  version: Version5;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "CompiledArtifact".
 */
export interface CompiledArtifact {
  artifact?: ArtifactRef | null;
  backend: Backend;
  backend_version: BackendVersion;
  digest: Digest;
  stats?: Stats;
}
export interface Stats {
  [k: string]: unknown | undefined;
}
/**
 * sha256 of the canonical IR
 */
export interface Digest1 {
  algorithm?: Algorithm;
  value: Value;
}
/**
 * namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved
 */
export interface Extensions2 {
  [k: string]: Extension | undefined;
}
/**
 * plugin category that produced the IR
 */
export interface PluginRef1 {
  plugin_id: PluginId;
  version: Version;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "ModelSource".
 */
export interface ModelSource {
  artifact?: ArtifactRef | null;
  author?: Author;
  format: Format;
  origin?: Origin;
  parent_version?: ParentVersion;
  text?: Text;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PlanningContext".
 */
export interface PlanningContext {
  action_specs: ActionSpecs;
  actor_id: ActorId3;
  budget: Budget;
  candidates: Candidates;
  model: ModelRef;
  observation: Observation;
  run_id: RunId4;
  seed: Seed1;
  step: Step5;
  step_id: StepId2;
  usage: BudgetUsage;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PluginDescriptor".
 */
export interface PluginDescriptor {
  capabilities?: Capabilities;
  config_schema?: ConfigSchema;
  contract_version?: ContractVersion3;
  entrypoint: Entrypoint;
  extensions?: Extensions3;
  input_schema?: InputSchema;
  interface: PluginInterface;
  interface_version?: InterfaceVersion;
  license?: License;
  output_schema?: OutputSchema;
  plugin_id: PluginId2;
  semantic_profiles?: SemanticProfiles;
  source?: Source1;
  ui: PluginUi;
  version: Version7;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "Capability".
 */
export interface Capability {
  id: Id3;
  params?: Params2;
  version?: Version6;
}
export interface Params2 {
  [k: string]: unknown | undefined;
}
export interface ConfigSchema {
  [k: string]: unknown | undefined;
}
/**
 * namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved
 */
export interface Extensions3 {
  [k: string]: Extension | undefined;
}
/**
 * Display metadata; the Web UI renders plugins exclusively from this and the schemas.
 *
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PluginUi".
 */
export interface PluginUi {
  action_display?: ActionDisplay;
  action_labels?: ActionLabels;
  category?: Category;
  description?: Description11;
  entity_labels?: EntityLabels;
  label: Label7;
  metric_labels?: MetricLabels;
  state_labels?: StateLabels;
  value_labels?: ValueLabels;
}
/**
 * action type → template, e.g. '分配 {op} → {machine}'
 */
export interface ActionDisplay {
  [k: string]: string | undefined;
}
/**
 * action type → label
 */
export interface ActionLabels {
  [k: string]: string | undefined;
}
export interface EntityLabels {
  [k: string]: string | undefined;
}
export interface MetricLabels {
  [k: string]: string | undefined;
}
/**
 * state variable → label
 */
export interface StateLabels {
  [k: string]: string | undefined;
}
/**
 * enum symbol → label
 */
export interface ValueLabels {
  [k: string]: string | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "RunManifest".
 */
export interface RunManifest {
  artifacts?: Artifacts;
  budget: Budget;
  budget_usage?: BudgetUsage;
  config?: Config2;
  contract_version?: ContractVersion4;
  created_at: CreatedAt1;
  extensions?: Extensions4;
  matrix_id?: MatrixId;
  model: ModelRef;
  participants: Participants1;
  platform: PlatformInfo;
  plugins: Plugins;
  project_id: ProjectId;
  run_id: RunId5;
  scenario: ScenarioManifest1;
  scenario_digest: Digest;
  seed: Seed2;
  source_run_id?: SourceRunId;
  status: RunStatus;
  status_reason?: StatusReason;
}
export interface Config2 {
  [k: string]: unknown | undefined;
}
/**
 * namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved
 */
export interface Extensions4 {
  [k: string]: Extension | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PlatformInfo".
 */
export interface PlatformInfo {
  source_revision?: SourceRevision;
  version: Version8;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "PluginPin".
 */
export interface PluginPin {
  descriptor_digest: Digest;
  interface: PluginInterface;
  interface_version: InterfaceVersion1;
  plugin_id: PluginId3;
  role: Role1;
  version: Version9;
}
/**
 * scenario snapshot as it was when the run was created
 */
export interface ScenarioManifest1 {
  budget: Budget;
  contract_version?: ContractVersion1;
  description?: Description1;
  environment: EnvironmentSpec;
  extensions?: Extensions1;
  model: ModelRef;
  name: Name4;
  objectives?: Objectives;
  participants: Participants;
  revision?: Revision;
  scenario_id: ScenarioId;
  seed?: Seed;
  stop_conditions?: StopConditions;
}
/**
 * This interface was referenced by `FormalLabContractsV1`'s JSON-Schema
 * via the `definition` "TraceEvent".
 */
export interface TraceEvent {
  actor_id?: ActorId4;
  causal_parents?: CausalParents;
  event_id: EventId;
  event_type: EventType;
  idempotency_key?: IdempotencyKey;
  logical_step?: LogicalStep;
  payload?: Payload;
  payload_schema: PayloadSchema;
  run_id: RunId6;
  seq: Seq;
  wall_time: WallTime;
}
export interface Payload {
  [k: string]: unknown | undefined;
}
