# Plán prác — CistaFirma

**Aktualizované:** 2026-09-13
**Vetva:** `feat/ai-ready-baseline` (celá lokálna, bez upstreamu)
**Autor:** Samuel Šugra + Claude Code

Toto je živý dokument. Hovorí, čo je hotové, čo sa práve robí a čo ešte
čaká — vrátane vecí, ktoré sa nedajú spraviť a prečo. Keď sa niečo dokončí,
prepíše sa sem jeho stav; keď sa nájde nový problém, pribudne sem.

---

## Ako sa to číta

| stav | znamená |
|---|---|
| ✅ **Hotové** | nasadené, otestované, commitnuté |
| 🔄 **Robí sa** | rozpracované v tejto chvíli |
| ⏳ **Čaká** | vieme ako na to, ešte nespriahnuté |
| ⛔ **Blokované** | narazili sme na prekážku, ktorá sa nedá obísť kódom |
| ⏭️ **Vedome vynechané** | rozhodli sme sa to nestavať |

Pre sekcie firemného profilu je zdrojom pravdy
`frontend/companySections.ts` — jeden vlastník zoznamu, na ktorom sa musia
zhodnúť navigácia, routa aj telo sekcie. Typecheck nedovolí označiť sekciu
`ready` bez tela.

---

## 1. Hotové v tomto cykle

| # | Vec | Commit |
|---|---|---|
| 79 | Odkaz na portál RUZ funguje — `domain/accountingentity/show/<ruz_id>`, stará trasa vracala 403 | `fd23ba9` |
| 80 | `CompanyFinancialResult.ruz_statement_id` — sync ho zapíše z id, ktoré už drží v ruke | `fd23ba9` |
| 81 | Závierky sa sťahujú z nášho API, nie odkazom na register | `fd23ba9` |
| 82 | Kliknutie na rok vypíše dokumenty a stiahne ich | `fd23ba9` |
| 84 | „Sledovať" prihlásene vedie na prihlásenie a vráti čitateľa späť na firmu | `0dd2565` |

**Overené naživo:** výpis dokumentov pre ECKLIMA s.r.o. (IČO 48097781)
a stiahnutie reálneho 852 417-bajtového PDF so slovenským názvom.

---

## 2. Robí sa

### #83 — RUZ inkrementálny sync od 11. 9. mlčky nerobil nič

**Príčina.** `fetch_ruz_data` preberal `pokracovat_za_id` z
`SyncProgress.last_processed_ruz_id` aj pri **novom** behu, nielen pri
`--resume`. Beh #12 (10. 9. 18:27) prešiel okno až do konca a nechal tam
posledné id (2624307). Každý ďalší beh sa tak pýtal na zmeny *za koncom okna,
ktoré už dokončil*. Overené naživo:

- `zmenene-od=2026-08-04` samo → 1000 id
- to isté s `pokracovat-za-id=2624307` → **0 id**

Prázdna stránka je pritom legitímna podmienka „došli sme na koniec", takže beh
zavolal `complete_job` a uložil sa ako `completed` s nulou položiek. Desať
behov za tri dni. A `zmenene_od` sa nikdy neposúval, takže okno zostarlo.

**Oprava — tri časti, ktoré fungujú len spolu:**

1. ✅ **Cursor nesmie prežiť svoj beh.** Bez `--resume` sa začína s
   `pokracovat_za_id = None`.
2. ✅ **Okno sa posúva.** Po dokončenom prechode sa `zmenene_od` nastaví na
   deň začiatku behu **mínus jeden deň prekrytia** — `zmenene_od` je len
   dátum, a firma zmenená v posledných hodinách okna by inak prepadla medzi
   dvoma oknami.
3. ✅ **Čestná kontrola.** `sync_health` má štvrtú podmienku: okno staršie
   než `CISTAFIRMA_SYNC_WINDOW_DAYS` (default 3) na riadku, ktorého posledný
   prechod skončil. Súdi sa **vekom, nie počtom položiek** — vek okna je stav,
   nie prah na objem. Presne to tu chýbalo: `make ops-check` bol zelený,
   pretože nič nezlyhalo.

**Stav:** prvá oprava commitnutá v `b7aa428` (611 testov zelených, predtým 595);
oprava dier, ktoré našla revízia, v tomto commite (679 testov zelených).

**Overené naživo proti bežiacej databáze** — nová kontrola hlásila práve jedno
`FAIL` a bol to jediný riadok, ktorý to hovoril:

