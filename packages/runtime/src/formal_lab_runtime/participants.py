"""Per-participant planner input (phase 3A, G4).

A participant's `ParticipantView` decides what its planner receives; everything a planner gets passes through one
`ParticipantInput`:

- the observation (turn start, round start, answers to observation requests): facts and unknown items of withheld
  locations are removed, so the participant's belief treats them as never observed (ASSUMED_INITIAL);
- observation requests: withheld locations are not served (the refusal is on the record);
- `last_outcome`: field differences on withheld locations are dropped from the effect comparison it carries;
- settings: `ParticipantServices.get_setting` reads the participant's own settings before the platform's.

The kernel keeps working on the full observation (precondition checks, predictions, effect comparison) — the view
restricts the planner, not the platform. Planner checkpoints only ever contain what the planner saw, so a restored
planner continues on the same input. Without a view nothing is filtered and the input is the phase-2 one.

Phase 4A (A2) widens the same rule to everything that reaches a participant: `project()` removes withheld
locations from any payload — keys that are withheld locations, items carrying a withheld `path`, withheld entries of
path lists — and redacts withheld locations named in free text (a gate's reason, an error message), so
`last_outcome` (result, conflict, error) and the participant's download carry exactly what its view allows. The
operator's evidence stays complete. `ParticipantServices.get_setting` never hands out an environment write
credential or a signing key. In-process plugins are trusted Python code, not a sandbox: the enforced boundary for
writes is the environment's own process (e.g. the order service refuses writes without its credential).
"""

from __future__ import annotations

import copy
import fnmatch
import re
from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ModelPackage,
    Observation,
    Participant,
    ParticipantView,
    digest_of,
)


def _family(path: str) -> str:
    return path.split("[", 1)[0]


def _hit(path: str, patterns: list[str]) -> bool:
    return any(path == p or _family(path) == p for p in patterns)


WITHHELD = "⟨withheld⟩"
_LOCATION = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)(\[[^\]\s]*\])?")
_VALUE_AFTER = re.compile(r"^\s*(?:==|=|:|<=|>=|<|>|≥|≤)\s*[^\s,;)]+")
PATH_LIST_KEYS = ("paths", "changed_paths", "written_paths", "requested_paths", "free_paths", "unknown_paths",
                  "withheld", "compared_paths")
# environment write credentials and signing keys: never handed to a participant's planner
SECRET_SETTINGS = ("*WRITE_TOKEN*", "*TOKEN_FILE*", "*SIGNING*", "*KEYSTORE*", "*_SECRET*", "*PASSWORD*",
                   "FAL_PARTICIPANT_TOKEN_KEY", "ORDERS_*", "FAL_ENV_*")


class Projection:
    """The one projection rule of a participant's view, applicable to any payload (phase 4A, A2)."""

    def __init__(self, view: ParticipantView | None, families: set[str] | None = None):
        self.view = view
        self.families = families or set()

    @property
    def filtered(self) -> bool:
        return self.view is not None and bool(self.view.include or self.view.exclude)

    def allows(self, path: str) -> bool:
        if not self.filtered:
            return True
        assert self.view is not None
        if self.view.include and not _hit(path, self.view.include):
            return False
        return not _hit(path, self.view.exclude)

    def _is_location(self, token: str) -> bool:
        return "[" in token or _family(token) in self.families

    def text(self, value: str) -> str:
        """Withheld locations named in free text are replaced (with the value written right after them)."""
        if not self.filtered or not value:
            return value
        out, i = [], 0
        for m in _LOCATION.finditer(value):
            token = m.group(0)
            if not self._is_location(token) or self.allows(token):
                continue
            out.append(value[i:m.start()] + WITHHELD)
            i = m.end()
            after = _VALUE_AFTER.match(value[i:])
            if after:
                i += after.end()
        return "".join(out) + value[i:] if out else value

    def value(self, obj: Any) -> Any:
        """Deep projection of a payload (dicts, lists, strings; other scalars unchanged)."""
        if not self.filtered:
            return obj
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if isinstance(k, str) and self._is_location(k) and not self.allows(k):
                    continue
                if k in PATH_LIST_KEYS and isinstance(v, list):
                    out[k] = [x for x in v if not (isinstance(x, str) and not self.allows(x))]
                elif k == "path" and isinstance(v, str) and not self.allows(v):
                    out[k] = WITHHELD
                else:
                    out[k] = self.value(v)
            return out
        if isinstance(obj, list):
            return [self.value(x) for x in obj
                    if not (isinstance(x, dict) and isinstance(x.get("path"), str) and not self.allows(x["path"]))]
        if isinstance(obj, str):
            return self.text(obj)
        return obj


