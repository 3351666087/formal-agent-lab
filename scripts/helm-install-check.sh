#!/usr/bin/env bash
# Install the Helm chart into a throw-away kind cluster and run an experiment through it (P1-113 install check).
# Evidence: docs/execution/evidence/helm/install.json. The cluster is deleted at the end (--keep to keep it).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/formal-agent-lab}"
KIND_VERSION=v0.33.0
KUBECTL_VERSION=v1.37.1
NODE_IMAGE="kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
CLUSTER=fal-helm
ARCH=$(uname -m | sed 's/aarch64/arm64/;s/x86_64/amd64/')
OUT=docs/execution/evidence/helm/install.json
LOG=docs/execution/evidence/helm/install.log
exec > >(tee "$LOG") 2>&1
python3 scripts/disk_guard.py --need 8 --label "helm install check (images + kind node)" --trim

command -v kind >/dev/null && kind version | grep -q "$KIND_VERSION" || \
  curl -fsSLo "$HOME/.local/bin/kind" "https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}/kind-linux-${ARCH}"
command -v kubectl >/dev/null && kubectl version --client 2>/dev/null | grep -q "$KUBECTL_VERSION" || \
  curl -fsSLo "$HOME/.local/bin/kubectl" "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl"
chmod +x "$HOME/.local/bin/kind" "$HOME/.local/bin/kubectl"

REV=$(git rev-parse HEAD); TAG=${REV:0:12}
echo "==> images"
FAL_SOURCE_REVISION=$REV docker compose -f deploy/compose/docker-compose.yaml build --quiet
for n in api worker web; do docker tag formal-agent-lab/$n:local formal-agent-lab/$n:$TAG; done

echo "==> kind cluster $CLUSTER ($NODE_IMAGE)"
kind delete cluster --name $CLUSTER >/dev/null 2>&1 || true
kind create cluster --name $CLUSTER --image "$NODE_IMAGE" --wait 180s
trap '[[ "${1:-}" == "--keep" ]] || kind delete cluster --name '$CLUSTER' >/dev/null 2>&1' EXIT
# our locally built (single-platform) images are loaded into the node; the public backing-service images are
# exported for the node's platform only and loaded as archives (`kind load docker-image` of a multi-platform image
# fails with Docker's containerd image store, and pulling seaweedfs from inside the node takes minutes)
for img in formal-agent-lab/api:$TAG formal-agent-lab/worker:$TAG formal-agent-lab/web:$TAG; do
  kind load docker-image --name $CLUSTER $img >/dev/null
done
bash scripts/kind-load-public.sh $CLUSTER

echo "==> test backing services"
kubectl apply -f deploy/helm/test/backing-services.yaml
kubectl rollout status deploy/postgres deploy/temporal deploy/s3 --timeout=600s  # node pulls these

echo "==> helm install (images pinned by tag loaded into the node; pullPolicy Never)"
T0=$(date +%s)
helm install fal deploy/helm/formal-agent-lab --wait --timeout 6m \
  --set image.tag=$TAG --set image.pullPolicy=Never \
  --set externalServices.temporal.address=temporal:7233 \
  --set externalServices.artifacts.s3.endpoint=http://s3:8333
helm status fal
kubectl get pods -o wide
kubectl wait --for=condition=complete job -l app.kubernetes.io/component=migrate --timeout=10s 2>/dev/null || true

echo "==> seed + experiment through the web service"
kubectl exec deploy/fal-formal-agent-lab-api -- python -m formal_lab_api.seed
kubectl port-forward svc/fal-formal-agent-lab-web 18090:80 >/dev/null 2>&1 &
PF=$!; sleep 3
export FAL_API_URL=http://127.0.0.1:18090/api/v1
uv run --frozen python - "$OUT" "$NODE_IMAGE" "$TAG" "$T0" <<'PY'
import json, subprocess, sys, time
from formal_lab_sdk import Client
out, node, tag, t0 = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
c = Client()
ready = c.get("/health/ready")
pid = c.find_project("生产调度示例")["id"]
sc = {s["name"]: s["id"] for s in c.scenarios(pid)}
st = {s["name"]: s["id"] for s in c.strategies(pid)}
run = c.start_run(pid, sc["状态延迟"], st["Z3 有界规划"], seed=4)
events = [e.seq for e in c.follow(run["id"])]
done = c.wait(run["id"])
pods = json.loads(subprocess.run(["kubectl", "get", "pods", "-o", "json"], capture_output=True, text=True, check=True).stdout)
evidence = {
    "check": "P1-113 Helm install on a kind cluster",
    "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "cluster": {"tool": "kind v0.33.0", "node_image": node,
                "kubernetes": subprocess.run(["kubectl", "version", "-o", "json"], capture_output=True, text=True).stdout and
                json.loads(subprocess.run(["kubectl", "version", "-o", "json"], capture_output=True, text=True).stdout)["serverVersion"]["gitVersion"]},
    "chart": "deploy/helm/formal-agent-lab", "release": "fal", "image_tag": tag,
    "backing_services": "test fixture deploy/helm/test/backing-services.yaml (not part of the chart)",
    "pods": [{"name": p["metadata"]["name"], "phase": p["status"]["phase"],
              "ready": all(cs.get("ready") for cs in p["status"].get("containerStatuses", []))} for p in pods["items"]],
    "ready": ready,
    "run": {"id": run["id"], "status": done["status"], "events": done["event_seq"], "sse_events": len(events),
            "metrics": {k: v["value"] for k, v in done["metrics"].items()}},
    "passed": ready["ready"] and done["status"] == "SUCCEEDED" and events == list(range(1, done["event_seq"] + 1)),
    "install_to_result_s": int(time.time()) - t0,
}
open(out, "w").write(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({"passed": evidence["passed"], "run": evidence["run"]["status"], "kubernetes": evidence["cluster"]["kubernetes"]}))
assert evidence["passed"]
PY
kill $PF || true
echo "==> OK ($OUT)"
