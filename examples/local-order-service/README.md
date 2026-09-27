# Local order service example

An independent business service — orders, stock reservation, a processing queue, stations, completion — run as a
separate process (FastAPI + SQLite), next to a pure-data model of the same order handling. The platform reaches
the service only through the environment adapter plugin. The engine never contains a business client. All data is
synthetic.

| part | module | role |
|---|---|---|
| business service | `service.py` | fixed HTTP API, one SQLite file per tenant (= environment session) |
| model (pure backend) | `model.py`, `instance.py` | the same rules as IR, run by `formal-lab.env.ir-world`; shared synthetic instances |
| environment adapter | `env.py` (`formal-lab.example.orders.service-env`) | Environment + SessionEnvironment over HTTP |
| lifecycle | `lifecycle.py` | create → start → ready → reset → close; process or Compose; project labels; precheck; cleanup |
| probe | `plugins.py` (`formal-lab.example.orders.probe`) | throughput, completion rate, queue length, backlog, latency, operation latency, recovery time — read from the service itself |
| strategy / scorer | `plugins.py` | rule strategy; orders completed / late / mean latency |
| comparison | `compare.py` | pure vs service, step by step, down to the state field and operation id |
| end to end | `e2e.py` | empty work dir → environment → experiment → export → reset → rerun → cleanup, with a log |

## Action contract (both backends)

`reserve(o)`, `enqueue(o)`, `start(o, st)` (FIFO head on a free station), `tick()` (time +1: processing, completion,
arrivals of new orders), `restock(sku)` (once per SKU).

## What the service guarantees

- Each operation runs in one SQLite transaction (`BEGIN IMMEDIATE`). The operation id is a primary key checked
  inside that transaction, so an id takes effect at most once. A re-sent id returns the stored answer
  (`replayed: true`), even while the first attempt is still in flight.
- Updates are conditional on the business preconditions. With `REJECT_STALE` they are also conditional on the
  locations the operation reads not having been written after the caller's `based_on_revision` (per-field change
  log). This is the service-side counterpart of the kernel's revision arbitration.
- A crash before COMMIT leaves no trace. A crash after COMMIT leaves the operation recorded, and
  `GET /t/{tenant}/operations/{id}` settles an unanswered call.
- Not covered: several service processes sharing one database file over a network file system.

## Declared capabilities

The adapter declares persistent session, snapshot (session markers only), query operation, idempotent step,
multi-actor, observe on request, service reset and state import. It does **not** declare pure replay or restore:
a worker restoring an old snapshot cannot roll the service back, so recovery re-attaches and reconciles by
operation id instead. The recovery modes are `SERVICE_RESET` and `STATE_IMPORT`; the pure model has `RESEED` and
`SNAPSHOT`.

## Cases

| case | what happens |
|---|---|
| `normal` | enough stock, nominal speed, prompt answers |
| `shortage` | too little stock: SKUs must be restocked |
| `delayed` | every 4th answer is held past the client timeout after commit → OUTCOME_UNKNOWN → looked up → RECONCILED |
| `restart` | the process exits right after committing its 5th operation; the supervisor restarts it; the run continues |
| `deviation` | station p2 runs at half speed in the service; the model predicts nominal speed → effect differences |

## Running it

```bash
make orders-up          # service on 127.0.0.1:8765, project "dev" (data under var/.fal-orders/dev)
make orders-status
make orders-down        # ARGS=--purge also removes the data
make orders-e2e         # process and Compose end to end, logs in docs/execution/evidence/phase2/orders/
```

To run the service in Compose on its own, use `examples/local-order-service/compose.yaml`; the lifecycle
manager's `mode="compose"` drives it with `-p fal-orders-<project>`. In the full stack
(`deploy/compose/docker-compose.yaml`) the service is `orders` and the platform reaches it at
`http://orders:8765` (`FAL_ORDERS_ENDPOINT`). Every container and volume carries
`dev.formal-lab.project=<project>`, and cleanup removes only those.