```
  incremental   completed  2026-08-04  40d old  FAIL
  (sync window 'incremental': the last completed walk left the window
   starting 2026-08-04 (40d old), and every run since has reported success
   without moving it ...)
```

Sedem po sebe idúcich `ruz_incremental` behov predtým: všetky `completed`,
všetky s nulou spracovaných položiek.

**Toto už neplatí a je dôležité, prečo.** Kým opravný beh #23 beží, riadok má
status `running`, a `running` sa zámerne nesúdi — takže kontrola práve teraz
nesúdi **nula** riadkov. Verdikt teda visí na tom, že sa stav raz zmení. To je
správne správanie (beh v pokroku nie je zastavený sync), ale znamená, že
„kontrola hlási FAIL" je tvrdenie o minulom stave, nie o tom súčasnom.

**Adversariálna revízia (2026-09-13) — jadro drží, tri diery boli reálne.**
Nezávislý recenzent prešiel šesť útočných bodov a našiel tri veci, ktoré
oprava sama zaviedla. Opravené v tomto commite:

1. **Okno sa posúvalo aj po zlyhaných položkách.** `get_company_details`
   vracia pri transportnom zlyhaní `None` (default `raise_on_transport_error=
   False`), beh to zapíše ako `skipped` **bez per-firmového riadku** — a okno
   sa posunie za firmu, ktorá sa nikdy neprečítala. Pred opravou sa okno
   neposúvalo, takže sa čítala znovu; oprava tú poistku odstránila. Teraz je
   klient **striktný** (`RuzUnreachable` → chyba položky) a okno sa posúva len
   keď `errors == 0`. Podložené meraním: **žiadny RUZ job v tejto databáze
   nikdy nemal `failed_items > 0` ani `skipped_items > 0`**, takže podmienka
   v praxi nič nestojí. „Nemáme záznam" (`skipped`) sa naďalej posúva — register
   odpovedal, že firma neexistuje, a to je fakt o firme, nie diera.
2. **`full*` behy si okno posúvali samy.** `full` má hardcoded `2000-01-01`,
   ale `full_companies` / `full_individuals` čítajú štart **z toho istého
   stĺpca** — zápis `dnes - 1` by ďalší full resync zúžil na jeden deň.
   Posun je teraz len pre inkrementálny prechod.
3. **Focus Mode by zhasil bránu za dokumentovanú akciu.** `fetch_ruz_data_task`
   zámerne nie je v `FOCUS_KEEP_TASKS`, takže Focus Mode vypne beat a okno
   zostarne — a nová podmienka by po 3 dňoch dala FAIL s vetou „every run since
   has reported success", čo je **nepravda, lebo žiadne behy neboli**. Presne
   tento problém už raz vyriešil `source_health` (`SOURCES_PAUSED_BY_FOCUS_MODE`);
   `sync_health` má teraz tú istú výnimku. Dnes latentné — `SyncFocusModeState`
   má nula riadkov.

**Zaznamenané, zámerne neopravené** (mimo rozsahu tohto commitu, každé s
dôvodom):

- **`failed` riadok okna sa nesúdi navždy.** Recenzent to nazval slepou škvrtou
  a má pravdu v tom, že kontrola nevie odlíšiť mŕtvy zvyšok od živého synca,
  ktorého dispečer prestal. Ale `incremental_companies` (2447 dní, `failed`) je
  naozaj mŕtvy riadok bez beat entry, takže súdiť ho = trvalý falošný FAIL.
  Správna oprava je súdiť len to, čo beat naozaj dispečuje — to je nová
  väzba `sync_type → PeriodicTask`, ktorá si zaslúži vlastné rozhodnutie.
- **Prerušený beh (`running`, zabitý worker) prejde okno odznova.** Duplicita je
  neškodná (`update_or_create` na `ico`, `detect_status_change` vráti 0), ale
  nafúkne `succeeded_items`. Počítadlá sa nesúdia, takže žiadna kontrola sa
  nemýli.
- **200 s telom bez použiteľného `id`** (napr. obálka proxy) sa číta ako „došli
  sme na koniec" a okno sa posunie. Nevieme to odlíšiť od legitímnej prázdnej
  strany.
- **Tvrdenie v message commitu `b7aa428`**, že `zmenene_od` je „the coarsest
  cursor the register offers", je vecne nesprávne: register prijíma aj časovú
  formu. Hrubý je **náš** `DateField`. História sa už prepísala (pushnuté), takže
  opravený je komentár v kóde; message zostáva ako omyl.

**Ešte spraviť:**

