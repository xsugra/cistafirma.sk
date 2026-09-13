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
| 85 | Sídlo firmy na minimape — ako **oblasť**, nie ako bod (`a6d7b8c`, `16c2ae3`, `100f4d4`); dnešná podoba je z #97 | `100f4d4` |
| 86 | Graf osôb už netvrdí, že každá väzba je súčasná — „nevieme" nestojí pod riadkom, ktorý to práve vyvrátil | `79745d7` |
| 87 | Hľadanie osoby podľa mena, a jedna stránka na osobu | `0963f21` |
| 88 | Výsledky sa delia na naše dáta a živý register | `0963f21` |
| 89 | Jedna osoba je viac riadkov `Person` — zhlukuje sa **pri čítaní**, kľúč je zamrznutý | `9c0b652` |
| 90 | RUZ vracia IČO, ktoré schéma neudrží — stĺpce na 20 znakov, orezanie a spätný import | `dcb839c` |
| 91 | #89 krok 1 — zhlukovanie osôb pri čítaní | `9c0b652` |
| 92 | #89 krok 1 — testy a frontend | `2c469c4` |
| — | Legenda stavu funkcie tvrdila o firme, že sme ju nečítali — pri riadku, ktorý je na stránke len preto, že sme ju čítali. Kreslí ju `roleState.ts` | `70271d1` |
| — | Hĺbka fronty sa súdi per-frontovým prahom — `insurance` má vlastný, odvodený z návrhu (cap = odtok), takže kontrola prestala svietiť na dizajnový stav | `87d755a` |
| 96 | Mapa sídla je oficiálne Google Maps — Leaflet preč, kruh zostal tvrdením, kľúč a Map ID z prostredia. **Prekonané #97 v ten istý deň** | `ed50844` |
| — | Produkčný frontend image dostane obe `VITE_` hodnoty ako `--build-arg`. **Prekonané #97** — build-argy aj obe premenné zmizli, image sa stavia z holého zdroja | `c493eed` |
| 97 | Mapa sídla je OpenStreetMap s vlastnou kartografiou (`maplibre-gl`) — bez kľúča, účtu aj karty; druhá téma je `setStyle`, nie druhá mapa | tento commit |

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

- [x] Spustiť prvý beh po oprave — bežal ako job #23 od 09:54
- [x] Overiť, že `zmenene_od` sa posunul a `ops-check` je zelený
- [x] Nezávislé overenie opravy (adversariálna revízia)
- [x] Reštartovať `celery_worker_ruz` po dokončení job #23 — worker držal starý
      kód v pamäti, takže beatový beh by inak bežal po starom

**Ako to dopadlo (2026-09-13).** Job #23: `09:54:43` → `11:57:35` UTC, teda
**2 h 03 min**, `processed_items=45306`, `succeeded=37118`, `failed=1`,
`skipped=1`. Behy #18–#22 mali predtým každý `processed_items=0` — to je celá
porucha v jednom čísle. `zmenene_od` sa posunul **2026-08-04 → 2026-09-12**
a `make ops-check` hlási `Sync jobs: 0 unmet`, okno `1d old OK`. Jediný unmet
kontrola ostáva tá známa — nenamontovaný `/Volumes/CistaFirmaBackups`.

**Ale tento beh nedokazuje to, čo by sa na prvý pohľad zdalo — a to je
podstatné.** Okno posunul kód, ktorý **predchádza** novej poistke:

- Worker proces sa reštartoval o `09:54:35` UTC, osem sekúnd predtým, než beat
  dispatchol job #23 (`triggered_via=beat_schedule`). V tej chvíli bol na disku
  `b7aa428` (09:53:47) — ale **nie** `d96c368` (11:27:34) ani `680c1b5`
  (11:40:30). Oba vznikli **počas** behu a Python drží modul management commandu
  v `sys.modules` od prvého importu, takže sa do bežiaceho behu nemohli dostať.
- Dôkaz z logu, nie z úvahy: chybový riadok znie
  `Error processing company ID 1520199: value too long for type character varying(8)`
  — to je formulácia **pôvodného** `except Exception`, kým `680c1b5` píše
  `Unstorable record ID …`. A `SyncProgress.notes` je prázdny, hoci `680c1b5`
  by doň zapísal id neuložiteľných záznamov.
- Kód, ktorý vtedy bežal, posúval okno **bezpodmienečne** — `window_end =
  run_started_on - timedelta(days=1)` a `if window_end > parse_date(zmenene_od)`,
  žiadne `holds_window`. (`git show d96c368^:…/fetch_ruz_data.py`, riadky 308–313.)

Čo to teda dokazuje: **`b7aa428` je skutočná príčina aj oprava zastavenia** —
cursor, ktorý prežil svoj beh, je to, čo desať behov zmenilo na nulu položiek.
Čo to **nedokazuje**: že nová poistka drží okno. Tá sa prvýkrát dostala do
workera až reštartom o `12:00:27` UTC a prejde až najbližší beatový beh
(`13:50`). Až ten je meraním poistky; tento beh je meraním opravy cursoru.

Jedna vec na tom sedí náhodou, nie zámerom: jediné zlyhanie je práve ten
deterministický `unstorable` prípad z #90 (`SZZ Základná organizácia 43-1`)
a okno sa cez neho posunulo. To je správanie, ktoré `680c1b5` neskôr zvolil
**zámerne** — vtedy sa tak stalo len preto, že poistka ešte v procese nebola.

**Ako to dopadlo (2026-09-13 13:50).** Beatový beh je job **#24**:
`13:50:06.609` → `13:50:08.678` UTC, teda **2,07 s**, `processed_items=10`,
`ok=10`, `fail=0`, `via=beat_schedule`. V logu workera stojí
`Pokračujem za ID: 0` — to je `b7aa428` vidieť v praxi: čerstvý beh zdedil
**nula** z predošlého cursoru, nie 2,5 milióna. `zmenene_od` ostal
**2026-09-12**, a to je správne: `window_end = deň behu − 1 = 2026-09-12`
a posúva sa len `if window_end > zmenene_od`, čo je nepravda. Okno je teda
už na najnovšom konci a nie je kam posúvať.

**Čo tento beh (ne)dokazuje.** Riadok `Okno neposunuté …` sa neobjavil, čiže
`holds_window` bolo `False` (`unreadable = 0`) — poistka nemusela držať.
To je meranie toho, že poistka **nezavadzala**, nie toho, že správne drží:
vetva, v ktorej okno naozaj podrží, na živých dátach zatiaľ nameraná nebola.

**10 položiek, nie ~1 160, ako som predpovedal — a predpoveď bola zlá.**
Počítal som `45 306 ÷ 39 dní`, lenže job #23 mal to isté `window_end`
(`2026-09-12`) a toho dňa už všetko prečítal. #24 číta ten istý deň druhýkrát,
pretože prekrytie je zámerné, a nájde len to, čo sa zmenilo od 11:57. Desať je
teda **zvyšok**, nie objem dňa.

