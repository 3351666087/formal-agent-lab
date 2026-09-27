#!/usr/bin/env bash
# Helm upgrade / rollback on a throw-away single-node kind cluster (P2-104).
#   previous: the phase-1 release (handoff commit 46400ad: chart 0.1.0, database migrations up to 0001)
#   current : HEAD (chart 0.2.0, migration 0002 adds columns with defaults and new tables)
# install previous → seed + experiment → upgrade (pre-upgrade migration hook) → old data readable + new experiment →
# rollback (no migration hook runs: the phase-1 code meets the 0002 schema) → the phase-1 app still serves and runs.
# Evidence: docs/execution/evidence/helm/upgrade.{json,log}. Results hold for a single-node development cluster only.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/formal-agent-lab}"
NODE_IMAGE="kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
CLUSTER=fal-upgrade
PREV=46400ad
REV=$(git rev-parse HEAD); TAG=${REV:0:12}; PTAG=p1-$PREV
OUT=docs/execution/evidence/helm/upgrade.json
LOG=docs/execution/evidence/helm/upgrade.log
exec > >(tee "$LOG") 2>&1
WT=$(mktemp -d)/phase1
stop_forward() { # never `kill 0`: with PF unset that would signal this whole process group
  if [[ -n "${PF:-}" ]]; then kill "$PF" 2>/dev/null || true; PF=; fi; }
cleanup() {
  stop_forward
  [[ "${1:-}" == "--keep" ]] || kind delete cluster --name $CLUSTER >/dev/null 2>&1 || true
  git worktree remove --force "$WT" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> images: previous ($PREV → $PTAG) and current ($TAG)"
git worktree add --detach "$WT" $PREV >/dev/null
(cd "$WT" && FAL_IMAGE_TAG=$PTAG FAL_SOURCE_REVISION=$(git rev-parse HEAD) \
   docker compose -f deploy/compose/docker-compose.yaml build --quiet api worker web)
FAL_IMAGE_TAG=$TAG FAL_SOURCE_REVISION=$REV docker compose -f deploy/compose/docker-compose.yaml build --quiet api worker web

echo "==> kind cluster $CLUSTER"
kind delete cluster --name $CLUSTER >/dev/null 2>&1 || true
kind create cluster --name $CLUSTER --image "$NODE_IMAGE" --wait 180s
for t in $PTAG $TAG; do for n in api worker web; do kind load docker-image --name $CLUSTER formal-agent-lab/$n:$t >/dev/null; done; done
kubectl apply -f deploy/helm/test/backing-services.yaml
kubectl rollout status deploy/postgres deploy/temporal deploy/s3 --timeout=180s

SET="--set image.pullPolicy=Never --set externalServices.temporal.address=temporal:7233 --set externalServices.artifacts.s3.endpoint=http://s3:8333"
revision() { kubectl exec deploy/postgres -- psql -U fal -d fal -Atc "select version_num from alembic_version"; }
forward() { stop_forward; sleep 1
  kubectl port-forward svc/fal-formal-agent-lab-web 18091:80 >/dev/null 2>&1 & PF=$!; sleep 4; }
probe() { # phase label → JSON line appended to $STATE
  uv run --frozen python scripts/helm_upgrade_probe.py "$1" http://127.0.0.1:18091/api/v1 "$STATE"; }
STATE=$(mktemp)

echo "==> install previous chart + images ($PREV)"
helm install fal "$WT/deploy/helm/formal-agent-lab" --wait --timeout 6m --set image.tag=$PTAG $SET
kubectl exec deploy/fal-formal-agent-lab-api -- python -m formal_lab_api.seed >/dev/null
echo "alembic: $(revision)"; echo "{\"phase\": \"installed-revision\", \"alembic\": \"$(revision)\"}" >> "$STATE"
forward; probe previous

echo "==> upgrade to current chart + images ($TAG)"
helm upgrade fal deploy/helm/formal-agent-lab --wait --timeout 8m --set image.tag=$TAG $SET
kubectl exec deploy/fal-formal-agent-lab-api -- python -m formal_lab_api.seed >/dev/null
echo "alembic: $(revision)"; echo "{\"phase\": \"upgraded-revision\", \"alembic\": \"$(revision)\"}" >> "$STATE"
forward; probe upgraded

echo "==> rollback to revision 1 (previous chart + images; the database stays at $(revision))"
helm rollback fal 1 --wait --timeout 6m
helm history fal
echo "{\"phase\": \"rolled-back-revision\", \"alembic\": \"$(revision)\"}" >> "$STATE"
forward; probe rolled-back

uv run --frozen python - "$STATE" "$OUT" "$PREV" "$TAG" "$NODE_IMAGE" <<'PY'
import json, sys, time
state, out, prev, tag, node = sys.argv[1:6]
rows = [json.loads(l) for l in open(state) if l.strip()]
by = {r["phase"]: r for r in rows}
passed = (by["installed-revision"]["alembic"] == "0001" and by["upgraded-revision"]["alembic"] == "0002"
          and by["previous"]["run_status"] == "SUCCEEDED" and by["upgraded"]["old_run_readable"]
          and by["upgraded"]["run_status"] == "SUCCEEDED" and by["rolled-back"]["ready"]
          and by["rolled-back"]["run_status"] == "SUCCEEDED")
json.dump({"check": "P2-104 Helm upgrade / rollback on kind (single-node development cluster)",
           "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "node_image": node,
           "previous": {"commit": prev, "chart": "0.1.0"}, "current": {"image_tag": tag, "chart": "0.2.0"},
           "phases": rows, "passed": passed,
           "scope": "single-node kind; test-fixture backing services; not a multi-node or production upgrade"},
          open(out, "w"), indent=2, ensure_ascii=False)
print(json.dumps({"passed": passed, **{r["phase"]: r.get("alembic", r.get("run_status")) for r in rows}}))
assert passed
PY
echo "==> OK ($OUT)"