- [x] Spustiť prvý beh po oprave — beží ako job #23 od 09:54
- [ ] Overiť, že `zmenene_od` sa posunul a `ops-check` je zelený
- [x] Nezávislé overenie opravy (adversariálna revízia)

---

## 3. Čaká na prácu

### Hľadanie osôb — „v akých firmách figuruje Miroslav Trnka"

Samostatný návrh: `docs/PLAN-OSOBY.md`. Zhrnutie: ORSR to vie naživo
(`search_osoba.asp`), ale **sync podľa mena netreba** — graf osôb už máme
(44 897 osôb, 64 128 väzieb, 19 906 firiem) a endpoint
`/api/persons/<id>/` na „v akých firmách figuruje" už existuje. Chýba len
hľadanie podľa mena. **Blokuje to jedna chyba:** `is_active` sa zapisuje
natvrdo ako `True` a `zanik_funkcie` sa nikdy nedopĺňa, hoci RPO `validTo`
posiela a klient ho aj parsuje — takže naša databáza dnes o všetkých
64 128 väzbách tvrdí, že sú aktuálne.


### #85 — Minimapa so sídlom firmy (rozhodnuté)

Podobne ako to má FinStat.

- `Company` má `ulica` / `mesto` / `psc` **štruktúrovane**: `mesto` a `psc` na
  100 %, `ulica` na 99,7 % z 445 626 riadkov
- len **2 919 rôznych miest** — takže join na úrovni mesta je 2 919 hodnôt,
  nie 445 tisíc dopytov

**Prieskum 2026-09-13 prepísal dve veci v pôvodnom postupe.** Obe boli
overené proti živému zdroju (hlavička stiahnutého súboru, SPARQL katalógu),
nie prevzaté z dokumentácie:

1. **Zdroj nie je ŠÚ SR, ale MV SR.** Dataset `Adresy podľa krajov (csv)`
   (`data.gov.sk/set/b27f57f1-7e76-45e0-8968-631f9176b2e9`, priamy download
   `data.slovensko.sk/download?id=d22c42f3-82b5-450d-b8fb-4245d50a31ec`)
   publikuje podľa SPARQL katalógu `dct:publisher` = `legal-subject/00151866`,
   teda **Ministerstvo vnútra SR**. ŠÚ SR pri adresách nefiguruje.
   `dct:modified` = **2026-08-21**, `accrualPeriodicity` = **QUARTERLY**,
   `content-length` = **162 404 526 B** — všetko overené nezávisle.
2. **Geokódovanie netreba vôbec.** Stiahnutá hlavička je
   `IDENTIFIKATOR;KRAJ;OKRES;OBEC;CAST_OBCE;ULICA;SUPISNE_CISLO;ORIENTACNE_CISLO_CELE;PSC;ADRBOD_X;ADRBOD_Y`
   a `ADRBOD_X`/`ADRBOD_Y` sú zemepisná dĺžka a šírka v desatinných stupňoch
   (desatinná **čiarka**). Že ide o WGS84, plynie z kontrolnej vzorky —
   `Badín, PSČ 97632 → 19,121502 / 48,6661543` je skutočne Badín — a zo
   sesterských GeoJSON datasetov MV SR, ktoré sú explicitne `CRS84`.
   Transformácia zo S-JTSK teda netreba. Z 1 739 536 riadkov má 2,0 % prázdne
   súradnice, ale **každá `OBEC` má aspoň jednu platnú**.

**Licencia: CC0 1.0** podľa `termsOfUse` distribúcie. *Toto je jediné tvrdenie
v tejto sekcii, ktoré som nevedel overiť sám* — stránka s podmienkami je
JavaScriptová aplikácia, ktorá bez JS vráti len prázdny shell, a katalóg
`dct:license` na úrovni datasetu nevedie vôbec. Pred zverejnením odvodených
dát treba licenciu potvrdiť z prehliadača.

**Nominatim je vylúčený.** Jediný korektný dopyt s vlastným `User-Agent`
vrátil **HTTP 403** podľa vlastnej politiky používania — presne ten druh
cudzieho limitu, ktorému sa tento projekt vyhýba, a to sme poslali *jeden*
dopyt, nie 2 919. OpenAddresses je tá istá dáta o vrstvu ďalej: v ich
`sources/sk/countrywide.json` je ako zdroj uvedená tá istá URL.

**Dve úskalia, ktoré patria do implementácie, nie do poznámky pod čiarou:**

