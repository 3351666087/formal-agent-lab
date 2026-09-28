#!/usr/bin/env bash
# Load the public backing-service images of deploy/helm/test/backing-services.yaml into a kind node from the local
# Docker, exported for the node's platform only (pulling them from inside the node is slow; `kind load docker-image`
# of a multi-platform image fails with Docker's containerd image store).   usage: kind-load-public.sh <cluster>
set -euo pipefail
cd "$(dirname "$0")/.."
CLUSTER=$1
PLATFORM=linux/$(uname -m | sed 's/aarch64/arm64/;s/x86_64/amd64/')
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
for img in $(grep -oE 'image: [^ ]+' deploy/helm/test/backing-services.yaml | awk '{print $2}' | sort -u); do
  docker image inspect "$img" >/dev/null 2>&1 || docker pull --platform "$PLATFORM" "$img" >/dev/null
  docker save --platform "$PLATFORM" "$img" -o "$TMP/image.tar"
  kind load image-archive --name "$CLUSTER" "$TMP/image.tar" >/dev/null
  rm -f "$TMP/image.tar"
  echo "loaded $img ($PLATFORM)"
done
