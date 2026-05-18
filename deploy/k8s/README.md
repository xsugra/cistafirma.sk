# Kubernetes nasadenie

Tento adresár obsahuje Kubernetes layout pre `cistafirma`, pripravený pre GitLab CI/CD.

## Štruktúra

| Cesta | Popis |
|---|---|
| `base/` | Spoločné manifesty (namespace, deploymenty, services, ingress, migračný job) |
| `overlays/dev` | Dev-specific zmeny (replicas, host) |
| `overlays/prod` | Produkčné zmeny (replicas, host) |
| `optional/postgres-statefulset.yaml` | Voliteľná šablóna in-cluster PostgreSQL |
| `secret.example.yaml` | Šablóna požadovaného Kubernetes Secretu |

## Povinný Secret

Pred prvým deployom vytvor `cistafirma-secrets` v namespace `cistafirma`:

```bash
kubectl apply -f deploy/k8s/secret.example.yaml
```

Potom nahraď placeholder hodnoty reálnymi secretmi vo vlastnom secure workflow (nikdy necommituj reálne tajomstvá).

## CI/CD flow

Pipeline v [`.gitlab-ci.yml`](../../.gitlab-ci.yml) robí:

1. Validate (Python compile + frontend build + Helm lint + K8s dry-run).
2. Backend testy.
3. Docker image build/push (backend + frontend).
4. Deploy via `scripts/k8s/deploy.sh`.

Branch/tag stratégia:

- `dev` branch → automatický deploy do dev overlay.
- `v*` tagy → manuálny deploy do prod overlay.

## Bezpečná migračná stratégia DB

`deploy.sh` spúšťa dedikovaný Kubernetes migračný job **pred** rolloutom deploymentov.

Poradie:

1. Voliteľný DB backup.
2. Spustenie migračného jobu (`python manage.py migrate` + `collectstatic`).
3. Aplikovanie app overlay manifestov.
4. Čakanie na backend/frontend rollout status.

Tento postup chráni existujúce DB dáta a bráni spusteniu app podov proti zastaranej schéme.

## Manuálne operácie

### Nasadenie

```bash
export BACKEND_IMAGE=registry.example.com/group/project/backend
export FRONTEND_IMAGE=registry.example.com/group/project/frontend
export DEPLOY_IMAGE_TAG=v1.0.0
export DEPLOY_ENV=prod
export K8S_NAMESPACE=cistafirma

scripts/k8s/deploy.sh
```

### Iba migrácia

```bash
export BACKEND_IMAGE_REF=registry.example.com/group/project/backend:v1.0.0
export K8S_NAMESPACE=cistafirma

scripts/k8s/migrate.sh
```

### Rollback deploymentu

```bash
export K8S_NAMESPACE=cistafirma
scripts/k8s/rollback.sh
```

### DB backup / restore

```bash
export DB_HOST=postgres-host
export DB_PORT=5432
export DB_NAME=cistafirma
export DB_USER=cistafirma
export DB_PASSWORD=secret

scripts/k8s/backup_postgres.sh
```

```bash
export DB_HOST=postgres-host
export DB_PORT=5432
export DB_NAME=cistafirma
export DB_USER=cistafirma
export DB_PASSWORD=secret
export BACKUP_FILE=./backups/cistafirma_YYYYMMDD_HHMMSS.dump

scripts/k8s/restore_postgres.sh
```

## Poznámky

- Aktuálny backend image entrypoint používa gunicorn a očakáva env z secret/configmap.
- Ak používaš managed DB (odporúčané pre produkciu), nechaj `optional/postgres-statefulset.yaml` vypnutý.
- DB migrácie drž backward-compatible počas rolling update.
- Kompletný operačný runbook (deploy/rollback/incident): [`docs/DEPLOYMENT_RUNBOOK.md`](../../docs/DEPLOYMENT_RUNBOOK.md).
