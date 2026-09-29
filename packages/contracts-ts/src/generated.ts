/* eslint-disable */
// GENERATED from contracts/v2/bundle.serialization.schema.json by scripts/generate.mjs — do not edit.

export type ActionType = string;
export type BasedOnRevision = number;
/**
 * locations written since based_on_revision
 */
export type ChangedPaths = string[];
export type CurrentRevision = number;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ConflictPolicy".
 */
export type ConflictPolicy = "REVALIDATE" | "REJECT_STALE";
export type Reason = string;
/**
 * null when it is unknown whether the effect took place
 */
export type EffectApplied = boolean | null;
/**
 * basis of `observed`: fresh observation, verified within a stated scope (probe / operation query), or unknown (not comparable); `predicted` marks a value only the model supplies (v2)
 */
export type Evidence = "observed" | "verified-within-scope" | "predicted" | "unknown";
/**
 * predicted by the model
 */
export type Expected = boolean | number | string | null;
export type Freshness = "FRESH" | "STALE" | "MISSING";
export type Observed = boolean | number | string | null;
export type ObservedAtStep = number | null;
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
export type Kind =
  | "event"
  | "artifact"
  | "check"
  | "snapshot"
  | "operation"
  | "model_call"
  | "probe"
  | "query_bundle"
  | "release"
  | "rule"
  | "plan"
  | "regression_case"
  | "session";
export type Note = string | null;
export type Evidence1 = EvidenceRef[];
/**
 * what produced the expectation, e.g. model:<package>@<version>
 */
export type ExpectedBy = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ComparisonVerdict".
 */
export type ComparisonVerdict = "MATCH" | "DIFFERENT" | "INSUFFICIENT_INFORMATION";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
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
export type Evidence2 = EvidenceRef[];
export type OperationId = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "OperationState".
 */
export type OperationState =
  "PREPARED" | "DISPATCHED" | "COMPLETED" | "FAILED" | "OUTCOME_UNKNOWN" | "RECONCILED";
export type ProposalId = string | null;
export type RevisionAfter = number | null;
export type RevisionBefore = number;
export type RunId = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
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
export type ActorStep = number;
export type GlobalStep = number;
export type Round = number;
export type ActorId1 = string;
export type PlanBasis = "FULLY_OBSERVED" | "ASSUMPTION_BASED" | "ROBUST";
export type Count = number;
/**
 * observation state_revision the proposal relied on
 */
export type BasedOnRevision1 = number;
export type CandidatesConsidered = number | null;
export type ApplicableCompletion = {
  [k: string]: boolean | number | string | undefined;
} | null;
/**
 * ground action key the request is about
 */
export type ForAction = string | null;
export type InapplicableCompletion = {
  [k: string]: boolean | number | string | undefined;
} | null;
/**
 * @minItems 1
 */
export type Paths = [string, ...string[]];
export type Reason1 = string;
export type NodeId = string | null;
export type PlanId = string;
export type Version = number;
export type ProposalId1 = string;
export type Rationale = string | null;
export type RunId1 = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ProposalSourceKind".
 */
export type ProposalSourceKind = "RULE" | "SYMBOLIC" | "LLM" | "LLM_STUB" | "HUMAN" | "EXTERNAL";
/**
 * model identifier for LLM / LLM_STUB sources
 */
export type Model = string | null;
export type ModelCallIds = string[];
export type PluginId = string;
export type Version1 = string;
export type Step = number;
export type StepId1 = string;
export type Attempts = number;
export type InputTokens = number;
export type ModelCalls = number;
export type OutputTokens = number;
export type UnconfirmedCalls = number;
export type UnreportedCalls = number;
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
 * max_over/min_over only: value when no member qualifies
 */
export type Default = (ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr) | null;
/**
 * entity set or enum to range over
 */
export type Domain1 = string;
export type Op2 = "forall" | "exists" | "count" | "sum" | "max_over" | "min_over";
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
export type AsOfStep = number | null;
export type Path2 = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Provenance".
 */
export type Provenance = "KNOWN" | "STALE" | "UNKNOWN" | "ASSUMED_INITIAL";
export type Reason2 = string | null;
/**
 * value the plan assumed (null for free UNKNOWN locations)
 */
export type Value3 = boolean | number | string | null;
export type Items = AssumptionItem[];
export type ActorId2 = string;
/**
 * locations completion-based checks range over (the observation's unknown items); other non-KNOWN locations are assumed at their value
 */
export type FreePaths = string[];
export type Step1 = number;
export type WorldRevision = number;
export type Assumptions = string[];
export type Name3 = string;
export type Version2 = string;
/**
 * maximum path length explored (0 for single-step queries)
 */
export type MaxSteps = number;
export type TimeoutMs = number | null;
export type CheckId = string;
export type ContractVersion = "formal-lab-contracts/v2";
export type Explanation = string | null;
export type SchemaId = string;
export type Version3 = string;
export type Horizon = number;
export type Level = string;
export type Optimal = boolean;
/**
 * no plan within the horizon is cheaper than this
 */
export type ProvenLower = number | null;
/**
 * a plan at most this expensive exists
 */
export type ProvenUpper = number | null;
/**
 * objective value of the returned plan
 */
export type Value4 = number | null;
export type Levels = ObjectiveBound[];
export type Method = string;
export type ObjectiveId = string;
export type PlanLength = number | null;
export type Scope = "MODEL_INTERNAL_WITHIN_HORIZON";
export type SolverCalls = number;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "OptimizationStatus".
 */
export type OptimizationStatus =
  "OPTIMAL" | "FEASIBLE" | "NO_PLAN_WITHIN_HORIZON" | "UNKNOWN" | "UNSUPPORTED";
export type InitialState = "MODEL_INITIAL" | "GIVEN_STATE";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "QueryKind".
 */
export type QueryKind =
  | "GOAL_REACHABILITY"
  | "INVARIANT_VIOLATION"
  | "ACTION_PRECONDITION"
  | "OPTIMIZE_OBJECTIVE"
  | "ROBUST_SEQUENCE";
export type Accumulation = "until_goal";
export type Description1 = string | null;
export type GoalProperty = string;
export type Horizon1 = number;
/**
 * @minItems 1
 */
export type Levels1 = [ObjectiveLevel, ...ObjectiveLevel[]];
export type Direction = "minimize" | "maximize";
export type Id1 = string;
export type Label1 = string | null;
/**
 * use the terms of ModelIR.objectives[id]
 */
export type ModelObjective = string | null;
export type Expr = (ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr) | null;
export type Kind4 = "action_cost" | "state_rate" | "terminal";
export type Label2 = string | null;
export type Weight = number;
export type Terms = CostTerm[];
export type Unit = string;
export type ObjectiveId1 = string;
/**
 * goal / invariant property to query
 */
export type PropertyId = string | null;
/**
 * ROBUST_SEQUENCE: actions in order (v2)
 */
export type Sequence = GroundAction[];
/**
 * completion of the unknowns that breaks it
 */
export type Counterexample = {
  [k: string]: boolean | number | string | undefined;
} | null;
/**
 * first action that is inapplicable (0-based)
 */
export type FailingIndex = number | null;
export type GoalFails = boolean;
export type RequireGoal = string | null;
/**
 * ground action keys, in order
 */
export type Sequence1 = string[];
export type UnknownPaths = string[];
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RobustnessVerdict".
 */
export type RobustnessVerdict = "ROBUST" | "NOT_ROBUST" | "UNKNOWN" | "UNSUPPORTED";
/**
 * conclusion holds for the model, not for the real system
 */
export type Scope1 = "MODEL_INTERNAL";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "QuerySemantics".
 */
export type QuerySemantics = "EXISTS_PATH" | "ALL_PATHS" | "SINGLE_STEP" | "OPTIMAL_PATH" | "ALL_COMPLETIONS";
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
export type Reason3 = string;
export type Verdict = SearchVerdict | PreconditionVerdict | OptimizationStatus | RobustnessVerdict;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "SearchVerdict".
 */
export type SearchVerdict = "WITNESS" | "NO_WITNESS_WITHIN_BOUND" | "UNKNOWN" | "UNSUPPORTED";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PreconditionVerdict".
 */
export type PreconditionVerdict = "APPLICABLE" | "INAPPLICABLE" | "UNKNOWN" | "UNSUPPORTED";
export type Replay = "CONFIRMED" | "REFUTED" | "NOT_REPLAYED";
export type ReplayNote = string | null;
export type Step2 = number;
export type Steps = WitnessStep[];
export type InputTokens1 = number;
export type ModelAttempts = number;
export type ModelCalls1 = number;
export type ObservationRequests = number;
export type OutputTokens1 = number;
export type Steps1 = number;
export type UnconfirmedCalls1 = number;
export type UnreportedCalls1 = number;
export type WallSeconds = number;
/**
 * applicability judged on the actor's observation (unknown facts stay UNKNOWN)
 */
export type PreconditionVerdict1 = "APPLICABLE" | "INAPPLICABLE" | "UNKNOWN" | "UNSUPPORTED";
export type Label3 = string | null;
/**
 * why it is INAPPLICABLE / UNKNOWN (v2)
 */
export type Reason4 = string | null;
export type Compatible = boolean;
export type Granted = string[];
export type MissingOptional = string[];
export type MissingRequired = string[];
export type PluginId1 = string;
export type PluginVersion = string;
/**
 * human-readable explanation (v2)
 */
export type Reasons = string[];
/**
 * role of the plugin in the run (v2)
 */
export type Role = string | null;
/**
 * SUPPORTED: all granted; PARTIAL: optional ones missing; UNSUPPORTED (v2)
 */
export type Verdict1 = ("SUPPORTED" | "PARTIAL" | "UNSUPPORTED") | null;
export type Id2 = string;
export type MinVersion = string;
export type Optional = boolean;
export type Detail = string | null;
/**
 * None: the gate could not determine it
 */
export type Holds = boolean | null;
export type Name4 = string;
/**
 * state locations the condition read
 */
export type Paths1 = string[];
export type Backend = "PURE_DATA" | "SERVICE";
export type Capabilities = string[];
export type CreatedAt = string;
/**
 * base URL of a service backend (loopback / service name)
 */
