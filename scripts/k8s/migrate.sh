#!/usr/bin/env sh
set -eu

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
K8S_NAMESPACE=${K8S_NAMESPACE:-cistafirma}
BACKEND_IMAGE_REF=${BACKEND_IMAGE_REF:-}

if [ -z "$BACKEND_IMAGE_REF" ]; then
  echo "ERROR: BACKEND_IMAGE_REF must be set (e.g. registry.gitlab.com/group/proj/backend:v1.2.3)"
  exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

cp -R "$ROOT_DIR/deploy/k8s/base" "$TMP_DIR/base"
RUN_ID=$(date +%s)

sed -i.bak "s|__BACKEND_IMAGE__|$BACKEND_IMAGE_REF|g" "$TMP_DIR/base/migrate-job.yaml"
sed -i.bak "s|__RUN_ID__|$RUN_ID|g" "$TMP_DIR/base/migrate-job.yaml"
find "$TMP_DIR" -name '*.bak' -delete

kubectl apply -f "$TMP_DIR/base/namespace.yaml"
JOB_NAME="cistafirma-migrate-$RUN_ID"
kubectl apply -f "$TMP_DIR/base/migrate-job.yaml"
kubectl wait --for=condition=complete --timeout=900s "job/$JOB_NAME" -n "$K8S_NAMESPACE"

echo "Migration finished: job=$JOB_NAME"

