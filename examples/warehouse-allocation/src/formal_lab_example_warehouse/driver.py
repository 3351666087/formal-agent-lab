"""Semantic driver for `warehouse_alloc_v1` — an independent implementation (no neutral IR anywhere).

The run kernel reaches this model only through the `SemanticDriver` / `LoadedModel` interfaces: candidates,
predictions, properties, belief and display all come from here (P2-012). Applicability with unknown locations is
decided by enumerating the completions of the locations an action reads (bounded; beyond the limit → UNKNOWN),
because the bounded verifier of the platform speaks only the neutral IR (its checks answer UNSUPPORTED here).

Actions
    putaway(inbound, zone)      dock[inbound] > 0 and the zone has room for all of it → move it into stock
    assign(station, zone)       the station does not serve the zone and no other station does → serve it
    release(station)            the station serves a zone → serve none
    pick(order, line, zone)     line open, zone served by a station, enough stock → take it; the order completes
                                (done_at = clock + 1) when its last line is picked
    tick()                      clock < horizon → clock + 1
Properties
    all_picked (goal), docks_clear (goal), capacity_ok (invariant), on_time (invariant)
"""

from __future__ import annotations

import itertools
from functools import lru_cache
from typing import Any

from formal_lab_contracts import (
    ActionSpec,
    BeliefState,
    CandidateAction,
    GroundAction,
    ModelPackage,
    Observation,
    ObservationRequest,
    PluginDescriptor,
    PreconditionVerdict,
    StateScalar,
    digest_of,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import InvalidInput
from formal_lab_contracts.interfaces import PartialChecker, Prediction
from formal_lab_model.belief import belief_state_from
from pydantic import ValidationError

from .model import NAMESPACE, PROFILE, SCHEMA_ID, WarehouseModel, json_schema

DRIVER_ID = "formal-lab.example.warehouse.driver"
MAX_COMPLETIONS = 4096

DESCRIPTOR = PluginDescriptor(
    plugin_id=DRIVER_ID,
    version="1.0.0",
    interface="SEMANTIC_DRIVER",
    capabilities=[{"id": f"profile.{PROFILE}"}, {"id": caps.DRIVER_CANDIDATES}, {"id": caps.DRIVER_PREDICT},
                  {"id": caps.DRIVER_PROPERTIES}, {"id": caps.DRIVER_BELIEF}, {"id": caps.DRIVER_DISPLAY},
                  {"id": caps.DRIVER_STATS}],
    semantic_profiles=[PROFILE],
    input_schema=json_schema(),
    config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    entrypoint="formal_lab_example_warehouse.driver:create",
    ui={"label": "仓储分配语义", "category": "semantic_driver",
        "description": "warehouse_alloc_v1: put-away into capacity-bounded zones, pick-station assignment, "
                       "order picking (independent Python semantics)",
        "action_labels": {"putaway": "上架", "assign": "分配工位", "release": "释放工位", "pick": "拣选",
                          "tick": "推进时间"},
        "state_labels": {"dock": "月台待上架", "stock": "库存", "serves": "工位服务区", "picked": "已拣行",
                         "done_at": "订单完成时刻", "clock": "逻辑时间"},
        "action_display": {"putaway": "上架 {inbound} → {zone}", "assign": "工位 {station} → {zone}",
                           "release": "释放 {station}", "pick": "拣选 {order}#{line} @ {zone}", "tick": "推进时间"}},
    license="Apache-2.0",
    source="formal-lab-example-warehouse",
)

ACTION_SPECS = {
    "putaway": ("上架", ["dock[inbound] > 0", "free capacity of zone ≥ dock[inbound]"],
                ["stock[zone, sku(inbound)] += dock[inbound]", "dock[inbound] := 0"], "RECONCILE_THEN_RETRY"),
    "assign": ("分配工位", ["serves[station] ≠ zone", "no other station serves zone"], ["serves[station] := zone"],
               "IDEMPOTENT"),
    "release": ("释放工位", ["serves[station] ≠ none"], ["serves[station] := none"], "IDEMPOTENT"),
    "pick": ("拣选", ["not picked[order, line]", "a station serves zone", "stock[zone, sku] ≥ qty"],
             ["stock[zone, sku] -= qty", "picked[order, line] := true", "done_at[order] := clock + 1 when complete"],
             "RECONCILE_THEN_RETRY"),
    "tick": ("推进时间", ["clock < horizon"], ["clock := clock + 1"], "IDEMPOTENT"),
}


def parse_payload(package: ModelPackage) -> WarehouseModel:
    if package.payload.kind != "namespaced" or package.payload.namespace != NAMESPACE:
        raise InvalidInput(f"{DRIVER_ID} reads {NAMESPACE} payloads")
    if package.payload.schema_id != SCHEMA_ID:
        raise InvalidInput(f"unsupported warehouse schema {package.payload.schema_id!r} (expected {SCHEMA_ID})")
    try:
        return WarehouseModel.model_validate(package.payload.data)
    except ValidationError as exc:
        raise InvalidInput("warehouse model does not match its schema",
                           details={"errors": [f"{'/'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]}
                           ) from exc


class WarehouseLoaded:
    def __init__(self, package: ModelPackage, model: WarehouseModel):
        self.package = package
        self.m = model
        self.zones = [z.id for z in model.zones]
        self.capacity = {z.id: z.capacity for z in model.zones}
        self.inbound = {i.id: i for i in model.inbound}
        self.orders = {o.id: o for o in model.orders}
        self.skus = list(model.skus)

    # ------------------------------------------------------------------ state space
    def initial_state(self) -> dict[str, StateScalar]:
        s: dict[str, StateScalar] = {"clock": 0}
        for i in self.m.inbound:
            s[f"dock[{i.id}]"] = i.qty
        for z in self.zones:
            for k in self.skus:
                s[f"stock[{z},{k}]"] = 0
        for cell in self.m.initial_stock:
            s[f"stock[{cell.zone},{cell.sku}]"] = cell.qty
        for st in self.m.stations:
            s[f"serves[{st.id}]"] = "none"
        for o in self.m.orders:
            for n in range(len(o.lines)):
                s[f"picked[{o.id},{n}]"] = False
            s[f"done_at[{o.id}]"] = 0
        return s

    def state_paths(self) -> list[str]:
        return sorted(self.initial_state())

    def domain(self, path: str) -> list[StateScalar]:
        fam, _, rest = path.partition("[")
        args = rest.rstrip("]").split(",") if rest else []
        if fam == "dock":
            return list(range(self.inbound[args[0]].qty + 1))
        if fam == "stock":
            return list(range(self.capacity[args[0]] + 1))
        if fam == "serves":
            return ["none", *self.zones]
        if fam == "picked":
            return [False, True]
        return list(range(self.m.horizon + 2))  # done_at, clock

    # ------------------------------------------------------------------ actions
    def stats(self) -> dict[str, int]:
        """Sizes for release records (capability driver.stats)."""
        return {"ground_actions": len(self.ground_actions()), "state_locations": len(self.state_paths())}

    def ground_actions(self, scope: Any = None) -> list[GroundAction]:
        acts = [GroundAction(action_type="putaway", params={"inbound": i, "zone": z})
                for i in self.inbound for z in self.zones]
        acts += [GroundAction(action_type="assign", params={"station": st.id, "zone": z})
                 for st in self.m.stations for z in self.zones]
        acts += [GroundAction(action_type="release", params={"station": st.id}) for st in self.m.stations]
        acts += [GroundAction(action_type="pick", params={"order": o.id, "line": n, "zone": z})
                 for o in self.m.orders for n in range(len(o.lines)) for z in self.zones]
        acts.append(GroundAction(action_type="tick", params={}))
        if scope is None:
            return acts
        out = []
        for a in acts:
            if scope.action_types and a.action_type not in scope.action_types:
                continue
            if any(k in a.params and a.params[k] not in allowed for k, allowed in scope.params.items()):
                continue
            out.append(a)
        return out

    def action_specs(self) -> list[ActionSpec]:
        props = {"putaway": {"inbound": {"type": "string", "enum": list(self.inbound)},
                             "zone": {"type": "string", "enum": self.zones}},
                 "assign": {"station": {"type": "string", "enum": [s.id for s in self.m.stations]},
                            "zone": {"type": "string", "enum": self.zones}},
                 "release": {"station": {"type": "string", "enum": [s.id for s in self.m.stations]}},
                 "pick": {"order": {"type": "string", "enum": list(self.orders)},
                          "line": {"type": "integer", "minimum": 0, "maximum": 9},
                          "zone": {"type": "string", "enum": self.zones}},
                 "tick": {}}
        return [ActionSpec(action_type=t, label=lab, preconditions=pre, expected_effects=eff, retry=retry,
                           cost=float(self.m.station_cost) if t == "assign" else 1.0,
                           params_schema={"type": "object", "properties": props[t], "required": list(props[t]),
                                          "additionalProperties": False})
                for t, (lab, pre, eff, retry) in ACTION_SPECS.items()]

    def _check(self, action: GroundAction) -> None:
        if action not in self.ground_actions():
            raise InvalidInput(f"not a ground action of this model: {action.action_type}{action.params}")

    def reads(self, action: GroundAction) -> set[str]:
        """Locations the action's applicability depends on (conflict arbitration, completion enumeration)."""
        p, t = action.params, action.action_type
        if t == "putaway":
            return {f"dock[{p['inbound']}]"} | {f"stock[{p['zone']},{k}]" for k in self.skus}
        if t == "assign":
            return {f"serves[{s.id}]" for s in self.m.stations}
        if t == "release":
            return {f"serves[{p['station']}]"}
        if t == "pick":
            sku = self.orders[p["order"]].lines[int(p["line"])].sku
            return {f"picked[{p['order']},{p['line']}]", f"stock[{p['zone']},{sku}]"} | \
                {f"serves[{s.id}]" for s in self.m.stations}
        return {"clock"}

    def _applicable(self, s: dict[str, StateScalar], action: GroundAction) -> str | None:
        """None when applicable, else the reason."""
        p, t = action.params, action.action_type
        if t == "putaway":
            qty = int(s[f"dock[{p['inbound']}]"])
            if qty <= 0:
                return "NOTHING_AT_DOCK"
            used = sum(int(s[f"stock[{p['zone']},{k}]"]) for k in self.skus)
            if used + qty > self.capacity[p["zone"]]:
                return f"ZONE_FULL: {p['zone']} holds {used}/{self.capacity[p['zone']]}, needs {qty}"
            return None
        if t == "assign":
            if s[f"serves[{p['station']}]"] == p["zone"]:
                return "ALREADY_SERVING"
            if any(s[f"serves[{st.id}]"] == p["zone"] for st in self.m.stations if st.id != p["station"]):
                return f"ZONE_TAKEN: another station serves {p['zone']}"
            return None
        if t == "release":
            return None if s[f"serves[{p['station']}]"] != "none" else "NOT_SERVING"
        if t == "pick":
            n = int(p["line"])
            order = self.orders[p["order"]]
            if n >= len(order.lines):
                return "NO_SUCH_LINE"
            if s[f"picked[{p['order']},{n}]"]:
                return "ALREADY_PICKED"
            if not any(s[f"serves[{st.id}]"] == p["zone"] for st in self.m.stations):
                return f"NO_STATION: no station serves {p['zone']}"
            line = order.lines[n]
            held = int(s[f"stock[{p['zone']},{line.sku}]"])
            if held < line.qty:
                return f"SHORT: {p['zone']} holds {held} of {line.sku}, needs {line.qty}"
            return None
        if t == "tick":
            return None if int(s["clock"]) < self.m.horizon else "HORIZON"
        return "UNKNOWN_ACTION"

    def predict(self, state: dict[str, StateScalar], action: GroundAction) -> Prediction:
        try:
            self._check(action)
        except InvalidInput as exc:
            return Prediction(applicable=False, reason=f"INVALID_ACTION: {exc.message}", next_state=None)
        reason = self._applicable(state, action)
        if reason is not None:
            return Prediction(applicable=False, reason=reason, next_state=None)
        s = dict(state)
        p, t = action.params, action.action_type
        written: list[str] = []
        if t == "putaway":
            sku = self.inbound[p["inbound"]].sku
            key = f"stock[{p['zone']},{sku}]"
            s[key] = int(s[key]) + int(s[f"dock[{p['inbound']}]"])
            s[f"dock[{p['inbound']}]"] = 0
            written = [f"dock[{p['inbound']}]", key]
        elif t == "assign":
            s[f"serves[{p['station']}]"] = p["zone"]
            written = [f"serves[{p['station']}]"]
        elif t == "release":
            s[f"serves[{p['station']}]"] = "none"
            written = [f"serves[{p['station']}]"]
        elif t == "pick":
            order = self.orders[p["order"]]
            line = order.lines[int(p["line"])]
            key = f"stock[{p['zone']},{line.sku}]"
            s[key] = int(s[key]) - line.qty
            s[f"picked[{order.id},{p['line']}]"] = True
            written = [key, f"picked[{order.id},{p['line']}]"]
            if all(s[f"picked[{order.id},{n}]"] for n in range(len(order.lines))):
                s[f"done_at[{order.id}]"] = int(s["clock"]) + 1
                written.append(f"done_at[{order.id}]")
        elif t == "tick":
            s["clock"] = int(s["clock"]) + 1
            written = ["clock"]
        return Prediction(applicable=True, reason=None, next_state=s, written_paths=sorted(written))

    # ------------------------------------------------------------------ properties
    def properties(self, state: dict[str, StateScalar]) -> dict[str, bool]:
        clock = int(state["clock"])
        return {
            "all_picked": all(state[f"picked[{o.id},{n}]"] for o in self.m.orders for n in range(len(o.lines))),
            "docks_clear": all(int(state[f"dock[{i}]"]) == 0 for i in self.inbound),
            "capacity_ok": all(sum(int(state[f"stock[{z},{k}]"]) for k in self.skus) <= self.capacity[z]
                               for z in self.zones),
            "on_time": all(clock <= o.due or int(state[f"done_at[{o.id}]"]) > 0 for o in self.m.orders),
        }

    def property_kinds(self) -> dict[str, str]:
        return {"all_picked": "goal", "docks_clear": "goal", "capacity_ok": "invariant", "on_time": "invariant"}

    # ------------------------------------------------------------------ belief / candidates
    def belief(self, observation: Observation) -> BeliefState:
        return belief_state_from(observation, self.initial_state())

    def candidates(self, belief: BeliefState, *, scope: Any = None, partial_checker: PartialChecker | None = None
                   ) -> list[CandidateAction]:
        """Applicability over all completions of the free locations the action reads (own enumeration; the IR
        verifier's partial checker does not apply to this profile)."""
        free = set(belief.free_paths)
        labels = {t: v[0] for t, v in ACTION_SPECS.items()}
        out = []
        for action in self.ground_actions(scope):
            relevant = sorted(self.reads(action) & free)
            if not relevant:
                reason = self._applicable(belief.state, action)
                verdict = PreconditionVerdict.APPLICABLE if reason is None else PreconditionVerdict.INAPPLICABLE
                out.append(CandidateAction(action=action, label=labels[action.action_type],
                                           belief_applicability=verdict, reason=reason))
                continue
            verdict, request = self._over_completions(belief.state, action, relevant)
            out.append(CandidateAction(action=action, label=labels[action.action_type], belief_applicability=verdict,
                                       observation_request=request))
        return out

    def _over_completions(self, state, action, relevant):
        domains = [self.domain(p) for p in relevant]
        total = 1
        for d in domains:
            total *= len(d)
        if total > MAX_COMPLETIONS:
            return PreconditionVerdict.UNKNOWN, ObservationRequest(
                paths=relevant, for_action=_key(action),
                reason=f"{total} completions exceed the enumeration limit {MAX_COMPLETIONS}")
        yes = no = None
        for combo in itertools.product(*domains):
            s = dict(state)
            s.update(zip(relevant, combo, strict=True))
            ok = self._applicable(s, action) is None
            if ok and yes is None:
                yes = dict(zip(relevant, combo, strict=True))
            if not ok and no is None:
                no = dict(zip(relevant, combo, strict=True))
            if yes is not None and no is not None:
                differing = [p for p in relevant if yes[p] != no[p]]
                return PreconditionVerdict.UNKNOWN, ObservationRequest(
                    paths=differing or relevant, for_action=_key(action),
                    reason="applicability depends on unknown locations", applicable_completion=yes,
                    inapplicable_completion=no)
        return (PreconditionVerdict.APPLICABLE if no is None else PreconditionVerdict.INAPPLICABLE), None

    def display(self) -> dict[str, Any]:
        return {"kind": PROFILE, "name": self.m.name, "zones": [z.model_dump() for z in self.m.zones],
                "stations": [s.model_dump() for s in self.m.stations], "skus": self.skus,
                "inbound": [i.model_dump() for i in self.m.inbound], "orders": [o.model_dump() for o in self.m.orders],
                "horizon": self.m.horizon, "ground_actions": len(self.ground_actions()),
                "locations": len(self.state_paths()), "properties": self.property_kinds()}


def _key(action: GroundAction) -> str:
    return f"{action.action_type}({', '.join(f'{k}={v}' for k, v in action.params.items())})"


@lru_cache(maxsize=32)
def _parsed(digest: str, data_json: str) -> WarehouseModel:
    return WarehouseModel.model_validate_json(data_json)


class WarehouseDriver:
    descriptor = DESCRIPTOR

    def validate(self, package: ModelPackage) -> list[str]:
        if package.semantic_profile != PROFILE:
            return [f"{DRIVER_ID} handles {PROFILE}, not {package.semantic_profile}"]
        try:
            parse_payload(package)
        except InvalidInput as exc:
            return [exc.message, *exc.details.get("errors", [])]
        body = {"namespace": package.payload.namespace, "schema_id": package.payload.schema_id,
                "data": package.payload.data}
        if digest_of(body) != package.digest:
            return ["package digest does not match its payload"]
        return []

    def load(self, package: ModelPackage) -> WarehouseLoaded:
        problems = self.validate(package)
        if problems:
            raise InvalidInput(f"warehouse model {package.package_id}@{package.version} cannot be loaded",
                               details={"problems": problems})
        import json

        model = _parsed(package.digest.value, json.dumps(package.payload.data, sort_keys=True))
        return WarehouseLoaded(package, model)


def create(config: dict[str, Any] | None = None, services: Any = None) -> WarehouseDriver:
    return WarehouseDriver()