export type Endpoint = string | null;
export type Note1 = string | null;
/**
 * ownership label on every resource this session creates
 */
export type ProjectLabel = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RecoveryMode".
 */
export type RecoveryMode = "RESEED" | "SNAPSHOT" | "SERVICE_RESET" | "STATE_IMPORT";
export type RecoveryModes = RecoveryMode[];
export type Revision = number;
export type SessionId = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "SessionStatus".
 */
export type SessionStatus = "CREATED" | "STARTING" | "READY" | "RESETTING" | "CLOSED" | "FAILED";
export type UpdatedAt = string;
export type Kind5 = "FULL_STATE" | "SESSION_MARKER";
export type SessionId1 = string | null;
export type StateRevision = number;
export type Step3 = number;
export type Backend1 = "PURE_DATA" | "SERVICE";
export type FinalStep = number;
export type Evidence3 = EvidenceRef[];
export type LogicalStep = number | null;
export type Metric = string;
export type MissingReason = string | null;
export type ProbeId = string;
/**
 * where the value was read, e.g. GET /metrics of the order service
 */
export type Source = string;
export type Status1 = "OK" | "MISSING" | "ERROR";
export type Unit1 = string;
export type Value5 = number | null;
export type WallTime = string;
export type End = number;
export type Kind6 = "LOGICAL_STEPS" | "WALL_SECONDS";
export type Size = number;
export type Start = number;
export type Probes = ProbeResult[];
export type RunId2 = string;
export type MaxModelCalls = number | null;
export type MaxSteps1 = number | null;
export type MaxTokens = number | null;
export type MaxWallSeconds = number | null;
export type ContractVersion1 = "formal-lab-contracts/v2";
export type Description2 = string | null;
/**
 * pre-execution decision plugins (EXECUTION_GATE) consulted in order before every send of an operation (phase 3A); none = phase-2 behaviour
 */
export type ExecutionGates = StrategySpec[];
export type PackageId = string;
export type Version4 = number;
export type Name5 = string;
export type Description3 = string | null;
export type MetricId = string | null;
export type PropertyId1 = string | null;
export type Objectives = Objective[];
/**
 * @minItems 1
 */
export type Participants = [Participant, ...Participant[]];
export type ActorId3 = string;
/**
 * the participant's own goal property (v2)
 */
export type Goal = string | null;
export type Label4 = string | null;
export type Role1 = string;
/**
 * empty = every action type
 */
export type ActionTypes = string[];
export type ReleaseId = string;
export type Revision1 = number;
export type RulesetId = string;
export type Version5 = number;
export type ScenarioId = string;
export type Seed = number;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "StopConditionKind".
 */
export type StopConditionKind = "GOAL_REACHED" | "INVARIANT_VIOLATED" | "NO_APPLICABLE_ACTION";
export type PropertyId2 = string | null;
/**
 * v1 stop conditions; used only when `termination` is not given
 */
export type StopConditions = StopCondition[];
export type ActorGoalMode = "IGNORE" | "ALL" | "ANY";
/**
 * a violation ends the run as FAILED
 */
export type Invariants = string[];
/**
 * property whose truth ends the run successfully
 */
export type JointGoal = string | null;
/**
 * end with NO_PROGRESS after this many consecutive turns without a state change
 */
export type NoProgressLimit = number | null;
export type NoActionPolicy = "FAIL" | "SKIP_ACTOR" | "END";
export type ConflictPolicy1 = "REVALIDATE" | "REJECT_STALE";
export type TurnMode = "ROUND_ROBIN" | "FIXED_TABLE";
export type ObservationTiming = "TURN_START" | "ROUND_START";
/**
 * FIXED_TABLE: actor ids in turn order
 */
export type Table = string[];
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
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
/**
 * acting participant (v2)
 */
export type ActorId4 = string | null;
export type Checks = BoundedCheckResult[];
export type ActorId5 = string;
export type Evidence4 = EvidenceRef[];
export type ObservedAtStep1 = number;
/**
 * state location path, e.g. op_status[o1_cut]
 */
export type Path3 = string;
export type Source1 = "DIRECT" | "DELAYED";
export type Value6 = boolean | number | string;
export type Facts = Fact[];
/**
 * locations observed fresh on request (OBSERVE_MORE, v2)
 */
export type RequestedPaths = string[];
export type RunId3 = string;
export type Semantics = string;
/**
 * world revision the observation reflects
 */
export type StateRevision1 = number;
/**
 * logical step at which the observation is taken
 */
export type Step4 = number;
export type ObservationTiming1 = "TURN_START" | "ROUND_START";
export type Path4 = string;
export type Reason5 = "OBSERVATION_DELAY" | "NOT_OBSERVABLE" | "NOT_YET_OBSERVED";
export type Unknowns = UnknownItem[];
export type ActorId6 = string | null;
export type Attempts1 = number;
export type BasedOnRevision2 = number | null;
export type ActorId7 = string | null;
export type At = string;
export type CheckedAtRevision = number | null;
export type Conditions = ConditionCheck[];
export type DecisionId = string;
export type OperationId1 = string;
/**
 * Which kind of send a pre-execution decision is about (phase 3A, G2).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ExecutionPhase".
 */
export type ExecutionPhase = "FIRST_SEND" | "RESEND" | "REEXECUTE";
export type Reason6 = string;
export type RequestDigest = string;
export type RunId4 = string;
export type Step5 = number;
export type ValuesSource = "FRESH" | "OBSERVATION" | "NONE";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "GateVerdict".
 */
export type GateVerdict = "ALLOW" | "DENY";
/**
 * pre-execution decisions (phase 3A)
 */
export type Decisions = ExecutionDecision[];
export type Kind7 = "apply" | "reset" | "probe";
export type OperationId2 = string;
export type ProposalId2 = string | null;
/**
 * the environment knows the operation (it took effect or was rejected)
 */
export type Found = boolean;
export type Method1 = "QUERY_OPERATION" | "STATE_COMPARISON" | "SNAPSHOT_REPLAY" | "MANUAL";
export type Note2 = string;
/**
 * sha256 of the canonical request (actor, kind, action); the same id with another request is a conflict (phase 3A)
 */
export type RequestDigest1 = string | null;
export type At1 = string;
export type By = string;
export type Note3 = string | null;
export type Status2 = "NEEDS_REVIEW" | "CONFIRMED_APPLIED" | "CONFIRMED_NOT_APPLIED" | "TERMINATED";
export type RunId5 = string;
export type Step6 = number;
export type At2 = string;
export type Attempt = number;
/**
 * What one operation transition did to the backend (phase 3A, G2): reading history is not a side effect.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "OperationEffect".
 */
export type OperationEffect = "NONE" | "SEND" | "QUERY" | "REUSE";
export type Reason7 = string;
export type Transitions = OperationTransition[];
export type Probes1 = ProbeResult[];
export type ElapsedMs1 = number;
export type Evidence5 = EvidenceRef[];
export type InputDigest = string | null;
export type Note4 = string | null;
export type OutputDigest = string | null;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RetrySemantics".
 */
export type RetrySemantics1 = "IDEMPOTENT" | "RECONCILE_THEN_RETRY" | "NOT_RETRYABLE";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ExecutionStage".
 */
export type ExecutionStage =
  "TURN" | "OBSERVE" | "PROPOSE" | "CHECK" | "EXECUTE" | "RECONCILE" | "PROBE" | "COMPARE" | "TERMINATE";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "StageStatus".
 */
export type StageStatus = "OK" | "SKIPPED" | "FAILED" | "UNKNOWN";
export type Stages = StageRecord[];
export type Step7 = number;
export type Steps2 = StepRecord[];
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TerminationReason".
 */
export type TerminationReason =
  | "JOINT_GOAL_REACHED"
  | "ACTOR_GOAL_REACHED"
  | "ALL_ACTOR_GOALS_REACHED"
  | "INVARIANT_VIOLATED"
  | "NO_APPLICABLE_ACTION"
  | "NO_PROGRESS"
  | "BUDGET_EXHAUSTED"
  | "ACTOR_BUDGETS_EXHAUSTED"
  | "CANCELLED"
  | "FAILED"
  | "OPERATION_UNRESOLVED";
export type ActorId8 = string | null;
export type BasedOnRevision3 = number | null;
export type OperationId3 = string;
export type ProposalId3 = string | null;
export type RequestDigest2 = string;
export type RunId6 = string;
export type Step8 = number;
export type ValuesRevision = number | null;
export type ValuesSource1 = "FRESH" | "OBSERVATION" | "NONE";
export type Conditions1 = ConditionCheck[];
export type Reason8 = string;
/**
 * @minItems 1
 */
export type Actions = [ActionDecl, ...ActionDecl[]];
export type Cost1 = number;
export type Description4 = string | null;
export type Effects2 = (AssignEffect | WhenEffect | ForallEffect)[];
export type Label5 = string | null;
export type Name6 = string;
export type Name7 = string;
export type Type = BoolType | IntType | EnumType | EntityType;
export type Kind8 = "bool";
export type Kind9 = "int";
export type Max = number;
export type Min = number;
export type Kind10 = "enum";
/**
 * name of a declared enum
 */
export type Name8 = string;
export type Kind11 = "entity";
/**
 * name of a declared entity set
 */
export type Set = string;
export type Params2 = ParamDecl[];
export type Precondition = ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr;
export type Retry = "IDEMPOTENT" | "RECONCILE_THEN_RETRY" | "NOT_RETRYABLE";
export type TimeoutSeconds1 = number;
export type Description5 = string | null;
/**
 * entity sets / enums indexing the table
 */
export type Index2 = string[];
export type Name9 = string;
export type Type1 = BoolType | IntType | EnumType | EntityType;
export type Index3 = string[];
export type Value7 = boolean | number | string;
export type Cells = CellValue[];
export type Default1 = boolean | number | string | null;
export type Constants = ConstantDecl[];
export type Description6 = string | null;
export type Description7 = string | null;
export type Label6 = string | null;
/**
 * @minItems 1
 */
