# DevOps / CI·CD dokumentácia

Tento dokument popisuje **skutočný** release a deployment tok projektu
`cistafirma` — nie cieľový stav. Pre K8s/Helm budúcnosť (ktorá dnes
nenasadená nie je a vedome sme ju odložili) platí
[`DEPLOYMENT_CONTRACT.md`](DEPLOYMENT_CONTRACT.md); tento dokument opisuje, čo
beží.

## Rozdelenie strojov

| Stroj | Rola |
|---|---|
| **Mac** (MacBook) | Iba vývoj. **Nemá GitLab runner** — bol odstránený 15. 9. 2026. |
| **lenovo** | Beží GitLab (`https://sam-lenovo.taildb03cf.ts.net`; starý `http://gitlab.home.arpa:8088` už len presmerúva na https) **aj CI runner**, ktorý spúšťa joby. |
| **dell** | Produkcia. Beží `docker-compose.yml` + `docker-compose.prod.yml`. **Zámerne bez runnera.** |

Prečo dell nemá runner: je to produkcia s neopraviteľným volume
`cistafirma_postgres_data`, bežia tam rate-limitované Celery workery a runner
s prístupom k Docker socketu by len rozšíril útočnú plochu o stroj, na ktorom
záleží najviac. Build ani deploy tam nepotrebujeme — pozri „Prečo tu nie je
build ani deploy".

## Git stratégia

- `main` – produkčne pripravená vetva.
- `dev` – integračná vetva pre aktívny vývoj.
- Release cez tagy: `vX.Y.Z`.

Odporúčané názvy vetiev:

- `feature/<scope>-<name>`
- `hotfix/<scope>-<name>`

Promočný model:

1. Feature → merge do `dev`.
2. Testovanie v dev prostredí.
3. Merge `dev` → `main`.
4. Vytvorenie tagu `vX.Y.Z` na `main`.

**Nasadenie je manuálny krok** — pozri „Ako sa dnes nasadzuje".

## Fázy pipeline

Definované v [`.gitlab-ci.yml`](../.gitlab-ci.yml). Sú dve, a to je celé:

1. **`validate`**
   - `backend_validate` – `python -m compileall backend` v `python:3.12-slim`.
   - `frontend_validate` – `npm ci && npm run build` v `node:20-alpine`.
   - `docs_audit` – validácia interných Markdown odkazov.
   - `helm_render_validate` – `helm lint` + render dev/prod manifestov
     (`alpine/helm:3.17.2`); rendery idú ako artefakt ďalej.
   - `helm_runtime_validate` – kontrola vyrenderovaného manifestu
     (`python:3.12-slim`): backend, frontend, práve jeden Celery Beat a worker
     pre každú z piatich front. Beží **v inom obraze než render**, lebo
     `alpine/helm` python3 nemá.
2. **`test`**
   - `frontend_tests` – `npm test` (Vitest) + `npm run typecheck`.
   - `backend_tests` – Django test suite (899 testov) proti **service
     kontajnerom** `postgres:16-alpine` a `redis:7-alpine` — tým istým verziám,
     aké prevádzkuje produkcia. Pred testami púšťa `collectstatic`, rovnako
     ako to robí produkčný kontajner pred `gunicorn`.

```mermaid
flowchart LR
    A[Commit / Tag] --> B[validate]
    B --> C[test]

    B --> B1[backend_validate]
    B --> B2[frontend_validate]
    B --> B3[docs_audit]
    B --> B4[helm_render_validate]
    B4 --> B5[helm_runtime_validate]
    C --> C1[frontend_tests]
    C --> C2[backend_tests]
```

`workflow.rules` púšťa pipeline pre každú vetvu aj každý tag. Každý job má
vlastné `rules`, takže pipeline sa dá spustiť aj ručne z UI.

### Kde pipeline beží

Na **lenovo**, ako *projektový* runner `sam-lenovo` (id 1) pre `cistafirma.sk`.
`.gitlab-ci.yml` nemá v žiadnom jobe `tags:`, takže runner musí mať
**`run_untagged = true`**. To je nastavenie **na serveri GitLabu**, nie
v `config.toml`:

