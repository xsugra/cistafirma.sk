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

**Stav:** commitnuté v `b7aa428`, 611 testov zelených (predtým 595).

**Overené naživo proti bežiacej databáze** — nová kontrola hlási práve jedno
`FAIL` a je to jediný riadok, ktorý to hovorí:

```
  incremental   completed  2026-08-04  40d old  FAIL
  (sync window 'incremental': the last completed walk left the window
   starting 2026-08-04 (40d old), and every run since has reported success
   without moving it ...)
```

Sedem po sebe idúcich `ruz_incremental` behov predtým: všetky `completed`,
všetky s nulou spracovaných položiek.

**Ešte spraviť:**

- [ ] Spustiť prvý beh po oprave — spracuje ≥10 000 firiem, ~30–60 min
- [ ] Overiť, že `zmenene_od` sa posunul a `ops-check` je zelený
- [ ] Nezávislé overenie opravy (adversariálna revízia)

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

Podobne ako to má FinStat. Prieskum dopadol výborne:

- `Company` má `ulica` / `mesto` / `psc` **štruktúrovane**: `mesto` a `psc` na
  100 %, `ulica` na 99,7 % z 445 626 riadkov
- len **2 919 rôznych miest** — geokódovanie na úrovni mesta teda nie je
  445 tisíc dopytov, ale 2 919, raz, navždy uložených

**Zvolený postup** (rozhodnuté, lebo je najpresnejší pre slovenské adresy a
bez cudzích rate-limitov):

1. **Zdroj:** oficiálny **Registr adries** ŠÚ SR — presné slovenské adresy,
   jednorazový import datasetu, žiadne API limity
2. **Dlaždice:** OpenStreetMap s povinnou atribúciou
3. **Knižnica:** `leaflet` + `react-leaflet`, lenivo načítané (projekt už tak
   code-splituje `ConnectionGraph`)
4. **Umiestnenie:** kompaktná karta pod adresným riadkom v `CompanyHeader.tsx:199`
5. **Čestnosť:** adresa v registri **nie je** zameraná súradnica — pin nesie
   viditeľnú poznámku „približná poloha podľa adresy v registri"

**Ešte spraviť:**

- [ ] Naimportovať Registr adries a overiť pokrytie proti našim `mesto`/`psc`
- [ ] Geokódovať 2 919 miest jednorazovo, uložiť do DB
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