export type Members = [string, ...string[]];
export type Name10 = string;
export type EntitySets = EntitySetDecl[];
export type Description8 = string | null;
export type Name11 = string;
/**
 * @minItems 1
 */
export type Values1 = [string, ...string[]];
export type Enums = EnumDecl[];
/**
 * semantic features the model relies on beyond the profile (e.g. 'probabilistic_effects'); unsupported features make engines answer UNSUPPORTED
 */
export type Features = string[];
export type Name12 = string;
export type Description9 = string | null;
export type Direction1 = "minimize" | "maximize";
export type Id3 = string;
export type Label7 = string | null;
/**
 * @minItems 1
 */
export type Terms1 = [CostTerm, ...CostTerm[]];
export type Unit2 = string;
/**
 * named cost objectives (v2)
 */
export type Objectives1 = ObjectiveDecl[];
export type Description10 = string | null;
export type Expr1 = ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr;
export type Id4 = string;
export type Kind12 = "goal" | "invariant";
export type Label8 = string | null;
export type Properties = PropertyDecl[];
export type SemanticProfile = string;
/**
 * @minItems 1
 */
export type State2 = [StateVarDecl, ...StateVarDecl[]];
export type Description11 = string | null;
export type Index4 = string[];
export type Label9 = string | null;
export type Name13 = string;
/**
 * false: never revealed to agents directly
 */
export type Observable = boolean;
export type Type2 = BoolType | IntType | EnumType | EntityType;
export type Kind13 = "fal-ir";
export type CellId = string;
export type ConfigDigest = string;
export type RulesEnabled = boolean;
export type ScenarioId1 = string;
export type ScenarioRevision = number | null;
export type Seed1 = number;
export type Split = "dev" | "acceptance";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Aggregation".
 */
export type Aggregation = "MEAN" | "SUM" | "MEDIAN" | "MIN" | "MAX" | "RATE";
export type Description12 = string | null;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "MetricDirection".
 */
export type MetricDirection = "HIGHER_IS_BETTER" | "LOWER_IS_BETTER" | "NONE";
export type Label10 = string;
export type MetricId1 = string;
export type Unit3 = string;
export type ValueType = "float" | "int" | "bool";
export type Version6 = string;
export type High = number;
export type Level1 = number;
export type Low = number;
export type Method2 = string;
export type N = number;
export type Evidence6 = EvidenceRef[];
export type MetricId2 = string;
export type MetricVersion = string;
export type MissingCount = number | null;
export type MissingReason1 = string | null;
/**
 * number of runs aggregated (aggregates only)
 */
export type SampleSize = number | null;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "MetricStatus".
 */
export type MetricStatus = "OK" | "MISSING" | "NOT_APPLICABLE" | "ERROR";
/**
 * run id, or matrix-cell key for aggregates
 */
export type Subject = string;
export type Unit4 = string | null;
export type Value8 = number | null;
export type Backend2 = string;
export type BackendVersion = string;
export type Compiled = CompiledArtifact[];
export type ContractVersion2 = "formal-lab-contracts/v2";
export type CreatedAt1 = string;
export type PackageId1 = string;
export type Payload = IRPayload | NamespacedPayload;
export type Kind14 = "namespaced";
export type Namespace = string;
export type SchemaId1 = string;
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
export type Version7 = number;
export type Assumptions1 = string[];
/**
 * bounds the checks used
 */
export type Bounds = string[];
export type CheckId1 = string | null;
export type Detail1 = string | null;
export type Kind15 = QueryKind | ("TYPE_CHECK" | "RULE_CHECK" | "OBJECTIVE_CHECK");
export type Passed = boolean;
/**
 * property / rule / objective checked
 */
export type Subject1 = string;
export type Verdict2 = string;
export type Checks1 = ReleaseCheck[];
export type Compiled1 = CompiledArtifact[];
export type CreatedAt2 = string;
export type Reasons1 = string[];
export type CaseId = string;
export type Detail2 = string;
export type Status3 = "PASS" | "FAIL" | "ERROR";
export type Regression = RegressionResult[];
export type ReleaseId1 = string;
export type Scope2 = "MODEL_INTERNAL";
export type Stages1 = StageRecord[];
export type Status4 = "RELEASED" | "REJECTED";
export type ActorId9 = string;
/**
 * keys of reusable solver/plan cache entries
 */
export type CacheRefs = string[];
export type ActorId10 = string;
export type AssumptionsDigest = string | null;
export type CreatedAtStep = number;
/**
 * node currently being executed
 */
export type Cursor = string | null;
/**
 * RULE / SYMBOLIC / LLM / LLM_STUB / EXTERNAL
 */
export type ProposalSourceKind1 = "RULE" | "SYMBOLIC" | "LLM" | "LLM_STUB" | "HUMAN" | "EXTERNAL";
export type Method3 = string | null;
export type Model1 = string | null;
export type Attempts2 = number;
export type CompletedAtStep = number | null;
export type DependsOn = string[];
/**
 * completion criterion over the belief state (IR)
 */
export type DoneWhen = (ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr) | null;
export type Label11 = string | null;
export type NodeId1 = string;
export type Note5 = string | null;
export type TaskStatus = "PENDING" | "READY" | "IN_PROGRESS" | "DONE" | "FAILED" | "SKIPPED";
export type Nodes = TaskNode[];
export type ObjectiveValue = number | null;
export type ParentVersion1 = number | null;
export type PlanId1 = string;
export type AtStep = number;
export type Detail3 = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PlanTrigger".
 */
export type PlanTrigger =
  | "INITIAL"
  | "NEW_OBSERVATION"
  | "RESOURCE_CHANGE"
  | "BUDGET"
  | "EFFECT_DIFFERENCE"
  | "ACTION_REJECTED"
  | "RULE"
  | "RESTORED";
export type Status5 = "ACTIVE" | "COMPLETED" | "INVALIDATED" | "ABANDONED";
export type Version8 = number;
/**
 * random.getstate() as JSON
 */
export type RngState = unknown[] | null;
/**
 * global step after which the checkpoint was taken
 */
export type Step9 = number;
/**
 * short natural-language summary (model-assisted)
 */
export type Summary = string | null;
export type ActionSpecs = ActionSpec[];
export type ActorId11 = string;
export type Candidates = CandidateAction[];
/**
 * the actor's goal (participant goal, else joint goal)
 */
export type Goal1 = string | null;
/**
 * the environment can answer an ObservationRequest this turn (v2)
 */
export type ObservationRequestAllowed = boolean;
/**
 * all actor ids in turn order (v2)
 */
export type Participants2 = string[];
/**
 * reason a REPLAN rule fired for this actor (v2)
 */
export type ReplanRequested = string | null;
export type RunId7 = string;
export type Seed2 = number;
export type Step10 = number;
export type StepId2 = string;
/**
 * e.g. query.goal_reachability, profile.deterministic_finite_v1
 */
export type Id5 = string;
export type Version9 = string;
export type Capabilities1 = Capability[];
export type ContractVersion3 = "formal-lab-contracts/v1" | "formal-lab-contracts/v2";
/**
 * python import path 'module:attr' of the factory
 */
export type Entrypoint = string;
export type InputSchema = {
  [k: string]: unknown | undefined;
} | null;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PluginInterface".
 */
export type PluginInterface =
  | "MODEL_FRONTEND"
  | "PLANNER"
  | "VERIFIER"
  | "ENVIRONMENT"
  | "EVALUATOR"
  | "ARTIFACT_STORE"
  | "SEMANTIC_DRIVER"
  | "PROBE"
  | "EXECUTION_GATE";
export type InterfaceVersion = string;
export type License = string | null;
export type OutputSchema = {
  [k: string]: unknown | undefined;
} | null;
export type PluginId2 = string;
/**
 * capabilities this plugin needs from its collaborators; params.of names the role (driver / environment / verifier), e.g. {id: env.persistent_session, params: {of: environment}}
 */
export type Requires = Capability[];
export type SemanticProfiles = string[];
/**
 * package name / URL providing the plugin
 */
export type Source2 = string | null;
export type Category = string | null;
export type Description13 = string | null;
export type Label12 = string;
export type Version10 = string;
export type BundleId = string;
export type CreatedAt3 = string;
/**
 * the shared, rendered explanation
 */
export type Explanation1 = string[];
export type Format1 = "formal-lab/query-bundle@1";
export type State3 = {
  [k: string]: boolean | number | string | undefined;
} | null;
export type UnknownPaths1 = string[];
export type Actions1 = GroundAction[];
export type CaseId1 = string;
export type ComparedPaths = string[];
export type CreatedAt4 = string;
export type Minimized = boolean;
export type Seed3 = number | null;
export type Source3 = "COUNTEREXAMPLE" | "EFFECT_DIFFERENCE";
export type CompletionsChecked = number;
export type Explanation2 = string;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RuleOutcome".
 */
export type RuleOutcome = "CONTINUE" | "OBSERVE_MORE" | "REPLAN" | "PAUSE";
export type Priority = number;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RuleResult".
 */
export type RuleResult = "TRUE" | "FALSE" | "UNKNOWN" | "TIMEOUT" | "CONFLICT" | "UNSUPPORTED";
export type RuleId = string;
export type Evaluations = RuleEvaluation[];
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
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
  | "LOG"
  | "TURN_STARTED"
  | "TURN_SKIPPED"
  | "OBSERVATION_REQUESTED"
  | "PLAN_UPDATED"
  | "PLANNER_CHECKPOINT"
  | "OPERATION_STATE"
  | "OPERATION_RECONCILED"
  | "OPERATION_REVIEW"
  | "PROBE_SAMPLED"
  | "RULE_EVALUATED"
  | "SESSION_STATE"
  | "RECOVERY"
  | "MODEL_REVISION_SUGGESTED"
  | "REGRESSION_CASE_CREATED"
  | "EXECUTION_DECIDED";
export type PriorityExplanation = string;
export type Winner = string | null;
export type CreatedAt5 = string | null;
export type Name14 = string;
export type Note6 = string | null;
export type ParentVersion2 = number | null;
export type Condition1 = ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr;
export type Enabled = boolean;
export type Label13 = string | null;
export type Message2 = string;
/**
 * OBSERVE_MORE: locations to request
 */
