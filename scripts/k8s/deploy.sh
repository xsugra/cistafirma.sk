#!/usr/bin/env sh
set -eu

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
K8S_NAMESPACE=${K8S_NAMESPACE:-cistafirma}
DEPLOY_ENV=${DEPLOY_ENV:-dev}
DEPLOY_IMAGE_TAG=${DEPLOY_IMAGE_TAG:-latest}
BACKEND_IMAGE=${BACKEND_IMAGE:-}
FRONTEND_IMAGE=${FRONTEND_IMAGE:-}
RUN_DB_BACKUP=${RUN_DB_BACKUP:-false}

if [ -z "$BACKEND_IMAGE" ] || [ -z "$FRONTEND_IMAGE" ]; then
  echo "ERROR: BACKEND_IMAGE and FRONTEND_IMAGE must be set"
  exit 1
fi

if [ "$DEPLOY_ENV" != "dev" ] && [ "$DEPLOY_ENV" != "prod" ]; then
  echo "ERROR: DEPLOY_ENV must be dev or prod"
  exit 1
fi

if [ "$RUN_DB_BACKUP" = "true" ]; then
  if command -v pg_dump >/dev/null 2>&1 && [ -n "${DB_HOST:-}" ] && [ -n "${DB_NAME:-}" ] && [ -n "${DB_USER:-}" ] && [ -n "${DB_PASSWORD:-}" ]; then
    echo "Running pre-deploy DB backup..."
    sh "$ROOT_DIR/scripts/k8s/backup_postgres.sh"
  else
    echo "WARNING: DB backup requested but pg_dump/DB env vars are missing. Skipping backup."
  fi
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

cp -R "$ROOT_DIR/deploy" "$TMP_DIR/deploy"

BACKEND_IMAGE_REF="$BACKEND_IMAGE:$DEPLOY_IMAGE_TAG"
FRONTEND_IMAGE_REF="$FRONTEND_IMAGE:$DEPLOY_IMAGE_TAG"
RUN_ID=$(date +%s)

# Inject dynamic image references and migration job run id
sed -i.bak "s|__BACKEND_IMAGE__|$BACKEND_IMAGE_REF|g" "$TMP_DIR/deploy/k8s/base/backend-deployment.yaml"
sed -i.bak "s|__FRONTEND_IMAGE__|$FRONTEND_IMAGE_REF|g" "$TMP_DIR/deploy/k8s/base/frontend-deployment.yaml"
sed -i.bak "s|__BACKEND_IMAGE__|$BACKEND_IMAGE_REF|g" "$TMP_DIR/deploy/k8s/base/migrate-job.yaml"
sed -i.bak "s|__RUN_ID__|$RUN_ID|g" "$TMP_DIR/deploy/k8s/base/migrate-job.yaml"
find "$TMP_DIR/deploy/k8s" -name '*.bak' -delete

# Ensure namespace exists before running migration job
kubectl apply -f "$TMP_DIR/deploy/k8s/base/namespace.yaml"
# Ensure migration prerequisites exist before creating migration job
kubectl apply -f "$TMP_DIR/deploy/k8s/base/configmap.yaml"
if ! kubectl get secret cistafirma-secrets -n "$K8S_NAMESPACE" >/dev/null 2>&1; then
  echo "ERROR: Required secret 'cistafirma-secrets' is missing in namespace '$K8S_NAMESPACE'."
  exit 1
fi

MIGRATE_JOB_NAME="cistafirma-migrate-$RUN_ID"
echo "Applying migration job: $MIGRATE_JOB_NAME"
kubectl apply -f "$TMP_DIR/deploy/k8s/base/migrate-job.yaml"
if ! kubectl wait --for=condition=complete --timeout=900s "job/$MIGRATE_JOB_NAME" -n "$K8S_NAMESPACE"; then
  echo "ERROR: Migration job did not complete within timeout. Diagnostics:"
  kubectl get job "$MIGRATE_JOB_NAME" -n "$K8S_NAMESPACE" -o wide || true
  kubectl describe job "$MIGRATE_JOB_NAME" -n "$K8S_NAMESPACE" || true
  for pod in $(kubectl get pods -n "$K8S_NAMESPACE" -l "job-name=$MIGRATE_JOB_NAME" -o name 2>/dev/null || true); do
    kubectl describe "$pod" -n "$K8S_NAMESPACE" || true
    kubectl logs "$pod" -n "$K8S_NAMESPACE" --all-containers --tail=200 || true
    kubectl logs "$pod" -n "$K8S_NAMESPACE" --all-containers --tail=200 --previous || true
  done
  exit 1
fi

# Apply selected overlay
kubectl apply -k "$TMP_DIR/deploy/k8s/overlays/$DEPLOY_ENV"

# Rollout checks
kubectl rollout status deployment/cistafirma-backend -n "$K8S_NAMESPACE" --timeout=600s
kubectl rollout status deployment/cistafirma-frontend -n "$K8S_NAMESPACE" --timeout=600s

echo "Deploy finished: env=$DEPLOY_ENV backend=$BACKEND_IMAGE_REF frontend=$FRONTEND_IMAGE_REF"
