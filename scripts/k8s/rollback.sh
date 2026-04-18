#!/usr/bin/env sh
set -eu

K8S_NAMESPACE=${K8S_NAMESPACE:-cistafirma}

kubectl rollout undo deployment/cistafirma-backend -n "$K8S_NAMESPACE"
kubectl rollout undo deployment/cistafirma-frontend -n "$K8S_NAMESPACE"

kubectl rollout status deployment/cistafirma-backend -n "$K8S_NAMESPACE" --timeout=600s
kubectl rollout status deployment/cistafirma-frontend -n "$K8S_NAMESPACE" --timeout=600s

echo "Rollback finished for namespace: $K8S_NAMESPACE"

