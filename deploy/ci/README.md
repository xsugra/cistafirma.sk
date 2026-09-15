# GitLab Runner na sam-lenovo

Nasadené 11. 9. 2026 ako **dva kontajnery** cez `docker compose`.

> **Toto je verzionovaná kópia.** Súbory v `deploy/ci/` sú bajt na bajt totožné
> s tými na lenovo (`sha256sum` overené 16. 9. 2026). Zdrojom pravdy pre
> **bežiaci** runner je naďalej `/home/sam/gitlab-runner/` na lenovo — sem sa
> kopírujú preto, aby konfigurácia CI runnera mala históriu, diff a zálohu:
> predtým existovala len na jednom stroji a nikde v repozitári.
>
> **`config/config.toml` sa sem NIKDY nekopíruje.** Je to generovaný výstup
> a obsahuje živý runner token (v `setup-config.sh` je len placeholder
> `__TOKEN__`, ktorý sa doplní až pri spustení zo `runner-token.txt`). Preto je
> v tomto adresári bezpečné verzionovať všetko okrem `config/`.
>
> `commit-ci-tags.rb` sa nekopíruje — je označený ako nepoužitý.

```
/home/sam/gitlab-runner/
├── docker-compose.yml        # proxy + runner
├── setup-config.sh           # generuje config/config.toml (jediný zdroj pravdy)
├── commit-ci-tags.rb         # NEPOUŽITÉ — tagy sa nakoniec neriešili cez commit
├── README.md                 # tento súbor
└── config/
    └── config.toml           # 0600, obsahuje runner token
```

## Ovládanie

```bash
cd /home/sam/gitlab-runner

docker compose ps                 # stav
docker compose logs -f gitlab-runner
docker compose restart gitlab-runner
docker compose down               # zastaviť
docker compose up -d              # spustiť (prežije reboot cez restart: unless-stopped)

# zmena konfigurácie: edituj setup-config.sh, potom
bash setup-config.sh && docker compose restart gitlab-runner
```

## Bezpečnostný model

Toto je realizácia pravidla z runbooku:

> *„Ak ho budeš chcieť späť, tak jedine cez obmedzený socket proxy
> (napr. tecnativa/docker-socket-proxy), nikdy s priamym prístupom k socketu."*

**Kto vidí `docker.sock`:**

| | socket | ako |
|---|---|---|
| `gitlab-runner-proxy` | **áno** | `/var/run/docker.sock` namontovaný **read-only** |
| `gitlab-runner` | **nie** | rozpráva sa len s `tcp://docker-socket-proxy:2375` |
| job kontajnery | **nie** | `volumes = ["/cache"]`, žiadny socket |

Proxy nemá publikovaný **žiadny port** — je dosiahnuteľný len z vnútra siete
`runner-net`. Job kontajnery bežia na default bridge, teda v inej sieti.

### Overené naostro (11. 9. 2026)

```
runner kontajner: /var/run/docker.sock      -> neexistuje
runner mounty:                              -> len config + vlastný volume
job kontajner (default bridge) -> proxy     -> nedosiahne (timeout)
job kontajner: /var/run/docker.sock         -> neexistuje
proxy z runnera:
    GET /version, /containers/json,
        /images/json, /networks            -> 200 OK
    GET /secrets, /services, /nodes,
        /info, /build                       -> 403 Forbidden
    POST /exec/...                          -> 403 Forbidden
```

### Dôležité a neintuitívne: proxy sám o sebe nestačí

Proxy obmedzuje, **ktoré API endpointy** sú dosiahnuteľné — ale **nerobí
inšpekciu tela požiadavky**. `POST /containers/create` s `-v /:/host
--privileged` v tele prejde cez proxy rovnako ako cez surový socket.
`POST: 1` a `CONTAINERS: 1` sú pritom pre runner nevyhnutné, inak nespustí
žiadny job.

Skutočnú ochranu preto robí až to, že **job kontajnery sú neprivilegované
a bez socketu** (`privileged = false`, `volumes = ["/cache"]` v `config.toml`).
Proxy je druhá vrstva: zužuje, čo zvládne sám daemon runnera — žiadne
`exec` do bežiacich kontajnerov (napr. GitLabu), žiadne secrets, swarm,
system endpointy.

Keby niekto raz pridal do `config.toml` `privileged = true` alebo
`/var/run/docker.sock:/var/run/docker.sock` do `volumes`, celý profil padá.
Sú tam komentáre, ktoré to hovoria.

## Obmedzenia, ktoré treba poznať

- **`concurrent = 1`, `limit = 1`, `memory = 1g`** — stroj má 3.7 GiB a beží
  na ňom GitLab, motionEye aj kamera. `memory_swap = memory` znamená, že job
  nesmie swapovať; pri prekročení dostane OOM kill (job zlyhá, stroj prežije).
  Najťažší job je `frontend_validate` (`npm ci && npm run build`).
- **Image buildy tu nefungujú zámerne.** `allowed_images` neobsahuje
  `docker:27.1.2` ani `docker:27.1.2-dind`. Build joby potrebujú DinD,
  DinD potrebuje `privileged`, a to by zrušilo celý profil.
  **Od 15. 9. 2026 to nie je obmedzenie, ale súlad s realitou:** stage `build`
  z `.gitlab-ci.yml` zmizol celý, lebo vyrábal obrazy, ktoré nič nečíta
  (produkcia na delle stavia z `build:` kontextu). Preto sa 15. 9. 2026
  `bitnami*`/`kubectl` položky z `allowed_images` **odstránili** — biela
  listina, ktorá drží obraz pre job, ktorý neexistuje, len predstiera, že
  niečo chráni.
