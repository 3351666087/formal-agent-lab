"""Worker process: `python -m formal_lab_orchestrator.worker` (or the `fal-worker` script)."""

from __future__ import annotations

import asyncio
import logging
import signal
from concurrent.futures import ThreadPoolExecutor

from formal_lab_api.settings import get_settings
from temporalio.client import Client
from temporalio.worker import Worker

from .activities import ALL
from .workflow import ExperimentWorkflow, MatrixWorkflow

log = logging.getLogger("formal_lab.worker")


async def run_worker(max_concurrent_activities: int = 8) -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from formal_lab_api.db import session_scope
    from formal_lab_api.services.catalog import sync_catalog

    with session_scope() as s:
        n = sync_catalog(s)
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    with ThreadPoolExecutor(max_workers=max_concurrent_activities) as pool:
        worker = Worker(client, task_queue=settings.temporal_task_queue, workflows=[ExperimentWorkflow, MatrixWorkflow],
                        activities=ALL, activity_executor=pool,
                        max_concurrent_activities=max_concurrent_activities)
        log.info("worker started: queue=%s temporal=%s plugins=%d", settings.temporal_task_queue,
                 settings.temporal_address, n)
        async with worker:
            await stop.wait()
        log.info("worker stopped")


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
