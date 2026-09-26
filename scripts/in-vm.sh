#!/usr/bin/env bash
# Run a command inside the Colima Ubuntu VM, in the same directory (the home dir is shared via virtiofs).
# Usage: scripts/in-vm.sh make test
set -euo pipefail
PROFILE="${COLIMA_PROFILE:-default}"
exec colima ssh -p "$PROFILE" -- bash -lc "cd $(printf '%q' "$PWD") && $*"