```bash
ssh lenovo 'docker exec gitlab-server gitlab-rails runner \
  "Ci::Runner.find(1).update!(run_untagged: true)"'
```

> **Toto je presne miesto, kde sa 11. 9. 2026 CI potichu zastavilo.** Oba
> vtedajšie runnery mali `run_untagged = false` a žiadny job v histórii repa
> nemal `tags:` — takže **žiadny job nemal kto prevziať**. Pipeline sa
> spúšťala, joby ostávali `pending`, a nikto si to štyri dni nevšimol.
> V `config.toml` je `run_untagged` pre **už registrovaný** runner inertný —
> runner ho posiela len pri registrácii. Overené 15. 9. 2026: po reštarte
> s `run_untagged = true` v configu ostal v GitLabe stav `false`
> (`ci_runners.updated_at` sa nepohol).

> **Domerané 17. 9. 2026 — a GitLab to pomenoval sám.** Záznamy jobov dávajú
> odseku vyššie presné čísla. **Všetkých 49 jobov**, ktoré medzi **10. 9. 2026
> 20:15 a 15. 9. 2026 13:45** skončili `failed` bez toho, aby ich niekto
> prevzal, má `failure_reason = 26` — `stuck_pending_no_matching_runners` —
> a `runner_id` prázdne. To nie je interpretácia, to je GitLabov vlastný
> verdikt, že job ostal visieť, pretože naň **nemal kto**: 49 jobov, nula
> runnerov. Ostatné príčiny sú v menšine a iné — `script_failure` (10 jobov,
> 11.–15. 9.), `runner_system_failure` (6, 11. 9. 17:59–18:05) a jeden
> `server_timeout_canceling` (15. 9. 20:01). Mená hodnôt sú z
> `Enums::Ci::CommitStatus.failure_reasons`, nie odhadnuté z čísel.
>
> Závislosť na `tags:` je v tých dátach vidieť priamo. Keď `d8fd936` (11. 9.
> 19:55) tagy pridal, joby sa začali prevzímať — pipeline 6 na jeho vetve má
> `runner_id = 1` a padá až na `script_failure`. Keď vetva 13. 9. tagy zase
> stratila (`4731a620`), tie isté joby sa vrátili do
> `stuck_pending_no_matching_runners`. Kedy presne sa `run_untagged` prepol na
> `true`, v databáze nie je (históriu `ci_runners` GitLab nevedie), ale dá sa to
> ohraničiť: posledný job, ktorý nikto neprevzal, je z **15. 9. 13:45:34**
> a prvý, ktorý runner 1 prevzal, z **15. 9. 20:01:13** (pipeline 102).
> Prepnutie teda bolo medzi tým — nie až o 21:19, ako som najprv napísal:
> pipeline 105 nebola prvá, ktorú runner vzal, len prvá, ktorá celá prešla
> (`backend_tests` na tejto vetve padal na `script_failure` ešte v 103 a 104).
>
> „Štyri dni" v odseku vyššie je teda zmeraných **päť** (10. 9. 20:15 → 15. 9.
> 13:45), a netýkalo sa to len `main`: tých 49 jobov je z viacerých vetiev.

> **Oprava 17. 9. 2026 — „žiadny job v histórii repa nemal `tags:`" nie je
> pravda.** Zmerané na refoch: commit `d8fd936` (`ci: tagy pre runner na
> sam-lenovo + oprava neexistujuceho kubectl image`, 11. 9. 2026 **19:55**)
> pridáva do `.gitlab-ci.yml` osem `tags:` riadkov a je predok
> `gitlab-home/main`, ktorý ich má dodnes. Pravda je teda užšia: **do 19:55
> toho dňa** nemal `tags:` ani jeden job — a vetva, na ktorej sa CI robilo
> 13.–15. 9., ich nemá tiež (zmizli v `4731a620`, 13. 9. 17:27). Istý je ale
> dôsledok: **`gitlab-home/main` dnes nesie `tags:` aj celý starý `build`
> a `deploy` stage** — teda presne ten stav, ktorý tento dokument o pár odsekov
> nižšie opisuje ako odstránený. Podrobnosti a zvyšok: `docs/PLAN.md` §7.

