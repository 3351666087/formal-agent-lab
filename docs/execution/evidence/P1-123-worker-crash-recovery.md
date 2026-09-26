# Worker crash recovery evidence (P1-026 / P1-027 / P1-028 / P1-123)

Test: `tests/integration/test_platform_runs.py::test_worker_crash_is_recovered_without_duplicates`
(real PostgreSQL 16 + Temporal dev server 1.9.1 / server 1.32.0, API and worker as subprocesses; worker killed with
SIGKILL on its process group while the run was at step ≥ 4 of the state-delay scenario, restarted 3 s later).

Result of the 2026-09-26 run: `10 passed in 92.95s` for tests/integration/test_platform_runs.py.

Temporal history of workflow `run-run_8dbfb89baadf41bd9d29` (the crash test run), filtered to retried/failed items:

```
36 ACTIVITY_TASK_STARTED attempt=2 lastFailure={"message": "activity Heartbeat timeout", "source": "Server",
   "timeoutFailureInfo": {"timeoutType": "TIMEOUT_TYPE_HEARTBEAT"}}
```

Operation ledger for the steps around the crash (`operations` table): every propose/apply operation completed exactly
once — the retried activity found no COMPLETED apply record, reused nothing it should not, and committed once:

```
run_8dbfb89baadf41bd9d29:s4:apply|COMPLETED|1
run_8dbfb89baadf41bd9d29:s4:propose|COMPLETED|1
run_8dbfb89baadf41bd9d29:s5:apply|COMPLETED|1
run_8dbfb89baadf41bd9d29:s5:propose|COMPLETED|1
run_8dbfb89baadf41bd9d29:s6:apply|COMPLETED|1
run_8dbfb89baadf41bd9d29:s6:propose|COMPLETED|1
```

The test also asserts: gap-free event sequence, unique idempotency keys, closed causal graph, exactly one ACTION_OUTCOME
per logical step, final status SUCCEEDED and workflow status COMPLETED.
