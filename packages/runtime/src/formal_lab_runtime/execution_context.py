"""Authoritative execution basis of a send (phase 4A, A2).

Right before every send — first send, re-send, pure-data re-execution — the kernel builds an `ExecutionContext`:

- identity from the kernel's own turn (`turn.actor_id`, run id, step), never from the proposal's claim; a proposal
  that claims another actor / run / step is refused before anything is sent;
- environment, session and service identity from the run's environment;
- the **current** revision from the environment's own authoritative read (`env.current_revision`, FRESH); a pure-data
  environment is the world itself and the step is serialized (SERIALIZED); anything else is UNKNOWN;
- the proposal's planning revision kept apart from it, and the versions the decision depends on (model, driver,
  rules, participant view, environment, gates).

Gates receive it in `GateRequest.execution`. When the environment applies operations conditionally
(`env.conditional_step`) the kernel sends `expected_revision = current_revision`, so a state change between the check
and the write is refused where the side effect happens; if that revision cannot be read the write is blocked.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    ActionProposal,
    ExecutionContext,
    ExecutionPhase,
    OperationRecord,
    TurnRef,
    digest_of,
    params_digest,
    utcnow,
)
from formal_lab_contracts import capabilities as caps


def authoritative_revision(env: Any, env_caps: set[str]) -> tuple[int | None, str, str]:
    """(revision, source, note) — the environment's current state revision as known right now."""
    if caps.ENV_CURRENT_REVISION in env_caps and hasattr(env, "current_revision"):
        try:
            return int(env.current_revision()), "FRESH", "read from the environment right before the send"
        except Exception as exc:  # unreachable service, malformed answer: unknown, never guessed
            return None, "UNKNOWN", f"current revision could not be read: {type(exc).__name__}: {str(exc)[:160]}"
    if caps.ENV_PURE_REPLAYABLE in env_caps and hasattr(env, "snapshot"):
        try:
            return int(env.snapshot().state_revision), "SERIALIZED", (
                "pure-data environment: its state is this process's world and the step is serialized")
        except Exception as exc:
            return None, "UNKNOWN", f"snapshot revision could not be read: {type(exc).__name__}: {str(exc)[:160]}"
    return None, "UNKNOWN", "the environment declares no authoritative revision read (env.current_revision)"


def _session(env: Any, run_id: str) -> tuple[str | None, str | None]:
    if hasattr(env, "session"):
        try:
            s = env.session()
            return s.session_id, (s.endpoint or s.session_id)
        except Exception:
            return None, None
    plugin = getattr(getattr(env, "descriptor", None), "plugin_id", "env")
    return f"{plugin}:{run_id}", None  # an in-process world: the run is its session


def run_versions(rc: Any, actor: str) -> dict[str, str]:
    m = rc.manifest
    versions = {"model": f"{rc.package.package_id}@{rc.package.version}:{rc.package.digest.value[:16]}"}
    if rc.driver_ref is not None:
        versions["driver"] = f"{rc.driver_ref.plugin_id}@{rc.driver_ref.version}"
    env_ref = getattr(getattr(rc.env, "descriptor", None), "ref", None)
    if callable(env_ref):
        r = env_ref()
        versions["environment"] = f"{r.plugin_id}@{r.version}"
    if getattr(m, "rules", None) is not None:
        versions["rules"] = f"{m.rules.ruleset_id}@{m.rules.version}"
    participant = rc.participants.get(actor)
    if participant is not None and participant.view is not None:
        versions["view"] = digest_of(participant.view.model_dump(mode="json")).value[:16]
    if rc.gates:
        versions["gates"] = ",".join(f"{ref.plugin_id}@{ref.version}" for ref, _, _ in rc.gates)
    return versions


def build_context(rc: Any, *, step: int, turn: TurnRef | None, actor: str, record: OperationRecord,
                  proposal: ActionProposal, phase: ExecutionPhase) -> ExecutionContext:
    revision, source, note = authoritative_revision(rc.env, rc.env_caps)
    session_id, service = _session(rc.env, rc.run_id)
    env_ref = rc.manifest.scenario.environment.plugin
    return ExecutionContext(
        run_id=rc.run_id, step=step, turn=turn, actor_id=actor, operation_id=record.operation_id, phase=phase,
        action_type=proposal.action.action_type, action_params_digest=params_digest(dict(proposal.action.params)),
        request_digest=record.request_digest or "", environment=env_ref, session_id=session_id,
        service_identity=service, proposal_revision=proposal.based_on_revision, current_revision=revision,
        revision_source=source, revision_note=note, versions=run_versions(rc, actor), read_at=utcnow())


def identity_problem(context: ExecutionContext, proposal: ActionProposal) -> str | None:
    """A proposal's claimed identity must equal the kernel's; a strategy string is never the authority."""
    if proposal.actor_id != context.actor_id:
        return (f"IDENTITY_MISMATCH: the proposal claims actor {proposal.actor_id!r} but the turn belongs to "
                f"{context.actor_id!r}; nothing is sent")
    if proposal.run_id != context.run_id:
        return f"IDENTITY_MISMATCH: the proposal claims run {proposal.run_id!r}, this is {context.run_id!r}"
    if proposal.step != context.step:
        return f"IDENTITY_MISMATCH: the proposal claims step {proposal.step}, this is step {context.step}"
    return None