ENVIRONMENT = "⟨environment⟩"
_URL = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\"'<>]+", re.IGNORECASE)


def _config_strings(obj: Any) -> set[str]:
    """Addresses and file paths in a configuration (endpoint, credential file, keystore, receipts store)."""
    if isinstance(obj, dict):
        return set().union(*(_config_strings(v) for v in obj.values())) if obj else set()
    if isinstance(obj, list):
        return set().union(*(_config_strings(v) for v in obj)) if obj else set()
    if isinstance(obj, str) and ("://" in obj or (obj.startswith("/") and len(obj) > 3)):
        return {obj}
    return set()


def _scrub(obj: Any, literals: list[str]) -> Any:
    """Environment addresses and configured paths replaced in every string of a payload."""
    if isinstance(obj, dict):
        return {k: _scrub(v, literals) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v, literals) for v in obj]
    if isinstance(obj, str):
        for lit in literals:
            if lit in obj:
                obj = obj.replace(lit, ENVIRONMENT)
        return _URL.sub(ENVIRONMENT, obj)
    return obj


def secret_setting(key: str) -> bool:
    return any(fnmatch.fnmatchcase(key.upper(), pat) for pat in SECRET_SETTINGS)


class ParticipantInput:
    """Filters what one participant's planner receives (see module docstring)."""

    def __init__(self, participant: Participant, families: set[str] | None = None):
        self.participant = participant
        self.view: ParticipantView | None = participant.view
        self.projection = Projection(self.view, families)

    @property
    def filtered(self) -> bool:
        return self.view is not None and bool(self.view.include or self.view.exclude)

    def allows(self, path: str) -> bool:
        if not self.filtered:
            return True
        assert self.view is not None
        if self.view.include and not _hit(path, self.view.include):
            return False
        return not _hit(path, self.view.exclude)

    def observation(self, obs: Observation) -> tuple[Observation, list[str]]:
        """The planner's observation and the withheld locations (sorted)."""
        if not self.filtered:
            return obs, []
        withheld = sorted({f.path for f in obs.facts if not self.allows(f.path)}
                          | {u.path for u in obs.unknowns if not self.allows(u.path)})
        if not withheld:
            return obs, []
        return obs.model_copy(update={
            "facts": [f for f in obs.facts if self.allows(f.path)],
            "unknowns": [u for u in obs.unknowns if self.allows(u.path)],
            "requested_paths": [p for p in obs.requested_paths if self.allows(p)],
        }), withheld

    def request(self, paths: list[str]) -> tuple[list[str], list[str]]:
        """(served, declined) locations of an observation request."""
        return [p for p in paths if self.allows(p)], [p for p in paths if not self.allows(p)]

    def outcome(self, data: dict[str, Any] | None) -> ActionOutcome | None:
        """The previous outcome as this participant may see it: effect differences, written values, conflict paths
        and every reason / error text are projected through the view."""
        if data is None:
            return None
        outcome = ActionOutcome.model_validate(data)
        if not self.filtered:
            return outcome
        projected = ActionOutcome.model_validate(self.projection.value(outcome.model_dump(mode="json")))
        cmp = projected.effect_comparison
        if cmp is not None:
            counts: dict[str, int] = {}
            for d in cmp.diffs:
                counts[d.evidence] = counts.get(d.evidence, 0) + 1
            projected = projected.model_copy(update={"effect_comparison": cmp.model_copy(update={
                "evidence_counts": counts})})
        return projected

    def digest(self, obs: Observation) -> str:
        """Digest of what the planner receives (turn, request and evidence metadata excluded): equal inputs → equal
        digests, before and after a recovery."""
        return digest_of({"actor_id": obs.actor_id, "revision": obs.state_revision,
                          "facts": sorted(((f.path, f.value, f.observed_at_step) for f in obs.facts),
                                          key=lambda x: x[0]),
                          "unknowns": sorted((u.path, u.reason) for u in obs.unknowns)}).value


