# Kubernetes nasadenie

Tento adresar obsahuje Kubernetes layout pre `cistafirma`, pripraveny pre GitLab CI/CD.

## Struktura

- `base/`: spolocne manifesty (namespace, deploymenty, services, ingress, migracny job)
- `overlays/dev`: dev-specific zmeny (replicas, host)
- `overlays/prod`: produkcne zmeny (replicas, host)
- `optional/postgres-statefulset.yaml`: volitelna sablona in-cluster PostgreSQL
- `secret.example.yaml`: sablona pozadovaneho Kubernetes Secretu

## Povinny Secret

Pred prvym deployom vytvor `cistafirma-secrets` v namespace `cistafirma`.

```bash
kubectl apply -f deploy/k8s/secret.example.yaml
```

Potom nahrad placeholder hodnoty realnymi secretmi vo vlastnom secure workflow (nikdy necommituj realne tajomstva).

## CI/CD flow

Pipeline v [`.gitlab-ci.yml`](../../.gitlab-ci.yml) robi:

1. validate (python compile + frontend build)
2. backend tests
3. Docker image build/push (backend + frontend)
4. deploy via `scripts/k8s/deploy.sh`

Branch/tag strategia:

- `dev` branch -> automaticky deploy do dev overlay
- `v*` tagy -> manualny deploy do prod overlay

## Bezpecna migracna strategia DB

`deploy.sh` spusta dedikovany Kubernetes migracny job **pred** rolloutom deploymentov.

Poradie migracie:

1. volitelny DB backup
2. spustenie migracneho jobu (`python manage.py migrate` + `collectstatic`)
3. aplikovanie app overlay manifestov
4. cakanie na backend/frontend rollout status

Tento postup chrani existujuce DB data a brani spusteniu app podov proti zastaranej schemme.

## Manualne operacie

### Nasadenie

```bash
export BACKEND_IMAGE=registry.example.com/group/project/backend
export FRONTEND_IMAGE=registry.example.com/group/project/frontend
export DEPLOY_IMAGE_TAG=v1.0.0
export DEPLOY_ENV=prod
export K8S_NAMESPACE=cistafirma

scripts/k8s/deploy.sh
```

### Iba migracia

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

## Poznamky

- Aktualny backend image entrypoint pouziva gunicorn a ocakava env z secret/configmap.
- Ak pouzivas managed DB (odporucane pre produkciu), nechaj `optional/postgres-statefulset.yaml` vypnuty.
- DB migracie drz backward-compatible pocas rolling update.
- Kompletny operator runbook (deploy/rollback/incident): [`docs/DEPLOYMENT_RUNBOOK.md`](../../docs/DEPLOYMENT_RUNBOOK.md)