> **Domerané 17. 9. 2026 — čo z toho `main` naozaj zažil.** Na otázku, ktorú
> `git log` nezodpovie, odpovedajú záznamy jobov z GitLabu (`gitlab-psql`). Na
> `main` bežalo dokopy šesť pipeline a **od 11. 9. 2026 ani jedna**. Posledná
> (`8ea1e509`, 11. 9. 19:53 UTC) má **všetkých osem automatických jobov
> `success`** a `deploy_main_to_dev` v stave `manual` — čiže **`main` nie je
> červený, je zablokovaný na manuálnej bráne**, a to šesť dní. Predošlé štyri
> (`5bd111ce`, `1148bc69`, `d80df5ad`, `38f66393`) padali na
> `build_backend_image` a `build_frontend_image`, nie na validáciách.
>
> Dve veci z toho sa týkajú priamo tohto odseku. (1) Runner 1 má dnes
> `run_untagged = true` — overené v `ci_runners` 17. 9., takže to, čo tu stálo
> o neprevzateľných joboch, už neplatí; `config.toml` ani reštart na to
> nestačili, stav sa musel zmeniť server-side (príkaz vyššie). (2) Tie dva build
> joby na `main` majú `tags: [macos]` a jediný runner s tým tagom (`mac-runner`,
> id 2, `run_untagged = false`) sa naposledy ozval **15. 9. 2026 20:21:48 UTC** —
> takže dnes by také joby **nespadli, ale ostali `pending`**, teda v presne tej
> istej tichosti, ktorú tento odsek opisuje. Tabuľka pipeline, jobov a runnerov:
> `docs/PLAN.md` §7.

Bezpečnostný model runnera (socket proxy, neprivilegované job kontajnery,
`allowed_images`, pamäťové limity) je v [`deploy/ci/README.md`](../deploy/ci/README.md)
— `config.toml` je **generovaný** skriptom [`deploy/ci/setup-config.sh`](../deploy/ci/setup-config.sh),
ktorý je jediným zdrojom pravdy.

Obe sú **verzionované kópie**; bežiaci runner číta `/home/sam/gitlab-runner/` na
lenovo a obsah tých dvoch adresárov je totožný (`sha256sum`, overené 16. 9. 2026
a znovu 17. 9. 2026 po zmene nižšie).
Dovtedy existoval celý runner — vrátane `setup-config.sh`, ktorý tento dokument
označuje za jediný zdroj pravdy — **len na jednom stroji a nikde v repozitári**:
žiadny diff, žiadna história, žiadna záloha. `config/config.toml` sa zámerne
nekopíruje, lebo obsahuje živý token; v skripte je zaň len placeholder.