⚠️ **A jedna pasca v tom istom logu:** `Processed: 58533` a `Errors: 1` sú
**kumulatívne** počítadlá z `SyncProgress`, nie tohto behu. Riadok `SyncProgress`
id=1 to má napísané v `notes` („counters below are cumulative across runs, so
they do not describe a run that ever finished"). Kto prečíta `Processed: 58533`
ako prácu tohto behu, nafúkne ju **5 853-násobne**. Skutočné číslo behu je
`SyncJob.processed_items`.

### #90 — RUZ vracia IČO, ktoré sa do našej schémy nezmestí

Toto je nález, ktorý **odkryl až opravný beh #23** — a keby som ho neriešil,
oprava z #83 by sa ticho zmenila na novú poruchu.

**Čo sa deje.** `Company.ico` je `varchar(8)`. Register ale pre organizačné
zložky vracia **12-znakové IČO**: `001781521576` je IČO rodiča
(`00178152`) plus štvormiestne poradie. Postgres zápis odmietne
(`value too long for type character varying(8)`), záznam sa neuloží a beh ide
ďalej.

Namerané naživo 2026-09-13 — RUZ id `1520199`, `SZZ Základná organizácia 43-1`,
Ružomberok, **13 účtovných závierok**. Nie je to odpad v registri: je to
účtovná jednotka, ktorá riadne zverejňuje. Len sa k nám nikdy nedostane.

**Prečo to bola blokujúca vec.** Oprava z #83 drží okno, keď má beh chyby —
správne, lebo neprečítaná firma sa inak stratí navždy. Ale táto chyba je
**deterministická**: opakované čítanie vráti tú istú dvanásťznakovú hodnotu.
Okno by sa teda neposunulo **nikdy**, každý beh by znovu prečítal celé okno
(47 800 položiek, ~1,5 h) a brána by navždy svietila na červeno s vetou, ktorá
už neplatí. Presne tá trieda poruchy, ktorú má #83 zavrieť.

**Preto som zlyhania rozdelil na dve**, lebo potrebujú opačnú reakciu:

| | čo to je | okno |
|---|---|---|
| `unreadable` | register neodpovedal, záznam sme nevideli | **drží** — je to diera a okno je jediné, čo si ju pamätá |
| `unstorable` | záznam prišiel, schéma ho neudrží | **posunie sa** — opakované čítanie vráti to isté |

Neuložiteľné záznamy sa vypíšu a uložia do `SyncProgress.notes` (id + IČO), aby
diera nebola len počtom. Zámerne **nie** do `CompanySyncStatus(source='ruz')`:
tá dráha znamená „tejto firme sme znovu prečítali dátumy" a 9 244 riadkov tam
dnes tvrdí, že sa to podarilo; zamiešať do toho zlyhanie walku by pokazilo obe
čítania naraz.

**Druhá vec v tom istom náleze.** Register vracia aj IČO **doplnené medzerami**
— `'177474  '`, `'630021  '`, `'9155139 '` — pre staré 6- a 7-miestne IČO.
V databáze sú 3 také riadky a **nikdy nesadnú** na ORSR, RPO ani Finančnú
správu: lookup cesta robí `ico.strip().zfill(8)`, kým walk zapisuje hodnotu tak,
ako prišla. Dve rôzne normalizácie na dvoch koncoch toho istého toku.

**Tretia vec, a je to rozhodnutie, nie oprava: `Company.ico` má `unique=True`,
čo je falošné obmedzenie.** Register drží **viac účtovných jednotiek na jedno
IČO** — dopyt `ico='00177474'` vráti tri rôzne entity (RUZ id 1677, 1049449,
1070716). Zamýšľaný kľúč registra je `ruz_id` (už `unique=True`), nie IČO.

Zmerané 2026-09-13, aby to nebol dohad:

- **Vzorka 40 IČO → presne 1 entita každé. Žiadna kolízia.** Nejde teda
  o systémovú vlastnosť registra, ale o okrajovú populáciu — a tá je
  **organizačné zložky**, presne tá skupina, ktorá nesie to 12-znakové IČO.
- **`.zfill(8)` je na vstupe neobhájiteľné.** Dopyt registra `ico=` chce
  nulami doplnený tvar (`'177474'` → nič, `'00177474'` → 3 entity), ale
  `'177474  '` (DHZ Sološnica) a `'00177474'` (DHZ Nová Kelča) sú **dve rôzne
  sesterské jednotky**. Doplnenie núl ich teda **zlúči do jednej**. Na vstupe
  je obhájiteľné len `.strip()`; `.zfill(8)` smie zostať na lookup ceste, kde
  je to parametr dopytu, nie zápis do schémy.

**Rozhodnuté 2026-09-13, a je to rozdelenie na dve veci, nie jedno rozhodnutie.**

Sweep naprieč backendom a frontendom (**74 nástrojových volaní**) zmenil odhad
dosahu: `unique=True` **nie je** možné zhodiť samostatne. `.get(ico=…)` je na
**13 miestach** a všetky okrem dvoch chytajú len `DoesNotExist` — takže druhý
riadok na to isté IČO by z každého spravil `MultipleObjectsReturned`, teda
**HTTP 500** (`/api/companies/<ico>/`, report, documents, peers, graph,
watchlist, `score_single_company`) alebo pád behu. Ešte horšie sú tiché miesta:
`filter(ico=…).first()` vracia náhodného súrodenca a `notifications/services.py`
na troch miestach rozposiela udalosť jedného súrodenca **sledujúcim všetkých**.

Preto:

- **90a — teraz: schéma, vstup a kľúč behu. `unique` zostáva.** Šírka
  `ico` na 20 v troch tabuľkách (`Companies and SZCO`, `Individual Entities`,
  `registers_orsrcompanyprofile` — všetky tri sú dnes `varchar(8)`, overené
  proti `information_schema`), na vstupe **len `.strip()`**. Zásadnejšie:
  **walk sa previaže z `ico` na `ruz_id`**, čo je skutočný kľúč registra a je
  už `unique`.

  Prečo to nie je kozmetika: dnešný zápis je
  `update_or_create(ico=X, defaults={'ruz_id': Y})`. Keď register vráti pre
  IČO `X` inú účtovnú jednotku `Y`, Django nájde riadok **podľa `ico`**
  a prepíše mu `ruz_id` na `Y` — ak `ruz_id=Y` ešte neexistuje, **prejde to
  bez chyby** a riadok entity `Z` teraz tvrdí, že je entita `Y`. Tichá zámena
  identity, nie kolízia. Kľúčovanie na `ruz_id` to robí nemožným.
- **Kolízia IČO sa tým nestráca, ale prestáva byť deštruktívna.** Ak nový
  `ruz_id` prinesie IČO, ktoré už drží iný riadok, `unique` index vráti
  `IntegrityError` — a ten musí byť **odchytený spolu s `DataError`** ako
  `unstorable` (okno sa posunie, id sa zapíše do `notes`). Bez toho by spadol
  do všeobecného `except Exception`, počítal sa ako `unreadable` a **okno by
  držal navždy** — presne porucha, ktorú zavrela #83.
- **90b — vlastný prírastok: verejný kľúč endpointu.** Čo má
  `/api/companies/<ico>/` vrátiť, keď IČO držia dve entity? Nameraná hustota
  je **nula kolízií na 449 763 riadkoch** `Company`, takže správna odpoveď nie
  je prerobiť verejný kontrakt, ale spraviť jeho voľbu **deterministickou
  a zdokumentovanou** (primárna entita + počet súrodencov v odpovedi), a to
  spolu s tými 13 miestami. Zámerne odložené: meniť kontrakt pre populáciu,
  ktorú sme v dátach ešte nevideli, by bolo rozhodnutie naslepo — a `unique`
  medzitým drží dáta v bezpečí.

**Čo zostáva — vlastný prírastok, nie tento.** Je to zmena schémy na
neobnoviteľnej databáze plus oprava dát, takže:

- [x] **Rozhodnúť kľúč** `/api/companies/<ico>/` pri viacnásobnom IČO — rozhodnuté
      vyššie: verejný kontrakt sa v 90a nemení, `unique` zostáva
- [x] Zmapovať dosah — sweep hotový (13 miest s `.get(ico=…)`, 8 tichých)
- [x] Nová overená záloha — `cistafirma_20260913T120958Z.dump`, `verify` prešiel
- [x] Migrácia šírky + `.strip()` na vstupe + previazanie walku na `ruz_id`
      (v jednej zmene, inak `update_or_create` podľa `ico` narazí na `ruz_id`
      unique)
- [x] `frontend/pages/Monitoring.tsx` — `^\d{8}$` nahradené zdieľaným
      predikátom `looksLikeIco` (`frontend/utils/ico.ts`), rozsah 6–20 zhodný
      s backendovým `_ICO_RE`
- [x] Oprava tých 3 riadkov a spätný import preskočených zložiek — **nie z
      `notes`**, ako tu stálo pôvodne: beh, ktorý ich preskočil, `notes`
      nezapísal, lebo v procese ešte nebol kód, ktorý ich zapisuje (viď #83).
      Menovite teda poznáme **jednu** zložku — RUZ id `1520199` z logu workera
      — a `notes` začne fungovať až od najbližšieho behu po reštarte o 12:00:27.
      Koľko ďalších behov predtým zložku zahodilo, sa už nedozvieme.

**Ako to dopadlo (2026-09-13).** Záloha `cistafirma_20260913T120958Z.dump`
overená, migrácie `companies.0021` a `registers.0016` aplikované
(`varchar(8)` → `varchar(20)` v troch tabuľkách, potvrdené proti
`information_schema`), potom `repair_ico_shape`:

- **`.strip()`**: 3 riadky, **0 konfliktov** — presne tie tri namerané
  (`'177474  '` Sološnica, `'9155139 '` Fecenková, `'630021  '` TJ VATRA).
- **`--ruz-id 1520199`**: `SZZ Základná organizácia 43-1` uložená ako
  `001781521576`, teda záznam, ktorý dovtedy skončil ako `failed` a okno sa
  cez neho posunulo.

Overené na **živej API**, nie na úrovni querysetu — a to je zároveň dôkaz, že
`.strip()` nebola kozmetika a že nezlúčila dve jednotky:

| IČO | pk | entita | ruz_id |
|---|---|---|---|
| `177474` | 353723 | DHZ **Sološnica** | 1825863 |
| `00177474` | 688 | DHZ **Nová Kelča** | 1832086 |
| `9155139` | 390668 | Fecenková Miroslava | 1680728 |
| `630021` | 396989 | TJ VATRA | 1702402 |
| `001781521576` | 449965 | SZZ Základná organizácia 43-1 | 1520199 |

Sološnica a Nová Kelča sú **stále dva rôzne riadky s rôznym `ruz_id`** — to je
ten hazard, kvôli ktorému sa `.zfill(8)` nesmie aplikovať na zápis. Pred
opravou `GET /api/companies/177474/` vracalo 404 (uložené bolo `'177474  '`,
`_company_or_404` robí `get(ico=…)` bez normalizácie); teraz vracia Sološnicu.
Všetkých päť kódov odpovedá 200.

`zfill(8)` po zmene zostáva **len na odchádzajúcich** cestách do cudzích
API (`ruz_api.py:113`, `rpo_client.py:189`, `orsr_scraper.py:603,689`), kde je
to parameter dopytu externého systému, nie zápis do našej schémy — v celom
backendovom kóde už nie je ani jedno `zfill` na lokálnom párovaní riadkov.

Testy: `registers/tests_sync_pipeline.py` (54) + nový
`registers/tests_ico_shape.py` (12) + celá sada **718 OK**; frontend
`npm test` (234), `typecheck`, `build` — všetko zelené.

Dva testy v `tests_sync_pipeline.py` museli dostať **novú premisu**: stavali na
tom, že Postgres odmietne 12-znakové IČO proti `varchar(8)`. Po rozšírení je to
platná hodnota, takže `_FakeRuzApi` má teraz tri tvary — `long_ico_ids`
(12 znakov, teraz **uložiteľné**), `unstorable_ids` (21 znakov, stále odmietnuté)
a `duplicate_ico_ids` (dve entity, jedno IČO → `IntegrityError`). Práve ten
tretí je nová poistka: `IntegrityError` musí byť klasifikovaný spolu s
`DataError` ako `unstorable`, inak by kolízia držala okno **navždy**.


**Koľko ich je**, presne nevieme — jeden na 49 600 prečítaných v tomto okne
a vo vzorke 40 IČO nula. Hustota sa nedá spočítať z registra, len z ďalších
behov.

### #89 — Jedna osoba je viac riadkov `Person` (rozhodnuté)

**Rozhodnutie: `Person.fingerprint` sa nemení. Nezlúči sa ani jeden riadok,
neprepíše sa ani jeden kľúč, nezmaže sa nič. Opravuje sa *čítanie*, nie kľúč.**

Nájdené pri #87 (hľadanie osôb): to isté meno sa v hľadaní ukazovalo trikrát.
Namerané naživo 2026-09-13 — **56 162 riadkov `Person`, 86 179 väzieb**,
a v nich napríklad:

| id | meno | adresa | `fingerprint` |
|---|---|---|---|
| 44903 | Matej Vácha | `Dátum narodenia: 20.08.1992` | iný |
| 44904 | Matej Vácha | *(prázdna)* | iný |
| 45335 | Matej Vácha | `Beniakova, 3100/12, Bratislava - mestská časť Karlova Ves, 841 05` | iný |

Jeden človek, tri riadky, tri odtlačky. `Person` je pritom kľúčovaný na
`fingerprint` (`unique=True`), takže sú to pre databázu traja ľudia.

**Príčina je v extrakcii, nie v identite.** `compute_fingerprint`
(`connections/models.py:29`) berie ako kľúč **meno + poslednú zložku adresy,
ktorá nie je číslo**:

```python
if len(part) > 2 and not part.isdigit():
```

Holé slovenské PSČ (`81103`) **je** číslica, takže pravidlo ho preskočí a kľúč
pristane na **meste**. V dátach je holé PSČ v **33 424** riadkoch a s medzerou
len v **6 426** — kľúč sa teda zdegeneroval na „meno + mesto" (`bratislava`
samotná v **3 832** riadkoch). PSČ `04001` drží **1 284** riadkov `Person`.

**Druhá, väčšia príčina: jeden dokument zapíše jedného človeka dvakrát.**
Z **4 238** skupín `(firma, meno_normalizované)` má **3 558 (84 %) všetkých
členov vytvorených v priebehu 60 sekúnd, medián 7,7 ms**. To nie sú dva zdroje
s dvoma formátmi adresy — to je jeden ORSR dokument, ktorý vykreslí toho istého
funkcionára raz pod `Predstavenstvo` a raz pod `Spoločníci`, a tie dve sekcie
**nemajú tie isté riadky**, takže vzniknú dve adresy a dva odtlačky. Riadkový
kľúč ich nemôže spojiť — a `Spoločníci` navyše nenesie **žiadny dôkaz**
(odtiaľ tie prázdne adresy a „Dátum narodenia" ako adresa: **14** riadkov má
miesto adresy dátum narodenia, **3** majú adresu prázdnu).

**Prečo nie zlúčenie riadkov.** Zlúčenie je jediná operácia, ktorá sa nedá
vrátiť a nie je vidieť:

1. Zlúčením sa **vyrába funkcia, ktorú register nikdy neuvádza** — keby tie dva
   riadky boli otec a syn, výsledok tvrdí, že jedna osoba sedí v predstavenstve
   aj medzi spoločníkmi. Neviditeľne a natrvalo.
2. **Žiadna čítacia cesta nefiltruje „zlúčené"** — značka by nikde nebola
   vidieť, takže chybné zlúčenie sa v produkte neprejaví ako chyba, ale ako
   fakt.
3. Chybná **skupina** je oproti tomu **vysvetlená aj s riadkami, z ktorých
   vznikla** — čitateľ, ktorý vie, že sú to otec a syn, to môže opraviť.
   Zlúčenie tú možnosť berie.

Preto sa zhlukuje **pri čítaní** a každá skupina sa čitateľovi **vypíše aj
s riadkami, z ktorých vznikla** (`PersonRecordsNote`).

**Jedna vec, ktorú zhlukovanie samo vytvorilo — a preto je moja.** Keď sa
väzby z viacerých riadkov spoja, môže vedľa seba vzniknúť to, čo na jednom
riadku nebolo: tá istá firma a tá istá funkcia raz **s dátumom** a raz **bez
neho**. Naživo to je Vácha a firma `52366332` — `Spoločník v.o.s. / s.r.o.`
s `vznik 2019-05-18` a hneď pod tým `spoločník` s `nevieme`. Legenda pritom
`nevieme` vysvetľuje vetou „Funkciu sme pre túto firmu ešte neoverili
v registri", a postavená pod funkciu, ktorú register práve datoval, je to
**nepravda** — datovaná väzba pre tú istú funkciu *je* to overenie. (Do
`70271d1` bola tá veta ešte voľnejšia, „túto firmu sme ešte nečítali", hoci
firma je na stránke len preto, že sme ju čítali.) Väzba bez dátumov nie je
druhé obdobie funkcie — neuvádza žiadne obdobie, takže ani nemôže byť — a keď
pre tú istú funkciu existuje datovaná, zahodí sa. Datované väzby sa do seba
**nikdy** nezlievajú, takže skutočné druhé obdobie prežije. Zmerané: **4 riadky
v celej tabuli**, všetky štyri vznikli zhlukovaním.

**Dve dôkazové pravidlá, nič viac.** Sú to jediné dva tvary, ktoré naozaj
znamenajú „ten istý človek":

| | pravidlo | kedy sa odmietne |
|---|---|---|
| 1 | **jedna firma + jedno meno** — teda jeden dokument | keď si dve neprázdne PSČ odporujú |
| 2 | **jedno meno + jedno PSČ**, hocijaká firma | nikdy (PSČ je zhoda, nie odhad) |

Plus tvrdá poistka: **nikdy sa nespájajú riadky s dvomi rôznymi neprázdnymi
IČO**. Zmerané: bez tejto poistky by sa zlúčila **presne jedna** firemná
skupina navyše — takže je to poistka proti okrajovej populácii, nie proti
systémovej chybe, ale je lacná.

**Prečo je pravidlo 2 bezpečnejšie, než sa zdalo.** Riziko bola predstava, že
dve slovenské dediny môžu mať rovnaké PSČ a rovnaké meno. Zmerané: **20**
zhlukov `meno + PSČ` v celej tabuľke pomenúva viac než jednu obec — a sú to
takmer výlučne **zahraničné adresy** (`nemecka spolkova republika`,
`talianska republika`, `ceska republika`, `nespecifikovane`), nie slovenské
obce. Pravidlo 2 teda zostáva.

**Čo to spraví s delenými osobami naprieč registrami.** **4 038** mien zdieľa
aspoň jednu firmu. **2 745** mien nemá medzi členmi **žiadnu** spoločnú firmu —
a z nich **1 323** má **presne jedno** rôzne PSČ, takže ich pravidlo 2 spojí
bezpečne. Firemné pravidlo samotné zbalí 3 457 mien / 3 592 nadbytočných
riadkov a nechá 581 / 660 nerozdelených.

**Celá tabuľka sa zvládne.** 56 162 riadkov sa načíta za **0,9 s** a zhlukuje
za **0,2 s** → 50 991 zhlukov, 5 171 nadbytočných riadkov zbalených, najväčší
zhluk má **5 riadkov a všetky jedno PSČ**. Napriek tomu je hľadanie **ohraničené**:
najhorší dopyt (`an`) sedí na **20 050** riadkov, takže `PersonSearchView`
prejde `CLUSTER_SCAN_LIMIT = 300` riadkov a keď okno nestačí, vráti
`total_people: null` — „počet, ktorý sme nespočítali, nie je počet nula",
rovnaká úprimnosť ako `coverage: null` v #87.

**Čo bolo zamietnuté.** (a) Zlúčenie riadkov — dôvody vyššie. (b) Prepočítanie
`fingerprint` na `meno + PSČ` a spätné prekľúčovanie — kľúč by sa tým **zlepšil
len o málo**, lebo 84 % duplicít nemá žiadne druhé PSČ na zhode, a stálo by to
prepísanie 56 162 riadkov, na ktoré visia väzby. (c) Zúžený regulárny výraz na
PSČ — líši sa v **76** riadkoch a voľnejší tvar zachraňuje
`Bratislava … Nové Mesto 831 04`, kde je PSČ zapísané do zložky mesta; prijatý
falošný poplach je `HRB 29493`, ktoré sa číta ako PSČ. (d) Zlučovanie podľa
holého mena (bez PSČ) — to je presne trieda, ktorá spája otca so synom.

**Kroky.** Krok 1 je hotový (tento commit). Kroky 2–4 menia **zápis**, a preto
každý z nich začína **čerstvou overenou zálohou** (`make db-backup` +
`make db-backup-verify`) a **nie je schválený**:

1. ✅ **Zhlukovanie pri čítaní** — `connections/identity.py` (čistý modul, nič
   neukladá), `views.py` (hľadanie, detail, oba grafy), `PersonRecordsNote`.
2. ⏳ **`Person.birth_date`** (`DateField`) — aditívna migrácia.
3. ❌ **Zapisovač preberá namiesto vytvárania — vypúšťam.** Takto napísaný krok
   je to isté zlúčenie, len o poschodie nižšie: keby zapisovač pri zhode prebral
   existujúci riadok, zmizne práve to, čo robí zhlukovanie bezpečným —
   **vypísanie riadkov, z ktorých skupina vznikla**, aj možnosť ju vrátiť.
   A keďže obe zložky jedného dokumentu nesú **rôzne adresy** (Vácha: jedna má
   dátum narodenia, druhá ulicu), jedna z nich by sa ticho zahodila — práve tá
   informácia, ktorá ich od seba odlišuje. Rozhodnutie z tohto cyklu znie
   „nezlučovať"; krok 3 by ho obišiel.
4. ⏳ **Dátum narodenia sa prestane ukladať ako adresa** — ale **závisí od
   kroku 2, nie od kroku 3**. Ten údaj drží nový stĺpec; preberanie riadkov
   s ním nemá nič spoločné. Pôvodná väzba bola nesprávna.

**Prečo je dátum narodenia v adrese vôbec.** Nie je to zvláštny prípad, ale
**záchytná vetva**: `orsr_scraper.py:468` ukladá do `address_lines` **všetko,
čo nespozná** — spoznáva `Vznik funkcie`, `Iné identifikačné číslo`, `IČO`
a zopár fráz (`osoba je…`), zvyšok ide do adresy. Riadok `Dátum narodenia: …`
nespoznáva, tak sa z neho stane adresa.

Zmerané 2026-09-13: dvojbodku v adrese má **27** riadkov a z toho **14** je
dátum narodenia — a **vo všetkých 14 je dátum celá adresa**, teda dokument
adresu nemal vôbec. Zvyšných 13 sú skutočné zahraničné adresy
(`No: 1C`, `D: 3`, `Box: 453193`). Z toho dvoch vecí:

- Oprava „riadok s dvojbodkou nie je adresa" je **odmietnutá** — zhodila by
  13 platných adries.
- `birth_date` dnes **nie je silnejší dôkaz totožnosti**, než sa zdalo:
  register nám dátum ukáže len tam, kde adresu nemá. Krok 2 má teda cenu
  „prestať sa vlámať do `address`", nie „lepšie spájať osoby". Či register dáva
  dátum aj k adrese, z našich dát **nezistíme** — to by chcelo čítanie
  z registra, nie dopyt do databázy.

**Odporúčanie (na jedno slovo).** Spraviť **krok 2 a krok 4 spolu, v jednom
incrementu a úzko**: stĺpec pribudne a parser dostane **jednu** vetvu pre
prefix `Dátum narodenia:` — tá hodnota sa uloží do stĺpca a do `address_lines`
sa nepridá. Všeobecné pravidlo „riadok s dvojbodkou nie je adresa" **nie** —
13 platných zahraničných adries je dôkaz, že je nesprávne.

Prečo úzko a prečo vôbec: záchytná vetva na riadku 468 je **všeobecná chyba
(všetko nespoznané sa stane adresou), ale NIE je to všeobecne opraviteľné** —
register píše do toho istého miesta adresy aj ďalšie údaje a my nevieme, ktoré.
Prefix `Dátum narodenia:` je jediný tvar, o ktorom to vieme **isto**, lebo ho
register pomenúva. Test naň patrí k zmene; dnešný stav (14 riadkov, kde je
dátum celá adresa) je meranie, nie odhad.

**Existujúcich 14 riadkov sa nedotkneme** — rovnako ako pri #89 sa neprepisuje
to, čo už je uložené. Opraví ich **#95 sám**: tie firmy sú v rotácii, ktorá
beží, a keď sa prečítajú znova, zapíšu sa už správne. Migrácia dát by teda
robila ručne to, čo bežiaca rotácia spraví za sebou.

Bez tohto rozhodnutia sa nič nedeje a nič nestráca — krok 2 ostáva aditívny
a vratný, `address` sa nemení, kým sa krok 4 nedokončí.

**Testy.** `connections/tests_identity.py` — 34 testov (holé funkcie aj API).
Sada `connections` je **72 OK** (38 pôvodných + 34 nových); frontend 239 OK,
`typecheck`, `build`. Kľúčové prípady: skutočné Vácha riadky 44903/44904/45335
v jednej firme → **1 zhluk**; riadok bez IČO nesmie premostiť dve IČO → 2
zhluky; dve PSČ v jednej firme zostanú oddelené; riadok bez PSČ sa nepridá na
ani jednu stranu → 3 zhluky; `total_people` je `null`, keď okno nestačí.

---

### #95 — História funkcií z RPO sa dopĺňa (beží)

Pôvodný čítač zapisoval `is_active` natvrdo ako `True` a `zanik_funkcie` nikdy
nedoplnil, takže graf o všetkých väzbách tvrdil, že trvajú. Nový čítač
(`read_person_history`) to vie a **beží** — toto je stav dopĺňania, nie nová
práca. Overené 2026-09-13 na bežiacej databáze:

| | 11:00 | 13:34 |
|---|---|---|
| RPO profily (`rpo_id`) | 24 601 | **24 712** |
| z toho s prečítanou históriou (`osoby_historia`) | 2 398 | **2 489** |
| **čaká** | **22 223** | **22 223** |
| väzby celkom | 92 928 | — |
| — `is_active=True` | 5 454 | — |
| — `is_active=False` | 26 103 | — |
| — `is_active IS NULL` (nevieme) | 61 371 | — |

**Fronta sa nedá čítať ako pokrok — a to je druhá pasca tohto čísla.** Za tie
necelé tri hodiny stúpol počet prečítaných histórií o **91** (2 398 → 2 489),
ale `pending_person_history()` je **22 223 v oboch meraniach**: populácia
`rpo_id` totiž rastie tiež (+111), lebo rotácia ORSR priebežne pridáva nové
profily. Prírastok a úbytok sú takmer rovnaké, takže fronta stojí na mieste,
hoci práca pribúda. Identita `rpo_id − osoby_historia = čaká` sedí presne
(24 712 − 2 489 = 22 223); v pôvodnej tabuľke nesedela o 20, čo znamená, že
tie tri čísla neboli namerané v jednom okamihu. **Miera pokroku je počet
prečítaných (2 489), nie dĺžka fronty.**

Jedna dávka **2 000** firiem prebehla **ručne** 10:36:14 → 12:51:16 UTC, teda
2 h 15 min pri ~14,8 firmy za minútu — presne na strope `rate_limit='15/m'`.
V logu workera `orsr` je za tých 12 h **2 001** prečítaní a **0** trvalých
zlyhaní `read_person_history` (všetkých 68 `failed permanently` patrí
`sync_company_orsr_data`, teda monitorovacej rotácii, nie tomuto čítaniu).

**Tá dávka bola moja a „tri dispatche po 10" bol môj vlastný grep.** Postupnosť
je v logoch `celery_default` a `celery_orsr` presne takáto:

| čas (UTC) | čo sa stalo |
|---|---|
| 10:28:56 | `schedule_person_history_resync.delay(10)`, prvý dymový test → **zahodený**: `Received unregistered task of type 'registers.tasks.schedule_person_history_resync'. The message has been ignored and discarded.` Worker bežal kód spred tejto úlohy. |
| 10:30:05 | reštart `celery_default` (ready 10:30:06) |
| 10:30:06 | druhé `.delay(10)` prešlo — `succeeded in 0.81s: 'Scheduled person-history resync for 10 companies'` |
| 10:35:59 | reštart `celery_orsr` (ready 10:36:00), aby načítal nový čítač |
| 10:37:00 | `refresh_person_history --limit 2000` — 2 000 úloh |

Môj merací skript hlásil **tri** dispatche po 10 firmách. Grep na
`Scheduled person-history resync for [0-9]+ companies` totiž chytí aj riadok
`succeeded in …: 'Scheduled person-history resync for 10 companies'` — teda
návratovú hodnotu tej istej jednej úlohy, vytlačenú druhýkrát. Bol to **jeden**
dispatch. Je to tá istá chyba ako `grep -c` v § 7: počítadlo, ktoré nevie
rozlíšiť, čo vlastne počíta, dá sebavedomé číslo.

**Deväť z desiatich úloh zmizlo bez stopy — a to je nález, nie anomália.**
Reštart workera `orsr` o 10:35:59 prišiel po dispatche o 10:30:08. Namerané:
z desiatich úloh sa vykonala **jedna** (10:36:13, `31681271`, 62 záznamov),
`read_person_history` v logu má **2 001** prijatí a 2 001 úspechov, a keďže
dávka o 10:37:00 poslala presne 2 000, na tých zvyšných deväť neexistuje
žiadna stopa — žiadna chyba, žiadny záznam vo `SyncJob`, fronta `orsr` nula.
Práca jednoducho nie je.

Mechanizmus je s tým konzistentný, ale **nie je dosvedčený**: `orsr` beží
`--concurrency=2` a `worker_prefetch_multiplier` nie je v `settings.py`
nastavený, takže platí default `4` — **4 × 2 = 10**, presne toľko, koľko sa ich
dispatchlo, a teda všetky sa v tom okamihu mohli nachádzať v rukách workera.
`task_acks_late` tiež nie je nastavené (default `False`) a `visibility_timeout`
tiež nie. Ktorá z tých páčok to spôsobila, som nemeral; namerané je len to, že
deväť úloh po reštarte nebežalo a nikde to nie je zapísané.

Nič sa teda nestratilo z dávky; stratilo sa z dymového testu spusteného tesne
pred reštartom. Pre #95 to znamená, že **fronta ani dispatch log nie sú miera
pokroku** — miera je počet prečítaných (`osoby_historia`). Tých deväť prežilo
len preto, že selektor je idempotentný a tie firmy vyberie v ďalšom kole;
nebyť toho, je to ticho stratená práca a nikto by si nevšimol. Cena za reštart
workera kvôli novému kódu je až (prefetch × concurrency) rozbehnutých správ —
a je to tá istá trieda chyby ako „unregistered task" vyššie, len bez hlásenia.

**Dve čítania plnia tú istú populáciu a je to zámer.** `osoby_historia`
zapisuje aj `sync_company` (`rpo_sync.py:377`), aj `read_person_history` —
a `_drop_person_history_marker` ju **zoberie späť**, keď extrakcia zlyhá, aby
firma ostala na čakaní a skúsila sa zas, namiesto toho aby ticho zmizla.
Populácia sa preto zmenšuje z oboch strán.

**Odhad dobehu.** 22 223 ÷ 2 000 na tick ≈ **11 tickov ≈ 44 hodín** — ale len
ak populácia `rpo_id` prestane rásť. Keďže medzitým rastie (vyššie), je to
skôr horná hranica než plán; správne meranie je prírastok `osoby_historia`
za tick, nie úbytok fronty. Jedna dávka trvá 2 h 15 min, takže sa do
4-hodinového intervalu vmestí s ~1 h 45 min rezervou — **úzkym miestom nie je
fronta, ale interval**. Fronta `orsr` má 127 správ a prah varovania je 50 000,
takže 2 000-ový skok je bezpečný.

**Tretí spôsob, ako firma z fronty zmizne — a tiež to nie je pokrok.** Keď RPO
k IČO nevráti entitu, `RpoSyncService.sync_company` zalomí na HTML čítačku
(`rpo_sync.py:131-133`), a tá `raw_payload` prepíše **celý a bez `rpo_id`**.
Profil tým z `pending_person_history()` vypadne a jeho už prečítaná história
zmizne — potichu. Nameraných 16 takých profilov; mechanizmus je v § 7.

**Jedna vec, ktorá sa dá prečítať zle.** Beat riadok
`refresh-person-history-every-4-hours` má `last_run_at=None`
a `total_run_count=0`, takže dávku **nespustil on** — spustil ju môj ručný beh
o 10:37:00 (a pred ním dva dymové testy, vyššie).
Prvý beh beat riadku čakám **2026-09-13 17:20:12,9 UTC** (a nie 14:28:25, ako
tu stálo; referenčný bod je `date_changed` riadku, ktorý som si posunul sám
svojím overovacím skriptom — oboje v § 7). To nie je druhá chyba, len
iný spúšťač; ale kým `total_run_count` ostane 0, **nedá sa z neho čítať, či
dopĺňanie napreduje** — a to je presne tá pasca z § 7.

**Meranie, ktoré to rozhodne.** Východisko, odčítané 13:59:37 UTC priamo
z bežiacej databázy:

```
riadok  last_run_at=None  total_run_count=0  date_changed=2026-09-13 13:20:12.935493
pending 22 223     prečítaných (osoby_historia) 2 489
fronty   celery=0  orsr=0  financials=0  insurance=61062  ruz_full=0
```

Ak riadok naozaj vystrelí, o 17:20:12,9 čakám `last_run_at≈17:20:12,9`,
`total_run_count=1`, frontu `orsr≈2000`, `Sending due task` v beatoovi
a `Scheduled person-history resync for 2000 companies` v logu workera.
Dávka sa potom leje 133 minút (2 000 ÷ 15/m) a **populácia sa zmenší len
o to, čo sa naozaj prečíta** — fronta je len medzikrok. Ak riadok nevystrelí,
`date_changed` sa posunul znova a aj to je odpoveď; práve preto sa meria
o 17:21 a o 17:50, nie „o hodinu".

**Predletová kontrola, 14:50 UTC — štyri články reťaze, ktoré ten pokus
o 17:20 mohol ticho zhodiť, a všetky štyri držia.** Bolo by trápne čakať
2,5 hodiny na tick, ktorý nemá ako uspieť, tak som ich overil vopred:

| článok | ako som ho overil | výsledok |
|---|---|---|
| dispatcher je na živom workerovi | `celery inspect registered` | `registers.tasks.schedule_person_history_resync` **aj** `read_person_history [rate_limit=15/m]` sú registrované |
| fronta má svojho konzumenta | `inspect active_queues` | každý worker odoberá **práve jednu** frontu: `celery`→`worker_default`, `orsr`→`worker_orsr`. Dispatcher teda nepristane na tom istom workerovi, ktorý sa o chvíľu zaplaví 2 000 úlohami |
| selektor je naozaj živý a je to cursors | `person_history_batch(5)` | vráti `[3901, 3896, 3904, 3905, 3903]`; najstaršie `last_synced_at` v populácii je **2026-08-05 07:39**, koniec fronty **2026-09-13 13:32** |
| čítač nemôže zahodiť `rpo_id` | `refresh_person_history` (`rpo_sync.py:239-250`) | `payload = dict(profile.raw_payload or {})` — **zlúči**, neprepíše; a ORSR fallback je tam výslovne vypnutý práve preto, že `rpo_id` zhadzuje |

K tomu **aritmetika sedí na jednotku**: `pending 22 223 + prečítaných 2 489 =
24 712 =` presne počet profilov s `rpo_id`. To je nezávislé potvrdenie, že
žiadny profil zatiaľ nezmizol ani jednou z troch ciest opísaných vyššie — a je
to kontrola, ktorá sa dá zopakovať po každom ticku (identity rovnica prestane
platiť presne vtedy, keď začne unikať).

Overené bolo aj to, že **profilová rotácia `osoby_historia` nezmazáva**:
`done` bolo 2 489 o 13:59:37 aj o 14:49, a to naprieč `sync-missing-orsr-
profiles-every-4-hours`, ktorý vystrelil o 12:58:47. Dva vzorky nie sú dôkaz,
takže som to dohľadal v kóde — a je to ten istý mechanizmus ako v riadku
„čítač nemôže zahodiť `rpo_id`" vyššie: čítač payload zlučuje, takže cudzie
kľúče prežijú.

**Dva workery boli medzitým reštartované a tabuľka v § 2 to neuvádza.**
`docker inspect` dáva `celery_worker_default` **12:13:05,8** a
`celery_worker_orsr` **12:13:06,3** (`celery_beat` beží od 10:28:12,5).
Tabuľka vyššie pozná len reštarty 10:30:05 a 10:35:59 — tie boli moje, kvôli
novému kódu; o 12:13 som nič reštartovať nešiel. Podľa mechanizmu, ktorý § 2
opisuje, mohol reštart `orsr` workera o 12:13:06 ticho zhodiť až
(prefetch 4 × concurrency 2) = **10** rozbehnutých čítaní — a padol **doprostred
ručnej dávky**, ktorá bežala 10:37:00 → 12:51:16.

Že sa tak nestalo, sa dá povedať len nepriamo: `done` je 2 489 a dávka bola
2 000, takže ak pred dávkou bolo 489, sedí to na jednotku a nič sa nestratilo.
To „ak" je poctivá hranica tohto tvrdenia — počiatočný stav som si pred dávkou
nezapísal. Je to tá istá trieda ako deväť stratených z dymového testu: **reštart
workera je jediná operácia, ktorá vie zmazať prácu bez jedinej stopy v logu**,
a preto sa počas 17:20 dávky nemá robiť. Ak by ju bolo treba, správne poradie je
počkať na `orsr=0`, nie reštartovať pod záťažou.

#### Verdikt ticku o 17:20 — polovica predpovede vyšla, polovica nie

Predpoveď vyššie bola zámerne konkrétna, aby sa dala vyvrátiť. Odčítané
2026-09-13 o 17:21–17:23 UTC:

| čo som predpovedal | namerané | |
|---|---|---|
| `Sending due task refresh-person-history-…` v beate | `17:20:12.941581` | ✅ |
| fronta `orsr ≈ 2000` | **2 172** | ✅ |
| populácia klesne len o to, čo sa naozaj prečíta | prečítaných 2 489 → **2 789** | ✅ |
| `last_run_at ≈ 17:20:12,9` | **stále `None`** | ❌ |
| `total_run_count = 1` | **stále `0`** | ❌ |

**Riadok teda vystrelil a nezapísal o tom nič.** Tvrdenie na konci
predchádzajúcej časti („`last_run_at=None`, takže dávku nespustil on") bolo
v tom čase správne — dávku naozaj spustil môj ručný beh o 10:37 — ale **ako
pravidlo je nesprávne** a dnešok to dokázal: `last_run_at=None` neznamená „úloha
nebežala". Počítadlo je pri tejto úlohe nepoužiteľné oboma smermi a § 7 to
zapisuje ako samostatný nález.

**Tretí riadok v logu bol zasa tá istá pasca.** `Scheduled person-history resync
for 2000 companies` sa objavil **trikrát**, ale fronta je 2 172 — keby to boli
tri dispatche, čakalo by tam ~6 000. Je to **jeden** dispatch a tá hodnota sa
v logu vypisuje viackrát; presne to isté, čo táto časť opisuje o hodinu vyššie
pri dymovom teste s desiatimi firmami. Keby som frontu nemeral, zapíšem 6 000.

**Kde je fronta teraz a či to stíha.** 2 172 správ čaká, z toho ~2 000 čítaní;
worker `orsr` ale najprv dorába zvyšok profilovej rotácie z 16:58
(`sync_company_orsr_data`), takže čítania stoja za nimi v rade. Strop je
`rate_limit='15/m'` = **900/h** (a hodina 11:00 s 890 prečítaniami ukazuje, že sa
naň naozaj dostane), takže jedna dávka 2 000 sa vyleje za **~133 min** a do
4-hodinového intervalu sa vmestí. Dispatcher žiada 2 000 za 4 h = 500/h, teda
**pod stropom** — fronta teda nerastie donekonečna a odhad ~44 h (11 tickov) na
vyprázdnenie populácie 22 223 platí ďalej.

**Identita drží aj po ticku:** 2 789 + 22 223 = **25 012** = presne počet
profilov s `rpo_id`. Ani jeden profil nezmizol.

#### Ako rýchlo #95 naozaj odteká — a prečo to nie je 44 hodín

Druhá vec, ktorú treba po ticku o 17:20 opraviť, je **odhad dobehu** — nie
preto, že by strop 900/h neplatil, ale preto, že platí len vtedy, keď register
odpovedá. Merané 2026-09-13 večer:

| (UTC) | prečítaných | fronta `orsr` |
|---|---|---|
| 17:21 | 2 789 | 2 172 |
| 20:53 | 3 414 | 1 568 |
| 20:59 | **3 501** | 1 488 |

Za 3 h 32 min (17:21 → 20:53) to je **+625 prečítaní = 177/h**, a v posledných
25 minútach toho okna len **74/h** — ani jedno sa nepribližuje k 900/h. Ale
v zdravom okne 20:53 → 20:59 je to **+87 za 6,8 min = 771/h**, teda rádovo na
strope. Je to kontrola, ktorá sa dá zopakovať kedykoľvek: keď fronta klesá
o 5 správ za 20 s, populácia musí klesať ~900/h.

**Príčina je latencia registra, nie rate limiter.** `read_person_history` volá
RPO s `timeout=30` a `Retry(total=4, read=4, backoff_factor=1.5)`
(`rpo_client.py:183-185`). Jedna entita, ktorá neodpovie, teda stojí
**5 pokusov × 30 s + backoff 22,5 s = 172,5 s**. Worker `orsr` beží
`--concurrency=2`, takže v takom okne prepustí **~42 entít/h** — dvadsaťjedenkrát
pod stropom. Rate limit `15/m` pritom neviaže vôbec: worker nestihne ani
*ponúknuť* 15 úloh za minútu, keď oba sloty drží tri minúty jedna otázka.

Nameraný priebeh to potvrdzuje: v hodine 18:00–19:00 UTC bolo **128 prijatí
a 0 dokončení**, s **474 riadkami `ReadTimeoutError`** na `api.statistics.sk`.
O sedem hodín skôr (11:00) tá istá úloha spravila **890/h** — presne na strope.
Rozdiel medzi tými dvoma hodinami nie je v našom kóde.

**Fronta preto osciluje medzi dvoma režimami — a nerastie donekonečna.**
Nameraný celý jeden cyklus: pred tickom o 17:20 mala `orsr` **172** správ, po
ňom 2 172, a o 20:55 **1 553** — teda ešte pred ďalším tickom takmer dotiekla.
O 20:55 sa fronta zmenšovala o **5 správ za 20 s = 15/min**, čo je *presne*
`rate_limit='15/m'`, a worker pritom spracúval **45 úloh za 3 min** (dĺžky
0,4–2,0 s) — výhradne `read_person_history`. Strop 900/h je teda skutočný
a dosiahnuteľný, a platí **na worker, nie na potomka**: pri `--concurrency=2`
je to 15/min spolu, nie 30/min. (Keby bol limit na potomka, bolo by to 30/min.)

| stav registra | odtok | čistý tok pri dispatchi 500/h |
|---|---|---|
| zdravý (11:00, 20:55) | **~900/h** | **−400/h** → fronta sa vyprázdni |
| degradovaný (18:00–20:00) | ~42–105/h | **+395/h** → fronta narastá |

**Konvergencia teda nie je vlastnosť návrhu, ale vlastnosť počasia na strane
registra** — a dispatcher nemá ako zistiť, ktoré z tých dvoch práve je. Pridáva
2 000 správ bez ohľadu na to, koľko ich ešte čaká, takže **každé degradované
okno zanechá vo fronte trvalý prírastok**, ktorý musí dohnať okno zdravé.
Dnešný cyklus takto pridal ~1 400 správ. Kým sú zdravé okná dlhé, dobehne to;
keď sa degradácia natiahne na dni, fronta rastie rýchlejšie, než sa stíha
vyprázdňovať. Je to náhodná prechádzka, ktorej drift nikto nemeria — tá istá
trieda chyby, akú tento dokument dokumentuje inde: **riadiaca slučka, ktorá
nesúdi výsledok, len záťaž.**

**Opravený odhad dobehu.** Ten pôvodný („22 223 ÷ 2 000 na tick ≈ 44 h") rátal
s tým, že fronta je väzbou. Nie je — väzbou je odtok `osoby_historia`
(~900/h zdravý, mínus ~45/h nových profilov z rotácie ORSR, namerané
25 012 → 25 171 za 3 h 32 min). Keď register drží, populácia sa tenčí
**~855/h**, takže 21 757 čakajúcich je **~25 h nepretržitého zdravia**, nie 44 h.
Degradovaná hodina pritom vráti len ~105 čítaní namiesto 900, čiže **každá
jedna posunie dokončenie o ~0,9 h** — zhruba jedna k jednej.

**A to je presne to, čo `ops-check` nevidí.** Prah varovania pre `orsr` je
**50 000** a jeho komentár ho odôvodňuje tým, že `orsr` „drain to zero: they sit
at 0 in steady state" (`ops_check.sh:59`, prah na `:92`). To už neplatí: od #95
sedí `orsr` v steady state na ~1 500–2 200, pretože dispatcher pridáva 2 000
každé 4 h. Fronta zmenila charakter z „vyprázdni sa" na „udržiava dávku" — a prah,
ktorý z toho vychádzal, je nastavený na hodnotu, ktorú by prekročila až po
mnohých dňoch za sebou. Kontrola teda existuje a je ticho presne vtedy, keď má
čo povedať. Keby `orsr` dostal prah odvodený z jeho nového tvaru — dávka 2 000,
trojnásobná rezerva, teda ~6 000 — dnešný cyklus by ho ešte neprekročil, ale
dvojdňová degradácia áno. **Zámerne nemenené**: prekalibrovať kontrolu, na ktorú
sa spolieha týždenný job (pri zlyhaní zapíše `LAST_FAILURE` a pošle notifikáciu),
si zaslúži samostatné rozhodnutie, nie tichú úpravu v rámci #95.

**Štrukturálny dôvod nízkeho odtoku.** `read_person_history`
a `sync_company_orsr_data` majú **oba** `queue='orsr'` a `rate_limit='15/m'`
(`tasks.py:697` a `:818`) a delia sa o tie isté **dva** sloty. Za 13 h worker
spravil 3 706 profilových rotácií proti 2 454 čítaniam histórie — #95 teda
súperí o sloty s monitorovacou rotáciou, ktorá volá ten istý register, a obe
si navzájom zvyšujú latenciu.

**Hotové** (`fb2713b`). Dispatcher sa teraz riadi hĺbkou fronty, nie pevným
počtom:

```python
backlog = _orsr_backlog()                      # None, keď broker neodpovie
limit   = min(limit, max(0, BOUND - backlog))  # BOUND = 6 000
if limit <= 0: tick preskoč a zapíš prečo
```

Je to poistný ventil, nie škrtič: dávka je 2 000 a rotácia ORSR pridáva 200,
takže zdravá fronta nikdy neprekročí ~2 200 a `min()` sa chytí až pri naozaj
nahromadenom backlogu — na šťastnej ceste sa nemení nič. Zaseknúť sa nedá,
odtok je vždy > 0, takže fronta raz pod strop klesnúť musí a dispatch sa obnoví
sám. A keď sa broker nedá prečítať, dispatch ide neorezaný: najhorší prípad
výpadku má byť pôvodné správanie, nie zastavená populácia.

**Čo sa smie reštartovať a čo nie.** Zmena patrí dispatcheri, ktorý beží na
`celery` → `celery_worker_default`; tej fronte je **0**, takže reštart tam
nestratí nič. Worker `celery_worker_orsr` sa **nesmie** reštartovať, kým má
fronta 1 568 správ — § 2 už nameralo, že reštart pod záťažou ticho zhodí až
`prefetch 4 × concurrency 2 = 10` rozbehnutých čítaní. Zvýšenie `--concurrency`
(sloty sú pri latencii väzbou, nie rate limit) je preto **neskoršia** zmena:
až keď je `orsr = 0`.

---

## 3. Čaká na prácu

### #98 — Kruh okolo sídla je tvrdenie o presnosti; dá sa nahradiť skutočnou budovou

**Otázka Samuela (2026-09-13):** „načo tam je ten kruh okolo toho miesta? to je
zbytočné, ja potrebujem len jedno presné zobrazenie na mape."

**Odpoveď: kruh nie je dekorácia, je to miera nevedomosti.** Dnes spájame výhradne
na PSČ (`PostalCodeArea`, `get_seatLocation`). Stred PSČ je od svojich vlastných
adresných bodov vzdialený **medián 1 980 m (p90 4 118 m)**. Bodka na tom mieste by
tvrdila presnosť vchodu do budovy, ktorú nemáme — a to je horšie než kruh, lebo
tomu číslu nikto nevidí na pravdu. Preto je kruh.

**Ale presnosť sa dá kúpiť za nulu.** Ten istý register MV SR, ktorý už sťahujeme
(zadarmo, bez karty, bez tretej strany), nesie v hlavičke aj
`ULICA;SUPISNE_CISLO;ORIENTACNE_CISLO_CELE;ADRBOD_X;ADRBOD_Y` — teda ulicu,
súpisné aj orientačné číslo a súradnice. `import_postal_codes.py` z neho dnes číta
len `PSC`, `OBEC`, `OKRES`, `KRAJ` a súradnice a zvyšok zahodí. Držíme teda kľúč
od presnej adresy a nepoužívame ho.

**Zmerané 2026-09-13 na všetkých 449 764 firmách** (`match_seat_addresses
--dry-run` po naimportovaní registra — celá tabuľka, nie vzorka):

| úroveň | firiem | podiel |
|---|---|---|
| **budova** (ulica + číslo, jeden konkrétny bod) | 353 463 | **78,6 %** |
| ulica (stred ulice, kruh) | 30 977 | 6,9 % |
| **lepšie než PSČ spolu** | **384 440** | **85,5 %** |
| register to neumiestni — zostáva kruh PSČ | 65 324 | 14,5 % |

Ktorá vrstva odpovedala: `psc_ulica_orient` 281 663 (62,6 %), `psc_ulica_supisne`
38 382 (8,5 %), `psc_ulica` 29 494 (6,6 %), `obec_ulica_supisne` 20 399 (4,5 %),
`obec_ulica_orient` 13 019 (2,9 %), `obec_ulica` 1 483 (0,3 %).

**Ostrý beh to zopakoval na cifru** (dokončený 21:01, 53 minút, 449 764 firiem):
`Considered 449 764 companies; 384 440 changed` — 353 463 budova, 30 977 ulica,
65 324 neumiestnených, a rozpad vrstiev **presne** 281 663 / 38 382 / 29 494 /
20 399 / 13 019 / 1 483. Zhoda suchého behu s ostrým nie je formalita: suchý beh
počíta tou istou funkciou, ale **nič nezapisuje**, takže zhoda je dôkaz, že zápis
nezmenil vstup ani pre jednu firmu — matcher je idempotentný, čo je pri 384 440
zápisoch do zdieľanej tabuľky to, čo chceš vedieť predtým, než ho pustíš druhý raz.

Polomer ulice na celej tabuľke je `min 50 m, medián 296 m, p90 906 m, max 3 793 m`
(50 m je podlaha `MIN_STREET_RADIUS_M`, nie pozorovanie), a budova má polomer
**0** vo všetkých 353 463 prípadoch — čo je presne to, čo karta nesmie vytlačiť
ako „±0 m".

**A import je overený do posledného riadku — pretože diera v spojovacom kľúči je
presne tá chyba, ktorú tu celý čas pomenúvame.** Súbor má 1 739 536 riadkov,
tabuľka `companies_addresspoint` 1 704 346. Rozdiel 35 190 riadkov (2,0 %) som
nenechal ako „asi to sedí": prehnal som **tou istou** postupnosťou preskokov
celý súbor a dostal 1 704 346 a zvyšok **nula**. Celý rozdiel je jediná vec —
35 190 riadkov nemá `ADRBOD_X`/`ADRBOD_Y` alebo sa nedá prečítať ako číslo.
Nula riadkov bez obce, nula bez oboch čísel. Príkaz to hlási ako `no_coordinate`,
takže to nie je tichý preskok, ale ani to nebolo overené, kým sa to nespočítalo.

Vidiecke riadky pritom stoja za zmienku: **943 949** z nich (z 973 318, ktoré zdroj
takto označuje) sa do tabuľky dostane a nesú adresu bez ulice. To je 55,4 %
tabuľky, takže dedinský kľúč nie je okrajový prípad — je to väčšinový tvar
adresy v registri.

**Cesta k číslu bolo šesť meraní a päť z nich opravovalo mňa, nie dáta** — to je
podstatná časť nálezu:

1. 19,8 % presných, 42,4 % „bez zhody" — ale príklady (`Bratislavská 1458/71`)
   ukázali, že register drží súpisné a orientačné číslo v dvoch stĺpcoch a ja som
   ich hľadal spolu.
2. 38,5 % budova — dedinské adresy (`Krajné 52`) majú v `ulica` názov obce
   a register má `ULICA` prázdnu.
3. 55,7 % — ale dedinský kľúč som staval nad všetkými riadkami, takže v obci
   s tromi ulicami sa to isté číslo vyskytlo trikrát a kľúč vyzeral nejednoznačný.
4. 47,9 % — **regresia, ktorú som si spôsobil sám**: osamotené číslo na skutočnej
   ulici (`Starohájska 3`) som skúšal len proti dedinskému kľúču.
5. 79,1 % — a navyše čítač „zamietnuté" som mal vo vnútri slučky kandidátov, takže
   jedna firma sa napočítala viackrát a nafúkla menovateľ.
6. **85,5 % — a to posledné meranie neopravilo kód, ale vzorku.** Vzorka bola
   `order_by("ruz_id")[:4000]`, teda zoradený začiatok, nie náhodný výber; `ruz_id`
   prideľujú krajské súdy v blokoch, takže vzorka obsahovala len tri prefixy PSČ
   (0: 42,9 %, 8: 15,9 %, 9: 41,2 %) a v inom pomere než celá tabuľka (32,2 / 29,2
   / 38,6 %). Dôsledok nebol malý: vo vzorke odpovedala `psc_ulica_orient` v 39,9 %
   prípadov, v celej tabuľke v 62,6 % — posunuté firmy padali na obecnú vrstvu.
   Overené tak, že tá istá vzorka prehnaná **produkčnou** fetch funkciou
   (`match_seat_addresses._fetch_points`, nie kópiou logiky) dala na tie isté riadky
   presne tie isté čísla 2 979 / 185 / 836 — takže kód ani index z CSV sa
   nerozchádzajú a rozdiel bol celý vo výbere. Náhodná vzorka tej istej veľkosti
   dáva 86,2 % a rozloženie vrstiev do 0,4 bodu zhodné s celou tabuľkou.
7. **Tá istá vychýlená vzorka podhodnotila aj samotné jadro metódy.** Skracovanie
   názvov ulíc (`Bratislavská` vs `bratislavska ulica`, `17. novembra` vs
   `17.novembra`, `J. L. Bellu` vs `j. l. bellu`) bolo zmerané na 4 000-vzorke
   a vyšlo z toho „+72 firiem, −13 kľúčov". Na 20 000 náhodných firmiach je to
   **15 333 umiestnených bez skracovania proti 17 106 so skracovaním — 76,7 %
   proti 85,5 %**. Nie je to kozmetika, ktorá pridá zlomok percenta: bez nej
   vypadne skoro každá jedenásta firma o úroveň nižšie. Že ide o skutočný údaj
   a nie o artefakt vzorky, potvrdzuje tretia nezávislá cesta — náhodná vzorka
   dáva 85,53 %, celá tabuľka (`--dry-run`) 85,5 %.

**Pravidlo, ktoré z toho robí čestný údaj — a nie je to detail.** Veľa kľúčov
ukazuje na viac než jeden bod a správna reakcia závisí od toho, **ako ďaleko od
seba tie body sú**:

* **≤ 150 m** — jedna budova s dvoma vchodmi, spriemerovať a je to stále presnosť
  budovy;
* **> 150 m** — dve rôzne miesta; nevyberať. Padá sa na nižšiu úroveň.

**Zmerané znovu na 100 000 firmách vybraných náhodne** (`md5(ico)`), pretože
pôvodné čísla k tomuto pravidlu pochádzali z tej istej vychýlenej vzorky ako
bod 6 nižšie — a tá inde podhodnotila výsledok dvadsaťpäťkrát, takže sa nedalo
predpokladať, že tu je v poriadku:

| | kľúčov | |
|---|---|---|
| kľúč dosiahne **presne jeden** bod | 78 208 | nemá čo merať, rozpätie je 0 |
| kľúč dosiahne **2 a viac** bodov | 6 712 | z toho **485 prejde** (7,2 %), 6 227 padá |

Rozpätie kľúčov, ktoré **prejdú**: medián **30,4 m**, p90 83,6 m, p99 136,1 m,
maximum **145,1 m**. Rozpätie tých, ktoré **padnú**: minimum **154,5 m**, medián
4,23 km, maximum **337 km**. Hranica 150 m teda sedí v medzere **145 – 155 m**,
ktorá je v dátach prázdna: pravidlo neoddeľuje dva podobné prípady, oddeľuje
dvojicu vchodov od dvoch rôznych miest. (Pôvodný text tvrdil „medián 0 m, maximum
51 m" — medián 0 m platí len vtedy, ak sa doň počítajú jednobodové kľúče, ktoré
žiadne rozpätie nemajú; medzi viacbodovými je medián 30 m a maximum 145 m, teda
takmer na hranici.)

Bez tohto pravidla by sme časti firiem pribili špendlík na nesprávnu obec.
Zamietnuté kľúče siahajú od **154 m po 337 km** (medián 4,23 km) — nie preto, že
by dáta boli zlé, ale preto, že **názov obce nie je na Slovensku jedinečný**
(`Nevidzany` existuje v dvoch okresoch, 62 km od seba).

**Druhý nález z merania — a rozhodnutie, ktoré z neho padlo:** dedinské PSČ
pokrýva viac obcí, takže súpisné číslo 52 existuje v každej z nich (rozpätie
2,6 – 5,6 km). Ponúkalo sa preto dedinský kľúč na PSČ **neviazať vôbec**.
Nakoniec sa viaže, ale **ide prvý a spread pravidlo ho zahodí**, keď je rozptýlený:
keď dedinské PSČ sedí na jednu obec, je to silnejšie tvrdenie než obecný kľúč
(firma je v tom PSČ), a keď nesedí, zahodí ho presne to isté pravidlo, ktoré by
inak bránilo obecnému kľúču. Poradie teda nie je detail — je to celá politika:
**úzky rozsah prvý, pretože chyba úzkeho rozsahu je vynechanie a chyba širokého
je lož.** Že to nie je kozmetika, ukazuje 8,5 % firiem, ktoré nakoniec odpovie
práve `psc_ulica_supisne`.

**Návrh — jedno zobrazenie, ktorého tvar nesie presnosť:**

| presnosť | čo sa kreslí | podiel |
|---|---|---|
| `building` | plný bod, **žiadny kruh** | **78,6 %** |
| `street` | stred ulice + kruh tej ulice | 6,9 % |
| `postal_code` | terajší kruh PSČ | 14,5 % |

Kruh teda nezmizne preto, že sme prestali priznávať nepresnosť — zmizne pre **85,5 %
firiem preto, že bod sa stal skutočným**. Tam, kde presnejšie dáta nemáme, zostane
a dostane vetu, ktorá povie prečo. Jedno zobrazenie, nie dve (dnes kreslíme bod
**aj** kruh).

Podiel je zámerne ten istý, aký dáva meranie vyššie, nie odhad: tabuľka sa plnila
z `--dry-run` na celej tabuľke. Že to nie je to isté číslo ako „koľko firiem
odpovie ktorá vrstva", je tiež zámer: vrstva hovorí *odkiaľ* odpoveď prišla,
`precision` hovorí *čo sa dá nakresliť*. `psc_ulica_supisne` odpovie 8,5 % firiem,
ale kreslí bod — číslo je to isté, menovateľ nie.

**Práca:** nový model + migrácia v `companies` (za `0021_alter_company_ico`) pre
vyhľadávacie kľúče ulica/číslo → bod; `import_postal_codes.py` sa rozšíri, aby
popri PSČ agregáte postavil aj tento (ten istý 162 MB súbor, ktorý už leží
v `backend/data/adresy/` — **žiadna nová tretia strana, žiadna karta**); služba
na párovanie so spread pravidlom; `get_seatLocation` vráti `precision` a bod;
frontend kreslí jeden objekt podľa `precision`; testy na všetky tri úrovne aj na
spread pravidlo.

**Bezpečnosť dát:** migrácia pridáva tabuľku (nič nemazne), ale ide na zdieľanú
DB — pred ňou čerstvá overená záloha (`make db-backup` +
`make db-backup-verify BACKUP_FILE=…`).

**Stav: hotové a nasadené** (schválené vetou „pokracuj a vyber vsetko odporucane"
nad #98). Deväť súborov, migrácia `0022_company_seat_lat_company_seat_lon_and_more`
(pridáva stĺpce a jednu tabuľku, nič nemazne), nový `import_address_points`
a `match_seat_addresses`.

**Ale tá istá prírastka prešla aj protirečivou kontrolou — a tá našla deväť vecí.**
Dvadsať agentov, 15 nálezov, 11 prežilo protirečenie, po odstránení duplikátov
9 skutočných chýb. Dve boli v meraniach, ktoré som do tohto plánu napísal vyššie
(a sú opravené), jedna je vážna a je o **tom, čo kruh vlastne zaručuje**:

* **VÁŽNÉ — `is_one_place` je pravidlo o rozptyle, nie o rozsahu.** Funkcia vracia
  `True` pre `len(points) < 2`, a to je ako odpoveď na *rozptyl* správne: jeden bod
  žiadny rozptyl nemá. Lenže to isté pravidlo sa nedá použiť na kľúč, ktorému
  zúženie/rozšírenie zmenilo **rozsah** a ktorý potom dosiahne práve jeden bod.
  `normalize_obec` skladá 17 rôznych hodnôt `Bratislava-*` na `bratislava`, obecné
  vrstvy idú pred PSČ vrstvou ulice — takže neoveriteľné tvrdenie širokého rozsahu
  predbehne kruh ulice, ktorý by sa nakreslil vnútri vlastného PSČ tej firmy.
  Rozsah je zmeraný a **obmedzený**: 34 901 firiem (9,1 % umiestnených) umiestňujú
  obecné vrstvy, z toho **7 415** sedí na jedinom bode v obci, ktorú register na
  časti **delí** (40,1 % umiestnených firiem nejakú časť menuje) — tam sa časť
  zahodí a jediný bod sa nedá overiť. To je 1,9 % umiestnených, 1,6 % všetkých
  firiem. Čísla sú z **hotového behu** nižšie, merané **produkčnou**
  `normalize_obec` (nie jej kópiou) proti tabuľke, ktorú matcher práve zapísal;
  skoršie znenie tu malo 28 283 / 6 781 / 39,4 %, čo boli čísla z behu, ktorý
  ešte nebol dokončený. **Nemenil som to potichu**: vypnúť obecné vrstvy by
  zahodilo 9,1 % umiestnení, aby sa predišlo menšej škode, a zmeniť výstup pre
  7 415 riadkov je rozhodnutie, nie oprava (viď otvorená otázka nižšie).
  Pôvodné tvrdenie v kóde („kolízia sa stane zamietnutým kľúčom, nikdy
  premiestneným špendlíkom") bolo **nepravdivé** a je nahradené zmeraným znením.
* **Vážne, ale tiché — diera v spojovacom kľúči.** `Company.psc` nesie tri hodnoty
  s medzerou (`602 00`, `024 01`, `941 01`), register ich píše bez. Import medzeru
  odstránil, matcher ju `normalize_text`-om **nechal** — takže každá PSČ vrstva pre
  tie firmy ticho minula. Kľúč je teraz jedna funkcia (`psc_key` v `address.py`,
  volaná z modelu, matchera aj importu; inak by vznikol cyklus, lebo `models.py`
  importuje `seat_matching`). Zmerané dopady: `id=435544` (Kysucké Nové Mesto)
  a `id=437237` (Bánov) sa tým stanú umiestniteľnými, `id=421376` (Brno, ČR) nie —
  register na `60200` nemá ani bod. Všetky tri sú dnes neumiestnené, takže
  **dnešný výstup sa nemení ani o riadok**; bola to latentná chyba.
* **`import_address_points` prijme skrátený súbor a skončí s 0.** Hlavičková
  kontrola nemôže odhaliť odseknuté telo (hlavičku má aj odseknutý súbor) a ani
  kontrola po riadkoch: `csv.DictReader` doplní chýbajúce kľúče `None` a každý
  prístup tu krátky riadok toleruje — takže sa súbor dočíta do konca, commitne
  a vráti 0. Skrátený súbor vyzerá presne ako „register tie adresy nepozná", takže
  by to ticho vymazalo umiestnenia. Nový prah `MAX_SHRINK = 5 %` to odmietne vo
  vnútri transakcie (predchádzajúci stav prežije) a `--allow-shrink` je explicitná
  výnimka.
* **`--limit 0` obišiel vlastný limit.** `if limit:` je pre nulu nepravdivé, takže
  sa slice nikdy neaplikoval a prešla celá tabuľka. `--limit -N` je bezpečný —
  Django naň vyhodí `ValueError` pred iteráciou.
* **Poistka `NO_DATA` na mape nemohla nikdy zabrať.** `queryRenderedFeatures()`
  bez argumentov sa pýta **celého výrezu a všetkých zdrojov** — vrátane našej
  vlastnej vrstvy bodu, ktorá je pridaná skôr, než sa poistka naozaj spustí. Takže
  `features.length === 0` nemohlo nastať, kým mapa čokoľvek kreslí, a zlyhanie
  dlaždíc sa čítalo ako „prázdne plátno s jednou modrou bodkou a bez správy".
  Poistka sa teraz pýta len vrstiev základného štýlu (`SEAT_LAYER_IDS` z `SEAT_LAYERS`).
* **Karta tvrdila jednu vetu pre všetky tri úrovne.** Text pre `postal_code`
  („register pozná len stred PSČ") zostal stáť pre **každé** sídlo — takže 85,5 %
  firiem, ktoré register umiestni, čítalo opak toho, čo vedľa kreslila mapa.
  Budova nemá kruh vôbec a kruh ulice je rozptyl tej ulice, nie PSČ.
* Tri zastarané čísla v próze kódu (`20,9 %`, „2,5 – 73 km", „zmizne pre 73 %")
  pochádzali z tej istej vychýlenej 4 000-riadkovej vzorky ako bod 6 vyššie.

**Otvorená otázka, ktorú nechávam Samuelovi — nie je to chyba, je to politika:**
má `obec`-úrovňový kľúč (obec bez ulice, teda najširší) smieť umiestniť firmu na
**jediný** bod, keď register tú obec delí na časti? Dnešná odpoveď je „áno",
pretože pravidlo o rozptyle na jeden bod nemá čo povedať. Správna oprava by
vyžadovala kľúč, ktorý si časť obce nesie ďalej — a to znamená zmeniť **import**
(`AddressPoint.obec` je už poskladaná, časť sa v nej stratila), teda ďalšiu
prírastku. Alternatíva je lacnejšia: nechať to a v karte pre `postal_code` povedať,
že register obec pozná, ale jej časti nie. **Odporúčam druhú cestu** — 1,5 %
firiem neznesie ďalší import, a veta je presne to, čo tu celý čas chýbalo.

**Dva nálezy, ktoré som zámerne neopravil** (mimo schválenej prírastky, hlásim):
`serializers.py:152` nemá cestu, ktorá by po zmene adresy v RUZ zneplatnila
`seat_*` — umiestnenie teda prežije zmenu adresy, kým sa matcher znova nespustí;
a § 1 tabuľka nižšie vynecháva #85 – #92.

### #93 — Jedna funkcia je rozsekaná na intervaly podľa dokumentov registra

**Nález z #89, nie jeho súčasť.** Po zhlukovaní som na živej stránke osoby
narazil na toto — a `records: 1`, takže zhlukovanie za to nemôže:

```
FREYSSINET CS, a. s.   (osoba 56172, jedna firma, jedna funkcia `ine`)
  2026-07-07 -> teraz        active=True
  2026-06-26 -> 2026-07-06
  2022-06-15 -> 2026-06-25
  …                        (12 riadkov)
  2011-06-08 -> 2013-01-30
```

Register vykresľuje **jednu nepretržitú funkciu od 8. 6. 2011** ako dvanásť
nadväzujúcich intervalov, pretože každý zápis ju ukončí a ďalší deň znovu
otvorí. My každý interval ukladáme ako samostatnú väzbu, takže stránka osoby
vypíše dvanásť riadkov a **odpoveď na „odkedy" je zahrabaná na dne** — čitateľ
vidí `od 07.07.2026`.

Príklad vyššie je overený živý (osoba 56172 má naozaj 12 väzieb, najstaršia
`2011-06-08`, najnovšia `2026-07-07`, takže čitateľ vidí „od 07.07.2026").
Tabuľka pod ním je však **snímka urobená uprostred behu #95**, nie vlastnosť
tabuľky:

| | počet |
|---|---|
| skupín `(riadok, firma, funkcia)` celkom | 77 551 |
| z toho s viac než jednou väzbou | 6 091 |
| **obsahuje reťaz intervalov deň po dni** | **3 779 (62 %)** |
| naozaj oddelené obdobia | 2 312 |
| najdlhší reťaz | 10 intervalov |
| čisto bez dátumov | **0** |

#### Premerané o pár hodín neskôr — a prečo to nie je tvar registra

Kľúč `(osoba, firma, funkcia)`, 2026-09-13 ~21:05 UTC:

| | plán (skôr dnes) | teraz |
|---|---|---|
| skupín celkom | 77 551 | 91 209 |
| s viac než jednou väzbou | 6 091 | 11 238 |
| obsahuje reťaz deň po dni | 3 779 (62 %) | **10 273 (91 %)** |
| naozaj oddelené obdobia | 2 312 | 965 |
| najdlhší reťaz | 10 | 10 |
| čisto bez dátumov | 0 | 0 |

Tabuľka rástla **aj medzi dvoma mojimi meraniami** (110 654 → 110 744 väzieb
za pár minút), takže rozdiel nie je iná metrika — niečo ju plní. Rozdelenie
podľa `created_at` to pomenuje:

| | väzieb | skupín s >1 | reťazí |
|---|---|---|---|
| vznikli **pred** 2026-09-13 | 59 714 | **276** | **16** |
| vznikli **2026-09-13** | 51 030 | **10 097** | **9 478** |

Reťaz deň po dni teda **nie je tvar registra, ktorý sme mali** — je to, čo
dnes vyrobil dopĺňač histórie #95. Do dneška ich bolo **16**. To je dôležité
pre rozhodnutie: #93 nie je čistenie starého dlhu, je to daň za #95, ktorá
začala vznikať dnes.

**A nie je to chyba zápisu.** Overené na celej tabuľke: **0** presných
duplicít (ingest je idempotentný) a **0** prekryvov (nepočíta dvakrát).
#93 je teda naozaj len prezentačná vec, ako plán tvrdí.

**Koľko toho ešte bude.** #95 má pred sebou **21 633** firiem; dnešných 4 692
prinieslo 51 147 väzieb, teda **10,9 na firmu**. Projekcia: **~235 819 ďalších
väzieb** — graf z 110 744 na **~346 000 (3×)** a nadväzných dvojíc zo 17 148
(15,5 % väzieb) na rádovo 60 000. Krížová kontrola zdarma: 21 633 / 900 za
hodinu = **24,0 h** zdravej drenáže, čo nezávisle potvrdzuje odhad ~25 h z §2.

#### Tri plochy, nie jedna

Plán menoval stránku osoby. Reťaz sa premieta na tri miesta a dve z nich plán
nezachytil:

| plocha | kde | dnes |
|---|---|---|
| detail osoby + výsledky hľadania | `connections/views.py` `_merged_relations` | 12 riadkov |
| **hrana grafu** | `CompanyGraphView`, `views.py:295` | **12 rovnobežných hrán** medzi tým istým párom |
| admin počítadlo | `connections/admin.py:29` | surové riadky (staff-only, správne) |

`CompanyGraphView` zhlukuje **osoby** (jeden uzol na človeka), ale hranu pridá
**za každú väzbu** — a komentár na `views.py:266` to hovorí ako zámer. Graf je
teda plocha, kde je redundancia najviditeľnejšia. Používateľské počty inde
neobchádzajú spojenie (overené: `person_relations` sa v produkčnom kóde
používa len ako filter grafu).

**Odporúčanie (spresnené):** spojiť nadväzujúce intervaly raz, v **jednej
zdieľanej pomocnej funkcii nad väzbami**, a použiť ju na všetkých troch
plochách — inak sa detail osoby a graf rozídu v tom, čo tvrdia o tom istom
človeku. Načasovanie je výhodnejšie než pri pôvodnom pláne: 91 % skupín
s reťazou znamená, že bez spojenia bude graf po dobehnutí #95 kresliť 3× toľko
hrán. Živý príklad výsledku: osoba 56172 má v reťazi **34-dňovú dieru**
(`2013-04-10` → `2013-05-14`), takže správne spojenie dá **2 riadky z 12**,
nie jeden — a to je presne to, čo musí #93 trafiť.

**Čo musí spojenie zachovať** (inak to vybuchne až pri implementácii):

- **Kľúč je `(firma, funkcia)`**, nie `(firma)` — `konateľ` do 31. 12. a
  `prokurista` od 1. 1. sú dve funkcie, nie jedna, a musia ostať dve.
- **Nadväznosť potrebuje oba dátumy.** Interval s `zanik_funkcie = None`
  nemôže byť ničím, čo sa spája dozadu — je otvorený, takže reťaz ním končí.
- **`is_active` pochádza z najnovšieho článku**, lebo spojená funkcia trvá práve
  vtedy, keď trvá jej posledný interval. A `is_active = None` („túto firmu sme
  nečítali", #86) musí ostať `None` — spojenie nesmie vymyslieť „aktívna".
- **`vznik` = najskorší, `zanik` = najneskorší** a ak je za tým viac dokumentov
  registra, povedať to (plán to už žiada).

**Read-time nie je preferencia, je to štrukturálne vynútené.** Tabuľka má
unikátny kľúč `(person_id, company_id, role, vznik_funkcie)` — ten vysvetľuje
nameraných 0 duplicít (re-import tej istej histórie je idempotentný), ale
zároveň znamená, že **spojenie na strane zápisu by najbližší re-import vrátil
späť**: zlúčený riadok si ponechá `vznik` prvého dokumentu, takže dokumenty
2..12 by sa nemali na čo priradiť a `_create_relation` by ich založil znova.
Zápis by teda musel buď obchádzať vlastný unikátny kľúč, alebo si pamätať, čo
už zlúčil — a to je presne tá kniha, ktorú read-time nepotrebuje.

**Prečo to nie je hotové teraz:** je to nová prírastka, nie dokončenie #89
(zhlukovanie spája *riadky osôb*, toto spája *obdobia funkcie*), a mení to, čo
stránka tvrdí o histórii — to patrí do samostatného rozhodnutia. Podklad preň
je premeranie vyššie; rozhodnutie je Samuelovo.

### #100 — Graf kreslí tú istú hranu 12× (a #95 to zhoršuje)

**Nález pri overovaní #93, ale iná vec než #93.** Overené na živej odpovedi
`GET /api/companies/<ico>/graph/` dňa 2026-09-13:

```
FREYSSINET CS, a. s. (31798446)   nodes=10  edges=21  distinct=9
  12x  person_56172 -> company_31798446  role='Iné'
   2x  person_56169 -> company_31798446  role='Iné'
```

osem firiem s najviac väzbami:

| | spolu | rôznych | redundantných |
|---|---|---|---|
| 8 firiem | 1 953 | 872 | **1 081 (55 %)** |

Príčina je v `CompanyGraphView`: slučka ide cez **každú väzbu** firmy
(`views.py:275`) a vnútri nej sa `other_relations` (`:305`) pýta **znova pre
každú väzbu**, bez dedup proti `edges`. Slučka teda nemá pojem „tá istá hrana":
rovnaká väzba centrálnej firmy sa pripočíta raz za každý svoj interval.

**Prečo to nie je #93 a dá sa schváliť samostatne.** #93 je otázka *významu*
(má stránka osoby ukázať jednu funkciu alebo dvanásť období?) — tam sa rozhoduje
o dátach. Toto je otázka *identity hrany*: graf nemá časovú os, takže dvanásť
rovnakej hrany nevyjadruje „dvanásť období" — nevyjadruje nič. Zbaliť ich
nestráca informáciu, ktorú by graf vedel ukázať.

**Pasca, ktorá rozhoduje o správnej oprave.** Tá istá hrana má
`isActive=False` **11×** a `isActive=True` **1×**. Naivný dedup (napr. `set`)
teda s veľkou pravdepodobnosťou zobrazí **súčasného funkcionára ako
bývalého** — presne chyba, ktorú odstránil #86, len naopak. `isActive` sa musí
zdieľať tými istými pravidlami ako v `_merged_relations` (`active` vyhráva,
`None` len keď nič lepšie nie je), nie výberom ľubovoľného zástupcu.

**Čo oprava prinesie:** odpoveď grafu menšia o 55 % — a keďže redundancia
rastie spolu s väzbami, po #95 by bola ~3× väčšia. Zmiznú aj dotazy navyše:
`other_relations` sa dnes vykoná raz **na väzbu** namiesto raz na osobu.

**Nemerané:** či je to vidieť aj na plátne. Hrany sa prekrývajú, takže
vizuálne to môže vyzerať ako jedna čiara; overené je len to, že všetkých 21
hrán ide do renderu (`useGraphData.ts:55` pri prvom načítaní nededuplikuje).

### Hľadanie osôb — ✅ hotové (#87, #88, #89)

Návrh: `docs/PLAN-OSOBY.md`. ORSR to vie naživo (`search_osoba.asp`), ale
**sync podľa mena netreba** — graf osôb už máme, a tak je to aj postavené:
`/api/persons/?q=` hľadá v našom grafe (`PersonSearchView`),
`/api/persons/orsr/` je živý register (`OrsrPersonSearchView`) a frontend ich
drží oddelené.

**Text, ktorý tu stál, už neplatí.** Hovoril, že hľadanie blokuje jediná
chyba — `is_active` sa zapisuje natvrdo ako `True` a `zanik_funkcie` sa nikdy
nedopĺňa — a že graf má 44 897 osôb, 64 128 väzieb a 19 906 firiem, o ktorých
**všetkých** tvrdí, že sú aktuálne. Ani jedno z toho dnes neplatí: čítač
histórie existuje a beží (#95) a graf má **59 186** osôb, **92 928** väzieb
a **21 580** firiem — z toho **26 103** väzieb hovorí „funkcia skončila"
a **61 371** „nevieme", takže o aktuálnosti netvrdí nič tam, kde ju nevie.

**Čo z toho ostáva:** už len dobehnutie histórie — #95.


### #85 — Minimapa so sídlom firmy — ✅ hotové

Podobne ako to má FinStat. Nasadené v `a6d7b8c` (oblasť z registra adries MV
SR), `16c2ae3` (sídlo ako oblasť, nie bod) a `100f4d4` (karta s mapou) —
a `d8e4944` sem dopísal, ako import dopadol.

- `Company` má `ulica` / `mesto` / `psc` **štruktúrovane**: `mesto` a `psc` na
  100 %, `ulica` na 99,7 % z 445 626 riadkov

**Kľúč je PSČ, nie mesto — a to je prepis pôvodného postupu.** Prieskum
2026-09-13 nameral, prečo sa `mesto` ako kľúč použiť nedá a prečo PSČ áno.
Zmerané proti našej databáze (449 763 riadkov) a proti stiahnutému CSV
(1 739 536 riadkov):

| kľúč | pokrýva | poznámka |
|---|---|---|
| `mesto` | **nedá sa použiť** | 95 názvov `OBEC` leží vo **viac než jednom okrese**; náš zápis je iný než registrový (`Bratislava - mestská časť Ružinov` vs `Bratislava-Ružinov`), takže by to bolo fuzzy párovanie |
| `psc` | **441 165 / 449 763 = 98,09 %** | žiadne párovanie názvov; 3 riadky bez PSČ |
| `(obec, psc)` | 3 288 párov | zbytočne zložité — my chceme *bod pre PSČ*, nie identitu obce |

Čo z toho plynie:

1. **Zdroj pozná 1 415 PSČ a my máme všetky.** Každá PSČ, ktorú CSV obsahuje,
   sa u nás vyskytuje. Množina zdroja je celá podmnožinou tej našej.
2. **Nespárovaných je 8 595 riadkov (1,91 %), a nie je to chyba kľúča.**
   Zdroj tie PSČ **vôbec neuvádza** — `94001` (674 riadkov) tam neexistuje,
   pre Nové Zámky ide rovno `94002`. Sú to PSČ poštových úradov, ktoré nemajú
   vlastný adresný bod. Nedajú sa dorátať; **vypíšu sa a nič sa im nepriradí.**
3. **Prázdne PSČ sa musí preskočiť.** Zdroj má 224 riadkov s prázdnym `PSC`,
   ale platnými súradnicami. Naivné `GROUP BY PSC` by z nich vyrobilo oblasť
   so „ťažiskom" rozptýleným na **161 km** a 3 naše firmy bez PSČ by dostali
   špendlík do stredu Slovenska. Import musí prázdnu hodnotu zahodiť.
4. **Presnosť je ~2 km, nie adresa.** Polomer, ktorý pre každú PSČ pokryje 90 %
   jej adresných bodov: **medián 1 980 m**, p90 4 118 m, p99 6 202 m, najhoršia
   vidiecka PSČ 8,7 km. Preto karta nesmie ukázať holý špendlík — ten tvrdí
   presnosť, ktorú nemáme. Ukáže **bod plus kruh** s týmto polomerom, a ten
   rozdiel je vidieť, nie schovaný v poznámke.

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

**Úskalia, ktoré patria do implementácie, nie do poznámky pod čiarou:**

1. **Bratislava a Košice: pôvodná obava bola nesprávna, ale záver zostáva.**
   Register ich delí na mestské časti (`Bratislava-Staré Mesto` … 17,
   `Košice-Sever` … 22) a holý riadok `Bratislava` neexistuje. Pôvodný plán
   tvrdil, že náš `mesto` má holé názvy a join by ticho zahodil dve najväčšie
   mestá. **To je nepravda** — náš `mesto` mestské časti už nesie
   (`'Bratislava - mestská časť Ružinov'`, 8 304 firiem). Problém je iný:
   **formát je iný než registrový**, takže by to bolo fuzzy párovanie názvov.
   Riešenie nie je normalizovať názvy, ale **nepoužiť ich vôbec** — PSČ
   `82108` je Ružinov bez toho, aby sme hádali, ako sa to píše. Tým úskalie
   mizne, nerieši sa.
2. **Nepriradené PSČ sa musia vypísať**, nie zahodiť — a musia sa vypísať
   **s dôvodom**. Pri 8 595 riadkoch je dôvod „zdroj tú PSČ nevedie"; to je iná
   veta než „náš kľúč je zlý", a keby sa pomiešali, tichý nárast prvého by
   vyzeral ako druhý.

**Zvolený postup:**

1. **Zdroj:** CSV MV SR (vyššie) — jednorazový import, agregácia **na `PSC`**
   (ťažisko `ADRBOD_X`/`ADRBOD_Y`, **nie prvý riadok**) → ~1 415 riadkov.
   Prázdne `PSC` sa preskočí (viď vyššie). K importu sa zapíše `dct:modified`
   zdroja ako verzia, aby bolo vidno, z čoho dáta sú.
2. **Tabuľka sa volá `PostalCodeArea` (`psc` unique, `lat`, `lon`,
   `radius_m`, `point_count`, `obec`, `okres`, `kraj`, verzia zdroja).**
   `obec`/`okres`/`kraj` sú **opisné**, odvodené od najčastejšej hodnoty
   v danej PSČ — pri 834 PSČ, ktoré ležia vo viac než jednej obci, to nie je
   identita, len popis. Kľúč je `psc`.
3. **Mapový podklad: OpenStreetMap, dlaždice OpenFreeMap** — výsledok troch
   kôl toho istého dňa: pôvodne tu bolo OpenStreetMap, Samuel ho vrátil
   a žiadal Google Maps, a keď Google neprešiel podmienkou „bez karty", vrátilo
   sa to na OpenStreetMap s **vlastnou kartografiou**. Aktuálny stav je
   v „Tretie kolo" nižšie; obe staršie kolá tam ostávajú ako záznam, nie ako
   opis kódu. Žiadny kľúč, žiadny Map ID, žiadna fakturácia.
4. **Knižnica:** `maplibre-gl@6.9.0` (BSD-3-Clause) — vykresľovač, ktorý sám
   o sebe kartografiu nemá, takže štýl je vlastný (`frontend/map/style.ts`).
   Načítava sa lenivo v `SeatMap.tsx`. `leaflet`, `react-leaflet`,
   `@types/leaflet` aj `@googlemaps/js-api-loader` odišli z `package.json`.
5. **Umiestnenie:** kompaktná karta pod adresným riadkom v `CompanyHeader.tsx:199`
6. **Čestnosť — tretia formulácia, a tá je meraná.** Adresný bod je zameraný
   bod vchodu do budovy, takže zdroj je presný; nepresné je **naše priradenie**
   — a to nie je „máme mesto, nie vchod", ale **„vieme PSČ, a to je medián
   1 980 m"**. Karta preto kreslí **bod aj kruh s reálnym polomerom tej PSČ**.
   Holý špendlík by tvrdil presnosť na budovu, ktorú nemáme; poznámka pod mapou
   by to len ospravedlňovala. Kruh to ukáže.

**Ešte spraviť:**

- [x] Import command + tabuľka `PostalCodeArea` (kľúč `psc`, prázdne preskočiť,
      verzia zdroja, `radius_m` z 90 % pokrytia)
- [x] Report nepriradených PSČ s dôvodom (`zdroj nevedie` vs `náš kľúč`)
- [x] Backend: vrátiť bod **aj polomer** v payload-e firmy
- [x] Frontend: karta s mapou — bod + kruh + veta, čo ten kruh znamená
- [x] `PostalCodeArea` v admine ako read-only zrkadlo importu (vedľa
      `SectorBenchmark`) — dva údaje, ktoré rozhodujú o tom, či sa mapa vôbec
      kreslí (`point_count`, `radius_m`), sa inak nedajú skontrolovať

**Ako to dopadlo** (import 2026-09-13, `source_version = 2026-08-21`):

| | |
|---|---|
| Riadkov v zdroji | 1 739 536 |
| Preskočené bez PSČ — s bodmi / bez bodov | 224 / 177 |
| Preskočené bez použiteľných súradníc | 35 013 |
| PSČ pod hranicou 20 bodov | 5 (`83004`, `83005`, `83007`, `85000`, `85009`) |
| **Uložené oblasti** | **1 410** |
| Pokrytie našich firiem | **441 139 / 449 763 = 98,08 %** |
| Nepriradené PSČ | 2 074 = 2 069 „zdroj nevedie" + 5 „naša hranica" |

Uložený polomer: min 270 m, medián 1 996 m, p90 4 138 m, max 8 717 m. Najmenší
uložený `point_count` je 58, teda hranica 20 je hlboko pod tým, čo v dátach
naozaj je — žiadna uložená oblasť sa jej neblíži.

Report **oddeľuje dva dôvody** a nie je to kozmetika: „register tú PSČ nevedie"
je slepá ulička, kým „nedali sme ju pod hranicu 20 bodov" je rozhodnutie tohto
príkazu a jediný prípad, s ktorým sa dá niečo spraviť. Prvá verzia hlásila oba
ako „zdroj nevedie", čo bola nepravda o zdroji — a práve tá veta je jediná,
podľa ktorej by sa niekto zachoval.

**Zmenené 2026-09-13 — podklad je Google Maps, nie OpenStreetMap.**
**(PREKONANÉ v ten istý deň — Google Maps neprešlo podmienkou „bez
akejkoľvek platobnej karty", viď „Tretie kolo" na konci tejto sekcie. Toto
je záznam rozhodnutia a jeho odôvodnenia, nie opis toho, čo dnes beží;
body 1 až 3 na konci sú bezpredmetné.)**

Pôvodné body 3 a 4 stavili na OpenStreetMap a `react-leaflet@5`. Samuel to
vrátil: *„ja nechcem openstreetmap či čo si to našiel, ja chcem oficiálne
google maps"*. Nebolo to len o vkuse. Ten istý bod 3 sám priznával, že OSM je
„best-effort bez SLA — pre verejný launch treba platený alebo self-hosted
zdroj": Google Maps je presne ten platený zdroj, ktorý si plán vypýtal, a jeho
SLA je zmluvné, nie dobrá vôľa.

Čo sa tým mení vecne:

- **Dlaždice prestali byť náš záväzok.** OSM politika (jediná povolená URL,
  žiadne subdomény, cache ≥ 7 dní, žiadny prefetch) bola pravidlá, ktoré sme
  museli držať v kóde. Google si dlaždice servíruje sám.
- **Fakturácia je za každé načítanie mapy**, preto sa skript načíta až
  v lenivom chunku `SeatMap` a **bez kľúča sa nežiada vôbec** — nasadenie bez
  kľúča sa Googla ani nedotkne.
- **Dark mode má oficiálnu cestu** (`colorScheme`), ale tá je len na vektorovej
  mape, teda vyžaduje Map ID. Bez neho sa mapa kreslí ďalej a dark mode ticho
  nerobí nič — to je dôvod, prečo je Map ID druhá premenná a nie konštanta.
  A `colorScheme` je navyše **len pri vytvorení mapy**: Google ju v `setOptions`
  ignoruje, takže živá mapa sa pretémať nedá. Prepnutie témy preto stavia druhú
  mapu (jedno ďalšie fakturované načítanie) — prvá verzia to skúšala cez
  `setOptions` a bol to tichý no-op, ktorý sa tváril ako hotová vec.
- **Ticho zlyhať sa dá tromi spôsobmi a každý má vlastnú vetu**: chýbajúci kľúč,
  nenačítaný skript, a kľúč odmietnutý Googlom. Tretí je záludný —
  `gm_authFailure` príde **po** úspešnom načítaní skriptu, takže bez toho háčika
  sa mapa vykreslí ako sivý obdĺžnik s vodoznakom a nikto sa nedozvie prečo.
  Presne tomu sa tu vyhýbame.
- **Špendlík zostal bodkou.** `AdvancedMarkerElement` je predvolene slzička, a
  slzička má hrot, ktorý pomenúva vchod. Ten nemáme — patrí nám PSČ a jej
  medián. Preto vlastný `content` (10 px bodka) a kruh ako vlastné tvrdenie.
- **Súradnice sa nezmenili.** `Zdroj: Register adries MV SR` pod mapou platí
  ďalej; Google je podklad, nie pôvod údajov.

**Štyri veci, ktoré z tohto ostávajú na Samuela:**
**(body 1–3 padli s rozhodnutím o OpenStreetMap — ostáva iba bod 4; pozri
„Tretie kolo" nižšie, kde je ten istý bod preformulovaný na nový tok údajov)**

1. **(neplatí)** Vytvoriť Maps JavaScript API kľúč (s fakturáciou) a obmedziť ho na
   `http://localhost:5173/*` aj na produkčnú doménu, a len na „Maps JavaScript
   API". Kľúč je v balíku verejný — toto obmedzenie je jeho jediná ochrana.
2. **(neplatí)** Vytvoriť produkčný Map ID. `DEMO_MAP_ID` je Googlova vzorka pre vývoj.
3. **(neplatí)** Vložiť obe hodnoty ako **masked CI/CD premenné** v GitLabe (`VITE_GOOGLE_MAPS_API_KEY`,
   `VITE_GOOGLE_MAPS_MAP_ID`). Produkčný frontendový image sa stavia s kontextom
   `frontend/`, takže root `.env` sa do buildu **vôbec nedostane** — bez týchto
   premenných sa image postaví bez kľúča a každá mapa sídla ohlási chýbajúci kľúč.
   `build_frontend_image` ich odovzdáva cez `--build-arg` a `vite.config.ts` na
   chýbajúcu premennú aspoň **pomenovane upozorní v logu**; build to nezhodí,
   pretože aplikácia musí vedieť bežať aj bez kľúča (CI tak beží).
4. **(platí ďalej, s inou adresou)** `frontend/pages/Privacy.tsx` dnes v sekcii
   technických údajov menuje iba IP adresu, typ prehliadača a prístupové logy.
   Mapa je prvý **tok údajov k tretej strane**, aký v aplikácii máme. V google
   verzii to bola požiadavka na `maps.googleapis.com` s IP adresou návštevníka
   a adresou stránky, plus Googlove vlastné cookies; v dnešnej verzii je to
   požiadavka na `tiles.openfreemap.org` s IP adresou a prezeranými súradnicami
   a **bez cookies aj bez identifikátora**. Čo z toho musí byť v zásadách a či
   to potrebuje súhlas pred načítaním mapy, je právne rozhodnutie, nie moje —
   preto ho **nezapisujem sám**, navrhnem vetu a počkám na slovo.

**Druhé kolo: adversariálna verifikácia (2026-09-13).** Pätnásť agentov prešlo
hotovú zmenu piatimi optikami (Google API, React, testy, env/build, integrácia)
a každý nález sa musel nechať vyvrátiť. Deväť obstálo — a päť z nich boli moje
vlastné chyby, opravené pred commitom:

- `colorScheme` je len pri vytvorení mapy → efekt na `[isDark]` bol tichý no-op
  (vyššie). Opravené: prepnutie témy mapu postaví znova a starú korektne pustí.
- Mapa, kruh ani marker sa pri odmontovaní **nikdy neuvoľňovali**. Google nemá
  `destroy()`, takže teardown je odpojenie overlayov a vyprázdnenie kontajnera —
  bez neho ostáva za každým prečítaným profilom firmy živá mapa s WebGL kontextom.
- Test „does not ask Google for the script at all" **nemohol zlyhať**: tvrdil
  prázdny zoznam máp v momente, keď `render()` ešte len vrátil, kým mapa sa
  vytvára až v mikroúlohe. Teraz tvrdí `libraryNames`, ktoré mock zapisuje
  synchrónne — a mutačný test to potvrdil.
- Test predvoleného Map ID závisel na **ambientnej** `VITE_GOOGLE_MAPS_MAP_ID`:
  v momente, keď Samuel spraví krok 2 podľa tohto plánu, zčervenal na teste
  o téme. Teraz si ho každý test explicitne vyprázdni.
- `vite-env.d.ts` tvrdil, že `tsc` odchytí preklep v názve premennej. Neodchytil:
  `vite/client` dáva `ImportMetaEnv` fallback `[key: string]: any`. Doplnené
  `ViteTypeOptions.strictImportMetaEnv` ten fallback odstráni — až teraz to
  tvrdenie platí (a `npm run typecheck` to overuje).
- Komentár tvrdil, že sa karta medzi firmami **znovu použije** a preto sa
  nefakturuje dvakrát. Neznovu použije: obe dnešné cesty ju medzi firmami
  odmontujú, takže mapa sa stavia raz na profil. Komentár je opravený na to, čo
  je pravda; vetva ostáva, lebo je správna pri znovupoužití.

Mutačný test: šesť zámerných chýb v `SeatMap.tsx` (pevný radius, zmazaná poistka
na kľúč, vypustená téma zo závislostí, chýbajúce uvoľnenie, zmenený Map ID,
odstránený stub) — každú zhodel presne ten test, ktorý ju pomenúva. Sada nie je
vatová.

**Jedna z tých šiestich bola nepresná a musel som ju zopakovať.** Pri piatej
(zmenené predvolené Map ID) som `sed`-om trafil `DEMO_MAP_ID;` aj vnútri
`|| DEMO_MAP_ID;` v `mapId()`, takže v kóde vznikol **nedefinovaný identifikátor**
— asynchrónna IIFE to chytila do `catch`, zavolala `setFailed(LOAD_FAILED)`
a zhodilo sa **10 testov na timeout**, nie ten jeden, ktorý to pomenúva. Bol to
teda pád, nie dôkaz, a ako dôkaz som ho pôvodne uvádzal. Zopakované presne
(`|| 'DEMO_MAP_ID_X'`, 14:48 UTC) dalo to, čo malo: **18 testov, 1 zlyhanie**,
a to práve `draws in the app theme, which needs a Map ID` s vetou
`expected 'DEMO_MAP_ID_X' to be 'DEMO_MAP_ID'`. Šesť zo šiestich je teda
čistých; poctivá formulácia je „šesť mutácií, päť čistých na prvý raz".

**Tretie kolo 2026-09-13 — Google Maps neprešlo podmienkou, podklad je OpenStreetMap.**

Samuel tú štvoricu otázok prečítal a odpovedal na prvý bod:
*„je to zadarmo? pretoze chcem verziu zadarmo. ak to nie je mozne zadarmo (uplne
zadarmo), tak chcem prejst na uplne free verziu"*, a potom to zúžil:
*„musi vyzerat podobne ako google maps a mat podobne funkcie ako GMaps. uz
nemusis prehladavat. ale musia byt uplne zadarmo bez akehokolvek platenia alebo
zadavania platobnej karty."*

**Odpoveď na jeho otázku je nie.** Od 1. marca 2025 Google zrušil opakovaný
kredit 200 $/mesiac a nahradil ho bezplatnými volaniami podľa SKU (Essentials
10 000, Pro 5 000, Enterprise 1 000 za mesiac) — ale **fakturačný účet s kartou
sa vyžaduje aj v bezplatnom pásme**. Bez karty existuje len „Maps Demo Key",
ktorý Google sám licencuje ako *„only for testing, prototyping, evaluation, and
learning — not designed for production use"*. To nie je verzia zadarmo; to je
verzia, ktorá sa nesmie nasadiť. Podmienka „bez akejkoľvek platobnej karty" teda
Google Maps vylučuje, a to je celé — zvyšok je dôsledok.

**Čo to nahradilo:** `maplibre-gl@6.9.0` (BSD-3-Clause) ako vykresľovač
a OpenFreeMap ako zdroj dlaždíc. Ani jedno nechce kľúč, účet ani kartu.
`@googlemaps/js-api-loader` a `@types/google.maps` odišli z `package.json`,
`@maplibre/maplibre-gl-style-spec` a `@types/geojson` pribudli ako výslovné
devDependencies (prvý z nich `maplibre-gl` ťahá tranzitívne, ale importujeme
z neho priamo).

**MapLibre je len vykresľovač — štýl je odteraz náš.** `frontend/map/style.ts`
je vlastná kartografia (svetlá aj tmavá): teplý svetlosivý podklad, `#aadaff`
voda, jantárové diaľnice, `#242f3e` tmavý podklad — teda Googlove farby, aby
jeho podmienka „musí vyzerať podobne" platila. Štyri veci o dátach ho formujú,
a **všetky štyri boli odmerané dekódovaním skutočných dlaždíc, nie pamätané**:

- **`boundary` nemá `class`.** Nesie `admin_level` (2, 4, 6, 8), `disputed`
  a `maritime`. Filter na `class` je ten najsamozrejmejší tip a nezodpovedá
  ničomu — Slovensko by sa vykreslilo **bez hraníc a bez chyby**.
- **`building` tiež nemá `class`.** Nesie `render_height`, `colour`, `hide_3d`.
  Tá istá pasca.
- **`park.class` je voľný text** — reálne hodnoty zahŕňajú `Natura 2000`,
  `Prírodná rezervácia`, `Národná prírodná rezervácia` popri anglických. `match`
  na pamätaný slovník by vyhodil slovenské chránené územia a nechal generické;
  to je to najhoršie čiastočné zlyhanie, lebo vyzerá, že funguje.
- **Vektorové dlaždice vynechajú pole, ktoré nemá ani jeden prvok v tej
  dlaždici.** `ref` je raz prítomný a raz nie, takže „neprítomné tu" nič
  nedokazuje — a štýl sa proti jednej dlaždici validovať nedá.

**Pasca, ktorá by inak ticho vyrobila prázdne plátno.** OpenFreeMap dlaždicová
šablóna bez verzie — `…/planet/{z}/{x}/{y}.pbf`, tá, ktorú ukazuje takmer každý
návod — vracia **HTTP 200 s prázdnym telom (0 B)** a hlavičkou
`x-ofm-debug: empty tile`, pre každú dlaždicu. Mapa na nej vykreslí prázdne
plátno a **do konzoly nenapíše nič**. Funguje len verzovaná cesta
(`…/planet/20260906_080001_pt/…`, 558 261 B pre dlaždicu Bratislavy v z14),
a práve tú inzeruje TileJSON na `https://tiles.openfreemap.org/planet`. Zdroj je
preto `{type: 'vector', url: TILEJSON_URL}` — **dokument, nie šablóna** — a
`style.test.ts` to drží: `source.tiles` musí byť `undefined`.

**Čo sa zmenilo k lepšiemu, nielen k lacnejšiemu:**

- **Téma sa mení na živej mape.** Googlov `colorScheme` bol len pri vytvorení,
  takže prepnutie témy stavalo druhú mapu a bolo to druhé fakturované načítanie.
  `setStyle()` preoblečie tú istú mapu a **zachová kameru** — čitateľ ostane
  pozerať tam, kam sa pozeral.
- **Žiadny kľúč, žiadny Map ID, žiadne build-argy.** `Dockerfile.prod`
  a `build_frontend_image` v `.gitlab-ci.yml` ich stratili; produkčný image sa
  stavia z holého zdroja. Bod 1 až 3 predošlého zoznamu tým **zmizli**.
- **`VITE_*` je teraz prázdna množina.** Aplikácia nečíta ani jednu, a
  `vite-env.d.ts` to **vynucuje** — prázdne `ImportMetaEnv` so
  `strictImportMetaEnv` spraví z hocijakého `VITE_` mena chybu kompilácie.
  Predtým to bolo len tvrdenie v komentári.

**Čo sa zmenilo k horšiemu, a hovorím to rovno:**

- **Chunk je väčší.** `SeatMap` je po builde 1,04 MB (285 kB gzip) plus 83 kB CSS
  pre `maplibre-gl.css`. Je to stále **lenivý** chunk, takže sa netýka prvého
  vykreslenia — ale je to najväčšia vec na stránke a `SeatLocationCard` ho drží
  mimo všetkých ostatných stránok práve preto.
- **Atribúcia je teraz náš záväzok.** OpenFreeMap + `© OpenMapTiles` + `Data from
  OpenStreetMap` (s odkazom na `openstreetmap.org/copyright`) musia byť viditeľné.
  Kreslíme si ich sami ako React odkazy — `attributionControl: false`, aby
  licenčná poznámka nebola HTML reťazec z cudzieho dokumentu.

**Overené, a overené tak, aby to mohlo zlyhať.** `map/style.test.ts` púšťa štýl
cez vlastný validátor specifikácie (`validateStyleMin`; `validate` je v tomto
builde rozbitý a na hocijakom štýle hodí výnimku) — a hneď vedľa je test, ktorý
mu podstrčí zámerne pokazený štýl a **žiada nenulový počet chýb**. Bez neho by
tvrdenie „validátor nič nenašiel" platilo aj o validátore, ktorý nenájde nikdy
nič. To je tá istá chyba, akú tu už raz spravil `grep -c` nad spadnutým príkazom.

Nad rámec testov prešiel hotový štýl **dvoma skriptami proti skutočným dlaždiciam**
(15 vzoriek: Bratislava z7/z9/z12/z14, Košice, D1, Gerlachov štít, Nízke Tatry,
Žitný ostrov, dve hranice, letisko): každý `source-layer`, ktorý štýl menuje,
a každé pole, ktoré ktorýkoľvek výraz číta, v dátach existuje — a každý `match`
na `class` má aspoň jeden reálny prvok. **Negatívne kontroly**: filter na
neexistujúce pole aj neexistujúci `source-layer` skript odhalil, takže „nula
problémov" niečo znamená. `landcover` matchuje všetko, čo sa vo vzorke vyskytlo
(`grass farmland wood rock sand wetland`); `ice` ostáva deklarovaná a nepoužitá.

**Zostáva na Samuela jediná vec, a je iná než predtým — bod 4, už nie body 1–3.**
Tretia strana v toku údajov **nezanikla, len sa zmenila adresa**: otvorenie
profilu firmy teraz spraví požiadavku na `tiles.openfreemap.org` s IP adresou
návštevníka a prezeranými súradnicami. Nie je tam kľúč, cookie ani identifikátor
— ale samotná požiadavka je poskytnutie údajov a v zásadách má byť pomenovaná.
Rovnako ako minule to **nezapisujem sám**; navrhnem vetu a počkám na slovo.

**Dodatok v ten istý deň — mapa sa v skutočnosti nekreslila vôbec.** To, čo je
vyššie opísané ako overené, overené bolo: štýl sedí na slovník dlaždíc, validátor
ho prijme, testy prechádzajú. Lenže **ani jedno z toho nie je dôkaz, že mapa
kreslí**, a práve to bola pravda — snímka živej stránky `firma/48097781`
v reálnom čase ukazovala kartu s vetou „Mapa sa nenačítala — dlaždice sa
nepodarilo stiahnuť. Skontrolujte pripojenie a obnovte stránku." Mapa sa
nekreslila **vôbec**, v dev serveri ani v postavenom `dist/`. To je tá istá
trieda chyby, ktorú tu platíme stále: niečo vyzerá overené, len nie na tú otázku,
na ktorú sa čitateľ pýta.

Príčina je v preklade, nie v štýle. MapLibre 6 hľadá svoj dlaždicový worker cez
`new URL('./maplibre-gl-worker.mjs', import.meta.url)` — teda **vedľa vlastného
modulu**. Bundler ten modul presunie a workera nechá na mieste:

| požiadavka | odpoveď |
|---|---|
| `/node_modules/.vite/deps/maplibre-gl-worker.mjs` (dev) | **404** |
| `/node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs` | 200 |
| `dist/assets/maplibre-gl-worker.mjs` (build) | **nikdy sa nevygeneroval** |

Worker sa teda nenačíta, neparsuje sa ani jedna dlaždica, `sourcedata` nikdy
neohlási `isSourceLoaded` a plátno ostane prázdne **s čistou konzolou**. Presne
preto to nešlo vidieť v logoch: jediné, čo to nakoniec povedalo, bol náš vlastný
timeout — a ten obvinil pripojenie čitateľa.

Kontrolované A/B to vytriezvelo. Tá istá knižnica (6.9.0), ten istý štýl, ten
istý pôvod, ten istý tab, **jediná premenná je cesta importu**:

| import | `ready` | `tilesLoaded` | snímky |
|---|---|---|---|
| `/node_modules/.vite/deps/maplibre-gl.js` (to, čo sme posielali) | **false** | **false** | 2, zamrznuté |
| `/node_modules/maplibre-gl/dist/maplibre-gl.mjs` | **true** | **true** | 5, ustálené |

Predtým som porovnával verzie (4.7.1 a 5.6.0 z cdnjs išli, 6.9.0 nie) a vyzeralo
to ako regresia v 6.x. **To porovnanie bolo neplatné** a je poučné, prečo: cdnjs
servíruje UMD build, ktorý nesie workera v sebe, kým my sme mali ESM build
predbundlovaný Vite-om. Nemerala sa verzia proti verzii, meral sa UMD proti ESM.
Až keď sa zmenila jediná premenná, ukázala sa skutočná príčina.

Oprava je jedna a platí pre obe prostredia: `?worker&url` nechá Vite postaviť
workera ako vlastný vstup (aj s `maplibre-gl-shared.mjs`, ktorý si sám importuje)
a `setWorkerUrl()` povie MapLibre, kde je — takže jeho vlastný odhad sa nikdy
nepoužije. Build teraz generuje `dist/assets/maplibre-gl-worker-*.js` (508 kB) a
mapa sa overene kreslí v dev serveri **aj** v `dist/` servovanom s proxy na API.

Druhá chyba, nezávislá od prvej a tiež zmeraná: poistka `NO_DATA` („Dlaždice
prišli prázdne") sa pýtala `querySourceFeatures()`, čo je **nesprávna otázka**.
Na mape, ktorá viditeľne kreslí cesty a vodu, táto metóda vracia **0** — na tej
istej snímke `queryRenderedFeatures()` vrátil **240**. Poistka teda odsudzovala
každú zdravú mapu. Otázka je „dostalo sa niečo na obrazovku", a tú zodpovie len
`queryRenderedFeatures()`; komentár v kóde to ostatne tvrdil od začiatku („the
viewport holds nothing"), len kód robil niečo iné.

**Poučenie, ktoré si sem píšem, aby sa nezopakovalo:** overiť štýl proti
dlaždiciam a overiť, že mapa kreslí, sú dve rôzne tvrdenia. Prvé sme mali a bolo
pravdivé; druhé sme nemali a tvárilo sa ako prvé.

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
riadkov (94,3 %)**.

**Je to meranie k 2026-09-12, nie stála vlastnosť** — nad 14 818 vtedy
uloženými riadkami (zdrojom je komentár v `BalanceSheetSection.tsx`, kde je
aj základ merania). Riadkov pribúda s každým RUZ syncom, takže číslo starne.
Jeden ďalší riadok je mimo o menej než euro a **835 (5,7 %) sú skutočné
nezrovnalosti** — preto sa dá na tú kontrolu pozerať: kto vidí, že nesedí,
pozerá na podozrivý riadok. Keď závierke chýba iné číslo, kontrola to pomenuje
a rovnicu neposudzuje — nesľubuje teda viac, než vie.

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
- ✅ **Kontrola poistného backlogu bola pod ustáleným stavom, ktorý sama
  dokumentácia opisuje ako normálny — svietila stále. Opravené (delegované
  rozhodnutie).** Overené naživo 2026-09-13: `make ops-check` hlásil
  `WARN queue 'insurance' holds 62 055 message(s), above the 50000 threshold`
  — a tá istá zostava má ustálený stav **vyššie** než ten prah, lebo poistný
  priechod je na ~15 dní (414 tis. neoverených firiem ÷ 14 400 za tick).

  Namerané v ten deň: fronta **62 051 → 62 026** za ~5 minút,
  `redis used_memory_human: 84.12M` (incident z 12. 9. mal ~5 GB), worker
  `celery_worker_insurance` **beží a každá firma uspeje** (~1,3 s), a fronta
  sa vyprázdňuje presne rýchlosťou, na ktorú je navrhnutá
  (`rate_limit='20/m'`). Príčina rastu je vyriešená v kóde: 12. 9. bolo
  **5 108 434 správ / ~5 GB** a `schedule_insurance_debt_checks` je odvtedy
  capnutý na `INSURANCE_BATCH_PER_TICK = 20 × 60 × 12 = 14 400` za tick.

  Cap je naozaj v tej vrstve, ktorá rozhoduje — overené na `PeriodicTask`
  riadku, nie na dicte: `args='[14400]'`, `queue='celery'`,
  `last_run=2026-09-13 07:50`, `total_run_count=36`. To je dôležité, lebo
  `DatabaseScheduler` spúšťa riadok, nie `CELERY_BEAT_SCHEDULE`.

  ***Oprava môjho vlastného čítania: fronta neklesá — je to píla.*** Cap
  je **presne toľko, koľko 20/m worker stihne za tých istých 12 h**
  (20 × 60 × 12 = 14 400). Príjmy sa teda rovnajú odtokovej kapacite a hĺbka
  je **zachovaná**: ani nerastie, ani sa sama nevyprázdni. Kolíše o jednu
  dávku okolo toho, čo zdedila — tesne pred dispečerom ~54 000, tesne po ňom
  ~68 000, stred ~61 000. Dnešné čísla (63 140 / 62 055 / 61 062 / 60 912 /
  60 859) sú **vzorky tej istej píly, nie trend**. Overené: medzi 13:59:37
  a 14:10:28 žiadny dispečer nebežal (posledný 07:50:06, ďalší 19:50:06)
  a fronta klesala ~19/min, čo je presne návrhová rýchlosť. Dôsledok, ktorý
  stojí za zapamätanie: **cap zastaví rast, ale zdedený backlog sám
  nevyčerpá** — na to by muselo byť due firiem v ticku menej než 14 400.

  **Prah 50 000 bol preto zlý nástroj, nie fronta.** Absolútna hĺbka nevie
  rozlíšiť „beží záplava" od „beží návrh", a keďže ustálený stav je vyššie
  než prah, kontrola hlásila poplach, ktorý sa nedal vypnúť. Kontrola, ktorá
  svieti vždy, je kontrola, ktorú nikto nečíta.

  **Zmenené.** Prah je odteraz per-frontový (`scripts/local/ops_check.sh`):
  `celery`, `ruz_full`, `orsr` a `financials` ostávajú na 50 000 (vyprázdňujú
  sa do nuly), `insurance` má vlastný `CISTAFIRMA_QUEUE_WARN_DEPTH_INSURANCE`
  s defaultom **144 000** — desať tickov, teda päť dní odtokovej kapacity,
  zhruba dvojnásobok vrcholu zdedenej píly a ~58× pod záplavou z 12. 9.
  (8,4 mil. správ za deň). Precedencia zostala: explicitný `CISTAFIRMA_QUEUE_WARN_DEPTH` platí
  ďalej pre **všetky** fronty vrátane `insurance` — per-frontová premenná je
  len konkrétnejšia a vyhrá pre svoju frontu. Overené tromi behmi
  s prepísanými prahmi a potom naostro: `Operational controls: 1 unmet,
  0 warning(s)`, kde jediný FAIL je tá istá nenamontovaná off-site záloha.
  Kontrola si **nezakrýva, čo nevie**: WARN text hovorí, že nevie rozlíšiť
  záplavu od zastaveného odtoku, a že „či práca ešte niečo prináša" je
  verdikt `Source health`, nie tento.

  Rozhodujúce je, že ten verdikt už v repozitári je: `source_health.py`
  v úvode hovorí, že hĺbka fronty „nič nehovorí o tom, či tá práca niečo
  *prináša*", a jeho tretia podmienka zlyhania je **doslova mechanizmus,
  ktorým sa táto fronta plní** (zdroj prestane hlásiť „žiadny dlh", firma
  sa nikdy neoznačí za skontrolovanú a ostane due navždy). `vszp` aj
  `social` tam majú vlastný riadok a `Source health: 0 unmet`.

- ⚠️ **`expires` sa na `PeriodicTask` riadok nikdy nedostane.** Ten istý
  riadok má `expires=None`, hoci `CELERY_BEAT_SCHEDULE` preň hovorí
  `'expires': 43000.0`. Potvrdené naživo, nie odvodené — je to tá istá trieda
  ako `options`/`queue`, kde je rozhodujúci riadok a nie dict.

- ⚠️ **Reštart workera ticho zahodí rozpracované správy — a nikde to nie je
  vidieť.** Namerané 2026-09-13 pri #95: dispatcher poslal o 10:30:08 desať
  úloh `read_person_history` do fronty `orsr`, o 10:35:59 som worker reštartoval
  (aby načítal nový kód) a vykonala sa **jedna** z nich. Na zvyšných deväť
  neexistuje žiadna stopa: žiadna chyba, žiadny záznam vo `SyncJob`, fronta
  `orsr` nula. Práca jednoducho nie je.

  Mechanizmus je konzistentný, nie dosvedčený: `orsr` beží `--concurrency=2`,
  `worker_prefetch_multiplier` nie je nastavený (default `4`), teda 4 × 2 = 10
  správ mohlo byť v rukách workera naraz; `task_acks_late` ani
  `visibility_timeout` nastavené nie sú. Ktorá z tých páčok to spôsobila, som
  nemeral — namerané je, že deväť úloh nebežalo.

  **Netýka sa to len #95.** Rovnaký mechanizmus platí pre každú frontu, a tá
  poistná má v ustálenom stave ~61 000 správ (vyššie), takže každý reštart
  `celery_worker_insurance` môže ticho zahodiť až (prefetch × concurrency)
  kusov rozpracovanej práce. `make ops-check` to nevidí, lebo hĺbka fronty sa
  tým vráti do normálu. Zámerne **nemenené** — `task_acks_late` je zmena
  správania celej fronty a patrí do samostatného rozhodnutia; dnes to
  prežijeme len preto, že selektory sú idempotentné a prácu vyberú znova.

- ⚠️ **Nový `PeriodicTask` riadok nezačne bežať hneď — jeho prvý beh čaká
  celý interval.** Rozhodujúci riadok je `ModelEntry.__init__`
  v `django-celery-beat`, nie základná trieda Celery:

      if not model.last_run_at:
          model.last_run_at = model.date_changed or self._default_now()

  Riadok s `last_run_at = NULL` sa teda nepočíta od „teraz pri načítaní
  rozvrhu" — to je správanie `celery.beat.ScheduleEntry`, ktoré tu stálo
  predtým a je **nesprávne** — ale od **`date_changed`**, obyčajného stĺpca
  v DB. Overené v oboch verziách, ktoré tu bežia: kontajner `2.9.0`, host
  venv `2.8.1`; riadok je v oboch identický, takže dokumentovaný verzný
  posun je pre toto správanie bez následku.

  **Dôsledok je opačný, než tu stálo:** načítanie rozvrhu
  (`DatabaseScheduler: Schedule changed.`) tie hodiny **neposúva** — číta
  ten istý stĺpec. Posunúť ich môže len **zápis toho riadku**: jeho vlastný
  dispatch (beat si ho pri ňom zapíše) alebo rekonciliácia rozvrhu.

  Namerané 2026-09-13 na `refresh-person-history-every-4-hours`
  (`task = registers.tasks.schedule_person_history_resync`, `args='[2000]'`,
  `enabled=True`, `last_run_at=None`, `total_run_count=0`): beat ho od
  vytvorenia **nikdy nevyslal**, `entry.is_due()` o 13:18 vracia
  `is_due=False, next=14399.9`, a `date_changed = 13:20:12.935493`. Prvý beh
  preto čakám **2026-09-13 17:20:12,9 UTC** — a to je teraz pevný údaj, nie
  odhad, práve preto, že hodiny visia na stĺpci a nie na prevádzke iných
  úloh.

  ⚠️ **Ten `date_changed` som si posunul sám — a moja „read-only" kontrola
  bola zápis.** Riadok som vytvoril ja o 10:27:50 (`get_or_create`), a o
  13:20:11.757 som spustil overenie obchvatu, ktoré si postavilo
  `DatabaseScheduler(app=app)`. Lenže konštruktor volá `setup_schedule()`,
  a to je zápis do zdieľanej tabuľky:

      def setup_schedule(self):
          self.install_default_entries(self.schedule)
          self.update_from_dict(self.app.conf.beat_schedule)

  `update_from_dict` prejde `CELERY_BEAT_SCHEDULE` a pre každú položku
  spraví `ModelEntry.from_entry` → `PeriodicTask.objects.update_or_create`.
  Sedem riadkov sa preto zapísalo v 47 ms (`.901392` → `.948508`), presne
  v poradí `install_default_entries` (`celery.backend_cleanup` prvý) a potom
  dict zo settings. „Schedule changed." o 13:20:15 je **následok** tohto
  zápisu, nie jeho príčina.

  Skript pritom tvrdil „in memory only, never saved" a na konci vypísal
  `db row unchanged` — lenže kontroloval `last_run_at`, ktorý
  `_unpack_fields` do `defaults` nedáva a naozaj sa nezmenil. Zmenil sa
  `date_changed`, teda stĺpec, na ktorý sa ten test nepozeral. **Kontrola,
  ktorá číta jeden stĺpec, nemôže dosvedčiť, že zápis nenastal.**

  **Vedľajší, ale skutočný následok:** `compute-sector-benchmarks-daily`
  dostal tým istým zápisom **prvý riadok v histórii** a je due
  **2026-09-14 13:20:12,9 UTC**. Dovtedy `SectorBenchmark` ostáva prázdna
  a benchmark blok sa nevykresľuje — presne to, čo opisuje komentár
  v `settings.py:493`. Ten komentár („no entry here and no `PeriodicTask`
  row ever existed") je tým **zastaraný**; zámerne nemenený, je to kód.

  **Mechanizmus sám nie je vada** — po prvom behu si riadok `last_run_at`
  zapíše a je z neho obyčajná 4-hodinovka. Je to pasca pre každý ručne
  pridávaný riadok („pridal som ho a je `enabled`" neznamená „beží")
  a pre každý overovací skript, ktorý si postaví `DatabaseScheduler`.
  **Obchvat** (overený v pamäti, bez zápisu): ak má riadok `last_run_at`
  v minulosti, `is_due()` vráti `True` hneď na prvom ticku — namerané
  `schedstate(is_due=True, next=14400.0)` pri posune o 5 hodín. Teraz ho
  netreba, riadok je due o 17:20:12,9 sám. Zámerne **nemenené** v kóde
  aj v dátach.

- ⚠️ **Redis nemá `maxmemory`.** `maxmemory_human: 0B`,
  `maxmemory_policy: noeviction`. Pri brokere je `noeviction` **správne** —
  evikcia by ticho zahodila úlohy — ale bez limitu je poruchový mód „Redis
  zožerie RAM hostiteľa", čo sa 12. 9. aj stalo (~5 GB). Limit (napr. 1–2 GB)
  by z neobmedzeného rastu spravil hlasité a ohraničené zlyhanie zápisu.
  Zámerne **nemenené**: je to zásah do bežiacej „produkčnej" zostavy.
- ⚠️ **V `.git/config` je remote s heslom v čistom texte.** Overené
  2026-09-13: `git remote -v` vracia pre `gitlab`
  `http://root:<heslo>@localhost:8088/web/cistafirma.git` — meno aj heslo sú
  súčasťou URL. Súbor nepatrí do repa, takže sa nikam necommitne; je to ale
  čitateľný poverený údaj na disku a pri použití tohto remote sa objaví
  v zozname procesov aj v histórii shellu. Kanonický remote je pritom
  **`gitlab-home`** (`ssh://git@gitlab.home.arpa:2222/web/cistafirma.sk.git`),
  čiže `gitlab` je aj zastaraný. Zámerne **nemenené**: `git remote remove`
  je zásah do konfigurácie repa a nie je moje. Správny krok je remote
  odstrániť **a** to heslo v GitLabe rotovať — odstránenie samotné nestačí,
  keďže hodnota už raz na disku v čitateľnej podobe bola.
- ℹ️ **`ruz_statement_id`** je zatiaľ na 11 z 58 197 riadkov. Dopĺňa ho
  12-hodinový `schedule_ruz_financials_sync`. **Funkciu to neblokuje** —
  `ruz_documents` si id odvodí naživo a uloží, takže chýbajúci záznam
  znamená jeden request navyše pri kliknutí na rok.
- ⚠️ **Hostiteľský venv a kontajner sa rozchádzajú vo verzii
  `django-celery-beat` — a hostiteľské `migrate` preto prepíše históriu
  migrácií v zdieľanej databáze.** `venv` má **2.8.1**, `requirements.txt`
  pinuje **2.9.0** (kontajner ju má). V hostiteľskom `site-packages` je
  odbočka migrácií, ktorú tam 31. 1. 2026 vygeneroval `makemigrations`
  pod Djangom 5.2.10: `0015_alter_clockedschedule_id_...` →
  `0020_merge_20260131_1724` → `0021_alter_...`, a `0021` prepisuje `id`
  polia **späť na `AutoField`** — preto stĺpce ostali `integer` a čistý
  efekt je no-op, ktorý sedí s aktuálnou schémou.

  Nebolo to neškodné: `migrate` z hostiteľského venv naplánoval a použil
  štyri `django_celery_beat` migrácie, ktoré som neplánoval — pretože som
  si predtým „overil" neaplikované migrácie cez
  `showmigrations | grep -c '^\[ \]'`, a to je **zlé počítadlo**: chybová
  hláška sa počíta ako nula. Po aplikovaní overené: beat zdravý (0
  error riadkov, dispatch prebehol v okamihu zápisu), 6 beat tabuliek
  na mieste, `PeriodicTask` 10 riadkov, `migrate --check` v oboch
  prostrediach exit 0.

  **Zámerne neopravené** — je to porucha prostredia, nie kódu, a je mimo
  schváleného rozsahu. Správna oprava je preinštalovať hostiteľský venv
  z `requirements.txt`, alebo migrations púšťať len v kontajneri. Do tej
  doby platí: `make migrate` (venv) a `make docker-migrate` (kontajner)
  **nie sú** to isté a história migrácií sa v nich líši.
- ℹ️ **Cudzia rozpracovaná zmena v pracovnom strome už nie je.**
  `frontend/components/company/sections/PeopleOrgansSection.tsx` bol
  13. 9. upravený a nebol môj (diff zhadzoval fallback
  `Typ: <typ orgánu>` a nechával `structured` nepoužité). Dnes je súbor
  **čistý a zhodný s HEAD** (`8d7695b`) — fallback aj `structured` sú
  späť. Nič z tej zmeny nebolo commitnuté a nie je čo riešiť; záznam
  ostáva len preto, aby bolo vidno, že sa to stratilo zámerne a nie
  omylom.

- ⚠️ **Fallback v `RpoSyncService.sync_company` ticho zmaže `rpo_id` aj
  prečítanú históriu funkcií.** Keď RPO k IČO nevráti entitu, služba zalomí
  na HTML čítačku (`rpo_sync.py:131-133`:
  `return OrsrSyncService().sync_company(company)`). Tá zapisuje
  `raw_payload` **celý naraz** (`orsr_sync.py:56`) — a jej `structured`
  (vlastná `_build_structured`, `orsr_scraper.py:96`) `osoby_historia`
  neobsahuje a `rpo_id` nevysiela vôbec. Dôsledok pre #95: profil vypadne
  z `pending_person_history()` (ktorá vyžaduje `raw_payload__has_key='rpo_id'`)
  a jeho už prečítaná história zmizne — **potichu, a navonok to vyzerá ako
  pokrok**, lebo fronta sa skráti.

  Namerané 2026-09-13: z 24 948 profilov má **236** bez `rpo_id`, z toho
  **16** nesie presne tento odtlačok (`structured` bez `rpo_id`). Je to teda
  reálna, ale **malá a približne stabilná** populácia — `pending_person_history`
  ju sama dokumentuje na 231, takže nejde o záplavu. Zámerne **nemenené**:
  správna oprava je, aby fallback zapísal len polia, ktoré HTML čítačka
  naozaj čítala, a `raw_payload` nechal na pokoji — a to je zmena správania
  synchronizácie.

- ⚠️ **220 profilov sú čisté zlyhania a nevyzdvihne ich ani jeden selektor.**
  `OrsrSyncService.sync_company` pri `OrsrScraperError` založí profil cez
  `get_or_create(company=..., defaults={"ico": ...})` (`orsr_sync.py:67-70`),
  teda riadok s `fetch_ok=False`, `last_error`, prázdnym `obchodne_meno`
  aj `sidlo` a `raw_payload={}`. Overené 2026-09-13: prázdne `obchodne_meno`
  má **220** profilov a je to **presne tá istá množina** ako `fetch_ok=False`
  (220), `raw_payload={}` (220), `last_error` nastavený (220) a `rpo_id`
  (0) — päť rôznych počtov, jeden zhodný riadok. Ani jeden z troch
  selektorov, ktoré som čítal, ich nevyzdvihne: `pending_person_history()`
  chce `rpo_id`, `fetch_orsr_data --only-missing` chce
  `orsr_profile__isnull=True` (profil existuje), `sync_orsr_filtered` chce
  `raw_payload.structured` (je `{}`). Firma s takým riadkom teda ostáva bez
  ORSR údajov. Zámerne **nemenené** — je to zmena selekcie, nie porucha.

### #95 nemá ani jeden riadok `SyncJob` — jeho beh a zlyhanie sú neviditeľné

Zmerané 2026-09-13 večer, keď #95 bežal:

| `job_type` | riadkov | najnovší |
|---|---|---|
| `ruz_incremental` | 18 | 2026-09-13 13:50 |
| `ruz_full_firmy` | 4 | 2026-08-04 13:55 |
| **hocičo s „person" alebo „histor"** | **0** | **nikdy** |

Dopĺňanie histórie funkcií teda nemá v `registers_syncjob` **žiadny** záznam —
ani začiatok, ani koniec, ani počet zlyhaní. Jeho jediným dôkazom života je
riadok v beat logu a to, že sa pohli dáta. To je presne trieda poruchy, ktorú
tento projekt rieši inde („kontrola musí súdiť výsledok, nie záťaž"): keby táto
úloha prestala fungovať, `make ops-check` to nepovie, lebo nemá čo čítať.

Zámerne **nemenené** — doplniť `SyncJob` záznam znamená zasiahnuť do bežiacej
úlohy a je to samostatná zmena, nie súčasť #95.

### Počítadlo v `PeriodicTask` sa pri dvoch úlohách nepíše vôbec

```
NEVER     runs=0    refresh-person-history-every-4-hours
NEVER     runs=0    compute-sector-benchmarks-daily
2026-09-13 17:13  runs=355  detect-stuck-sync-jobs-every-10-min
2026-09-13 17:18  runs=327  send-pending-notifications-every-15-min
… 8 z 10 riadkov počítadlo má
```

**2 z 10 riadkov `last_run_at`/`total_run_count` nemajú nikdy**, hoci
`refresh-person-history-every-4-hours` 2026-09-13 o 17:20:12 **naozaj vystrelil**
(„Sending due task refresh-person-history-every-…") a rozposlal prácu. Počítadlo
je teda pri týchto dvoch úlohách nepoužiteľné ako dôkaz behu — a čokoľvek, čo by
sa oň oprelo, prehlási zdravú úlohu za mŕtvu.

**Príčinu som neoveril** a nebudem ju hádať; rozdiel je medzi dvoma konkrétnymi
riadkami a zvyškom, nie systematický, takže sa to dá zúžiť — ale to je
samostatná práca. Zámerne **nemenené** a **nezapisujem domnienku**.

### `make test` na SQLite vôbec nebeží — a dokumentácia tvrdí opak

`CLAUDE.md` aj `Makefile` hovoria, že mimo Dockeru sa pri prázdnom `DATABASE_URL`
padá na SQLite (`backend/db.sqlite3`). Pre **testy** to neplatí:
`companies/migrations/0014_add_pattern_ops_structured_indexes.py` je nechránené
`RunSQL` s `text_pattern_ops`, čo je operátorová trieda len pre Postgres. SQLite
na nej padne ešte pri stavaní testovacej databázy:

```
django.db.utils.OperationalError: near "text_pattern_ops": syntax error
```

`Makefile` pritom `DATABASE_URL` nikdy nenastavuje ani nečíta `.env`, takže
`make test` v shelli, ktorý ju nemá exportovanú, **vždy** skončí takto. Testovacia
databáza sa stavia migráciami, takže jedna postgresová migrácia zablokuje celý
suite — nielen `companies`.

**Zmerané 2026-09-13:** na Postgrese (loopback, `test_cistafirma` sa vytvorí
a zhodí, živá `cistafirma` sa neotvorí) suite beží. Riešenie je jednorazové —
obaliť `RunSQL` v 0014 na `vendor == 'postgresql'`, alebo doplniť `DATABASE_URL`
do `make test` — a je to **samostatná zmena**: zasahuje do odovzdanej migrácie,
takže zámerne **nemenené**.

### Spustenie testov z koreňa repa nájde 0 testov a vráti 0

```
$ venv/bin/python backend/manage.py test          # z koreňa repa
Found 0 test(s).
Ran 0 tests in 0.000s
NO TESTS RAN
[exited with code 0]
```

Django objavuje testy od **aktuálneho adresára**, a `tests*.py` žijú
v `backend/<app>/`. `make test` preto robí `cd $(BACKEND_DIR)` — ale nič to
nevynucuje a ručný beh z koreňa je ticho zelený. Je to tá istá trieda ako
`grep -c` vracia 0 aj pre spadnutý príkaz: **údaj, ktorý nevie zobraziť zlyhanie,
sa nedá použiť ako dôkaz.** `NO TESTS RAN` je jediná stopa a je ľahké ju prehliadnuť
cez `| tail`, ktorý navyše prepíše návratový kód na 0.

### `docker compose logs --timestamps` dá dva časy na riadok a `grep -o` spočíta oba

Namerané 2026-09-13 večer pri meraní #95, na mojej vlastnej chybe. `docker
compose logs --timestamps` predradí riadku čas od Dockeru, ale telo riadka je
štruktúrovaný JSON, ktorý nesie **svoj** `"timestamp"` — takže na jednom riadku
sú **dva**. `grep -o` vypíše každý *výskyt* vzoru, nie každý riadok, takže
`grep -o 'T[0-9][0-9]' | sort | uniq -c` spočíta oba a číslo vyjde presne
dvojnásobné:

```
$ … | grep "succeeded in" | grep -o 'T[0-9][0-9]' | sort | uniq -c
 1780 T11        # ← dvojnásobok
$ … tá istá množina, počítaná cez distinct task_id
  890 T11        # ← pravda, a presne na strope 900/h
```

Je to zákerné preto, že výsledok nevyzerá ako chyba, ale ako **nález**: 1 780/h
sa dá prečítať ako „rate limit `15/m` neplatí" — teda presne opačný záver, než
je pravda. Odhalí to len nezávislé počítadlo: `grep -oE
'read_person_history\[[0-9a-f-]+\]' | sort -u | wc -l` dalo **2 452** na
**2 452** riadkoch, teda žiadnu duplicitu. Tá istá trieda ako `grep -c` vyššie:
**počítadlo, ktoré nevie, čo počíta, dá sebavedomé číslo.** Pri `docker compose
logs` sa preto hodiny musia počítať z jedného časového poľa, nie z `grep -o`
cez celý riadok.

### Meranie tabuľky, do ktorej práve beží zápis, je pozorovanie s časom — nie vlastnosť

Namerané 2026-09-13 pri premeriavaní #93, na chybe v tomto pláne. Tabuľka v #93
stála na vete „Zmerané 2026-09-13 na celej tabuľke" a tvrdila **3 779 reťazí
(62 %)**. O pár hodín: **10 273 (91 %)**. Po dobehnutí #95 projekcia rádovo
**60 000**. Ani jedno z tých čísel nie je nesprávne — všetky sú pravdivé
o inom okamihu.

Tabuľku totiž celý ten čas zapisoval #95: 2026-09-13 vzniklo **51 030** väzieb,
kým za všetky predchádzajúce týždne spolu **59 714**. Rozdelenie podľa
`created_at` je to, čo oddelí tvar registra od našeho postupu:

| | skupín s >1 | reťazí |
|---|---|---|
| pred 2026-09-13 | **276** | **16** |
| 2026-09-13 | **10 097** | **9 478** |

„62 % skupín má reťaz" teda nikdy nebola vlastnosť registra. Bol to **ukazovateľ
postupu**, ktorý sa čítal ako fakt o dátach.

Je to zákerné preto, že 62 % a 91 % vyzerajú rovnako ako nález a že číslo
**rastie k svojej konečnej hodnote** — skoré čítanie ju teda vždy podhodnotí,
a to bez toho, aby vyzeralo nesprávne. Rovnaká rodina ako prah `ops_check` na
50 000 nižšie: číslo, ktoré raz bolo pravda. Odhalí to len rozpad podľa
`created_at`. **Ak sa meria tabuľka so živým zapisovateľom, patrí k číslu čas
a počet riadkov, pri ktorom bolo vzaté — a záver o *zdroji* sa smie urobiť až
po rozpade podľa dátumu vzniku.**

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
