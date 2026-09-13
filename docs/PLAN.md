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
| — | Legenda stavu funkcie tvrdila o firme, že sme ju nečítali — pri riadku, ktorý je na stránke len preto, že sme ju čítali. Kreslí ju `roleState.ts` | `70271d1` |

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
a `total_run_count=0`, takže dávku **nespustil on** — spustil ju ručný beh.
Prvý beh beat riadku čakám **2026-09-13 17:20:12,9 UTC** (a nie 14:28:25, ako
tu stálo; referenčný bod je `date_changed` riadku, ktorý som si posunul sám
svojím overovacím skriptom — oboje v § 7). To nie je druhá chyba, len
iný spúšťač; ale kým `total_run_count` ostane 0, **nedá sa z neho čítať, či
dopĺňanie napreduje** — a to je presne tá pasca z § 7.

---

## 3. Čaká na prácu

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

Zmerané 2026-09-13 na celej tabuľke:

| | počet |
|---|---|
| skupín `(riadok, firma, funkcia)` celkom | 77 551 |
| z toho s viac než jednou väzbou | 6 091 |
| **obsahuje reťaz intervalov deň po dni** | **3 779 (62 %)** |
| naozaj oddelené obdobia | 2 312 |
| najdlhší reťaz | 10 intervalov |
| čisto bez dátumov | **0** |

**Odporúčanie (read-time, ako #89 krok 1):** spojiť nadväzujúce intervaly
(deň po dni) do jednej funkcie s najskorším `vznik` a najneskorším `zanik`,
a ak je za tým viac dokumentov, povedať to. Naozaj oddelené obdobia (2 312)
zostať oddelené — tie sú dve funkcie a je to vidieť na diere medzi nimi.
Zápis sa nemení, takže je to vratné a dá sa to vypnúť.

**Prečo to nie je hotové teraz:** je to nová prírastka, nie dokončenie #89
(zhlukovanie spája *riadky osôb*, toto spája *obdobia funkcie*), a mení to, čo
stránka tvrdí o histórii — to patrí do samostatného rozhodnutia.

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
3. **Dlaždice:** OpenStreetMap — jediná povolená URL
   `https://tile.openstreetmap.org/{z}/{x}/{y}.png` (subdomény `a/b/c` nie),
   viditeľná atribúcia „© OpenStreetMap contributors", cache ≥ 7 dní, žiadny
   prefetch. Číselný limit neexistuje, ale je to „best-effort" bez SLA — pre
   verejný launch treba platený alebo self-hosted zdroj. Repo nemá CSP, takže
   dlaždice nič neblokuje.
4. **Knižnica:** `react-leaflet@5` (`peerDependencies: react ^19.0.0` — repo je
   na 19.2.3, teda sedí) + `leaflet@1.9.4`, lenivo načítané. Verzie 4.x chcú
   React 18 a pýtali by `--legacy-peer-deps`.
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
- ⚠️ **Kontrola poistného backlogu je pod ustáleným stavom, ktorý sama
  dokumentácia opisuje ako normálny — takže svieti stále.** Overené naživo
  2026-09-13: `make ops-check` hlási
  `WARN queue 'insurance' holds 62 055 message(s), above the 50000 threshold`
  — a tá istá zostava má ustálený stav **vyššie** než ten prah, lebo poistný
  priechod je na ~15 dní (414 tis. neoverených firiem ÷ 14 400 za tick).

  Namerané v ten deň: fronta **62 051 → 62 026** za ~5 minút (klesá),
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

  **Preto je prah 50 000 zlý nástroj, nie fronta.** Absolútna hĺbka nevie
  rozlíšiť „beží záplava" od „beží návrh" — a keďže ustálený stav je vyššie
  než prah, kontrola hlási poplach, ktorý sa nedá vypnúť. Prah odvodený
  z návrhu (`INSURANCE_BATCH_PER_TICK` a jeho násobok) by tú istú situáciu
  prečítal správne. Zámerne **nemenené** — je to zmena kontrolného prahu,
  nie porucha, a patrí do samostatného rozhodnutia.

- ⚠️ **`expires` sa na `PeriodicTask` riadok nikdy nedostane.** Ten istý
  riadok má `expires=None`, hoci `CELERY_BEAT_SCHEDULE` preň hovorí
  `'expires': 43000.0`. Potvrdené naživo, nie odvodené — je to tá istá trieda
  ako `options`/`queue`, kde je rozhodujúci riadok a nie dict.

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
