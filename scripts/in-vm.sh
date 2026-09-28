#!/usr/bin/env bash
# Run a command inside the Colima Ubuntu VM, in the same directory (the home dir is shared via virtiofs).
# Usage: scripts/in-vm.sh make test
set -euo pipefail
PROFILE="${COLIMA_PROFILE:-default}"
# loopback never through the proxy Lima copies from the host into the VM's /etc/environment (it cannot reach the
# VM's own 127.0.0.1); outbound traffic keeps using it
LOOP='127.0.0.1,localhost,::1'
exec colima ssh -p "$PROFILE" -- bash -lc "export NO_PROXY=\"\${NO_PROXY:+\$NO_PROXY,}$LOOP\" no_proxy=\"\${no_proxy:+\$no_proxy,}$LOOP\"; cd $(printf '%q' "$PWD") && $*"
