# Kubernetes nasadenie

> ⚠️ **NENASADENÉ — nepostupuj podľa tohto dokumentu.** Ani táto cesta, ani Helm
> chart v [`deploy/helm/cistafirma/`](../helm/cistafirma/) dnes nebežia, lebo
> **neexistuje klaster**. Produkcia beží na serveri `dell` cez `docker compose`
> z koreňa repa (viď `CLAUDE.md` → „Where production runs").
>
> **Oprava 2026-09-18** (konsolidácia dokumentácie, #169). Dovtedy tu stálo, že
> „CI/CD od verzie 0.41+ používa Helm chart" a že tieto manifesty „už nie sú
> udržiavané". Ani jedno nebolo pravda:
>
> - **„verzia 0.41+" neexistuje.** `Chart.yaml` má `version: 0.1.0` a
>   `appVersion: "0.40.0"`; reťazec `0.41` sa v repozitári nevyskytuje nikde.
> - **Žiadny „aktuálny deploy flow" neexistuje.** `.gitlab-ci.yml` má stages len
>   `validate` a `test` — žiadny build, žiadny deploy, žiadny klaster.
>   `scripts/k8s/helm-deploy.sh` je odkazovaný **výhradne z tohto README**
>   (`git grep -ln 'helm-deploy\.sh'` → `deploy/k8s/README.md`).
> - **Udržiavané naopak sú.** Naposledy ich zmenil commit `eb22b41`
>   (2026-09-17): `base/frontend-deployment.yaml` (+14) a
>   `scripts/k8s/deploy.sh` (+14) — a to práve kvôli povinnému
>   `BACKEND_RESOLVER` opísanému nižšie.

---

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

**Táto sekcia bola do 2026-09-18 nepravdivá a celá sa prepisuje.** Opisovala
build/push obrazov, automatický deploy z vetvy `dev` a manuálny deploy z tagov
`v*`. Nič z toho v pipeline nie je a nikdy nebolo spustené proti klastru.

Čo [`.gitlab-ci.yml`](../../.gitlab-ci.yml) naozaj robí:

```
stages:
  - validate
  - test
```

To je celé — sedem jobov, žiadny `build`, žiadny `deploy`. Obrazy sa
**nestavajú v CI vôbec**: produkcia na `dell` stavia zo `build:` kontextu
`docker-compose.yml`. Stage `build` bol odstránený 2026-09-15 (`422addf`), lebo
vyrábal obrazy, ktoré nič nečíta.

Deploy je dnes **manuálny krok na `dell`** — `git pull gitlab-home <vetva>`,
`docker compose up -d --build`, `migrate`. Žiadny tag, žiadny overlay, žiadny
klaster. Viď [`docs/DEVOPS_CICD.md`](../../docs/DEVOPS_CICD.md).

> Až keď bude existovať klaster, bude mať zmysel sem vrátiť build aj deploy —
> dovtedy je celá táto cesta návod bez adresáta.

## Bezpečná migračná stratégia DB

`deploy.sh` spúšťa dedikovaný Kubernetes migračný job **pred** rolloutom deploymentov.

Poradie (`scripts/k8s/deploy.sh`):

1. Voliteľný DB backup — beží **len** ak `RUN_DB_BACKUP=true` a sú nastavené
   `pg_dump` + `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`. Inak skript
   vypíše `WARNING: ... Skipping backup` a **pokračuje ďalej** (riadky 35–42).
   Ak chceš backup ako podmienku, over si, že sa naozaj spustil.
2. `namespace.yaml` + `configmap.yaml`, potom migračný job
   (`python manage.py migrate`).
3. Aplikovanie app overlay manifestov.
4. Čakanie na backend/frontend rollout status.

Tento postup chráni existujúce DB dáta a bráni spusteniu app podov proti zastaranej schéme.

## Manuálne operácie

### Nasadenie

`BACKEND_RESOLVER` **je povinný** — skript bez neho skončí s `exit 1`
(`scripts/k8s/deploy.sh:23-28`). Je to adresa clusterového DNS pre nginx vo
frontend pody a odvodiť sa nedá, každý klaster má inú.

```bash
export BACKEND_IMAGE=registry.example.com/group/project/backend
export FRONTEND_IMAGE=registry.example.com/group/project/frontend
export DEPLOY_IMAGE_TAG=v1.0.0
export DEPLOY_ENV=prod
export K8S_NAMESPACE=cistafirma
export BACKEND_RESOLVER=10.96.0.10   # kubeadm/kind; k3s má 10.43.0.10

scripts/k8s/deploy.sh
```

Over si ju pre svoj klaster:

```bash
kubectl -n kube-system get svc kube-dns -o jsonpath='{.spec.clusterIP}'
```

### Iba migrácia

```bash
export BACKEND_IMAGE_REF=registry.example.com/group/project/backend:v1.0.0
export K8S_NAMESPACE=cistafirma

scripts/k8s/migrate.sh
```

> **`migrate.sh` nerobí to, čo `deploy.sh`.** Aplikuje len `namespace.yaml`
> a `migrate-job.yaml` (`scripts/k8s/migrate.sh:23,25`) — **`configmap.yaml`
> neaplikuje**, hoci `deploy.sh:64` áno. Ak migračný job potrebuje configmap,
> musí už v namespace existovať; inak job narazí na chýbajúci ConfigMap
> a `kubectl wait` zlyhá na timeoute.

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

> ⚠️ **`restore_postgres.sh` je deštruktívny a nemá poistku.**
> Spúšťa `pg_restore --clean --if-exists` (`scripts/k8s/restore_postgres.sh:17-26`)
> proti databáze, ktorú mu dáš cez `DB_*` — teda `--clean` **zahodí existujúce
> objekty** v cieli. Skript nemá `--dry-run`, nepotvrdzuje cieľ a neoveruje, či
> mieri na živú produkciu. V tomto repozitári plati
> **„nikdy nerob restore nad bežiacou databázou `cistafirma`"** (`CLAUDE.md`,
> `docs/DATA_PROTECTION.md`) — restore drill patrí do izolovaného kontajnera,
> viď `make db-restore-drill`.

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
- Kompletný operačný runbook (deploy/rollback/incident):
  [`docs/DEPLOYMENT_RUNBOOK.md`](../../docs/DEPLOYMENT_RUNBOOK.md) — **opisuje
  tú istú nenasadenú K8s cestu a nesmie sa podľa neho postupovať, kým klaster
  neexistuje.** Pre dnešnú produkciu platí `docs/DEVOPS_CICD.md` a `CLAUDE.md`.
- Kontrakt tej istej nenasadenej cesty: [`docs/DEPLOYMENT_CONTRACT.md`](../../docs/DEPLOYMENT_CONTRACT.md).