class ParticipantServices:
    """PluginServices for one participant's planner: the run's services, with the participant's own settings read
    first. `participant()` tells the planner who it plans for."""

    def __init__(self, base: Any, participant: Participant):
        self._base = base
        self._participant = participant

    def pinned_model(self) -> ModelPackage:
        return self._base.pinned_model()

    def get_model(self, ref) -> ModelPackage:
        return self._base.get_model(ref)

    def loaded_model(self) -> Any:
        return self._base.loaded_model()

    refused_settings: list[str]

    def get_setting(self, key: str) -> str | None:
        """The participant's own setting first, then the platform's — never an environment write credential or a
        signing key (those belong to the environment / broker, not to the read / propose channel)."""
        if secret_setting(key):
            self.refused_settings = [*getattr(self, "refused_settings", []), key]
            return None
        own = self._participant.view.settings if self._participant.view else {}
        return own[key] if key in own else self._base.get_setting(key)

    def participant(self) -> Participant:
        return self._participant

    @property
    def actor_id(self) -> str:
        return self._participant.actor_id


def participant_bundle(bundle: Any, actor_id: str) -> Any:
    """The replay bundle one participant may download (phase 4A, A2): its own turns and the run-level events, every
    payload projected through its view; the environment's and the gates' configuration (endpoints, credential file
    paths, truth overrides), every environment address or configured path named in a payload, and the other
    participants' strategy configuration and views are removed. Metrics and
    artifacts are operator evidence and are not included. The operator's own export stays complete."""
    from formal_lab_contracts import OperationRecord, TraceEvent
    from formal_lab_contracts.bundle import ReplayBundle
    from formal_lab_contracts.errors import NotFound

    m = bundle.manifest
    me = next((p for p in m.participants if p.actor_id == actor_id), None)
    if me is None:
        raise NotFound(f"{actor_id!r} is not a participant of run {m.run_id}")
    families: set[str] = set()
    if getattr(bundle.package, "is_ir", False):
        families = {s.name for s in bundle.package.ir.state}
    proj = Projection(me.view, families)

    def other(p: Participant) -> Participant:
        return p if p.actor_id == actor_id else p.model_copy(update={
            "view": None, "strategy": p.strategy.model_copy(update={"config": {}})})

    scenario = m.scenario.model_copy(update={
        "environment": m.scenario.environment.model_copy(update={"config": {}}),
        "execution_gates": [g.model_copy(update={"config": {}}) for g in m.scenario.execution_gates],
        "participants": [other(p) for p in m.scenario.participants]})
    manifest = m.model_copy(update={"scenario": scenario, "participants": [other(p) for p in m.participants]})
    # how to reach the environment (endpoints, credential / keystore / receipt paths) is not the participant's
    literals = sorted(_config_strings([m.scenario.environment.config, *[g.config for g in m.scenario.execution_gates]]),
                      key=len, reverse=True)
    # the participant's events are renumbered 1..n and keep only links to events it can see, so the download is a
    # valid bundle for the same offline reader (contiguous sequence, causal parents precede)
    events: list[Any] = []
    kept: set[str] = set()
    for e in sorted(bundle.events, key=lambda x: x.seq):
        if e.actor_id not in (None, actor_id):
            continue
        payload = _scrub(copy.deepcopy(proj.value(e.payload)), literals)  # never alias the operator's payload
        if "manifest" in payload:  # RUN_CREATED carries the full manifest: replace it by the participant's
            payload["manifest"] = manifest.model_dump(mode="json")
        events.append(TraceEvent.model_validate({**e.model_dump(mode="json"), "payload": payload,
                                                 "seq": len(events) + 1,
                                                 "causal_parents": [x for x in e.causal_parents if x in kept]}))
        kept.add(e.event_id)
    operations = [OperationRecord.model_validate(_scrub(proj.value(op.model_dump(mode="json")), literals))
                  for op in bundle.operations if op.actor_id == actor_id]
    info = {**{k: v for k, v in (bundle.info or {}).items() if k in ("format", "contract_version")},
            "participant": actor_id, "projection": "phase-4A participant view",
            "renumbered": "events renumbered 1..n; links to events outside the participant's scope removed",
            "view": me.view.model_dump(mode="json") if me.view else None}
    return ReplayBundle(manifest=manifest, events=events, package=bundle.package, metrics=[], artifacts={},
                        info=info, operations=operations)
