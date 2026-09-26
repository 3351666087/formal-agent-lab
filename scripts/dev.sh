#!/usr/bin/env bash
# Local development processes (inside the Ubuntu VM): backing services, API, worker, web dev server.
#   scripts/dev.sh up|down|status|restart [api|worker|web]
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/formal-agent-lab}"
export PATH="$HOME/.local/bin:$PATH"
RUN_DIR=var/run
LOG_DIR=var/log
mkdir -p "$RUN_DIR" "$LOG_DIR"
COMPOSE="docker compose -f deploy/compose/services.dev.yaml -p fal-dev"

start() { # name command...
  local name=$1; shift
  if [[ -f $RUN_DIR/$name.pid ]] && kill -0 "$(cat $RUN_DIR/$name.pid)" 2>/dev/null; then
    echo "$name already running (pid $(cat $RUN_DIR/$name.pid))"; return
  fi
  setsid nohup "$@" >"$LOG_DIR/$name.log" 2>&1 < /dev/null &
  echo $! > "$RUN_DIR/$name.pid"
  echo "$name started (pid $!, log $LOG_DIR/$name.log)"
}

stop() {
  local name=$1
  if [[ -f $RUN_DIR/$name.pid ]]; then
    local pid; pid=$(cat "$RUN_DIR/$name.pid")
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in {1..20}; do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -KILL -- "-$pid" 2>/dev/null || true
    rm -f "$RUN_DIR/$name.pid"; echo "$name stopped"
  fi
}

wait_http() { for _ in {1..60}; do curl -fsS "$1" >/dev/null 2>&1 && return 0; sleep 0.5; done; echo "timeout waiting for $1" >&2; return 1; }

services_up() {
  $COMPOSE up -d --wait
  uv run --frozen python -m formal_lab_api.migrate upgrade
}

case "${1:-status}" in
  up)
    services_up
    uv run --frozen python -m formal_lab_api.seed
    targets=${2:-"api worker web"}
    [[ $targets == *api* ]] && start api uv run --frozen python -m formal_lab_api.app && wait_http http://127.0.0.1:8000/health
    [[ $targets == *worker* ]] && start worker uv run --frozen python -m formal_lab_orchestrator.worker
    if [[ $targets == *web* && -d web/node_modules ]]; then start web pnpm --dir web dev --host 127.0.0.1 --port 5173; fi
    ;;
  services) services_up ;;
  down) for n in web worker api; do stop $n; done ;;
  services-down) $COMPOSE down ;;
  restart) for n in ${2:-web worker api}; do stop "$n"; done; exec "$0" up "${2:-api worker web}" ;;
  status)
    for n in api worker web; do
      if [[ -f $RUN_DIR/$n.pid ]] && kill -0 "$(cat $RUN_DIR/$n.pid)" 2>/dev/null; then echo "$n: running (pid $(cat $RUN_DIR/$n.pid))"; else echo "$n: stopped"; fi
    done
    $COMPOSE ps --format '{{.Service}}: {{.Status}}' ;;
  kill-worker) # simulate a worker crash (SIGKILL, no graceful shutdown)
    pid=$(cat $RUN_DIR/worker.pid); kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid"; rm -f $RUN_DIR/worker.pid; echo "worker killed" ;;
  *) echo "usage: $0 up|down|status|restart|services|services-down|kill-worker" >&2; exit 2 ;;
esac
