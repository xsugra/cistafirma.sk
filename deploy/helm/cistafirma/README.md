# Helm chart: `cistafirma`

Produkčne orientovaný Helm chart pre platformu `cistafirma.sk`.

## Čo nasadzuje

- Django backend (gunicorn).
- React/Vite frontend servovaný cez nginx.
- Celery worker (queues: `ruz_full`, `orsr`, `financials`, `insurance`, `celery`).
- Celery beat scheduler.
- Kubernetes ingress.
- Pre-install / pre-upgrade migračn�� job.

## Secrets

Chart štandardne očakáva existujúci Kubernetes Secret:

- `cistafirma-secrets`

Mal by obsahovať minimálne:

- `SECRET_KEY`
- `DATABASE_URL`
- Voliteľne Redis/Celery premenné, ak ich overrideuješ v Secrete.

Celery pody používajú backend image a očakávajú rovnakú app konfiguráciu plus Redis broker/backend cez premenné ako `REDIS_URL`, `CELERY_BROKER_URL` alebo `CELERY_RESULT_BACKEND`.

## Inštalačné príklady

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

V GitLab CI odovzdaj buildnutý image tag cez `--set global.backendImage.tag=$CI_COMMIT_TAG` a `--set global.frontendImage.tag=$CI_COMMIT_TAG`.

## Bezpečný deploy flow pre DB

1. Urob backup DB.
2. Spusti Helm pre-upgrade migračný job.
3. Rolloutni backend a frontend.
4. Over readiness probe.

Tento postup chráni existujúce DB dáta a robí schéma zmeny explicitnými.

## Validácia

Pred aplikovaním chartu odporúčané kontroly:

```bash
helm lint .
helm template cistafirma-dev . -f values.yaml -f values-dev.yaml --namespace cistafirma-dev > /tmp/cistafirma-dev-render.yaml
helm template cistafirma-prod . -f values.yaml -f values-prod.yaml --namespace cistafirma > /tmp/cistafirma-prod-render.yaml
kubectl apply --dry-run=client -f /tmp/cistafirma-dev-render.yaml
kubectl apply --dry-run=client -f /tmp/cistafirma-prod-render.yaml
kubectl apply --dry-run=server -f /tmp/cistafirma-dev-render.yaml
kubectl apply --dry-run=server -f /tmp/cistafirma-prod-render.yaml
```

V GitLab CI job `helm_render_validate` spustí `helm lint` a oba `helm template` rendery. Job `helm_k8s_validate` potom spustí oba `kubectl --dry-run=client` checky a, ak je dostupný validný `KUBE_CONFIG`, aj oba server dry-run checky. Ak nastavíš `STRICT_K8S_VALIDATION=true`, job failne v prípade, že server dry-run sa nedá spustiť.

CI flow je rozdelený do dvoch jobov:

- **`helm_render_validate`** – lint + render + upload artefaktov.
- **`helm_k8s_validate`** – client dry-run vždy, server dry-run pri dostupnom cluster prístupe.
