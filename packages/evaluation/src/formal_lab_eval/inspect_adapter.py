"""Inspect (inspect_ai) adapter.

Reused from Inspect: Task / Sample datasets, the solver + scorer pipeline, metric reducers, the eval runner and
the `.eval` log format (plus Inspect's model providers through `InspectModelClient`).
Kept independent: the platform's RunManifest / MetricResult contracts. The solver runs a platform episode with
the shared step engine; the scorer only converts platform MetricResults (computed deterministically from the
simulator truth) into Inspect Scores. `metric_results_from_log` converts back.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from formal_lab_contracts import MetricResult, ModelPackage, RunManifest
from formal_lab_runtime import run_local
from formal_lab_runtime.bundles import bundle_from_local
from inspect_ai import Task
from inspect_ai.dataset import Sample
from inspect_ai.log import EvalLog, read_eval_log
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score, Target, mean, scorer, stderr
from inspect_ai.solver import Generate, TaskState, solver

ManifestFactory = Callable[[dict[str, Any]], tuple[RunManifest, ModelPackage]]
METADATA_KEY = "formal_lab"


def result_to_score(metrics: list[MetricResult], always: list[str], run_id: str, status: str) -> Score:
    """Platform MetricResults → Inspect Score. Metrics without a value stay out of `value` (Inspect reducers need
    numbers) but keep their platform status in `metadata`, so missing never becomes 0."""
    by_id = {m.metric_id: m for m in metrics}
    value = {k: float(by_id[k].value) for k in always if k in by_id and by_id[k].value is not None}
    return Score(
        value=value,
        answer=status,
        explanation=f"run {run_id}: {status}; " + ", ".join(f"{m.metric_id}={m.value if m.value is not None else m.status.value}"
                                                           for m in metrics),
        metadata={"run_id": run_id, "metric_results": [m.model_dump(mode="json") for m in metrics]},
    )


def metric_results_from_log(log: EvalLog) -> dict[str, list[MetricResult]]:
    """Inspect EvalLog → platform MetricResults per sample id (inverse of result_to_score)."""
    out: dict[str, list[MetricResult]] = {}
    for sample in log.samples or []:
        for score in (sample.scores or {}).values():
            data = (score.metadata or {}).get("metric_results")
            if data is not None:
                out[str(sample.id)] = [MetricResult.model_validate(m) for m in data]
    return out


def bundle_paths_from_log(log: EvalLog) -> dict[str, str]:
    return {str(s.id): s.metadata[METADATA_KEY]["bundle"] for s in log.samples or []
            if s.metadata and METADATA_KEY in s.metadata and s.metadata[METADATA_KEY].get("bundle")}


@solver
def platform_episode(factory: ManifestFactory, bundle_dir: str):
    """Run one platform episode per sample and record its manifest, metrics and replay bundle."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        manifest, package = factory(dict(state.metadata))
        t0 = time.perf_counter()
        result = await asyncio.to_thread(run_local, manifest, package)
        path = Path(bundle_dir) / f"{manifest.run_id}.zip"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bundle_from_local(result, package, {"inspect_sample": str(state.sample_id)}))
        state.metadata[METADATA_KEY] = {
            "run_id": manifest.run_id, "status": result.status.value, "reason": result.reason,
            "bundle": str(path), "wall_seconds": round(time.perf_counter() - t0, 3),
            "metrics": [m.model_dump(mode="json") for m in result.metrics],
            "sources": sorted({s.proposal.source.kind.value for s in result.steps if s.proposal}),
        }
        state.output = ModelOutput.from_content("formal-lab/platform", f"{result.status.value}: {result.reason}")
        state.completed = True
        return state

    return solve


def platform_scorer(always: list[str]):
    @scorer(metrics={k: [mean(), stderr()] for k in always})
    def platform_metrics():
        async def score(state: TaskState, target: Target) -> Score:
            info = state.metadata[METADATA_KEY]
            metrics = [MetricResult.model_validate(m) for m in info["metrics"]]
            return result_to_score(metrics, always, info["run_id"], info["status"])

        return score

    return platform_metrics()


def platform_task(samples: list[Sample], factory: ManifestFactory, *, bundle_dir: str, always: list[str],
                  name: str) -> Task:
    return Task(dataset=samples, solver=platform_episode(factory, bundle_dir), scorer=platform_scorer(always),
                name=name, metadata={"formal_lab_contract": "formal-lab-contracts/v1"})


class InspectModelClient:
    """ModelClient backed by Inspect's model providers (e.g. mockllm/model in tests, openai-api/... in use)."""

    is_stub = False

    def __init__(self, model: Any, *, label: str | None = None):
        from inspect_ai.model import get_model

        self._model = get_model(model) if isinstance(model, str) else model
        self.model = label or str(self._model)
        self.is_stub = self.model.startswith("mockllm")

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
                      payload: dict[str, Any]):
        from formal_lab_strategies.model_clients import ModelResponse
        from inspect_ai.model import ChatMessageSystem, ChatMessageUser, GenerateConfig, ResponseSchema
        from inspect_ai.util import JSONSchema

        async def go():
            return await self._model.generate(
                [ChatMessageSystem(content=system), ChatMessageUser(content=user)],
                config=GenerateConfig(response_schema=ResponseSchema(name=schema_name,
                                                                     json_schema=JSONSchema.model_validate(schema))))

        t0 = time.perf_counter()
        out = asyncio.run(go())
        text = out.completion
        usage = out.usage
        return ModelResponse(content=json.loads(text), raw_text=text, model=out.model, call_id=f"inspect-{id(out)}",
                             input_tokens=usage.input_tokens if usage else 0,
                             output_tokens=usage.output_tokens if usage else 0,
                             latency_ms=(time.perf_counter() - t0) * 1000, request={"via": "inspect_ai"})


def read_log(path: str | Path) -> EvalLog:
    return read_eval_log(str(path))
