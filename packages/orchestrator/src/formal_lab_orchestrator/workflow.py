"""ExperimentWorkflow: durable, replayable orchestration of one run.

The workflow only sequences activities and reacts to signals; all I/O (database, object store, model
calls, solver, simulator) happens in activities. Pause takes effect at logical-step boundaries; cancel
is delivered as workflow cancellation and finalises the run with status CANCELLED.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError
from temporalio.workflow import ActivityCancellationType

NON_RETRYABLE = ["INVALID_INPUT", "VERSION_MISMATCH", "UNSUPPORTED", "NOT_FOUND", "CONFLICT",
                 "NON_RETRYABLE_FAILURE", "CANCELLED"]
RETRY = RetryPolicy(initial_interval=timedelta(seconds=1), backoff_coefficient=2.0,
                    maximum_interval=timedelta(seconds=20), maximum_attempts=6,
                    non_retryable_error_types=NON_RETRYABLE)
STEP_TIMEOUT = timedelta(minutes=10)


HEARTBEAT_TIMEOUT = timedelta(seconds=20)  # a crashed worker is detected within ~20 s


def _opts(timeout: timedelta = STEP_TIMEOUT) -> dict[str, Any]:
    # WAIT_CANCELLATION_COMPLETED: a cancel request lets the in-flight step finish (or observe the request),
    # so cancellation takes effect at a logical-step boundary and never races the finalisation.
    return {"start_to_close_timeout": timeout, "heartbeat_timeout": HEARTBEAT_TIMEOUT, "retry_policy": RETRY,
            "cancellation_type": ActivityCancellationType.WAIT_CANCELLATION_COMPLETED}


@workflow.defn(name="ExperimentWorkflow")
class ExperimentWorkflow:
    def __init__(self) -> None:
        self.pause_requested = False
        self.paused = False
        self.step = 0
        self.phase = "starting"

    @workflow.signal
    def pause(self) -> None:
        self.pause_requested = True

    @workflow.signal
    def resume(self) -> None:
        self.pause_requested = False

    @workflow.query
    def state(self) -> dict[str, Any]:
        return {"step": self.step, "phase": self.phase, "pause_requested": self.pause_requested,
                "paused": self.paused}

    @workflow.run
    async def run(self, inp: dict[str, Any]) -> dict[str, Any]:
        run_id: str = inp["run_id"]
        self.pause_requested = bool(inp.get("pause_requested", False))
        try:
            if inp.get("next_step") is None:
                self.phase = "preparing"
                prep = await workflow.execute_activity("prepare_run", run_id, **_opts())
                if prep.get("terminal"):
                    return await self._finish(run_id, prep)
                self.step = prep["next_step"]
            else:
                self.step = int(inp["next_step"])
            while True:
                if self.pause_requested:
                    self.phase = "pausing"
                    await workflow.execute_activity("mark_paused", run_id, **_opts(timedelta(minutes=1)))
                    self.paused, self.phase = True, "paused"
                    await workflow.wait_condition(lambda: not self.pause_requested)
                    await workflow.execute_activity("mark_resumed", run_id, **_opts(timedelta(minutes=1)))
                    self.paused = False
                self.phase = "stepping"
                res = await workflow.execute_activity("run_step", args=[run_id, self.step], **_opts())
                if res.get("terminal"):
                    return await self._finish(run_id, res)
                self.step = int(res["next_step"])
                if workflow.info().is_continue_as_new_suggested():
                    workflow.continue_as_new({"run_id": run_id, "next_step": self.step,
                                              "pause_requested": self.pause_requested})
        except asyncio.CancelledError:
            return await self._cancelled(run_id)
        except ActivityError as err:
            cause = err.cause
            if isinstance(cause, CancelledError):  # workflow cancelled while an activity was in flight
                return await self._cancelled(run_id)
            message = str(cause) if cause is not None else str(err)
            code = cause.type if isinstance(cause, ApplicationError) else "NON_RETRYABLE_FAILURE"
            self.phase = "failing"
            return await workflow.execute_activity(
                "finalize_run", args=[run_id, "FAILED", f"{code}: {message}", {"code": code, "message": message}],
                **_opts(timedelta(minutes=2)))

    async def _cancelled(self, run_id: str) -> dict[str, Any]:
        self.phase = "cancelling"
        return await workflow.execute_activity(
            "finalize_run", args=[run_id, "CANCELLED", "cancelled by user", None], **_opts(timedelta(minutes=2)))

    async def _finish(self, run_id: str, res: dict[str, Any]) -> dict[str, Any]:
        self.phase = "finalizing"
        if res.get("finalized"):
            return res
        return await workflow.execute_activity(
            "finalize_run", args=[run_id, res["status"], res.get("reason"), None], **_opts(timedelta(minutes=2)))
