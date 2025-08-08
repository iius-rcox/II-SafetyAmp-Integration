#!/usr/bin/env bash
set -euo pipefail

# Build, push, and rollout app image with observability changes
#
# Usage:
#   ./update-application-code.sh \
#     --image "<acr>.azurecr.io/safetyamp-integration" \
#     --tag "$(git rev-parse --short HEAD)" \
#     --registry-login-server "<acr>.azurecr.io" \
#     --registry-username "<svc-principal>" \
#     --registry-password "<password>" \
#     [--namespace safety-amp]

IMAGE=""
TAG=""
REGISTRY=""
REG_USER=""
REG_PASS=""
NAMESPACE="safety-amp"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --tag) TAG="$2"; shift 2 ;;
    --registry-login-server) REGISTRY="$2"; shift 2 ;;
    --registry-username) REG_USER="$2"; shift 2 ;;
    --registry-password) REG_PASS="$2"; shift 2 ;;
    --namespace) NAMESPACE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$IMAGE" ]]; then
  echo "Provide --image <registry/repo>" >&2
  exit 2
fi

if [[ -z "$TAG" ]]; then
  TAG="$(date +%Y%m%d%H%M%S)"
fi

FULL_IMAGE="$IMAGE:$TAG"

echo "==> Building image: $FULL_IMAGE"
docker build -t "$FULL_IMAGE" .

if [[ -n "$REGISTRY" && -n "$REG_USER" && -n "$REG_PASS" ]]; then
  echo "==> Logging into registry $REGISTRY"
  echo "$REG_PASS" | docker login "$REGISTRY" -u "$REG_USER" --password-stdin
fi

echo "==> Pushing image: $FULL_IMAGE"
docker push "$FULL_IMAGE"

echo "==> Rolling out to Kubernetes (ns/$NAMESPACE)"
kubectl -n "$NAMESPACE" set image deployment/safety-amp-agent safety-amp-agent="$FULL_IMAGE"
kubectl -n "$NAMESPACE" rollout status deployment/safety-amp-agent

echo "✓ Deployment updated to $FULL_IMAGE"
