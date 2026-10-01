"""D6 evidence: the MAL domain goes end-to-end through the platform's public interfaces (phase 3B).

Exercises the one path the Web / API / CLI / SDK all wrap, on the committed fixture (offline, no MAL toolchain):
  import   — a `mal-attack-graph/v1` source envelope is compiled by the registered MODEL_FRONTEND plugin into a package;
  config   — a red-team scenario is built (strategy, horizon, budget);
  run      — the episode runs in ir-world and reaches the target;
  explain  — a bounded query produces a QueryBundle with the witness, its rendered explanation and an independent
             driver replay;
  export   — the bundle (with the model package embedded) is written to disk;
  offline-replay — the exported bundle is re-read and re-verified from itself alone, with the same verdict.

Also confirms the domain plugins are discoverable (so the existing Web model-workbench and CLI see them) and lists the
six D-package deliverables with their evidence files. Writes $FAL_EVIDENCE_DIR/d6-domain-acceptance.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from formal_lab_contracts import CheckQuery, ModelSource
from formal_lab_domain_mal.frontend import MalFrontend, attack_graph_of
from formal_lab_domain_mal.run import run_red_team, run_summary
from formal_lab_runtime import PluginRegistry, default_registry
from formal_lab_runtime.query import replay_query, run_query

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packages" / "domain-mal"
EVDIR = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3")
OUT = EVDIR / "d6-domain-acceptance.json"
BUNDLE = EVDIR / "d6-mal-query-bundle.json"

D_EVIDENCE = {
    "D1": "d1-mal.json", "D2": "d2-broker.json", "D3": "d3-strategies.json",
    "D4": "d4-service-lab.json", "D5": "d5-cage.json", "D6": "d6-domain-acceptance.json",
}


def main() -> int:
    graph = json.loads((PKG / "tests/fixtures/net_app_data.graph.json").read_text())
    native = json.loads((PKG / "tests/fixtures/net_app_data.native.json").read_text())["reachable_case"]
    model = json.loads((PKG / "src/formal_lab_domain_mal/models/net_app_data.json").read_text())
    reg = default_registry()

    # import — through the registered frontend plugin, from a source envelope (the Web/CLI/SDK path)
    envelope = {"language": {"name": "coreLang", "version": "1.0.0"}, "model": model, "graph": graph,
                "entry_points": native["entry"], "goal": native["goal"], "reachable": native["compromised"]}
    frontend = MalFrontend()
    pkg = frontend.compile(ModelSource(format="mal-attack-graph/v1", text=json.dumps(envelope, ensure_ascii=False)),
                           package_id="mal-net-app-data", version=1)
    imported = {"frontend": frontend.descriptor.plugin_id, "package_id": pkg.package_id,
                "semantic_profile": pkg.ir.semantic_profile, "digest": pkg.digest.value[:16]}

    # run — the red-team episode
    episode = run_summary(run_red_team(pkg), attack_graph_of(pkg)["lowering"]["id_map"])

    # explain — a bounded query with witness + rendered explanation + independent driver replay
    bundle = run_query(reg, pkg, CheckQuery(kind="GOAL_REACHABILITY", property_id="target_reached",
                                            bound={"max_steps": 60, "timeout_ms": 30000}))
    explain = {"verdict": str(bundle.result.verdict), "explanation": bundle.explanation,
               "witness_replay": bundle.replay}

    # export — embed the package so the bundle replays offline, write to disk
    exported = bundle.model_copy(update={"package": pkg})
    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    BUNDLE.write_text(exported.model_dump_json(indent=2))

    # offline replay — re-read the bundle from disk and re-verify from itself alone
    from formal_lab_contracts import QueryBundle

    reloaded = QueryBundle.model_validate_json(BUNDLE.read_text())
    replay = replay_query(reg, reloaded.package, reloaded)

    # plugins discoverable (so the Web model-workbench and CLI see the domain)
    disc = PluginRegistry().discover()
    domain_plugins = sorted(e.descriptor.plugin_id for e in disc.entries()
                            if e.descriptor.source in ("formal-lab-domain-mal", "formal-lab-domain-broker"))

    # the six deliverables and their evidence files (D6 is this script's own output, written below)
    deliverables = {d: {"evidence": f, "present": d == "D6" or (EVDIR / f).exists()} for d, f in D_EVIDENCE.items()}

    result = {
        "deliverable": "phase3B-D6",
        "domain_end_to_end": {
            "import": imported, "config": {"strategy": "symbolic", "goal": "target_reached"},
            "run": {"status": episode["status"], "goal_reached": episode["status"] == "SUCCEEDED",
                    "attack_path_len": len(episode["attack_path"])},
            "explain": explain,
            "export": {"bundle_file": str(BUNDLE.relative_to(ROOT)), "embedded_package": True,
                       "bytes": len(BUNDLE.read_text())},
            "offline_replay": replay,
        },
        "surfaces": {
            "sdk_api_runtime": "import/run/query/export/replay exercised above through the public runtime that the "
                               "SDK Client and the platform API wrap",
            "cli": "the CLI replay/query commands wrap run_query/replay_query (same QueryBundle)",
            "web": "the model-workbench discovers MODEL_FRONTEND plugins; the domain frontend is in the registry",
            "domain_plugins_discoverable": domain_plugins, "load_errors": disc.load_errors,
        },
        "deliverables": deliverables,
        "conclusion": {
            "import_run_explain_export_offline_replay": (imported["semantic_profile"] == "deterministic_finite_v1"
                                                         and episode["status"] == "SUCCEEDED"
                                                         and explain["verdict"] == "WITNESS"
                                                         and replay["same"]),
            "all_six_evidence_present": all(v["present"] for v in deliverables.values()),
            "plugins_discoverable_no_errors": not disc.load_errors and len(domain_plugins) >= 4,
            "offline_readable": True,
        },
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"wrote {OUT.relative_to(ROOT)}")
    c = result["conclusion"]
    print(f"  import->run->explain->export->offline-replay: {c['import_run_explain_export_offline_replay']}")
    print(f"  run={episode['status']} explain={explain['verdict']} replay_same={replay['same']} "
          f"witness_replay={bundle.replay.get('witness')}")
    print(f"  domain plugins: {domain_plugins}")
    print(f"  all six evidence present: {c['all_six_evidence_present']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