export type ObservePaths = string[];
/**
 * higher first; ties with different outcomes are a CONFLICT
 */
export type Priority1 = number;
export type RuleId1 = string;
/**
 * event types that make the rule evaluate
 *
 * @minItems 1
 */
export type Events = [EventType, ...EventType[]];
export type Rules = Rule[];
export type RulesetId1 = string;
export type Version11 = number;
export type Artifacts = ArtifactRef[];
export type ContractVersion4 = "formal-lab-contracts/v2";
export type CreatedAt6 = string;
export type MatrixId = string | null;
/**
 * capability negotiation performed before the run was created (v2)
 */
export type Negotiation = CapabilityNegotiation[];
/**
 * effective per-actor strategy (after overrides)
 */
export type Participants3 = Participant[];
export type SourceRevision = string | null;
export type Version12 = string;
export type InterfaceVersion1 = string;
export type PluginId3 = string;
/**
 * environment / strategy:<actor> / verifier / evaluator / model_frontend
 */
export type Role2 = string;
export type Version13 = string;
export type Plugins = PluginPin[];
export type ProjectId = string;
export type RunId8 = string;
export type Seed4 = number;
/**
 * run this one re-runs (lineage)
 */
export type SourceRunId = string | null;
export type StatusReason = string | null;
export type ActorId12 = string | null;
/**
 * event ids this event was caused by
 */
export type CausalParents = string[];
export type EventId = string;
export type IdempotencyKey = string | null;
export type LogicalStep1 = number | null;
/**
 * schema id of payload, e.g. formal-lab/events/ACTION_PROPOSED@1
 */
export type PayloadSchema = string;
export type RunId9 = string;
/**
 * monotonic per-run sequence number, gap-free
 */
export type Seq = number;
export type WallTime1 = string;
/**
 * last completed global step (0 before the first turn)
 */
export type GlobalStep1 = number;
/**
 * actors whose own goal holds
 */
export type GoalsReached = string[];
/**
 * consecutive turns without a state change
 */
export type NoProgress = number;
/**
 * index into the turn cycle of the next turn
 */
export type Position = number;
/**
 * actors out of budget / finished; never scheduled
 */
export type Retired = string[];
export type Round1 = number;
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ActorGoalMode".
 */
export type ActorGoalMode1 = "IGNORE" | "ALL" | "ANY";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "NoActionPolicy".
 */
export type NoActionPolicy1 = "FAIL" | "SKIP_ACTOR" | "END";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ObservationTiming".
 */
export type ObservationTiming2 = "TURN_START" | "ROUND_START";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PlanBasis".
 */
export type PlanBasis1 = "FULLY_OBSERVED" | "ASSUMPTION_BASED" | "ROBUST";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TaskStatus".
 */
export type TaskStatus1 = "PENDING" | "READY" | "IN_PROGRESS" | "DONE" | "FAILED" | "SKIPPED";
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TurnMode".
 */
export type TurnMode1 = "ROUND_ROBIN" | "FIXED_TABLE";

/**
 * formal-lab-contracts/v2: all contract types as serialized by the platform (generated, do not edit)
 */
