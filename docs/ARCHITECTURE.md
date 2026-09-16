# Architektúra

Tento dokument popisuje logickú aj runtime architektúru projektu `cistafirma`.

## 1. Logické komponenty

- `frontend/` – React aplikácia, ktorá volá backend cez `/api`
- `backend/` – Django + DRF API, admin, auth, business logika
- `registers` modul – synchronizácia dát z externých zdrojov a periodické úlohy
- `companies` modul – read-only API pre vyhľadávanie/detail firiem
- `users` modul – registrácia, JWT token, profil používateľa
- Celery worker + beat – asynchrónne vykonávanie a plánovanie úloh
- Redis – broker/result backend pre Celery
- PostgreSQL (resp. SQLite fallback) – trvalé úložisko

## 2. Runtime topológia

```mermaid
flowchart TD
    Browser[Prehliadač] --> Frontend[Frontend Vite/React]
    Frontend -->|/api| Django[Django API]

    Django --> DB[(PostgreSQL / SQLite)]
    Django --> Redis[(Redis)]

    Beat[Celery Beat] -->|schedule| Redis
    Worker[Celery Worker] -->|consume tasks| Redis
    Worker --> DB

    Worker --> RUZ[RUZ API]
    Worker --> ORSR[ORSR]
    Worker --> VSZP[VŠZP]
    Worker --> SOC[Sociálna poisťovňa]
    Worker --> FS[Finančná správa]
```

## 3. Aplikačné moduly (backend)

### `users`

- JWT autentifikácia (`/api/auth/token/`, `/api/auth/token/refresh/`)
- Registrácia (`/api/auth/register/`)
- Profil (`/api/auth/profile/`)

### `companies`

- List/search/detail endpointy pre firmy (`/api/companies/`)
- Lookup podľa `ico`
- Agregovaný detail vrátane ORSR profilu a finančných výsledkov

### `registers`

- Trigger endpointy pre manuálne spustenie sync taskov
- Celery tasky pre RUZ, ORSR, finančné výsledky, poisťovne
- Orchestrácia full/incremental/repair sync flow

### `adminapi`

- Admin API endpointy (`/api/admin/`)
- `AuditLogMiddleware` pre logovanie admin operácií

## 4. Dátová synchronizácia

Periodické úlohy sú zapísané **dvakrát** a obe miesta musia súhlasiť:

- `CELERY_BEAT_SCHEDULE` v `backend/backend/settings.py` — čitateľný zápis
  zámeru, ale **nie to, čo naozaj beží**.
- Tabuľka `PeriodicTask` (`django_celery_beat`) — `celery_beat` beží s
  `--scheduler django_celery_beat.schedulers:DatabaseScheduler`, takže
  dispatcher číta riadky z DB. Zmena dávky (`args`) v `settings.py` bez zmeny
  riadku teda **nič neurobí** a naopak.

Preklad: `sync-ruz-financials-every-12-hours` má v DB `args=[2000]` (2 000
firiem / 12 h); rovnaké číslo je aj v `settings.py`. Obe sa menia spolu.

Queue layout (každá queue mapuje na samostatný Celery worker v K8s):

| Queue | Interval | Úloha |
|---|---|---|
| `ruz_full` | 6 h | Inkrementálne sťahovanie dát z RUZ |
| `orsr` | 4 h | ORSR sync pre chýbajúce profily |
| `financials` | 12 h | RUZ finančné výsledky per-company |
| `insurance` | 12 h | Kontrola dlhov v poisťovniach (VŠZP, Soc. poisťovňa) |
| `celery` (default) | 24 h | Aktualizácia FS dát, sektorové mediány, orchestračné a ad-hoc úlohy |

