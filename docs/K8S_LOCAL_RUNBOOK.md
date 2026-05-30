# Lokálny k8s runbook (Docker Desktop)

Prevádzkový manuál pre lokálne Kubernetes prostredie `cistafirma` na Docker Desktop.
Pokrýva re-setup po strate dát, spustenie synchronizácií, monitoring a zálohovanie.

## Architektúra

```
cistafirma namespace
├── postgres (StatefulSet, 10 Gi PVC)
├── redis (Deployment, 1 Gi PVC)
├── backend (Deployment, gunicorn :8000)
├── frontend (Deployment, nginx :80)
├── celery-beat (Deployment, 1 replica)
├── celery-ruz (Deployment, 1 replica)          queue: ruz_full
├── celery-orsr (Deployment, 1 replica)         queue: orsr
├── celery-financials (Deployment, 1 replica)   queue: financials
├── celery-insurance (Deployment, 1 replica)    queue: insurance
├── celery-default (Deployment, 1 replica)      queue: celery
└── postgres-backup (CronJob 0 3 * * *, 5 Gi PVC)
```

Image-y sa pullujú z lokálneho registra `172.18.0.10:5000` (kontajner `kind-registry` na `kind` sieti).

## Prerekvizity

- Docker Desktop spustený, Kubernetes zapnutý (Settings → Kubernetes → Enable).
- `kubectl config current-context` → `docker-desktop`.
- Alokované resources v DD: min. 8 GB RAM, 4 CPU, 40 GB disk.
- Nainštalované: `kubectl`, `helm`.

## Prvý setup (fresh install)

```bash
# z root adresara projektu

# 1. Lokálny registry (ak ešte nebeží)
docker run -d --restart=always -p 127.0.0.1:5001:5000 --network kind --name kind-registry registry:2 || true

# 2. Build image-ov
docker build -t cistafirma-backend:local ./backend
docker build -t cistafirma-frontend:local -f ./frontend/Dockerfile.prod ./frontend

# 3. Push do lokálneho registra
docker tag cistafirma-backend:local localhost:5001/cistafirma-backend:local
docker tag cistafirma-frontend:local localhost:5001/cistafirma-frontend:local
docker push localhost:5001/cistafirma-backend:local
docker push localhost:5001/cistafirma-frontend:local

# 4. Namespace + Secret (iba prvýkrát)
kubectl create namespace cistafirma --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f deploy/k8s/secret.example.yaml

# 5. Helm install
helm upgrade --install cistafirma deploy/helm/cistafirma \
  -f deploy/helm/cistafirma/values-dev.yaml \
  --namespace cistafirma --wait --timeout 10m

# 6. Superuser (iba prvýkrát)
kubectl exec -n cistafirma deployment/cistafirma-cistafirma-backend -- sh -c "
  DJANGO_SUPERUSER_USERNAME=admin \
  DJANGO_SUPERUSER_EMAIL=admin@local \
  DJANGO_SUPERUSER_PASSWORD=admin \
  python manage.py createsuperuser --noinput --settings=backend.settings
"
```

## Rebuild a upgrade

```bash
# Po zmene kódu:
docker build -t cistafirma-backend:local ./backend
docker tag cistafirma-backend:local localhost:5001/cistafirma-backend:local
docker push localhost:5001/cistafirma-backend:local

# Reštart všetkých deployov používajúcich backend image:
kubectl rollout restart -n cistafirma \
  deployment/cistafirma-cistafirma-backend \
  deployment/cistafirma-cistafirma-celery-beat \
  deployment/cistafirma-cistafirma-celery-ruz \
  deployment/cistafirma-cistafirma-celery-orsr \
  deployment/cistafirma-cistafirma-celery-financials \
  deployment/cistafirma-cistafirma-celery-insurance \
  deployment/cistafirma-cistafirma-celery-default
```

## Prístup k aplikácii

```bash
# Backend + admin na http://127.0.0.1:8080
kubectl port-forward -n cistafirma svc/cistafirma-cistafirma-backend 8080:8000

# Frontend na http://127.0.0.1:5173
kubectl port-forward -n cistafirma svc/cistafirma-cistafirma-frontend 5173:80
```

- Admin: http://127.0.0.1:8080/admin/  (admin/admin)
- Sync Dashboard: http://127.0.0.1:8080/admin/ → "Manual Sync Dashboard"
- Healthcheck: http://127.0.0.1:8080/healthz/

## Spustenie synchronizácie po fresh installe

Odporúčané poradie (rešpektuje závislosti):

### Fáza A — RUZ full sync (sekvenčná, ~hodiny)

Vytvorí `Company` záznamy (iba táto fáza zapisuje do `companies_company`).

```bash
# Cez admin:
# http://127.0.0.1:8080/admin/registers/syncprogress/trigger/full/
# Alebo cez celery shell:
kubectl exec -n cistafirma deployment/cistafirma-cistafirma-backend -- \
  python manage.py shell --settings=backend.settings -c \
  "from registers.tasks import start_full_ruz_sync; start_full_ruz_sync.delay()"
```

Sleduj progress:

