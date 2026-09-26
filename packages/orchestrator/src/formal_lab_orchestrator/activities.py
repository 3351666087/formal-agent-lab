"""Temporal activities: thin wrappers over formal_lab_api.services.execution (sync, thread pool)."""

from __future__ import annotations

import contextvars
import functools
import threading
from typing import Any

from formal_lab_contracts.errors import FormalLabError
from temporalio import activity
from temporalio.exceptions import ApplicationError


HEARTBEAT_EVERY_S = 5.0


def _heartbeating(stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_EVERY_S):
        try:
            activity.heartbeat()
        except Exception:  # heartbeating is best effort; the activity result is what matters
            return


def _mapped(fn):
    @functools.wraps(fn)
    def wrapper(*args: Any) -> Any:
        stop = threading.Event()
        ctx = contextvars.copy_context()  # carries the activity context into the heartbeat thread
        beat = threading.Thread(target=ctx.run, args=(_heartbeating, stop), daemon=True)
        beat.start()
        try:
            return fn(*args)
        except FormalLabError as exc:
            raise ApplicationError(exc.message, exc.to_info().model_dump(mode="json"), type=exc.code.value,
                                   non_retryable=not exc.retryable) from exc
        finally:
            stop.set()

    return wrapper


@activity.defn(name="prepare_run")
@_mapped
def prepare_run(run_id: str) -> dict[str, Any]:
    from formal_lab_api.services import execution

    return execution.prepare_run(run_id)


@activity.defn(name="run_step")
@_mapped
def run_step(run_id: str, step: int) -> dict[str, Any]:
    from formal_lab_api.services import execution

    return execution.run_step(run_id, step)


@activity.defn(name="mark_paused")
@_mapped
def mark_paused(run_id: str) -> dict[str, Any]:
    from formal_lab_api.services import execution

    return execution.mark_paused(run_id)


@activity.defn(name="mark_resumed")
@_mapped
def mark_resumed(run_id: str) -> dict[str, Any]:
    from formal_lab_api.services import execution

    return execution.mark_resumed(run_id)


@activity.defn(name="finalize_run")
@_mapped
def finalize_run(run_id: str, status: str, reason: str | None, error: dict[str, Any] | None) -> dict[str, Any]:
    from formal_lab_api.services import execution

    return execution.finalize_run(run_id, status, reason, error)


ALL = [prepare_run, run_step, mark_paused, mark_resumed, finalize_run]
