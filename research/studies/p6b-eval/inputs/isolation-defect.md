# Mechanism: tenant/object access isolation on the order service

One page, written before modelling. Scope: the local order service (examples/local-order-service) with the phase-5B
authorization research fixture (`research_isolation.py`), on local test tenants only.

- **Subject.** A client identified by a bearer token. The fixture knows two principals: `alpha` (token fixt-alpha,
  granted tenant `acme`) and `bravo` (token fixt-bravo, granted tenant `globex`). The program identifies the subject
  by looking the bearer token up in the authorization layer; an unknown or missing token is 401. Initial permission =
  the principal's grant set. Known information = its own token and the tenant ids in the URL space.
- **Resource.** A tenant's business state (orders, stock, operations), one SQLite file per tenant, owned by the tenant.
  Fixed synthetic instances (the `normal` case, seed 1). Relevant state: whether a request reads or changes a tenant's
  stored values.
- **Capability.** The subject can issue the local HTTP API (`/t/{tenant}/state`, `/operations`, `/admin/*`, …) with any
  tenant id and body it chooses — the tenant id and request body are controllable input. It cannot forge another
  tenant's server-side grant record, cannot read the SQLite files directly, and cannot change the authorization layer:
  those are uncontrollable program facts.
- **Trust boundary.** The tenant id and bearer token in each request need server-side validation. The judgement is made
  by the authorization layer (`research_isolation.create_isolation_app`'s middleware) before the request reaches the
  business route. The business layer itself does not re-check tenant ownership.
- **Action.** `access(subject, tenant)` maps to one HTTP request to `/t/{tenant}/…`. Precondition (secure): the subject
  is granted that tenant. Failure result: 401 (unknown principal) or 403 (not granted). Success: the business route
  runs and the tenant's state/observation may change (write) or be returned (read).
- **Property.** `tenant_isolation` (invariant): no access by a subject to a tenant succeeds unless the subject is
  granted that tenant — `forall s,t: accessed[s][t] -> grant[s][t]`. Machine-checkable on the finite model; the expr
  digest is recorded in the case.
- **Oracle.** Independent of the subject under test: the real HTTP status, and the tenant's stored state read back
  through that tenant's own authorized principal (did a cross-tenant write actually land? did a cross-tenant read
  actually return the other tenant's values?). A request the oracle cannot classify (e.g. the authorization layer let
  it through but the business layer rejected it for an unrelated precondition, so no state changed) stays UNKNOWN.


## The recorded run to judge

Each line is one request a principal made and exactly what the service did (the grant table above says which tenant each principal may use):

- principal `alpha` sent a read request to tenant `acme`: responded 200 and returned acme's stored order state
- principal `alpha` sent a write request to tenant `acme`: responded 200; the operation was applied and changed acme's stored state (confirmed by reading acme's state afterwards)
- principal `bravo` sent a read request to tenant `globex`: responded 200 and returned globex's stored order state
- principal `bravo` sent a write request to tenant `globex`: responded 200; the operation was applied and changed globex's stored state (confirmed by reading globex's state afterwards)
- principal `alpha` sent a read request to tenant `globex`: responded 200 and returned globex's stored order state
- principal `alpha` sent a write request to tenant `globex`: responded 200 but the business logic rejected the operation, so globex's state did not change
- principal `bravo` sent a read request to tenant `acme`: responded 200 and returned acme's stored order state
- principal `bravo` sent a write request to tenant `acme`: responded 200 but the business logic rejected the operation, so acme's state did not change