```bash
kubectl logs -n cistafirma deployment/cistafirma-cistafirma-celery-ruz -f --tail=50
```

### Fáza B — ORSR + Financials + Insurance (paralelne, per-company)

Dá sa spustiť buď cez sync dashboard (tlačidlo "Spustiť ORSR + Financials") alebo:

```bash
kubectl exec -n cistafirma deployment/cistafirma-cistafirma-backend -- \
  python manage.py shell --settings=backend.settings -c "
from registers.tasks import schedule_missing_orsr_sync, schedule_ruz_financials_sync, force_check_all_companies_debts
schedule_missing_orsr_sync.delay(limit=10000)
schedule_ruz_financials_sync.delay(limit=10000, missing_only=True)
force_check_all_companies_debts.delay()
"
```

Každá queue beží vo svojom workeri, takže všetky tri idú paralelne.

## Monitoring

```bash
# Stav podov
kubectl get pods -n cistafirma

# Živé logy konkrétneho workera
kubectl logs -n cistafirma deployment/cistafirma-cistafirma-celery-ruz -f
kubectl logs -n cistafirma deployment/cistafirma-cistafirma-celery-orsr -f
kubectl logs -n cistafirma deployment/cistafirma-cistafirma-celery-financials -f
kubectl logs -n cistafirma deployment/cistafirma-cistafirma-celery-insurance -f

# Celery task queue dĺžka v Redise
kubectl exec -n cistafirma deployment/cistafirma-cistafirma-redis -- redis-cli LLEN ruz_full
kubectl exec -n cistafirma deployment/cistafirma-cistafirma-redis -- redis-cli LLEN orsr
kubectl exec -n cistafirma deployment/cistafirma-cistafirma-redis -- redis-cli LLEN financials
kubectl exec -n cistafirma deployment/cistafirma-cistafirma-redis -- redis-cli LLEN insurance

# Počet firiem v DB
kubectl exec -n cistafirma cistafirma-cistafirma-postgres-0 -- \
  psql -U cistafirma -d cistafirma -c 'SELECT count(*) FROM "Companies and SZCO";'
```

## Škálovanie workerov

```bash
# Zvýšiť ORSR scrapery (pozor na rate limit orsr.sk):
kubectl scale -n cistafirma deployment/cistafirma-cistafirma-celery-orsr --replicas=3

# Alebo cez Helm hodnotu (perzistentne):
# V values-dev.yaml zvýš celery.workers.orsr.replicaCount a spusti helm upgrade.
```

## Backup & restore

CronJob `cistafirma-cistafirma-postgres-backup` robí denne o 03:00 `pg_dump` do `cistafirma-cistafirma-backup` PVC, retention 7 dní.

### Manuálne vynútiť backup

```bash
kubectl create job -n cistafirma --from=cronjob/cistafirma-cistafirma-postgres-backup backup-manual-$(date +%s)
```

### Vytiahnutie backupu na host

```bash
POD=$(kubectl get pods -n cistafirma -l app.kubernetes.io/component=backup -o jsonpath='{.items[0].metadata.name}')
FILE=$(kubectl exec -n cistafirma "$POD" -- sh -c "ls -t /backups/*.dump | head -1")
kubectl cp "cistafirma/${POD}:${FILE}" "./backups/$(basename "$FILE")"
```

### Restore

```bash
# 1. Skopíruj dump do postgres podu
kubectl cp ./backups/cistafirma_YYYYMMDD_HHMMSS.dump cistafirma/cistafirma-cistafirma-postgres-0:/tmp/restore.dump

# 2. Spusti restore (DESTRUKTÍVNE, prepíše DB)
kubectl exec -n cistafirma cistafirma-cistafirma-postgres-0 -- \
  sh -c "pg_restore -U cistafirma -d cistafirma --clean --if-exists /tmp/restore.dump"
```

## Cleanup

```bash
# Zastaviť stack (dáta ostanú v PVC):
helm uninstall cistafirma -n cistafirma

# Úplne zmazať (POZOR — prídeš o všetky dáta):
kubectl delete namespace cistafirma
kubectl delete pvc -n cistafirma --all  # už zmazané cez ns
```

## Troubleshooting

| Symptóm | Príčina | Riešenie |
|---|---|---|
| `ErrImagePull` | Lokálny registry nebeží alebo image nebol pushnutý | Skontroluj `docker ps --filter name=kind-registry`, re-push |
| Pod v `CrashLoopBackOff` s `OperationalError` v logoch | Postgres ešte nebol ready pri štarte | InitContainer by mal čakať; skontroluj `kubectl logs -c wait-for-...` |
| Celery worker konzumuje inú queue ako očakávaš | Stará verzia taskov v Redise | `kubectl exec -n cistafirma deployment/cistafirma-cistafirma-redis -- redis-cli FLUSHDB` |
| RUZ full sync sa zasekol | Rate-limit / network / timeout | Admin → Sync Progress → Resume, alebo `resume_full_ruz_sync.delay()` |
| Backup PVC `Pending` | Zatiaľ nebol spustený žiaden CronJob run | Normálne; PVC sa Bind-ne pri prvom backup jobe |