Jedna výnimka z toho „jediného zdroja pravdy": **mená aj IP GitLabu sú zapísané
aj v `docker-compose.yml`** (`extra_hosts` runner kontajnera), a je to minimum,
nie nedopatrenie — runner a job kontajnery sú dva kontajnery s dvoma vlastnými
`/etc/hosts`, takže jeden spoločný zdroj tu neexistuje. Sú to **dve mená**
(kanonické `*.ts.net` a staršie `*.home.arpa`, viď „GitLab na HTTPS" nižšie),
a to je tiež zámer: ktoré z nich dostane job ako clone URL, závisí od
`external_url` v GitLabovom compose súbore — iný súbor, menený v iný moment.
Job kontajner, ktorý vie preložiť len jedno z nich, padne vždy, keď sa tie dve
veci rozídu.

Aby sa nemohli ticho rozísť, `setup-config.sh` pri každom spustení overí, že
`docker-compose.yml` vedľa neho nesie **obe** svoje mená, a skončí s `exit 1`,
keď nie. Kópia, ktorá sa nemôže rozísť, je lepšia než komentár, ktorý to sľubuje.

### GitLab na HTTPS

Nasadené 1. 10. 2026. Kanonická adresa je
`https://sam-lenovo.taildb03cf.ts.net` a cert je dôveryhodný (overené bez
`-k`: `ssl_verify_result: 0`, issuer `Let's Encrypt CN=YE2`, platnosť
1. 10. – 30. 12. 2026).

TLS **terminuje GitLab sám**, na porte, ktorý publikuje Docker
(`100.120.104.84:443`). Prvé riešenie bolo `tailscale serve`; bolo
jednoduchšie a bolo **nesprávne**, takže dôvod, prečo od neho upúšťame, patrí
sem — aby ho nikto neskúsil znovu.

`tailscale serve` je *hostový* listener na tailnet IP. Na lenove beží `ufw`
(active/enabled) a root tam nie je poruke, z čoho platia dve veci naraz:

- Dockerom publikovaný port ide cez DNAT v `nat PREROUTING`, a to `ufw`-ové
  `INPUT` pravidlá obchádza — preto sa na publikovaný port dovolá aj kontajner.
- Holý hostový listener — čokoľvek, čo si bindne `tailscaled`, alebo aj
  jednorazový `socat` na `172.17.0.1` — `INPUT` neobchádza, takže sa naň
  z docker bridge **nedovolá nikto**.

Odmerané, nie odvodené: z runner kontajnera `dial tcp 100.120.104.84:443:
i/o timeout`, kým na publikovaný `:8088` ten istý kontajner dostane 200 — a to
isté pre holý hostový listener na `172.17.0.1:9999`. Následok bol presne ten,
ktorý sa 1. 10. aj stal: GitLab po prepnutí `external_url` začal vydávať
`https://…` clone URL a runner **neprevzal ani jeden job**, lebo na tú adresu
nemal ako dosiahnuť. V prehliadači pritom https celý čas fungovalo —
prehliadač nie je kontajner, a to je rozdiel, ktorý celú vec na začiatku
zamaskoval.

Z toho plynie pravidlo pre každú ďalšiu službu na tomto stroji: **na lenove
musí TLS terminovať kontajner, nie hosť** — terminátor musí byť niečo, čo
Docker publikuje.

Tým sa ale stráca to, prečo bolo `tailscale serve` prvé: cert si `tailscaled`
obnovoval sám. Cert preto leží na disku a obnovuje ho cron:

```bash
# na lenovo (už nainštalované): @daily a @reboot /home/sam/gitlab/renew-cert.sh
crontab -l
```

`renew-cert.sh` je idempotentný — keď `tailscale cert` vráti ten istý cert,
nginx sa **NE**reloaduje — a **hlasno zlyhá** (`exit 1`), keď certu zostáva
menej než 21 dní. Cron výstup nikto nečíta, takže ticho zlyhaná obnova by inak
znamenala 90 dní ticha a potom expirovaný cert v prehliadači.
`fullchain.pem` a `privkey.pem` (mode 600) sú v `/home/sam/gitlab/ssl/` a do
kontajnera sa montujú **read-only** — zapisuje doň výhradne skript na hoste.

**Prečo `external_url` musí byť `https`.** GitLab berie schému absolútnych URL
(clone URL, API `web_url`, redirecty) z `external_url`, a svoju predstavu
o schéme posiela Railsom v `X-Forwarded-Proto`. V tomto image je tam hodnota
**odvodená od `external_url`, nie `$scheme`** — a to je zároveň najlacnejšia
kontrola, že prepnutie naozaj prebehlo:
`/var/opt/gitlab/nginx/conf/service_conf/gitlab-rails.conf` má dnes na dvoch
miestach `proxy_set_header X-Forwarded-Proto https;`, kým pri
`external_url http` tam bolo `http`. Bez tejto zmeny by https endpoint bol len
obal nad http inštanciou a GitLab by ďalej vydával `http://` clone URL.

K tomu patrí `letsencrypt['enable'] = false`, a to už **nie je redundantné**.
`should_auto_enable?`
(`/opt/gitlab/embedded/cookbooks/letsencrypt/libraries/lets_encrypt.rb`) je

```
rails_listen_https? && nginx_enabled? && nginx_listen_https? &&
  (le_auto_enabled? || !cert_files_present? || needs_renewal?)
```

Kým bolo `listen_https = false`, celá brána bola zavretá a ACME sa nemohlo
zapnúť ani teoreticky. Teraz je `nginx_listen_https?` pravda, takže bránu
otvára už len posledná zátvorka — a tá sa raz otvorí: keď sa cert začne
blížiť expirácii, `needs_renewal?` zmení výsledok na `true`. ACME pritom nemá
ako vyjsť: meno `*.ts.net` nie je z internetu na porte 80 dosiahnuteľné.
Ten riadok je teda to, čo v ten deň zabráni tichému pokusu o ACME. Dnes je
posledná zátvorka `false` (certy sú na mieste a platia do 30. 12.), takže sa
nedeje nič.

Čo sa zámerne **nemení**:

- **Registry** ostáva na `http://gitlab.home.arpa:5050` (zdravý, `/v2/`
  vracia 401). Je zapnutý, ale CI z neho netiahne ani raz (všetky `image:`
  v `.gitlab-ci.yml` sú verejné na docker.io), takže vlastný cert a vlastná
  obnova by bola práca za nič.
- **Starý `http://gitlab.home.arpa:8088`** už nie je druhá živá cesta, ale
  **presmerovanie**: `redirect_http_to_https` robí z neho 301 na https
  (1. 10. overené na `/` aj `/users/sign_in`). V redirecte je aj port
  (`https://sam-lenovo.taildb03cf.ts.net:443/…`) — neškodná kozmetika,
  `:443` je default a každý klient ho prijme. Port ostáva publikovaný.
- **SSH remote `gitlab-home`** na delle a Macu sa nemení
  (`ssh://git@gitlab.home.arpa:2222/…`) — je to tá istá cesta k tomu istému
  stroju a je to závislosť produkčného nasadenia; meniť ju by bol zásah do
  deploy cesty bez funkčného zisku.

## Prečo tu nie je `build` ani `deploy`

Stages `build` a `deploy` aj s celým obsahom (`.build_template`,
`build_backend_image`, `build_frontend_image`, `.deploy_template`,
`deploy_dev`, `deploy_main_to_dev`, `deploy_prod`, `helm_k8s_validate`) boli
odstránené **15. 9. 2026**. Neboli to stratené schopnosti — boli to joby, ktoré
nemohli prejsť:

- **`build`** pushoval obrazy do GitLab registra, ktorý **nič nečíta**.
  Produkcia na delle stavia z `build:` kontextu v `docker-compose.yml`; `image:`
  sa v celom compose súbore vyskytuje len pri cudzích obrazoch (postgres,
  redis, prometheus, grafana) a dell v `.env` nemá ani jednu zmienku
  o registri. Jediný teoretický konzument bol Helm chart, ktorého values
  ukazujú na `registry.example.com` — placeholder, ktorý neexistuje.
  Navyše build potrebuje `docker:dind`, teda privileged kontajner, čo runner
  na lenovo zámerne nevie.

- **`deploy`** nepodmienene robil `echo "$KUBE_CONFIG" | base64 -d >
  ~/.kube/config`, ale `KUBE_CONFIG` nie je definovaná nikde (projekt, skupina,
  inštancia). K8s klaster nemáme. Job teda nemal ako prejsť.

- **`helm_k8s_validate`** — `kubectl apply --dry-run=client` aj tak robí
  discovery voči API serveru, takže bez klastra neprejde. A jeho obraz
  `bitnami/kubectl:1.30` na Docker Hube **neexistuje** (Bitnami presunul free
  obrazy do `bitnamilegacy`) — padol by na pull image na akomkoľvek runneri.

Job, ktorý nemôže prejsť, učí ľudí ignorovať červenú — a to je presne trieda
chyby, ktorá nechala CI štyri dni mŕtve. Zelená pipeline má cenu len vtedy, keď
červená niečo znamená.

## Ako sa dnes nasadzuje

Nasadenie je **manuálne a zámerne jednoduché**. CI mu nepredchádza bránou —
podmienkou je zelená pipeline a commit, ktorý je pushnutý na `gitlab-home`.

Kanonický remote je **`gitlab-home`** (`ssh://git@gitlab.home.arpa:2222/web/cistafirma.sk.git`).
Na delle nevolaj `git pull` bez mena remote — globálny gitconfig tam má
`fetch.all = true`, takže fetch sa pokúsi aj o `origin` (GitHub) bez
prihlásenia, príkaz skončí s exit kódom 1 a **nič neurobí**. Vždy menuj
`gitlab-home` a kontroluj exit kód, nie výstup.

```bash
# na delle
cd <repo>
git pull gitlab-home <vetva>          # over exit kód!
docker compose up -d --build          # NIKDY s -v
docker compose exec backend python manage.py migrate
```

`docker compose up -d --build` **nikdy** nedostane `-v` — to by zničilo volume
`cistafirma_postgres_data`. Platí celý zoznam zákazov z
[`DATA_PROTECTION.md`](DATA_PROTECTION.md).

### Migrácie

Migrácie **nie sú** súčasťou `up` — compose ich zámerne nespúšťa automaticky.
Poradie je: `up -d --build` → `migrate`. Pred migráciou, ktorá vyzerá
schéma-meniacne, platí `make db-backup` + `make db-backup-verify`.

### Rollback

Rollback je dnes `git checkout` predchádzajúceho commitu + `docker compose up -d
--build`. Pre dátovú vrstvu je to restore zálohy podľa
[`DATA_PROTECTION.md`](DATA_PROTECTION.md) — **nikdy** restore nad bežiacu
databázu.

K8s rollback skripty (`scripts/k8s/rollback.sh`, `scripts/k8s/restore_postgres.sh`)
a [`DEPLOYMENT_RUNBOOK.md`](DEPLOYMENT_RUNBOOK.md) opisujú **nenasadenú**
K8s cestu. Nepoužívaj ich, kým neexistuje klaster.

## CI premenné

Pipeline dnes **nepotrebuje žiadnu povinnú CI premennú.** Registračné údaje
(`CI_REGISTRY_*`), `KUBE_CONFIG`, `DB_*` ani `STRICT_K8S_VALIDATION` sa už
nepoužívajú — obsluhovali odstránené joby.

Premenné, ktoré pipeline používa, sú v `.gitlab-ci.yml`: `GIT_STRATEGY: clone`
(čistý klon pre každý job) a pre `backend_tests` dvojica `DATABASE_URL` /
`REDIS_URL` mieriaca na jeho service kontajnery, spolu s `POSTGRES_*` údajmi
pre ne. Sú to jednorazové prihlasovacie údaje efemérneho kontajnera, nie
secrets — preto sú v `.gitlab-ci.yml` na rozdiel od `.env` na delle.

### Prečo `backend_tests` predtým nebežal vôbec

Job nemal `DATABASE_URL`, takže sa `settings.py` ticho prepol na SQLite.
Migrácia `companies/0014_add_pattern_ops_structured_indexes.py` ale vytvára
index s `text_pattern_ops` — Postgres-only trieda operátorov — takže
`create_test_db` spadol skôr, než sa stihol spustiť jediný test:

```
django.db.utils.OperationalError: near "text_pattern_ops": syntax error
```

Červený bol teda vždy, nech bol kód akýkoľvek, a nikto z neho nič nevyčítal.
To je presne tá trieda chyby, ktorú tento dokument opísal pri `helm_k8s_validate`:
job, ktorý nemôže prejsť, učí ľudí ignorovať červenú.

Tri veci boli treba, aby job naozaj testoval:

1. **Postgres** — bez neho sa schéma ani nedá postaviť.
2. **Redis** — bez neho padne šesť testov na `ConnectionError` (päť v hľadaní
   osôb, jeden admin dashboard) a healthz test čaká 200, ale dostane 503. V CI
   nie je `.env`, takže `REDIS_URL` ostal na predvolenom `localhost`.
3. **`collectstatic`** — Django si počas testov sám prepne `DEBUG` na `False`
   (`DiscoverRunner(debug_mode=False)`), čím sa
   `CompressedManifestStaticFilesStorage` prepne do striktného režimu. Bez
   manifestu padne šesť testov admin dashboardov na
   `Missing staticfiles manifest entry for 'unfold/fonts/inter/styles.css'`.
   Vypnúť tú striktnosť by bolo nesprávne — je to tá istá vec, ktorá
   v produkcii odhalí chýbajúci statický súbor.

Oba obrazy (`postgres:16-alpine`, `redis:7-alpine`) museli pribudnúť do
`allowed_images` runnera na lenovo; zavádza sa to cez
`/home/sam/gitlab-runner/setup-config.sh` (jediný zdroj pravdy pre `config.toml`)
a prejaví sa po reštarte runnera.

> **Prečo práve `allowed_images`, keď ide o `services:`.** Runner má dva
> zoznamy — `allowed_images` pre obraz jobu a `allowed_services` pre obrazy
> `services:`. `allowed_services` ale **nie je nastavený** (overené 15. 9. 2026:
> nevyskytuje sa ani v `config.toml`, ani v `setup-config.sh`), a v tom
> prípade GitLab Runner **fallbackuje na `allowed_images`** — čo je dôvod, prečo
> pipeline 105 a 106 prešli.
>
> Je to nezamýšľaná väzba a je to pasca: kto raz `allowed_services` nastaví
> (napríklad aby služby vôbec sprísnil), **rozbitne `backend_tests`** bez toho,
> aby sa dotkol repozitára — job spadne na pull image service kontajnera.
> Ak sa `allowed_services` niekedy zavedie, musia v ňom byť `postgres:16-alpine`
> aj `redis:7-alpine`.

## Helm validačné príkazy (lokálne)

Presne to, čo robí CI — dá sa pustiť aj ručne:

```bash
cd deploy/helm/cistafirma
helm lint .
helm template cistafirma-dev . -f values.yaml -f values-dev.yaml --namespace cistafirma-dev > /tmp/cistafirma-dev-render.yaml
helm template cistafirma-prod . -f values.yaml -f values-prod.yaml --namespace cistafirma > /tmp/cistafirma-prod-render.yaml
cd -
python3 scripts/k8s/validate_helm_runtime.py /tmp/cistafirma-dev-render.yaml
python3 scripts/k8s/validate_helm_runtime.py /tmp/cistafirma-prod-render.yaml
```

`validate_helm_runtime.py` je jediná vec, ktorá overuje, že by nasadenie podľa
chartu naozaj spustilo všetkých päť Celery workerov — chráni Helm chart ako
budúci deploy kontrakt. **Musí bežať v obraze, ktorý má python3**; v
`alpine/helm` padá na `exit 127`.

## Ďalšie odporúčané hardening kroky

- **Kontrola živosti CI.** CI zomrelo 11. 9. 2026 a štyri dni to nikto
  nezachytil, lebo nič nesleduje, či pipeline vôbec niečo spustila. Chýbajúca
  zelená pipeline je presne tá trieda chyby, ktorú tento projekt rieši inde.
- Doplniť SAST/dependency scanning.
- Doplniť smoke testy po nasadení.
- Vynútiť protected tagy pre produkčné releasy.
- Presunúť secrets do Vault / SealedSecrets / ExternalSecrets.
- Zvážiť `tags:` v `.gitlab-ci.yml` — dnes je runner povolený na untagged joby
  serverovým prepínačom. Explicitný tag na joboch by bol viditeľnejší
  a prežil by prenos projektu inam.