1. **Bratislava a Košice sú v registri rozdelené na mestské časti**
   (`Bratislava-Staré Mesto` … 17, `Košice-Sever` … 22) a **holý riadok
   `Bratislava` ani `Košice` neexistuje**. Náš `Company.mesto` pritom takmer
   isto obsahuje holé názvy, takže naivný join by ticho zahodil dve najväčšie
   mestá na Slovensku — presne tá trieda tichého zlyhania, ktorú tu máme
   pomenovanú ako hlavnú.
2. **Nenamapované mestá sa musia vypísať**, nie zahodiť. Pokrytie je úplné
   (2 817 `OBEC` proti 2 927 z GeoNames, chýbajú len dva vojenské obvody), takže
   každá nenamapovaná hodnota je chyba nášho kľúča alebo cudzí zápis v `mesto`.

**Zvolený postup:**

1. **Zdroj:** CSV MV SR (vyššie) — jednorazový import, agregácia na `OBEC`
   (ťažisko alebo medián `ADRBOD_X`/`ADRBOD_Y`, **nie prvý riadok**) → ~2 817
   riadkov. K importu sa zapíše `dct:modified` zdroja ako verzia, aby bolo
   vidno, z čoho dáta sú.
2. **Dlaždice:** OpenStreetMap — jediná povolená URL
   `https://tile.openstreetmap.org/{z}/{x}/{y}.png` (subdomény `a/b/c` nie),
   viditeľná atribúcia „© OpenStreetMap contributors", cache ≥ 7 dní, žiadny
   prefetch. Číselný limit neexistuje, ale je to „best-effort" bez SLA — pre
   verejný launch treba platený alebo self-hosted zdroj. Repo nemá CSP, takže
   dlaždice nič neblokuje.
3. **Knižnica:** `react-leaflet@5` (`peerDependencies: react ^19.0.0` — repo je
   na 19.2.3, teda sedí) + `leaflet@1.9.4`, lenivo načítané. Verzie 4.x chcú
   React 18 a pýtali by `--legacy-peer-deps`.
4. **Umiestnenie:** kompaktná karta pod adresným riadkom v `CompanyHeader.tsx:199`
5. **Čestnosť — preformulované.** Adresný bod je **zameraný bod vchodu do
   budovy**, nie odhad, takže poznámka o približnosti nepatrí zdroju. Nepresné
   je **naše priradenie adresy firmy** (máme `mesto`, nie vchod) — a to je aj
   poctivá formulácia pre používateľa.

**Ešte spraviť:**

- [ ] Import command + tabuľka `City` (`mesto`, `lat`, `lon`, verzia zdroja)
- [ ] Normalizácia `Bratislava`/`Košice` na mestské časti + report nenamapovaných
- [ ] Backend: vrátiť súradnice v payload-e firmy
- [ ] Frontend: karta s mapou + poznámka o približnosti

---

## 4. Blokované — a prečo to nie je len tak

Tieto dve narazili na **tú istú prekážku** a je dôležité pomenovať ju presne:
nie je to klasifikácia textu, ako sme si najprv mysleli.

| sekcia | stav | prekážka |
|---|---|---|
| **Platobné rozkazy** | ⛔ | Rozhodnutia majú štruktúrované pole „forma rozhodnutia" a „Platobný rozkaz" nesie 594 608 z nich — to nie je problém. Problém je, že **rozhodnutie neobsahuje IČO ani účastníka**. Priradiť rozkaz firme sa dá len hľadaním mena v plnom texte, a „Slovnaft" sa tak vráti 4 472-krát, aj ako zmienka. Sekcia by tvrdila príbuzenstvo, ktoré nevieme overiť. |
| **Súdne rozhodnutia** | ⛔ | Otvorené dáta MS SR, CC BY-SA 4.0, s katalogizovaným príznakom, že obsahujú osobné údaje. Naša pôvodná poznámka „bez API" bola nesprávna — popri hromadných súboroch (zmrazené na máj 2024) beží nezverejnený REST API na `obcan.justice.sk/pilot/api`, aktuálny k dnešnému dňu. **Rovnaká prekážka: chýba IČO a pole účastníka.** |

**Čo by to odblokovalo:** entitné rozlíšenie (entity resolution) — priradiť
meno z textu konkrétnej firme tak, aby sa dalo obhájiť. To je samostatný
projekt, nie úloha do sekcie.

---

## 5. Vedome vynechané

| vec | prečo |
|---|---|
| **Exekúcie** | Bezplatný register MS SR pokrýva len exekúcie po 1. 4. 2017 a len ručným vyhľadaním. Strojová cesta je platená (CRE, 1,60 € za prístup) — a exekúcie spred 2017 sú výhradne tam. Rozhodnutie: nestavať. |