> `refresh-person-history-every-4-hours` bola **jednorazová, samovyprázdňujúca sa
> oprava**: vyberala firmy, ktorých profil nemá v `structured` kľúč
> `osoby_historia`, a keďže ten istý kľúč zapisuje aj nový čítač, po prečítaní
> posledného profilu už nenaplánovala nič. **17. 9. 2026 boli zmazané obe jej
> vrstvy — záznam v `CELERY_BEAT_SCHEDULE` aj jeho riadok `PeriodicTask`** —
> lebo `refresh_person_history --dry-run` na delle hlásil `0 z 27 426 RPO
> profilov`. Zmazanie, nie vypnutie: vypnutý riadok je kontrola, ktorá sa tvári,
> že niečo rozhoduje nad prázdnou množinou. Dávka bola 2 000 firiem každé 4 h
> a vychádzala z toho, že queue `orsr` odtečie 15 requestov/min (~133 min na
> dávku), takže sa stihla vyprázdniť pred ďalším plánovaním aj s 500 firmami
> z `sync-missing-orsr-profiles-every-4-hours`. Dispatcher bežal na queue
> `celery`: plánovač na queue, ktorú sám zaplavuje, čaká za vlastným backlogom.
> Samotná úloha `read_person_history` aj jej dispatcher ostávajú — volá ich
> manuálny dispatcher a testy.
>
> Prácu vykonáva `read_person_history`, **nie** `sync_company_orsr_data`, a to
> je zámer. Tá druhá úloha je vstupný bod ORSR *monitoringu* a
> `is_orsr_eligible_company` tam patrí: ORSR vedie len aktuálne záznamy, takže
> sledovať zrušenú firmu znamená míňať cudzí server na odpoveď, ktorá sa už
> nezmení. Či RPO vedie históriu osôb je **iná otázka** a RPO ju vedie celú —
> kým na obe odpovedala tá istá podmienka, 92 z 24 227 čakajúcich profilov
> (90 zrušených, 2 s právnou formou, ktorú ORSR nevedie) nemohlo kľúč získať
> nikdy, populácia teda nemohla klesnúť na nulu a riadok by sa nedal vypnúť
> s čistým svedomím. Overené naživo 2026-09-13: `31408834` (v likvidácii)
> 16 záznamov / 15 ukončených väzieb, `31681271` 62 záznamov, dve cirkevné
> organizácie s `pravna_forma = NULL` po 2 záznamoch — ani jedna nevrátila
> „RPO o firme nevie".
>
> Kľúč `osoby_historia` je zároveň značka „prečítané", takže sa zapisuje **až
> po** úspešnom zápise väzieb; ak extrakcia zlyhá, čítač ho z profilu zase
> odoberie a firma sa vráti do populácie. Bez toho by profil s kľúčom a bez
> väzieb vyzeral ako hotový — presne to sa stalo, keď chýbal stĺpec
> `connections_person.name_normalized`: firma na svojej stránke ticho stratila
> osoby a každý log riadok hovoril, že sync prebehol úspešne.

> `compute-sector-benchmarks-daily` prepočítava mediány (`SectorBenchmark`),
> proti ktorým sa na stránke firmy porovnávajú jej vlastné ukazovatele. Úloha
> mala v docstringu „beží raz denne cez Celery Beat" odjakživa, ale **žiadny
> záznam v `CELERY_BEAT_SCHEDULE` ani riadok v `PeriodicTask` neexistoval** —
> tabuľka bola prázdna a benchmark sa nezobrazoval nikde (ani v PDF). Zapisuje
> výhradne riadky `SectorBenchmark` (`update_or_create`, jeden na NACE sekciu),
> číta len našu databázu a na registre nerobí žiadny request.

> `insurance` je **kapacitne viazaná, nie intervalom viazaná**: interval určuje
> len to, ktoré firmy sú *due* (`last_insurance_debt` staršie ako 12 h alebo
> nikdy), nie to, že sa stihnú za 12 h. Pri 441 714 firmách, dvoch zdrojoch na
> firmu a zámernom `rate_limit='20/m'` trvá jeden plný priechod **~15 dní**.
> Detaily a dôvod, prečo sa rate limit nezvyšuje bez rozhodnutia:
> `docs/SOURCE_DATA_INTEGRITY.md`.
>
> `schedule-insurance-debt-checks-every-12-hours` plánuje **dávku veľkosti
> jedného intervalu** (`INSURANCE_BATCH_PER_TICK`, odvodená z `rate_limit`), nie
> celú due populáciu, a **beží na queue `celery`, nie na `insurance`** — plánovač
> na queue, ktorú sám zaplavuje, čaká za vlastným backlogom a potom sa spúšťa
> opakovane. Všetky tri vrstvy (`CELERY_TASK_ROUTES`, `CELERY_BEAT_SCHEDULE`,
> riadok `PeriodicTask`) musia súhlasiť; na živom systéme rozhoduje **riadok**.

