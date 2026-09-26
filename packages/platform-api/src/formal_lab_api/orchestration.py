"""Client side of the Temporal orchestration (used by the API and the SDK-facing services)."""

from __future__ import annotations

import asyncio
from typing import Any

from formal_lab_contracts.errors import RetryableFailure
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.service import RPCError

from .settings import Settings, get_settings

WORKFLOW_NAME = "ExperimentWorkflow"


class TemporalOrchestrator:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    async def client(self) -> Client:
        async with self._lock:
            if self._client is None:
                try:
                    self._client = await asyncio.wait_for(
                        Client.connect(self.settings.temporal_address, namespace=self.settings.temporal_namespace),
                        timeout=5)
                except Exception as exc:
                    raise RetryableFailure(f"Temporal is unreachable at {self.settings.temporal_address}: {exc}") from exc
            return self._client

    async def start(self, run_id: str, workflow_id: str) -> str:
        client = await self.client()
        try:
            handle = await client.start_workflow(
                WORKFLOW_NAME, {"run_id": run_id}, id=workflow_id, task_queue=self.settings.temporal_task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            )
        except RPCError as exc:
            raise RetryableFailure(f"could not start workflow {workflow_id}: {exc}") from exc
        return handle.id

    async def signal(self, workflow_id: str, name: str) -> None:
        client = await self.client()
        await client.get_workflow_handle(workflow_id).signal(name)

    async def cancel(self, workflow_id: str) -> None:
        client = await self.client()
        await client.get_workflow_handle(workflow_id).cancel()

    async def describe(self, workflow_id: str) -> dict[str, Any]:
        client = await self.client()
        handle = client.get_workflow_handle(workflow_id)
        try:
            desc = await handle.describe()
        except RPCError as exc:
            return {"workflow_id": workflow_id, "found": False, "error": str(exc)}
        state: Any = None
        if desc.status == WorkflowExecutionStatus.RUNNING:
            try:
                state = await asyncio.wait_for(handle.query("state"), timeout=3)
            except Exception as exc:  # query needs a live worker
                state = {"query_error": str(exc)}
        return {"workflow_id": workflow_id, "found": True, "status": desc.status.name if desc.status else None,
                "run_id": desc.run_id, "history_length": desc.history_length, "task_queue": desc.task_queue,
                "start_time": desc.start_time, "close_time": desc.close_time, "state": state}

    async def health(self) -> dict[str, Any]:
        try:
            client = await self.client()
            await asyncio.wait_for(client.service_client.check_health(), timeout=3)
            return {"ok": True, "address": self.settings.temporal_address}
        except Exception as exc:
            return {"ok": False, "address": self.settings.temporal_address, "error": str(exc)}
