"""The child side of the subprocess environment example (phase 4A, A4): a world in its own process.

The parent (`adapter.SubprocessWorldEnvironment`) starts `python -m formal_lab_example_subprocess.world` and talks
JSON lines over stdin / stdout — one request `{"id", "op", "args"}`, one answer `{"id", "ok", "result" | "error"}`, in
order. The child hosts the generic driver world for the pinned model (any semantic profile) and keeps its own count of
world steps: every `step` / `step_batch` that is not a replay of an already applied operation id advances the world by
exactly one step and, with `world_log`, appends `{"world_step", "kind", "operation_id", "actors", ...}` to that file —
the record the platform's batches are compared against. Automatic participants (`automatic`: actor id + actions in
order of preference) act at the end of each world step; `world_step_report` answers the last step and their actions.

Protocol `formal-lab/subprocess-env@1`. `hello` answers the protocol, the backend and what the backend can do
(`load_state`: whether `restore` loads a snapshot; a backend without it is rebuilt by the parent through reset +
replay). The child exits when stdin closes, so it never outlives its parent.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

PROTOCOL = "formal-lab/subprocess-env@1"


class World:
    def __init__(self) -> None:
        self.env: Any = None
        self.package: Any = None
        self.options: dict[str, Any] = {}
        self.report: dict[str, Any] | None = None  # the last world step: index and automatic participants

    # ------------------------------------------------------------------ setup
    def init(self, package: dict[str, Any], world: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
        from formal_lab_contracts import ModelPackage
        from formal_lab_env.driver_world import DriverWorldEnvironment
        from formal_lab_runtime import default_registry
        from formal_lab_runtime.engine import RuntimeServices

        self.package = ModelPackage.model_validate(package)
        reg = default_registry()
        driver = reg.create(reg.driver_for(self.package.semantic_profile).descriptor.ref(), {},
                            RuntimeServices(self.package))
        self.env = DriverWorldEnvironment(world, RuntimeServices(self.package, loaded=driver.load(self.package)))
        self.options = dict(options)
        return {"model": f"{self.package.package_id}@{self.package.version}"}

    def _log(self, kind: str, operation_id: str, actors: list[str], automatic: list[dict[str, Any]]) -> None:
        path = self.options.get("world_log")
        if not path:
            return
        data = self.env._data
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"world_step": data["step"], "kind": kind, "operation_id": operation_id,
                                 "actors": actors, "automatic": [a["actor_id"] for a in automatic
                                                                 if a["status"] == "APPLIED"],
                                 "revision": data["revision"], "run_id": data["run_id"],
                                 "pid": os.getpid(), "at": time.time()}) + "\n")

    def _automatic(self) -> list[dict[str, Any]]:
        """The environment's own automatic participants act at the end of the world step: each applies the first of
        its configured actions whose precondition holds on the state the members left (they are not proposals)."""
        from formal_lab_contracts import GroundAction

        data, done = self.env._data, []
        for auto in self.options.get("automatic") or []:
            for spec in auto.get("actions", []):
                action = GroundAction.model_validate(spec)
                pred = self.env.loaded.predict(data["state"], action)
                if pred.applicable and pred.next_state is not None:
                    data["state"] = pred.next_state
                    data["revision"] += 1
                    for path in pred.written_paths:
                        data["writes"][path] = [data["revision"], auto["actor_id"]]
                    data["history"][-1] = pred.next_state  # the world step ends after the automatic actions
                    done.append({"actor_id": auto["actor_id"], "action": action.model_dump(mode="json"),
                                 "status": "APPLIED", "written_paths": list(pred.written_paths)})
                    break
            else:
                done.append({"actor_id": auto["actor_id"], "action": auto["actions"][0] if auto.get("actions")
                             else {"action_type": "none"}, "status": "REJECTED",
                             "note": "no configured action applicable"})
        return done

    def _stepped(self, kind: str, operation_id: str, actors: list[str], rebuild: bool) -> None:
        automatic = self._automatic()
        self.report = {"world_step": self.env._data["step"], "automatic": automatic, "operation_id": operation_id}
        if not rebuild:  # a rebuild replays recorded steps: not new world steps
            self._log(kind, operation_id, actors, automatic)

    def _applied(self, key: str) -> bool:
        return self.env._data is not None and key in self.env._data["applied_ops"]

    # ------------------------------------------------------------------ operations
    def handle(self, op: str, args: dict[str, Any]) -> Any:
        from formal_lab_contracts import ActionProposal, EnvironmentSnapshot, ScenarioManifest

        if op == "hello":
            from formal_lab_contracts import capabilities as caps
            from formal_lab_env.driver_world import ENV_ID, ENV_VERSION

            return {"protocol": PROTOCOL, "backend": f"{ENV_ID}@{ENV_VERSION}", "pid": os.getpid(),
                    "load_state": bool(args.get("load_state", True)),
                    "batch_semantics": caps.BATCH_START_STATE_DISJOINT_WRITES}
        if op == "init":
            return self.init(args["package"], args.get("world") or {}, args.get("options") or {})
        if self.env is None:
            raise RuntimeError("init first")
        if op == "reset":
            obs = self.env.reset(ScenarioManifest.model_validate(args["scenario"]), self.package,
                                 run_id=args["run_id"], seed=int(args["seed"]))
            return obs.model_dump(mode="json")
        if op == "observe":
            return self.env.observe(args["actor_id"]).model_dump(mode="json")
        if op == "step":
            proposal = ActionProposal.model_validate(args["proposal"])
            replay = self._applied(args["operation_id"])
            out = self.env.step(proposal, operation_id=args["operation_id"])
            if not replay:
                self._stepped("step", args["operation_id"], [proposal.actor_id], bool(args.get("rebuild")))
            return {"outcome": out.model_dump(mode="json"), "world_step": self.env._data["step"], "replayed": replay}
        if op == "step_batch":
            proposals = [ActionProposal.model_validate(p) for p in args["proposals"]]
            replay = self._applied(f"batch:{args['operation_id']}")
            outs = self.env.step_batch(proposals, operation_id=args["operation_id"])
            if not replay:
                self._stepped("batch", args["operation_id"], [p.actor_id for p in proposals], bool(args.get("rebuild")))
            return {"outcomes": [o.model_dump(mode="json") for o in outs], "world_step": self.env._data["step"],
                    "replayed": replay}
        if op == "query_operation":
            data = self.env._data
            found = data["applied_ops"].get(args["operation_id"]) if data else None
            return found if isinstance(found, dict) else None
        if op == "snapshot":
            return self.env.snapshot().model_dump(mode="json")
        if op == "restore":
            if not self.options.get("load_state", True):
                raise NotImplementedError("this backend cannot load a state (rebuild by reset + replay)")
            self.env.restore(EnvironmentSnapshot.model_validate(args["snapshot"]))
            return {"world_step": self.env._data["step"]}
        if op == "world_step_report":
            return self.report or {"world_step": self.env._data["step"] if self.env._data else 0, "automatic": []}
        if op == "truth_state":
            return self.env.truth_state()
        if op == "truth_properties":
            return self.env.truth_properties()
        if op == "sleep":  # for timeout tests
            time.sleep(float(args.get("seconds", 0)))
            return {"slept": args.get("seconds")}
        raise ValueError(f"unknown operation {op!r}")


def main() -> int:
    world = World()
    for line in sys.stdin:  # EOF (parent gone or closed us) ends the loop
        if not line.strip():
            continue
        req = json.loads(line)
        if req.get("op") == "close":
            print(json.dumps({"id": req.get("id"), "ok": True, "result": "closed"}), flush=True)
            break
        try:
            answer = {"id": req.get("id"), "ok": True, "result": world.handle(req["op"], req.get("args") or {})}
        except Exception as exc:  # every failure goes back to the parent, typed by its class
            answer = {"id": req.get("id"), "ok": False,
                      "error": {"type": type(exc).__name__, "message": str(exc)[:2000],
                                "code": getattr(getattr(exc, "code", None), "value", None)}}
        print(json.dumps(answer, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