export interface FormalLabContractsV2 {
  ActionOutcome?: ActionOutcome;
  ActionProposal?: ActionProposal;
  ActionSpec?: ActionSpec;
  ArtifactRef?: ArtifactRef;
  AssumptionSet?: AssumptionSet;
  BeliefState?: BeliefState;
  BoundedCheckResult?: BoundedCheckResult;
  BudgetUsage?: BudgetUsage;
  CandidateAction?: CandidateAction;
  CapabilityNegotiation?: CapabilityNegotiation;
  CapabilityRequirement?: CapabilityRequirement;
  CheckQuery?: CheckQuery;
  ConditionCheck?: ConditionCheck;
  EnvironmentSession?: EnvironmentSession;
  EnvironmentSnapshot?: EnvironmentSnapshot;
  EpisodeRecord?: EpisodeRecord;
  ErrorInfo?: ErrorInfo;
  EvidenceRef?: EvidenceRef;
  ExecutionDecision?: ExecutionDecision;
  Extension?: Extension;
  GateRequest?: GateRequest;
  GateResult?: GateResult;
  IRPayload?: IRPayload;
  MatrixCellSpec?: MatrixCellSpec;
  MetricDefinition?: MetricDefinition;
  MetricResult?: MetricResult;
  ModelIR?: ModelIR;
  ModelPackage?: ModelPackage;
  ModelReleaseRecord?: ModelReleaseRecord;
  NamespacedPayload?: NamespacedPayload;
  ObjectiveSpec?: ObjectiveSpec;
  Observation?: Observation;
  ObservationRequest?: ObservationRequest;
  OperationRecord?: OperationRecord;
  OptimizationResult?: OptimizationResult;
  PlannerCheckpoint?: PlannerCheckpoint;
  PlanningContext?: PlanningContext;
  PluginDescriptor?: PluginDescriptor;
  ProbeResult?: ProbeResult;
  QueryBundle?: QueryBundle;
  RegressionCase?: RegressionCase;
  RobustnessResult?: RobustnessResult;
  RuleDecision?: RuleDecision;
  RuleEvaluation?: RuleEvaluation;
  RuleSet?: RuleSet;
  RunManifest?: RunManifest;
  ScenarioManifest?: ScenarioManifest;
  StageRecord?: StageRecord;
  StepRecord?: StepRecord;
  TaskPlan?: TaskPlan;
  TerminationPolicy?: TerminationPolicy;
  TraceEvent?: TraceEvent;
  TurnPolicy?: TurnPolicy2;
  TurnRef?: TurnRef;
  TurnState?: TurnState;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ActionOutcome".
 */
export interface ActionOutcome {
  action: GroundAction;
  conflict: ConflictInfo | null;
  effect_applied: EffectApplied;
  effect_comparison: EffectComparison | null;
  error: ErrorInfo | null;
  evidence: Evidence2;
  operation_id: OperationId;
  /**
   * coordination state (v2)
   */
  operation_state: OperationState | null;
  proposal_id: ProposalId;
  result: Result;
  revision_after: RevisionAfter;
  revision_before: RevisionBefore;
  run_id: RunId;
  status: OutcomeStatus;
  step_id: StepId;
  turn: TurnRef | null;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "GroundAction".
 */
export interface GroundAction {
  action_type: ActionType;
  params: Params;
}
export interface Params {
  [k: string]: boolean | number | string | undefined;
}
/**
 * Why a proposal based on an older world revision was rejected (shared-resource arbitration).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ConflictInfo".
 */
export interface ConflictInfo {
  based_on_revision: BasedOnRevision;
  changed_paths: ChangedPaths;
  current_revision: CurrentRevision;
  policy: ConflictPolicy;
  reason: Reason;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EffectComparison".
 */
export interface EffectComparison {
  diffs: Diffs;
  evidence: Evidence1;
  evidence_counts: EvidenceCounts;
  expected_by: ExpectedBy;
  verdict: ComparisonVerdict;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "FieldDiff".
 */
export interface FieldDiff {
  evidence: Evidence;
  expected: Expected;
  freshness: Freshness;
  observed: Observed;
  observed_at_step: ObservedAtStep;
  path: Path;
  status: Status;
}
/**
 * Reference to something that supports a claim: an event, artifact, check or snapshot.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EvidenceRef".
 */
export interface EvidenceRef {
  artifact: ArtifactRef | null;
  id: Id;
  kind: Kind;
  note: Note;
}
/**
 * Pointer to a large object held by an ArtifactStore (never inlined into events).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ArtifactRef".
 */
export interface ArtifactRef {
  digest: Digest;
  format_version: FormatVersion;
  media_type: MediaType;
  name: Name;
  size_bytes: SizeBytes;
  uri: Uri;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Digest".
 */
export interface Digest {
  algorithm: Algorithm;
  value: Value;
}
/**
 * evidence status → fields (v2)
 */
export interface EvidenceCounts {
  [k: string]: number | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ErrorInfo".
 */
export interface ErrorInfo {
  code: ErrorCode;
  details: Details;
  field_errors: FieldErrors;
  message: Message1;
  retryable: Retryable;
}
export interface Details {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
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
 * Position of one action in the interleaving: global step g, round r, and the actor's own step count.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TurnRef".
 */
export interface TurnRef {
  actor_id: ActorId;
  actor_step: ActorStep;
  global_step: GlobalStep;
  round: Round;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ActionProposal".
 */
export interface ActionProposal {
  action: GroundAction;
  actor_id: ActorId1;
  /**
   * what the proposal assumed (v2)
   */
  assumptions: AssumptionSetRef | null;
  based_on_revision: BasedOnRevision1;
  candidates_considered: CandidatesConsidered;
  /**
   * ask for fresh observations first; `action` is the fallback if none are possible
   */
  observation_request: ObservationRequest | null;
  /**
   * task-plan node this proposal executes (v2)
   */
  plan: PlanRef | null;
  proposal_id: ProposalId1;
  rationale: Rationale;
  run_id: RunId1;
  source: ProposalSource;
  step: Step;
  step_id: StepId1;
  turn: TurnRef | null;
  usage: ModelUsage;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "AssumptionSetRef".
 */
export interface AssumptionSetRef {
  basis: PlanBasis;
  count: Count;
  counts: Counts;
  digest: Digest;
}
export interface Counts {
  [k: string]: number | undefined;
}
/**
 * Extra observations that would settle an UNKNOWN verdict (P2-027).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ObservationRequest".
 */
export interface ObservationRequest {
  applicable_completion: ApplicableCompletion;
  for_action: ForAction;
  inapplicable_completion: InapplicableCompletion;
  paths: Paths;
  reason: Reason1;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PlanRef".
 */
export interface PlanRef {
  node_id: NodeId;
  plan_id: PlanId;
  version: Version;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ProposalSource".
 */
export interface ProposalSource {
  kind: ProposalSourceKind;
  model: Model;
  model_call_ids: ModelCallIds;
  strategy: PluginRef;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PluginRef".
 */
export interface PluginRef {
  plugin_id: PluginId;
  version: Version1;
}
/**
 * Model usage of one proposal: `model_calls` usable responses, `attempts` requests sent; tokens as reported.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ModelUsage".
 */
export interface ModelUsage {
  attempts: Attempts;
  input_tokens: InputTokens;
  model_calls: ModelCalls;
  output_tokens: OutputTokens;
  unconfirmed_calls: UnconfirmedCalls;
  unreported_calls: UnreportedCalls;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ActionSpec".
 */
export interface ActionSpec {
  action_type: ActionType1;
  cost: Cost;
  description: Description;
  effects: Effects;
  expected_effects: ExpectedEffects;
  label: Label;
  params_schema: ParamsSchema;
  precondition_expr: PreconditionExpr;
  preconditions: Preconditions;
  retry: RetrySemantics;
  timeout_seconds: TimeoutSeconds;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "AssignEffect".
 */
export interface AssignEffect {
  kind: Kind1;
  target: AssignTarget;
  value: Value2;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "AssignTarget".
 */
export interface AssignTarget {
  index: Index;
  var: Var1;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ConstExpr".
 */
export interface ConstExpr {
  domain: Domain;
  op: Op;
  value: Value1;
}
/**
 * Reads a state variable or a constant table at the given index.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "VarExpr".
 */
export interface VarExpr {
  index: Index1;
  name: Name2;
  op: Op4;
}
/**
 * Reads an action parameter or a quantifier-bound variable.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RefExpr".
 */
export interface RefExpr {
  name: Name1;
  op: Op1;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ApplyExpr".
 */
export interface ApplyExpr {
  args: Args;
  op: Op3;
}
/**
 * forall/exists → bool, count → number of satisfying members, sum → sum of an int body,
 * max_over/min_over → largest/smallest int body over the satisfying members (`default` when there is none).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "QuantExpr".
 */
export interface QuantExpr {
  body: Body;
  default: Default;
  domain: Domain1;
  op: Op2;
  var: Var;
  where: Where;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "WhenEffect".
 */
export interface WhenEffect {
  condition: Condition;
  kind: Kind2;
  otherwise: Otherwise;
  then: Then;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ForallEffect".
 */
export interface ForallEffect {
  domain: Domain2;
  effects: Effects1;
  kind: Kind3;
  var: Var2;
  where: Where1;
}
/**
 * JSON Schema of the parameter object
 */
export interface ParamsSchema {
  [k: string]: unknown | undefined;
}
/**
 * Everything a belief-based conclusion assumed beyond fresh observations (P2-025).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "AssumptionSet".
 */
export interface AssumptionSet {
  counts: Counts1;
  digest: Digest;
  items: Items;
}
/**
 * provenance → number of locations
 */
export interface Counts1 {
  [k: string]: number | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "AssumptionItem".
 */
export interface AssumptionItem {
  as_of_step: AsOfStep;
  path: Path2;
  provenance: Provenance;
  reason: Reason2;
  value: Value3;
}
/**
 * What one participant may plan with: every location has a value, each with its provenance (P2-025).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "BeliefState".
 */
export interface BeliefState {
  actor_id: ActorId2;
  as_of_step: AsOfStep1;
  assumptions: AssumptionSet;
  free_paths: FreePaths;
  provenance: Provenance1;
  state: State;
  step: Step1;
  world_revision: WorldRevision;
}
/**
 * STALE locations: step of the value
 */
export interface AsOfStep1 {
  [k: string]: number | undefined;
}
export interface Provenance1 {
  [k: string]: Provenance | undefined;
}
export interface State {
  [k: string]: boolean | number | string | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "BoundedCheckResult".
 */
export interface BoundedCheckResult {
  action_digest: Digest | null;
  /**
   * assumptions behind the answer (v2)
   */
  assumption_set: AssumptionSet | null;
  assumptions: Assumptions;
  backend: BackendInfo;
  bound: CheckBound;
  check_id: CheckId;
  contract_version: ContractVersion;
  explanation: Explanation;
  extensions: Extensions;
  model_digest: Digest;
  /**
   * UNKNOWN precondition: which observations would settle it (v2)
   */
  observation_request: ObservationRequest | null;
  optimization: OptimizationResult | null;
  query: CheckQuery;
  /**
   * replayable query package (v2)
   */
  query_bundle: ArtifactRef | null;
  robustness: RobustnessResult | null;
  scope: Scope1;
  semantics: QuerySemantics;
  state_digest: Digest | null;
  stats: SolverStats;
  unsupported: UnsupportedInfo | null;
  variable_mapping: VariableMapping;
  verdict: Verdict;
  witness: Witness | null;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "BackendInfo".
 */
export interface BackendInfo {
  name: Name3;
  version: Version2;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "CheckBound".
 */
export interface CheckBound {
  max_steps: MaxSteps;
  timeout_ms: TimeoutMs;
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
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Extension".
 */
export interface Extension {
  data: Data;
  schema_id: SchemaId;
  version: Version3;
}
export interface Data {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "OptimizationResult".
 */
export interface OptimizationResult {
  horizon: Horizon;
  levels: Levels;
  method: Method;
  objective_id: ObjectiveId;
  plan_length: PlanLength;
  scope: Scope;
  solver_calls: SolverCalls;
  status: OptimizationStatus;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ObjectiveBound".
 */
export interface ObjectiveBound {
  level: Level;
  optimal: Optimal;
  proven_lower: ProvenLower;
  proven_upper: ProvenUpper;
  value: Value4;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "CheckQuery".
 */
export interface CheckQuery {
  /**
   * action for ACTION_PRECONDITION
   */
  action: GroundAction | null;
  bound: CheckBound;
  initial_state: InitialState;
  kind: QueryKind;
  /**
   * OPTIMIZE_OBJECTIVE: what to minimise (v2)
   */
  objective: ObjectiveSpec | null;
  property_id: PropertyId;
  sequence: Sequence;
}
/**
 * What a cost-aware planner optimises (P2-020).
 *
 * A candidate plan is a path s_0 → … → s_k (k ≤ horizon) that ends in the first state where `goal_property`
 * holds. Its value on each level is the sum of the level's terms over that path (see `CostTerm`); levels are
 * compared lexicographically in list order. Costs stop accumulating once the goal holds.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ObjectiveSpec".
 */
export interface ObjectiveSpec {
  accumulation: Accumulation;
  description: Description1;
  goal_property: GoalProperty;
  horizon: Horizon1;
  levels: Levels1;
  objective_id: ObjectiveId1;
}
/**
 * One lexicographic level: minimise (or maximise) the sum of its terms over the path.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ObjectiveLevel".
 */
export interface ObjectiveLevel {
  direction: Direction;
  id: Id1;
  label: Label1;
  model_objective: ModelObjective;
  terms: Terms;
  unit: Unit;
}
/**
 * One additive cost term of an objective level.
 *
 * - action_cost: `weight` × the declared `cost` of every action taken on the path.
 * - state_rate: `weight` × `expr` (int) evaluated on every post-state s_1..s_k of the path.
 * - terminal: `weight` × `expr` (int) evaluated on the final state s_k of the path.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "CostTerm".
 */
export interface CostTerm {
  expr: Expr;
  kind: Kind4;
  label: Label2;
  weight: Weight;
}
/**
 * Open-loop robustness of a fixed action sequence over all completions (P2-026). This is not policy
 * synthesis: the sequence cannot branch on later observations.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RobustnessResult".
 */
export interface RobustnessResult {
  counterexample: Counterexample;
  failing_index: FailingIndex;
  goal_fails: GoalFails;
  require_goal: RequireGoal;
  sequence: Sequence1;
  unknown_paths: UnknownPaths;
  verdict: RobustnessVerdict;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "SolverStats".
 */
export interface SolverStats {
  elapsed_ms: ElapsedMs;
  reason_unknown: ReasonUnknown;
  solver_status: SolverStatus;
  steps_explored: StepsExplored;
  timeout_ms: TimeoutMs1;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "UnsupportedInfo".
 */
export interface UnsupportedInfo {
  extension_point: ExtensionPoint;
  feature: Feature;
  reason: Reason3;
}
/**
 * solver symbol → state path
 */
export interface VariableMapping {
  [k: string]: string | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Witness".
 */
export interface Witness {
  replay: Replay;
  replay_note: ReplayNote;
  steps: Steps;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "WitnessStep".
 */
export interface WitnessStep {
  /**
   * action leading into this state (null for step 0)
   */
  action: GroundAction | null;
  state: State1;
  step: Step2;
}
export interface State1 {
  [k: string]: boolean | number | string | undefined;
}
/**
 * Usage counters. `model_calls` counts calls that returned a usable response; `model_attempts` every request
 * sent (incl. failures and lost responses); tokens are only what the provider reported — calls without usage data
 * are counted in `unreported_calls`, calls whose response was lost in `unconfirmed_calls`.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "BudgetUsage".
 */
export interface BudgetUsage {
  input_tokens: InputTokens1;
  model_attempts: ModelAttempts;
  model_calls: ModelCalls1;
  observation_requests: ObservationRequests;
  output_tokens: OutputTokens1;
  steps: Steps1;
  unconfirmed_calls: UnconfirmedCalls1;
  unreported_calls: UnreportedCalls1;
  wall_seconds: WallSeconds;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "CandidateAction".
 */
export interface CandidateAction {
  action: GroundAction;
  belief_applicability: PreconditionVerdict1;
  label: Label3;
  /**
   * UNKNOWN: what would settle it (v2)
   */
  observation_request: ObservationRequest | null;
  reason: Reason4;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "CapabilityNegotiation".
 */
export interface CapabilityNegotiation {
  compatible: Compatible;
  granted: Granted;
  missing_optional: MissingOptional;
  missing_required: MissingRequired;
  plugin_id: PluginId1;
  plugin_version: PluginVersion;
  reasons: Reasons;
  role: Role;
  verdict: Verdict1;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "CapabilityRequirement".
 */
export interface CapabilityRequirement {
  id: Id2;
  min_version: MinVersion;
  optional: Optional;
}
/**
 * One business / resource condition evaluated by an execution gate.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ConditionCheck".
 */
export interface ConditionCheck {
  detail: Detail;
  holds: Holds;
  name: Name4;
  observed: Observed1;
  paths: Paths1;
  required: Required;
}
export interface Observed1 {
  [k: string]: unknown | undefined;
}
export interface Required {
  [k: string]: unknown | undefined;
}
/**
 * A running environment instance and its lifecycle (P2-050 / P2-062).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EnvironmentSession".
 */
export interface EnvironmentSession {
  backend: Backend;
  capabilities: Capabilities;
  created_at: CreatedAt;
  endpoint: Endpoint;
  environment: PluginRef;
  health: Health;
  note: Note1;
  owner: Owner;
  project_label: ProjectLabel;
  recovery_modes: RecoveryModes;
  revision: Revision;
  session_id: SessionId;
  status: SessionStatus;
  updated_at: UpdatedAt;
}
export interface Health {
  [k: string]: unknown | undefined;
}
/**
 * project_id / run_id / profile
 */
export interface Owner {
  [k: string]: string | undefined;
}
/**
 * Environment state at a step. FULL_STATE snapshots of pure-data environments can be restored; persistent
 * service sessions produce SESSION_MARKER snapshots (revision + session reference only), which are never restored
 * — recovery reconciles against the live session instead (v2).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EnvironmentSnapshot".
 */
export interface EnvironmentSnapshot {
  data: Data1;
  digest: Digest;
  environment: PluginRef;
  kind: Kind5;
  session_id: SessionId1;
  state_revision: StateRevision;
  step: Step3;
}
export interface Data1 {
  [k: string]: unknown | undefined;
}
/**
 * Input to Evaluator.score: everything needed to compute metrics deterministically.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EpisodeRecord".
 */
export interface EpisodeRecord {
  actor_usage: ActorUsage;
  backend: Backend1;
  environment_summary: EnvironmentSummary;
  final_step: FinalStep;
  final_truth_state: FinalTruthState;
  probes: Probes;
  run_id: RunId2;
  scenario: ScenarioManifest;
  status: RunStatus;
  steps: Steps2;
  termination_reason: TerminationReason | null;
  usage: BudgetUsage;
}
export interface ActorUsage {
  [k: string]: BudgetUsage | undefined;
}
export interface EnvironmentSummary {
  [k: string]: unknown | undefined;
}
export interface FinalTruthState {
  [k: string]: boolean | number | string | undefined;
}
/**
 * An independent business observation (P2-064): taken from the service itself, not from the agent's view.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ProbeResult".
 */
export interface ProbeResult {
  evidence: Evidence3;
  logical_step: LogicalStep;
  metric: Metric;
  missing_reason: MissingReason;
  probe: PluginRef;
  probe_id: ProbeId;
  source: Source;
  status: Status1;
  unit: Unit1;
  value: Value5;
  wall_time: WallTime;
  window: ProbeWindow;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ProbeWindow".
 */
export interface ProbeWindow {
  end: End;
  kind: Kind6;
  size: Size;
  start: Start;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ScenarioManifest".
 */
export interface ScenarioManifest {
  budget: Budget;
  contract_version: ContractVersion1;
  description: Description2;
  /**
   * semantic driver; default: the one for the profile
   */
  driver: PluginRef | null;
  environment: EnvironmentSpec;
  execution_gates: ExecutionGates;
  extensions: Extensions1;
  model: ModelRef;
  name: Name5;
  /**
   * cost objective for planners and reports (v2)
   */
  objective: ObjectiveSpec | null;
  objectives: Objectives;
  participants: Participants;
  /**
   * checked model release the scenario runs on (v2)
   */
  release: ReleaseRef | null;
  revision: Revision1;
  /**
   * event–condition–handler rules to apply (v2)
   */
  rules: RuleSetRef | null;
  scenario_id: ScenarioId;
  seed: Seed;
  stop_conditions: StopConditions;
  /**
   * v2 termination; overrides stop_conditions
   */
  termination: TerminationPolicy | null;
  turns: TurnPolicy;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Budget".
 */
export interface Budget {
  max_model_calls: MaxModelCalls;
  max_steps: MaxSteps1;
  max_tokens: MaxTokens;
  max_wall_seconds: MaxWallSeconds;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EnvironmentSpec".
 */
export interface EnvironmentSpec {
  config: Config;
  plugin: PluginRef;
}
export interface Config {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "StrategySpec".
 */
export interface StrategySpec {
  config: Config1;
  plugin: PluginRef;
}
export interface Config1 {
  [k: string]: unknown | undefined;
}
/**
 * namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved
 */
export interface Extensions1 {
  [k: string]: Extension | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ModelRef".
 */
export interface ModelRef {
  digest: Digest;
  package_id: PackageId;
  version: Version4;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Objective".
 */
export interface Objective {
  description: Description3;
  metric_id: MetricId;
  property_id: PropertyId1;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Participant".
 */
export interface Participant {
  actor_id: ActorId3;
  /**
   * per-participant budget, counted separately (v2)
   */
  budget: Budget | null;
  goal: Goal;
  label: Label4;
  role: Role1;
  /**
   * ground actions this participant may choose (v2)
   */
  scope: ActionScope | null;
  strategy: StrategySpec;
}
/**
 * Which ground actions a participant may choose (candidates outside the scope are not offered to it).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ActionScope".
 */
export interface ActionScope {
  action_types: ActionTypes;
  params: Params1;
}
/**
 * parameter → allowed values (unlisted = any)
 */
export interface Params1 {
  /**
   * This interface was referenced by `Params1`'s JSON-Schema definition
   * via the `patternProperty` "^[A-Za-z_][A-Za-z0-9_]*$".
   */
  [k: string]: (boolean | number | string)[] | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ReleaseRef".
 */
export interface ReleaseRef {
  digest: Digest;
  release_id: ReleaseId;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RuleSetRef".
 */
export interface RuleSetRef {
  digest: Digest;
  ruleset_id: RulesetId;
  version: Version5;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "StopCondition".
 */
export interface StopCondition {
  kind: StopConditionKind;
  property_id: PropertyId2;
}
/**
 * When a run ends. Budget exhaustion always ends it; the rest is configured here (v1 stop conditions map to
 * `joint_goal`, `invariants` and `on_no_action=FAIL`).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TerminationPolicy".
 */
export interface TerminationPolicy {
  actor_goals: ActorGoalMode;
  invariants: Invariants;
  joint_goal: JointGoal;
  no_progress_limit: NoProgressLimit;
  on_no_action: NoActionPolicy;
}
/**
 * interleaving of participants (v2)
 */
export interface TurnPolicy {
  conflict_policy: ConflictPolicy1;
  mode: TurnMode;
  observation_timing: ObservationTiming;
  table: Table;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "StepRecord".
 */
export interface StepRecord {
  actor_id: ActorId4;
  checks: Checks;
  observation: Observation;
  operation: OperationRecord | null;
  outcome: ActionOutcome | null;
  probes: Probes1;
  proposal: ActionProposal | null;
  stages: Stages;
  step: Step7;
  turn: TurnRef | null;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Observation".
 */
export interface Observation {
  actor_id: ActorId5;
  evidence: Evidence4;
  facts: Facts;
  requested_paths: RequestedPaths;
  run_id: RunId3;
  semantics: Semantics;
  state_revision: StateRevision1;
  step: Step4;
  timing: ObservationTiming1;
  /**
   * turn the observation was taken for (v2)
   */
  turn: TurnRef | null;
  unknowns: Unknowns;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Fact".
 */
export interface Fact {
  observed_at_step: ObservedAtStep1;
  path: Path3;
  source: Source1;
  value: Value6;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "UnknownItem".
 */
export interface UnknownItem {
  last_known: Fact | null;
  path: Path4;
  reason: Reason5;
}
/**
 * Coordination record of one environment operation (P2-051). Intent is recorded before dispatch; every state
 * change is kept with its reason.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "OperationRecord".
 */
export interface OperationRecord {
  action: GroundAction | null;
  actor_id: ActorId6;
  attempts: Attempts1;
  based_on_revision: BasedOnRevision2;
  decisions: Decisions;
  kind: Kind7;
  operation_id: OperationId2;
  outcome: ActionOutcome | null;
  proposal_id: ProposalId2;
  reconciliation: ReconciliationResult | null;
  request_digest: RequestDigest1;
  review: ReviewMark | null;
  run_id: RunId5;
  state: OperationState;
  step: Step6;
  transitions: Transitions;
}
/**
 * Typed record of one pre-execution decision (phase 3A, G2): kept on the operation record and as an event, so
 * decision, operation record and the backend's side effect can be traced to each other.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ExecutionDecision".
 */
export interface ExecutionDecision {
  actor_id: ActorId7;
  at: At;
  checked_at_revision: CheckedAtRevision;
  conditions: Conditions;
  decision_id: DecisionId;
  gate: PluginRef;
  operation_id: OperationId1;
  phase: ExecutionPhase;
  reason: Reason6;
  request_digest: RequestDigest;
  run_id: RunId4;
  step: Step5;
  values_source: ValuesSource;
  verdict: GateVerdict;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ReconciliationResult".
 */
export interface ReconciliationResult {
  found: Found;
  method: Method1;
  note: Note2;
  outcome: ActionOutcome | null;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ReviewMark".
 */
export interface ReviewMark {
  at: At1;
  by: By;
  note: Note3;
  status: Status2;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "OperationTransition".
 */
export interface OperationTransition {
  at: At2;
  attempt: Attempt;
  /**
   * what this transition did to the backend (phase 3A); absent in records written before it
   */
  effect: OperationEffect | null;
  reason: Reason7;
  state: OperationState;
}
/**
 * Typed record of one execution stage (P2-016): inputs/outputs by digest, retry semantics, error, evidence.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "StageRecord".
 */
export interface StageRecord {
  elapsed_ms: ElapsedMs1;
  error: ErrorInfo | null;
  evidence: Evidence5;
  input_digest: InputDigest;
  note: Note4;
  output_digest: OutputDigest;
  retry: RetrySemantics1;
  stage: ExecutionStage;
  status: StageStatus;
}
/**
 * What an execution gate sees for one send (phase 3A, G2). `values` are the locations the gate asked for, read
 * by the kernel right before the send: fresh from the environment when it answers observation requests
 * (env.observe_on_request), else from the actor's current observation.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "GateRequest".
 */
export interface GateRequest {
  action: GroundAction;
  actor_id: ActorId8;
  based_on_revision: BasedOnRevision3;
  config: Config2;
  operation_id: OperationId3;
  phase: ExecutionPhase;
  proposal_id: ProposalId3;
  request_digest: RequestDigest2;
  run_id: RunId6;
  step: Step8;
  values: Values;
  values_revision: ValuesRevision;
  values_source: ValuesSource1;
}
/**
 * the gate's scenario configuration
 */
export interface Config2 {
  [k: string]: unknown | undefined;
}
export interface Values {
  [k: string]: boolean | number | string | undefined;
}
/**
 * A gate's answer: ALLOW or DENY with the reason and the conditions it evaluated.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "GateResult".
 */
export interface GateResult {
  conditions: Conditions1;
  reason: Reason8;
  verdict: GateVerdict;
}
/**
 * Model in the neutral finite-state IR (profile deterministic_finite_v1).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "IRPayload".
 */
export interface IRPayload {
  ir: ModelIR;
  kind: Kind13;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ModelIR".
 */
export interface ModelIR {
  actions: Actions;
  constants: Constants;
  description: Description6;
  entity_sets: EntitySets;
  enums: Enums;
  features: Features;
  name: Name12;
  objectives: Objectives1;
  properties: Properties;
  semantic_profile: SemanticProfile;
  state: State2;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ActionDecl".
 */
export interface ActionDecl {
  cost: Cost1;
  description: Description4;
  effects: Effects2;
  label: Label5;
  name: Name6;
  params: Params2;
  precondition: Precondition;
  retry: Retry;
  timeout_seconds: TimeoutSeconds1;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ParamDecl".
 */
export interface ParamDecl {
  name: Name7;
  type: Type;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "BoolType".
 */
export interface BoolType {
  kind: Kind8;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "IntType".
 */
export interface IntType {
  kind: Kind9;
  max: Max;
  min: Min;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EnumType".
 */
export interface EnumType {
  kind: Kind10;
  name: Name8;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EntityType".
 */
export interface EntityType {
  kind: Kind11;
  set: Set;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ConstantDecl".
 */
export interface ConstantDecl {
  description: Description5;
  index: Index2;
  name: Name9;
  type: Type1;
  value: ValueTable;
}
/**
 * Values of an indexed location family: `default` everywhere, overridden by `cells`.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ValueTable".
 */
export interface ValueTable {
  cells: Cells;
  default: Default1;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "CellValue".
 */
export interface CellValue {
  index: Index3;
  value: Value7;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EntitySetDecl".
 */
export interface EntitySetDecl {
  description: Description7;
  label: Label6;
  members: Members;
  name: Name10;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "EnumDecl".
 */
export interface EnumDecl {
  description: Description8;
  name: Name11;
  values: Values1;
}
/**
 * A named cost objective declared by the model: the sum of its terms over a path.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ObjectiveDecl".
 */
export interface ObjectiveDecl {
  description: Description9;
  direction: Direction1;
  id: Id3;
  label: Label7;
  terms: Terms1;
  unit: Unit2;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PropertyDecl".
 */
export interface PropertyDecl {
  description: Description10;
  expr: Expr1;
  id: Id4;
  kind: Kind12;
  label: Label8;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "StateVarDecl".
 */
export interface StateVarDecl {
  description: Description11;
  index: Index4;
  initial: ValueTable;
  label: Label9;
  name: Name13;
  observable: Observable;
  type: Type2;
}
/**
 * One matrix cell: the complete configuration; `cell_id` is derived from its canonical digest.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "MatrixCellSpec".
 */
export interface MatrixCellSpec {
  ablations: Ablations;
  budget: Budget1;
  cell_id: CellId;
  config_digest: ConfigDigest;
  environment: Environment;
  model: ModelRef | null;
  participants: Participants1;
  rules: RuleSetRef | null;
  rules_enabled: RulesEnabled;
  scenario_id: ScenarioId1;
  scenario_revision: ScenarioRevision;
  seed: Seed1;
  split: Split;
}
/**
 * mechanism switches (e.g. observation delay)
 */
export interface Ablations {
  [k: string]: unknown | undefined;
}
export interface Budget1 {
  [k: string]: unknown | undefined;
}
/**
 * {plugin, config} (backend)
 */
export interface Environment {
  [k: string]: unknown | undefined;
}
/**
 * actor → {plugin, config}
 */
export interface Participants1 {
  [k: string]:
    | {
        [k: string]: unknown | undefined;
      }
    | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "MetricDefinition".
 */
export interface MetricDefinition {
  aggregation: Aggregation;
  description: Description12;
  direction: MetricDirection;
  label: Label10;
  metric_id: MetricId1;
  unit: Unit3;
  value_type: ValueType;
  version: Version6;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "MetricResult".
 */
export interface MetricResult {
  aggregation: Aggregation | null;
  ci: ConfidenceInterval | null;
  evidence: Evidence6;
  metric_id: MetricId2;
  metric_version: MetricVersion;
  missing_count: MissingCount;
  missing_reason: MissingReason1;
  sample_size: SampleSize;
  status: MetricStatus;
  subject: Subject;
  unit: Unit4;
  value: Value8;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ConfidenceInterval".
 */
export interface ConfidenceInterval {
  high: High;
  level: Level1;
  low: Low;
  method: Method2;
  n: N;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ModelPackage".
 */
export interface ModelPackage {
  compiled: Compiled;
  contract_version: ContractVersion2;
  created_at: CreatedAt1;
  digest: Digest1;
  extensions: Extensions2;
  frontend: PluginRef1;
  package_id: PackageId1;
  payload: Payload;
  semantic_profile: SemanticProfile1;
  source: ModelSource;
  version: Version7;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "CompiledArtifact".
 */
export interface CompiledArtifact {
  artifact: ArtifactRef | null;
  backend: Backend2;
  backend_version: BackendVersion;
  digest: Digest;
  stats: Stats;
}
export interface Stats {
  [k: string]: unknown | undefined;
}
/**
 * sha256 of the canonical payload (IR: of the canonical IR, as in v1)
 */
export interface Digest1 {
  algorithm: Algorithm;
  value: Value;
}
/**
 * namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved
 */
export interface Extensions2 {
  [k: string]: Extension | undefined;
}
/**
 * plugin that produced the payload
 */
export interface PluginRef1 {
  plugin_id: PluginId;
  version: Version1;
}
/**
 * Model in a profile-specific format owned by a semantic-driver plugin. `schema_id` names the JSON Schema
 * (published in the driver's descriptor `input_schema`) that validates `data`.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "NamespacedPayload".
 */
export interface NamespacedPayload {
  data: Data2;
  kind: Kind14;
  namespace: Namespace;
  schema_id: SchemaId1;
}
export interface Data2 {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ModelSource".
 */
export interface ModelSource {
  artifact: ArtifactRef | null;
  author: Author;
  format: Format;
  origin: Origin;
  parent_version: ParentVersion;
  text: Text;
}
/**
 * Compilation and checking facts of a model (+ rules + objective) at release time. A run that pins a release
 * runs exactly what was checked; nothing here claims correctness outside the stated bounds and assumptions.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ModelReleaseRecord".
 */
export interface ModelReleaseRecord {
  assumptions: Assumptions1;
  bounds: Bounds;
  checks: Checks1;
  compiled: Compiled1;
  created_at: CreatedAt2;
  digest: Digest;
  driver: PluginRef | null;
  log: ArtifactRef | null;
  model: ModelRef;
  objective: ObjectiveSpec | null;
  reasons: Reasons1;
  regression: Regression;
  release_id: ReleaseId1;
  ruleset: RuleSetRef | null;
  scope: Scope2;
  stages: Stages1;
  status: Status4;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "ReleaseCheck".
 */
export interface ReleaseCheck {
  bound: CheckBound | null;
  check_id: CheckId1;
  detail: Detail1;
  kind: Kind15;
  passed: Passed;
  subject: Subject1;
  verdict: Verdict2;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RegressionResult".
 */
export interface RegressionResult {
  case_id: CaseId;
  detail: Detail2;
  status: Status3;
}
/**
 * Recoverable planner state (P2-041): persisted with the step's proposal and restored in a fresh process.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PlannerCheckpoint".
 */
export interface PlannerCheckpoint {
  actor_id: ActorId9;
  cache_refs: CacheRefs;
  digest: Digest | null;
  plan: TaskPlan | null;
  planner: PluginRef;
  progress: Progress;
  remaining_budget: BudgetUsage | null;
  rng_state: RngState;
  step: Step9;
  summary: Summary;
}
/**
 * A structured, versioned plan with a cursor (P2-040). Every revision is a new version with its reason.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TaskPlan".
 */
export interface TaskPlan {
  actor_id: ActorId10;
  assumptions_digest: AssumptionsDigest;
  created_at_step: CreatedAtStep;
  cursor: Cursor;
  generator: PlanGenerator;
  nodes: Nodes;
  objective_value: ObjectiveValue;
  parent_version: ParentVersion1;
  plan_id: PlanId1;
  /**
   * why this version replaced the previous one
   */
  revision: PlanRevision | null;
  status: Status5;
  version: Version8;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PlanGenerator".
 */
export interface PlanGenerator {
  kind: ProposalSourceKind1;
  method: Method3;
  model: Model1;
  strategy: PluginRef;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TaskNode".
 */
export interface TaskNode {
  /**
   * action that executes the task (if any)
   */
  action: GroundAction | null;
  attempts: Attempts2;
  completed_at_step: CompletedAtStep;
  depends_on: DependsOn;
  done_when: DoneWhen;
  label: Label11;
  node_id: NodeId1;
  note: Note5;
  status: TaskStatus;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PlanRevision".
 */
export interface PlanRevision {
  at_step: AtStep;
  detail: Detail3;
  trigger: PlanTrigger;
}
/**
 * structured task progress / memory
 */
export interface Progress {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PlanningContext".
 */
export interface PlanningContext {
  action_specs: ActionSpecs;
  actor_budget: Budget | null;
  actor_id: ActorId11;
  actor_usage: BudgetUsage | null;
  /**
   * provenance of the belief (v2)
   */
  assumptions: AssumptionSet | null;
  budget: Budget;
  candidates: Candidates;
  goal: Goal1;
  /**
   * the actor's previous outcome incl. its effect comparison (plan revision, v2)
   */
  last_outcome: ActionOutcome | null;
  model: ModelRef;
  objective: ObjectiveSpec | null;
  observation: Observation;
  observation_request_allowed: ObservationRequestAllowed;
  participants: Participants2;
  replan_requested: ReplanRequested;
  run_id: RunId7;
  seed: Seed2;
  step: Step10;
  step_id: StepId2;
  /**
   * global/actor step of this decision (v2)
   */
  turn: TurnRef | null;
  usage: BudgetUsage;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PluginDescriptor".
 */
export interface PluginDescriptor {
  capabilities: Capabilities1;
  config_schema: ConfigSchema;
  contract_version: ContractVersion3;
  entrypoint: Entrypoint;
  extensions: Extensions3;
  input_schema: InputSchema;
  interface: PluginInterface;
  interface_version: InterfaceVersion;
  license: License;
  output_schema: OutputSchema;
  plugin_id: PluginId2;
  requires: Requires;
  semantic_profiles: SemanticProfiles;
  source: Source2;
  ui: PluginUi;
  version: Version10;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Capability".
 */
export interface Capability {
  id: Id5;
  params: Params3;
  version: Version9;
}
export interface Params3 {
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
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PluginUi".
 */
export interface PluginUi {
  action_display: ActionDisplay;
  action_labels: ActionLabels;
  category: Category;
  condition_labels: ConditionLabels;
  description: Description13;
  entity_labels: EntityLabels;
  label: Label12;
  metric_labels: MetricLabels;
  state_labels: StateLabels;
  value_labels: ValueLabels;
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
/**
 * execution-gate condition name → label (phase 3A)
 */
export interface ConditionLabels {
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
 * Replayable package of one check (P2-029): everything needed to re-ask and to explain the answer.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "QueryBundle".
 */
export interface QueryBundle {
  assumptions: AssumptionSet | null;
  bundle_id: BundleId;
  created_at: CreatedAt3;
  driver: PluginRef | null;
  explanation: Explanation1;
  format: Format1;
  model: ModelRef;
  /**
   * embedded model package (exports), so the bundle can be replayed offline
   */
  package: ModelPackage | null;
  query: CheckQuery;
  replay: Replay1;
  result: BoundedCheckResult;
  state: State3;
  unknown_paths: UnknownPaths1;
  verifier: PluginRef;
}
/**
 * independent re-check of the witness
 */
export interface Replay1 {
  [k: string]: unknown | undefined;
}
/**
 * Minimal replayable case from a counterexample or an effect difference (P2-076).
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RegressionCase".
 */
export interface RegressionCase {
  actions: Actions1;
  case_id: CaseId1;
  compared_paths: ComparedPaths;
  created_at: CreatedAt4;
  expected: Expected1;
  initial_state: InitialState1;
  minimized: Minimized;
  model: ModelRef;
  observed: Observed2;
  origin: Origin1;
  scenario: ScenarioManifest | null;
  seed: Seed3;
  source: Source3;
}
/**
 * model prediction for the compared locations
 */
export interface Expected1 {
  [k: string]: boolean | number | string | undefined;
}
export interface InitialState1 {
  [k: string]: boolean | number | string | undefined;
}
/**
 * what the run observed
 */
export interface Observed2 {
  [k: string]: boolean | number | string | undefined;
}
/**
 * run_id / step / check_id it came from
 */
export interface Origin1 {
  [k: string]: unknown | undefined;
}
/**
 * Resolution of all rules that evaluated for one event: the winning outcome and why.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RuleDecision".
 */
export interface RuleDecision {
  evaluations: Evaluations;
  event_type: EventType;
  outcome: RuleOutcome;
  priority_explanation: PriorityExplanation;
  winner: Winner;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RuleEvaluation".
 */
export interface RuleEvaluation {
  completions_checked: CompletionsChecked;
  explanation: Explanation2;
  /**
   * outcome applied (null when the rule did not decide)
   */
  outcome: RuleOutcome | null;
  priority: Priority;
  result: RuleResult;
  rule_id: RuleId;
  ruleset: RuleSetRef | null;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RuleSet".
 */
export interface RuleSet {
  created_at: CreatedAt5;
  digest: Digest | null;
  model: ModelRef1;
  name: Name14;
  note: Note6;
  parent_version: ParentVersion2;
  rules: Rules;
  ruleset_id: RulesetId1;
  version: Version11;
}
/**
 * model the rules are written against (checked with it)
 */
export interface ModelRef1 {
  digest: Digest;
  package_id: PackageId;
  version: Version4;
}
/**
 * Typed event–condition–handler rule. The condition is a pure IR expression over the actor's belief state and
 * the rule context parameters; it is type-checked against the model before release.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "Rule".
 */
export interface Rule {
  condition: Condition1;
  enabled: Enabled;
  label: Label13;
  message: Message2;
  observe_paths: ObservePaths;
  outcome: RuleOutcome;
  priority: Priority1;
  rule_id: RuleId1;
  trigger: RuleTrigger;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RuleTrigger".
 */
export interface RuleTrigger {
  events: Events;
  /**
   * restrict to events of this stage
   */
  stage: ExecutionStage | null;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "RunManifest".
 */
export interface RunManifest {
  actor_usage: ActorUsage1;
  artifacts: Artifacts;
  budget: Budget;
  budget_usage: BudgetUsage;
  config: Config3;
  contract_version: ContractVersion4;
  created_at: CreatedAt6;
  extensions: Extensions4;
  matrix_id: MatrixId;
  model: ModelRef;
  negotiation: Negotiation;
  objective: ObjectiveSpec | null;
  participants: Participants3;
  platform: PlatformInfo;
  plugins: Plugins;
  project_id: ProjectId;
  release: ReleaseRef | null;
  rules: RuleSetRef | null;
  run_id: RunId8;
  scenario: ScenarioManifest1;
  scenario_digest: Digest;
  seed: Seed4;
  source_run_id: SourceRunId;
  status: RunStatus;
  status_reason: StatusReason;
  /**
   * effective termination policy (v2)
   */
  termination: TerminationPolicy | null;
  termination_reason: TerminationReason | null;
  turns: TurnPolicy1;
}
/**
 * per-participant usage (v2)
 */
export interface ActorUsage1 {
  [k: string]: BudgetUsage | undefined;
}
export interface Config3 {
  [k: string]: unknown | undefined;
}
/**
 * namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved
 */
export interface Extensions4 {
  [k: string]: Extension | undefined;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PlatformInfo".
 */
export interface PlatformInfo {
  source_revision: SourceRevision;
  version: Version12;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "PluginPin".
 */
export interface PluginPin {
  descriptor_digest: Digest;
  interface: PluginInterface;
  interface_version: InterfaceVersion1;
  plugin_id: PluginId3;
  role: Role2;
  version: Version13;
}
/**
 * scenario snapshot as it was when the run was created
 */
export interface ScenarioManifest1 {
  budget: Budget;
  contract_version: ContractVersion1;
  description: Description2;
  /**
   * semantic driver; default: the one for the profile
   */
  driver: PluginRef | null;
  environment: EnvironmentSpec;
  execution_gates: ExecutionGates;
  extensions: Extensions1;
  model: ModelRef;
  name: Name5;
  /**
   * cost objective for planners and reports (v2)
   */
  objective: ObjectiveSpec | null;
  objectives: Objectives;
  participants: Participants;
  /**
   * checked model release the scenario runs on (v2)
   */
  release: ReleaseRef | null;
  revision: Revision1;
  /**
   * event–condition–handler rules to apply (v2)
   */
  rules: RuleSetRef | null;
  scenario_id: ScenarioId;
  seed: Seed;
  stop_conditions: StopConditions;
  /**
   * v2 termination; overrides stop_conditions
   */
  termination: TerminationPolicy | null;
  turns: TurnPolicy;
}
/**
 * effective interleaving (v2)
 */
export interface TurnPolicy1 {
  conflict_policy: ConflictPolicy1;
  mode: TurnMode;
  observation_timing: ObservationTiming;
  table: Table;
}
/**
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TraceEvent".
 */
export interface TraceEvent {
  actor_id: ActorId12;
  causal_parents: CausalParents;
  event_id: EventId;
  event_type: EventType;
  idempotency_key: IdempotencyKey;
  logical_step: LogicalStep1;
  payload: Payload1;
  payload_schema: PayloadSchema;
  run_id: RunId9;
  seq: Seq;
  /**
   * execution stage that emitted it (v2)
   */
  stage: ExecutionStage | null;
  /**
   * turn the event belongs to (v2)
   */
  turn: TurnRef | null;
  wall_time: WallTime1;
}
export interface Payload1 {
  [k: string]: unknown | undefined;
}
/**
 * Explicit interleaving semantics: exactly one participant acts per logical (global) step.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TurnPolicy".
 */
export interface TurnPolicy2 {
  conflict_policy: ConflictPolicy1;
  mode: TurnMode;
  observation_timing: ObservationTiming;
  table: Table;
}
/**
 * Persistent cursor of the TurnScheduler (P2-031): restored exactly after pause, crash or continue-as-new.
 *
 * This interface was referenced by `FormalLabContractsV2`'s JSON-Schema
 * via the `definition` "TurnState".
 */
export interface TurnState {
  actor_steps: ActorSteps;
  global_step: GlobalStep1;
  goals_reached: GoalsReached;
  no_progress: NoProgress;
  position: Position;
  retired: Retired;
  round: Round1;
  skipped: Skipped;
}
export interface ActorSteps {
  [k: string]: number | undefined;
}
/**
 * turns passed per actor (no action)
 */
export interface Skipped {
  [k: string]: number | undefined;
}
