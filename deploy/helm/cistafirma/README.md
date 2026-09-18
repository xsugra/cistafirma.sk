# Helm chart: `cistafirma`

> ⚠️ **NENASADENÝ — nepostupuj podľa tohto dokumentu.** Chart je pripravený, ale
> **neexistuje klaster, do ktorého by sa dal nasadiť**. Produkcia beží na serveri
> `dell` cez `docker compose` z koreňa repa (viď `CLAUDE.md`). Toto je
> **kontrakt pre budúcu K8s cestu**, nie opis dnešného stavu — rovnaké
> upozornenie má [`docs/DEPLOYMENT_CONTRACT.md`](../../../docs/DEPLOYMENT_CONTRACT.md).
>
> **Oprava 2026-09-18** (konsolidácia dokumentácie, #169): šesť tvrdení nižšie
> bolo nepravdivých alebo zastaraných a sú prepísané — migračný job je
> `post-install,post-upgrade` (nie pre-install), zoznam kľúčov v Secrete je
> neúplný, `REDIS_URL` nie je voliteľný, prod inštalácia potrebuje aj image
> repozitáre a `CI_COMMIT_TAG` v CI neexistuje. Detaily sú pri jednotlivých
> miestach.

## Čo nasadzuje

Chart defaultne nasadzuje (`helm template` renderuje 22 objektov):

- Django backend (gunicorn) + Service + init kontajner čakajúci na `migrate --check`.
- React/Vite frontend servovaný cez nginx.
- Celery worker (queues: `ruz_full`, `orsr`, `financials`, `insurance`, `celery`).
- Celery beat scheduler.
- Kubernetes ingress.
- **Post-install / post-upgrade migračný job** (beží *po* aplikovaní manifestov, nie pred nimi — viď „Bezpečný deploy flow" nižšie).
- **In-cluster Postgres StatefulSet s PVC** (`postgres.enabled: true`) a **Redis** (`redis.enabled: true`).
- **Denný `pg_dump` CronJob do backup PVC** (`backup.enabled: true`, `0 3 * * *`, retencia 14 dní).
- **PodDisruptionBudget** pre backend aj frontend (`pdb.enabled: true`).

Posledné štyri tu do 2026-09-18 uvedené neboli, hoci ich chart nasadzuje
defaultne — a pre sekciu „Bezpečný deploy flow pre DB" sú podstatné: chart má
**vlastný** záložný mechanizmus, ktorý tam nebol spomenutý.

## Secrets

Chart štandardne očakáva existujúci Kubernetes Secret:

- `cistafirma-secrets`

**Musí obsahovať všetkých päť kľúčov**, ktoré šablóny čítajú:

| Kľúč | Kto ho číta |
|---|---|
| `SECRET_KEY` | backend, celery, migrate job |
| `DATABASE_URL` | backend, celery, migrate job |
| `POSTGRES_DB` | `templates/postgres-statefulset.yaml`, `templates/backup-cronjob.yaml` |
| `POSTGRES_USER` | tamtiež |
| `POSTGRES_PASSWORD` | tamtiež |

Tri `POSTGRES_*` kľúče treba len kým je `postgres.enabled` / `backup.enabled`
true (oba sú default). Pri managed DB ich vypneš spolu s týmito dvoma —
pozor, `backup-cronjob` ich číta tiež.

**`REDIS_URL` je povinný, nie voliteľný.** `templates/celery-worker-deployment.yaml:43`
ho číta v init kontajneri v neohraničenej slučke `until …; do … sleep 2; done`.
Bez neho padne `KeyError`, chyba je potlačená (`2>/dev/null`) a init kontajner
sa zacyklí navždy s textom „Waiting for Redis...". Chart pritom **vlastný Redis
nasadzuje, ale žiadna šablóna jeho adresu nezapája** — meno
`<release>-cistafirma-redis` sa v renderi mimo `redis.yaml` nevyskytuje ani raz.
Hodnotu teda musíš dodať sám, napr.
`REDIS_URL=redis://<release>-cistafirma-redis:6379/0`.

## `frontend.backendResolver` — jediná hodnota, ktorá sa nedá odvodiť

Frontend má nginx, ktorý prekladá meno backendu **za behu** (`resolve` +
`resolver` v `frontend/nginx.conf.template`). To je oprava výpadku z 17. 9. 2026,
keď si nginx preložil adresu raz pri štarte a po rekreovaní backendu na ňu
ukazoval ešte 3 h 43 min.

Meno backendu si chart počíta sám (`cistafirma.backendUpstream` z `fullname`),
takže sa nemôže rozísť s Service, ktorý naozaj vytvára. **Adresu resolvera ale
odvodiť nevie** — je vlastnosť klastra, nie chartu:

| klaster | adresa |
|---|---|
| kubeadm, kind | `10.96.0.10` |
| k3s | `10.43.0.10` |

Over si ju pre svoj klaster:

```bash
kubectl -n kube-system get svc kube-dns -o jsonpath='{.spec.clusterIP}'
```

`values-dev.yaml` ju má vyplnenú (lokálny kind). `values-prod.yaml` ju **nemá**,
a to je zámer: neexistuje klaster, ktorému by patrila. Kým sa nedoplní, frontend
pod do produkcie nenabehne — nginx odmietne štart s `no name servers defined`.
To je hlasité zlyhanie, ktoré menuje samo seba; vymyslená adresa by vracala 502
na každej požiadavke a pod by sa pritom hlásil ako zdravý, lebo jeho probe je
voči backendu zámerne slepý. Rozdiel medzi tými dvoma je celý zmysel tohto
nastavenia.

`backendResolver` ale **nie je jediná chýbajúca hodnota** v prod ceste.
`values-prod.yaml` nastavuje len `tag`, nikdy `repository`, takže
`helm template cistafirma-prod` vyrenderuje
`image: registry.example.com/cistafirma/backend:latest` — placeholder, ktorý
`.gitlab-ci.yml:201-203` sám nazýva neexistujúcim. Prod inštalácia preto
potrebuje aj `global.backendImage.repository` a `global.frontendImage.repository`
(presne to robí `scripts/k8s/helm-deploy.sh:47-50` cez `--set`).

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
  --set global.backendImage.repository=<registry>/<cesta>/backend \
  --set global.frontendImage.repository=<registry>/<cesta>/frontend \
  --set frontend.backendResolver=<IP clusterového DNS> \
  --wait --atomic
```

## Image tagy

> **Manuálny krok pre budúcu K8s cestu.** GitLab CI dnes žiadny image nestavia —
> stage `build` bol 15. 9. 2026 odstránený, lebo vyrábal obrazy, ktoré nič nečíta.

Tag odovzdaj cez `--set global.backendImage.tag=<tag>` a
`--set global.frontendImage.tag=<tag>`.

`$CI_COMMIT_TAG` **v dnešnej pipeline neexistuje** — premennú definuje len tag
pipeline a project má jedinú pipeline s tagmi zakázanými. Keby build job niekedy
vznikol, musí ju odovzdať explicitne.

## Bezpečný deploy flow pre DB

1. Urob backup DB (vlastný, alebo spoľahni na `pg_dump` CronJob chartu — viď „Čo nasadzuje").
2. `helm upgrade --install … --wait --atomic`.
3. Deploymenty sa dostanú do ready — backend čaká na `manage.py migrate --check`.
4. **Až potom** dobehne migračný job ako `post-upgrade` hook.

Tým je poradie **rollout → migrácia**, opačne, než tu stálo do 2026-09-18
(„2. migračný job, 3. rollout"). Vychádza z `helm.sh/hook: post-install,post-upgrade`
v `templates/migrate-job.yaml:10` a z `--wait`, ktorý README odporúča vyššie:
Helm najprv aplikuje a nechá dobehnúť Deploymenty a hook spustí až potom.

Dôsledok, ktorý treba poznať: `--wait` **zlyhá**, ak schéma ešte nie je
aplikovaná, lebo backend init kontajner drží `migrate --check` v slučke
(`templates/backend-deployment.yaml:38`). Pri zámene schém je to správne
hlasité zlyhanie; pri prvej inštalácii do prázdneho klastra to znamená, že
prvý `--wait` beh neprejde.

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

## Otvorené, neopravené

- `Chart.yaml:3` — `description: Production-ready Helm chart …`: „production
  ready" bez kvalifikátora, ktorý zvyšok repozitára má. Chart ako celok rozdiel
  netají (toto README aj `docs/DEPLOYMENT_CONTRACT.md` ho priznávajú), ale ten
  riadok je holé tvrdenie.
- `Chart.yaml:6` — `appVersion: "0.40.0"`. Jediný ďalší výskyt `0.40.0`
  v repozitári je `.gitignore:70`; `frontend/package.json` má `0.0.0`. Číslo
  teda nemá oporu v žiadnom verzovacom zdroji.
