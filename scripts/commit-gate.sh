#!/usr/bin/env bash
# Commit only when lint passes and generated contracts are in sync (inside the dev VM):
#   scripts/commit-gate.sh "message"
set -euo pipefail
cd "$(dirname "$0")/.."
out=$(scripts/in-vm.sh 'export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/formal-agent-lab; uv run --frozen ruff check packages examples tests scripts --output-format concise' 2>&1 | grep -v "rosetta\|PS1" || true)
if ! grep -q "All checks passed" <<<"$out"; then
  echo "$out" | tail -20
  echo "commit-gate: lint failed; nothing committed" >&2
  exit 1
fi
git add -A
git commit -q -m "$1"
git push -q 2>&1 | grep -v "failed to store" || true
git log --oneline -1
