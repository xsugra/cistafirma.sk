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

> **Toto je návod pre K8s cestu, ktorá nie je nasadená.** GitLab CI dnes žiadny
> image nestavia — stage `build` bol 15. 9. 2026 odstránený, lebo vyrábal
> obrazy, ktoré nič nečíta. Až keď bude existovať klaster, bude mať zmysel
> build vrátiť.

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

`kubectl` príkazy vyššie sú **lokálne** a patria k nenasadenej K8s ceste — bez
klastra neprejdú (`--dry-run=client` aj tak robí discovery voči API serveru).

CI flow je rozdelený do dvoch jobov, a to zámerne **do dvoch rôznych obrazov**:

- **`helm_render_validate`** (`alpine/helm:3.17.2`) – `helm lint` + oba rendery,
  ktoré odovzdá ako artefakt ďalej.
- **`helm_runtime_validate`** (`python:3.12-slim`) – spustí
  `scripts/k8s/validate_helm_runtime.py` nad oboma rendermi.

Rozdelenie nie je estetické: `alpine/helm` je holé Alpine s helmom a **python3
v ňom nie je**, takže kým bol skript súčasťou render jobu, job padal na
`exit 127` a kontrola sa nikdy nevykonala.

Job `helm_k8s_validate` (a s ním `STRICT_K8S_VALIDATION`) bol 15. 9. 2026
odstránený — nemal ako prejsť bez klastra a jeho obraz `bitnami/kubectl:1.30`
na Docker Hube ani neexistuje.