### `SyncJob` vs `SyncProgress`

Dva záznamy, ktoré vyzerajú podobne, ale majú iný životný cyklus:

- `SyncJob` je **per-run** záznam: jeden riadok na jedno spustenie syncu, s
  vlastnými počítadlami (`processed_items`, `succeeded_items`, `failed_items`,
  `skipped_items`) a vlastným `last_heartbeat`, ktorý stráži watchdog.
- `SyncProgress` je **dlho žijúci, kumulatívny** riadok: `get_or_create_active`
  ho medzi behmi recykluje a `start()` resetuje len `started_at`, takže jeho
  počítadlá sa naprieč behmi sčítavajú. Worker log to ukázal priamo: pred
  spracovaním 17 záznamov hlásil 6350 a po ňom 6367.

Preto `SyncProgress` nevie odpovedať na otázku „čo spravil posledný beh?" a
výsledky behu patria na job: zapisuje ich `set_job_outcome()`
(`registers/services/sync_engine.py`), ktoré mení iba počítadlá a `status`
necháva životnému cyklu (`complete_job` / `fail_job`). Bez toho bol job #8
(`ruz_incremental`) uložený ako `completed` s `processed_items=0`, hoci beh
vytvoril 17 firiem — nerozoznateľný od behu, ktorý nič neurobil.

## 5. Vyhľadávací flow (request lifecycle)

```mermaid
sequenceDiagram
    participant U as Používateľ
    participant FE as Frontend
    participant BE as Django API
    participant DB as Databáza

    U->>FE: zadá IČO alebo názov
    FE->>BE: GET /api/companies/search/?q=...
    BE->>DB: query na Company
    DB-->>BE: výsledky
    BE-->>FE: JSON response
    FE-->>U: zoznam firiem

    U->>FE: otvorí detail firmy
    FE->>BE: GET /api/companies/{ico}/
    BE->>DB: company + orsr_profile + financial_results
    DB-->>BE: detailné dáta
    BE-->>FE: JSON detail
    FE-->>U: detail firmy + rizikové signály
```

## 6. Konfigurácia prostredia

- Root `.env` je centrálny zdroj konfigurácie.
- Backend načítava najprv root `.env`, fallback na backend-specific `.env` súbory.
- Docker Compose mapuje backend na host port `8080`, frontend na `5173`.

## 7. Dizajnové rozhodnutia

- **Monorepo** – spoločný release rytmus frontend/backend/deploy.
- **Async pipeline** – heavy I/O synchronizácie mimo request-response cesty.
- **K8s migrate-first deploy** – schéma migrácie pred rolloutom app deploymentov.
- **API-first backend** – frontend závislý na stabilných DRF endpointoch.
- **Plánové limity sa nevynucujú** – `SubscriptionPlan.max_watched_companies`
  a `pdf_reports_per_month` číta len admin a profil, nikde neblokujú operáciu;
  jediné limity, ktoré projekt naozaj uplatňuje, sú DRF throttles v
  `companies/throttles.py`. Je to rozhodnutie, nie nedokončená práca: nemáme
  počítadlo stiahnutí, serverový report endpoint nemá ani volajúceho (PDF sa
  skladá v prehliadači) a žiadny plán sa nepredáva. Vynútiť kvótu na endpoint,
  ktorý nikto nevolá, by vytvorilo kontrolu, ktorá sa tvári zdravo a nerobí nič.
  Dôvod je rozpísaný v docstringu modelu.

## 8. Rizikové miesta

- Kvalita dát / dostupnosť externých API (RUZ, ORSR).
- Queue backlog pri väčšom sync jobe.
- Schéma zmeny vyžadujúce backward-compatible migrácie.
- Konzistencia dokumentácie pri rýchlych zmenách endpointov.