- **Service kontajnery pre `backend_tests`.** `allowed_images` preto obsahuje
  aj `postgres:16-alpine` a `redis:7-alpine` — rovnaké verzie, aké prevádzkuje
  produkcia (`docker-compose.yml`). Nie sú to job obrazy, ale služby, ktoré si
  job pýta cez `services:`; runner ich vytvára cez ten istý socket proxy
  (`IMAGES=1`, `CONTAINERS=1`, `NETWORKS=1`), neprivilegované ako job.
  Bez nich testy backendu nebežali vôbec: bez `DATABASE_URL` sa `settings.py`
  ticho prepne na SQLite a tam `create_test_db` spadne na migrácii
  `companies/0014` (`text_pattern_ops` je Postgres-only), takže job bol
  červený vždy a nekontroloval nič.
- **DNS v joboch.** Kontajnery dostávajú DNS z routera (`192.168.1.1`),
  ktorý o `home.arpa` nevie. dnsmasq na tailnet IP (`100.120.104.84:53`)
  z docker bridge **neodpovedá** — Tailscale to blokuje (overené:
  `connection timed out`). Preto statický `extra_hosts` v `config.toml`
  (pre joby) aj v `docker-compose.yml` (pre runner). Overené: `git ls-remote`
  z kontajnera funguje. **Ďalší `*.home.arpa` hostname treba pridať na obe miesta.**

## Ako na tomto runneri závisí CI

Toto je **jediný runner**, ktorý cistafirma má. Mac svoj runner stratil
15. 9. 2026 (Mac je len na vývoj), dell runner zámerne nikdy nedostane
(produkcia s neopraviteľným Postgres volume).

`.gitlab-ci.yml` nemá v žiadnom jobe `tags:`. Runner preto musí mať
**`run_untagged = true`**, a to je nastavenie **na serveri GitLabu**, nie
v `config.toml`:

```bash
docker exec gitlab-server gitlab-rails runner \
  'Ci::Runner.find(1).update!(run_untagged: true)'
```

**V `config.toml` je `run_untagged` pre už registrovaný runner inertný** —
runner ho posiela len pri registrácii. Overené 15. 9. 2026: po prepísaní
configu na `true` a reštarte ostal v GitLabe stav `false` a
`ci_runners.updated_at` sa nepohol. Preto v `setup-config.sh` nie je tento
kľúč nastavený — je tam len komentár s týmto príkazom.

Bez tohto prepínača **runner nespustí ani jeden job** a pipeline sa tvári
zdravo, len joby ostávajú `pending`. Presne to sa stalo 11. 9. 2026 a štyri
dni to nikto nevidel.

> Ak joby visia v `pending` a runner je `online`, je to takmer vždy toto.

## Čo ešte treba spraviť (nespravené, čaká na teba)

1. **Zvyšný root súbor `/etc/gitlab-runner/config.toml`** (3488 B, root:root
   0640). Pochádza z nepodareného behu natívneho inštalačného skriptu a
   **obsahuje runner token**. Nič ho nečíta — kontajner má vlastný config
   v `/home/sam/gitlab-runner/config/`. Na zmazanie treba root:

   ```bash
   sudo rm -rf /etc/gitlab-runner
   ```

2. **Zrotovať runner token.** Pri skúmaní rozbitého generovaného configu
   (15. 9. 2026) bol token vypísaný v čitateľnej podobe do logu session —
   nie je to únik mimo stroja, ale token bol videný a má sa pokladať za
   prezradený. Žije v `gitlab-runner-setup/runner-token.txt` a v
   `config/config.toml`. Rotácia: vygenerovať nový v GitLabe
   (Settings → CI/CD → Runners) a spustiť `setup-config.sh` znova.

3. **`gitlab-runner_19.3.2-1_amd64.deb` (30 MB)** v
   `/home/sam/gitlab-runner-setup/` je zvyšný, netreba ho.

### Čo je naopak vyriešené (15. 9. 2026)

- **`bitnami/kubectl:1.30` neexistuje** — už neškodí. Job `helm_k8s_validate`,
  ktorý ho používal, bol z `.gitlab-ci.yml` odstránený spolu s celým deploy
  stage (nemal ako prejsť: `--dry-run=client` aj tak robí discovery voči API
  serveru a klaster nemáme).
- **Tagy sa do `.gitlab-ci.yml` necommitli.** Zvolila sa serverová cesta
  (`run_untagged = true`), ktorá je pre projektový runner prirodzenejšia.
  `commit-ci-tags.rb` aj `/home/sam/gitlab-runner-setup/ci-tags.md` ostávajú
  ako pripravená alternatíva, keby raz bolo treba runner presunúť inam —
  explicitný `tags:` je viditeľnejší a prežije prenos projektu.

## História: prečo nie natívny balík

Prvý pokus bol nainštalovať `gitlab-runner` ako natívny deb. Zlyhalo to:
balík závisí od `gitlab-runner-helper-images (= 19.3.2-1)`, čo je **538 MB**
samostatný balík, ktorý v stiahnutom deb nie je. `dpkg -i` preto spadol na
závislostiach, `apt-get -f install` ho odstranil, a inštalačný skript
pokračoval ďalej a hlásil úspech — **to bola chyba toho skriptu, neoveroval
výsledok inštalácie.** Skript je preto premenovaný na
`install-runner-native-OBSOLETE.sh` a je označený ako nepoužiteľný.

Kontajnerová cesta je lepšia aj tak: image už bol na disku (489 MB),
nepotrebuje 538 MB závislosť ani žiadne rozšírenie sudo práv.
