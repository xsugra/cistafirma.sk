# K8s (k3s) na dell — plán, s Postgresom a Redisom mimo clusteru

> **Stav: návrh. Nič z tohto nie je nasadené a nič sa podľa tohto nesmie spustiť
> bez prejdenia brány príslušnej fázy.** Platí preň to isté ako pre
> `docs/DEPLOYMENT_RUNBOOK.md` — aj ten popisuje nenasadenú cestu.

Toto je plán, ako na **dell** postaviť k3s a presunúť doň aplikáciu, aby deploy
prestal byť výpadok a začal byť rolling update. Vznikol na základe rozhodnutia
z 1. 10. 2026, po tom, čo boli zmerané náklady aj prínosy ([§1](#1-prečo-a-za-akých-hraníc)).

---

## 1. Prečo a za akých hraníc

**Čo tým chceme:** rolling update bez výpadku a deklaratívny, opakovateľný deploy.
To sú dve veci, ktoré sa dnes robia ručne a pri každom nasadení spôsobia merateľný
výpadok (`frontend/nginx.conf.template:43-45` — **502 na ~9–12 s** po recreation
backendu, domerané na produkcii 17. 9. 2026).

**Čo je mimo rozsahu, a je to zámer:**

- **HPA / autoscaling.** V celom `deploy/helm/` je `HorizontalPodAutoscaler`
  **0 výskytov**. Nikdy nebol na stole, takže jeho vypustenie nič nestojí.
- **Multi-node.** Na jednom stroji je klasický prínos k8s (rozloženie záťaže,
  prežitie výpadku uzla) presne nula. Toto je vedomé rozhodnutie, nie prehliadnutie.

**Tvrdá hranica, ktorá definuje celý zvyšok plánu:**

> **`cistafirma_postgres_data` sa nepresúva. Postgres ani Redis nevstupujú do
> klastra. Ostávajú v Dockeri na delle, tak ako dnes.**

Dôvod je konkrétny: databáza má **3 117 MB** a je to **jediná kópia**. Chart
defaultne nasadzuje in-cluster Postgres StatefulSet s 20 Gi PVC
(`deploy/helm/cistafirma/templates/postgres-statefulset.yaml:79-89`,
`values.yaml:78`), ale jeho vlastný komentár na `values.yaml:73` hovorí:
*„In-cluster Postgres + Redis (pre lokál / dev). V prod použi managed DB a tieto vypni."*
A `docs/DEPLOYMENT_CONTRACT.md` to zakazuje ešte ostnejšie: *„Never rely on an
automatically created new PVC to preserve data."*

Presun by znamenal dump a restore jedinej kópie — presne tú operáciu, ktorú
`docs/DATA_PROTECTION.md` zakazuje robiť rutinne. Zároveň je to **zbytočné**:
databáza nemá z orchestrace nič. Tým, že ostane vonku, sa celý klastrový projekt
vyhne svojmu najrizikovejšiemu kroku.

---

## 2. Cieľová topológia na delle (merané 1. 10. 2026)

| Veličina | Namerané |
|---|---|
| CPU / RAM | 4 vCPU / **7,1 GiB** |
| Kontajnery | **16** |
| RAM použité / dostupné | **3,3–3,4 GiB** / **3,7–3,8 GiB** (`free`; tiež vzorka, viď nižšie) |
| **Swap v použití** | **713 MiB** zo 7,6 GiB — **vzorka, nie konstanta** |
| Disk | 466 GB, 47 GB použitých, **400 GB voľných** |
| Docker | 29.8.0, swarm `inactive` |
| k8s nástroje | `kubectl`, `k3s`, `helm`, `kubeadm`, `kind` — **žiadny** |

Ten swap je dôležitejší, než vyzerá: **odswapovaných 713 MiB znamená, že box už
dnes nie je bez pamäťového tlaku.** k3s si vypýta ďalších zhruba 0,5–1 GiB
(kontrolný plán, kubelet, containerd, Traefik, CoreDNS). „Dostupné 3,7 GiB" je
teda číslo, ktoré sa nesmie prečítať ako „3,7 GiB na rozdávanie" — časť z neho
je buff/cache, ktorý si systém vezme späť, len čo ho bude potrebovať.

**Ale to číslo je vzorka, nie vlastnosť boxu.** Tri merania v ten istý deň dali
835, 659 a 713 MiB. Preto sa z neho **nesmie** stať prah v bráne Fázy 1 — kto si
do brány napíše „swap < 835 MiB", porovnáva dve rôzne vzorky a vyhodnotí to ako
regresiu alebo ako zlepšenie podľa toho, kedy si kávu.

Čo je na ňom naopak stále: **celý používaný swap sedí v `zram0`** (`swapon
--show`: `/dev/zram0` 713,2 M, zatiaľ čo `/swap.img` má **0 B**). To je
komprimovaná RAM, nie disk — takže „swap v použití" tu neznamená odložené
stránky na disku, ale **skutočne zabratú pamäť** komprimovanou formou. Tlak je
teda reálny a zram ho len zmenšuje, neodstraňuje.

Preto brána Fázy 1 musí byť **rozdiel meraný v tej istej session** (`free -h`
pred a po spustení k3s), nie porovnanie s číslom zapísaným v tomto dokumente.

**Porty — a toto je najdôležitejší riadok celej sekcie:**

`ss -lntp` na delle (bez `sudo`, takže bez stĺpca s procesom — ten netreba,
meno držiteľa hovorí `tailscale serve status` nižšie):

```
LISTEN 0      1024        100.79.47.4:443    0.0.0.0:*
LISTEN 0      1024        100.79.47.4:8443   0.0.0.0:*
LISTEN 0      1024  [fd7a:115c:...:2f05]:443  [::]:*
LISTEN 0      1024  [fd7a:115c:...:2f05]:8443 [::]:*
```

To je **výňatok** — `ss -lnt` má na delle **17** TCP listenerov. Zvyšok je
lokálny alebo tailnetový a s k3s sa nestretáva: `127.0.0.1:5432` (Postgres),
`127.0.0.1:6380` (Redis), `127.0.0.1:5173` (frontend), `127.0.0.1:8080`
(backend), `127.0.0.1:3000` (Grafana), `127.0.0.1:9090` (Prometheus),
`100.79.47.4:9100` (node_exporter), `127.0.0.53%lo:53` a `127.0.0.54:53`
(systemd-resolved), `0.0.0.0:22` a `[::]:22` (ssh), plus dva efemérne porty
`tailscaled`. Uvádzam to preto, lebo **17 a nie 4 je rozdiel, ktorý sa dá
neoverene preniesť** — kto si prečíta len výňatok, bude číslo „voľných portov"
počítať z neho.

Všimni si adresu: `100.79.47.4`, teda **tailnet IP, nie `0.0.0.0`** — port je
viazaný len na tailnet. `tailscale serve status` prezrádza aj to, kam mieri:

```
https://dell.taildb03cf.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:5173

https://dell.taildb03cf.ts.net:8443 (tailnet only)
|-- / proxy http://127.0.0.1:3000
```

**6443, 8472 ani 80 sa v tom výpise nevyskytujú — sú voľné.** To je celý
priestor, ktorý k3s potrebuje. (Zámerne neuvádzam pid `tailscaled`: pri
reštarte sa zmení a tvrdenie by zastaralo bez toho, aby prestalo platiť.
Adresa plus `serve status` dokazujú to isté a dajú sa kedykoľvek zopakovať.)

**Dôsledok: k3s ingress sa na 443 nezmestí — a nie je to mäkké tvrdenie.**
Linux nedovolí `bind(0.0.0.0:443)`, keď je na tom istom porte už viazaná
konkrétna adresa (`100.79.47.4:443`); vráti `EADDRINUSE`. k3s štandardne
nasadzuje Traefik **aj** ServiceLB (`klipper-lb`), a ten druhý si na 443 a 80
robí `hostPort`. Jeho pod teda narazí na `EADDRINUSE` a **pôjde do crash-loopu**
— pričom `k3s` sám, API server a zvyšok klastra budú vyzerať zdravo.

Toto je zatiaľ **odvodenie, nie meranie** — a presne preto je Fáza 1
„k3s, a nič viac": jej úlohou je to potvrdiť alebo vyvrátiť skôr, než na tom
bude niečo stáť. Praktický dôsledok pre inštaláciu:

```
curl -sfL https://get.k3s.io | sh -s - server \
  --disable traefik --disable servicelb \
  --write-kubeconfig-mode 644
```

(Vypnutie Traefiku znamená aj to, že v Fáze 4 treba ingress vystaviť inak —
NodePort, prípadne vlastný ingress controller na porte, ktorý je naozaj voľný.
To je rozhodnutie Fázy 4, nie Fázy 1.)

`tailscale serve` tak ostáva terminátorom TLS a v poslednej fáze sa jeho cieľ
prepne z `127.0.0.1:5173` na port, ktorý vystaví klaster. Voľné ostávajú 6443
(API server), 8472 (flannel, UDP) a 80.

To, že `tailscale serve` na delle **funguje**, nie je náhoda a nie je to v rozpore
s tým, čo bolo 1. 10. odstránené z lenova. Na lenove bol `serve` hostový listener,
na ktorý sa z docker bridge **nikto nedovolal** — a presne to bol dôvod, prečo tam
TLS musel prevziať GitLab sám. Na delle je to naopak: `serve` je vstupná brána pre
prehliadače z tailnetu a **žiadny kontajner ho dosiahnuť nepotrebuje**. Rovnaký
mechanizmus, opačný záver, lebo je opačný smer prevádzky.

**Firewall je naklonený v prospech tohto plánu.** `ufw` je `active`,
default `deny (incoming)`, `deny (routed)`, plus `Anywhere on tailscale0 ALLOW IN`
— takže API server k3s na 6443 bude z lenova (GitLab runner) dostupný po tailnete
**bez novej diery**. A `docker-ufw-guard.sh`, aktívny od 26. 9. 2026, zahadzuje
v `DOCKER-USER` len to, čo príde na **fyzickom** rozhraní `enp3s0` mimo
`192.168.1.0/24` — prevádzky z k3s podov sa teda netýka. To ale **neznamená, že
je priechod vyriešený**; rozhoduje o ňom politika `FORWARD`, viď
[§3](#3-najväčšie-technické-riziko-ako-sa-pody-dostanú-na-postgres-a-redis).

---

## 3. Najväčšie technické riziko: ako sa pody dostanú na Postgres a Redis

Toto je miesto, kde tento plán buď prejde, alebo ticho zlyhá — a je to **presne
tá istá trieda chyby, aká sa 1. 10. namerala na lenove** (hostový listener
dosiahnuteľný odnikiaľ).

Dnešný stav na delle: databáza aj Redis sú publikované **len na loopback**

```
cistafirma_db    127.0.0.1:5432->5432/tcp
cistafirma_redis 127.0.0.1:6380->6379/tcp
```

Pod v klastri má **vlastný** `127.0.0.1`. Takže takto sa k nim nedostane a
`DATABASE_URL=…@127.0.0.1:5432/…` v podu zlyhá na connection refused.

Sú tri možnosti:

**A. Publikovať db/redis na gateway docker bridge siete** (`172.18.0.1`, resp.
`172.17.0.1`) namiesto `127.0.0.1`, a `DATABASE_URL` v podoch namieriť na tú IP.
Rozsah `172.18.0.0/16` nie je z LAN routovateľný, takže expozícia je obmedzená na
host a jeho kontajnery — ale **je to zmena dnešnej bezpečnostnej postoje**
„db a redis sú len na loopbacku" a musí prejsť vedome, nie mimochodom.

**B. Kubernetes Service bez selektora + manuálne Endpoints** na IP hosta. Je to
idiomatickejšie pre k8s a drží konfiguráciu v klastri, ale meny sa to isté ako A:
niekde musí byť IP, na ktorej je Postgres z podu dosiahnuteľný.

**C. Dedičná macvlan/ipvlan sieť** pre db a redis s vlastnou routovateľnou IP.
Najčistejšie z hľadiska oddelenia, ale najväčší zásah do dnešného compose.

**Odporúčaná je A**, pretože je najmenšia a vratná jedným riadkom v compose.

### Čo presne treba odmerať (a prečo to nie je zrejmé)

`DOCKER-USER` to **nie je** — to sa dá vylúčiť už teraz, meraním. Reťazec má na
delle len dve pravidlá a to zahadzujúce platí na `-i enp3s0`:

```
-N DOCKER-USER
-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER ! -s 192.168.1.0/24 -i enp3s0 -j DROP
```

Prevádzka z podu prichádza na k3s rozhranie, nie na fyzickú NIC, takže cez neho
neprejde. Skutočná otázka je inde — v `FORWARD`:

```
-P FORWARD DROP          # ufw: DEFAULT_FORWARD_POLICY="DROP"
```

Dnešné DNAT pravidlá pre publikované porty sú **scoped na loopback**:

```
-A DOCKER -d 127.0.0.1/32 ! -i br-45957a09f575 -p tcp --dport 5432 -j DNAT --to-destination 172.18.0.9:5432
-A DOCKER -d 127.0.0.1/32 ! -i br-45957a09f575 -p tcp --dport 6380 -j DNAT --to-destination 172.18.0.2:6379
```

To je presne to, čo dnes drží databázu na loopbacku. Pri možnosti A sa `-d` zmení
na `172.18.0.1/32` a packet z podu sa po DNAT stane **forwardovanou** prevádzkou
(zdroj = IP podu, cieľ = IP kontajnera) — takže o ňom rozhoduje `-P FORWARD DROP`
a to, či Docker pre ten most vygeneroval `ACCEPT`. To je jediná vec, ktorú Fáza 2
overuje.

> **A musí sa to ZMERAŤ, nie odvodiť.** Nikto to zatiaľ neskúsil a je to presne
> tá trieda chyby, aká sa 1. 10. namerala na lenove: mechanizmus, o ktorom sa
> „vie", že funguje, a nikdy nebol spustený v tomto smere. Preto **Fáza 2 nižšie
> je meranie a nič iné**, a to s pozitívnou kontrolou: nestačí, že sa spojenie
> nepodarí — treba vedieť, že rovnaký test na port, o ktorom vieme, že odpovedá,
> naozaj prejde.

---

## 4. Čo chart naozaj umí a čo nie (overené 1. 10. 2026)

**Umí — a to je viac, než by človek čakal od „nenasadeného" chartu:**

- **22 objektov pri defaultných hodnotách** (t. j. aj s in-cluster Postgresom
  a Redisom, ktoré v našom návrhu vypneme): 9 Deploymentov (backend, frontend,
  beat, 5 celery workerov, Redis), 4 Service, 2 PDB, 2 PVC, StatefulSet,
  migrate Job, denný `pg_dump` CronJob, Ingress, ConfigMap. Doložené:
  `templates/` má 18 deklarácií `kind:`, z toho jediný cykliaci template
  (`celery-worker-deployment.yaml:1`, `range … .Values.celery.workers`) sa
  renderuje 5× — 17 + 5 = 22.
- `values.yaml:22` backend `replicaCount: 2`, `:32` frontend `2` — **rolling
  update je teda default**, nie niečo, čo treba dopĺňať.
- Probes readiness aj liveness (`backend-deployment.yaml:54-65`).
- `backend-deployment.yaml:21` init kontajner `wait-for-migrations`: čaká na TCP
  dostupnosť Postgresu (timeout 3 s, pauza 2 s), potom na
  `manage.py migrate --check` (pauza 3 s). To je presne to, čo robí rolling
  update bezpečným voči migráciám.
- `celery-beat-deployment.yaml:9-11` — `replicas: 1` a `strategy: Recreate`.
- `scripts/k8s/rollback.sh` už existuje a robí `kubectl rollout undo`.

**Neumí, alebo je rozbité — a toto treba opraviť skôr, než naň fáza narazí**
(body 2, 8 a 9 pred Fázou 3 — Secret musí existovať a `REDIS_URL` musia dostať
workery aj backend; body 1, 3–7 pred Fázou 4):

| # | Problém | Dôkaz |
|---|---|---|
| 1 | Image repozitáre sú placeholdery a **nikto ich nevyrába** | `values.yaml:3-4,7-8` `registry.example.com/cistafirma/…`; build stage odstránený `.gitlab-ci.yml:202-204` |
| 2 | Chart nasadí vlastný Redis, ale **adresu nezapája nikam** | `deploy/helm/cistafirma/README.md:54-61`; `REDIS_URL` sa v žiadnej šablóne nenastavuje |
| 3 | `backendResolver` default `""` → nginx **odmietne naštartovať** | `values.yaml:46`; pre k3s treba `10.43.0.10` (nie `10.96.0.10` z `values-dev.yaml:42`) |
| 4 | `BACKEND_UPSTREAM` **nie je nastaviteľný cez values** | `templates/_helpers.tpl:34-36` ho počíta natvrdo ako `<fullname>-backend:8000` |
| 5 | Postgres StatefulSet s 20 Gi PVC je zapnutý defaultne | `values.yaml:74,78` — v našom návrhu musí byť `postgres.enabled=false` a `redis.enabled=false` |
| 6 | `ingressClassName: nginx`, ale k3s vezie **Traefik** (trieda `traefik`) | `values.yaml:11` → `ingress.yaml:9-11`. Ingress sa nikdy nepriradí a `https://…` vráti 404 **od Traefiku** — teda nie „nič neodpovedá", ale „odpovedá niekto iný", čo sa ladí oveľa horšie |
| 7 | migrate Job je `post-install,post-upgrade` **hook**, ale Deploymenty čakajú na `migrate --check` | `migrate-job.yaml:10` vs `backend-deployment.yaml:38`. `scripts/k8s/helm-deploy.sh:51-52` volá `helm upgrade --install … --wait --timeout 15m`, a Helm s `--wait` púšťa post-install hooky **až keď sú resources ready** — Deploymenty sa však ready nestanú, kým hook neprebehne. Release s novou migráciou teda **visí 15 minút a potom spadne na timeout**; nie je to teoretická možnosť, je to presne to, čo ten skript spraví |
| 8 | Chart **nevytvára Secret**, iba naň odkazuje | `values.yaml:10` `existingSecret: cistafirma-secrets`; v `templates/` **nie je** `secret.yaml`. `configmap.yaml:8-12` nesie len 5 ne-tajomných hodnôt — `DATABASE_URL`, `SECRET_KEY` aj `REDIS_URL` si musí vyrobiť operátor ručne, a nikde to nie je napísané |
| 9 | `REDIS_URL` chýba **aj backendu** — a zlyhá to **ticho** | `backend/backend/settings.py:248-249`: `os.getenv('CELERY_BROKER_URL') or os.getenv('REDIS_URL', 'redis://localhost:6379/0')`. V podu je `localhost` sám pod, takže API beží ďalej a `enqueue` padá ticho. Toto je presne trieda chyby, ktorú [§8](#8-riziká-ktoré-sa-prejavia-ticho) opisuje |

**CI to neodchytí, a to je samostatný nález.** `scripts/k8s/validate_helm_runtime.py`
je jediná runtime kontrola chartu a kontroluje **zoznam Deploymentov a názvy
frontov** (`:98`, `:136`, `:143`) — `REDIS_URL`, `envFrom` ani existenciu
Secretu nerieši. Zelený `helm_runtime_validate` teda znamená „workloady sú
deklarované", **nie** „workloady naozaj naštartujú". Body 2, 8 a 9 prejdú CI
a prejavia sa až v klastri.

**Bod 4 je architektonický, nie kozmetický.** Znamená, že frontend z chartu sa
**nedá** namieriť na backend bežiaci mimo klastra. Fázovanie sa tomu musí
podriadiť: **backend a frontend idú do klastra v tej istej fáze.** Nedá sa
presunúť jeden a druhý nechať v Dockeri.

---

## 5. Fázy

Každá fáza má **bránu** (čo musí platiť, aby sa šlo ďalej) a **rollback**.
Poradie je od najnižšieho rizika k najvyššiemu.

### Fáza 0 — príprava (bez zmeny čohokoľvek)

- `make db-backup` a `make db-backup-verify BACKUP_FILE=…`.
- **`make db-backup-replicate BACKUP_FILE=…`** — a tento krok v prvom návrhu
  chýbal, čím bola brána Fázy 0 **nedosiahnuteľná**. Zdôvodnenie nižšie.
- `make db-restore-drill BACKUP_FILE=…` — aby existoval čerstvý záznam v
  `restore_drills.log` a `db-offsite-status` nepadal na starobu drillu.
- Zaznamenať baseline `make ops-check` **pred** akýmkoľvek zásahom, nech je
  s čím porovnávať.

**Prečo tam `db-backup-replicate` musí byť.** `make db-backup` volá
`scripts/local/backup_postgres.sh`, a v tom skripte **nie je ani jedno slovo o
replikácii** (overené: `grep -c 'replicat\|offsite'` → 0). Oddelený je aj
`make db-backup-replicate` → `scripts/local/replicate_postgres_backup.sh`.
`make ops-check` pritom kontroluje inú vec, než by človek čakal: nie „existuje
nejaká replika", ale **`<offsite>/<basename najnovšieho dumpu>.gpg`**. Kým sa
replikácia nespraví, najnovší dump repliku nemá — a brána „baseline zelený" sa
nedá splniť, nech sa spraví čokoľvek iné.

Namerané 1. 10. 2026, presne v tomto poradí:

| kontrola | stav pred replikáciou |
|---|---|
| najnovší dump | `cistafirma_20261001T171632Z.dump` — **bez `.gpg`** |
| najnovšia replika | `cistafirma_20260928T195631Z.dump.gpg` — o 3 dni staršia |
| dôsledok | `ops-check`: `FAIL no off-site replica of the newest dump` |
| po `db-backup-replicate` | `OK newest dump has a checksum-verified off-site replica, encrypted at source to F3B8F3ADFBA9DB8F` |

**Brána:** záloha overená, **replika overená**, drill zapísaný, baseline zelený.
**Rollback:** netreba, nič sa nemenilo.

**Vykonané 1. 10. 2026** (všetko na delle, `/home/sam/cistafirma`): dump
`cistafirma_20261001T171632Z.dump`, `db-backup-verify` EXIT=0, replika na
`/mnt/cistafirma-offsite` s overeným šifrovaním na zdroji, drill
`39 public tables restored into isolated container`, baseline `ops-check`
`Operational controls: SATISFIED` EXIT=0.

### Fáza 1 — k3s, a nič viac

Nainštalovať k3s na dell a **nenasadiť doň nič**. Cieľom je zistiť, či samo
spustenie k3s rozbije dnešný stack.

- Inštalovať s `--disable traefik --disable servicelb`, ako je to v
  [§2](#2-cieľová-topológia-na-delle-merané-1-10-2026) — inak ServiceLB narazí
  na `100.79.47.4:443` a pôjde do crash-loopu.
- Odmerať `free -h` **pred a po** spustení k3s, v jednej session. Rozhoduje
  **rozdiel**, nie absolútne číslo — swap je vzorka (viď §2).
- Overiť, že `100.79.47.4:443` stále drží `tailscaled` a že
  `https://dell.taildb03cf.ts.net` stále odpovedá.
- `kubectl get pods -A` — **žiadny pod v `CrashLoopBackOff`**. Prázdny klaster
  bez jedného bežiaceho workloadu je práve ten stav, v ktorom by to nikto
  nevidel, keby sa nepozrel.

**Brána:** dnešný stack beží nezmenený, `make ops-check` zelený, swap po
spustení k3s **nerastie o viac, než je šum vzorky**, a v klastri nič
nekrachuje. Ak swap rastie, je to signál, že sa do klastra nemá presúvať ešte
aj aplikácia.
**Rollback:** `k3s-uninstall.sh` (k3s ho inštaluje sám).

Toto je jediná fáza, kde je rollback úplný a bez následkov. Preto sa v nej nič
nenasádza.

### Fáza 2 — meranie siete, a nič iné

Overiť [§3](#3-najväčšie-technické-riziko-ako-sa-pody-dostanú-na-postgres-a-redis):
zmeniť publikovanie `db`/`redis` podľa zvolenej možnosti a **z podu v klastri**
skúsiť TCP spojenie na databázu. S pozitívnou kontrolou.

**Brána:** z podu sa dá otvoriť spojenie na Postgres **aj** Redis, a pozitívna
kontrola potvrdzuje, že test vie uspieť aj zlyhať. Bez tohto sa nepokračuje.
**Rollback:** vrátiť publikovanie na `127.0.0.1`.

### Fáza 3 — celery workery (+ beat) do klastra

Workery sú najnižšie riziko: nemajú vstup zvonka, iba konzumujú z Redisu.
**Pozor na jednu pascu:** `beat` musí byť na svete **presne raz**. Ak sa do
klastra pridá klastrový beat a súčasne sa nezastaví dockerový, budú dva — a to je
tichá chyba, ktorá sa prejaví duplicitnými periodickými úlohami, nie pádom.
Preto sa beat a jeho dockerová verzia menia **v jednej zmene**.

**Brána:** fronty sa vyprázdňujú, `SyncJob` pribúdajú, `make ops-check` zelený
(číta okrem iného hĺbky frontov a dispatch beat entries).
**Rollback:** vypnúť klastrové workery, dockerové ostanú (alebo sa vrátia).

### Fáza 4 — backend + frontend do klastra

**Spolu, kvôli bodu 4 v [§4](#4-čo-chart-naozaj-umí-a-čo-nie-overené-1-10-2026).**
Súčasne:

- `postgres.enabled=false`, `redis.enabled=false` — **databáza sa nehýbe**.
- `backendResolver=10.43.0.10` (overiť po inštalácii, že je to naozaj adresa
  kube-dns v tomto klastri).
- Vlastné image repozitáre namiesto placeholderov — a rozhodnúť, **odkiaľ sa
  obrazy berú**, keďže build stage v CI neexistuje.
- `tailscale serve` prepnúť z `127.0.0.1:5173` na klastrový ingress.

**Brána:** `https://dell.taildb03cf.ts.net` odpovedá, API funguje, výpadok pri
rolloute je nulový (to je celý zmysel).
**Rollback:** `scripts/k8s/rollback.sh`, alebo návrat compose stacku a `serve`
späť na `127.0.0.1:5173`.

**Toto je jediná fáza, ktorá mení používateľskú skúsenosť.** Ideálne mimo
pracovných hodín.

### Fáza 5 — automatizácia deployu

Až teraz, keď je čo nasadzovať.

**Odporúčaná je pull varianta:** systemd timer na delle, ktorý zistí, že sa `main`
pohol, a spraví `helm upgrade`. Výhody: **žiadne credentials na lenovom runneri**,
žiadny inbound na dell, a sedí to do existujúceho vzoru — dell už systemd timery
má (`backup-app.service`, `docker-ufw-guard.service`).

Push varianta (job na lenovo runneri → `helm upgrade`) by si vyžiadala kubeconfig
s cluster-admin v CI premenných na lenovom runneri. To je **väčšia** expozícia
credentials, nie menšia, a preto sa neodporúča ako prvá.

---

## 6. Dátová bezpečnosť (nad všetkým ostatným)

- **`cistafirma_postgres_data` sa v žiadnej fáze nepresúva, nekopíruje ani
  nereštauje.** Postgres ostáva tam, kde je.
- Pred **každou** fázou: `make db-backup` + `make db-backup-verify`.
- `make docker-reset`, `docker compose down -v`, `docker volume rm/prune` —
  zakázané, ako vždy. Rovnako žiadny restore nad bežiacou databázou.
- Ak by niekedy v budúcnosti mal Postgres do klastra vstúpiť, je to **samostatný
  projekt** s vlastným plánom, vlastnou zálohou a vlastným drillom — nie krok
  v tomto pláne.

---

## 7. Čo sa bude musieť prepísať, keď to prejde

Toto nie je „pekná dokumentácia k tomu" — sú to miesta, ktoré po migrácii
**prestanú platiť** a budú ticho klamať, ak sa nechajú:

- **`make ops-check`** — jediná prevádzková brána, ktorú tento projekt má. Číta
  compose stack (hĺbky frontov, scrape health, sync joby, dispatch beat entries,
  zálohy, off-site, drilly). Po migrácii ju treba portovať, inak prestane merať
  to, čo si myslí, že meria.
- `docs/DEVOPS_CICD.md` — deploy recept (dnes `git pull` + `docker compose up -d --build`).
- `docs/DEPLOYMENT_CONTRACT.md` a `docs/DEPLOYMENT_RUNBOOK.md` — stav „nenasadené"
  a sedembodový checklist.
- `deploy/k8s/README.md` — `NENASADENÉ` v hlavičke.
- `CLAUDE.md` — sekcia „Where production runs" a zoznam CI stageov.

---

## 8. Riziká, ktoré sa prejavia ticho

Toto sú veci, ktoré pri neúspechu **nevypíšu chybu** — a preto sú nebezpečnejšie
než tie, ktoré spadnú:

1. **Pody nedosiahnu Postgres.** Prejaví sa to ako `wait-for-migrations` v slučke
   navždy, nie ako pád. Presne preto je Fáza 2 samostatná a s pozitívnou kontrolou.
2. **Dva celery beaty.** Duplicitné periodické úlohy. Nič nepadne.
3. **`REDIS_URL` nezapojený** ([§4](#4-čo-chart-naozaj-umí-a-čo-nie-overené-1-10-2026) body 2 a 9).
   Dva rôzne prejavy, a ten druhý je horší:
   - **Worker:** `celery-worker-deployment.yaml:43` ho číta v **init kontajneri**
     v neohraničenej slučke `until …; do … sleep 2; done` s potlačenou chybou
     (`2>/dev/null`). Worker teda **vôbec neštartuje** a pod ostane navždy
     v `Init:0/1` s textom „Waiting for Redis…" — nie je to worker, ktorý beží
     naprázdno, je to pod, ktorý nikdy nie je ready.
   - **Backend:** `settings.py:248-249` padá na `redis://localhost:6379/0`.
     V podu je `localhost` **sám pod**, takže API odpovedá, `/healthz/` je
     zelené, liveness probe prechádza — a každé `enqueue` ticho zlyhá. Toto je
     horšie než worker, ktorý neštartuje, lebo **nič nevyzerá rozbité**.
4. **`PROMETHEUS_MULTIPROC_DIR`** — `docker-compose.yml:102-107` vysvetľuje, že
   s viac než jedným gunicorn procesom musí byť nastavený a **nesmie ho zdieľať
   viac kontajnerov**. Pri dvoch replikách backendu to treba držať rovnako.
5. **Bind-mount vs. image.** Dnešný backend dostáva kód bind mountom a gunicorn
   beží **bez** `--reload`. Klasický zmätok „nasadil som a nič sa nezmenilo" je
   tu už dnes známy; v k8s sa zmení na „image je starý a nikto to nepovie".

---

## 9. Otvorené otázky, ktoré treba rozhodnúť pred Fázou 3

1. **Stojí to za to?** Nameraný výpadok pri deployi je ~9–12 s. Ak sa deploy
   deje raz za týždeň mimo pracovných hodín, je to celé veľa práce za málo.
   Toto je otázka, ktorá rozhoduje o celej veci — ostatné body sú technické
   detaily, tento je o tom, či sa do toho vôbec púšťať.
2. **Odkiaľ sa berú obrazy?** Build stage v CI bol odstránený 15. 9. a chart má
   placeholdery. Bez odpovede nemá klaster čo nasadiť.
3. **Čo s `ops-check`?** Portovať ju na k8s API, alebo ju nechať nad Dockerom
   a dopísať k nej druhú, klastrovú?
4. **Migrácie.** Rolling update znamená, že počas rollu bežia **obe** verzie kódu
   nad jednou databázou. To vyžaduje expand/contract migrácie — disciplínu
   v aplikácii, ktorú k8s nerieši. Chart to zvládne (`wait-for-migrations`), ale
   iba ak migrácia nie je deštruktívna voči starej verzii.
