#!/usr/bin/env sh
# Spustí lokálny docker registry pripojený na DD k8s "kind" sieť,
# aby DD Kubernetes mohol pullovať image-y bez použitia rozbiteho
# interného registry-mirror.
#
# Usage: ./scripts/k8s/local_registry.sh
set -eu

REG_NAME=${REG_NAME:-kind-registry}
REG_PORT=${REG_PORT:-5001}
REG_NETWORK=${REG_NETWORK:-kind}

if [ -n "$(docker ps -q --filter name=^${REG_NAME}$)" ]; then
  echo "Registry ${REG_NAME} už beží."
  exit 0
fi

if [ -n "$(docker ps -aq --filter name=^${REG_NAME}$)" ]; then
  echo "Registry ${REG_NAME} existuje, štartujem..."
  docker start "${REG_NAME}"
  exit 0
fi

echo "Spúšťam registry ${REG_NAME} na porte ${REG_PORT}, sieť ${REG_NETWORK}..."
docker run -d \
  --restart=always \
  -p "127.0.0.1:${REG_PORT}:5000" \
  --network "${REG_NETWORK}" \
  --name "${REG_NAME}" \
  registry:2

IP=$(docker inspect "${REG_NAME}" --format "{{.NetworkSettings.Networks.${REG_NETWORK}.IPAddress}}")
echo "Registry bežiaci na:"
echo "  host:       localhost:${REG_PORT}"
echo "  cluster:    ${IP}:5000"
echo ""
echo "Push example:"
echo "  docker tag cistafirma-backend:local localhost:${REG_PORT}/cistafirma-backend:local"
echo "  docker push localhost:${REG_PORT}/cistafirma-backend:local"
echo ""
echo "V Helm values.yaml použi:"
echo "  global.backendImage.repository: ${IP}:5000/cistafirma-backend"
