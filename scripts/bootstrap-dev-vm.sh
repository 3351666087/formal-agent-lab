#!/usr/bin/env bash
# Install the pinned development toolchain on an Ubuntu 24.04 host/VM (arm64 or amd64).
# Idempotent: re-running only installs what is missing or at a different version.
set -euo pipefail

UV_VERSION=0.12.19
NODE_VERSION=24.21.0
PNPM_VERSION=12.6.0
HELM_VERSION=4.3.0
TEMPORAL_CLI_VERSION=1.9.1
KUBECONFORM_VERSION=0.8.0

PREFIX="${PREFIX:-$HOME/.local}"
mkdir -p "$PREFIX/bin" "$PREFIX/opt"
export PATH="$PREFIX/bin:$PATH"

case "$(uname -m)" in
  aarch64|arm64) ARCH=arm64; NODE_ARCH=arm64; UV_ARCH=aarch64 ;;
  x86_64|amd64)  ARCH=amd64; NODE_ARCH=x64;   UV_ARCH=x86_64 ;;
  *) echo "unsupported arch $(uname -m)" >&2; exit 1 ;;
esac

log() { printf '==> %s\n' "$*"; }

if ! command -v make >/dev/null || ! command -v jq >/dev/null || ! command -v unzip >/dev/null \
   || ! python3 -c "import ensurepip" 2>/dev/null; then
  log "apt packages"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential git curl jq unzip ca-certificates python3-venv >/dev/null
fi

if [[ "$(uv --version 2>/dev/null | awk '{print $2}')" != "$UV_VERSION" ]]; then
  log "uv $UV_VERSION"
  curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${UV_ARCH}-unknown-linux-gnu.tar.gz" \
    | tar -xz -C "$PREFIX/bin" --strip-components=1
fi

if [[ "$(node --version 2>/dev/null)" != "v$NODE_VERSION" ]]; then
  log "node $NODE_VERSION"
  rm -rf "$PREFIX/opt/node"
  mkdir -p "$PREFIX/opt/node"
  curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz" \
    | tar -xJ -C "$PREFIX/opt/node" --strip-components=1
  for b in node npm npx corepack; do ln -sf "$PREFIX/opt/node/bin/$b" "$PREFIX/bin/$b"; done
fi

if [[ "$(pnpm --version 2>/dev/null)" != "$PNPM_VERSION" ]]; then
  log "pnpm $PNPM_VERSION"
  npm install -g --silent --prefix "$PREFIX/opt/node" "pnpm@${PNPM_VERSION}"
  ln -sf "$PREFIX/opt/node/bin/pnpm" "$PREFIX/bin/pnpm"
fi

if [[ "$(helm version --template '{{.Version}}' 2>/dev/null)" != "v$HELM_VERSION" ]]; then
  log "helm $HELM_VERSION"
  curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" \
    | tar -xz -C "$PREFIX/bin" --strip-components=1 "linux-${ARCH}/helm"
fi

if ! temporal --version 2>/dev/null | grep -q "$TEMPORAL_CLI_VERSION"; then
  log "temporal cli $TEMPORAL_CLI_VERSION"
  curl -fsSL "https://github.com/temporalio/cli/releases/download/v${TEMPORAL_CLI_VERSION}/temporal_cli_${TEMPORAL_CLI_VERSION}_linux_${ARCH}.tar.gz" \
    | tar -xz -C "$PREFIX/bin" temporal
fi

if ! kubeconform -v 2>/dev/null | grep -q "$KUBECONFORM_VERSION"; then
  log "kubeconform $KUBECONFORM_VERSION"
  curl -fsSL "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-${ARCH}.tar.gz" \
    | tar -xz -C "$PREFIX/bin" kubeconform
fi

grep -q 'formal-agent-lab toolchain' "$HOME/.profile" 2>/dev/null || cat >> "$HOME/.profile" <<EOF

# formal-agent-lab toolchain
export PATH="$PREFIX/bin:\$PATH"
EOF

log "toolchain"
printf '%-10s %s\n' uv "$(uv --version)" node "$(node --version)" pnpm "$(pnpm --version)" \
  helm "$(helm version --short)" temporal "$(temporal --version)" kubeconform "$(kubeconform -v)" python3 "$(python3 --version)" make "$(make --version | head -1)"
