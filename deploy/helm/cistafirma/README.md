# Helm chart: `cistafirma`

Produkcne orientovany Helm chart pre platformu `cistafirma.sk`.

## Co nasadzuje

- Django backend
- React/Vite frontend servovany cez nginx
- Celery worker
- Celery beat scheduler
- Kubernetes ingress
- Pre-install / pre-upgrade migracny job

## Secrets

Chart standardne ocakava existujuci Kubernetes Secret:

- `cistafirma-secrets`

Mal by obsahovat minimalne:

- `SECRET_KEY`
- `DATABASE_URL`
- volitelne Redis/Celery premenne, ak ich overrideujes v Secrete

Celery pody pouzivaju backend image a ocakavaju rovnaku app konfiguraciu plus Redis broker/backend cez premenne ako `REDIS_URL`, `CELERY_BROKER_URL` alebo `CELERY_RESULT_BACKEND`.

## Instalacne priklady

### Dev

```bash
helm upgrade --install cistafirma-dev . \
  -f values.yaml \
  -f values-dev.yaml \
  --namespace cistafirma-dev \
  --create-namespace \
  --wait --atomic
```

### Prod

```bash
helm upgrade --install cistafirma-prod . \
  -f values.yaml \
  -f values-prod.yaml \
  --namespace cistafirma \
  --create-namespace \
  --wait --atomic
```

## Image tagy v CI/CD

V GitLab CI odovzdaj buildnuty image tag cez `--set global.backendImage.tag=$CI_COMMIT_TAG` a `--set global.frontendImage.tag=$CI_COMMIT_TAG`.

## Bezpecny deploy flow pre DB

1. Urob backup DB.
2. Spusti Helm pre-upgrade migracny job.
3. Rolloutni backend a frontend.
4. Over readiness probe.

Tento postup chrani existujuce DB data a robi schema zmeny explicitnymi.

## Validacia

Pred aplikovanim chartu odporucane kontroly:

```bash
helm lint .
helm template cistafirma-dev . -f values.yaml -f values-dev.yaml --namespace cistafirma-dev > /tmp/cistafirma-dev-render.yaml
helm template cistafirma-prod . -f values.yaml -f values-prod.yaml --namespace cistafirma > /tmp/cistafirma-prod-render.yaml
kubectl apply --dry-run=client -f /tmp/cistafirma-dev-render.yaml
kubectl apply --dry-run=client -f /tmp/cistafirma-prod-render.yaml
kubectl apply --dry-run=server -f /tmp/cistafirma-dev-render.yaml
kubectl apply --dry-run=server -f /tmp/cistafirma-prod-render.yaml
```

V GitLab CI job `helm_render_validate` spusti `helm lint` a oba `helm template` rendery. Job `helm_k8s_validate` potom spusti oba `kubectl --dry-run=client` checky a, ak je dostupny validny `KUBE_CONFIG`, aj oba server dry-run checky. Ak nastavis `STRICT_K8S_VALIDATION=true`, job failne v pripade, ze server dry-run sa neda spustit.

CI flow je rozdeleny do dvoch jobov:

- `helm_render_validate`: lint + render + upload artefaktov
- `helm_k8s_validate`: client dry-run vzdy, server dry-run pri dostupnom cluster pristupe

