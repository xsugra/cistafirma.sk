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

# Pre-deploy DB backup (production only)
if [ "$RUN_DB_BACKUP" = "true" ]; then
  if command -v pg_dump >/dev/null 2>&1 && [ -n "${DB_HOST:-}" ] && [ -n "${DB_NAME:-}" ] && [ -n "${DB_USER:-}" ] && [ -n "${DB_PASSWORD:-}" ]; then
    echo "Running pre-deploy DB backup..."
    sh "$ROOT_DIR/scripts/k8s/backup_postgres.sh"
  else
    echo "WARNING: DB backup requested but pg_dump/DB env vars are missing. Skipping backup."
  fi
fi

HELM_CHART="$ROOT_DIR/deploy/helm/cistafirma"
VALUES_FILE="$HELM_CHART/values-${DEPLOY_ENV}.yaml"
BACKEND_IMAGE_REF="$BACKEND_IMAGE:$DEPLOY_IMAGE_TAG"
FRONTEND_IMAGE_REF="$FRONTEND_IMAGE:$DEPLOY_IMAGE_TAG"

echo "Helm deploy: env=$DEPLOY_ENV backend=$BACKEND_IMAGE_REF frontend=$FRONTEND_IMAGE_REF"

# Lint before deploy
helm lint "$HELM_CHART" -f "$VALUES_FILE"

# Deploy/upgrade via Helm
helm upgrade --install cistafirma "$HELM_CHART" \
  --namespace "$K8S_NAMESPACE" \
  --create-namespace \
  --values "$VALUES_FILE" \
  --set global.backendImage.repository="$BACKEND_IMAGE" \
  --set global.backendImage.tag="$DEPLOY_IMAGE_TAG" \
  --set global.frontendImage.repository="$FRONTEND_IMAGE" \
  --set global.frontendImage.tag="$DEPLOY_IMAGE_TAG" \
  --wait \
  --timeout 15m

# Rollout status checks
echo "Waiting for backend rollout..."
kubectl rollout status deployment/cistafirma-backend -n "$K8S_NAMESPACE" --timeout=600s
echo "Waiting for frontend rollout..."
kubectl rollout status deployment/cistafirma-frontend -n "$K8S_NAMESPACE" --timeout=600s

# Check Celery worker deployments
for worker in ruz orsr financials insurance default; do
  if kubectl get deployment "cistafirma-celery-${worker}" -n "$K8S_NAMESPACE" >/dev/null 2>&1; then
    echo "Waiting for celery-${worker} rollout..."
    kubectl rollout status deployment "cistafirma-celery-${worker}" -n "$K8S_NAMESPACE" --timeout=300s || true
  fi
done

echo "Helm deploy finished: env=$DEPLOY_ENV"