---

## 6. Stav firemných sekcií

Zdroj: `frontend/companySections.ts`. Dvadsať sekcií, z toho sedemnásť hotových.

| sekcia | stav |
|---|---|
| Prehľad o firme, Rizikové skóre, Obchodný register | ✅ |
| Finančný report, Finančné ukazovatele, Súvaha, Výkaz ziskov a strát | ✅ |
| Účtovné závierky | ✅ *(dokončené 13. 9. — sťahovanie)* |
| Dlhy a pohľadávky | ✅ |
| Udalosti vo firme | ✅ *(tri typy udalostí; plná verzia = agregácia cez šesť zdrojov)* |
| Osoby, Prepojenia | ✅ |
| Podobné spoločnosti, Firmy v kraji, Firmy v odvetví, Firmy podľa zamestnancov, Firmy podľa tržieb | ✅ |
| Platobné rozkazy, Súdne rozhodnutia | ⛔ blokované |
| Exekúcie | ⏭️ |

### Kontrola súvahy — ako je na tom

Sekcia `suvaha` počíta, či `aktíva = vlastné imanie + záväzky + časové
rozlíšenie`. Chýbajúce časové rozlíšenie sa číta ako nula — v 2 326 z 2 336
takých riadkov to tak naozaj je. Kontrola sedí presne v **13 816 zo 14 652
riadkov (94,3 %)**. Keď závierke chýba iné číslo, kontrola to pomenuje a
rovnicu neposudzuje — nesľubuje teda viac, než vie.

---

## 7. Prevádzkové nálezy (mimo kódu)

- ⚠️ **„Plná sada testov" z koreňa repa nespustí nič a vráti 0.** `make test`
  robí `cd backend` a až potom `manage.py test`; spustenie
  `python backend/manage.py test` z koreňa vypíše `Ran 0 tests ... NO TESTS
  RAN` a **exit 0**. Presne tá trieda poruchy, ktorú tu celý čas naháňame —
  zelený výsledok, ktorý nič neznamená. Kto si „overil testy" takto, neoveril
  nič. Správne je `make test`, alebo z koreňa `cd backend && ../venv/bin/python
  manage.py test` (611 testov).
- ⚠️ **Off-site záloha nie je pripojená** — `/Volumes/CistaFirmaBackups`
  nie je namontovaný, `make ops-check` preto hlási 1 FAIL. Lokálne zálohy
  aj posledný restore drill sú v poriadku.
- ℹ️ **Poistný backlog** ~66 tis. firiem je zdokumentovaný ustálený stav:
  jeden plný priechod trvá ~15 dní, 12-hodinový interval len vyberá, čo je
  na rade.
- ℹ️ **`ruz_statement_id`** je zatiaľ na 11 z 58 197 riadkov. Dopĺňa ho
  12-hodinový `schedule_ruz_financials_sync`. **Funkciu to neblokuje** —
  `ruz_documents` si id odvodí naživo a uloží, takže chýbajúci záznam
  znamená jeden request navyše pri kliknutí na rok.
- ⚠️ **Cudzia rozpracovaná zmena v pracovnom strome** —
  `frontend/components/company/sections/PeopleOrgansSection.tsx` je
  upravený a **nie je môj**. Diff zhadzuje fallback `Typ: <typ orgánu>`
  a necháva `structured` nepoužité. Žiadna iná session nebeží, takže je to
  pozostatok. Zámerne necommitnuté — commitovať cudziu prácu by znamenalo
  tvrdiť, že jej rozumiem.

---

## 8. Nemenné pravidlá

Toto sa nemení bez výslovného súhlasu. Detaily v `docs/DATA_PROTECTION.md`.

- Docker volume `cistafirma_postgres_data` je nenahraditeľný a lokálny Docker
  **je** produkcia.
- **Nikdy**: `make docker-reset`, `docker compose down -v`, `docker volume rm`,
  `docker volume prune`.
- **Nikdy** rušiť `make celery-purge`, plný RUZ resync ani restore ako
  rutinnú akciu.
- **Nikdy** nerobiť restore cez bežiacu `cistafirma` databázu.
- Pred každou migráciou alebo deštruktívne vyzerajúcou zmenou: čerstvá
  overená záloha (`make db-backup` + `make db-backup-verify`).
- `.claude/settings.json` drží tieto príkazy zamietnuté na permission vrstve.
