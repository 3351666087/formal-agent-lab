"""Real-model integration check (P1-074): runs only when FAL_LLM_API_KEY is configured (pytest -m llm).

Evidence is written to var/evidence/P1-074-llm-integration.json; the phase-1 acceptance check sets
FAL_LLM_EVIDENCE to docs/execution/evidence/P1-074-llm-integration.json, so an ordinary test run never rewrites
the recorded phase-1 evidence.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from formal_lab_contracts import PluginRef
from formal_lab_example_scheduling.scenarios import STRATEGIES, model_package, scenario
from formal_lab_runtime import default_registry, make_manifest, new_run_id, run_local
from formal_lab_runtime.settings import get_setting, llm_configured

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(os.environ.get("FAL_LLM_EVIDENCE") or ROOT / "var" / "evidence" / "P1-074-llm-integration.json")

pytestmark = [pytest.mark.llm,
              pytest.mark.skipif(not llm_configured(), reason="FAL_LLM_API_KEY not configured (NOT_RUN)")]


def test_real_llm_strategy_runs_an_episode():
    pkg, reg = model_package(), default_registry()
    sc = scenario("normal", pkg, seed=1, strategy=STRATEGIES["llm"])
    manifest = make_manifest(run_id=new_run_id(), project_id="integration", scenario=sc, package=pkg, registry=reg,
                             evaluators=[PluginRef(plugin_id="formal-lab.eval.generic", version="1.0.0"),
                                         PluginRef(plugin_id="formal-lab.example.scheduling.scorer", version="1.0.0")],
                             budget={"max_steps": 30, "max_model_calls": 30, "max_tokens": 400_000,
                                     "max_wall_seconds": 900})
    res = run_local(manifest, pkg, reg)
    sources = {s.proposal.source.kind for s in res.steps if s.proposal}
    models = {s.proposal.source.model for s in res.steps if s.proposal}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps({
        "check": "P1-074 real model integration",
        "endpoint": get_setting("FAL_LLM_BASE_URL"),
        "model_configured": get_setting("FAL_LLM_MODEL"),
        "models_reported": sorted(m for m in models if m),
        "run_id": res.manifest.run_id,
        "status": res.status.value,
        "reason": res.reason,
        "usage": res.usage.model_dump(),
        "proposal_sources": sorted(sources),
        "metrics": {m.metric_id: m.value for m in res.metrics},
        "first_rationales": [s.proposal.rationale for s in res.steps[:3] if s.proposal],
        "model_call_ids": [c["call_id"] for c in res.model_calls][:5],
    }, indent=2, ensure_ascii=False) + "\n")
    assert sources == {"LLM"}
    assert res.usage.model_calls >= res.usage.steps >= 1
    assert res.usage.input_tokens > 0
    assert res.status.value in ("SUCCEEDED", "BUDGET_EXHAUSTED", "FAILED")
