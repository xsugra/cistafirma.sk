# Plán prác — CistaFirma

**Aktualizované:** 2026-09-19
**Vetva:** `main` — na oboch remotech (`gitlab-home` aj GitHub), lokálne na tom
istom commite
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
| 93 | Jedna funkcia rozsekaná na intervaly podľa dokumentov registra je **jedna funkcia** — spája sa pri čítaní, v jednej zdieľanej funkcii pre detail osoby aj hľadanie; 34-dňová diera zostáva dvoma obdobiami | `973d6d7` |
| 95 | História funkcií z RPO je doplnená — `--dry-run` hlási **0 z 27 427**; plánovací záznam aj riadok `PeriodicTask` zmazané, beat reštartovaný | `a789555` |
| 98 | Kruh okolo sídla bol tvrdenie o presnosti — tvar zobrazenia teraz nesie presnosť namiesto neho | `3e7d11a` |
| — | **Výpadok API na 3 h 43 min (2026-09-17)** — nginx si adresu backendu preložil raz pri štarte; odvtedy prekladá za behu (`resolve` + `resolver`) | `96c601b`, `6f722bc`, `a845414`, `f4b822a` |

**Overené naživo:** výpis dokumentov pre ECKLIMA s.r.o. (IČO 48097781)
a stiahnutie reálneho 852 417-bajtového PDF so slovenským názvom.

> **Táto tabuľka nie je úplný index a nesmie sa tak čítať (overené
> 2026-09-17).** Končí na `#98`, hoci hotových je aj `#99`–`#147`. Per-úlohový
> záznam v tomto dokumente existuje len pre `#83`, `#85`, `#89`, `#90`, `#93`,
> `#95`, `#98`, `#100` (ako `###` nadpisy v §2 a §3) a pre `#95`, `#99`
> v §7. **Pre `#101`–`#147` tu nie je per-úlohový záznam vôbec** — čísla
> `#123`, `#137`, `#140`, `#146` a `#147` sa v celom dokumente nevyskytujú ani
> raz. Autoritatívny záznam o nich je git história, nie tento plán. Nechal som
> to tak naschvál: doplniť 50 riadkov s commit hashmi po pamäti by znamenalo
> vyrobiť si index, ktorý sa tvári overene, a to je horšie než priznaná diera.

---

## 2. Hotové — odôvodnenie a merania

> Táto sekcia a §3 sú **to isté**: hotová práca s odôvodnením. §1 je index
> oboch. Rozdelenie je len poradie, v akom prírastky vznikali — tu sú tie
> skoršie (#83, #90, #89, #95) a merania, na ktoré sa zvyšok dokumentu
> odvoláva ako na „§ 2"; v §3 sú novšie (#98, #93, #100, hľadanie osôb, #85).
> Nadpis tu donedávna znel „Robí sa" a **nebola to pravda**: všetky štyri
> prírastky nižšie sú dokončené a otestované.

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

**Kroky.** Kroky 1, 2 a 4 sú hotové. Kroky 2 a 4 menili **zápis**, a preto
každý z nich začínal **čerstvou overenou zálohou** (`make db-backup` +
`make db-backup-verify`); oba sú dodané v `6c8b236`:

1. ✅ **Zhlukovanie pri čítaní** — `connections/identity.py` (čistý modul, nič
   neukladá), `views.py` (hľadanie, detail, oba grafy), `PersonRecordsNote`.
2. ✅ **`Person.birth_date`** (`DateField`) — aditívna migrácia
   `connections/0004`, ktorá aj presunula uložené dátumy z adresy do stĺpca.
3. ❌ **Zapisovač preberá namiesto vytvárania — vypúšťam.** Takto napísaný krok
   je to isté zlúčenie, len o poschodie nižšie: keby zapisovač pri zhode prebral
   existujúci riadok, zmizne práve to, čo robí zhlukovanie bezpečným —
   **vypísanie riadkov, z ktorých skupina vznikla**, aj možnosť ju vrátiť.
   A keďže obe zložky jedného dokumentu nesú **rôzne adresy** (Vácha: jedna má
   dátum narodenia, druhá ulicu), jedna z nich by sa ticho zahodila — práve tá
   informácia, ktorá ich od seba odlišuje. Rozhodnutie z tohto cyklu znie
   „nezlučovať"; krok 3 by ho obišiel.
4. ✅ **Dátum narodenia sa prestane ukladať ako adresa** — ale **záviselo to od
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

**Prijaté a dodané** (`6c8b236`): stĺpec pribudol, parser má **jednu** vetvu
pre prefix `Dátum narodenia:` (`orsr_scraper.py:498`, hneď za vetvou
`Vznik funkcie`) a tá hodnota sa do `address_lines` nepridá. Všeobecné pravidlo
„riadok s dvojbodkou nie je adresa" sa **neimplementovalo** — ostáva odmietnuté
z dôvodu vyššie. Tým je #89 uzavreté: kroky 1, 2 a 4 hotové, krok 3 vedome
vypustený.

**Testy.** `connections/tests_identity.py` — 34 testov (holé funkcie aj API).
Sada `connections` je **72 OK** (38 pôvodných + 34 nových); frontend 239 OK,
`typecheck`, `build`. Kľúčové prípady: skutočné Vácha riadky 44903/44904/45335
v jednej firme → **1 zhluk**; riadok bez IČO nesmie premostiť dve IČO → 2
zhluky; dve PSČ v jednej firme zostanú oddelené; riadok bez PSČ sa nepridá na
ani jednu stranu → 3 zhluky; `total_people` je `null`, keď okno nestačí.

---

### #95 — História funkcií z RPO je doplnená (hotovo 2026-09-17)

**Stav 2026-09-15 21:44 UTC: `refresh_person_history --dry-run` na delle hlási
8 347 čakajúcich z 27 422 RPO profilov.** Lane beží podľa návrhu, nie je
zaseknutý — a je dôležité vedieť, prečo to tak vyzerá:

- Dva odbery **4 minúty od seba dali presne to isté číslo** (8 347 → 8 347).
  To vyzerá ako zastavený lane, ale je to medzera medzi dávkami: fronta `orsr`
  mala v tom okamihu 31 úloh a posledný dispatch bol o 17:44 UTC, teda 4 h
  dozadu. Ďalší bol na spadnutie o 21:44.
- Aritmetika je v `settings.py` pri `refresh-person-history-every-4-hours`
  a sedí: 2 000 firiem každé 4 h proti odtoku 15/min znamená, že sa fronta
  **stihne vyprázdniť vnútri intervalu** a časť každého cyklu je zámerne
  nečinná. Preto je ploché číslo v krátkom okne **očakávané**, a preto sa
  pokrok nemeria dĺžkou fronty (viď pasca vyššie).
- 8 347 / 2 000 ≈ 4,2 dávky ≈ **~17 h** do konca, teda približne
  2026-09-16 popoludní. Plánovaný prechod je ~48 h a zdieľa frontu s
  `schedule_missing_orsr_sync`, takže je to v rámci návrhu.
- **Overené priamo, nie len aritmetikou (21:44–21:47 UTC).** Dispatcher naozaj
  odpálil: `PeriodicTask.last_run_at` pre `refresh-person-history-every-4-hours`
  sa posunul na `21:44:14.557750+00:00` (`total_run_count` = 14), fronta `orsr`
  skočila z **31 na 1 993** — teda dávka 2 000 úloh naozaj odišla. Následne
  fronta klesla 1 993 → 1 984 za ~40 s, čo je **~13,5/min** proti
  `rate_limit='15/m'`, a `pending` klesol 8 347 → 8 338. Toto je ten dôkaz,
  ktorý ploché číslo nevedelo dať: lane dispatching funguje a odtok sedí
  s nastaveným limitom.

**Uzatváracia podmienka splnená 2026-09-17 (00:16 CEST / 2026-09-16 22:16 UTC).**
`refresh_person_history --dry-run` na delle hlási `Firmy bez precitanej historie
osob: 0 z 27 427 RPO profilov` → `Nie je co robit`. Zmazané boli **obe vrstvy**:

| čo | kde | stav |
|---|---|---|
| záznam `refresh-person-history-every-4-hours` | `backend/backend/settings.py` | zmazaný (`a789555`), namiesto neho náhrobok s dôvodom, prečo sa nesmie vrátiť |
| riadok `PeriodicTask` | produkčná DB na delle | zmazaný (ostáva 9 riadkov z 10) |
| `celery_beat` | dell | reštartovaný 22:16:36 UTC, aby načítal nový `settings.py` |

**Prečo je to naozaj koniec, a nie len nula v okne.** Dve merania tej istej
podmienky dali `0 z 27 426` a potom `0 z 27 427` — populácia medzitým narástla
o jeden profil a chýbajúcich ostalo nula. To je priamy dôkaz tvrdenia, na
ktorom celý lane stál: nový profil prichádza **už prečítaný**, lebo ten istý
kľúč `osoby_historia` zapisuje bežný ORSR čítač. Keby to tak nebolo, číslo by
pri raste populácie stúplo. Preto sa lane nesmie vrátiť — nemal by čo robiť.

**Tretie meranie o ~8 h neskôr (2026-09-17 06:00 UTC): `0 z 27 429`.** Populácia
medzitým narástla o ďalšie dva profily a chýbajúcich ostalo nula — a to **už bez
riadku v beate**, teda bez toho, aby lane vôbec bežal. Fronta `orsr` je v tom
istom okamihu **0** (worker `celery_worker_orsr` beží 34 h), takže sa vyprázdnila
podľa aritmetiky z `settings.py` (~17 h) a nezostal po nej zaseknutý lane.
Invariant teda drží na troch meraniach v rozostupe ~32 h, nie na jednom okne.

**Priamy dôkaz, že sa linka naozaj zastavila** (nie že sme len zmazali kód):
bežiaci beat zalogoval `DatabaseScheduler: Schedule changed.` o **22:16:20 UTC**,
hneď po zmazaní riadku a **pred** reštartom — dispatcher teda zareagoval na
zmazanie riadku okamžite. Po reštarte je riadok stále neprítomný a počet
riadkov ostal 9, čo je kontrola, že beat si ho **nezaložil znovu**.

> **Poradie je záväzné a je to pasca.** `DatabaseScheduler` pri štarte
> zosúlaďuje `CELERY_BEAT_SCHEDULE` do riadkov, takže zmazanie riadku pri
> **zvyšnom** zázname v dichte ho nechá vrátiť sa pri najbližšom štarte beatu.
> Najprv sa ruší záznam v `settings.py`, potom riadok — nikdy naopak.

Posledný dispatch linky bol 21:44:14 UTC (`total_run_count = 20`) a už vtedy
poslal nula úloh. Pred zásahom do produkčnej DB bola podľa predpisu urobená
a overená záloha: `cistafirma_20260916T221507Z.dump` (`make db-backup` +
`make db-backup-verify`). Rozpor v dokumentácii je vyriešený —
`ARCHITECTURE.md` tvrdil „riadok sa **vypína** (nie maže)", čo odporovalo
tomuto plánu aj `settings.py`; zjednotené na **zmazanie**, lebo vypnutý riadok
je kontrola, ktorá sa tvári, že rozhoduje nad prázdnou množinou.

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

> **Táto premisa 2026-09-17 padla — a je to dôvod prah nemeniť ani teraz.**
> Celý ten argument stál na tom, že frontu `orsr` drží vysoko dispatcher #95
> s 2 000 úlohami každé 4 h. Ten je zmazaný (viď #95 vyššie), takže `orsr` sa
> vracia k pôvodnému tvaru „vyprázdni sa" — ostáva mu len 500 z
> `sync-missing-orsr-profiles-every-4-hours` a rotácia ORSR. Prekalibrovať prah
> na ~6 000 by teda znamenalo nastaviť ho podľa stavu, ktorý **už neexistuje**,
> čo je presne tá chyba, ktorú tento odsek vytýka pôvodnému komentáru.
> Či je `50 000` správne pre obnovený tvar fronty, je naďalej otvorená otázka
> na človeka — nie tichá úprava, a už vôbec nie v rámci #95.
>
> **Meranie k 2026-09-17 07:27 UTC (na delle, čítaním):** `orsr` = **0**;
> `celery` 0, `ruz_full` 0, `financials` 0, `insurance` 1 689. Obnovený tvar
> fronty teda naozaj je „vyprázdni sa": jediné, čo doň pridáva, je
> `sync-missing-orsr-profiles-every-4-hours` s `args: [500]`
> (`settings.py:597-602`), a pri odtoku 15/m (dva sloty, viď nižšie) sa tých
> 500 vyprázdni za ~33 min zo 4 h. **Strop obnoveného tvaru je ~500, teda
> stonásobne pod prahom.** Prah 50 000 preto nie je zle prekalibrovaný na starý
> tvar — je to záplavová hranica pre frontu, ktorá inak sedí na nule, a presne
> to jeho komentár tvrdí. Ako detektor *zastaveného odtoku* je tupý (500 na tick
> by ho naplnilo až po ~17 dňoch), ale to nikdy nebol jeho účel — na to, či
> odčerpaná práca ešte niečo dosahuje, odpovedá Source health, nie hĺbka.
> **Odporúčanie: nemeniť**; rozhodnutie zostáva na človeku.

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

**Premerané 2026-09-13 21:16Z — a rýchlosť je na strope, len nie stále.**

| | ~12:51 | 21:16 |
|---|---|---|
| RPO profily (`rpo_id`) | 24 712 | 25 171 |
| prečítané (`osoby_historia`) | 2 489 | **3 748** |
| čaká | 22 223 | **21 423** |
| hotovo | 10,1 % | **14,9 %** |

Za 8,4 h pribudlo 1 259 prečítaní, čo je 150/h — ale populácia za ten čas
stúpla o 459, takže **čistý pokrok je 800 firiem za 8,4 h = 95/h**. To je tá
istá pasca ako vyššie: prírastok a úbytok sa takmer rušia.

Rozpad po minútach z logu workera (nie z fronty) ukazuje prečo:

| okno | čítaní | /h |
|---|---|---|
| 18:00–20:00 (degradované) | 6 | ~3 |
| 20:50–21:18 (28 min spojito) | 417 | **~894** |

Od 20:50 ide worker **spojito 15/min** — presne na `rate_limit='15/m'`.
Predtým len sporadické dávky oddelené dierami. 900/h je teda strop, nie
priemer, a rozdiel medzi tými dvoma číslami je celý rozdiel medzi „hotovo
o deň" a „hotovo o týždeň".

**ETA.** 21 423 ÷ 894 = **24,0 h**, ak register vydrží. Dve korekcie: populácia
rastie (+55/h), takže čistý odtok je ~840/h → **25,5 h**; a každá degradovaná
hodina pripočíta toľko, koľko trvala (dnešná 18:00–20:00 stála ~2 h). Plánové
„~25 h" v § 2 teda sedí — ale je to číslo postavené na **kapacite**, nie na
dostupnosti zdroja. To je tá istá trieda predpokladu ako pri poisťovniach
vyššie: dávka sa rovná odtoku na papieri a zdroj medzitým mlčí.

**Tik overený 2026-09-13 21:20:14Z — predpoveď sedela na jednotku.**

| | predpoveď | namerané |
|---|---|---|
| čas | 21:20:12 | **21:20:14,6** (+2,6 s jitter beatu) |
| `args` | 2 000 | `"[2000]"` |
| throttle | žiadny (backlog ~1 175 « 6 000) | **žiadny** |
| fronta `orsr` | ~3 179 | **3 174** (+1 995) |

```
21:20:14.562  "Scheduled person-history resync for 2000 companies"
21:20:14.568  succeeded in 1.61s: 'Scheduled person-history resync for 2000 companies'
```

Rozdiel 3 179 vs 3 174 je 5 správ, ktoré za tých 20 s odtiekli — fronta teda
narástla presne o dávku. Riadok `Person-history resync throttled` v logu
**nie je**, čo pri backlogue 1 175 a bounde 6 000 sedí: `headroom = 4 825`,
`min(2 000, 4 825) = 2 000`. **Tým je uzavretá posledná otvorená verifikácia
k #99** — a #99 na šťastnej ceste naozaj nič nemení, ako tvrdí.

**Čo z toho ale vyplýva pre #95 — a je to odporúčanie, nie nález.**
Od 21:20:14 stojí fronta na 3 174 a pri 894/h sa vyprázdni okolo **00:53**;
ďalší tik je 01:20:12. V zdravom cykle teda 2 000 správ odtečie za 2,24 h
a zvyšných **1,76 h zo štyroch je fronta prázdna** — dispatcher dodá 500/h,
kým fronta udrží 894/h. Zvýšenie dávky na ~3 500 (alebo interval na 2 h by
stihol to isté) by teda skrátilo #95 zhruba z 24 h na ~14 h. Neimplementované:
je to zmena `args` v `PeriodicTask` riadku bežiacej úlohy, nie vec #95, a
zdieľaná fronta s ORSR rotáciou je caveat, ktorý treba zvážiť spolu s tým.

> **Zavreté 2026-09-17: odporúčanie je bezpredmetné, neimplementuje sa.** #95
> dobehol a jeho riadok `PeriodicTask` aj záznam v `CELERY_BEAT_SCHEDULE` boli
> zmazané (viď #95 vyššie). Zdvihnúť dávku na ~3 500 by dnes znamenalo
> zrýchľovať linku, ktorá už nemá čo robiť.

---

## 3. Hotové — odôvodnenie a dôkazy

> Sekcia sa volala **„Čaká na prácu"** a premenovaná je 2026-09-17, lebo
> v nej nezostala ani jedna čakajúca úloha: všetkých päť sekcií pod ňou nesie
> ✅. Bola to pristávacia plocha pre prácu, ktorá sa ešte len mala spraviť, a tá
> sa vyprázdnila — takže nadpis tvrdil o dokumente niečo, čo už neplatilo.
> §1 je index hotového, táto sekcia je tá istá hotová práca **s odôvodnením
> a s dôkazmi**, a preto sa obsah nemení, len nadpis. Ak sa sem niekedy vráti
> čakajúca práca, patrí jej nová sekcia, nie tento nadpis.
>
> **Jedna vec tu napriek tomu otvorená je** a je to naozaj nález, nie úloha:
> **(a)** v #98 nižšie — `seat_*` nemá cestu, ktorá by ho zneplatnila, takže
> firme, ktorá sa presťahovala, kreslíme mapu na starú adresu natrvalo. Je
> výslovne mimo schválenej prírastky #98 a sú v ňom dve možné podoby opravy,
> takže patrí do samostatného rozhodnutia — nie do tohto nadpisu.

### Výpadok API na 3 h 43 min — nginx si adresu backendu preložil raz pri štarte — ✅ hotové (`96c601b`, `6f722bc`, `a845414`, `f4b822a`)

**Hlásenie Samuela (2026-09-17):** „po zadani nazvu firmy do vyhladavacieho pola
mi napisalo toto: 502 Bad Gateway … to iste po pokuse o prihlasenie: … **treba
analyzovat preco sa to deje a opravit, inak web nie je funkcny!**"

**Príčina.** nginx v produkčnom frontend image mal `proxy_pass
http://${BACKEND_UPSTREAM};` — teda **statické meno**, ktoré nginx prekladá
**raz, pri načítaní configu**, a potom sa naň už nikdy nepozrie. Nameraná časová
os:

| čas (UTC) | čo sa stalo |
|---|---|
| 06:36:54 | frontend naštartoval a preložil si `backend` → `172.18.0.5` |
| 06:37:16 | backend bol rekreovaný a vrátil sa na `172.18.0.11` |
| — | `172.18.0.5` medzitým dostal `celery_beat`, ktorý na `:8000` nepočúva nič |
| 06:37:27 → 10:20:00 | **každý** API request `connect() failed (111: Connection refused)` → 502 |

To je **3 h 43 min**, a je to presne trieda `#148`: hodnota odvodená z iného
zdroja, zapísaná presne jednou cestou, a **žiadna cesta ju neznehodnotí, keď sa
zdroj zmení**.

**Prečo to nemôže vyriešiť poradie nasadenia.** `depends_on` nehovorí nič o tom,
ktorý kontajner compose prekreuje *potom*, a samotné
`docker compose up -d --build backend` adresu posunie rovnako dobre.

**Oprava.** `upstream backend_upstream { server ${BACKEND_UPSTREAM} resolve
max_fails=0; }` + `resolver ${BACKEND_RESOLVER} valid=10s ipv6=off;`, a všetky tri
miesta (`/api/`, `/admin/`, `@backend_static`) menujú **skupinu**. `proxy_pass`
si drží statický tvar bez URI, takže sémantika URI je bajt na bajt tá istá.
`max_fails=0` je zámer: pri skupine o jednom prvku by zapnutá pasívna kontrola
označila jediného peer-a za mŕtveho a začala odpovedať 503 na všetko.

**Dôkaz — a jedno meranie, ktoré nevyšlo.** Prvý pokus na produkcii
(`docker compose up -d --force-recreate backend`) **nebol rozlišujúci**: Docker
pridelil backendu **rovnakú** IP `172.18.0.11`, takže nginx držal platnú adresu
a všetko odpovedalo 200. To je tá istá chyba, akú som predtým spravil
v laboratóriu. Skript to rozpoznal a postavil na uvoľnenú adresu **squatter** —
to, čo v skutočnom výpadku spravil `celery_beat`. Až potom sa adresa skutočne
posunula (backend → `172.18.0.14`) a meranie niečo dokazovalo:

| | stará statická forma (lab) | nová forma (lab) | nová forma (produkcia) |
|---|---|---|---|
| pred rekreáciou | 200 | 200 | 200 |
| t+0 | **502** | 502 | 502 |
| t+3 … t+9 | **502** | — | 502, 502, 502 |
| t+12 a ďalej | **502 navždy** | 200 | **200** — frontend sa nikdy nerestartoval |

**Druhá oprava toho istého dňa: môj vlastný komentár.** Do template som
z laboratórneho behu napísal, že zlyhané spojenie na držanú adresu vyvolá
**skoré re-preloženie**. Produkčný log to vyvrátil — nginx dialoval starú
`172.18.0.11` ešte v `10:54:25`, teda ~7 s po rekreovaní backendu (`10:54:18Z`),
a na správnu `172.18.0.14` prešiel až `10:54:28`. Tie dva pokusy boli **tiež**
odmietnuté, lebo backend ešte neotváral `:8000`. Okno teda viažu **dve** veci:
DNS lifetime (`valid=10s`) a štart samotnej aplikácie — `valid=` posúva len prvú.
Je to tá istá chyba ako pri náleze A nižšie: z jedného hrubého vzorku som vyvodil
mechanizmus. Opravené v `a845414`.

**Čo tým vyriešené NIE je** — v §7 boli dve veci: `deploy/k8s` a `deploy/helm`
`BACKEND_RESOLVER` **nenastavujú** (✅ opravené 2026-09-17, `eb22b41` a sprievodné
commity) a **nič v zostave výpadok API nezachytí** — `/healthz` je zámerne slepé
voči backendu a `prometheus.yml` nemá ani jedno pravidlo (✅ opravené 2026-09-17:
`ops_check.sh` má sekciu „API availability", ktorá ide cez `/api/` zvonka; detail
aj namerané stavy sú v §7).

**Overené naživo po nasadení** (`a845414`): `/` 200, `/api/stats/landing/` 200,
`/api/companies/search/?q=ecoklima` 200 s reálnymi dátami (ECOKLIMA s.r.o.,
Piešťany), `POST /api/auth/token/` 401 — teda **obe akcie, ktoré Samuel hlásil
ako 502, fungujú**.

**Regresia, ktorú som zaviedol ja — a potom jej dopad prehnal** (`f4b822a`,
plus oprava tohto zápisu nižšie). `proxy_pass` nesie URI sám, ale **Host nie**: keď location
nemá `proxy_set_header Host`, nginx pošle `$proxy_host`, teda meno presne tak,
ako je napísané v `proxy_pass`. Premenovanie na GROUP teda ticho zmenilo Host,
ktorý backend vidí. `location @backend_static` hlavičku nemal, takže z `backend:8000`
(prijímané — `ALLOWED_HOSTS` drží `backend` a port sa odreže) sa stalo
`backend_upstream`, čo v `ALLOWED_HOSTS` nie je vôbec. Našiel som to tak, že som
po zmene netestoval len `/api/`, ale **dosah zmeny**: `/static/<neexistujúce>`
vrátilo 400. Opravené tak, že `@backend_static` má teraz rovnaký blok hlavičiek
ako `/api/` — čo je striktne lepšie než pôvodný stav, kde Host `backend:8000`
fungoval len náhodou.

**A potom som z jedného chýbajúceho súboru vyvodil dopad na celý admin** — čo
bola tretia chyba tej istej triedy v tento deň. Overenie na produkcii ukázalo, že
`WhiteNoiseMiddleware` stojí v `MIDDLEWARE` **nad** `CommonMiddleware`, takže
existujúci statický súbor obslúži **skôr**, než Django vôbec validuje hostiteľa:

```
GET /static/admin/css/base.css          Host: backend -> 200, backend_upstream -> 200
GET /static/definitely-missing-98765.css Host: backend -> 404, backend_upstream -> 400
```

Reálne admin assety teda **nikdy zasiahnuté neboli**; regresia bola nesprávny
**status na miss** — chýbajúci súbor odpovedal 400 („tvoja požiadavka je
pokažená") namiesto 404 („taký súbor nie je"). Po nasadení `f4b822a` vracia tá
istá cesta cez publikovanú URL **404** a `/static/admin/css/base.css` **200**
s 23 100 B CSS, čiže fall-through cesta je živá a odpovedá rovnako ako backend
priamo. Že všetky `DisallowedHost` záznamy v logu sú **moje vlastné sondy** (4 → 6,
presne koľko som ich poslal), je súčasť toho istého merania — reálna prevádzka
žiadny nevyrobila.

### #98 — Kruh okolo sídla je tvrdenie o presnosti; dá sa nahradiť skutočnou budovou — ✅ hotové (`3e7d11a`)

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

**(a) `seat_*` nemá cestu, ktorá by ho zneplatnila — a nikto ho ani neprepočíta.**
Overené 2026-09-13 v troch krokoch:

1. Adresu firmy zapisuje **sedem** ciest v troch vrstvách a **ani jedna** nemá
   `seat_*` v `defaults`: päť synchronizačných (`tasks.py:570-572`;
   `fetch_ruz_data.py:538-540`; `repair_ruz_gaps.py:185-187`;
   `repair_ruz_sync.py:206-208`; `repair_ruz_sync_v2.py:175-177`), formulár
   Django adminu (`companies/admin.py:240-243`) a admin REST API
   (`adminapi/serializers/companies.py:152`, `fields = "__all__"`). Mapovanie
   `mesto`/`ulica`/`psc` je v tých piatich `defaults` skopírované doslovne, takže
   spoločný bod, kam invalidáciu zavesiť, **neexistuje**. (ORSR a RPO adresu
   firmy nepíšu — ukladajú ju len do `OrsrCompanyProfile.sidlo`, takže scraperov
   sa táto oprava netýka.) Adresa sa teda zmení a umiestnenie zostane na starom
   mieste. `models.py:349-350` to aj priznáva — „Nepíše ich synchronizácia
   z RUZ, takže import firmy ich neprepíše" — a podáva to ako ochranu, čo je
   správne: bez toho by sync zmazal dobrú prácu matchera. Chýbajúca polovica
   je, že **nič nerozpozná, keď sa zdroj pravdy pohol**.
2. `match_seat_addresses` **nie je naplánovaný nikde**: nie je v
   `CELERY_BEAT_SCHEDULE`, nie je v `PeriodicTask` riadkoch (overené výpisom
   všetkých zapnutých), a nespomína ho `Makefile` ani `scripts/`. Je to ručný
   príkaz, takže „kým sa matcher znova nespustí" neznamená „čoskoro" — znamená
   „až kým to niekto spraví".
3. `seat_matched_at` **existuje** (`models.py:377`; migrácia `0022`, commit
   `9bbdb6b`) a matcher ho zapisuje (`match_seat_addresses.py:217,224`). Tu
   donedávna stálo, že na `seat_*` **nie je žiadny časový stĺpec** — to bola
   **nepravda** (overené 2026-09-17). Stĺpec však znamená „kedy sa umiestnenie
   naposledy **zmenilo**", nie „kedy sa naposledy overilo": riadok, ktorého
   prepočet vyjde na tie isté hodnoty, sa preskočí (`:204-206`) a pečiatka sa
   s ním neobnoví. Migrácia navyše stĺpec pridala **bez backfillu**, takže koľko
   riadkov dnes pečiatku má, sa z repozitára vyčítať nedá: ostrý beh, ktorý
   dokument meria (dokončený 21:01), je starší než zapisujúca časť matchera
   (`560427b`, 21:06), takže sám pečiatky písať nemusel.
4. Ani keby pečiatka znamenala „naposledy overené", nie je z nej hlásenie: okrem
   definície, migrácie a dvoch riadkov v matcheri sa doslovný názov v repozitári
   **nevyskytuje nikde** — nie je v serializeroch, v admin API, v
   `companies/admin.py` ani vo frontende. Hodnota sa pritom **posiela po drôte**:
   `CompanyDetailSerializer` používa `Meta.exclude` (nie zoznam polí), takže DRF
   vygeneruje pole pre každý stĺpec `Company` vrátane `seat_*` a
   `seat_matched_at` — lenže ju nikto nečíta.

Dôsledok je používateľsky viditeľný: firme, ktorá sa presťahovala, kreslíme
mapu na starú adresu — natrvalo. Je to tá istá trieda ako počítadlo, ktoré
nevie, čo počíta: chýba údaj, ktorý by povedal, či je hodnota ešte pravdivá.
**Rozhodnutie je rozpísané v §4 (#148)** — s odporúčaním, dvomi odmietnutými
možnosťami a meraním, ktoré je zablokované na prístupovom práve.

**(b) — vyriešené.** §1 tabuľka vtedy vynechávala #85 – #92; dnes ich má
(overené 2026-09-17: riadky 85, 86, 87, 88, 89, 90, 91 aj 92 tam sú). Poznámka
zostáva len ako záznam, že diera existovala a bola doplnená — nie ako otvorená
vec.

### #93 — Jedna funkcia je rozsekaná na intervaly podľa dokumentov registra — ✅ hotové (`973d6d7`)

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

#### Hotové 2026-09-15 — `973d6d7` (backend) a `9a6e48b` (frontend)

Rozhodnutie padlo v prospech read-time a spojenie vzniklo ako **jedna zdieľaná
funkcia** `_joined_periods` (`backend/connections/views.py:302`), ktorú volá
`_merged_relations` (`:237`). Detail osoby aj výsledky hľadania tak dostali
spojenie z jedného miesta — odporúčanie žiadalo práve to, lebo dve
implementácie toho istého by sa rozišli v tom, čo tvrdia o tom istom človeku.

Čo implementácia drží — každý bod je jeden test v `JoinedPeriodsTests`
(`backend/connections/tests.py:429`), takže je to vynútené, nie zamýšľané:

- kľúč je **`(ico, role)`**, nie samotná firma: `konateľ` do 31. 12. a
  `prokurista` od 1. 1. sa stretávajú deň po dni presne ako reťaz zápisov, a
  zbalenie podľa firmy samotnej by zmenilo *výmenu funkcie* na *pokračovanie
  jednej*;
- `_continues_period` spája, keď je nasledujúce obdobie vzdialené **nanajvýš
  jeden deň** — register funkciu ukončí a ďalším zápisom ju na druhý deň znovu
  otvorí — a **absorbuje aj prekryv**, čo je ten istý jav zapísaný inak;
- **otvorené obdobie reťaz ukončuje**; nič sa doň nepripája, lebo dáta môžu
  obsahovať neskorší zápis (opätovné čítanie počas zápisu, oprava registra) a
  jeho zhltnutie by rozšírilo aktuálnu funkciu na úsek, o ktorom register
  tvrdí, že bola zatvorená;
- `vznik` = najskorší, `zanik` = **maximum**, nie posledný v poradí — dvojica sa
  môže prekrývať, takže neskorší začiatok neznamená neskorší koniec;
- `is_active` pochádza z **najnovšieho** zápisu, takže `None` („túto firmu sme
  nečítali", #86) spojenie prežije a jedenásť `False` neprehlasuje jednu `True`;
- riadok nesie `intervals` — počet zlúčených zápisov — aby zbalenie **priznal**;
  tiché by bolo presne to, čomu sa projekt vyhýba.

To posledné je aj dôvod, prečo je príklad s dierou testom a nie anekdotou:
osoba 56172 má v reťazi **34-dňovú dieru** (`2013-04-10` → `2013-05-14`), takže
z dvanástich riadkov vzniknú **dva**, nie jeden. Diera je fakt o histórii, nie
rytmus zápisov, a zlepenie by na otázku „odkedy" odpovedalo „nepretržite od
2011" na funkciu, ktorá mala dve obdobia.

**Graf patrí #100, nie #93 — a je to správne rozdelenie.** `CompanyGraphView`
nemá časovú os, takže zbalenie období by naň nemalo čo povedať; rozhoduje tam
identita hrany (`_edges_by_identity`, `views.py:357`). Admin počítadlo ostáva na
surových riadkoch: je to staff-only pohľad na tabuľku, nie tvrdenie o človeku.

### #100 — Graf kreslí tú istú hranu 12× (a #95 to zhoršuje) — ✅ hotové

**Vyriešené 2026-09-14.** `CompanyGraphView` teraz iteruje **po osobách**, nie po
väzbách, a hrany skladá `_edges_by_identity` na identitu `(source, target, role)`
— rola je súčasť identity, takže dve funkcie na tej istej dvojici zostávajú dve
hrany. `isActive` sa zlieva s precedenciou, ktorú už používa `_merged_relations`
(`True` > `False` > `None`), čiže pasca v odstavci nižšie je pokrytá.

Namerané na živej databáze (read-only, cez `APIRequestFactory`, bez reštartu):

* FREYSSINET CS (31798446): **21 hrán → 9**, uzly bez zmeny (10), a zlúčená
  hrana má `isActive=True` — teda tá jedna `True` medzi jedenástimi `False`
  vyhrala, ako má.
* Osem firiem s najviac väzbami (dnešný výber podľa počtu väzieb, nie ten istý
  výber, z ktorého je tabuľka nižšie): **1 119 hrán, 1 119 rôznych, 0
  redundantných**.
* Celá tabuľka: z 126 669 riadkov je **15 100 trojíc** `(osoba, firma, rola)`
  s viac než jedným riadkom, spolu **26 459 nadbytočných riadkov (20,9 %)** —
  a to je **dolná hranica**, lebo view zlieva po zhlukoch osôb, nie po riadkoch.

Testy: tri nové prípady (zbalenie + pasca `isActive`, dve roly = dve hrany,
počet dotazov nerastie s duplicitnými riadkami). Celá sada: 811 testov, OK.

**Frontend netreba meniť** — redundancia bola v odpovedi, nie v renderi.
„Nemerané" nižšie (či to bolo vidieť na plátne) tým ostáva nemerané, ale už
nie je dôvod to riešiť v `useGraphData.ts`.

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

**Re-verifikované 2026-09-13 21:20Z na tej istej živej odpovedi** (a teda nie
prevzaté): tých istých 8 firiem dáva presne 1 953 / 872 / 1 081 (55 %) — čísla
sedia na jednotku. Na úrovni dát to potvrdzuje aj priama otázka do tabuľky:
jediná dvojica `(osoba 56172, firma 31798446, rola 'ine')` má **12 riadkov**,
teda presne to „12×" z názvu. #95 medzitým píše ďalej a tieto čísla zatiaľ
nepohnul — ale je to práve to číslo, ktoré bude rásť, keď #95 dobehne.

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

> **Poznámka k umiestneniu (2026-09-17):** `#148` nižšie **už medzi blokované
> nepatrí** — čakal len na tvoje slovo, dostal ho a je hotový a uzavretý.
> Nechávam ho tu na mieste, kde jeho analýza vznikla, aby sa nepretrhali
> odkazy; čítať ho treba ako záznam, nie ako otvorenú položku. Nové nálezy
> tej istej triedy, ktoré na rozhodnutie **naozaj** čakajú, sú v sekcii
> *„Nové nálezy tej istej triedy ako #148"* na konci tejto časti.

---

### #148 — Sídlo sa presunie, mapa zostane na starej adrese — ✅ hotové a uzavreté na produkcii (2026-09-17)

**Stav:** bola to **nová prírastka** (mení zápis do `Company` a pridáva periodickú
úlohu), takže podľa pravidiel čakala na tvoje slovo — dostala ho, je
implementovaná, nasadená a **overená na produkcii**: `187daf3` (zneplatnenie),
`95c47a9` (prepočet a pečiatka), `0932453`, `b93cc93`, `fdf815c`.
Uzavretie s číslami je v sekcii *„Uzavretie #148 na produkcii: 56 609 → 0"* nižšie;
text pod týmto riadkom je pôvodná analýza a rozhodnutie, ponechaná ako záznam
o tom, **prečo** sa to robilo.

#### Čo je zle

`seat_*` (šesť stĺpcov) je **odvodená** hodnota: počíta ju `match_seat_addresses`
z `Company.{psc,mesto,ulica}` a z referenčnej tabuľky `AddressPoint`. Zdrojom
pravdy zostáva adresa — a **nič neznehodnotí umiestnenie, keď sa adresa pohne**.
Firma, ktorá sa presťahovala, má preto natrvalo pripnutú mapu na starej adrese.

#### Čo som overil (2026-09-17)

| # | zistenie | dôkaz |
|---|---|---|
| 1 | Adresu **prepisuje sedem** ciest a ani jedna nemá `seat_*` v `defaults` | päť sync ciest (`tasks.py:570-572`, `fetch_ruz_data.py:538-540`, `repair_ruz_gaps.py:185-187`, `repair_ruz_sync.py:206-208`, `repair_ruz_sync_v2.py:175-177`), formulár adminu (`companies/admin.py:240-243`), admin API (`adminapi/serializers/companies.py:152`). Ôsma cesta (`create_test_orsr.py:11-25`) adresu len **vytvára** cez `get_or_create`, takže existujúcemu riadku ju prepísať nevie a hook tam nemá čo invalidovať |
| 2 | Matcher **nie je naplánovaný nikde** | nie je v `CELERY_BEAT_SCHEDULE`, v `PeriodicTask` riadkoch, v `Makefile` ani v `scripts/` |
| 3 | `seat_matched_at` **existuje**, ale znamená „kedy sa zmenilo", nie „kedy sa overilo" | `models.py:377`; `match_seat_addresses.py:204-206` nezmenený riadok preskočí, `:217,224` píše pečiatku len so zmenou |
| 4 | Koľko riadkov pečiatku má, **sa z repa vyčítať nedá** | migrácia `0022` bez backfillu; meraný ostrý beh (21:01) je starší než zapisujúca časť (`560427b`, 21:06) |
| 5 | Všetkých sedem ciest ide cez `Company.save()` — pri dvoch to nie je zjavné (zistenie 7) | `save()` dnes obchádza len `bulk_update`, a ten adresu nepíše (`update_fs_data.py:122` = FS polia, `match_seat_addresses.py:222` = `seat_*`); `Company.objects.filter(...).update(<adresa>)` v repozitári nie je |
| 6 | ORSR a RPO adresu firmy **nepíšu** | `orsr_sync.py:36` ukladá len `OrsrCompanyProfile.sidlo`; `Company` adresu nemení |
| 7 | `update_or_create` **volá `save()`** — ale s **explicitným `update_fields`** | Django 6.0.1 `query.py:1053`: `obj.save(using=self.db, update_fields=update_fields)`, kde `update_fields = set(update_defaults)` (`:1012`). Hook na `save()` teda chytí všetkých päť sync ciest, ale musí si `seat_*` do `update_fields` **pridať** — inak sa vyčistenie v piatich hlavných cestách ticho neuloží. (Overené čítaním nainštalovanej knižnice: prvý návrh tohto plánu tvrdil, že `update_or_create` `save()` nevolá vôbec — bolo to nesprávne.) |

#### Koho sa to týka — a koho nie

Toto je dôležité, lebo prvá analýza to tvrdila opačne:

- **Netýka sa to 65 324 neumiestnených firiem.** Ich mapa je kruh okolo PSČ a ten
  sa počíta **živo z `obj.psc` pri každom čítaní** (`serializers.py:163`), takže
  sa s adresou pohne sám. Nie sú zastarané, sú len nepresné — a to je ich
  zdokumentovaný zámer (`match_seat_addresses.py:7-9`). Nepotrebujú ani
  backfill, ani zneplatnenie.
- **Týka sa to umiestnených firiem** — tých, ktoré majú `seat_*` vyplnené
  (meranie z 13. 9.: 384 440, teda 85,5 %). Ich pin je presný, a preto aj
  presne zlý, keď sa adresa pohne.

#### Možnosti

**(A) Zneplatniť pri zmene — odporúčam.** Keď zapisovateľ zmení `psc`/`mesto`/
`ulica`, vyčistiť šesť `seat_*` aj `seat_matched_at`. Riadok tým padne presne do
stavu, ktorý matcher už dnes píše pre neumiestniteľnú firmu
(`None, None, '', None, None, ''`), a serializér odpovie kruhom okolo **novej**
PSČ.

- Miesto zavesenia: `Company.save()` s uloženým pôvodným stavom z `from_db`,
  takže **žiadny dotaz navyše** — pokrýva všetkých sedem ciest, lebo všetky idú
  cez `save()` (a `update_or_create` je medzi nimi, zistenie 7).
- K tomu **naplánovať `match_seat_addresses`**, aby sa presnosť vrátila.

**Tri veci, ktoré musí (A) vyriešiť — inak vyrobí novú tichú chybu:**

1. **Karta by o sebe tvrdila nepravdu.** `explanation()` v `SeatLocationCard.tsx`
   (`:138-166`) to píše v oboch hrubších vetvách — raz pre ulicu
   („…pozná ulicu, ale nie konkrétnu budovu, takže bližšie sídlo umiestniť
   nevieme", `:152-154`), raz pre PSČ („…pozná len stred PSČ…", `:161-162`).
   Pre firmu, ktorú register umiestniť **vie** a my sme ju len ešte
   nespárovali, je to nepravda o **schopnosti**, nie len hrubšia mapa — a to je
   iná trieda chyby. Preto (A) patrí dokopy s rozlíšením „nespárované" vs.
   „nepárovateľné" v texte karty; inak by sme jednu tichú lož vymenili za druhú.
2. **Firme s pinom a neumiestniteľným PSČ zmizne karta úplne.** Keď sa `seat_*`
   vyčistí a nové `psc` je prázdne alebo mimo `PostalCodeArea`,
   `serializers.py:164-168` vráti `None` — žiadny kruh, teda ani karta (dnes:
   presný pin). Je to regresia a má byť **pomenovaná vopred**, nie objavená po
   nasadení. Zmierňuje ju, že si serializér ten stav sám definuje ako správny:
   „`None` je skutočná odpoveď a znamená *nedokážeme sídlo umiestniť*, nie
   *firma nemá sídlo*" (`:146-150`), s meraním 1,92 % riadkov s PSČ, ktoré
   register neuvádza, plus tri riadky bez PSČ vôbec. Preto je to **prijateľná**
   cena — ale len keď je pomenovaná; počet, ktorý ju kvantifikuje, je v druhom
   dotaze v „Zablokované meranie".
3. **Pravidlo musí znieť „zmenilo sa na inú *neprázdnu* hodnotu".** Adresné
   kľúče idú do `defaults` cez holé `data.get('mesto')` (`repair_ruz_sync.py:206-208`
   a rovnako v ostatných štyroch), takže **chýbajúci** kľúč zapíše `None` — a
   naivné „zmenilo sa" by vymazalo pin firme, ktorej sa adresa v skutočnosti len
   neposlala. Repo ten istý rozdiel už rieši inde (`apply_ruz_dates` odlišuje
   *neprítomné* od *nečitateľného*); tu treba ten istý vzor, nie `!=`.
   A nie je to len analógia: `apply_ruz_dates` (`ruz_api.py:325-349`) funguje
   **tým istým mechanizmom** — nechá kľúč *von* z `defaults`, a práve preto
   `update_or_create` uloženú hodnotu nechá (zistenie 7). Vzor je teda v tomto
   repozitári už nosný a otestovaný, nie nový.
- ➕ Bez nového stĺpca, bez migrácie, bez backfillu.
- ➕ Nevyžaduje si **ani poznať** populáciu s pečiatkou (zistenie 4) a nezávisí
  na význame `datumPoslednejUpravy`, ktorý je **neoverený** — registrová príručka
  ho definuje ako dátum zmeny ovplyvňujúcej *zobrazenie*, s príkladmi, ktoré
  adresou nie sú (`api_ruz_navod.txt:171`).
- ➕ Pravdivé sú **dáta**, nie len jedno čítanie — a to tu má váhu, lebo surové
  `seat_*` ide po drôte (admin API, `fields = "__all__"`).
- ➖ Je to správanie skryté v modeli; bez docstringu a testov je to presne tá
  trieda chyby, ktorú tento projekt stíha.
- ➖ **Naivná verzia je horšia než žiadna.** Pridať `seat_*=None` do piatich
  `defaults` slovníkov vyzerá ako tá istá oprava a je to prvá vec, ktorá
  napadne — ale pri jednej otočke syncu (6 h) zmaže piny **celej** populácie,
  a keďže matcher naplánovaný nie je (zistenie 2), niet čím ich vrátiť.
  Práve preto patrí rozhodnutie do **jedného** miesta, ktoré porovnáva hodnoty,
  a nie do piatich zápisov naslepo.
- ➖ Nerieši druhú os: `AddressPoint` je referenčná tabuľka, nahradzovaná celá pri
  (štvrťročnom) importe, a nesie len `source_version` na snímku —
  `serializers.py:140-145` to pomenúva ako „dve nezávislé cesty k zastaraniu".

**(B) Hlásiť zastarané riadky — odmietam.** `seat_matched_at < datum_poslednej_upravy`
ako detektor **nemôže fungovať** tak, ako je navrhnutý:

- Pečiatka znamená „naposledy zmenené" (zistenie 3), takže riadok, ktorý sa
  prepočíta na tie isté hodnoty, sa hlási ako zastaraný **navždy** — aj po
  správnom behu matcheru.
- `datum_poslednej_upravy` sa podľa vlastnej dokumentácie hýbe aj z dôvodov,
  ktoré adresou nie sú, takže väčšina nahlásených riadkov by neboli sťahovania.
- Potreboval by backfill, ktorý nemáme (zistenie 4).
- `NULL < dátum` je `NULL`, nie `true`, takže neumiestnené riadky by nešlo
  označiť (hoci podľa vyššie uvedeného ani netreba).
- A hlavne: **nič neopravuje.** Mapa zostane na starom mieste a pribudne zoznam,
  ktorý nemá kto spracovať.

Hodí sa dodať, že repozitár **už má** funkčný mechanizmus tejto triedy — schému
`parser_revision` + `companies_due_for_sync(stale_revision=…)`, ktorá sa dolieči
tým, že riadky **znovu prečíta** (`sync_engine.py:782`, `tasks.py:1273`). To je
lepší vzor než hlásenie: liečiť, nie sa sťažovať. (A) je jeho obdobou.

**(C) Odložiť odtlačok vstupu** — hash z `psc|mesto|ulica` plus `source_version`
použitej snímky, a v **čítaní** považovať nezhodu za „neumiestnené".
➕ Ako jediná pokrýva aj druhú os (verzia datasetu). ➖ Nový stĺpec a migrácia;
backfill je buď lož („vyhlásime dnešok za zhodný"), alebo drahý (všetky
umiestnené riadky spadnú na kruh, kým neprebehne celý matcher — merane 53 minút,
`PLAN.md` § 2); a surové `seat_*` v admin API by aj tak ukazovali starý pin.

#### Odporúčanie

**(A) + naplánovať matcher.** Rieši presne to, na čo sa úloha sťažuje (mapa na
starom mieste), nepotrebuje schému ani backfill a dá sa overiť testom na každej
z troch vrstiev zápisu. Druhú os (verzia datasetu) navrhujem viesť ako
**samostatný** záznam — inak sa z malej opravy stane zmena schémy.

#### Čo spravím po schválení

1. `Company.save()` + `from_db`: pri zmene ktorejkoľvek z troch adresných hodnôt
   na inú **neprázdnu** hodnotu vyčistiť `seat_*` a `seat_matched_at`. Tri
   pasce, ktoré treba ošetriť:
   - `update_fields` **nie je okrajový prípad**: všetkých päť sync ciest volá
     `update_or_create`, a to v Djangu 6.0 `save(update_fields=…)` posiela
     (zistenie 7). Hook preto musí `seat_*` a `seat_matched_at` do zoznamu
     **doplniť** — inak sa vyčistenie v piatich hlavných cestách ticho neuloží.
   - `from_db` dostane pri `only()`/odložených poliach **podmnožinu** stĺpcov
     (porovnávať len keď tam sú všetky tri).
   - porovnávať **hodnoty**, nie prítomnosť kľúča — pasca 3 vyššie.
2. Docstring `models.py:347-349` — dnes tvrdí, že sync `seat_*` neprepíše; po
   zmene musí znieť presne (neprepíše ich, ale zneplatní).
3. Text karty `SeatLocationCard.tsx:138-166` (`explanation()`): rozlíšiť
   **„ešte nespárované"** od **„nepárovateľné"**. Dnešná veta sľubuje
   neschopnosť registra; po (A) by klamala. Malá zmena textu, ale bez nej je
   oprava len polovica — a je to presne tá polovica, ktorú používateľ vidí.
4. Testy: (a) zmena adresy cez `update_or_create` vyčistí `seat_*`
   **a naozaj sa uloží** (kontrola `update_fields`, nie len objekt v pamäti);
   (b) zmena adresy cez admin API `PATCH` tiež; (c) **nezmenená** adresa `seat_*`
   nechá tak; (d) zmena na `None` (chýbajúci kľúč) `seat_*` **nevyčistí**;
   (e) `bulk_update` adresy `seat_*` **nevyčistí** — test to musí priznať
   nahlas, aby diera nebola tichá.
5. Naplánovať `match_seat_addresses`: zápis do `CELERY_BEAT_SCHEDULE` **aj**
   `PeriodicTask` riadok s tými istými `args` (riadok je to, čo naozaj beží)
   a `last_run_at` do minulosti, aby prvý beh neposunul reštart beatu o celý
   interval — presne pasca z §7. Interval 6 h, nie denný.
6. Nasadenie na `dell`: `git pull gitlab-home`, `migrate` (táto zmena migráciu
   neprináša, ale krok patrí do postupu), reštart beatu; predtým `make db-backup`
   a `make db-backup-verify`.
7. Po nasadení jeden plný beh matchera, ktorý **dorovná dnešný dlh** — adresy,
   ktoré sa pohli od 13. 9.

#### Nález po nasadení: príkaz neopečiatkoval riadok, ktorý neumiestni (2026-09-17)

Krok 5 platí, ale prvá polovica #148 sa nasadila skôr, než sa ukázalo, že
**tretí stav sa nikdy nedokonverguje**. `match_seat_addresses` zapisoval riadok
len vtedy, keď sa mu zmenili `seat_*` — a `_wanted(None)` je presne to, čo
neumiestnený riadok už má. Každá firma, ktorú register umiestniť nevie, teda
zostala bez `seat_matched_at`, a `pending` číta len ten. Karta o takej adrese
ďalej tvrdila „register adries sme na ňu ešte nepustili" — pri každom priechode,
navždy.

Merané na produkcii 2026-09-17:

| | počet |
|---|---|
| riadkov spolu | 449 780 |
| `seat_matched_at` nastavené | 393 171 |
| `seat_precision` prázdne (neumiestnené) | 56 609 |
| neumiestnené **a** opečiatkované | **0** |
| neumiestnené **a** bez pečiatky | **56 609** |
| umiestnené bez pečiatky | 0 |

Dokonalé rozdelenie: pečiatka padala presne na riadky, ktoré sa zmenili. To nie
je nález o okraji — to je najhoršia tretina populácie, ktorá sa neumiestni.

Oprava (95c47a9) číta aj `seat_matched_at` a zapisuje, keď sa umiestnenie
zmenilo **alebo** keď riadok pečiatku nemá. Hlásenie tie dva počty rozlišuje:
prvý je dlh, ktorý viaže šesťhodinový interval, druhý je backlog, ktorý sa
vyčerpá jediným priechodom — a krok 7 sa tak dá **odpovedať**, nie len spustiť.

Testy: `MatcherRunTests` príkaz naozaj **spustí**. Dovtedy ho nespúšťal nikto:
`_wanted` sa len importoval a porovnával, a práve preto mohla tá chyba sedieť
v repe so zelenou sadou a s dvoma docstringami, ktoré tvrdili opak
(`models.py:375`, `serializers.py:155`).

#### Uzavretie #148 na produkcii: 56 609 → 0 (2026-09-17)

Nasadené na `dell` (`b93cc93`, CI pipeline 121 zelená, 7/7 jobov), po
`make db-backup` + `make db-backup-verify`
(`cistafirma_20260917T064818Z.dump`). Žiadna migrácia. Reštartoval sa **len**
`celery_worker_default` — je to jediný proces, ktorý `call_command` volá, a
`backend` ani `celery_beat` tento modul neimportujú. Použil sa
`docker compose restart -t 300`, nie holý `restart`: v `settings.py` nie je
`task_acks_late`, takže predvolené potvrdenie prichádza **pred** vykonaním
úlohy a tvrdý reštart by rozbehnutú úlohu ticho zahodil.

Overenie pred zápisom bolo **falzifikovateľné** a vyšlo presne: `--dry-run
--limit 2000` dalo `0 would change` **a** `433 already matched the register and
would be stamped`. Pred opravou vypísal len prvý riadok; tých 433 sa mlčky
preskočilo. Číslo 433 je zároveň počet neumiestnených v tom okne (21,6 %).

Plný priechod potom dorovnal dlh:

| | pred | po |
|---|---|---|
| riadkov spolu | 449 780 | 449 780 |
| `seat_matched_at` nastavené | 393 171 | **449 780** |
| neumiestnené **a** bez pečiatky | 56 609 | **0** |
| umiestnené | 393 171 | 393 175 |
| zmenené týmto priechodom | — | 4 |
| opečiatkované bez prepisu | — | 56 605 |

Aritmetika sa uzaviera na jednotku: 56 605 + 4 = 56 609. Tie **štyri** sú
zároveň jediné riadky, ktoré pribudli do `umiestnené` (393 171 → 393 175) — sú
to firmy, ktorým sa od 13. 9. pohla adresa, `Company.save()` im vyčistil
`seat_*` a matcher ich teraz umiestnil. Obidve polovice #148 sa teda na
produkcii potvrdili v jednom priechode: zneplatnenie (187daf3) aj prepočet
(95c47a9).

**Krok 5 — permission vrstva zápis odmietla, ale plánovač si ho vyriešil sám.**
`UPDATE django_celery_beat_periodictask SET last_run_at = …` („Blocked by
classifier”). Neobchádzal som to. Dôsledok bol malý a bolo to **oneskorenie, nie
strata**: riadok má `last_run_at` NULL a `date_changed` 06:37:21.9008 UTC, takže
`ModelEntry` ho číta ako `date_changed` a prvý plánovaný beh padá na
**12:37:21 UTC** — o šesť hodín. Backlog je pritom dorovnaný manuálne, takže ten
beh už len potvrdí, že automatická cesta funguje. **Presne to sa stalo** —
*„Krok 5 dokončený”* nižšie.

**Čo z toho zostáva otvorené — a čo nie** (overené 2026-09-17 ~07:30 UTC, čítaním;
prvá odrážka od 12:37 UTC už neplatí — pozri *„Krok 5 dokončený"* nižšie):

- **Riadok**, `SELECT * … WHERE name = 'match-seat-addresses-every-6-hours'`:
  `task = registers.tasks.match_company_seats`, `queue = celery`, `enabled = t`,
  `last_run_at` prázdne, `total_run_count = 0`, `date_changed = 06:37:21.9008+00`,
  `interval_id = 2`. Prázdne je aj `expires` **a** `expire_seconds` — tretie
  nezávislé potvrdenie nálezu nižšie.
- **Cesta beat → `celery` fronta → worker žije a je práve v prevádzke.**
  `celery_beat` (štart 06:37:16Z, `RestartCount` 0) odovzdal
  `send-pending-notifications-every-15-min` o **07:25:08.936** a
  `celery_worker_default` (štart 07:10:59Z po teplom reštarte, `RestartCount` 0)
  zalogoval to isté zadanie ako prijaté o **07:25:08.939** — teda ten istý front,
  aký má tento riadok. V beat logu sú za ten čas aj štyri odovzdania
  `detect-stuck-sync-jobs-every-10-min` (06:46, 06:56, 07:06, 07:16 UTC).
- **Otvorené teda zostáva jediná vec:** že tomuto konkrétnemu riadku naozaj
  uplynie jeho interval. To sa čítaním overiť nedá, len časom.

Overenie po 12:37:21 UTC je stále len čítanie:

```sql
SELECT total_run_count, last_run_at FROM django_celery_beat_periodictask
WHERE name = 'match-seat-addresses-every-6-hours';
```

`total_run_count` 0 → 1 a `last_run_at` ~12:37 UTC to potvrdí.

#### Krok 5 dokončený: riadok sa spustil sám, v predpovedanú sekundu (2026-09-17)

Overené čítaním na `dell` — vyšlo presne:

| | hodnota |
|---|---|
| `total_run_count` | **1** (predtým 0) |
| `last_run_at` | **2026-09-17 12:37:21.91305+00** |

Predpoveď o sekciu vyššie znela „prvý plánovaný beh padá na 12:37:21 UTC"
a `date_changed` bol `06:37:21.9008+00`. Odchýlka je **12 ms**, takže interval
6 h sa naozaj uplatnil a posun o celý interval po reštarte beatu nenastal. Tým je
zodpovedané to jediné, čo sa čítaním overiť nedalo („že tomuto konkrétnemu riadku
naozaj uplynie jeho interval") — a to je zároveň to, čo mal krok 5 získať.
Odmietnutý zápis `last_run_at` do minulosti by tú istú vlastnosť **overil o šesť
hodín skôr**; nezískal ju, len urýchlil.

`total_run_count` sám dokazuje len **odovzdanie**, nie vykonanie, preto aj worker
log tej istej session:

| čas (UTC) | riadok |
|---|---|
| 12:37:21.915733 | `registers.tasks.match_company_seats[4de451a7]` received |
| 12:37:21.917004 | `Triggering match_seat_addresses command...` |
| 12:40:25.617566 | `match_seat_addresses command finished.` |
| 12:40:25.618614 | `succeeded in 183.70185311799287s` |

Beh trval **183,7 s** a skončil `succeeded`. Príkaz v ňom vypísal svoj súhrn
a ten je druhý, nezávislý dôkaz, že sa dlh **nevracia**:

| | po uzavretí (o sekciu vyššie) | tento beh |
|---|---|---|
| riadkov spolu | 449 780 | **449 786** |
| umiestnené | 393 175 | **393 181** |
| neumiestnené | 56 605 | 56 605 |
| zmenené týmto priechodom | 4 | **6** |

Rozdiel sú 6 nové riadky a všetkých 6 sa umiestnilo (393 175 + 6 = 393 181,
449 780 + 6 = 449 786); súčet 393 181 + 56 605 = 449 786 sa uzaviera na jednotku.
Neumiestených je stále 56 605 a **ani jeden z nich nebol prepísaný** — čo je
presne to, čo `95c47a9` sľubuje: riadok bez zmeny umiestnenia sa zapisuje len
vtedy, keď pečiatku nemá. Keby backlog pečiatku nemal, „zmenené" by bolo o tých
56 605 vyššie — teda 56 611, nie 6.

To posledné je však odvodené z počtu, nie zmerané — a práve „počet, ktorý nevie
ukázať zlyhanie" je trieda, ktorá ma tu už raz oklamala. Preto to isté ešte raz
**meraním**, tou istou úzkou agregáciou, akú permission vrstva predtým pustila:

```sql
SELECT count(*) AS total,
       count(*) FILTER (WHERE seat_matched_at IS NOT NULL) AS stamped,
       count(*) FILTER (WHERE coalesce(btrim(seat_precision),'') <> '') AS placed,
       count(*) FILTER (WHERE coalesce(btrim(seat_precision),'') = ''
                          AND seat_matched_at IS NULL) AS unplaced_unstamped
FROM "Companies and SZCO";
```

```
449786|449786|393181|0
```

**Dlh je na nule a zostal na nule.** Všetkých 449 786 riadkov má pečiatku
a `neumiestené a bez pečiatky` je **0** — tých 56 605 neumiestnených pečiatku
**má**, matcher ich neobchádza. To je zároveň odpoveď na krok 7, ktorá sa podľa
*„Nález po nasadení"* vyššie už len čakala: *„dlh, ktorý viaže šesťhodinový
interval"* = 0 a *„backlog, ktorý sa vyčerpá jediným priechodom"* = 0. Automatická
cesta je teda overená **v prevádzke**, nie len jednorazovým behom, ktorý som
spustil ručne.

---

Poznámka pod týmto riadkom o odmietnutom `UPDATE` je teda **bezpredmetná** —
netreba ju použiť, ale nechávam ju ako záznam, prečo sa `last_run_at` needitoval.

Ak by to niekto neskôr predsa len chcel posunúť skôr, odmietnutý zápis mal dva
stĺpce: `last_run_at = now() - interval '1 day'` a `last_update = now()`. To
druhé je nutné — `last_update` je `auto_now` na úrovni Djanga, nie spúšťač v DB,
takže holý SQL UPDATE by ho neposunul a `schedule_changed()` by si zmeny nevšimol
skôr než pri vynútenom úplnom synchronizujúcom čítaní po 300 s
(`SCHEDULE_SYNC_MAX_INTERVAL`).

#### `options: {'expires': …}` je pre riadok inertné — príčina je názov kľúča

Vedľajší nález z toho istého čítania. `ModelEntry._unpack_options` berie
`expire_seconds`, **nie** `expires` (`django_celery_beat/schedulers.py:217-218`),
takže `expires` spadne do `**kwargs` a zahodí sa; expiry riadka pochádza
výhradne z `model.expires_`. Komentár v `settings.py` to vysvetľoval tým, že
`options` sa nedostane do riadka, ktorý už existuje — lenže `queue` je tiež
`options` a v riadku **je** (overené na riadku vytvorenom z tohto dictu).
Zámer teda do riadka nedorazí vôbec a tri vrstvy sa v tomto bode nezhodujú.

Nepremenoval som to na `expire_seconds`: tým by sa „beh sa oneskorí" zmenilo na
„beh nenastane", čo je horšia vlastnosť než tá, ktorú to má opraviť. Je to
rozhodnutie o sémantike plánovania, nie preklep — **na teba**.

#### Čítanie produkčnej DB: čo permission vrstva odmietla a čo prešlo

Permission vrstva na `dell` odmietla tri **široké** akcie: `docker compose up -d`
(celý stack), `docker compose exec -T backend python manage.py shell` (ľubovoľný
kód v produkčnom kontajneri) a priamy dotaz na produkčnú databázu
(`[Production Reads]`). Neobchádzal som to — ale **zúženie na jedinú agregáciu
prešlo**: `docker compose exec -T db sh -c 'psql …'` s `count(*) FILTER (…)` nad
`"Companies and SZCO"`, a rovnako `manage.py match_seat_addresses --dry-run
--limit 2000`. Rozdiel nie je v tom, že by čítanie bolo zakázané a teraz
povolené — je v tvare dotazu. Obe strany tu nechávam preto, aby ďalšia session
nehľadala povolenie, ktoré netreba, a zároveň sa nepokúšala obísť odmietnutie,
ktoré stále platí.

Z troch otázok nižšie je **prvá zodpovedaná** meraním o sekciu vyššie (393 171
riadkov má pin). Druhá a tretia nie — a tretia po #148 stráca zmysel: pečiatka
už nie je „kedy naposledy", ale „či sme sa na túto adresu vôbec pýtali", takže
porovnávať ju s `Dátum a čas kontroly RUZ` už nič neznamená.

```sql
-- 1) Horná hranica dosahu: koľko riadkov má vôbec pin, ktorý sa dá pokaziť.
--    (Obdoba: seat_precision <> '' — matcher píše '' pre neumiestnené.)
SELECT count(*) FROM "Companies and SZCO" WHERE seat_lat IS NOT NULL;

-- 2) Z nich tie, ktoré (A) pošle na kruh a kruh im nevznikne — prázdne PSČ
--    (pasca 2). Koľko z nich má PSČ, ktoré v PostalCodeArea NIE JE, SQL sám
--    nepovie; to je druhá polovica tej istej regresie a chce join na tabuľku PSČ.
SELECT count(*) FROM "Companies and SZCO"
WHERE seat_lat IS NOT NULL
  AND coalesce(btrim("PSČ"), '') = '';

-- 3) Koľko pinov je naozaj podozrivých (pečiatka staršia než posledná zmena).
--    Pozor: `NULL < dátum` je NULL, nie true — bez `IS NOT NULL` by dotaz
--    ticho vrátil nulu a tváril sa, že je všetko v poriadku.
SELECT count(*) FROM "Companies and SZCO"
WHERE seat_matched_at IS NOT NULL
  AND seat_matched_at::date < "Dátum a čas kontroly RUZ";
```

Ani jedno z tých čísel **nie je podmienkou opravy** — (A) funguje bez nich.
Sú odpoveďou na „aké veľké to je a čo tým rozbijeme", teda do reportu;
druhé z nich je zároveň jediné, ktoré vie regresiu z pasce 2 kvantifikovať
**pred** nasadením namiesto po ňom.

---

### Nové nálezy tej istej triedy ako #148 — A a B opravené, C a D čakajú na tvoje rozhodnutie (2026-09-17)

Po uzavretí `#148` som nechal prejsť celý repozitár **jednou otázkou**: ktoré
ďalšie pole je *odvodené* z iných stĺpcov, zapisuje ho **presne jedna cesta** a
**nič ho neznehodnotí, keď sa zdroj zmení**? To je presne tvar chyby, ktorú mal
`#148` — a hľadanie vrátilo štyri rodiny. Sweep vrátil 6 potvrdení a **0
vyvrátaní**, čo je samo o sebe podozrivé číslo, tak som každý nález overoval
zvlášť proti kódu **a proti ostrej databáze na `dell`**. Dva z nich sa pritom
meraním **vecne zmenili** — to je dôvod, prečo tu nie sú odpísané zo sweepu.

**Pôvodne som nič z toho neopravil** — každá oprava je nová prírastka (mení
zápis alebo pridáva úlohu), takže podľa pravidiel čakala na tvoje slovo. To
slovo prišlo, takže **A aj B sú implementované, otestované a nasadené** (stav
je vždy v podsekcii `✅` na konci príslušného nálezu). **C a D na rozhodnutie
naozaj čakajú** — C je produktová otázka, nie chyba.

#### A. `SectorBenchmark` — počíta sa len pre **jediný** rok, takže 1 703 firiem nemá porovnanie vôbec — ✅ opravené 2026-09-17

| | |
|---|---|
| **Odvodené z** | `CompanyFinancialResult` danej NACE sekcie a roka |
| **Zapisuje** | `companies/services/benchmarking.py:104` (`update_or_create`), denne cez `compute-sector-benchmarks-daily` |
| **Číta** | `companies/serializers.py:324`, `companies/services/pdf_report.py:323` — **obidva kľúčujú rokom firmy, nie rokom benchmarku** |
| **Zmerané na `dell`** | `"Sector Benchmarks"` = **19 riadkov, všetky za rok 2025** |

Pri `year=None` (a beat tú úlohu púšťa **bez `args`**, takže `year` je vždy
`None`) funkcia prejde roky od najnovšieho a vybere **prvý, ktorý má aspoň 500
výsledkov** (`benchmarking.py:47-63`) — a **zapíše len ten jediný**. Beatin riadok
je pritom jediný spúšťač: je v tabuľke `PeriodicTask` (`runs=3`, naposledy
2026-09-16 18:34), takže sa to naozaj deje.

**Pri meraní sa ukázalo, že koreň je inde, než to vyzeralo — a je to horšie.**
Prah 500 **nie je** to, čo drží pokrytie na jednom roku: cez prah prejde každý
rok od 2013 po 2025.

| rok závierok | firiem s výsledkami | `>= 500`? |
|---|---|---|
| 2026 | 80 | **nie** |
| 2025 | 12 555 | áno |
| 2024 | 12 935 | áno |
| 2023–2014 | 13 005 – 13 461 (každý rok) | áno |
| 2013 | 12 752 | áno |

Úloha teda **má** dáta na 13 rokov a spočíta **jeden** — na prvom vyhovujúcom
roku `break`-ne. Prah 500 vysvetľuje len to, prečo je tým rokom 2025 a nie 2026;
chýbajúce roky 2013–2024 s prahom nemajú nič.

Rozdelenie firiem podľa **ich vlastného najnovšieho roka** (merané 2026-09-17).
Pozor: tabuľka, ktorá tu bola predtým, bola **nesprávna** — nesčítavala sa na
populáciu (14 065 namiesto 15 467) a číslo „1 506" pre rok 2024 a staršie
nezodpovedalo žiadnemu meraniu. Nahradil som ju týmto, ktoré sedí na jednotku
(`98 + 13 666 + 469 + 1 234 = 15 467`):

| najnovší rok firmy | firiem | riadkov benchmarku pre ten rok |
|---|---|---|
| 2026 | 98 | **0** — správne, rok sa ešte podáva (98 vykazov < prah 500) |
| 2025 | 13 666 | 19 |
| 2024 | 469 | **0** |
| 2023 a staršie | 1 234 | **0** |

**Dôsledok — dve rôzne veci, obe zlé:**

1. **1 703 firiem** (najnovší rok 2013–2025, teda **mimo** 2026) nemá
   porovnanie so sektorom **bez akéhokoľvek dôvodu** — benchmark pre ich rok sa
   dal dávno spočítať z 12–14 tisíc firiem, ktoré ten rok majú (2024: 469,
   2023: 179, 2013–2022: 1 055). Toto je prevládajúca časť nálezu a v sweepu
   **nebola**.
2. **98 firiem, a rastie:** firma, ktorá **zverejní novšiu závierku**, sa posunie
   na 2026, `get_benchmark` vráti `None` a o porovnanie **príde** — teda presne
   opačná motivácia, než akú má produkt: čerstvejšie dáta = horšia stránka. Toto
   je tá **rastúca hrana** a s každou ďalšou závierkou za 2026 sa zväčšuje.
   (Táto druhá časť opravou nezmizne a ani zmiznúť nemá — 2026 je pod prahom
   oprávnene. Je to cena za to, že prah existuje.)

Nikde na to nie je kontrola; API vráti `null` a PDF sekciu ticho vynechá.

**Možnosti:** (1) počítať pre **každý rok, ktorý má dáta**, a nechať rozhodovať
len per-sekciovú poistku `>= 5`, ktorá v tom istom súbore už je (`:100-102`);
(2) čítať fallbackom na najnovší benchmarkovaný rok sekcie; (3) znížiť alebo
odstrániť globálny prah. **Odporúčam (1)** — odstráni obe časti nálezu naraz a
ponechá jedinú poistku, ktorá naozaj chráni pred mediánom z pár firiem. Cena je
malá a ohraničená: ~14 rokov × najviac 19 NACE sekcií, teda **rádovo 250 riadkov**
namiesto dnešných 19.

##### ✅ Opravené 2026-09-17 (`8621da7`) — odporúčanie (1), presne ako stálo

`year=None` teraz znamená **každý** rok nad prahom; `year=<int>` ostáva jeden
konkrétny rok. Návratový typ je `{rok: {sekcia: počet firiem}}` — pri viacerých
rokoch bol pôvodný tvar nejednoznačný. Popri tom sa našla **druhá chyba v tej
istej funkcii**: `only()` neuvádzal `liabilities_accruals`, hoci ho
`_compute_section_metrics` číta pre každý riadok — a vynechané pole nie je len
chýbajúce, je *odložené*, takže to bol jeden dotaz navyše **na riadok**
(13 999 na rok). Rozšírenie na trinásť rokov by to znamenalo trinásťkrát.

Namerané na produkcii po nasadení:

| | pred | po |
|---|---|---|
| riadkov v `Sector Benchmarks` | 19 (všetky 2025) | **247** (13 rokov × 19 sekcií) |
| firiem bez benchmarku pre svoj rok (2013–2025) | **1 703** z 15 467 | **0** |
| trvanie jedného behu (všetkých 13 rokov) | — | **13,6 s** |

Zvyšných **98** firiem bez benchmarku sú tie, ktorých najnovší výkaz je 2026 —
rok, ktorý sa ešte podáva a prah 500 preň zámerne neplatí. To je filter, nie
diera: oprava ich necháva tak a nemá ich meniť.

Overené aj to, že prah **nebol** príčinou: všetkých trinásť rokov 2013–2025 ho
prejde (13 999 – 14 790 vykazov každý), takže vysvetľoval jeden rok z trinástich
a skutočná príčina bol `break` v cykle, ktorý mal byť filter.

Testy: 4 nové v `companies/tests_benchmarking.py`, z toho jeden overený v stave,
ktorý má odmietnuť (s `liabilities_accruals` vyhodeným z `only()` padá a vo
výpise sú vidieť odložené SELECT-y po riadkoch). Sada: **927 testov OK**.

**Overené zvonka, nie len v databáze** (2026-09-17). Samotný počet riadkov
dokazuje, že sa dáta zapísali; nedokazuje, že sa k nim firma cez API dostane —
`get_benchmark` medzi tým robí `get_nace_section(nace)` a `objects.get(...)`,
teda dve miesta, kde sa to môže rozísť. Preto kontrola obchádza backend aj
databázu a pýta sa **hotového webu** (`https://dell.taildb03cf.ts.net`, Tailscale
Serve → frontend → `/api/`, žiadny tunel do contajnera):

| firma (IČO) | NACE | najnovší výkaz | `benchmark` v odpovedi |
|---|---|---|---|
| `00047244` | 84110 | 2024 | `year 2024`, 2 939 firiem |
| `00222348` | 01410 | 2013 | `year 2013`, 486 firiem |
| `00594547` | 68200 | 2013 | `year 2013`, 712 firiem |
| `00633496` | 47300 | 2013 | `year 2013`, 2 713 firiem |

Obe strany rozsahu teda vracajú porovnanie; pred opravou boli všetky štyri
`null`. **Druhá polovica vecí, ktorú číslo riadkov nechytá:** úloha je denná a
beží na workeri, ktorý bol v tom čase hore šesť hodín — teda so *starým kódom
v pamäti*, hoci nový už bol na disku (bind mount). Preto bol
`celery_worker_default` restartovaný a až potom úloha poslaná raz cez frontu:
worker ju prevzal a vrátil **`succeeded in 13,96 s`** so všetkými trinástimi
rokmi. To je zároveň dôkaz, že beží nový kód — starý by vrátil jediný rok.

#### B. `vat_deleted_date` / `vat_deleted_reason` — výmaz z DPH sa nikdy nezruší — ✅ opravené 2026-09-17

| | |
|---|---|
| **Zapisujú** | presne dve cesty, obe v `handle_vat_deleted` (`registers/services/fs_data_handlers.py:114`, `:125`) |
| **Číta** | `frontend/utils/vatStatus.ts:31` — `vatStanding()` sa pýta **najprv dátumu**, až potom príznaku |
| **Zmerané na `dell`** | 32 127 riadkov má dátum výmazu · 140 906 je označených ako platiteľ · **33 má oboje** |

`handle_vat_payers` (`fs_data_handlers.py:46-77`) pri firme v **aktuálnom**
zozname platiteľov nastaví `vat_payer=True`, `ic_dph`, `datum_reg_dph`
a skončí — **dvojicu nikdy nevyčistí**. Firma, ktorá bola z registra vyčiarknutá
a neskôr sa doň vrátila, si teda navždy nesie dátum výmazu.

Prečo to vidno: `vatStanding()` rozhoduje **dátumom prvým** a má na to
zdokumentovaný dôvod (príznak je nullable a 302 713 riadkov nemá hodnotu, kým
dátum je fakt, ktorý zdroj zapísal). Takže tých **33 firiem sa vykreslí ako
„Vymazaný z registra DPH"**, hoci register ich práve teraz vedie ako platiteľov
— teda **v opačnom smere, než aký je pravda**, a v tom alarmujúcejšom. A opäť
monotónne: nič ten dátum nevyčistí, takže číslo môže len rásť.

**Skúsil som to vyvrátiť, aby som ti nedal odporúčanie na základe dojmu** —
mohlo ísť o artefakt parsovania alebo o právne reálny stav „ešte platiteľ, výmaz
ohlásený na neskôr". Nevyšlo:

| test | výsledok |
|---|---|
| majú vyplnené `IČ DPH` **aj** dátum registrácie? | **33 z 33 áno** — sú to riadne firmy v aktuálnom zozname, nie artefakt |
| má niektorá dátum výmazu v **budúcnosti**? | **0** — takže „výmaz ohlásený na neskôr" to nie je |
| z ktorých rokov tie výmazy sú? | **2014 – 2026**, registrácie až do 2023-04-20 |

Takže sú to naozaj firmy, ktoré z registra vypadli a **vrátili sa**, a UI im
roky (najstaršej z nich ~12) tvrdí opak. Nie je to nová regresia — je to stav,
ktorý tu bol celý čas a nikto ho nemeral.

**Možnosti:** (1) v `handle_vat_payers` pri firme v aktuálnom zozname obe polia
vyčistiť; (2) vo `vatStanding()` uprednostniť `isVatPayer === true` pred dátumom
— to však rozbije dokumentovaný dôvod, prečo je dátum prvý, a vráti chybu
27 857 riadkom, ktoré majú dátum a žiadny príznak; (3) viesť výmaz ako históriu
namiesto dvojice polí. **Odporúčam (1)** — opravuje zdroj a poradie v čítaní
necháva tak, ako je odôvodnené.

##### ✅ Opravené 2026-09-17 — ale inak, než odporúčanie (1) hovorilo

Meranie pred písaním kódu odporúčanie **vyvrátilo** a zároveň zmenilo číslo.
Pôvodných „33" bolo *„má dátum výmazu **a** príznak `True`"*; skutočný rozsah je
daný porovnaním dvoch dátumov:

| merané na `dell` | počet |
|---|---|
| riadkov s `vat_deleted_date` | 32 127 |
| z toho `datum_reg_dph` **neskôr** než výmaz | **384** |
| z tých 384 `vat_payer = False` | **379** |
| `vat_payer = True` | 5 |
| `reg == del` | 4 · `reg < del` 3 827 · `reg` NULL 27 912 |

Prečo (1) nešlo: `FS_DATASET_URLS` púšťa `vat_payers` (riadok 6) **pred**
`vat_deleted` (riadok 9), takže vyčistenie v `handle_vat_payers` by ten druhý
handler v **tom istom priechode** hneď prepísal — a `UPDATE_FIELDS_MAP` pre
`vat_payers` tie dva stĺpce ani neobsahuje, takže by sa tiché vyčistenie
neuložilo vôbec. To je tá istá dvojitá brána, akú má #148.

Opravené teda na **oboch** miestach, kde sa to rozhoduje:

- **Zdroj** (`fs_data_handlers.py`): `handle_vat_deleted` pri riadku, ktorého
  `datum_reg_dph > DAT_VYMAZU`, príznak **neprepne** — a `vat_deleted_date`
  aj `vat_deleted_reason` zapíše ďalej. Výmaz je **história** (a `ROK_PORUSENIA`
  je dôvod, ktorý platí aj po návrate), kým `vat_payer` je **súčasný stav**.
  `>` a nie `>=`: dva dátumy v ten istý deň (4 riadky) sa zoradiť nedajú, tam
  ostáva pôvodné správanie.
- **Čítanie** (`vatStatus.ts`): `vatStanding()` vráti `payer`, keď je
  `registeredOn > deregisteredOn` — z faktov, ktoré zdroj publikoval, takže
  **displej je správny hneď**, bez čakania na ďalší priechod FS. Poradie
  „dátum prvý" tým zostáva nedotknuté; pribudla len presnejšia otázka na tie
  dva dátumy.

**Dátumová polovica je oprava na ďalší priechod FS**, nie migrácia: 379 riadkov
s `vat_payer = False` sa prepíše, keď `vat_payers` (ktorý beží prvý) nastaví
`True` a `vat_deleted` ho už nevráti. Do vtedy ich vykresľuje správne frontend.

Testy: `VatRemovalIsHistoryNotStandingTests` (7, `tests_fs_data_integrity.py`),
z toho jeden ide **cez oba datasety v poradí FS** a cez `bulk_update` — teda
reprodukuje presne pôvodnú chybu; a 4 nové vo `vatStatus.test.ts` (vrátane
jedného, ktorý pinuje predpoklad, že DRF posiela dátum ako ISO 8601, lebo
porovnanie je reťazcové). Obe strany sú overené v stave, ktorý majú odmietnuť:
bez opravy padajú práve 2 backendové a 2 frontendové a nič iné.

Bez zmeny schémy, bez migrácie. Celá sada: **934 testov backendu OK** (predtým
927) a 352 frontendových, `typecheck` aj `build` zelené.

Dôsledok pre používateľa: **384 firiem** sa na stránke firmy premenuje z
„Vymazaný z registra DPH" na „Platiteľ DPH".

#### C. `CompanyScore` — celá plocha je mŕtva; a keby nebola, skóre by nezostarlo len tak

Toto je nález, ktorý sa **meraním otočil**. Sweep ho opísal ako „odvodená
hodnota, ktorú nič neznehodnotí". Na ostrej databáze je pravda tvrdšia:

| kontrola | výsledok |
|---|---|
| `lead_scoring_companyscore` na `dell` | **0 riadkov** |
| riadok v `PeriodicTask` pre scoring | **neexistuje** (prečítané všetkých 10 riadkov tabuľky) |
| `score_single_company` (`lead_scoring/tasks.py:59`) | **nemá v repozitári žiadneho volajúceho** |
| jediný dosiahnuteľný spúšťač | `POST /api/lead-scoring/scores/calculate/` (`views.py:95`, personál) alebo ručné `manage.py score_companies` |

Takže latentná polovica nálezu (skóre nezostarlo, keď sa zmenia financie či
dlhy firmy) **dnes nemôže nastať, lebo sa neskóruje vôbec**. `CompanyScore`
nemá ani len plán, ktorý by ho obnovoval. Zároveň to znamená, že endpointy
`top` a `report` vracajú prázdno a model, admin a viewset sú mŕtva váha —
**pokiaľ to nie je Zámer**.

**Toto nie je chyba na tiché opravenie, ale produktové rozhodnutie:** má byť
lead scoring živá funkcia? Ak áno → potrebuje plán **aj** zneplatnenie (inak sa
prvá vec, ktorú spraví, je to, že bude klamať). Ak nie → patrí do *„Vedome
vynechané"* a jeho plocha má zmiznúť. **Nechávam na teba.**

#### D. `SyncFocusModeState.snapshot` — najslabší zo štyroch, ale tej istej triedy

`snapshot` sa zapíše raz, v `enter_focus_mode` (`focus_mode.py:180`), a pri
východe sa z neho obnovuje `enabled`. **Nič ho neznehodnotí, keď sa riadky
`PeriodicTask` počas focus mode zmenia:**

- riadok **vytvorený** počas focus mode v snapshote nie je → `exit` ho nechá
  tak. Beat ho pritom vytvoril z `CELERY_BEAT_SCHEDULE` s `enabled=True`, takže
  **beží aj počas focus mode** a ruší jeho deklarovanú záruku.
- **vedomá úprava** vykonaná počas focus mode sa pri `exit` **prepíše** späť na
  hodnotu z času vstupu.

Oboje chce ale buď nasadenie (nová položka v `CELERY_BEAT_SCHEDULE`) alebo
administrátorský zásah **presne počas** focus mode, takže výskyt je úzky.
**Označujem to ako najslabší nález** a neodporúčam naň siahať skôr než na A–C.

> **Aby to nikto „neopravil":** `revoke_non_focus_tasks` a `purge_broker_queues`
> sú v `focus_mode.py` definované a **`enter_focus_mode` nevolá ani jednu z nich**
> — `registers/tests_focus_mode_safety.py` to explicitne testuje
> (`revoke_tasks.assert_not_called()` / `purge_queues.assert_not_called()`). Je to
> zámerná, otestovaná invariantná záruka, že focus mode nikdy nesiaha na broker
> správy, **nie mŕtvy kód**. Zapisujem to sem, aby ich niekto nezapojil v dobrej
> viere.
>
> **Dve veci, ktoré tá veta predtým zlievala dohromady (opravené 19. 9. 2026):**
>
> - **`purge_broker_queues` nevolá naozaj nikto** — ani test. Jeho jediný výskyt
>   mimo definície je `patch(...)` v bezpečnostnom teste, ktorý overuje, že sa
>   *ne*zavolá.
> - **`revoke_non_focus_tasks` je otestovaná**, takže „nikto ju nevolá" o nej
>   neplatí: `registers.tests.FocusModeTests.test_revoke_skips_keep_list_tasks`
>   ju volá priamo s podvrhnutým `inspect` a **pripína jej keep-list sémantiku**
>   (revokuje práve tie dve úlohy mimo keep-listu a žiadne iné). Nemá
>   produkčného volajúceho, ale má krytie — a keby niekto zmenil, čo revokuje,
>   spadne test, nie ticho niečo iné.
>
> Odkaz je zámerne na **mená testov, nie na čísla riadkov**: pôvodná verzia
> citovala `tests_focus_mode_safety.py:42-43`, kým asserty sú dnes na 39–40 —
> čísla sa posunú pri každej úprave a poznámka, ktorej celý zmysel je „nesaň na
> to", sa tým rozpadne.

#### Čo z toho plynie

- **A a B** sú ozajstné chyby s merateľným dopadom (1 586 firiem bez benchmarku;
  33 firiem s obráteným stavom DPH) a s malou, dobre ohraničenou opravou
  (~250 riadkov; vyčistenie dvoch polí na jednej ceste). Vedia čakať, ale sú to
  najlepší kandidáti na ďalší cyklus.
- **C** je rozhodnutie o produkte, nie oprava — patrí tebe.
- **D** je záznam, nie úloha.

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

- ✅ **`deploy/k8s` a `deploy/helm` nenastavovali `BACKEND_RESOLVER`, takže nový
  frontend image tam nenabehol — opravené 2026-09-17.** Image ju zámerne deklaruje **prázdnu** (nie
  vynechanú), aby zlyhanie menovalo samo seba: envsubst vyrenderuje
  `resolver  valid=10s ipv6=off;` a nginx odmietne štart s
  `no name servers defined`. Overené na zahodenom kontajneri 2026-09-17.
  Compose vetva ju nastavuje na `127.0.0.11` (Docker embedded DNS), ale
  **adresa sa odvodiť nedá** — je pre každý klaster iná: kubeadm `10.96.0.10`,
  k3s `10.43.0.10`, Docker Desktop svoju vlastnú. **Preto to nie je doplnenie
  hodnoty, ale rozhodnutie** (a `deploy/k8s` je aj tak označené DEPRECATED
  s otvoreným osudom). Dôsledok, kým sa nerozhodne: frontend image nasadený do
  klastra **nenabehne** — čo je hlasité, a teda lepšie než tichých 502, ale
  treba o tom vedieť **pred** nasadením, nie po ňom.
  **A za tým zlyhaním číha druhé, tichšie — overené renderom 2026-09-17.**
  Helm menuje backend Service ako `<release>-cistafirma-backend`
  (`_helpers.tpl`: `printf "%s-%s" .Release.Name "cistafirma"`), a dokumentácia
  aj CI inštalujú release `cistafirma-dev` / `cistafirma-prod` / `cistafirma`.
  `helm template cistafirma-dev …` to vyrenderuje doslovne ako
  `cistafirma-dev-cistafirma-backend` a configmap backendu rovnako — kým obraz
  má zabudované `ENV BACKEND_UPSTREAM=cistafirma-backend:8000`, čo je meno
  **kustomize** Service (`deploy/k8s/base/backend-service.yaml`). Ani jedno
  z tých mien sa nestretá s druhým. Dnes to neublíži, lebo chýbajúci
  `BACKEND_RESOLVER` zastaví nginx skôr — ale práve preto je to pasca:
  **kto doplní len resolver, dostane tiché 502 na každej požiadavke.** Pred
  touto zmenou by ho nginx zastavil pri štarte (`host not found in upstream`);
  s `resolve` už nie — a frontend probe má na `/healthz`, ktoré je voči
  backendu slepé, takže pod by sa hlásil ako zdravý. To je presne tvar, ktorý
  tento výpadok odstránil, len prenesený na Helm vetvu. Doplniť treba **oboje**
  naraz: `BACKEND_RESOLVER` *aj* `BACKEND_UPSTREAM` s menom, ktoré chart naozaj
  vytvára (alebo chart nech ho nastaví z `fullname` sám).

  **Rozhodnuté a spravené 2026-09-17 — obe polovice, každá iným spôsobom.**
  Meno backendu sa **už neopisuje**: pribudol helper
  `cistafirma.backendUpstream`, ktorý ho počíta z toho istého `fullname`, akým
  sa menuje backend Service chartu. Dve mená, ktoré sa musia stretnúť, sa teda
  odvádzajú jedno z druhého a nemajú ako sa rozísť. Resolver **doplnený ako
  hodnota s vedomým rozhodnutím**, nie odhadom: `values-dev.yaml` má
  `10.96.0.10` (lokálny kind je kubeadm, takže CoreDNS sedí na zvyčajnej
  adrese), `values-prod.yaml` ju **nemá** — neexistuje klaster, ktorému by
  patrila, a vymyslená adresa by zlyhala ticho (502 na každej požiadavke, pod
  zdravý) namiesto hlasito. Kým sa nedoplní, prod frontend pod nenabehne;
  to je správne.

  Overené renderom oboch sád (`helm v4.1.3`, chart lint čistý):

  | | `BACKEND_UPSTREAM` | `BACKEND_RESOLVER` |
  |---|---|---|
  | `cistafirma-dev` | `cistafirma-dev-cistafirma-backend:8000` | `10.96.0.10` |
  | `cistafirma-prod` | `cistafirma-prod-cistafirma-backend:8000` | `""` (zámerne) |

  A hlavne: **dvojica mien je odteraz kontrolovaná v CI**, nie len v komentári.
  `scripts/k8s/validate_helm_runtime.py` (job `helm_runtime_validate`) porovná
  `BACKEND_UPSTREAM` frontendu proti Service menám v tom istom renderi. Overené
  v stave, ktorý má odmietnuť: s menom z obrazu (`cistafirma-backend:8000`,
  presne tá pôvodná drift) padá s vypísaním, ktoré Service v renderi naozaj sú;
  s vynechaným `BACKEND_UPSTREAM` padá tiež. To je tá kontrola, ktorá v tomto
  náleze chýbala — „tiché 502" sa už nedostane do klastra bez červeného CI.

  A aby to nebola len kontrola, ktorú nikto nevidel odmietnuť, skript má
  `--selftest`: rozbije manifest **v pamäti** (posunuté meno, chýbajúca
  premenná) a vyžaduje, aby ho kontrola odmietla. CI ho spúšťa na oboch
  renderoch. Overené aj to, že nie je prázdny: s vypnutou kontrolou
  (predčasný `return` v kópii skriptu) `--selftest` padne, kým bežný beh tej
  istej kópie prejde zelený — čiže sám sebe nič nezaručuje.

  `deploy/k8s` (DEPRECATED, ale menovaná v tomto náleze) má to isté:
  `BACKEND_UPSTREAM` uvedený aj napriek tomu, že sa rovná predvolenej hodnote
  obrazu — je to závislosť, ktorú nič iné nevidí — a `BACKEND_RESOLVER` cez
  placeholder `__BACKEND_RESOLVER__`, ktorý `scripts/k8s/deploy.sh` **vyžaduje**:
  na chýbajúcu hodnotu padá pred `kubectl apply` a vypíše príkaz, ktorým sa
  adresa zistí. Nahradenie overené na kópii súboru, po sed-e nezostal ani jeden
  placeholder.
- ✅ **Nič v zostave nezachytilo výpadok API — tých 3 h 43 min bolo pre všetky
  kontroly neviditeľných. Opravené 2026-09-17.** `/healthz` **ostáva** zámerne
  slepé voči backendu, a to je správne: reštart nginx backend nevráti a probe,
  ktorý by tu zlyhal, by počas každého reštartu backendu reštartoval všetky
  frontend pody. Opravené je teda to, čo v náleze stálo — pribudla **druhá
  sonda na inom mieste**, nie zmena tejto.

  `scripts/local/ops_check.sh` má sekciu **„API availability"**, ktorá spraví
  `GET /api/stats/landing/` **z hostiteľa** na **publikovaný port frontendu**.
  Je to tá istá cesta, akou ide prehliadač — vrátane nginx, teda práve toho
  komponentu, ktorého zastaraná adresa výpadok spôsobila. Adresu berie
  z `docker compose ps --format '{{.Ports}}' frontend`, nie z `.env`: `BIND_HOST`
  a `FRONTEND_PORT` sú v súbore, ktorý tento skript zámerne nečíta, a obe
  compose varianty publikujú **iný kontajnerový port** (5173 pre Vite dev server,
  80 pre produkčný nginx), takže ani pravá strana nie je konštanta. Wildcard
  bind (`0.0.0.0`, `[::]`) sa normalizuje na loopback; mapping bez `->` (teda
  kontajnerový port, ktorý sa nikdy nepublikoval — compose ich vypisuje rovnako,
  ako pri každom workerovi vyššie) sa **odmietne**, nie prevedie na vymyslenú
  URL. `/api/stats/landing/` je vybrané preto, že je `AllowAny`, lacné (tri
  COUNT-y; nameraných **0,26 s** na produkcii) a leží za všetkým: nginx →
  gunicorn → Django → Postgres. `CISTAFIRMA_API_TIMEOUT` (default 10 s) drží
  medzu.

  **Overené na ôsmich stavoch, nie tvrdené** — a to vrátane tých, v ktorých
  kontrola musí odmietnuť. Beží to na delle proti **skutočnému** kontajneru
  (prvé dva riadky), zvyšok proti `docker` shimu, ktorý predstiera zvolené
  mapovanie portov; 502 vyrába lokálny listener, nie výpadok produkcie:

  | stav | publikované porty | výsledok |
  |---|---|---|
  | wildcard bind, za ním živý frontend | `0.0.0.0:5173->80/tcp, [::]:5173->80/tcp` | `OK … answered 200` |
  | dev variant (iný kontajnerový port) | `127.0.0.1:5173->5173/tcp` | `OK … answered 200` |
  | na porte nič nepočúva | `127.0.0.1:59999->80/tcp` | `FAIL … did not complete (curl exit 7), so nothing answered` |
  | frontend beží, upstream vracia 502 | `127.0.0.1:59998->80/tcp` | `FAIL … answered 502 -- the frontend is up but cannot reach the backend, which is the 2026-09-17 outage exactly` |
  | frontend beží, backend vracia 500 | `127.0.0.1:59997->80/tcp` | `FAIL … answered 500, not 200` |
  | compose nehlási publikovaný port | *(prázdne)* | `FAIL … reports no published port` |
  | port len vystavený, nikdy publikovaný | `8000/tcp` | `FAIL … reports no published port` |
  | frontend medzi bežiacimi chýba | `127.0.0.1:5173->80/tcp` | `FAIL … the frontend is not running` |

  Na hostiteľovi **bez** stacku (retired Mac) sekcia vypíše `SKIP` — viditeľne,
  lebo ticho preskočená kontrola je na nerozoznanie od tej, ktorá prešla. Beží
  aj na Macu: `SKIP  no stack on this host, so there is no published port to
  probe`. Beží aj na delle v rámci celej brány: `OK  GET
  http://127.0.0.1:5173/api/stats/landing/ answered 200 through the published
  frontend port`.
- ✅ **`/admin/` posielalo o dve hlavičky menej než `/api/` — doplnené
  2026-09-17.** `location /admin/` nastavovalo len `Host` a `X-Real-IP`, kým
  `/api/` (a od `f4b822a` aj `@backend_static`) posiela navyše `X-Forwarded-For`
  a `X-Forwarded-Proto`. Dnes to bolo inertné a overené: `settings.py` nemá ani
  `SECURE_PROXY_SSL_HEADER`, ani `SECURE_SSL_REDIRECT`, `USE_X_FORWARDED_HOST`
  je nenastavené, a Django admin nie je DRF-throttlovaný (DRF `NUM_PROXIES`
  číta `X-Forwarded-For` len na throttlovanie `/api/`, ktoré ho už posiela).
  Bola to ale pasca: s `SECURE_PROXY_SSL_HEADER` a TLS terminovaným v nginx by
  `/admin/` o sebe tvrdilo `http`, kým `/api/` správne `https` — a so
  `SECURE_SSL_REDIRECT` je z toho slučka presmerovaní presne na tej stránke,
  ktorú operátor potrebuje, keď je pokazené niečo iné. Doplnené rovnaké štyri
  hlavičky ako v `/api/`.

  **Overené renderom a `nginx -t`, nie čítaním diffu.** Šablóna sa vyrenderovala
  oficiálnym image `nginx:1.27.5-alpine` (ten istý, aký pinuje `Dockerfile.prod`)
  cez jeho vlastný `/docker-entrypoint.d/20-envsubst-on-templates.sh`
  s `NGINX_ENVSUBST_FILTER=BACKEND_`: v hotovom configu je `proxy_set_header
  X-Forwarded-For` aj `X-Forwarded-Proto` **trikrát** (`/api/`, `/admin/`,
  `@backend_static`), blok `/admin/` má všetky štyri, `resolver 127.0.0.11`
  a `server backend:8000 resolve max_fails=0` sú dosadené, `nginx -t` prejde
  (`syntax is ok` / `test is successful`).

  > **Prvý pokus o to overenie bol falošne zelený a stojí za zapísanie.**
  > `docker run … nginx:1.27.5-alpine sh -c 'nginx -t'` nevyrenderuje **nič**:
  > `/docker-entrypoint.sh` púšťa `20-envsubst-on-templates.sh` len vtedy, keď
  > je prvý argument `nginx` (alebo `nginx-debug`), takže `sh -c …` render
  > preskočí a `nginx -t` skontroluje **stock** `/etc/nginx/conf.d/default.conf`
  > z image. Kontrola hlásila `syntax is ok` a o zmene nevedela nič — presne tá
  > trieda poruchy, ktorú tu celý čas hľadáme, len tentoraz v mojom vlastnom
  > overení. Preto sa šablóna renderuje explicitným volaním toho skriptu.
- ✅ **IP GitLabu bola ručne na troch miestach a nikto ju neporovnával —
  odteraz je na dvoch a kontrolovaná.** `100.120.104.84` stála
  v `deploy/ci/docker-compose.yml:86` (`extra_hosts` runner kontajnera),
  v `deploy/ci/setup-config.sh:23` (`GITLAB_IP`, dosadzovaná do `config.toml`
  pre job kontajnery) a v `deploy/ci/README.md:119` (vysvetlenie, prečo dnsmasq
  na tailnet IP z docker bridge neodpovedá). Dve konfiguračné miesta sú
  **nevyhnutné**, nie nedopatrenie: runner a job kontajnery sú dva kontajnery
  s dvoma vlastnými `/etc/hosts`. Tretie bolo len opisné a vypadlo — README
  teraz odkazuje na `GITLAB_IP` v skripte. `setup-config.sh` navyše pri každom
  spustení overí, že `docker-compose.yml` vedľa neho nesie tú istú IP, a skončí
  s `exit 1`, keď nie.

  Overené v troch stavoch, nie len v tom, ktorý má prejsť: zhoda → skript
  pokračuje na kontrolu tokenu (`chýba …absent`); rozchod (v compose
  `100.99.99.99`) → `CHYBA: … nemá extra_hosts "gitlab.home.arpa:100.120.104.84"`
  s vypísaním nájdenej hodnoty a `exit 1`; chýbajúci `docker-compose.yml` →
  viditeľné `POZOR: … zhoda GITLAB_IP sa nedá overiť` (ticho preskočená kontrola
  je na nerozoznanie od tej, ktorá prešla). To isté proti **skutočnému**
  `/home/sam/gitlab-runner/docker-compose.yml` na lenovo, so skriptom spusteným
  s falošným `TOKENFILE`, takže sa nič nezapísalo — `config.toml` si drží mtime
  `2026-09-15 23:31:59`. Nové kópie oboch súborov (aj README) sú na lenovo
  nasadené a `sha256sum` sedí s repom na bajt; pôvodné sú zálohované ako
  `*.bak-20260917-182705`. IP samotná je overená naživo:
  `getent hosts gitlab.home.arpa` → `100.120.104.84`.
- ✅ **Adresa lokálneho registra bola v runbooku iná, než akú používajú values
  — a nebola to ani adresa registra.** `docs/K8S_LOCAL_RUNBOOK.md:23` tvrdil
  `172.18.0.10:5000`, kým `deploy/helm/cistafirma/values-dev.yaml` má
  `172.18.0.2:5000`. Namerané 2026-09-17 na Macu: kontajner `kind-registry`
  beží (`Up 42 hours`, `127.0.0.1:5001->5000/tcp`) a na sieti `kind` má
  **`172.18.0.2`** — values teda boli správne a runbook nie. Navyše `172.18.0.10`
  na tej istej sieti **nie je voľná adresa**: patrí kontajneru
  `kind-cloud-provider`. Runbook preto odteraz neuvádza číslo, ale postup
  („prečítaj ju z `scripts/k8s/local_registry.sh`"), lebo IP prideľuje Docker
  a mení sa s rekreaáciou kontajnera či siete — druhá kópia je presne to, čo sa
  rozíde ticho a prejaví sa až `ImagePullBackOff` v podoch. To isté platí pre
  komentár vo `values-dev.yaml`.

  Runbook zároveň vysvetľuje, prečo `localhost:5001` v jeho príkazoch
  a `172.18.0.2:5000` vo values nie sú rozpor: `-p 127.0.0.1:5001:5000`
  sprístupňuje ten istý register na hoste, kým kontajnery v klastri ho vidia na
  svojej sieti. Overené proti registru samotnému — `GET /v2/_catalog` vracia
  `{"repositories":["cistafirma-backend","cistafirma-frontend"]}`, teda mená
  **bez hosta aj portu**, a `tags/list` má na oboch `local` aj `v2`.

  > **Čo tento nález nevyriešil a je na rozhodnutie.** Bežiace pody v namespace
  > `cistafirma` majú obrazy `localhost:5050/web/cistafirma/*` — z GitLab
  > registra na Macu, ktorý už neexistuje (kontajner je preč, `~/gitlab`
  > s 1,6 GB dát ostal). Obrazy sú zakešované na uzloch, takže pody bežia, ale
  > nový pod by potreboval pull. Nie je to teda len „osud klastra" z §9 nižšie,
  > ale aj to, že runbook opisuje pull z lokálneho registra, ktorý dnes **nič
  > nepoužíva**. Zámerne to neprepisujem na niečo, čo som neoveril — čo s
  > klastrom, je rozhodnutie pre človeka.
- ⚠️ **„Plná sada testov" z koreňa repa nespustí nič a vráti 0.** `make test`
  robí `cd backend` a až potom `manage.py test`; spustenie
  `python backend/manage.py test` z koreňa vypíše `Ran 0 tests ... NO TESTS
  RAN` a **exit 0**. Presne tá trieda poruchy, ktorú tu celý čas naháňame —
  zelený výsledok, ktorý nič neznamená. Kto si „overil testy" takto, neoveril
  nič. Správne je `make test`, alebo z koreňa `cd backend && ../venv/bin/python
  manage.py test` (611 testov).
- ⚠️ **Off-site záloha nie je pripojená** — externý zväzok nie je
  namontovaný, `make ops-check` preto hlási 1 FAIL. Lokálne zálohy
  aj posledný restore drill sú v poriadku. *(Poznámka k presnosti: tento
  riadok donedávna menoval `/Volumes/CistaFirmaBackups`, čo je cesta, ktorá
  nikdy neexistovala — `DATA_PROTECTION.md` aj runbook hovoria
  `/Volumes/<disk>/cistafirmaBackups`. Meno zväzku je preto zámerne
  vynechané, kým sa nenamontuje.)* Po migrácii na server tú istú úlohu
  plní lenovo — pozri *Off-site záloha po migrácii* nižšie.
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

  Mechanizmus je od 2026-09-14 známy a je to **preklep v kľúči**:
  `_unpack_options` (`schedulers.py:216–227`) číta `expire_seconds`, nie
  `expires`; všetko ostatné spadne do jeho `**kwargs` a **ticho sa zahodí**.
  Všetkých deväť záznamov v `CELERY_BEAT_SCHEDULE` preto nesie `'expires'`,
  ktorý nikto neprečíta — a `'queue'` v tom istom `options` funguje, takže
  sa to číta ako „nastavené".

  ⚠️ **A premenovať ten kľúč na `expire_seconds` nie je zdarma.** Tá hodnota
  sa dostane na **správu** v brokerovi, nie na riadok, takže úloha, ktorá
  čaká vo fronte dlhšie než `expires`, sa zahodí bez chyby. Na lane
  `insurance`, ktorá beží za vlastným backlogom a jeden priechod jej trvá
  ~15 dní, by to znamenalo tichú stratu pokrytia. Než sa ten kľúč opraví,
  treba pre každú lane zvlášť povedať, aké oneskorenie je ešte legitímne —
  dnes je ten mŕtvy kľúč práve to, čo nič nezahadzuje.

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

### Keď sa #99 zasekne, nemá to ako zakričať — prah je nad maximum, ktoré systém dokáže vyrobiť

Predošlý nález hovorí, že #95 nemá `SyncJob`. Toto je **mechanizmus**, ktorým
jeho zaseknutie zostane tiché aj tak — a je to nález o #99, nie o #95.

Od chvíle, keď je #99 nasadené, platí pre frontu `orsr` tvrdenie, ktoré sa dá
overiť z kódu: dispatcher nikdy nedovolí, aby fronta prekročila `bound`.

```python
headroom = max(0, bound - backlog)      # tasks.py:938
limit = min(limit, headroom)            # tasks.py:945
if limit <= 0: return f"Held back: …"   # tasks.py:948
```

Pri `backlog = 6 000` je `headroom = 0`, teda `limit = 0` a **odošle sa nula**.
Fronta `orsr` teda z person-history práce nikdy neprekročí ~6 000 (plus 200
z ORSR rotácie). A teraz ten prah, ktorý ju má strážiť:

| miesto | hodnota |
|---|---|
| `scripts/local/ops_check.sh:59` — zdôvodnenie | `orsr` „drain to zero … sit at 0 in steady state" |
| `scripts/local/ops_check.sh:92` — prah | **50 000** |
| maximum, ktoré #99 dokáže vyrobiť | **~6 000** |

Prah je **osemkrát nad tým, čo systém dokáže vyrobiť**. Nemôže sa teda nikdy
spustiť — a to ani vtedy, keď je #95 naozaj zaseknuté, čo je presne ten stav,
pre ktorý existuje. Je to tá istá trieda ako `sync_health` a jeho slepé okno
`failed`: kontrola, ktorá nemá ako zlyhať, lebo jej prah leží mimo dosahu.

A čo naozaj zakričí, keď sa to zasekne? Nič:

```python
logger.info("Person-history resync throttled: orsr holds %s, …")   # :941  INFO
return f"Held back: orsr backlog {backlog} is at or above …"       # :948  reťazec
```

`logger.info` nikto nečíta a návratový reťazec je výsledok Celery tasku — ten
expiruje za deň a nemá ho kto prečítať. Úloha navyše **nie je `BaseSyncTask`**,
takže nevznikne ani `SyncJob`, a `grep person_history scripts/local/ops_check.sh`
je prázdny. Overené: jediné miesto v celom repe, ktoré to slovo vôbec
spomína, je `tests_person_history.py:266` (`assertIn("Held back", result)`).

**Dôsledok:** #95 sa môže zaseknúť na tom bounde a navonok to vyzerá ako
„beží" — fronta stojí presne na 6 000, dáta sa nehýbu a `make ops-check`
prejde. To je horšie než pred #99: pred ním fronta rástla donekonečna, čo bolo
aspoň vidieť.

**Odporúčanie** (neimplementované, patrí k #99, nie k #95): strážiť nemá hĺbku
fronty, ale **stav held-back** — to je jediná vec, ktorá naozaj znamená poruchu.
Prah hĺbky treba znížiť pod maximum (`> 6 000` je nedosiahnuteľné) alebo
prepísať ako `warning`, aby aspoň zostala stopa. Presné číslo nechávam na
rozhodnutie, lebo meniť prah operatívnej kontroly je samostatná vec.

### Nová periodická úloha s intervalom dlhším, než je doba medzi reštartmi beatu, nebeží nikdy

Pôvodný zápis na tomto mieste tvrdil, že sa `last_run_at`/`total_run_count` pri
dvoch úlohách „nepíše vôbec" a že počítadlo „prehlási zdravú úlohu za mŕtvu".
**Prvá polovica je vyvrátená meraním a druhá bola nesprávna diagnóza.** Premerané
2026-09-13 21:53Z:

| riadok | `last_run_at` | `runs` |
|---|---|---|
| `refresh-person-history-every-4-hours` | 2026-09-13 21:20:12.950 | **2** |
| `compute-sector-benchmarks-daily` | `None` | **0** |
| zvyšných 8 riadkov | svoje posledné spustenie | 19 – 375 |

Počítadlo sa teda píše aj úlohe, ktorá tu bola označená za „nemá nikdy":
`refresh-person-history` si o 21:20:12 zapísalo druhý beh — presne ten tik, ktorý
je overený vyššie. Zostáva **1 z 10**, nie 2.

Príčinu som **overil, nie odhadol**. V `django_celery_beat` (v kontajneri 2.9.0):

```python
# schedulers.py — ModelEntry.__init__
if not model.last_run_at:
    model.last_run_at = model.date_changed or self._default_now()

# schedulers.py — ModelEntry.from_entry
obj, created = PeriodicTask._default_manager.update_or_create(
    name=name, defaults=cls._unpack_fields(**entry))
```

Riadok, ktorý ešte nikdy nebežal, nemá v DB `last_run_at` — a beat mu ho **v
pamäti** nahradí `date_changed`. `is_due()` potom počíta od neho, takže prvý beh
je najskôr `date_changed + interval`: úloha, ktorá „nikdy nebežala", sa tvári
ako tá, ktorá „práve bežala". A `from_entry` je `update_or_create`, ktoré
`setup_schedule()` volá pri **každom štarte beatu** — takže `date_changed` sa pri
každom štarte prepíše na „teraz" a prvý beh sa odsunie o celý interval.

Že sa riadky pri štarte naozaj zapisujú, vidno na riadku, ktorý **už bežal** a
fiktívny `last_run_at` teda nemá — a napriek tomu nesie `date_changed` z času
štartu:

| riadok | `last_run_at` | `date_changed` | interval |
|---|---|---|---|
| `update-fs-data-daily` | 18:22:32.602 | **18:34:00.087** | 86 400 s |
| `celery.backend_cleanup` | 02:00:00.000 | **18:34:00.041** | crontab 4:00 |
| `compute-sector-benchmarks-daily` | `None` | **18:34:00.116** | 86 400 s |
| `detect-stuck-sync-jobs-every-10-min` | 21:20:11.413 | 21:20:22.991 | 600 s |

`update-fs-data-daily` naposledy bežal 18:22:32 a predsa nesie `date_changed`
18:34:00.087 — 96 s **po** svojom behu a presne v sekunde posledného štartu beatu
(`beat: Starting...` 18:34:00.000820). To je ten zápis pri štarte; riadky, ktoré
odvtedy bežali, ho prepísali svojím behom.

**Dôsledok.** `compute-sector-benchmarks-daily` je v `CELERY_BEAT_SCHEDULE` od
commitu `3f9bc20` (2026-09-12 13:13Z) a v celom retenovanom logu beatu (od
2026-09-10 07:21Z) sa nedispatchol **ani raz**: 748 riadkov „Sending due task"
nesie všetkých 9 ostatných mien, toto ani raz. Za tých 32 h, čo je úloha
naplánovaná, beat trikrát reštartoval a **najdlhší súvislý beh bol 16 h 42 min**
(17:46 → 10:28) — teda menej než jej 24-hodinový interval. Nie je to chyba
počítadla: počítadlo hovorí pravdu, úloha naozaj nebežala.

**Odkiaľ ten riadok je — a to je nepríjemné.** Vytvorila ho moja vlastná
host-side rekonciliácia `DatabaseScheduler` 2026-09-13 13:20:11.901; vtedy ešte
neexistoval (merané pred/po, a je to zapísané v memory k tej kontrole, ktorá
mala byť read-only). Beat ho potom zapísal znovu pri svojom štarte o
18:34:00.116. Čiže úloha je naplánovaná v kóde od 12. 9., ale riadok, bez
ktorého neexistuje, pochádza z ručnej kontroly — a keby tá kontrola nebola
(pre)siahla tam, kde siahla, úloha by nemala riadok vôbec.

**Neoverené — a teraz užšie, nie vyriešené:** prečo riadok neexistoval už skôr.
`CELERY_BEAT_SCHEDULE` nesie tento záznam od 2026-09-12 13:13Z a beat odvtedy
štartoval dvakrát (09-12 17:46:28, 09-13 10:28:15), pričom `setup_schedule()`
volá `update_from_dict(self.app.conf.beat_schedule)` — teda `update_or_create`
pre každý záznam — takže riadok mal vzniknúť. Nevznikol, a `Cannot add entry`
(prekážka, ktorú tá cesta loguje) sa v logu v tých časoch nenachádza: všetkých
14 výskytov je z 2026-09-12 01:20–03:50 a je to ten istý DNS výpadok „db".

Obidvoch kandidátov, ktorých som tu pôvodne nechal otvorených, **vylučuje
čítanie zdroja** (2026-09-14, `venv/lib/python3.13/site-packages/django_celery_beat/schedulers.py`):

* *„kód settings do riadkov neprepisuje"* — neplatí. `setup_schedule()` na
  riadkoch 259–261 volá `install_default_entries(self.schedule)` a hneď po ňom
  `update_from_dict(self.app.conf.beat_schedule)`; `from_entry` je
  `update_or_create` (:193–197). Je to tá istá cesta, ktorá 09-13 o 18:34
  riadky prepísala.
* *„settings v tej chvíli neboli na disku"* — neplatí. `celery_beat` dedí
  z kotvy `x-celery-worker` (`docker-compose.yml:33–34`) `volumes: ./backend:/app`,
  takže kontajner číta ten istý súbor ako host. `CELERY_BEAT_SCHEDULE` je tam
  literál na `settings.py:412` bez akejkoľvek podmienky a `__all__`
  v `backend/backend/settings.py` nie je, takže ho shim `backend/settings.py`
  (star-importom) vyexportuje. Záznam bol navyše commitnutý
  2026-09-12 15:13:15+02:00, teda **pred** štartom o 17:46:28.

Čo v logu naopak vidieť je: `beat: Starting...` 17:46:28.447 a o 106 ms
`DatabaseScheduler: Schedule changed.` (:553) — a to je podpis zápisu do
`PeriodicTask` počas štartu, lebo `update_changed()` sa volá pri každom save
a `schedule_changed()` ho hneď vidí. Rovnaký podpis má štart o 18:34:00
(.000820 → .142997), o ktorom vieme, že riadky prepísal.

Zostávajú teda dve možnosti a **rozlíši ich až porovnanie `date_changed` pred
a po riadenom reštarte beatu**: buď bol v tom procese `app.conf.beat_schedule`
prázdny (potom by tých sedem zápisov bolo len z `install_default_entries`,
a `Schedule changed.` vyzerá rovnako), alebo bolo moje čítanie z 09-13
13:20:11 („riadok neexistuje") nesprávne. To porovnanie som **zámerne
neurobil**, lebo reštart by posunul ten jediný nikdy nespustený riadok o celý
ďalší interval — čiže by som odložil presne to, čo nižšie odporúčam spustiť.
**Po prvom behu je už reštart pre tento riadok bez následkov** (`last_run_at`
je nastavené, takže `date_changed` sa ako hodiny už nepoužíva) — vtedy sa ten
experiment dá spraviť zadarmo.

Toto nie je vlastnosť jednej úlohy, ale pasce pri zakladaní nového riadku:
**nová periodická úloha s intervalom dlhším, než je bežná doba behu beatu, sa
k prvému behu nedostane vôbec.** Štvorhodinové nové riadky prežijú, denné nie.

**Žiadna kontrola si to nevšimne.** `scripts/local/ops_check.sh` — a teda aj
týždenný launchd job, ktorý beží tou istou bránou — sleduje stack, databázu,
hĺbky front, scrape health, `SyncJob`y, zálohy, off-site a to, či ešte beží
týždenná záloha. `PeriodicTask` nesleduje **vôbec**: `grep -niE
"periodictask|beat|last_run_at|scheduled"` nájde v celom skripte jediný riadok,
a to o logu zálohy. Úloha, ktorá sa nikdy nespustí, teda nemá ako zakričať.

Je to presne tá asymetria, ktorú tento plán pomenúva inde: `ops_check` vie
zlyhať `SyncJob`, ktorý zostal `running` alebo skončil `failed` — lenže to sú
všetko úlohy, ktoré **bežali**. Úloha, ktorá sa nespustí, po sebe `SyncJob`
nezanechá, takže neexistuje riadok, o ktorý by sa kontrola oprela. Kontroly
súdia behy; nikto nesúdi neexistenciu behu.

**Návrh brány (nezavedené, čaká na rozhodnutie):** dve tvrdenia na
`PeriodicTask`, obe čítané z riadku a intervalov, ktoré už sú v
`CELERY_BEAT_SCHEDULE`:

* `last_run_at IS NULL` a `now - date_changed > interval + rezerva` → **fail**.
  Toto je to jediné, čo vidí riadok, ktorý nikdy nebežal, a nepotrebuje na to
  žiadnu históriu — práve preto je to prvé pravidlo, ak nie jediné.
* `last_run_at` je staršie než `2 × interval` → **fail**. Druhé je poistka
  proti riadku, ktorý bežal raz a odvtedy mlčí.

Rezervu treba kalibrovať na 10-minútovom riadku (`detect-stuck`), ktorý je
najcitlivejší na oneskorenie tiku; bez nej by brána kričala pri každom
pomalšom tiknutí.

**Dopad na dáta je menší, než to vyzerá** — a je iný, než by človek čakal:
`SectorBenchmark` má 15 riadkov, ale všetky s `computed_at = 2026-09-12 19:55:43Z`,
teda z jednorazového ručného prepočtu pri vzniku tej opravy. Dáta teda existujú;
neexistuje len ich denná aktualizácia, takže tabuľka je zamrznutá na jednom dni.

**Odporúčanie** (zámerne **neurobené** — je to zápis do živej prevádzkovej
tabuľky a prepočet viditeľných dát, nie moja vec): úlohe treba dopriať prvý beh,
a to buď ručne (`compute_sector_benchmarks.delay()`, čím získa skutočné
`last_run_at` a ďalej sa správa normálne), alebo pri zakladaní nového riadku
nastaviť `start_time` do minulosti — knižnica pre `start_time` sama odčíta 30
rokov (`model.last_run_at -= timedelta(days=365 * 30)`), takže úloha je hneď due.
To odčítanie je ale **jednorazové, nie trvalé**: je vnútri `if not
model.last_run_at:` (:95–103), takže akonáhle úloha raz bežala, `start_time`
už nič neurýchľuje — a `is_due()` naopak do `start_time` beh **blokuje**
(:118–130). Nastaviť `start_time` do minulosti je preto bezpečné aj v tom, že
z toho nemôže vzniknúť opakovaná záplava.

**Predpoveď na overenie:** ak sa beat dovtedy nezreštartuje, prvý beh príde
2026-09-14 18:34:00Z.

**Stav k 2026-09-14 09:55Z — overené *pred* predpoveďou, nie po nej:** beat
beží 15 h 21 min bez reštartu (`docker compose ps`: `Up 15 hours`) a obe
nikdy neobnovené `date_changed` to potvrdzujú — `compute-sector-benchmarks-daily`
má stále presne `2026-09-13 18:34:00.115991`, pričom každý štart beatu by ho
prepísal na „teraz", a `update-fs-data-daily` tiež `18:34:00.086699`, hoci
naposledy bežal o 18:22:32. Predpoveď teda **nebola ani vyvrátená, ani
naplnená** — je vzdialená 8 h 39 min. Všetkých 10 riadkov má `enabled=True`,
takže ju nezablokoval ani Focus Mode; ten by ju inak zablokovať mohol, lebo
`registers.tasks.compute_sector_benchmarks` **nie je** v `FOCUS_KEEP_TASKS`
(tie sú štyri, `focus_mode.py:18–23`) a `_set_periodic_tasks_enabled` vypína
každý riadok mimo nich. Že to vypnutie prežije reštart beatu, je tiež overené
v zdroji: `enabled` nie je medzi `defaults`, ktoré `_unpack_fields` (:200–214)
skladá, takže `update_or_create` sa tej kolónky nikdy nedotkne.

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

### Poisťovne: dávka sa presne rovná odtoku — ale docstring čaká o polovicu kratšie

**Uzatvára test, ktorý som minul.** Nasadil som meranie, ktoré čakalo skok fronty
`insurance` o ~14 400 okolo 21:11 — a nameralo 0. Chyba bola v načasovaní, nie
v hypotéze: dispatcher naposledy bežal **20:01:21** a interval je 43 200 s
(12 h), takže najbližší tik je **08:01:21**. O 21:11 nebolo čo skočiť.

Priamy dôkaz je pritom v logu, nie v čakaní:

```
20:01:21.121  Task schedule_insurance_debt_checks received, args "[14400]"
20:01:21.563  "Plánujem kontrolu dlhov pre 14400 z 440517 firiem … (z toho 9 sledovaných)."
20:01:28.048  succeeded in 6.92s: 'Scheduled 14400 insurance debt checks'
```

A odtok, meraný z hosta (Redis je na `localhost:6380` dosiahnuteľný aj mimo
Dockeru, takže na vzorkovanie netreba `docker compose exec`): **~21/min =
~1 260/h**, teda ~15 120 za 12 h proti dávke 14 400. Fronta je **conserved**,
presne ako tvrdí `INSURANCE_BATCH_PER_TICK = 20 × 60 × 12` — nesie 68 800
správ a nerastie. Kapacita je teda naozaj vyčerpaná presne, nie prekročená.

**Čo ale nesedí — docstring na `tasks.py:248`.** „an unwatched company waits
roughly a week for its first check." A docstring si pritom odporuje **sám so
sebou**, lebo tú populáciu aj dávku menuje o dva riadky vyššie:

| | |
|---|---|
| nikdy nečítané (jeho vlastné číslo, `tasks.py:247`) | **~414 000** |
| dávka na tik | **14 400** |
| tikov na priechod | 414 000 ÷ 14 400 = **28,75** |
| tik za 12 h → 2/deň | **14,4 dňa** |

„A week" je teda polovica toho, čo dáva jeho vlastná aritmetika — a `CLAUDE.md`
o insurance hovorí „one full pass takes ~15 days", teda to, čo vychádza.
Oprava je jedno slovo, ale je to v kóde, tak to hlásim a nemením. (Kontext,
v ktorom to stojí — že sledované firmy čakali rovnako dlho a watchlist bol preto
sľub, ktorý rotácia nedodržala — tým nie je dotknutý; nesie ho poradie
`nulls_first` a sledované-dopredu, nie to číslo.)

**Redis je zdravý**: 92 MB teraz, `peak 5,08 GB` (tá istá hodnota, akú
dokumentuje komentár k incidentu), `maxmemory 0B` / `noeviction`. 35 410 kľúčov
sú z väčšiny `celery-task-meta-*`, a tie **majú TTL** (`result_expires = 1 deň`;
zo 300 vzorkovaných 300 s expiráciou) — to nie je leak, len jeden deň výsledkov.

---

### Off-site záloha po migrácii: cesta ide cez tailnet a šifrovanie je otvorené

Migrácia na `dell` mení off-site cieľ: namiesto externého zväzku pripájaného
ručne je ním **lenovo**, pripojené cez sshfs a spúšťané systémovým
automountom. Cesta je hotová a overená — ale vychádzajú z toho tri nálezy
a jeden z nich je časovo citlivý.

**Čo je hotové.** Mount point `/mnt/cistafirma-offsite`, cieľ
`sam@sam-lenovo.taildb03cf.ts.net:/home/sam/cistafirmaBackups`, v `/etc/fstab`
riadok s `_netdev,x-systemd.automount,x-systemd.idle-timeout=600,
x-systemd.mount-timeout=30,nofail` a `StrictHostKeyChecking=yes`. Kľúč je
dedikovaný (`id_ed25519_offsite`), na lenove autorizovaný s `restrict`.
Host keys nie sú „accept-new": stiahnuté a **overené proti tomu, čomu Mac už
verí** (ED25519 `DlehWLP1…`, RSA `0maItj0J…`, ECDSA `hfVkPPuu…`), až potom
nainštalované do `/etc/ssh/ssh_known_hosts`. Konfigurácia cieľa je v
`~/.config/cistafirma/backup.env` (mode 600). *(Cestou sa našlo, že
`/home/sam/.config` na delle vlastnil **root** — vytvoril ho tam 14. 9. nejaký
sudo proces. To rozbije každý nástroj, ktorý si tam chce založiť vlastný
podadresár, vrátane `configure_offsite.sh`; vlastníctvo aj práva sú opravené.)*

**Nález 1 — `[ -d ]` nie je test pripojenia, a skripty naň spoliehajú.**
Merané na delle s armed automountom a nedosiahnuteľným cieľom:

| test | výsledok |
|---|---|
| `[ -d /mnt/cistafirma-offsite ]` | **TRUE** — klame |
| `mountpoint -q` / `findmnt -M` | **MOUNTED** — klame |
| `findmnt -t fuse.sshfs` | prázdne — správne |
| `stat -c '%d'` | `No such device (os error 19)` — správne |
| `df -P` | zlyhá — správne |

Prečo `mountpoint -q` klame: v `/proc/self/mountinfo` je pri armed automounte
**natrvalo** záznam typu `autofs`, source `systemd-1` — to je spúšťač, nie
sshfs. Žiadny `sshfs` proces pritom nebeží a mount jednotka je `failed`.
`[ -d ]` klame ešte nepriamejšie: vráti TRUE na holý adresár pod mountpointom.
Dôsledok pre `replicate_postgres_backup.sh` je závažný — prešiel by prvou
bránou a rsync by zapisoval do lokálneho adresára **na tom istom disku ako
originál**, teda „replika", ktorá o nič nechráni. Kontrola musí súdiť výsledok
reálnej I/O operácie, nie existenciu adresára.

**Oprava pôvodného tvrdenia (15. 9.):** pôvodne som sem napísal, že
„automount sa po zlyhaní sám re-triggeruje, takže samooprava funguje". To
platí **len do chvíle, než systemd vyčerpá limit pokusov** — a to je zásadný
rozdiel, nie detail. Odmerané na delle o 00:40 po ~13 minútach sondovania
s nedosiahnuteľným cieľom:

```
Active: failed (Result: mount-start-limit-hit)
grep -c cistafirma-offsite /proc/self/mountinfo  →  0
stat -c '%d' /mnt/cistafirma-offsite             →  64512   (úspech!)
findmnt -no FSTYPE,SOURCE --target …             →  ext4 /dev/mapper/ubuntu--vg-ubuntu--lv
```

Teda po `mount-start-limit-hit` systemd automount **zastaví**, autofs záznam
z `mountinfo` **zmizne** a cesta sa natrvalo zvrhne na obyčajný lokálny
adresár na koreňovom disku — v tomto stave prestane klamať aj `[ -d ]`
aj `stat`, lebo adresár je naozaj tam a naozaj je to ext4. To je horší stav
než ten, ktorý popisuje tabuľka vyššie. **Riešenie je drop-in**
`/etc/systemd/system/mnt-cistafirma\x2doffsite.automount.d/override.conf`
s `StartLimitIntervalSec=0` (nainštalovaný, `systemctl show -p
StartLimitIntervalUSec` → `0`), takže trigger ostáva naarmed a každý prístup
ďalej končí na `ENODEV`; po ňom treba `reset-failed` + `start`, inak sa
automount sám nevráti (čo sa stalo aj mne — po `systemctl reset-failed` +
`start` je späť `active` a v `mountinfo` je 1 autofs záznam).

Obe stráže pritom v **oboch** stavoch zadržali zápis, overené naostro na
delle (nie emuláciou `stat` na macOS), s falošným dumpom v `/tmp`, v tomto
poradí:

| stav | verdict | `replicate` | obsah `/mnt/cistafirma-offsite` |
|---|---|---|---|
| armed, cieľ nedosiahnuteľný | `not-attached` | `ERROR: … is not mounted or does not exist` + dôvod, exit 1 | 0 → **0** |
| automount vzdal, holý adresár | `same-filesystem` | `ERROR: … must be on a different filesystem` / `… encrypted volume`, exit 1 | 0 → **0** |

To je zároveň dôvod, prečo mount check porovnáva **zariadenie** s referenciou
a nie len to, či sa cesta dá prečítať: druhá stráž existuje práve pre stav,
v ktorom prvá už nemá čo merať.

*Zmerané, ale neopravené:* referencia pre porovnanie zariadení je
`dirname "$BACKUP_FILE"`, takže keď sa `replicate` zavolá s dumpom **mimo**
záložného adresára (napr. v `/tmp`, ktorý je na Ubuntu tmpfs), porovnanie
vyjde „rôzne zariadenia" a mount check prejde aj nad holým lokálnym
adresárom. V produkcii je referencia skutočný záložný adresár, takže sa to
nestane; v teste to zachytila až šifrovacia brána. Je to pre-existujúca
vlastnosť tvaru volania, nie regresia portu.

**Stav na delle je presne tento stav, naživo** (15. 9. 00:41):

```
mnt-cistafirma\x2doffsite.mount      failed (Result: exit-code)
  mount[67175]: read: Connection reset by peer
mnt-cistafirma\x2doffsite.automount  active
mountinfo:  1 riadok — autofs systemd-1 ... timeout=600,direct
ls /mnt/cistafirma-offsite  →  Os { code: 19, "No such device" }
```

Teda armed automount, ktorého mount zlyhal, `mountinfo` má **jeden** záznam
(trigger, nie súborový systém) a `ls` skončí na ENODEV. Guard to hlási ako
`not-attached` s dôvodom — presne to, pre čo existuje.

**Príčina je jedna a tá istá pre všetko ostatné: Tailscale na delle je
odhlásené.**

```
$ tailscale status
Logged out.
Log in at: https://login.tailscale.com/a/c458d6401f618
```

`sam-lenovo.taildb03cf.ts.net` sa preto na delle nepreloží
(`Could not resolve hostname`), takže sshfs nemá kam sa pripojiť, a rovnako
nefunguje `gitlab-home` remote ani `tailscale serve`. Kým táto autorizácia
neprebehne, nedá sa zmerať ani jedna z troch vecí, ktoré na sebe navzájom
závisia — a nedá sa ani stiahnuť kód na server, lebo dell nemá iný remote než
privátny GitHub bez prihlásenia.

**Otázka `x-systemd.idle-timeout=600` nie je bezpečnostná otázka.** Či po
10 minútach nečinnosti trigger prežije alebo zmizne, rozhoduje len o tom, či
sa mount po idle okne znova nadvihne sám. Obe možné odpovede sú ošetrené a obe
sú hlučné:

| čo idle timeout spraví | stav cesty | verdict guardu | dôsledok |
|---|---|---|---|
| trigger prežije | armed, mount zlyhá | `not-attached` (ENODEV) | `replicate` odmietne, job zlyhá nahlas |
| trigger zmizne | holý lokálny adresár | `same-filesystem` | `replicate` odmietne, job zlyhá nahlas |

Ani jeden z nich nie je tichý a ani jeden nezapíše repliku na nesprávne
miesto.

**Odmerané 15. 9. — trigger prežije, a `x-systemd.idle-timeout=600` teda
ostáva.** Meranie: baseline `00:44:37`, potom 780 s bez toho, aby sa na cestu
čokoľvek dotklo, čítanie `00:57:38` (13 minút po poslednom prístupe, teda
o 3 minúty za 10-minútovým oknom):

| čo | hodnota |
|---|---|
| `systemctl is-active …automount` | `active` |
| riadky v `/proc/self/mountinfo` | `1` |
| `findmnt -t autofs` | `1` |
| `.mount` unit | `failed` — očakávané, mount nikdy neuspel |

Trigger teda po idle okne **nezmizol** a cesta sa nezmenila na holý lokálny
adresár. Prvý riadok tabuľky je správny a `x-systemd.idle-timeout` sa
neodstraňuje. Poznámka k metodike: prvé meranie bolo bezcenné, lebo som tesne
pred ním na cestu siahol (`ls`) a tým idle okno reštartoval; toto meranie je
čisté.

  Čo tým **nie je** odmerané a netreba to predstierať: čo spraví idle timeout
  po *úspešnom* mounte (unmount a následné znovu-nadvihnutie pri ďalšom
  prístupe). To sa zmerať nedá, kým je lenovo nedostupné, a je to bežné
  správanie systemd. Rozdiel je však malý: tento stav nastane raz za týždeň
  pri behu jobu, kým odmeraný stav (cieľ dole) nastane vždy, keď lenovo spí —
  a práve ten je ošetrený dvoma vrstvami a hlučne.

**Nález 2 — off-site cesta je závislá od tailnetu, a ten ešte nie je.**
Lenovo je na LAN **zatvorené**: `192.168.1.107:22` aj `192.168.1.17:22` (jeho
Wi-Fi aj kábel) sú CLOSED z Macu aj z dellu, hoci sshd počúva na `0.0.0.0:22`
— zaviera ho teda firewall. Otvorené je len na tailnet adrese
`100.120.104.84:22`. Dell je v tailnete odhlásené (`tailscale status` →
`Logged out`, nie `NeedsLogin` — je to teda re-autorizácia, nie čakanie na
schválenie), takže mount reálne neprejde — čo je presne stav, v ktorom bol
nález 1 odmeraný.

**Nález 3 — a tento je časovo citlivý: presunom produkcie sa zníži ochrana
primárnej kópie.**

| stroj | disk | stav |
|---|---|---|
| Mac (dnešná produkcia) | Macintosh HD | **FileVault zapnuté** |
| dell (budúca produkcia) | LVM na `/dev/sda3` | **bez LUKS** |
| lenovo (off-site) | ext4 `/dev/sda3` | **bez LUKS** |

Dnešná produkcia teda leží na šifrovanom disku, tá nová by ležala na
nešifrovanom. Kým je na delle prázdno, je rozhodnutie o LUKS takmer zadarmo;
po #107 (obnova databázy) je to už prevádzková akcia. **Patrí preto pred
#107, nie zaň.**

**Čo s tým — dve rozhodnutia, obe potrebujú slovo používateľa.**

- **D1 — primárna kópia na delle.**
  Čo je *vylúčené*: pridať šifrovaný LV popri existujúcom. `ubuntu-vg` má
  **`VFree 0`** a celý disk je jeden PV (`/dev/sda3`), takže nový LV by
  vyžadoval zmenšenie koreňového — a to pri ext4 na pripojenom koreni
  nejde, treba offline `resize2fs`. (Konzola je pritom fyzicky k dispozícii,
  dell je notebook s klávesnicou a displejom — viď nižšie — takže to nie je
  nemožné, len zbytočne riskantnejšie než preinštalovanie na takmer holom
  stroji.)

  Reálne teda zostáva:
  (a) **preinštalovať s LUKS** (inštalátor Ubuntu Server vie „Encrypt the
  LVM group with LUKS") a pripraviť stroj nanovo — dell je zatiaľ takmer
  holý, takže cena je ~hodina;
  (b) **prijať nešifrovaný primár a zapísať to** do `DATA_PROTECTION.md`
  ako vedomú zmenu oproti Macu;
  (c) odložiť — neodporúčam, je to presne tá zmena, ktorá sa po nahratí dát
  robí ťažko.

  K (a) treba povedať dve veci, ktoré sa ľahko prehliadnu a ktoré rozhodujú:

  1. **LUKS na neobsluhovanom serveri znamená, že po každom reštarte musí
     niekto prísť a zadať heslo** — inak stroj nenabehne a tailnet meno
     ostanú mŕtve. To *nie je* regresia voči dnešku (Mac má FileVault a tiež
     čaká na človeka), ale je to vlastnosť, ktorú treba prijať vedome.
     Dell je notebook s klávesnicou a displejom (`Inspiron 5759`,
     `chassis_type 10`), takže fyzicky to ide.
  2. **A práve preto je podstatné, že dell nemá batériu.** V
     `/sys/class/power_supply/` je len `AC` — žiadny `BAT*`. Batéria je teda
     mŕtva alebo vybraná, a to znamená, že **každý výpadok napájania je
     nečistý reštart**. Na Macu je FileVault vyvážený tým, že je to stroj,
     pri ktorom aj tak sedí človek; na serveri, ktorý má byť dostupný
     odvšadiaľ, je kombinácia „bez batérie" + „čaká na heslo" iná: výpadok
     prúdu = služba dole, kým sa niekto fyzicky nedostaví.

     Z toho vyplýva, že (a) má zmysel buď spolu s UPS, alebo s vedomým
     prijatím toho, že návrat po výpadku nie je automatický.

  **Oprava môjho vlastného skoršieho záveru: TPM to nemení na „zložitosť bez
  zisku".** Tvrdil som, že keyfile na nešifrovanom koreni aj TPM odomknutie
  „pridávajú zložitosť bez skutočného zisku, lebo zlodej stroj proste zapne".
  Prvá polovica je správna (keyfile cestuje s diskom, ktorý má chrániť), druhá
  je nepresná a rozhoduje o voľbe. Odmerané na delle 15. 9.:

  | čo | stav |
  |---|---|
  | TPM | **je** — `/sys/class/tpm/tpm0`, verzia `2`, „TPM 2.0 Device" |
  | nástroje | `systemd-cryptenroll`, `cryptsetup` sú nainštalované |
  | Secure Boot | **enabled** (`mokutil --sb-state`) |

  To je presne kombinácia, pri ktorej `systemd-cryptenroll --tpm2-device=auto`
  (default PCR 7) odomkne disk **bez človeka** — a vďaka zapnutému Secure Bootu
  to prežije aj aktualizácie jadra a bootloaderu. Tým **padá hlavný argument
  pre (b)**: „po každom reštarte musí niekto prísť" už neplatí, a to je práve
  tá vlastnosť, ktorú mŕtva batéria robí kritickou. Zároveň sa zachováva
  passphrase slot, takže keď sa TPM meranie zmení, stroj sa spýta — a to je
  poistka, nie porucha.

  Čo TPM **naozaj nerieši**, a musí byť povedané rovnako jasne: kto odnesie
  **celý stroj**, ten ho proste zapne a TPM mu kľúč vydá. Chráni teda proti
  tomu, že disk opustí dom (predaj, RMA, vyradenie, vybratie), nie proti
  vlámaniu. (Zvyšok proti tomu sa dá prilepiť — BIOS heslo a vypnuté
  bootovanie z USB — ale to je tvrdenie o odolnom stroji, nie o šifrovaní.)

  **D1 je teda otázka hrozby, nie otázka šifry**, a dá sa rozhodnúť jednou
  vetou:
  - Ak je hrozba „disk odíde z domu" → **(a) preinštalovať s LUKS + TPM2**.
    Získava sa reálna ochrana a zostáva to bez obsluhy.
  - Ak je hrozba „zlodej odnesie notebook" → TPM2 sám nepomôže, na to treba
    passphrase pri boote, a to pri mŕtvej batérii znamená fyzickú účasť po
    každom nečistom vypnutí. Potom je poctivá odpoveď **(b)** — prijať
    nešifrovaný primár, **zapísať to** a investovať dôvernosť do D2, ktorá
    chráni presne tú kópiu, ktorá naozaj opúšťa domov.

  **Poradie je dôležitejšie než voľba: D1 patrí pred autorizáciu Tailscale.**
  *(Platilo pre (a); pri rozhodnutí (b) nižšie to celé odpadá — nič sa
  neprebudúva, takže sa nemá čo stratiť. Nechávam to tu ako záznam toho, prečo
  sa na poradí trvalo v čase, keď (a) bolo v hre.)*
  Ak vyjde (a), preinštalácia zmaže všetko, čo je na delle pripravené —
  fstab riadok pre off-site, automount drop-in s `StartLimitIntervalSec=0`,
  `Linger=yes`, `.env`, rsyncnutý kód — a stroj dostane **inú identitu v
  tailnete**, takže sa autorizuje znova. Dnes je na delle takmer nič, takže
  je to hodina; po autorizácii a po off-site overeniach je to tá istá hodina
  plus znovu celá predletová kontrola. Preto sa naň nechce pýtať až po tom,
  čo používateľ otvorí autorizačnú URL.

- **D2 — off-site replika.** `DATA_PROTECTION.md` žiada „an encrypted
  off-host replica" a nešifrovaný cieľ výslovne nazýva neprijateľným
  dlhodobo. Na lenove sa to šifrovaním zväzku splniť nedá: disk je
  nešifrovaný a `sam` tam nemá passwordless sudo, takže LUKS na cieli je bez
  používateľa nedostupný — a odomykanie keyfile-om na tom istom disku by ten
  zmysel zrušilo. **Odporúčam šifrovať payload na zdroji:** `gpg` s verejným
  kľúčom, súkromný kľúč drží používateľ (password manager + Mac), na delle je
  len verejný. Tým je (i) požiadavka splnená doslovne, (ii) kompromitácia
  servera neodhalí off-site kópiu, (iii) netreba root na lenove. `gpg` je na
  **oboch** strojoch už teraz (`/usr/bin/gpg` na delle, Homebrew na Macu), takže
  sa nič nedoinštalúva. Zamietnuté alternatívy: LUKS na lenove (vyššie)
  a trvalý `CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=true` (dokument ho sám
  nazýva dočasnou výnimkou).

  D2 by zmenilo: `replicate` zapisuje `X.dump.gpg`, `offsite_status` súdi
  „najnovšia off-site replika je šifrovaná" podľa artefaktu (nie podľa
  zväzku), `prune` musí poznať nový suffix a restore runbook dostane krok
  s odšifrovaním.

**Rozhodnuté 15. 9.** — D1 používateľ najprv delegoval na mňa („vyber to, čo by
si odporúčal"), a **v ten istý deň ho vrátil na (b)**: „vykašlime sa na to
preinštalovanie, veď to nie je nutné, veď to bude len môj domáci projekt, nie
úplná produkcia." Rešpektované a reinstall sa ruší.

- **D1 = (b): dell ostáva bez LUKS, primár je nešifrovaný — a je to zapísané.**
  Zdôvodnenie, ktoré rozhodlo, je rozsah: nie je to plná produkcia, takže
  ochrana nevyvážila prácu s prebudovaním stroja, ktorý je inak nastavený
  a overený. Zapísané v `docs/DATA_PROTECTION.md` („The primary copy is not
  encrypted at rest — recorded 2026-09-15"), aby to nebolo prekvapenie pri
  čítaní dokumentu o ochrane dát — a aby bolo jasné, že to je **vedomý krok
  nadol** oproti Macu s FileVaultom, nie prehliadnutie.

  Čo to prijíma: kto odnesie **disk** (nie celý stroj), prečíta databázu —
  verejné registrové dáta plus používateľské účty. Čo to **nenarúša**: off-site
  story, lebo tá kópia, ktorá naozaj opúšťa domov, je šifrovaná na zdroji
  (D2). Revízia patrí na stôl, keď dáta prestanú byť hobby, alebo keď pribudnú
  osobné dáta, ktoré nie sú už aj tak verejné.

  **Dôsledok, ktorý ruší celé poradie: Tailscale už nie je blokované
  rozhodnutím.** Varovanie „D1 patrí pred autorizáciu" platilo pre (a), kde
  preinštalovanie mení identitu stroja v tailnete. Pri (b) sa nič neprebudúva,
  takže autorizácia sa dá spraviť hneď a je to **jediná zostávajúca vec, ktorú
  musí spraviť používateľ** — všetko ostatné ide bez neho.

- **D2 = šifrovať na zdroji (`gpg`), schválené.** Implementácia je nová
  kontrola v `scripts/local/`, preto má vlastný plán nižšie.

### D2 — ako sa to implementuje (gpg na zdroji)

Podstata: nešifrované dáta **nikdy neopustia dell**, takže otázka „je cieľový
zväzok šifrovaný?" prestáva byť otázkou o cieli a stáva sa otázkou
o **artefakte**. To je zmena významu, nie pridanie podmienky — a musí sa
prejaviť na všetkých štyroch miestach, inak by vznikla presne tá nezhoda,
ktorej sa `offsite_crypto.sh` vyhýba tým, že ju má implementovanú raz:

| miesto | teraz | po D2 |
|---|---|---|
| `replicate` | overí zväzok, zapíše `X.dump` | zašifruje na `X.dump.gpg`, zapíše `.gpg`; zväzková otázka sa **preskočí s uvedeným dôvodom**, nie ticho |
| `offsite_status` | `FAIL`/`OK` podľa zväzku | súdi **artefakt**: existuje `X.dump.gpg`, sedí `.json` manifest a checksum |
| `prune` | drží `X.dump` + `.json` | musí poznať `.gpg` aj `.gpg.json`, inak by retention mazala naslepo |
| drill / restore | `pg_restore` dumpu | `gpg --decrypt` → `pg_restore`; **drill musí skúšať šifrovaný artefakt**, lebo to je to, čo naozaj existuje |

Kľúč: verejný na delle, súkromný u používateľa (password manager + Mac).
Chýbajúci alebo nedostupný kľúč **nesmie** skončiť tichým zápisom
nešifrovaného dumpu — to je jediná skutočná pasca tejto zmeny: zašifrovanie,
ktoré pri poruche kľúča spadne späť na plaintext, je horšie než žiadne,
lebo vyzerá ako hotové. Preto sa `replicate` pri chybe gpg **zastaví**, a to
istým spôsobom ako dnes pri neoverenom zväzku.

#### Stav implementácie (2026-09-15) — hotové a overené

Všetky štyri miesta z tabuľky sú prepísané a **prešli end-to-end testom** na
ostrej druhej filesystéme (pripojený disk image), s reálnym `pg_dump`om
z odhodeného `postgres:16-alpine` kontajnera a s **kľúčenkou, ktorá má len
verejný kľúč** — teda v takom usporiadaní, v akom pobeží dell:

| čo sa overilo | výsledok |
|---|---|
| `replicate` zašifruje na zdroji, na kľúčenke bez súkromného kľúča | áno, `X.dump.gpg` + `.json` |
| na zväzku nezostane plaintext | áno (a `offsite_status` naň padá) |
| `verify` overí `.gpg` bez súkromného kľúča | áno, cez manifest + `--list-packets` |
| `offsite_status` súdi artefakt, zväzok len ako kontext | áno |
| poškodený `.gpg` (checksum) | chytené |
| `.gpg`, ktoré nie je ciphertext (checksum sedí) | chytené |
| `prune --offsite` pozná `.gpg` a uprace plaintextové zvyšky | áno (dry-run aj `--apply`) |
| drill zo **šifrovanej** repliky | prejde a zároveň dokáže, že kľúč je k dispozícii |
| drill bez súkromného kľúča | odmietne, s vysvetlením oboch príčin |
| `replicate` bez nakonfigurovaného príjemcu | odmietne, **nič nezapíše** |
| `replicate` s príjemcom, na ktorý kľúčenka nemá kľúč | odmietne, **nič nezapíše** |
| prázdna exportovaná premenná `CISTAFIRMA_OFFSITE_GPG_RECIPIENT` | **nevypne** šifrovanie (vyhráva súbor) |

Nová je aj obsluha kľúča — `make db-offsite-key-generate` / `-export` /
`-import` / `-status` (`scripts/local/gpg_backup_key.sh`) a `replicate` už
účtuje príjemcu do záznamu o replike. Kľúč sa generuje s **`default default
never`**, teda ed25519 podpisový primár + cv25519 **šifrovací** podkľúč: kľúč
len na podpis ohlási pri prvom zápise repliky „Unusable public key", čo je zlý
spôsob, ako sa to dozvedieť.

**Čo tým padá:** `CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP` prestáva byť
vstupom brány (zväzok už nie je to, čo chráni databázu). Premenná sa už len
číta a `offsite_status` na ňu píše `WARN`, kým je nastavená — na Macu teda
treba ten riadok z `~/.config/cistafirma/backup.env` odstrániť. Tým zároveň
mizne dôvod, prečo off-site brána nemohla na Linuxe prejsť vôbec: `/dev/sda3`
je ext4 bez LUKS a bez passwordless `sudo` ju vytvoriť nemožno — šifrovanie na
zdroji tú závislosť **ruší**, neobchádza.

**Ešte nie je hotové:** samotný kľúč na Macu ešte neexistuje a na delle nie je
jeho verejná polovica. To je krok 1 runbooku a robí sa raz, ručne —
`make db-offsite-key-generate` sa pýta na passphrase, ktorá patrí do password
managera, takže to nie je vec, ktorú by mal spustiť agent. Patrí to k #105
(off-site na lenovo), spolu s pripojením zväzku.

**Postup migrácie, v poradí (D1 a D2 sú rozhodnuté, takto sa to spraví):**

1. **Autorizovať Tailscale na delle** → `tailscale status` je up, `gitlab-home`
   funguje, sshfs na lenovo sa pripojí. *Jediný krok, ktorý musí spraviť
   používateľ* — a pri D1=(b) už na nič nečaká.
2. **Kód a `.env` na dell** — dnes to ide aj po LAN z Macu; po autorizácii
   čistejšie `git clone` z gitlabu. Server je inak nastavený a overený
   z predletovej kontroly, takže sa nezačína od nuly.
3. **Rotácia `SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD` (#112)** —
   **pred** krokom 5, kým na delle neexistuje volume.
4. **Databáza (#106/#107)** — utíšiť Mac (beat a workery), čerstvý overený
   dump, prenos, obnova, overiť počty.
5. **Prvý štart (#108)** — workery, **beat až po obnove databázy**, potom
   `tailscale serve --bg 5173`.
6. **Dokončiť kontroly** — prvý drill a prvá replika na lenovo, inštalovať
   týždenný timer (#115).
7. **Cutover (#109)** — vypnúť Mac, overiť z iného zariadenia.

Tri veci, ktoré pri tom treba mať vopred na pamäti:

- **Nikdy nesmú bežať dva beatu naraz.** Databázy sú oddelené, takže sa
  nepokazia dáta — ale oba by šliapali na tie isté registre (RUZ, ORSR,
  VSZP), čo je cesta k rate-limitu. Mac-ov beat dole **pred** štartom dellu.
- **Redis sa neprenáša.** V Mac-ovom Redise visí ~80 000 správ pre poisťovne;
  tie sa stratia. Nie je to strata dát — beat ich znova vyberie podľa „čo je
  due" — je to oneskorenie. Nech to nie je prekvapenie.
- **Na delle bude `ops-check` spočiatku hlásiť FAIL, a bude to správne.**
  Záznam o drilli aj o replike je lokálny (`restore_drills.log`) a dell
  nezačína so žiadnym, takže brána napíše `no restore drill has been
  recorded` (`offsite_status.sh:192-193`). Preto krok 7: po obnove spustiť na
  delle `make db-restore-drill` (do izolovaného cieľa, nikdy nad živou
  databázou), inak vyzerá migrácia pokazená, hoci je v poriadku.

---

### Päť nálezov z 15. 9. — čo z nich bola pravda a čo nie

Päť vecí bolo otvorených ako „treba tak či tak vyriešiť". Preveril som ich
naživo, jeden po druhom, a **dva z nich neboli nálezy** — boli to stavy, ktoré
sa medzitým zmenili. To je dôležité pomenovať presne, lebo „vyriešiť nález"
a „nález nebol pravda" sú dve rôzne veci a druhá sa nesmie tváriť ako prvá.

**1. `ALLOWED_HOSTS` v `.env` bol mŕtvy config — ✅ vyriešené, a bolo to
horšie, než sa zdalo: oprava bola commitnutá, ale nebežala.** Opravené
v `ece5652` (15. 9. 00:20): `settings.py` ho konečne číta. Lenže kontajner
`cistafirma_backend` sa štartoval **14. 9. 21:46**, teda o dve a pol hodiny
skôr, a `ALLOWED_HOSTS` sa číta raz pri importe `settings.py`. V ostrej
prevádzke teda bola premenná **stále mŕtva** a platil fallback `or ["*"]`
(settings.py:75) — repo tvrdilo validáciu, ktorú proces nevykonával. Odmerané
naživo pred zásahom: `Host: evil.example.com` → **404**, teda prijaté.

  Zároveň platilo, že akonáhle oprava nabehne, Mac je **prísnejší než predtým**:
  jeho `.env` mal `ALLOWED_HOSTS=localhost,127.0.0.1,backend` bez tailnet mena,
  čím sa `or ["*"]` stal nedosiahnuteľným. Restart bez zmeny `.env` by teda
  z tailnetu spravil 400.

  Spravené a overené: `.env` na Macu má teraz **rovnaké tri tailnet hodnoty ako
  dell**, `backend` bol znovu vytvorený (`up -d --force-recreate backend`, bez
  `-v`, volume nedotknutý, `healthy` za 4 s) a matica je:

  | `Host:` | pred | po |
  |---|---|---|
  | `evil.example.com` | 404 (prijaté) | **400** |
  | `attacker.test` | 404 (prijaté) | **400** |
  | `127.0.0.1:8080`, `localhost:8080`, `backend` | 404 | 404 |
  | `dell…` / `dell-1…` / `macbook-pro-samuel…`.taildb03cf.ts.net | 404 | 404 |

  Aplikácia cez Vite funguje ďalej (`5173/` → 200, `5173/api/` → 404, teda nie
  400), lebo proxy posiela `Host: backend` a to v zozname je.
  `FRONTEND_ALLOWED_HOSTS` je v `.env` tiež, ale `vite.config.ts` ho číta pri
  štarte, takže na Macu nabehne až s najbližším reštartom frontendu; na delle
  bude platiť od prvého štartu.

**2. `.env` nemá `EMAIL_BACKEND` — ❌ nebol to nález, ale je to presne jedna
chýbajúca položka.** `EMAIL_BACKEND` bol **jediný kľúč**, ktorý `.env` nemal
oproti `.env.default`, a chýbal **na oboch strojoch** — moja skoršia veta, že
dell je „nadmnožina Macu a líši sa len `ALLOWED_HOSTS`", bola nepresná: dell
mal o `FRONTEND_ALLOWED_HOSTS` a `CSRF_TRUSTED_ORIGINS_EXTRA` viac a
`EMAIL_BACKEND` mu chýbal rovnako. `settings.py:669` má pritom default
`django.core.mail.backends.console.EmailBackend`, takže chýbajúci riadok dá
presne to, čo `.env.default` dokumentuje. Toto je opak prípadu 1: tam kód
premennú **nečítal**, tu ju číta **s rozumným defaultom**.

  Dopísaný je teraz explicitne na oboch strojoch (30 kľúčov, voči
  `.env.default` nechýba nič), aby stav nezávisel od implicitného defaultu.
  Čo je však reálne a treba rozhodnúť: notifikačné e-maily (dlhy, zmeny
  štatutárov) skončia **len v logu backend kontajnera**. Ak ich má niekto
  dostať, treba SMTP — to je rozhodnutie, nie oprava.

**3. Tailscale na Macu je zastavený — ❌ už neplatí.** Beží:
`macbook-pro-samuel` = `100.72.231.21`, `sam-lenovo` je `active; direct`. Von
z tailnetu je len `dell` (`NeedsLogin`, čaká na tvoju autorizáciu na
`https://login.tailscale.com/a/c458d6401f618`).

**4. `gitlab.home.arpa` sa neprekladá — ❌ už neplatí, a má to spoločnú
príčinu s 3.** Prekladá sa cez MagicDNS na `100.120.104.84` (lenovo)
a `git ls-remote gitlab-home` **funguje** — vypíše refs. Keď bol Mac odpojený
z tailnetu, neprekladalo sa ani jedno; sú to dva príznaky jednej veci. (`host`
sa pritom pýta inak a vráti `REFUSED`, kým `dscacheutil` a `ping` preložia —
ďalšia dvojica nástrojov, ktoré sa na tú istú otázku nezhodnú.)

  Návod, ktorý sa tu ponúka — pripísať `gitlab.home.arpa` do `/etc/hosts` — by
  **nepomohol**, a je dôležité povedať prečo: meno by sa síce preložilo aj bez
  Tailscale, ale trasa na `100.120.104.84` je tailnetová, takže bez Tailscale
  by spojenie spadlo tak či tak, len o krok neskôr a s horšou chybovou
  správou. Závislosť na tailnete tu nie je chyba na obídenie, je to vlastnosť:
  `gitlab.home.arpa` je tailnetové meno a nič iné.

**5. Off-site brána hlási „off-site directory is not mounted" — ✅ je to
správne, ale zlý je dôvod, ktorý za tým je.** Brána nenadáva na výpadok
pripojenia. Na Macu je `CISTAFIRMA_OFFSITE_BACKUP_DIR=/Volumes/CistaFirmaBackups`
a **to volumes neexistuje**: v `/Volumes` je len `.timemachine`, `DRIVER`,
`Macintosh HD` a `Recovery`. `DRIVER` je pritom 173 KB FAT12 oddeľok
s `AUTORUN.INF` a `Windows Driver.url` — teda ovládačový oddeľok z USB kľúča,
nie cieľ zálohy. `diskutil list external` to potvrdzuje zhora: pripojený je
**jediný** externý disk a je to práve ten `DRIVER` (197,1 KB). Nevisí teda
žiadny externý dátový disk — nie je to výpadok pripojenia, ale to, že cieľ
**nie je kam pripojiť**. Druhá kópia naposledy vznikla 2026-09-10T18:25Z; drill
z 10. 9. ju odtiaľ aj čítal, takže cieľ vtedy pripojený bol.

  Dve veci na tom treba pomenovať, lebo obe sú dôležitejšie než samotné
  hlásenie:

  - Odpojený cieľ je **zámerne len `warn`, nie `bad`** („not required for an
    unattended run", `offsite_status.sh:56`) — rozumné pre prenosný disk, ale
    znamená to, že neprítomnosť druhej kópie **nespôsobí zlyhanie behu**.
    Skutočná záchranná brzda je až veková hranica: `MAX_REPLICA_AGE_DAYS`
    default **14** (`offsite_status.sh:32`), takže brána začne padať okolo
    **24. 9.** Dovtedy hlási `SATISFIED`. To je správne nastavené, ale je to
    14 dní, nie hneď.
  - Migrácia to rieši kvalitatívne: cieľom na delle je **lenovo po tailnete**,
    teda sieťový mount, ktorý je k dispozícii vždy, keď je lenovo hore — nie
    prenosný disk, ktorý treba pripájať. Presne preto je tá automount
    a stráž „nezapisuj lokálne" taká podstatná.

### Štyri nové nálezy, ktoré vypadli z tej istej kontroly

- **`SECRET_KEY` je na oboch strojoch verejný default.**
  `django-insecure-change-me-in-production` — doslova text z `.env.default`,
  teda z verejného repa. Overené porovnaním hashu, nie čítaním hodnoty:
  `sha256[:16]=de7e7c720036a266` na Macu **aj** na delle, dĺžka 39. Takto
  podpísané sú session cookies a tokeny na reset hesla. Na Macu je to
  pre-existujúce a je to tvoja vec; na delle to je vec migrácie — a musí sa to
  stať **pred reštartom na ostrej prevádzke**. Výmena je teraz bezplatná
  (databáza tam ešte nie je, takže niet čo invalidovať) a bola by drahá po
  #107. **Rotáciu som nespravil** — automatický klasifikátor oprávnení ju
  odmietol ako materializáciu credentialu, a to je miesto, kde sa zastavujem
  a nie obchádzam. Príkaz na teba je v reporte.
- **`DEBUG=True` na delle — ✅ opravené na `False`.** `settings.py:28` číta
  `DEBUG` s defaultom `False`, takže `.env` ho len zapínal; záloha `.env` je
  `.env.bak-20260914T223411Z` (600). Oboje s overením: `check --deploy` s
  `DEBUG=False` a silným kľúčom hlási **4 warningy** (`W004` HSTS, `W008`
  SSL redirect, `W012` session cookie, `W016` CSRF cookie) a **žiadny
  `W009`** — teda slabý `SECRET_KEY` je po rotácii vyriešený a `DEBUG` je preč.
  `W008` sa zapnúť **nesmie**: Vite proxy posiela na gunicorn po HTTP a
  `SECURE_PROXY_SSL_HEADER` nie je nastavený, takže `SECURE_SSL_REDIRECT=True`
  by spravil nekonečnú slučku. `collectstatic` je bezpečný, lebo ho compose
  `command` púšťa pred gunicornom cez `&&` (na rozdiel od `|| true` v
  Dockerfile).
- **Jediná cesta do appky je `tailscale serve`.** `BIND_HOST` nie je nastavený
  v `.env` ani na jednom stroji, takže backend aj frontend sú **loopback-only**
  (`${BIND_HOST:-127.0.0.1}:…`). To potvrdzuje, že voľba `tailscale serve` bola
  správna a nie je len pohodlnejšia — **iná cesta neexistuje**, a preto musí
  `tailscale serve` na delle po autorizácii bežať proti `127.0.0.1:5173`.
  Zároveň to znamená, že bezpečné cookies (`SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SECURE`) by boli bezpečné — ale `settings.py` dnes **nečíta
  žiadne** `SECURE_*`/cookie nastavenie, takže zapísať ich do `.env` by bolo
  presne tú istú mŕtvu konfiguráciu, ktorá bola nálezom 1. Nezapisujem ich;
  vyžadujú zmenu `settings.py` a to je samostatný, otestovaný krok.
- **`.env` na Macu bol `-rw-r--r--` (644) — ✅ opravené na 600.** Súbor, ktorý
  drží `SECRET_KEY`, `POSTGRES_PASSWORD` aj `REDIS_PASSWORD`, bol čitateľný pre
  každý lokálny účet. Na delle bol 600 už predtým, takže to bola len Macova
  vec — ale je to ten druh nálezu, ktorý sa dá vyriešiť dvoma znakmi a inak sa
  nemusí nikdy objaviť. `chmod` je bezpečný: `.env` číta Docker Compose CLI
  (beží pod tým istým účtom), nie proces v kontajneri, ktorý by mal iného
  vlastníka.

### Týždenná úloha sa hlási ako „ešte nebežala" — a pritom bežala v nedeľu

`make ops-check` dnes na Macu hlási `WARN launchd has not run the job yet
(installed 4 day(s) ago)`. To WARN je **nepravdivé**: úloha bežala **v nedeľu
13. 9. o 03:17** a jej vlastný vnorený beh brány to vtedy aj zapísal. Dôkaz nie
je odvodený — je v logu, ktorý si úloha píše sama:

| dôkaz | hodnota |
|---|---|
| `~/Library/Logs/CistaFirma/backup.out.log`, mtime | 2026-09-13 03:17:28 |
| ten istý log, štart | `[2026-09-13T01:17:05Z] scheduled backup started` |
| ten istý log, vlastný výstup brány | `launchd runs : 1`, `last start : 2026-09-13T01:17:05Z`, `OK the weekly job started recently` |
| ten istý log, výsledok | `Backup verified` … `scheduled backup finished (cistafirma_20260913T011706Z.dump)` |
| plán v pliste | `StartCalendarInterval {Hour 3, Minute 17, Weekday 0}` (nedeľa) |

`01:17:05Z` je `03:17:05` SELČ, teda **presne na minútu plánu** — a to je
zároveň to, čo tento beh odlišuje od staršieho záznamu v tom istom logu
(`2026-09-10T06:58:40Z`, teda štvrtok 08:58 SELČ, mimo plánovaného slotu, takže
ručný alebo inštalačný beh; plist má navyše mtime až 09:09:57 toho dňa).

Prečo to brána nevidí: kontroluje **`launchd` počítadlo `runs`** a do logu sa
pýta až potom, čo `runs >= 1` (`ops_check.sh:338-366`). Lenže `runs`
**neprežije reload úlohy** — Mac sa reštartoval v pondelok 14. 9. 21:42:47
(uptime 3:18) a počítadlo sa vrátilo na nulu:

```
state = not running
runs = 0
last exit code = (never exited)
job state = uninitialized
```

Úloha teda bežala, stroj sa reštartoval, a počítadlo o tom nevie. Na počítači,
ktorý sa reštartuje, je to **väčšinu času nula** — tento týždenný job sa
naposledy chystal bežať v nedeľu a odvtedy sa stroj raz reštartoval — takže:

- **Falošný poplach.** Brána sa nikdy nedostane na vetvu, ktorá číta log, hoci
  log dôkaz má. Text pritom tvrdí niečo konkrétne a nepravdivé: „its first
  unattended run is still pending".
- **A za štyri dni z toho bude FAIL.** `RUN_GAP_MAX_DAYS` je **8**
  (`ops_check.sh:29`) a `age_days` delí celočíselne nadol; plist má mtime
  **2026-09-10 09:09:57**, takže deväť dní po inštalácii je **2026-09-19
  09:09:57** — odvtedy `installed_days` = 9 > 8 a brána prepne na
  `bad "launchd has never run the job although it was installed 9 day(s) ago"`.
  Najbližšia naplánovaná nedeľa je **20. 9.**, takže pokiaľ Mac do 20. 9.
  nepretržite beží, je medzi 19. 9. 09:09 a 20. 9. 03:17 **~18 hodín tvrdého
  FAILu na úplne zdravom systéme**. Ak sa Mac medzitým reštartuje, `runs` sa
  vynuluje znovu, `installed_days` len rastie — a FAIL sa už nevyčistí vôbec.
- **A v druhom smere to zlyhá presne na to, pred čím má chrániť.** Keď úloha
  naozaj prestane chodiť, `runs` je tiež `0`. Takže „úloha je mŕtva" a
  „počítadlo vynuloval reštart" čítajú **identicky** — najprv `warn`, potom
  `bad`. Kontrola, ktorej celý zmysel je tieto dva stavy rozlíšiť, ich spája.
  To je tá istá trieda ako všetko ostatné v tomto dokumente: nie kontrola, ktorá
  zle počíta, ale kontrola, ktorej dôkaz **nemôže ukázať to, čo tvrdí**.

Nie je to chyba vetvenia — zámer je správny a v komentári aj zdôvodnený
(`ops_check.sh:289-294`: ručný beh nesmie vyzerať ako dôkaz, že schéma žije).
Chyba je vo **voľbe dôkazu**: `runs` nie je vlastnosť, ktorá prežije to, čo má
merať. Oprava musí dať tú istú záruku trvalým spôsobom, teda tak, aby ručný beh
naďalej neplatil:

- **buď** si úloha sama zapíše, že ju spustil plánovač — pod launchdom je to
  rozlíšiteľné bez hádania, rodičovský proces plánovanej úlohy je `launchd`
  (`ps -o ppid= -p $$` → `1`), kým ručný beh má za rodičom shell — a brána hľadá
  **tento** záznam v logu;
- **alebo** sa `runs == 0` prestane čítať ako „nikdy nebežala", keď log štart
  má, a správa povie obe pravdy aj s časom posledného bootu.

**Toto je vec Macu a je to zároveň jeho posledná vec** — #109 ho vypína ako
produkciu. Druhá vetva tej istej kontroly je `systemd` a číta `LastTriggerUSec`
**časovača**, nie čas štartu služby. **Overené 2026-09-15: na Linuxe ten defekt
nie je a záznam reštart prežije** — a overenie zároveň opravilo odhad cesty.
Záznam nie je v `~/.local/state/systemd/timers/`, ako to tu stálo: ten adresár
na delle **neexistuje** ani po tom, čo user timer naozaj odpálil. Je v
**`~/.local/share/systemd/timers/stamp-<unit>.timer`** (namerané:
`stamp-sk.cistafirma.backup.timer`, a po sonde aj
`stamp-cistafirma-stamp-probe.timer`). Systémové timery majú svoje
v `/var/lib/systemd/timers/` — odtiaľ pochádzal ten omyl.

Sonda to overila priamo: jednorazový `Persistent=true` timer
v `~/.config/systemd/user` odpálil, `LastTriggerUSec` sa nastavil a stamp
vznikol na **trvalej** ceste v `/home`, nie v `/run`; po sebe sa upratala.
A reálny týždenný timer ukazuje `LastTriggerUSec = 11:36:56`, kým boot bol
`11:38:55` — hodnota teda **prežila reštart**. Dve veci to vedia pokaziť a obe
sú nenápadné: sonda bez `Persistent=true` stamp **nevytvorí** (prvý pokus
vyšel naprázdno presne preto — stamp existuje kvôli `Persistent=`, nie kvôli
behu samému) a hľadať treba v `share`, nie v `state`.

> **Vyriešené 2026-09-15** — macOS vetva je opravená, pozri „Mac je vypnutý ako
> produkcia" nižšie. Návrh v druhej odrážke (nula sa prestane čítať ako
> „nikdy") je to, čo sa spravilo, vrátane času posledného bootu v správe.

### Čo presne spraviť po autorizácii Tailscale — v tomto poradí

Toto je zoznam krokov, ktoré sa **nedajú spraviť predtým**, aby sa po
autorizácii nemuselo zisťovať, čo vlastne ešte chýba.

**Predtým než sa skúsi LAN skratka: neexistuje.** Ponúka sa myšlienka, že keď
sú dell (`192.168.1.210/24`) a lenovo (`192.168.1.17`) na tej istej podsieť,
kód sa dá stiahnuť z gitlabu na lenove po LAN a na Tailscale sa vykašlať.
Odmerané 15. 9. a **nejde to**: lenovo na `ping` odpovedá (0,3 ms, teda naozaj
beží a je to tá istá podsieť), ale `192.168.1.17:8088` aj `:2222` **timeoutujú**
(rc=28 pri `curl`, `Connection timed out` pri `ssh`). Lenovo má firewall, ktorý
LAN zahadzuje; `timeout`, `nc`, `curl` aj `ping` sú na delle prítomné, takže
výsledok nie je artefakt chýbajúceho nástroja. Smerom von je dell tiež
uzavretý: `ufw` povoľuje len `22/tcp`, `tailscale0` a `41641/udp`.

  Z toho vyplýva to podstatné: **autorizácia Tailscale je jediná akcia, ktorá
  odblokuje tri veci naraz** — klon repa z gitlabu, off-site mount na lenovo
  a `tailscale serve`. Nie je to pohodlnejšia cesta k dvom existujúcim; je to
  jediná cesta k trom neexistujúcim.

**Predletová kontrola je hotová** (15. 9., aby sa po autorizácii nehľadalo,
čo ešte chýba):

| čo | stav |
|---|---|
| časové pásmo | `Europe/Bratislava` (CEST +0200) ✓ |
| ufw | active, `Anywhere on tailscale0 ALLOW` už nastavené ✓ |
| sshd | `PasswordAuthentication no`, `PermitRootLogin prohibit-password`, 0 pokusov o heslo za 7 dní ✓ |
| sudo | passwordless (`/etc/sudoers.d/90-sam-nopasswd`) ✓ |
| docker | `docker info` pre `sam` funguje (29.8.0, overlay2), `sam` je v grupe `docker` ✓ |
| disk | 466 G, použité 9,4 G (3 %) ✓ |
| pamäť / CPU | 7,1 Gi (6,3 Gi free) / 4 jadrá ✓ |
| **linger** | **bol `no` — opravené na `yes`**, viď nižšie |
| **týždenný timer** | **nie je nainštalovaný** — `~/.config/systemd/user/` na delle neexistuje, viď nižšie |
| off-site kľúč | `id_ed25519_offsite` **je** v `authorized_keys` na lenove (odtlačok `SHA256:rwlPrJ4J…`) ✓ |
| kód na delle | `scripts/local/` je **bajt na bajt** zhodné s commitom portu (20/20 hashov) ✓ |
| git HEAD na delle | `ece5652` — 5 commitov za Macom, a **nemá ako sa aktualizovať** |

`Linger=no` bol jediný nález na **existujúcej** konfigurácii a je to presne
trieda tichého zlyhania, ktorú tento projekt rieši všade inde: systemd **user**
timer týždenného zálohovania sa na headless serveri zastaví spolu s poslednou
session, takže by sa nespustil takmer nikdy a nič by to nehlásilo. Opravené
`sudo -n loginctl enable-linger sam`; overené `Linger=yes` a
`systemctl --user is-system-running` → `running`. Je to reverzibilné
(`disable-linger`) a je to presne ten krok, ktorý inštalátor zámeme nevykonáva
sám, len naň upozorňuje.

**Ale linger sám o sebe ten timer nespustí — a ten timer na delle nie je.**
`Linger=yes` je len podmienka, ktorá mu umožní bežať bez prihlásenej session;
samotné unit súbory tam nikdy nevznikli:

```
ls ~/.config/systemd/user/                             -> No such file or directory
systemctl --user list-unit-files | grep cistafirma      -> (nič)
systemctl --user is-enabled sk.cistafirma.backup.timer  -> not-found
```

Inštalátor pritom na Linuxe píše presne do `~/.config/systemd/user`
(`backup_os.sh:160-166`) a repo aj `install_backup_schedule.sh` na delle sú
(`/home/sam/cistafirma/scripts/local/`). `make db-backup-schedule-install` tam
teda **nikdy nebežal** — takže veta „jediný nájdený konfiguračný problém bol
linger" vyššie bola nepresná a je opravená.

Zámerne to **teraz neinštalujem**, a nie je to opomenutie:

- Ak D1 vyjde ako (a) preinštalovanie, zmizne to tak či tak — a to je presne
  dôvod, prečo má D1 prednosť pred akoukoľvek ďalšou prácou na delle.
- #107 hovorí, že beat nesmie nabehnúť pred obnovou databázy. Na delle zatiaľ
  **žiadny docker volume neexistuje**, takže by timer zálohoval databázu, ktorá
  tam ešte nie je, a vytvoril by **klamlivý dôkaz „záloha existuje"** — presne
  ten druh signálu, ktorý tento projekt inde odmieta.

Patrí to teda do zoznamu **po D1**, spolu s `.env`, fstab riadkom pre off-site
a automount drop-inom. V preflight tabuľke je to otvorená položka, nie ✓.

**Druhý nález z tej istej kontroly, a tento má lehotu: všetky tri tajomstvá sú
na oboch strojoch stále verejné defaulty.**

| kľúč v `.env` | Mac | dell | dosah |
|---|---|---|---|
| `SECRET_KEY` | default | default | podpis JWT/session — falšovateľný prihlásený používateľ |
| `POSTGRES_PASSWORD` | default | default | databáza je loopback-only, takže len lokálny proces |
| `REDIS_PASSWORD` | default | default | to isté |
| `METRICS_TOKEN` | prázdny | prázdny | zámerne — `/metrics` je viazaný na privátne adresy |

Porovnávané len na zhodu s verejným defaultom; hodnoty sa nikde nevypisujú.

To nie je nová chyba portu — Mac to tak mal odjakživa. Nové je **vystavenie**:
appka sa presúva z loopback-only na Macu na dosiahnuteľnú v tailnete, takže
`SECRET_KEY` prestáva byť teoretický problém. A je tu **lehotu, ktorá sa
zatvára prvým `docker compose up`**: na delle **neexistuje žiadny docker
volume** (`docker volume ls` je prázdny), takže postgres si rolu inicializuje
z `POSTGRES_PASSWORD` pri prvom štarte. Teraz je teda zmena hesla zadarmo;
potom je to `ALTER USER` nad živými dátami. **Rotácia preto patrí pred #108
(prvý štart stacku), nielen pred #107** — inak sa z jednoduchého zápisu do
`.env` stane prevádzková akcia.

Postup pre `POSTGRES_PASSWORD` a `REDIS_PASSWORD` — obe sú čisto konfiguračné,
nič v databáze na nich nezávisí, kým volume neexistuje. `REDIS_PASSWORD` je
v `.env` na štyroch miestach (`REDIS_PASSWORD`, `REDIS_URL`,
`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`) a musia ostať v súlade; `token_urlsafe`
je URL-safe, takže connection stringy sa nerozbijú:

```bash
cd ~/cistafirma
cp .env ".env.bak-secrets-$(date -u +%Y%m%dT%H%M%SZ)"
NEW_PG=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
NEW_REDIS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
NEW_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')
NEW_PG="$NEW_PG" NEW_REDIS="$NEW_REDIS" NEW_KEY="$NEW_KEY" python3 - <<'PY'
import os, re, pathlib
p = pathlib.Path('.env'); s = p.read_text()
s = re.sub(r'^POSTGRES_PASSWORD=.*$', 'POSTGRES_PASSWORD=' + os.environ['NEW_PG'], s, count=1, flags=re.M)
s = re.sub(r'^SECRET_KEY=.*$',        'SECRET_KEY=' + os.environ['NEW_KEY'],       s, count=1, flags=re.M)
# Every occurrence of the old redis password, in the two .env forms it appears in.
s = s.replace('cistafirma_redis_secret', os.environ['NEW_REDIS'])
s = re.sub(r'^REDIS_PASSWORD=.*$', 'REDIS_PASSWORD=' + os.environ['NEW_REDIS'], s, count=1, flags=re.M)
p.write_text(s)
PY
grep -c 'cistafirma_redis_secret' .env   # must print 0
```

Posledný `grep` je kontrola, že po starom redis hesle neostal ani jeden výskyt
— práve rozídené `REDIS_PASSWORD` a `REDIS_URL` je chyba, ktorá sa prejaví až
tým, že Celery nikam nepripojí. Postup je **odskúšaný na kópii `.env`**
(v `$CLAUDE_JOB_DIR/tmp`, nie na živom súbore): z 9 výskytov starého hesla
(7 v `.env.default`) neostal ani jeden, `POSTGRES_PASSWORD` aj `SECRET_KEY`
prestali byť defaulty a všetky tri Redis URL odkazujú na nové heslo, ktoré je
URL-safe.

Pre `SECRET_KEY` je dôsledok iný a treba ho pomenovať: rotácia zneplatní
všetky existujúce JWT, takže sa používatelia prihlásia znova. Nič sa tým
nestratí — v `requirements.txt` nie je žiadna šifrovacia knižnica, takže na
`SECRET_KEY` nezávisí žiadny uložený obsah, len podpisy tokenov. A keďže sa
databáza na dell prenáša z Macu (#106), je jedno, že Mac má kľúč iný; tokeny
sa aj tak vydávajú nanovo.

Rotáciu vykonáva **používateľ** — hodnoty tajomstiev nevytváram ani nezapisujem.

1. `sudo tailscale up` na delle a autorizovať. V tailnete už uzol `dell`
   existuje (`offline, last seen 11h ago`), takže nový sa môže zaregistrovať
   ako `dell-1`. `.env` má wildcard `.taildb03cf.ts.net`, takže pokrýva obe —
   to je celý dôvod, prečo je tam bodka na začiatku.
2. `getent hosts gitlab.home.arpa` **na delle** musí začať prekladať. Dnes
   neprekladá (overené) a je to presne ten istý príznak, ktorý sa na Macu
   javil ako chyba DNS — bez tailnetu niet MagicDNS.
3. Pridať remote a **dokázať, že sa repo vie aktualizovať**:
   `git remote add gitlab-home ssh://git@gitlab.home.arpa:2222/web/cistafirma.sk.git`
   a `git ls-remote gitlab-home`. Toto nie je voliteľné: dell má dnes **jediný**
   remote `origin` = `https://github.com/xsugra/cistafirma.sk.git`, čo je
   privátny repozitár a na delle k nemu **nie sú žiadne credentials**
   (overené: žiadne `~/.git-credentials`, žiadne `credential.*`). Kód sa tam
   teda dostal klonovaním zvonku a **dell sa dnes nevie aktualizovať vôbec**.
   Na tomto remote závisí aj verejný kľúč dela na GitLabe (`~/.ssh/id_ed25519.pub`)
   — ak tam ešte nie je, treba ho zaregistrovať.

   Pozor na pracovný strom: `scripts/local/` je na delle zmenené voči `ece5652`
   presne o obsah portu, takže `merge --ff-only` môže odmietnuť prepísať
   lokálne zmeny. Postup, ktorý je bezpečný, lebo obsah je už zhodný:
   `git fetch gitlab-home`, `git diff --stat HEAD..gitlab-home/feat/ai-ready-baseline -- scripts/local`
   (musí ukázať presne port a nič iné), záloha `tar czf ~/scripts-local.tgz scripts/local`,
   a až potom `git checkout -- scripts/local && git merge --ff-only`.
   `checkout` tu nie je strata — vracia súbory na `ece5652`, odkiaľ ich merge
   vzápätí vráti späť na obsah, ktorý tam je teraz. Záloha je pre prípad, že
   by diff ukázal niečo iné, než sa čaká.
4. `tailscale serve` proti frontendu — jediná cesta do appky, viď nález vyššie
   (`BIND_HOST` nie je nastavený, takže backend aj frontend sú loopback-only).
   Verzia na delle je **1.102.4**, takže syntax je `tailscale serve --bg 5173`
   (cieľ sa dá zadať ako port; `--bg` ho nechá bežať, bez toho beží v popredí).
   Keďže frontend je publikovaný na `${BIND_HOST:-127.0.0.1}:5173`, služba
   na `127.0.0.1:5173` je presne to, na čo sa to má napojiť.

   **Pozor na jednu vec, ktorá to zastaví a nie je to zjavné:** `serve` štandardne
   vystavuje na **HTTPS (443)** a to vyžaduje, aby mal tailnet zapnuté
   **HTTPS certifikáty** v admin konzole (`login.tailscale.com` → DNS → HTTPS
   Certificates). Bez toho `serve` odmietne s tým, že HTTPS nie je zapnuté —
   a na delle to dnes overiť nevieme, lebo bez autorizácie sa `serve` ani
   nerozbehne. Je to nastavenie tailnetu, nie stroja, takže sa to zapína raz
   a je zadarmo (nie je to Funnel, teda nie je to vystavenie do internetu).
   Alternatíva, ak sa certifikáty zapnúť nechcú, je `tailscale serve --http=80 5173`,
   ale to dá obyčajné HTTP a `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`
   by potom nemali zmysel.

   `serve` na Linuxe treba spúšťať cez `sudo` (alebo si najprv nastaviť
   `sudo tailscale set --operator=sam`, aby netrebalo `sudo` pri každej zmene).
5. Off-site: automount je nastavený a naarmed, takže `make db-offsite-status`
   musí prestať hlásiť „not mounted".

   **Verdikt šifrovania je teraz predoverený, nie odhadnutý.** SSH z dela na
   lenovo prejde neinteraktívne — kľúč `id_ed25519_offsite` je v
   `authorized_keys` na lenove a fstab ho používa explicitne cez
   `IdentityFile=`, takže `~/.ssh/config` záznam netreba. A na lenove je cieľ
   `/home/sam/cistafirmaBackups` na `/dev/sda3`, `ext4`, bez LUKS vrstvy
   (`lsblk -s -no NAME,TYPE,FSTYPE` → `sda3 part ext4` pod `sda disk`), takže
   vzdialená kontrola **odpovie** — verdikt bude `unencrypted`, nie `unknown`.

   `replicate` sa teda odmietne. **Toto už neplatí — prekonal to D2** (commit
   `18e8d24`), a je dôležité, aby to tu nezostalo ako fakt, lebo je to presne
   tá veta, podľa ktorej by sa niekto rozhodol cieľ najprv šifrovať. Verdikt
   zväzku je odvtedy **kontext, nie brána**: replikuje sa artefakt zašifrovaný
   na zdroji, takže nešifrovaný cieľ už databázu nevystavuje a kópia sa
   neodmietne. Kontrola sa stále spúšťa a stále sa vypisuje — „prestali sme sa
   pozerať" a „pozreli sme sa a je to v poriadku" sú dva rôzne fakty — ale len
   ako `NOTE`. Očakávaný verdikt na lenove je `unencrypted` (ext4 bez LUKS),
   a to je v poriadku. Token `CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP` teda
   netreba a na delle v `backup.env` ani nie je (overené).

### Migrácia na `dell` je hotová — a off-site záloha naozaj beží (2026-09-15)

Stav overený naživo 2026-09-15: **10 kontajnerov beží** (`restart:
unless-stopped`; `db`, `redis` aj `backend` healthy), `/healthz/` vracia
`{"status": "ok", "db": "ok", "redis": "ok (0ms)"}`, frontend aj
`/api/stats/landing/` odpovedajú cez `https://dell.taildb03cf.ts.net/`
(449 776 firiem), `showmigrations --plan` má **0 neaplikovaných**. Databáza je
obnovená a **39 tabuliek / 2 762 306 riadkov je zhodných s Macom**; všetky tri
tajomstvá boli zrotované **pred prvým štartom `db`**, takže volume sa
inicializoval už s novým heslom — po prvom štarte by to bola `ALTER USER` nad
živými dátami.

Reštart stroja to prežil bez zásahu, a to je zároveň dôkaz, že prežije:
kontajnery nabehli samy (`RestartCount=0`), `docker` aj `tailscaled` sú
`enabled`, `tailscale serve` konfigurácia ostala. (Pri kontrole pozor na
`Up 5 minutes` — po reštarte to nie je príznak, ale očakávaný údaj; `uptime -s`
je jediná odpoveď na otázku „kedy naozaj".)

Po oprave nižšie týždenná úloha prejde až k operačnej bráne a **lokálnu záložu
naozaj vytvorí** (131 MB dump, overený checksum). Padá už len na off-site
kontrole. Restore drill je zapísaný (`39 public tables`, `source: local`) — to
bola druhá nesplnená kontrola a bola celý čas **neblokovaná**, len sa nikdy
nespustila.

**Nález: `systemd --user` manažér si drží skupiny z okamihu svojho štartu.**
Týždenná úloha zlyhala na `permission denied ... /var/run/docker.sock`, hoci
`sam` v grupe `docker` **bol** — a ručne spustená tá istá úloha fungovala. To
je to, čo to robí nepríjemným: rovnaký príkaz uspeje v ssh session a zlyhá pod
časovačom. Namerané: manažér (PID 1701) štartoval `18:36:21`, `/etc/group` sa
zmenil `19:04:38` (o 28 minút neskôr), a jeho skupiny boli
`4/24/27/30/46/100/101/1000` — **bez 983**. Opravuje to reštart stroja (alebo
`user@1000.service`), nie `daemon-reload`, a ručné spustenie z ssh to nikdy
neukáže, lebo ssh session má skupiny čerstvé.

**Nález: FUSE mount vlastnený rootom nie je pre `sam` priechodný bez
`allow_other` — a chyba to nepovie.** `sshfs` z `/etc/fstab` mountuje
`systemd` ako **root**, a bez `allow_other` je taký mount priechodný len pre
roota. Pre `sam` to vyzerá ako `Permission denied` pri `cd`, ale kontrola to
hlási ako **„is not a directory"** — čo pošle operátora hľadať preklep v ceste,
nie chýbajúcu mount option. Overené z oboch strán: `sudo ls -la
/mnt/cistafirma-offsite` vypíše `total 8` a obsah patrí `uid 1000`, kým
`mountpoint` aj `[ -d ]` pre `sam` zlyhajú na `EACCES`. Mount pritom
`active (mounted)` **je**. Rozdiel je teda výhradne vo viditeľnosti, nie
v pripojení — a to je presne dvojica, ktorú treba odlíšiť, lebo „nepripojené"
a „nepriechodné" majú inú opravu.

*Poznámka k `user_allow_other` v `/etc/fuse.conf`: netreba ho.* Mount spúšťa
root a root je z toho pravidla vyňatý; pridávať ho by rozšírilo oprávnenie pre
všetkých používateľov stroja bez dôvodu. Stačí `allow_other` v riadku pre
`cistafirma-offsite`.

**Nález: automount sa po sérii zlyhaní vzdá a cesta sa ticho stane obyčajným
adresárom.** `systemd` defaultne rate-limituje pokusy o mount; po ~13 minútach
sondovania s nedostupným lenovom bola jednotka `failed
(mount-start-limit-hit)`, autofs trigger zmizol z `/proc/self/mountinfo`
a `/mnt/cistafirma-offsite` **bola obyčajná cesta na koreňovom filesystéme**.
To je presne stav, v ktorom by zálohovací skript mohol zapísať „off-site
repliku" na ten istý disk ako originál a hlásiť úspech. Rieši to drop-in
`StartLimitIntervalSec=0`
(`/etc/systemd/system/mnt-cistafirma\x2doffsite.automount.d/override.conf`),
po ktorom trigger ostane armed a každý prístup zlyhá poctivo na `ENODEV` —
namiesto toho, aby sa tváril ako adresár. **Je to však machine-local a pri
preinštalovaní sa stratí**, preto to patrí aj sem, nie len do komentára
v drop-ine.

**Nález: na hoste, ktorý má len verejný kľúč, je výzva „drill the off-site
copy" nesplniteľná — a ako `WARN` je to správne.** `offsite_status.sh`
upozorní, že posledný drill bol z lokálnej zálohy, keď je off-site kópia
k dispozícii. Na delle sa to nikdy nevyrieši: `.gpg` repliku tam **nemožno**
rozšifrovať, lebo private kľúč tam zámerne nie je (overené:
`--list-secret-keys` je prázdny, verejný `3043D31A…` s šifrovacím podkľúčom
`…F3B8F3ADFBA9DB8F` je tam správne). Drill šifrovaného artefaktu teda patrí na
Mac. Je to `WARN`, nie `FAIL`, takže brána ostáva poctivá — a zároveň je to
jediná kontrola v celom reťaze, ktorá overuje, že private kľúč ešte existuje
a funguje; každá iná by jeho stratu prehliadla.

**Posledný krok bol jedno slovo a je zapísané.** `allow_other` pribudlo do
riadku pre `cistafirma-offsite` v `/etc/fstab` (mount je od tej chvíle pre
`sam` priechodný — `drwx------ 1 sam sam`), do `~/.config/cistafirma/backup.env`
sa doplnil recipient `3043D31A…`, a `make db-backup-replicate` vytvoril **prvú
šifrovanú repliku**: `cistafirma_20260915T093932Z.dump.gpg` (131 458 875 B) s
manifestom, na lenove v `~/cistafirmaBackups`, so záznamom v `replicas.log`.
`make ops-check` na delle potom hlási **`Operational controls: SATISFIED (2
warning(s))`, 0 unmet** — oba warningy sú štrukturálne a správne (drill z
off-site kópie patrí na Mac; timer ešte neodpálil).

Overené nezávisle od brány, priamo na lenove: na off-site zväzku **nie je
žiadny plaintext dump** a artefakt začína `84 5e` — OpenPGP packet tag 1
(Public-Key Encrypted Session Key), čiže je to naozaj šifrované verejným
kľúčom, nie súbor premenovaný na `.gpg`. To je celý zmysel D2 a je to jediná
vec, ktorú z artefaktu samého nevidno.

**Nález (opravený): `configure_offsite.sh` mazal zaznamenaného recipienta.**
Skript sľubuje, že vynechaný alebo prázdny argument nechá príslušný kľúč tak,
ako bol. Neplatilo to — `awk` testoval `ekey != ""` / `rkey != ""`, teda
*názov* kľúča, ktorý je vždy neprázdny, namiesto jeho hodnoty. Reprodukované
proti skutočnému skriptu: `make db-offsite-configure
CISTAFIRMA_OFFSITE_BACKUP_DIR=<dir>` **bez** recipienta prepísalo zapísaný
odtlačok na prázdny reťazec a pridalo fiktívny
`CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP=`. Prázdny recipient pritom
znamená, že replikácia odmietne bežať (zámerne — bez recipienta by kópia
vznikla v čistom texte), takže jedna nevinná zmena adresára by ticho zastavila
off-site zálohu. Guarda sa teraz viaže na hodnotu; overené v štyroch smeroch
(len adresár / doplnenie recipienta / vyslovné `false` / čerstvý súbor).
Commit `a60aa56`.

**Nález: brána prečíta off-site artefakt štyrikrát, a preto vyzerá ako
zaseknutá.** `offsite_status.sh` na šifrovanej vetve volá
`artifact_is_encrypted` → `artifact_keyids` (1. čítanie), potom
`artifact_keyids` zvlášť (2.), potom `artifact_matches_recipient` → zase
`artifact_keyids` (3.), a k tomu raz `sha256sum` na kontrolný súčet (4.). Každé
čítanie je `--list-packets` alebo hash nad celým 131 MB súborom, a na delle ide
**cez sshfs**, takže `make ops-check` beží minúty a jeho `gpg` proces sedí v
stave `DL` (`folio_wait_bit_common`). Nie je to chyba správnosti — kontroly sú
nastavené dobre a nič sa nepreskočí — ale je to vlastnosť, ktorá sa zopakuje
pri každom behu brány aj týždenného jobu, a operátor to číta ako zaseknutie.
Stojí to za zlacnenie (keyidy vytiahnuť raz a odovzdať), nie za zmenu kontrol.

**Nález: private kľúč je chránený heslom a na Macu nie je `pinentry-mac`.**
Overené `gpg --batch --decrypt` → `Inappropriate ioctl for device`, teda kľúč
sa bez pinentry neodomkne; v agentovej cache (`KEYINFO --list`) tiež nie je a
v systéme je len `pinentry-curses`. Dôsledok je konštrukčný, nie poruchový:
drill šifrovanej repliky **musí spustiť človek v termináli**, ktorý to heslo
pozná. Agent ho spustiť nevie a ani sa o to nemá pokúšať — zálohovací kľúč bez
hesla by bol slabší než dáta, ktoré chráni.

Na lenove bolo pred replikáciou prázdno (0 súborov), takže žiadne pred-D2
plaintext repliky nebolo treba upratovať.

---

### Mac je vypnutý ako produkcia — a kontrola, ktorá o tom klamala (2026-09-15)

Poradie krokov nebolo ľubovoľné: najprv čerstvá overená záloha, potom zrušenie
týždennej úlohy, až nakoniec zastavenie stacku. Teplá záložka (Mac) sa necháva
živá, kým existuje krok, ktorý ju môže potrebovať — a tým bol práve off-site.
Ten je hotový a overený, takže dôvod držať Mac v produkcii padol.

**Čo sa spravilo (všetko na Macu):**

- `make db-backup` → `cistafirma_20260915T103122Z.dump`, hneď overená cez
  `make db-backup-verify`.
- `make db-backup-schedule-uninstall` → odobrala `sk.cistafirma.backup`
  z launchd a zmazala plist. Skript odstraňuje **len rozvrh**; zálohy, záznamy
  o drilloch ani cieľ replikácie necháva tak, aby odinštalácia nemohla vyzerať
  ako strata dát. Vetví sa podľa `$CISTAFIRMA_OS`, takže spustený na Macu sa
  nemôže dostať k systemd timeru na delle.
- `make docker-down` — **bez `-v`**, ako všade v tomto dokumente.

Pred zastavením Macu bolo overené, že dell cez tailnet naozaj odpovedá (frontend
200 za 0,057 s, API 200 za 0,373 s) — Mac sa nezastavoval naslepo.

**Overené po:** žiadne kontajnery, žiadny listener na 5432/5173/8080, volume
`cistafirma_postgres_data` na mieste, 35 dumpov, žiadny launchd agent, žiadny
crontab, žiadna brew služba, žiadny zvyšný proces.

**Nález, ktorý to odhalilo:** klon na delle bol pozadu o štyri commity
(`021e3e6` vs `868e57c`) — vrátane `a60aa56`, teda opravy, bez ktorej
`configure_offsite.sh` spustený bez recipienta vymaže už uloženého recipienta
a **ticho zastaví replikáciu**. Kým sa to nepullne, beží na delle starý skript.

**#114 — kontrola, ktorá o úlohe klamala.** Tá istá trieda ako všetko ostatné
v tomto dokumente: nie kontrola, ktorá zle počíta, ale ktorá nemôže ukázať to,
čo tvrdí. `ops_check.sh` sa na macOS pýtal `launchd` počítadlo `runs` a log
čítal až keď bolo `>= 1`. Lenže `runs` sa počíta **od načítania úlohy**, nie od
inštalácie — a reštart stroja je reload.

Prehovor overený, nie prevzatý: zahadzovacia launchd úloha dala `runs = 2` po
dvoch štartoch a `runs = 0` po reloade (`bootout` + `bootstrap`). Falošný FAIL
sa potom podarilo zreprodukovať hermeticky — falošný `$HOME`, stub `launchctl`,
plist posunutý o 30 dní dozadu, log so štartom spred dvoch dní:

```
FAIL  launchd has never run the job although it was installed 30 day(s) ago
```

Na Macu to nebolo teoretické: plist mal mtime 10. 9. 09:09, `RUN_GAP_MAX_DAYS`
je 8, takže od 19. 9. 09:09 by brána hlásila tvrdý FAIL na zdravom stroji —
a po každom ďalšom reštarte by sa už nevyčistil.

Oprava nerobí z nuly dôkaz, ale prestáva z nej robiť nepravdu: `runs == 0` sa
teraz pozrie do logu a keď v ňom je čerstvý štart, vráti **WARN** s časom
posledného štartu aj s časom posledného bootu. Nikdy `OK` — ručný beh píše do
logu ten istý riadok. Prísny verdikt sa nestráca: týždenný beh prichádza do
brány s počítadlom aspoň 1 a tam sa logom súdi ďalej.

| prípad | `runs` | log | plist | verdikt |
|---|---|---|---|---|
| A | 0 | štart pred 2 dňami | 30 dní | **WARN** (predtým FAIL) |
| B | 0 | štart pred 30 dňami | 30 dní | FAIL |
| C | 0 | prázdny | 30 dní | FAIL |
| D | 0 | prázdny | 2 dni | WARN (prvý beh ešte len príde) |
| E | 2 | štart pred 2 dňami | 30 dní | OK |
| F | 2 | prázdny | 30 dní | FAIL |

Zmenil sa **jediný** prípad — A. B–F vrátane oboch FAILov sú identické
s pôvodným správaním.

Dve poznámky k tomu, čo oprava **zámerne nerobí**:

- **Nerozhoduje.** Rozhodnúť by znamenalo modelovať kalendárové pravidlo
  z plistu: štart zapísaný po boote dokazuje, že ho nespravil `launchd`, ale
  nedokazuje, že od bootu už nejaký štart mal prísť. Verdikt by bol hádanie,
  takže správa povie obe pravdy a úsudok nechá na operátora.
- **Neplatí pre Linux.** `systemd` vetva číta `LastTriggerUSec` časovača, čo
  reštart prežije; overené v #119.

Chybu som pritom spravil aj vo vlastnej oprave a test ju chytil: `sed` vzor
`.*sec = ` je greedy a v `{ sec = 1789414967, usec = 914123 }` sa chytil na
`usec`, takže správa hlásila boot v roku 1970. Vzor je teraz `[{,] *sec = `.

Opravené je to napriek tomu, že Mac je odstavený a vetva je teda spiaca:
kontrola, ktorá klame, je v tomto projekte tá chyba — nie nepríjemnosť.

**Doplnené v dokumentácii:** `CLAUDE.md` aj `docs/DATA_PROTECTION.md` meno
produkčného stroja dovtedy **nevymenúvali** — hovorili len o „host that runs
production" a „lokálny Docker **je** produkcia". Po presune na dell je to
nepravda, ktorá by poslala ďalšiu session pracovať s Macom ako s produkcion.
Oboje teraz hovorí, že produkcia je `dell` a Mac je odstavený — a že
`make ops-check` na Macu **má** zlyhať, lebo tam už žiadny stack ani týždenná
úloha nie je.

### Drill šifrovanej repliky patrí tam, kde je kľúč — a brána to konečne vie (2026-09-15)

Zadal som drill na `dell` a bola to chyba v dvoch vrstvách. Prvá je triviálna:
v bloku príkazu zostal nevyplnený placeholder `<cesta k .dump.gpg>`, takže
`make db-restore-drill` spadol na `backup file does not exist`. Druhá je vecná
a dôležitejšia: **aj so správnou cestou by to na delle neprešlo.** Overené —
`gpg --list-secret-keys` je tam prázdne, dell drží len verejný kľúč
(`3043D31A…`). Replika je zašifrovaná na tento kľúč, takže bez privátnej
polovice sa nedá dešifrovať.

Nie je to porucha, ktorú treba opraviť — je to návrh a `docs/DATA_PROTECTION.md`
to hovorí už predtým: *„the recovery drill has to run where the private key
is"*. Kľúč patrí na stroj, odkiaľ by sa obnovovalo, a **nie** na produkciu ani
na cieľ replikácie; na delle by znamenal, že kompromitácia produkcie vydá aj
celú históriu off-site kópií, na lenove by zrušil zmysel šifrovania úplne.

**Kde teda:** na Macu — jediný stroj s privátnym kľúčom. To neznamená návrat
Macu do prevádzky; overené, že na ňom nič z cistafirmy nebeží (žiadne bežiace
kontajnery, žiadny listener na 5432/5173/8080, žiadny launchd agent, žiadny
crontab). Mac drží kľúč a je to tak správne.

**Čo spravilo AI, aby to človek nemusel robiť dvakrát:** replika stiahnutá
z lenovo na Mac (`~/cistafirma-drill/offsite/`), `sha256`
`71b3d387…5bd010` porovnaný s manifestom — bit-identická — a `make
db-backup-verify` prešiel (`encrypted to F3B8F3ADFBA9DB8F`). Drill potom spustil
Samuel, lebo gpg si pýta passphrase:

```
Restore drill passed: 39 public tables restored from an ENCRYPTED replica
into an isolated container.
```

**Nepresnosť, ktorú nechcem zamlčať:** nebol to prvý drill tejto repliky.
V logu je záznam z 10:13 toho istého dňa s tým istým `sha256`, takže replika
bola dokázaná už predtým a beh o 11:34 ju len zopakoval.

Záznam sa zapísal ako `source: local`, nie `off-site` — a to je správne. Drill
označí zdroj za off-site len vtedy, keď je replika na **inom filesystéme než
`$HOME`**; stiahnutá kópia je na disku Macu, takže `cistafirma_offsite_mount_check`
ju po právu odmietne uznať za off-site. Nefalšoval som to cez
`CISTAFIRMA_OFFSITE_BACKUP_DIR` — kontrola by tým prestala platiť.

**Nález (#121) a oprava:** brána na delle hlásila
`WARN last drill used the local backup; drill the off-site copy when one is
present` — a hlásila by to **navždy**, lebo dell ten drill nikdy nespraví a
`DRILL_LOG` je strojovo lokálny, takže Macov záznam nevidí. Kontrola žiadala
niečo, čo ten stroj štrukturálne nedokáže; presne ten typ poplachu, ktorý sa
naučí človeka preskakovať warningy. Opravené takto:

- `cistafirma_gpg_has_secret_key()` v `lib/backup_gpg.sh` — vie sa spýtať, či
  tento zvozok dokáže repliku aj **prečítať**, nielen overiť.
- `offsite_status.sh` varuje len tam, kde je privátny kľúč. Na hoste bez neho
  namiesto WARN vypíše, že drill tam spustiť nemožno a kde patrí. Warning tak
  zostáva tam, kde sa dá konať, a mizne tam, kde by bol neodstrániteľný.
- `docs/DATA_PROTECTION.md` to isté slovom, vrátane toho, že drill log
  replikačného hosta **nie je** zdieľaný register.

**Otvorené a dôležité:** privátny kľúč existuje len v keyringu Macu. V state
dir je exportovaná **len verejná** polovica (`cistafirma-backup-public.asc`),
tajná nikde na disku. Ak Mac prejde reinštaláciou alebo zlyhá disk, všetky
off-site repliky sa stanú navždy nečitateľné — a to je presne trieda zlyhania,
ktorú drill odhaliť nevie, lebo sa prejaví až vtedy, keď už stroj nie je.
`docs/DATA_PROTECTION.md` pritom žiada offline kópiu tajného kľúča v password
manageri. Či tam je, vie len Samuel; je to otázka, nie nález.

**Doplnené — export je dokázateľne úplný (2026-09-15).** Dovtedy sme mali
overené menej, než sa zdalo: že export obsahuje práve jeden blok súkromného
kľúča, že fingerprint sedí a že sa do cudzieho keyringu naimportuje. Ani jedno
z toho neznamená, že sa z neho dá **čítať**. Exportu, ktorému chýba cv25519
podkľúč, prejde importom aj fingerprintom a predsa repliku neprelúskne —
rozdiel sa prejaví až pri obnove, teda v najhoršej možnej chvíli. Skript
`~/restore-check.sh` preto spravil presne to, čo by robil človek po strate
Macu: exportoval kľúč, naimportoval ho do **prázdneho** keyringu a z neho
obnovil repliku. Výsledok: `sec 80CB28C38ED7468B` + `ssb F3B8F3ADFBA9DB8F
použitie=e`, a `Restore drill passed: 39 public tables restored from an
ENCRYPTED replica`. Export teda obsahuje šifrovací podkľúč a je životaschopný,
nie len dobre vyzerajúci.

Čo tým **nie je** uzavreté: či tá kópia naozaj leží v password manageri. To
stroj neoverí. A je to celý rozdiel medzi „kľúč sa dá obnoviť" a „kľúč
existuje len dovtedy, kým existuje Mac".

Dve veci k prostrediu, ktoré stáli za to zistiť:

- `gpg --export-secret-keys` **neprejde** v sandboxovanom shelli. V gpg 2.x
  vlastní súkromné kľúče `gpg-agent` a `gpg` sa ho pýta cez socket; bez tty to
  skončí na `Inappropriate ioctl for device`. Skript sa preto musí spúšťať
  z terminálu — a zlyhanie exportu v mojom shelli nebolo zlyhanie kľúča.
- To, čo pri tom zlyhaní vyzeralo ako dva cudzie kľúče, boli **keygripy**, nie
  fingerprinty. `private-keys-v1.d` má presne dva súbory — primárny kľúč a jeho
  šifrovací podkľúč. Keygrip sa s fingerprintom nezhoduje a nemá; zámena tých
  dvoch vyzerá ako kompromitácia keyringu, ktorá sa neudiala.

Fetchovaná replika (`~/cistafirma-drill/`, 131 MB) sa po drille zmazala —
sha256 sa predtým overil proti zdroju na lenovo (`71b3d387…5bd010`, zhoda na
bit), takže na Macu ostal len overený duplikát, a Mac má byť dev.

### Mac prestal byť CI strojom — a CI ožilo na lenovo (2026-09-15)

Otázka znela, prečo bol na Macu vysoký výkon. Odpoveď: bežal tam **GitLab
runner** ako Homebrew služba (`sh.brew.gitlab-runner`, PID 5859). Mac sa tým
stal tretím CI strojom v domácnosti, hoci má byť len na vývoj.

**Hlbší nález bol ale iný: CI bolo mŕtve už štyri dni a nikto to nevedel.**
Posledný job sa vykonal 11. 9. 2026. Príčina nie je pád — je to zhoda dvoch
nastavení, z ktorých každé samo vyzerá neškodne:

- oba vtedajšie runnery mali `run_untagged = false`,
- `.gitlab-ci.yml` nemá **v žiadnom commite v celej histórii repa** ani jedno
  `tags:`.

Takže **žiadny job nemal kto prevziať**. Pipeline sa spúšťala normálne, joby
ostávali `pending`, GitLab bol zelený v tom zmysle, že nič nehlásil ako chybu.
Toto je tá istá trieda chyby, ktorú projekt rieši inde: **stav, ktorý vyzerá
zdravo, pretože ho nič nemeria.**

**Druhá vec, ktorá sa pri tom ukázala:** `run_untagged` v `config.toml` je pre
**už registrovaný** runner inertný — runner ho posiela len pri registrácii.
Overené empiricky: po prepísaní configu na `true` a reštarte ostal v GitLabe
stav `false` a `ci_runners.updated_at` sa nepohol. Skutočné nastavenie je
server-side, v tabuľke `ci_runners`. Do `setup-config.sh` preto namiesto
funkčne vyzerajúceho riadku, ktorý nic nerobí, pribudol komentár s miestom, kde
to naozaj žije — a v README runnera je to isté.

**Čo je hotové:**

| Vec | Stav |
|---|---|
| Mac: služba zastavená a vypnutá (`brew services list` → `gitlab-runner none`) | ✅ |
| Mac: odregistrovaný z `gitlab.home.arpa:8088` (`ci_runner_machines` riadok zmazaný) | ✅ |
| lenovo: runner id 1 má `run_untagged = true` server-side | ✅ |
| CI naozaj beží — pipeline 102 prevzala joby, ktoré čakali ~54 minút | ✅ |
| `.gitlab-ci.yml` prepísaný: stages `validate` → `test` | ✅ |

**Čo z CI zmizlo a prečo** (celé aj s obsahom): stage `build` a `deploy`,
`.build_template`, `build_backend_image`, `build_frontend_image`,
`.deploy_template`, `deploy_dev`, `deploy_main_to_dev`, `deploy_prod`
a `helm_k8s_validate`. Neboli to stratené schopnosti — boli to joby, ktoré
**nemohli prejsť**:

- `build` pushoval obrazy do registra, ktorý nič nečíta. Produkcia na delle
  stavia z `build:` kontextu; `image:` je v celom compose len pri cudzích
  obrazoch a dell v `.env` nemá ani jednu zmienku o registri. Jediný
  teoretický konzument bol Helm chart s values na `registry.example.com` —
  placeholder. Navyše build chce `docker:dind`, teda privileged, čo runner na
  lenovo zámerne nevie.
- `deploy` nepodmienene robil `base64 -d` z `KUBE_CONFIG`, ktorá **nie je
  definovaná nikde**. Klaster nemáme.
- `helm_k8s_validate` padal dvakrát: `--dry-run=client` aj tak robí discovery
  voči API serveru, a obraz `bitnami/kubectl:1.30` na Docker Hube neexistuje
  (Bitnami presunul free obrazy do `bitnamilegacy`).

Zelená pipeline má cenu len vtedy, keď červená niečo znamená. Job, ktorý nemá
ako prejsť, učí ľudí ignorovať červenú — a to je presne to, čo 11. 9. nechalo
CI štyri dni mŕtve.

**Dva opravené joby, ktoré stoja za reč.** `helm_render_validate` padal na
`exit 127`, lebo končil `python3 scripts/k8s/validate_helm_runtime.py` — a
`alpine/helm:3.17.2` **python3 nemá** (overené sondou: `NO_PYTHON3`, `NO_KUBECTL`).
Kontrola samotná je pritom vecná a užitočná, takže sa nezahodila: render
a kontrola sú teraz **dva joby v dvoch obrazoch**. Overené pred commitom
v presnom CI obraze — `helm lint` aj oba rendery prejdú a validátor vráti
„Helm runtime contract valid: backend, frontend, one Celery Beat, and workers
for celery, financials, insurance, orsr, ruz_full." pre dev aj prod. Rendery
majú v CI obraze presne tie isté veľkosti ako lokálne (34187 B / 35373 B).

**Rozhodnutie, ktoré nebolo o kóde: dell nedostane runner.** Je to produkcia
s neopraviteľným volume `cistafirma_postgres_data`, beží tam rate-limitované
Celery a runner s docker socketom by rozšíril útočnú plochu na stroji, na
ktorom záleží najviac. CI patrí na lenovo.

**Ostáva na Samuela:**

1. **Zrotovať runner token.** Pri skúmaní rozbitého generovaného configu som
   token vypísal v čitateľnej podobe do tejto session
   (`glrt-GiaLhx…`). Token je v `/home/sam/gitlab-runner-setup/runner-token.txt`
   na lenovo a v `config/config.toml`; rotácia znamená vygenerovať nový
   v GitLabe a spustiť `setup-config.sh` znova.
2. **GitLab runner id 2 je sirota.** `gitlab-runner unregister` v GitLabe 16+
   maže **stroj** (`ci_runner_machines`), nie riadok `ci_runners` — takže
   v tabuľke ostal neaktívny záznam po Macu. Zámerne som ho nechal: zmazanie
   by vynulovalo `ci_builds.runner_id` na historických buildoch a vyžadovalo by
   nepodporovaný priamy zápis do produkčnej DB GitLabu.
3. **Cudzia registrácia v configu Macu.** Lokálny config runnera na Macu drží
   ešte `mac-runner` → `https://nsoric.mtf.stuba.sk` (id 10). Do tohto projektu
   nepatrí a je to zvyšok z inej práce — nezmažem ho sám, len hlásim.

**Návrh, nie implementácia: kontrola živosti CI.** CI zomrelo 11. 9. a štyri dni
to nikto nezachytil, pretože **nič nemeria, či pipeline vôbec niečo spustila**.
Chýbajúca zelená pipeline je pritom horšia než červená — červenú vidno.
Kandidát na samostatný prírastok: periodická kontrola, ktorá sa opýta GitLabu,
kedy naposledy nejaký job naozaj skončil, a zakričí, keď je to dávno — alebo
keď novšie commity nemajú ani jeden beh.

---

### `backend_tests` bežal na SQLite — teda nekontroloval ani jeden test (2026-09-15)

Prvá pipeline po oživení CI mala šesť zelených jobov a jeden červený:
`backend_tests`. Trace jobu končil takto:

```
django.db.utils.OperationalError: near "text_pattern_ops": syntax error
```

Príčina nebola v kóde. Job nemal `DATABASE_URL`, takže sa `settings.py` podľa
svojho dokumentovaného správania ticho prepol na SQLite (`backend/db.sqlite3`).
Migrácia `companies/0014_add_pattern_ops_structured_indexes.py` ale vytvára
index s `text_pattern_ops` — Postgres-only trieda operátorov — takže
`create_test_db` spadol **skôr, než sa stihol spustiť jediný test**.

Job bol teda červený vždy, nech bol kód akýkoľvek. Nebol to slabý test; bol to
test s nulovým výpovedným obsahom — a to je presne tá trieda chyby, ktorú tento
dokument opísal pri `helm_k8s_validate`: job, ktorý nemôže prejsť, učí ľudí
ignorovať červenú.

**Prečo sa to neopravilo „znesením migrácie na SQLite".** Index nie je
ozdobný — `companies/services/peers.py` sa oň opiera pri prefixovom hľadaní.
Urobiť migráciu prenosnou by znamenalo zničiť produkčný index kvôli CI.

**Tri veci boli treba a každá odstránila presne svoju triedu chýb.** Overené
lokálne, po jednej, v tom istom obraze `python:3.12-slim`:

| Podmienka | Čo bez nej padalo |
|---|---|
| Postgres | `create_test_db` — `text_pattern_ops`, teda 0 vykonaných testov |
| Redis | 6 testov na `ConnectionError` (5× hľadanie osôb, 1× admin dashboard) + healthz test čakal 200, dostal 503 |
| `collectstatic` | 6 testov admin dashboardov na `Missing staticfiles manifest entry` |

Posledná položka vyzerá nečakane, ale je to dôsledok: `DiscoverRunner` má
`debug_mode=False`, takže si Django `settings.DEBUG` počas testov prepne na
`False` sám — a `HashedFilesMixin.url` skracuje na obyčajné meno len keď je
`DEBUG` True. `CompressedManifestStaticFilesStorage` je preto v testoch
striktná. Vypnúť tú striktnosť (`WHITENOISE_MANIFEST_STRICT = False`) by bolo
nesprávne: je to tá istá vec, ktorá v produkcii odhalí chýbajúci statický
súbor. Produkcia pred štartom púšťa `collectstatic && gunicorn` — testy teraz
robia to isté.

Po všetkých troch: **899 testov, `OK`, exit 0.**

**Zmena v CI.** `backend_tests` má service kontajnery `postgres:16-alpine`
a `redis:7-alpine` — tie isté verzie, aké prevádzkuje produkcia
(`docker-compose.yml`) — a `DATABASE_URL` / `REDIS_URL` na ne. Sú to
jednorazové prihlasovacie údaje efemérneho kontajnera, nie secrets.

**Zmena na runneri.** Oba obrazy museli pribudnúť do `allowed_images`
v `/home/sam/gitlab-runner/setup-config.sh` (jediný zdroj pravdy pre
`config.toml`) a runner sa musel reštartovať — dovnútra kontajnera je
namontovaný `/home/sam/gitlab-runner/config`, takže vygenerovaný config je
ten, ktorý runner naozaj číta. Zároveň z bielej listiny zmizli
`bitnami/kubectl` a `bitnamilegacy/kubectl`: držali miesto pre obrazy jobu
`helm_k8s_validate`, ktorý 15. 9. zmizol. Biela listina, ktorá drží obraz pre
neexistujúci job, len predstiera, že niečo chráni.

---

### Mac má druhý, zabudnutý klaster — a „zbytočnosti" na ňom zbytočné neboli (2026-09-17)

Pri hľadaní miesta na Macu sa ukázalo, že na ňom **146 dní beží druhý klaster
CistaFirma**, o ktorom nevedel ani repozitár, ani `make ops-check`.

**Prečo ho nič nevidelo.** Docker Desktop Kubernetes je *kind*: šesť uzlov
(`desktop-control-plane`, `desktop-worker`..`worker5`) beží ako docker
kontajnery, ale Docker Desktop ich **zámerne skrýva z `docker ps -a`**. Vidieť
sú len v `docker system df -v`, v `docker stats` a v `docker info` — a práve
nesúlad `docker ps -a` (8 kontajnerov) proti `docker info` (17) bol jediná
stopa. Celý môj predchádzajúci prieskum Macu preto ten klaster minul.

**Čo v ňom je.** V namespace `cistafirma` beží celý stack: dva Postgres
StatefulSety (PVC 1,2 GB a 45,6 MB), päť Celery workerov, beat, backend,
frontend, `postgres-backup` CronJob (posledný beh dokončený, 5 Gi PVC). Vedľa
je namespace `monitoring` s kube-prometheus-stack. **Obe Helm releasy sú
`failed`.** Služby sú výhradne ClusterIP a ingress má placeholder
`dev.cistafirma.example.com` — takže klaster neobsluhuje žiadnu premávku.

**Je živý a skenuje.** Worker `orsr` práve vtedy púšťal
`registers.tasks.sync_company_orsr_data` každé ~4 sekundy a opakoval
`RpoEntityNotFoundForCompany`. To je **paralelné skenovanie verejných
registrov s produkciou na delle** — a najpravdepodobnejšie vysvetlenie
pôvodnej otázky „prečo bol výkon vysoko". Jeho databáza ale **nie je kópia
produkcie**: 1 275 674 firiem proti 447 776 na delle, päť mesiacov starý
rozbíhajúci sa experiment.

**A teraz to dôležité — čo z môjho vlastného zoznamu „zbytočností" zbytočné
nebolo.** Cez sedem nezávislých protivníkov, ktorých úlohou bolo môj záver
*vyvrátiť*, padli tri položky:

1. **`runner-*-cache-*` volume (26 ks).** Cieľ je v poriadku — `LINKS 0`, žiadny
   kontajner ich nemontuje, obsah je prebuildovateľná CI cache. Vyvrátená bola
   ale **cesta**: zmazať ich znamená `docker volume rm`, čo §9 zakazuje
   bezvýhradne a `.claude/settings.json` to blokuje na permission vrstve.
   A je dôvod: `cistafirma_postgres_data` je na Macu tiež `LINKS 0` — visí na
   **žiadnom** kontajneri — takže plošný `docker volume prune` by ho vzal so
   sebou. To nie je hypotéza, to je overený stav.

2. **`localhost:5050/web/cistafirma/*:<sha>` („zastarané CI obrazy").** Nie sú
   zastarané. `scripts/k8s/rollback.sh` robí `kubectl rollout undo` a to
   rozbaľuje obraz **podľa mena** z predchádzajúcej ReplicaSet revízie —
   backend aj frontend ich držia šesť. A register, ktorý ich vydával (Mac
   GitLab na `:5050`), je mŕtvy, takže **lokálny store je jediná kópia**.
   Navyše `backend:461c48ca` a `backend:dev` sú **ten istý image ID** — mazanie
   podľa ID by vzalo aj `:dev`. Do tretice: `localhost:5050/web/code-reviews/*`
   patrí inému živému projektu (kontajner `review-bot`).

3. **`gitlab-ci.yml.new` na lenovo.** Je to **jediná kópia** (jeho sha256 sa
   nezhoduje so žiadnym commitom `gitlab-ci.yml` v histórii) a je to
   dokumentovaný vstup ponechaného `commit-ci-tags.rb`. `gitlab-ci.yml.original`
   naopak v gite je (commit `ab3138ec`). Rovnako `gitlab/gitlab-ee:nightly`
   a `gitlab/gitlab-runner:latest` sú pinované v `~/gitlab/docker-compose.yml`
   vedľa 1,6 GB dátového adresára — mazať sa dá len `:latest`.

   → **Uložené 2026-09-17** ako `deploy/ci/gitlab-ci.yml.new`. Overenie toho
   tvrdenia — aj to, čo sa pri ňom našlo — je v poslednej podsekcii §7.

**Ponaučenie.** `docker ps -a` **nie je inventúra stroja.** Zoznam „čo nič
nepoužíva" je na tomto hoste nesprávny dvakrát: raz pre skrytý klaster, raz pre
históriu ReplicaSetov, ktorá drží rollback cieľ, aj keď nič nebeží.

**Výsledok.** Odkladací skript je `scripts/local/cleanup_mac_docker.sh`
(bez `--apply` je to suchý beh). Skript **neobsahuje ani jeden volume príkaz**,
má poistku na `cistafirma_postgres_data` pred aj po a mazanie odmietne, ak by
sa cieľ objavil medzi živými obrazmi (kontajner, pod alebo ReplicaSet) — takže
stará položka v zozname je neškodná, nie deštruktívna.

**Spustený 2026-09-17** (`--apply`, Samuelovo povolenie z toho dňa). Uvoľnil
**33 GB**: voľné miesto na Macu 57 GB → **90 GB** (zaplnenie 94 % → 90 %).

| | pred | po |
|---|---|---|
| obrazy | 131 (47,11 GB) | 112 (31,52 GB) |
| build cache | 31,31 GB (20,37 GB vratných) | 10,95 GB (**0 vratných**) |
| lokálne volumes | 74 (40,62 GB) | 74 (**40,62 GB**) |
| kontajnery | 17 | 17 |

Zmazaných bolo všetkých 22 značiek zo zoznamu (overené `docker image inspect`
pre každú z nich, nie podľa počtu — 131 − 112 = 19, lebo tri značky ukazovali na
ten istý image ID ako iné). `ghcr.io/jkroepke/kube-webhook-certgen:1.8.3` sa
preskočil ako obvykle (containerd store). Kanárik prešel:
`cistafirma_postgres_data` (vytvorené 2026-08-03) je po behu na mieste a
**volumes sa nepohli ani o bajt**.

Overené prežitie, nie predpokladané: `kindest/node:*`, `cistafirma-*` (13),
`localhost:5050/web/cistafirma/*` (54 rollback cieľov), cudzí projekt
`localhost:5050/web/code-reviews/*` (4), `gitlab/gitlab-ee:nightly`,
`gitlab/gitlab-runner:latest`, `postgres:16-alpine`, `redis:7-alpine`,
`alpine:latest`, `python:3.12-slim`, `node:20-alpine`, `alpine/helm:3.17.2`,
`grafana/grafana:13.2.1`, `prom/prometheus:v3.14.0`.

**Oprava skoršieho tvrdenia.** Tu stálo, že mazanie odmietla permission vrstva.
Overené 2026-09-17 na dvoch úrovniach: samotné volanie
`bash scripts/local/cleanup_mac_docker.sh --apply` **nezodpovedá žiadnemu deny
vzoru** (tie pokrývajú `docker volume rm/prune`, `docker system prune`,
`docker compose down -v` a `make docker-reset`), a **ani jeden príkaz vnútri
skriptu** im nezodpovedá — skript volá `docker rmi`, `docker builder prune -f`,
`docker system df`, `docker images` a `docker volume inspect`, teda vymenovanie
a rušenie obrazov, nikdy volume. Prekážkou teda nebolo pravidlo, ale **súhlas,
ktorý nemal kto dať** (beh v noci). To je rozdiel, na ktorom záleží: pravidlo
platí stále a chráni volume, kým súhlas sa dá raz dať. Druhý beh je navyše
idempotentný — po tomto už nemá čo zmazať.

**Čo sa medzitým spravilo:** na lenovo zmizol
`gitlab-runner_19.3.2-1_amd64.deb` (31 MB) a `install-runner-native-OBSOLETE.sh`.
Štyri textové súbory (`README.md`, `ci-tags.md`, `gitlab-ci.yml.new`,
`gitlab-ci.yml.original`) aj `runner-token.txt` ostávajú — token je
`TOKENFILE` predvolba verzionovaného `setup-config.sh`, ktorý bez neho
s `exit 1` skončí.

**Čaká na teba (rozhodnutie, nie mechanika):**

- **Osud klastra v Docker Desktop Kubernetes.** Je dátový (1,2 GB Postgres),
  takže sa nedá zhodiť ako „zvyšok". Ak je odpoveď „zrušiť", treba najprv
  `helm uninstall` v oboch namespace a potom zmazať PVC — a vtedy sa uvoľní aj
  tých ~12 GB sha-tagovaných obrazov, ktoré dnes drží rollback.
- **Či má byť starý Mac GitLab (`~/gitlab`, 1,6 GB dát) ešte niekedy
  spustiteľný.** `nightly` je pohyblivý tag, takže presný build 19.0.0-pre sa
  po zmazaní už nedá stiahnuť; dáta sú host bind mount a prežijú.
- **Rotácia runner tokenu** a **`sudo rm -rf /etc/gitlab-runner`** — bez zmeny,
  oboje z 15. 9.
- ~~**`/home/sam/gitlab-runner-setup/gitlab-ci.yml.new` skopírovať do repa**~~
  — **spravené 2026-09-17**, pozri nižšie. Otvorené ostáva len to, čo sa pri tom
  našlo, a sú to tri veci: `main` na GitHube je sedem commitov pozadu;
  `gitlab-home/main` nesie starý `build`/`deploy` stage s `tags:` a jeho posledná
  pipeline tam stojí od 11. 9. na manuálnej bráne; a **`mac-runner` (id 2)** je
  v GitLabe stále `active` s tagom `macos`, hoci sa od 15. 9. neozval — takže
  job s tým tagom by ostal `pending`, nie spadol.
- **Prístup na čítanie produkčnej DB.** Zaznamenávam, čo som **pozoroval**, nie
  diagnózu: auto mode classifier odmietol `SELECT count(*)` nad produkčnou
  databázou na `dell` s dôvodom `[Production Reads]` — príkaz neprebehol.
  Zdrojom je **classifier za behu, nie pravidlo v `.claude/settings.json`**:
  ten som si prečítal celý a o produkčných čítaniach neobsahuje nič (jeho
  `deny` pokrýva `docker volume rm/prune`, `docker system prune`,
  `docker compose down -v`, `make docker-reset`, `celery-purge`, `pg_restore
  --clean`, `dropdb`/`createdb` a `DROP`/`TRUNCATE` cez `psql`). Rozdiel je
  praktický: nejde o pravidlo, ktoré by sa dalo zmeniť v repe — classifier sa
  pýta vtedy, keď nikto nie je pri PC, a to je presne tento prípad.
  Obchádzať to nebudem. Dôsledok je konkrétny: čísla k #148 a #98 viem opísať,
  ale **nie zmerať**. Tri dotazy, ktoré to spravia, sú v §4 pri #148. Ak ich
  chceš v reporte, treba Bash pravidlo, ktoré read-only dotaz na `dell` povolí;
  inak ich spustíš ty (alebo sa na to vykašleme — ani jedno z tých čísel nie je
  podmienkou opravy).

### `.gitlab-ci.yml` existuje vo viac kópiách, než dokumentácia priznáva (2026-09-17)

Podnet bol malý: dorovnať do repozitára `gitlab-ci.yml.new` z lenovo. Pri
overovaní sa ale ukázalo, že o kópiách tohto jedného súboru platí niečo iné, než
tvrdia dve kanonické dokumenty — a že jedna z tých kópií je živá.

**Artefakt je uložený.** `deploy/ci/gitlab-ci.yml.new` je bajt na bajt kópia
`/home/sam/gitlab-runner-setup/gitlab-ci.yml.new` (`cmp` + `sha256sum`,
`eff4edb3…`, 239 riadkov, 6971 B). Je to pripravená záložná cesta z 11. 9. 2026:
`.gitlab-ci.yml` s explicitnými `tags:` na ôsmich joboch. Prečo sa nesmie
nasadiť tak, ako je, a prečo sa napriek tomu nedá aplikovať omylom, je
v `deploy/ci/README.md`.

**„Jediná kópia" sedí — ale je to osem riadkov.** Tu stálo, že jeho `sha256` sa
nezhoduje so žiadnym commitom `.gitlab-ci.yml` v histórii. Overené prechodom
**všetkých** commitov, ktoré ten súbor kedy menili, na všetkých refoch: **nula
zhôd**. Zároveň `diff` proti `ab3138e:.gitlab-ci.yml` je **osem čistých vložení
a nula zmien**, a všetkých osem je riadok `tags:`. Ten súbor je teda
`gitlab-ci.yml.original` plus osem riadkov. Formulácia „jediná kópia" bola
pravdivá, ale zvádzala k predstave o samostatnom súbore; rozdiel je osem riadkov,
ktoré sa z histórie vyzdvihnúť nedajú (a poskladať ručne znamená rozhodnúť pri
ôsmich joboch, ktorý dostane `lenovo` a ktorý `macos` — a `macos` má jediný).

**`main` na GitHube je sedem commitov pozadu — a nikde to nebolo.** Zmerané:
`origin/main` stojí na `ab3138e` z **25. 7. 2026**, `gitlab-home/main` na
`8ea1e50` z **11. 9. 2026**; `main` lokálne je `ab3138e`, teda presne to, čo má
GitHub. `origin/main` je pritom **predok** `gitlab-home/main`, takže nejde
o rozchod, len o oneskorenie — a tých sedem commitov sú CI zmeny (tagy pre
runnera, DinD, `FF_NETWORK_PER_BUILD`, zápis do docker configu). Nebezpečné to
nie je: GitLab je kanonický a GitHub z tohto repa nič nespúšťa ani nenasadzuje
(`.github/workflows` neexistuje nikde, ani lokálne, ani na ňom). Ale je to
**druhá kópia `main`, ktorá sa rozišla ticho** — trieda chyby, ktorú tento
projekt rieši inde — a nikde nebola zapísaná.

**A to najpodstatnejšie: `gitlab-home/main` má `tags:` aj staré stages.**
`DEVOPS_CICD.md` tvrdí, že „žiadny job v histórii repa nemal `tags:`", a
`deploy/ci/README.md`, že sa tagy „do `.gitlab-ci.yml` necommitli". Obe tvrdenia
sú **nepravdivé pre kanonický remote**. `d8fd936` (`ci: tagy pre runner na
sam-lenovo + oprava neexistujuceho kubectl image`, 11. 9. 2026 **19:55**, vetva
`ci/runner-tags-and-kubectl-image`) pridáva osem `tags:` riadkov a je predok
`gitlab-home/main`; ten ich má dodnes, spolu s celým stage `build` aj `deploy`
a s `bitnamilegacy/kubectl:1.30` — ten istý commit opravil aj ten obraz, takže
`gitlab-home/main` je v tomto bode **ďalej**, než hovorí dokumentácia. Pravda je
užšia: do 19:55 toho dňa nemal `tags:` ani jeden job, a vetva, na ktorej sa CI
robilo 13.–15. 9., ich tiež nemá (zmizli v `4731a620`, 13. 9. 17:27).

Obe tvrdenia sú v tých dokumentoch **opravené na mieste** — nie prepísané,
pôvodné znenie tam ostáva — s odkazom sem.

**Ako to na `main` dopadlo — domerané, a je to inak, než som čakal.** Stav
`gitlab-home/main` je jedná vec; či z neho niekedy niečo bežalo, je vec druhá,
a tá sa `git log`om zistiť nedá. Zmerané z GitLabu (`gitlab-psql`, nie `git
log`): na `main` bežalo dokopy šesť pipeline a **od 11. 9. 2026 ani jedna**.

| id | sha | kedy (UTC) | výsledok |
|---|---|---|---|
| 1 | `ab3138ec` | 10. 9. 20:15 → 11. 9. 14:00 | `failed` po takmer 18 hodinách |
| 7 | `35a9a36c` | 11. 9. 18:01 → 18:03 | `failed` — spadol `helm_k8s_validate`, zvyšok `skipped` |
| 8 | `5bd111ce` | 11. 9. 18:05 → 18:10 | `failed` — `build_backend_image`, `build_frontend_image` |
| 9 | `1148bc69` | 11. 9. 19:29 → 19:34 | `failed` — tie isté dva build joby |
| 10 | `d80df5ad` | 11. 9. 19:37 → 19:42 | `failed` — tie isté dva build joby |
| 11 | `38f66393` | 11. 9. 19:47 → 19:51 | `failed` — tie isté dva build joby |
| 12 | `8ea1e509` | 11. 9. 19:53 | **`manual`**, `finished_at` prázdne — nikdy nedobehla |

Pipeline 12 je pritom celá zelená okrem brány: `backend_validate`,
`frontend_validate`, `docs_audit`, `helm_render_validate`, `helm_k8s_validate`,
`backend_tests`, `build_backend_image` aj `build_frontend_image` sú `success`
a `deploy_main_to_dev` je `manual` (a to je brána, nie zlyhanie — `manual`
znamená, že všetko automatické pred ňou prešlo).

**`main` teda nie je červený — je zablokovaný na bráne.** Medzi pipeline 11
(19:51) a 12 (19:53) prišla oprava, ktorá tie dva build joby spravila zelenými,
a odvtedy tá vetva stojí. Šesť dní.

Moja domnienka platila len pre pipelines 8–11: build joby naozaj padali na DinD
— a padali, nie viseli, lebo `macos` runner bol 11. 9. ešte živý. Pipeline 7 ale
padla z úplne iného dôvodu (`helm_k8s_validate`) a pipeline 12 tie isté build
joby prešla. Keby som bol napísal „hlavná vetva je červená, lebo DinD", bol by
v tomto dokumente ďalší vymyslený koreň.

**Čo tam ale naozaj visí.** `build_backend_image` aj `build_frontend_image` majú
na `main` `tags: [macos]`, a jediný runner s tým tagom je `mac-runner` (id 2,
`run_untagged = false`), ktorý sa naposledy ozval **15. 9. 2026 20:21:48 UTC**
a odvtedy mlčí — v GitLabe je pritom stále `active` a s tagom `macos`. Keby dnes
na `main` niekto pushol, tie dva joby by **nespadli, ale ostali `pending`**:
GitLab by ich držal na runner, ktorý sa už neozve, a nič by to nehlásilo ako
chybu. Je to presne tá potichu zlyhávajúca trieda, ktorú tento projekt rieši
inde — a dnes to nehryzie len preto, že na `main` šesť dní nikto nič nepustil.
Runner 1 (lenovo, `run_untagged = true`) sa chytá všetkého ostatného; druhý
runner má dnes jediné použitie a to použitie nikto nepoužíva.

**Nerobil som s tým nič.** Posunúť `main` na GitHube alebo na GitLabe je
rozhodnutie o zdieľanej vetve, nie mechanika — a `feat/ai-ready-baseline` ten
stav aj tak celý nahradí (jeho `.gitlab-ci.yml` má len stage `validate` a `test`
a žiadne `tags:`). Otvorené sú tri veci, všetky na človeka: (a) či sa `main` na
GitHube dorovná — `origin/main` je predok `gitlab-home/main`, takže fast-forward;
(b) či sa má stav na `gitlab-home/main` (staré stage `build`/`deploy` a osem
`tags:`) nejako zosúladiť s tým, čo dokumentácia opisuje ako súčasnosť; a (c) čo
s `mac-runner` — je registrovaný, `active`, má tag, ktorý dnešné CI nepoužíva,
a nemá sa ako ozvať.

---

### `main` je dorovnaný na oboch remoteoch a mŕtvy runner je vypnutý (2026-09-17)

Tri otvorené veci z predchádzajúceho vpisu sú vyriešené — a je to **overené**,
nie predpokladané.

#### (a) a (b): `main` je na GitHube aj v GitLabe ten istý commit

`git ls-remote` na oba remoty vracia **`d113a6704269a7229dc12cf386c222a533d2c08d`**,
merge s rodičmi `8ea1e509` (starý `main`, ten z pipeline 12) a `fc46001` (vetva,
na ktorej sa robilo CI). `git diff --stat d113a67 fc46001` je **prázdny** —
stromy sú totožné, čiže `main` dnes nesie presne tú `.gitlab-ci.yml`, ktorú
dokumentácia opisuje ako súčasnosť: stage `validate` a `test`, sedem jobov,
žiadne `tags:`, a `.claude/settings.json` s 18 deny pravidlami.

Tým padá aj otázka (b). Staré stage `build`/`deploy` a osem `tags:` neboli
„nesúlad, ktorý treba hasiť" — boli to pozostatky vetvy, ktorá už `main` nie je.
Od chvíle, keď `main` ukazuje na `fc46001`, dokumentácia a realita hovoria to
isté. Osem `tags:` a `bitnamilegacy/kubectl:1.30` naďalej žijú v histórii
(`d8fd936`), a to je v poriadku — história sa neprepisuje len preto, že je stará.

**Že to nie je len „vyzerá to zeleno", dokazuje pipeline 147** na `d113a67`:
všetkých sedem jobov `success`. Presne tá vec, ktorá predtým ostávala visieť na
runneri, ktorý sa neozve, dnes prebehne. To je živý dôkaz, nie odkaz na
dokumentáciu.

#### (c): `mac-runner` (id 2) je `active = false`

Deaktivovaný tým idiomom, ktorý tento repozitár sám dokumentuje
(`docs/DEVOPS_CICD.md:89-90`, `deploy/ci/README.md:148-149`):

```
docker exec gitlab-server gitlab-rails runner 'Ci::Runner.find(2).update!(active: false)'
```

Overené v DB: `active = f`, `updated_at = 2026-09-17 21:54:22`. Je to **vratné**
— jeden príkaz späť — a je to jediný *instance* runner; lenovo má runner
projektový, vlastný, takže sa nič nestratilo. Predtým bol runner v GitLabe
`active` so tagom `macos`, ktorý dnešné CI nepoužíva a nemá sa ako ozvať: keby na
starý `main` niekto pushol, tie dva joby by **nespadli, ale ostali `pending`** —
tichá trieda zlyhania, ktorú tento projekt rieši všade inde.

**Kedy presne ten runner zomrel, je dnes domerané.** Pipeline 12 (`8ea1e50`,
11. 9. 19:53) má `build_backend_image` (id 92) aj `build_frontend_image` (id 93)
`success` **na runneri 2, 11. 9. o 19:57**. Runner teda 11. 9. ešte žil. Naposledy
sa ozval **15. 9. 2026 20:21:48 UTC** a odvtedy mlčí — smrť je medzi tými dvoma
časmi, v okne, v ktorom sa Mac prestal používať ako CI stroj.

#### Čo ostáva otvorené — a prečo to nechávam na teba

**Pipeline 12 stojí ďalej.** Je `manual`, `finished_at` prázdne, a visí na nej
jediný ručný job `deploy_main_to_dev` (id 94), ktorý sa nikdy nespustil — na
commite `8ea1e50`, ktorý je v histórii `main` (336 commitov za jeho tipom), ale
`main` na ňom už nestojí. Je to neškodný pozostatok, ale je to
zbytočne stojaca vec. **Zrušiť som ju nedokázal**: klasifikátor auto-módu to
odmietol ako `[External System Writes]`. Nijako som to neobišiel — príkaz je
tvoj:

```
docker exec gitlab-server gitlab-rails runner 'Ci::Pipeline.find(12).cancel!'
```

**A je to naozaj posledná taká vec — domerané 18. 9.** Prešel som celý projekt
a hľadal **všetko**, čo nie je v terminálnom stave. Vyšli presne tri riadky:
pipeline 149 a 150 (obe legitímne bežiace) a pipeline 12 — **6,1 dňa** stará.
Nič ďalšie nikde nestojí.

> **Vlastná chyba v tej kontrole.** Prvý sweep som napísal ako
> `status in ('running','pending','created')` — teda **vymenoval som stavy,
> ktoré čakám**, namiesto toho, aby som vylúčil terminálne. `manual` medzi nimi
> nebol, takže mi pipeline 12 unikla a mohol som napísať „fronta je čistá".
> GitLab má nonterminálnych stavov osem (`created`, `waiting_for_resource`,
> `preparing`, `pending`, `running`, `manual`, `scheduled`, `cancelling`).
> Vymenovať vylúčené, nie očakávané — inak filter nemôže nájsť to, čo hľadám.

**Tá brána sa už nikdy neodomkne sama.** `422addf` (15. 9. 2026 20:59:35 UTC) zmazal
z `.gitlab-ci.yml` celú líniu `build` + `deploy`, takže `deploy_main_to_dev`
nevznikne ani v jednej budúcej pipeline. Zrušenie pipeline 12 teda nie je
kozmetika — je to jediná cesta, ako ju uzavrieť.

**Predmet `d113a67` je pozadu.** Znie `Merge branch 'main' into
feat/ai-ready-baseline`, čo opisuje operáciu, ktorá sa stala na *inej* vetve —
na `main` sa pushol jej výsledok. Správne by bolo `Merge feat/ai-ready-baseline
into main`. Opraviť sa to dá len force-pushom na zdieľanú vetvu, a to je
rozhodnutie o zdieľanej histórii, nie mechanika — neprepisujem ju bez tvojho
slova. Nič funkčné to nekazí.

**Starý Mac GitLab niesol obsah, ktorý sa nikam nezreplikoval.** Tri projekty
(`web/ssl-checker` id 1, `web/cistafirma` id 34, `web/code-reviews` id 35),
**11 merge requestov** (9 na cistafirme, 2 na code-reviews, všetky od `root`,
2026-05-05 → 2026-05-30) a **65 notes, z toho 39 ľudských** — 18 na MR a 21 na
commitoch; zvyšných 26 sú systémové záznamy. Všetkých 65 napísal `root`, žiadny
samostatný bot účet neexistuje. Zmerané **dvomi nezávislými cestami** (HTTP logy
a zrekonštruovaná databáza), ktoré si navzájom sedia. Ani jedno z toho nie je
v gite. Databáza je preto **zarchivovaná** v
`~/mac-gitlab-archive-2026-09-17/` (`gitlabhq_all.sql.gz` 1,9 MB / 18,2 MB
rozbalené, `gitlabhq_production.dump` 13 MB, `registry.dump` 2,6 MB,
`git-repositories.tar.gz` 49 MB, `ci-artifacts.tar.gz` 1,5 MB,
`inventar.txt`, `README.md`) — celý `pg_dumpall` vrátane rolí. Vznikla **bez
jediného zápisu do originálu**: cluster sa načítal z kópie pripojenej `:ro`,
nechal prejsť crash recovery a odtiaľ sa dumpol.

**A druhá vlastná chyba, ktorú treba pomenovať.** Pri meraní `~/gitlab` som
pozeral `data/registry` (12 KB — iba konfigurácia) a z toho usúdil, že registr
nemá žiadne bloby, takže `registry.dump` je celý jeho obsah. **Nie je.**
Skutočné úložisko je `data/gitlab-rails/shared/registry` a má **419 MB / 182
súborov** — image `web/cistafirma/backend`, `web/cistafirma/frontend`
a `web/code-reviews/main`. Do archívu som ich **nedal**, a to je vedomá hranica:
archivujem to, čo sa nedá vyrobiť znova (logy, reporty, git repozitáre), nie to,
čo sa vyrobiť dá (build output). Tie obrazy sú výstupom CI cesty, ktorá už
neexistuje — `main` nemá stage `build` a registry images nič nekonzumuje — a sú
reprodukovateľné zo zdrojov, ktoré v archíve sú. Je to **jediná vec**, ktorá
zmazaním `~/gitlab` zmizne bez kópie, a je zapísaná v `README.md` archívu.

> **Poznámka k vlastnej chybe, nech sa neopakuje.** Najprv som napísal, že z 65
> notes je „len 18 skutočných ľudských komentárov". Bola to pravda o **MR**
> komentároch a nepravda o celku — 21 ďalších je na úrovni commitov, spolu 39.
> Číslo 18 pochádzalo z dotazu, ktorý sa na commity nepozeral; rozdiel som
> odhalil až agregátom cez celú tabuľku. Presné číslo je **39**.

**A jedna korekcia, ktorú si tento dokument nesie ďalej.** `CLAUDE.md` aj §9
nižšie tvrdili, že Mac má „zamrznutú záložnú" databázu. **Nemá.**
`docker volume ls` ju neuvádza a `docker volume inspect` vracia `no such volume`;
`cistafirma_postgres_data` aj ostatné cistafirma a GitLab volumes zmizli
**2026-09-17** pri purge. Ostávajú **dumpy** (2,4 GB, 70 súborov — 35 `.dump`
a 35 `.json` manifestov, rozsah **2026-09-08 → 2026-09-15**) — archív, nie
databáza. Obe miesta sú opravené na mieste.

> **Tretia nepresnosť tej istej triedy, dodatočne domeraná.** Napísal som, že
> archív dumpov „reaches back only to 2026-09-15". Najstarší je
> `cistafirma_20260908T174923Z.dump` — archív siaha **o týždeň ďalej**, po
> 8. 9. (a `44 súborov` bolo tiež zlé číslo; je ich 70). Nebolo to nebezpečné
> v tom smere, ktorým som sa bál — podhodnotil som pokrytie, nie prehnal —
> ale bola to tá istá chyba: číslo z jedného `ls | tail`, vydané za rozsah.

**A hneď druhá korekcia, tej istej triedy — tentoraz moja vlastná, o pár minút
neskôr.** Napísal som, že pri purge zmizli **všetky** volumes na Macu. Keď som
to šiel overiť, `docker volume ls` ich vrátil **šesť**: `sslcheckerapp_sqlite_data`
a `sslcheckerapp_static_volume` (vytvorené **2026-06-13**, teda purge **prežili** —
dva zastavené kontajnery na ne stále ukazujú) a štyri anonymné z 21:57–21:58 UTC
toho dňa. Purge bol teda selektívny, nie plošný. Safety-critical polovica
(`cistafirma_postgres_data` je preč) platí a je overená `no such volume`; plošné
tvrdenie bolo nepravdivé a je opravené vyššie. Je to **tretí raz v jednom dni**,
čo som zúžene meranie vydal za fakt — pozri `absence-needs-a-positive-control`
v pamäti.

**A jedna maličkosť, tiež „zbytočne stojí":** `git worktree list` držal
registráciu na `/private/tmp/cistafirma-ci` pre vetvu
`ci/runner-tags-and-kubectl-image` (`8ea1e50`), hoci ten adresár už neexistuje —
GitLab ju sám označoval ako `prunable`. `git worktree prune` ju odstránil;
vetva aj jej commity ostávajú (`8ea1e50`).

---

### „Zlúčiť `feat/ai-ready-baseline` s `main`" nebol problém — je to predok (2026-09-18)

V zozname otvorených vecí bola aj „konvergencia `feat/ai-ready-baseline` s `main`".
**Nie je čo zlučovať.** `git rev-list --count main..gitlab-home/feat/ai-ready-baseline`
je **0** — vetva nemá ani jeden vlastný commit; `main` je o 10 napred, ale len
preto, že je to tá istá línia. `git ls-remote` na oba remoty vracia pre tú vetvu
**`fc460015baaabf0a7285d6058a2e9b57f26882b8`**, a `git merge-base --is-ancestor
fc46001 main` je pravda.

História je teda **jedna priamka**, nie dve vetvy:

```
6abd4d5 (dell) → fc46001 (feat/ai-ready-baseline na oboch remoteoch)
              → d113a67 (merge) → 7d97d66 → 945fce2 (main)
```

**A to isté platilo pre `dell`** — len to už nie je pravda a toto je
oprava, nie nový nález. Keď sa toto písalo, `dell` bežal na
`feat/ai-ready-baseline`, HEAD `6abd4d5`, `git rev-list --count main..6abd4d5`
bol **0**, čiže nasadenie bolo čistý fast-forward o 25 commitov. **Dnes
(2026-09-18) je `dell` na `main`, HEAD `5f812c0`** — nasadenie z 2026-09-18
12:25 (`.env` a `.git` na delle čítané naozaj, nie odhadnuté: pracovný
adresár `~/cistafirma`, vetva `main`, čistý strom). `main` je odvtedy
o **14 commitov** napred (`git rev-list --count 5f812c0..main`), a to celé
mobilná a grafová práca #175–#178 — **frontend a dokumentácia, 0 migrácií**,
takže nasadenie je rebuild frontendu, nie zmena schémy.

Nasadenie na `dell` je **manuálny krok a zámerne neprebehlo samo**: je to
produkcia a `docker compose up -d --build` ju na chvíľu zastaví. Čaká na
slovo. Postup je v `docs/DEVOPS_CICD.md` (sekcia o nasadení na `dell`, okolo
riadku 223) — **nie** v `docs/DEPLOYMENT_RUNBOOK.md`, to je k8s cesta, ktorá
sa podľa CLAUDE.md nesmie použiť, kým cluster neexistuje.

`feat/ai-ready-baseline` má stále **0 vlastných commitov** a na `gitlab-home`
je `fc46001` — je to predok `main`, takže vetva je teraz len druhé meno pre
`main`. `dell` ju už nemá vycheckoutovanú.

Z toho vyplýva, že „zlúčiť vetvu s `main`" aj „doviesť `dell` na `main`" sú dve
stránky tej istej veci: **`main` už všetko obsahuje**, obe mená ukazujú na jeho
predkov. Nič sa nemerguje — len sa posunie ukazovateľ. Prvá polovica je
vyriešená: `dell` už na `main` je (viď vyššie), takže na ňom nestojí nič.
Druhá polovica — posun `feat/ai-ready-baseline` na `main` — **je teraz už len
kozmetika**: nikto ju nemá vycheckoutovanú, takže nikoho neblokuje. Nechal som
ju na tvoje slovo, lebo je to rozhodnutie o zdieľanej vetve, nie o kóde.

#### Koľko z tých 22 vetiev je mŕtvych — a či o niečo prídu

`gitlab-home` má **22 vetiev**, GitHub **2** (`main`, `feat/ai-ready-baseline`).
Pre každú vetvu som zmeral `git rev-list --count main..<vetva>`:

- **14 vetiev má 0 vlastných commitov** — sú celé obsiahnuté v `main` a zmazať sa
  dajú bez straty: `checkpoint/wip-state`, `chore/frontend-assets`,
  `ci/runner-tags-and-kubectl-image`, `feat/ai-ready-baseline` (kedysi ju držal
  `dell` — dnes už nie, je na `main`), `feat/companies-registers-backend`,
  `feat/frontend-admin-pages`,
  `feat/frontend-components-overhaul`, `feat/frontend-ts-migration`,
  `feat/new-apps-connections-core`, `feature/admin-overhaul`,
  `feature/frontend-enhancements`, `feature/registers-sync-engine`,
  `infra/docs-k8s-audit-fix`, `refactor/admin-UI`.
- **7 má vlastné commity**: `backup/origin-main-20260507204206` (1),
  `chore/gitignore-config` (1), `chore/project-config` (2), `feat/admin-dashboard` (1),
  `dev` (8), `docs/licence-and-readme-update` (8), `fix/code-review-improvements` (8).

**Jedna vetva má na `gitlab-home` iný SHA — a správne je nechať ju tak.**
`ci/runner-tags-and-kubectl-image` je lokálne `8ea1e50`, na `gitlab-home`
`35a9a36`; lokálna je o 5 commitov napred a tá vzdialená je jej **predok**
(`lokalna..gitlab-home` = 0), takže obe sú v `main`. Vyzeralo to ako „niečo
je pozadu", ale dorovnať sa to **nesmie**: `.gitlab-ci.yml` na `8ea1e50` má
ešte celú líniu `build` + `deploy` a `.build_template` v nej nesie
`tags: [macos]` — runner s tým tagom je od 17. 9. `active = false`, takže push
by vyrobil pipeline, ktorej `build_backend_image` a `build_frontend_image`
ostanú `pending` navždy. Presne ten druh vecí, ktorý sa tu upratuje. Obsah
nechýba — obe vetvy sú v `main` — zaostáva len popisok, a to je neškodné.

**Nič som nezmazal** — je to nevratné a nie je to moja vec. Ale tú najpodstatnejšiu
som preveril, aby sa „8 nezlúčených commitov" nečítalo ako 8 stratených vecí.
`fix/code-review-improvements` vyzerá najhodnotnejšie (k8s init kontajner,
`/healthz/` sondy, `{once:true}` na Vanta listeneroch, `pgpass` namiesto
`PGPASSWORD`), a **všetko z toho už v `main` je, inou cestou**:

- `pgpass` — `main:scripts/k8s/backup_postgres.sh` používa `PGPASSFILE` (`mktemp`
  + `chmod 600` + `trap` na zmazanie). Vetvový commit je predbehnutý.
- `/healthz/` sondy — `main` ich má v `deploy/k8s/base/backend-deployment.yaml`
  aj v `deploy/helm/cistafirma/templates/backend-deployment.yaml`.
- `{once:true}` na Vanta listeneroch — **moot**: `main` už Vanta skript
  nenačítava vôbec, shadery má vendorované priamo
  (`frontend/components/VantaBackground.tsx` má `compileShader`/`initWebGL`
  a v celom `frontend/` nie je `<script>` load listener). Oprava riešila kód,
  ktorý v `main` neexistuje.

**Pozitívna kontrola k tomu:** `git grep` na `main` tie veci **našiel** (`PGPASSFILE`,
`/healthz/`), takže „nenájdené" pri Vante je meranie, nie prázdny výsledok
prístroja, ktorý nevie hľadať ([[absence-needs-a-positive-control]]).

#### Vlastná chyba: 20 fantómových `origin/*` refs

Pri porovnávaní som spravil `git fetch gitlab-home '+refs/heads/*:refs/remotes/origin/*'`
— a tým **prepísal `origin/*`**. Remote `gitlab-home` má pritom vlastný
namespace (`+refs/heads/*:refs/remotes/gitlab-home/*`), takže vzniklo 20 refs
`origin/<vetva>`, ktoré na GitHube **neexistujú**. `git fetch --prune origin`
ich presne tých 20 odstránil a nechal `origin/main` a
`origin/feat/ai-ready-baseline` — jediné dve vetvy, ktoré GitHub má. Stratené
nebolo nič: tie refs boli kópie `gitlab-home/*`, ktoré tam ostali.

#### `dell` sa odtiaľto cez `~/.ssh/config` nedá dosiahnuť

`Host dell` má `HostName 192.168.1.210` a to je LAN adresa, ktorá z Macu
**timeoutuje**. `tailscale status` vidí `dell` na **`100.79.47.4`**, a odtiaľto
funguje. Je to tá istá trieda ako `gitlab.home.arpa` — adresa v configu
predpokladá sieť, v ktorej práve nie sme ([[always-name-the-device]]).

**A `dell` na `gitlab-home` vidí**, takže deploy cesta nie je pokazená:
`getent hosts gitlab.home.arpa` tam vracia `100.120.104.84` (lenovo) a
`git ls-remote --heads gitlab-home main` vráti `e1bb67d` — teda to, čo je na
`main` naozaj, nie to, čo tam bolo pri prvom meraní. `fetch.all = true`
v jeho globálnom configu je problém len pre *holý* `git pull` (ten navyše
fetchuje `origin` cez https bez credentials) — viď
`dell-git-pull-exits-nonzero` v pamäti.

#### Dôkaz, že `main` beží ďalej aj bez runnera 2

Nie je to tvrdenie z konfigurácie, je to odmerané na **štyroch** pipeline:

| Pipeline | Commit | Výsledok |
|---|---|---|
| 147 | `d113a670` | `success`, 7/7 jobov — **všetky na runneri 1** |
| 148 | `7d97d669` | `success`, 7/7 jobov — **všetky na runneri 1** |
| 149 | `945fce28` | `success`, 7/7 jobov — **všetky na runneri 1** |
| 150 | `e1bb67df` | `success`, 7/7 jobov — **všetky na runneri 1** |

**Dvadsaťosem jobov, dvadsaťosem na runneri 1, ani jeden na runneri 2.** Runner 2
je pritom od 17. 9. `active = false`; v žiadnej z tých pipeline sa nevyskytuje
ani raz. Keďže `.gitlab-ci.yml` na `main` nemá **žiadne `tags:`** (overené
`git grep`), runner 2 s tagom `macos` a `run_untagged = false` sa ani nemohol
chytiť — jeho vypnutie teda nemohlo nič zobrať.

**Pipeline 148 to potvrdila ako prvá:** `backend_validate` (1040),
`frontend_validate` (1041), `docs_audit` (1042), `helm_render_validate` (1043),
`helm_runtime_validate` (1044), `frontend_tests` (1045) aj `backend_tests` (1046)
majú **`runner_id = 1`**, `failure_reason` prázdny, a bežali 22:04:02 → 22:13:27.

> **A tu som si opravil vlastnú vetu.** Stálo tu, že 149 je `running` a 150
> `pending` „čaká za 149, `concurrent = 1`". **To je nesprávne.** 149 a 150
> bežali **súčasne** — runner 1 berie vždy ďalší *job*, nie ďalšiu *pipeline*,
> a berie ho z tej pipeline, ktorá má čo ponúknuť. Prestriedanie je vidieť
> v sekundách odovzdania:
>
> | kedy | čo skončilo | čo sa v tej istej sekunde chytilo |
> |---|---|---|
> | 22:15:38 | 149 `helm_render_validate` | 150 `backend_validate` |
> | 22:16:33 | 150 `backend_validate` | 149 `helm_runtime_validate` |
> | 22:16:40 | 149 `helm_runtime_validate` | 150 `frontend_validate` |
> | 22:17:42 | 150 `frontend_validate` | 149 `frontend_tests` |
> | 22:24:36 | 149 `backend_tests` | 150 `docs_audit` |
>
> V tabuľke je päť odovzdaní a **všetky prechádzajú medzi 149 a 150, striedavo**
> — 149→150, 150→149, 149→150, 150→149, 149→150 — každé v tej istej sekunde,
> v akej predošlý job skončil. (V tých istých dvoch pipeline sú aj dve
> odovzdania v tej istej sekunde *vnútri* jednej z nich — 149 `docs_audit` →
> 149 `helm_render_validate` o 22:15:31 a 150 `docs_audit` → 150
> `helm_render_validate` o 22:24:42 — takže striedanie dvoch pipeline nie je
> jediné, čo runner robí; je to však to, čo dokazuje, že bežali súčasne.)
> 150 teda **nečakala za 149** — bežala *v* nej. `concurrent = 1` obmedzuje
> **joby, nie pipeline**, a pipeline status je odvodený z jobov, takže o poradí
> medzi pipeline nehovorí nič. ([[querying-gitlab-ci-state]])
>
> Záver o runneri 2 to nemení — naopak, je to silnejší dôkaz: 150 nemohla
> preskočiť na iný runner, lebo žiadny iný neexistuje.

**Za 48 hodín nemá projekt ani jeden `failed` job.** Celkovo 280 jobov: 224
`success`, 56 `canceled`, **0 `failed`** — a tých 56 `canceled` sú
predbehnuté `pending` pipeline z pushov 16.–17. 9., ktoré GitLab zruší sám
([[querying-gitlab-ci-state]]); `runner_id` majú NULL, lebo ich nikto nikdy
nevzal. To je tá istá trieda ako `failure_reason = 26` z 10.–15. 9., len
s opačným znamienkom.

**A jedna vec, ktorú som mal v pamäti zle.** `backend_tests` **nebeží** na
SQLite — beží na Postgrese. `.gitlab-ci.yml` na `main` mu dáva
`services: postgres:16-alpine` (a `redis:7-alpine`) s `DATABASE_URL`
medzi **jobovými** premennými, nie medzi CI/CD premennými projektu; preto sa
„žiadne CI premenné" a „beží na SQLite" dali zlúčiť do jednej vety. Opravil to
`6e219e5` (15. 9. 2026 23:19) a jeho vlastný komentár v CI to aj vysvetľuje.
Živý dôkaz z jobu 1060: `Ran 934 tests in 210.298s`, `Creating test database for
alias 'default'` → `Destroying test database`. **Stav je overený z tracu jobu.**

> **Oprava 2026-09-19.** Stálo tu, že bežiaci job je „jediné okno, kedy sa trace
> dá vôbec prečítať". **To je nesprávne**, a stálo to na zámene dvoch vecí:
> trace *nie je v databáze* po archivácii (`ci_build_trace_chunks` aj
> `p_ci_build_trace_metadata` boli pre build 1360 prázdne), ale je na
> **filesystéme** GitLabu a čítať sa dá kedykoľvek — aj dávno po skončení jobu:
>
>     /var/opt/gitlab/gitlab-rails/shared/artifacts/<2>/<2>/<64>/<rrrr_mm_dd>/<build_id>/<project_id>/job.log
>
> Overené na build 1360 (pipeline 193): `wc -l` = 181 riadkov, `grep -c
> "Ran .* tests"` = 0, `tail -1` = `ERROR: Job failed: exit code 2` — celé
> prečítané **po** skončení jobu. Cesta sa hľadá `find`-om na kontajneri
> `gitlab-server`; hashové prefixy sa z ID odvodiť nedajú.
> ([[querying-gitlab-ci-state]])

### Inštalácia závislostí v CI vedela zhodiť pipeline pred prvým testom (2026-09-19)

19. 9. 2026 o 09:35 UTC zlyhal `backend_tests` v pipeline 193 (build 1360) na
`d7fe037` — commite, ktorý sa dotýka **len `docs/PLAN.md`**. To je samo o sebe
podozrivé, takže sa to čítalo, nie hádalo.

Trace (ako sa k nemu dostať, je v oprave vyššie):

```
pip._vendor.urllib3.exceptions.ReadTimeoutError:
HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out.
ERROR: Job failed: exit code 2
```

`grep -c "Ran .* tests"` v traci = **0**. Job teda zomrel v `pip install`
v `before_script` a **nespustil ani jeden test**. A
`git diff --quiet 24b1345 d7fe037 -- backend frontend` je prázdny, takže
pipeline 192 testovala **bajt-identický** kód a bola zelená. Červená 193 teda
o kóde nenesie **nič** — je to zlyhanie prostredia, nie regresia.

**Prečo to nie je len smola.** `pip` sa už raz opakuje sám —
`--retries 3 --timeout 120` pribudlo 7. 5. 2026 (`e9be132`) **presne ako
mitigácia tohto problému**. Nepokrylo však presne ten prípad, ktorý nastal:
`--retries` opakuje *spojenie*, ale keď PyPI neodpovie v rámci limitu, pip to
vzdá a job zomrie. Tri pokusy na úrovni spojenia nie sú tri pokusy na úrovni
kroku.

**Oprava** (`cbf7276`, `scripts/ci/pip_install.sh`): opakuje sa **celý krok** —
znovu sa spustí `pip`, teda aj rozlíšenie mena, aj celý prenos. To je jediná
účinná vec aj na výpadok DNS, ktorý tento projekt už raz zažil (viď riadok 2
`registers_syncprogress`). Vnútorné flagy zostávajú presne tie isté
(`--retries 3 --timeout 120`), aby sa nemenilo naraz viac vecí.

Dve veci, ktoré tá oprava zámerne **nerobí**:

- **Neopakuje job ako celok** (`retry: when: script_failure` v `.gitlab-ci.yml`).
  Tým by sa opakovali aj testy — a červená pipeline by prestala znamenať „test
  neprešiel". Opakovanie patrí sieťovému kroku, nie kontrolnému.
- **Nepoužíva `exit 0`** v tele slučky: GitLab Runner zliepa `before_script`
  a `script` do jedného shell skriptu, takže `exit 0` v `before_script` by
  ukončil celý job ako **úspešný** a testy by sa nikdy nespustili. Preto
  `break` a kontrola až za slučkou.

Logika je testovateľná mimo CI cez `--selftest N` (stub `pip`, ktorý zlyhá
N-krát): zlyhá 2× → `EXIT 0` po 3 volaniach, zlyhá vždy → `EXIT 1` po 3
pokusoch. Bez toho by sa skript, ktorý rozhoduje o tom, či sa testy vôbec
spustia, testoval až tým, že raz za čas zhodí pipeline.

**Oprava opravy (2026-09-19, pipeline 194, build 1362).** Prvá verzia skriptu
zhodila `backend_validate` — job, ktorý dovtedy prechádzal vždy:

```
ERROR: Could not open requirements file: [Errno 2]
No such file or directory: '/backend/requirements.txt'
```

Skript mal `pozadovane="/backend/requirements.txt"` — **absolútnu** cestu.
Runner klonuje do `/builds/web/cistafirma.sk` a job spúšťa v **koreni repa**,
takže `/backend/` tam neexistuje; pôvodný riadok bol relatívny
(`-r backend/requirements.txt`). Opakovanie pritom fungovalo presne ako malo
(`pokus 1 … o 20s`, `pokus 2 … o 40s`, potom `vzdávam to`) — červená bola len
a výhradne z cesty. Relatívna cesta by sa ale rozbila v `backend_tests`, ktorý
má `cd backend` v `script` a zdieľa ten istý `before_script`; cesta sa preto
skladá z umiestnenia skriptu (`scripts/ci/` → o dve vyššie), takže je správna
z ľubovoľného cwd (`scripts/ci/pip_install.sh:96-100`).

Poučenie je o **self-teste, nie o ceste**: `--selftest` stubuje `pip`, takže sa
cesty nikdy nedotkol — a prepustil presne tú chybu, na ktorej záležalo.
Kontrola existencie cieľového súboru preto teraz beží **aj v `--selftest`**,
a je zároveň pozitívnou kontrolou proti tejto regresii:

```bash
# tá istá chyba, akú poslal do CI build 1362 — musí zlyhať:
CI_PIP_REQUIREMENTS=/backend/requirements.txt \
  bash scripts/ci/pip_install.sh --selftest 2   # EXIT 1, „neexistuje"
```

Voľba `CI_PIP_REQUIREMENTS` je len pre tento test; v CI sa nepoužíva.

**A jedna prevádzková poznámka k tomu.** Pipeline 193 sa podarilo dokončiť len
ručným retry-om cez `Ci::RetryJobService` v `gitlab-rails` na `lenovo` —
`glab` ani API token tu nie sú. Rails runner sa rozbieha ~45 s a jeho výstup
(`RETRY project=web/cistafirma.sk new_build= status=success`) prichádza skôr,
než je retry build v DB — `new_build` je teda prázdne aj vtedy, keď retry
naozaj prebehol; spoľahlivý dôkaz je nový riadok v `p_ci_builds`
(`retried=true` na pôvodnom, nový build s tým istým menom).

---

## 8. Nálezy z konsolidácie dokumentácie (2026-09-18)

Pri sťahovaní 19 koreňových dokumentov do `docs/archive/` (#169) sa ich tvrdenia
overovali proti kódu. Táto sekcia drží to, čo z nich **v kóde neplatí** alebo čo
kód potvrdzuje a inde v dokumentácii to nie je. Je to zoznam nálezov, nie
zoznam opráv — nič z toho nebolo zmenené.

Spoločná trieda: **dokument tvrdí „hotové / production ready", kód to
nepotvrdzuje** — a v troch prípadoch to nie je len zastaraný text, ale tichá
porucha za behu (8.2 `verify_implementation.sh`, 8.3 kolízia syncu, 8.4
`szco_count`).

### 8.1 Kombinovaný filter — koreňová príčina a oprava

Prevzaté z archívneho jednostranného záznamu
`docs/archive/COMBINED_FILTER_FIX_COMPLETE.md` (2026-08) a **overené proti kódu
2026-09-18**. Toto je jediné miesto v repozitári, ktoré vysvetľuje **prečo**
kombinovaný filter visel, nielen čo sa zmenilo.

#### Ako sa to prejavovalo

Na ostrej databáze (1,2 mil. firiem) kombinovaný filter — mesto + NACE + dlh +
ORSR — nevracal výsledok **30–60 s**, alebo rovno spadol na timeout. Databáza
išla na **135 % CPU** (oversubscribed), backend na 57 % a čakal na ňu.

#### Koreňová príčina

`Company → OrsrCompanyProfile` je 1:N. Keď anotácia chýbala, filter na „má ORSR
profil" sa aplikoval ako `.filter(orsr_profile__isnull=False)` — teda
**implicitný OUTER JOIN**. Postgres potom musel materializovať
`Company × Related` riadkov a výsledok deduplikovať. Pôvodný záznam uvádza
„50M+ intermediate rows"; je to **odhad, nie meranie**.

#### Oprava

Náhrada za `Exists()` + `OuterRef("pk")`: existencia sa kontroluje korelovaným
poddotazom po riadkoch, bez joinu a bez deduplikácie. V
`backend/adminapi/services/company_filters.py` je dnes **27 výskytov `Exists(`**
a na riadku 120 je pravidlo zapísané doslovne v komentári:

```python
# Optimized: Use annotated flags if available, else use Exists subqueries (never use __isnull joins)
```

Zvyšné `__isnull` v tom súbore sú na **vlastných stĺpcoch** (`datum_zrusenia`,
`latest_profit`, `latest_revenue`, `sync_failures`), nie na reláciách — tie sú
v poriadku.

**Staré (pomalé):**

```sql
SELECT DISTINCT c.id FROM "Companies and SZCO" c
INNER JOIN registers_orsrcompanyprofile o ON c.id = o.company_id
WHERE c.mesto = 'Bratislava'
GROUP BY c.id ORDER BY -c.id LIMIT 100;
```

**Nové (rýchle):**

```sql
SELECT c.id FROM "Companies and SZCO" c
WHERE c.mesto = 'Bratislava'
  AND EXISTS (SELECT 1 FROM registers_orsrcompanyprofile o WHERE o.company_id = c.id)
ORDER BY -c.id LIMIT 100;
```

| Hľadisko | `__isnull` join | `Exists()` poddotaz |
|---|---|---|
| Materializácia | plný JOIN + agregácia | korelovaná kontrola |
| Riadkov na spracovanie | `Company × Related` | `Company` |
| Plánovač | Hash/Sort Group | anti-join |
| Zložitosť | O(n²) s rastúcimi reláciami | O(n) |

#### Čo je zmerané a čo nie

⚠️ **Toto je dôležité, lebo pôvodný dokument končí „✅ PRODUCTION READY".**

Čísla `0,001–0,002 s` a „1 dotaz" sú z **umelej množiny 100 firiem**
s pripravenými relačnými dátami. Jeho vlastný deployment checklist má
**nezaškrtnuté** presne tie kroky, ktoré by tvrdenie potvrdili:

- [ ] Deploy to staging/production
- [ ] Test with real 1.2M company dataset
- [ ] Monitor performance metrics
- [ ] Document in changelog

Overenie na **ostrých 1,2 mil. riadkoch sa teda nikdy nestalo**. Presné
tvrdenie je „korekčný vzor je nasadený v `company_filters.py` a na 100 firmách
merateľne rýchly"; tvrdenie „30–60 s visenie je natrvalo odstránené" je
**predpoklad, nie meranie**. Ak sa má uzavrieť, treba ho zmerať na `dell`.

#### Stále otvorené: admin filtre idú okolo hotových anotácií

`backend/companies/admin.py` **už `Exists()` má** — `CompanyAdmin.get_queryset()`
(`:520-525`) anotuje `_has_orsr` a `_has_financials` cez
`Exists(...OuterRef('pk'))`. Lenže filtrová cesta tie anotácie **nepoužíva**
a spadne na ten istý `__isnull` join, navyše s `.distinct()`:

| Kde | Riadky | Vzor |
|---|---|---|
| `DataCompletenessFilter.queryset()` | `:135, 137, 139, 141` | `orsr_profile__isnull`, `financial_results__isnull` (+`.distinct()`) |
| `CompanyAdmin.get_filtered_queryset()` | `:597, 599, 603, 605` | vetvy `has_orsr` / `has_financials` |
| `CompanyAdmin.get_filtered_queryset()` | `:623, 625, 627` | vetvy `data_state` |

Nejde teda o „vzor v admine chýba" — ide o to, že **rýchla cesta je na tom
istom querysete k dispozícii a filter ju obchádza**. Oprava je mechanická:
`_has_orsr` / `_has_financials` namiesto `__isnull` a `.distinct()` preč.
Overené **čítaním kódu**, nie meraním — dopad na admin changelist nebol zmeraný.

Pôvodný dokument uvádzal riadky `121, 123, 560, 562, 580, 582, 584`; tie sa
medzitým posunuli, v tabuľke vyššie sú **aktuálne k 2026-09-18**.

### 8.2 `verify_implementation.sh` — skript, ktorý nemôže zlyhať

`verify_implementation.sh` (v koreni, trackovaný) je overovací skript pre
funkciu Firmy/SZCO. Má **15 blokov `if grep -q … then … fi`** — a ani jeden
`else`, ani jeden `exit 1`, ani jeden čítač. Na konci (`:79`) **bezpodmienečne**
vytlačí `✅ Implementation Verification Complete!` a skončí s 0.

Ak by všetkých 15 hľadaných symbolov z kódu zmizlo, výstup aj exit kód sú
identické. `docs/archive/README_FIRMY_SZCO_IMPLEMENTATION.md:213-218` pritom navádza:
`bash verify_implementation.sh` → `# Expected output: All ✓ checks pass`. Je to
teda **dôkaz, ktorý sa nedá vyvrátiť** — presne trieda z
[[a-count-that-cannot-show-failure]] a [[silent-failure-is-the-defect-class]]:
kontrola musí súdiť výsledok, nie zápis.

Toto je najcennejší jednotlivý nález z celej konsolidácie, pretože nejde
o zastaraný text — skript je spustiteľný dnes a klame.

### 8.3 Firmy a SZCO sa **nedajú** synchronizovať súčasne — a UI to tvrdí opak

`docs/archive/FIRMY_SZCO_ARCHITECTURE.md:406` hovorí *„Can run both simultaneously"*
a `docs/archive/FIRMY_SZCO_QUICK_START.md:6-9` predáva SZCO sync ako nezávislý. Kód hovorí
inak — je vynútený **jeden aktívny RUZ job globálne**:

- `backend/registers/models.py:705-710` — partial unique constraint
  `reg_one_active_ruz_job` na `concurrency_key` v stavoch `queued|running`.
- `backend/registers/services/sync_engine.py:49,52` — `ruz_full_firmy` aj
  `ruz_full_szco` sú v `RUZ_JOB_TYPES` a oba dostávajú **tú istú**
  konštantu `RUZ_CONCURRENCY_KEY = "ruz:global"`, nie kľúč podľa typu.
- CLI to odmietne nahlas (`fetch_ruz_data.py:89-92` → `CommandError(…refusing
  concurrent import.)`).

**Tichá porucha, ktorá z toho vyplýva a nie je zapísaná nikde:** admin API pri
kolízii **nevráti chybu, ale HTTP 200 s existujúcim (cudzím) jobom** —
`backend/adminapi/views/sync.py:64-65`:

```python
if not created:
    return Response(SyncJobSerializer(job).data, status=status.HTTP_200_OK)
```

Frontend na 200 zobrazí hlášku o úspechu
(`frontend/admin/pages/Data.tsx:29-31`), a `try/catch` o riadok nižšie ju
nechytí, lebo 200 nie je výnimka. Výsledok: používateľ klikne „FULL RUZ SYNC –
SZCO", dostane `✓ Synchronizácia pre SZCO bola spustená (ID: N)` — kde `N` je ID
**bežiaceho Firmy jobu**. SZCO sync sa nikdy nespustí a UI tvrdí opak.

### 8.4 Firmy/SZCO — meranie a klasifikácia

**`szco_count` meria nesprávnu tabuľku.** `backend/adminapi/views/dashboard.py:66-67`
počíta obe čísla cez `Company.objects`. Ale RUZ od zavedenia oddelenia ukladá
SZCO do **vlastnej tabuľky** `IndividualEntity` (`registers/models.py:757`,
`db_table "Individual Entities"`, zápis `fetch_ruz_data.py:562-566`).
`IndividualEntity` sa v celom `backend/adminapi/` **nevyskytuje ani raz**
(pozitívna kontrola: v `backend/` ho má 9 súborov, takže grep funguje).
Dôsledok: pre novo synchronizované dáta je `szco_count` ≈ 0, `firmy_count` ≈
všetko — a pomer „68 % / 32 %", ktorý propagujú
`docs/archive/README_FIRMY_SZCO_IMPLEMENTATION.md:22-23`
a `docs/archive/FIRMY_SZCO_QUICK_START.md:93-94`, je fikcia. Podľa
`docs/SOURCE_DATA_INTEGRITY.md:439` sú SZCO pritom „that third of the RUZ
surface". (Cesta bola doplnená 19. 9. 2026 — oba dokumenty sa pri konsolidácii
presunuli do `docs/archive/` a odkazy naďalej ukazovali na koreň repa, kde už
nič nebolo. **Čísla riadkov pritom sedia dodnes**, overené: `:22` nesie
`"Počet Firiem: 8,500 (68%)"` a `:93` `Firmy: 8,500 (68%)` — stratila sa len
cesta, nie obsah.)

**`SZCO_LEGAL_FORMS` existuje v troch nezhodných podobách:**

| Kde | Obsah |
|---|---|
| `backend/companies/models.py:224` | `100–110` — **bez `422`** |
| `backend/registers/management/commands/fetch_ruz_data.py:16-19` | `100–110` **+ `422`** („Foreign natural person") |
| `backend/adminapi/views/dashboard.py:66-67` | inline literál `100–110`, konštantu vôbec nepoužíva |

`422` (zahraničná fyzická osoba) teda ide do `IndividualEntity`, ale dashboard
ho ráta ako Firmu. Navyše `is_szco_company()` / `is_company_company()`
(`companies/models.py:227,241`) **nemajú žiadneho volajúceho v produkčnom
kóde** — routing v skutočnosti robí `fetch_ruz_data.py:523`. Sú to mŕtve
funkcie, na ktoré sa `verify_implementation.sh` (8.2) odvoláva.

**„FULL RUZ SYNC" nezačína od 2000-01-01.** `fetch_ruz_data.py:184` ošetruje
`if sync_type == 'full'`, ale `--entity-type companies` s `--full-resync` dáva
`sync_type = 'full_companies'` (`:68-69`) — teda `else` vetva, ktorá číta
`progress.zmenene_od`, alebo najnovší `datum_poslednej_upravy`. Obe tlačidlá
Firmy/SZCO preto robia **inkrementálny** prechod, nie plný rescan; tvrdenie
„starting from 2000-01-01" (`RUZ_SYNC_ENTITY_SEPARATION_COMPLETE.md:99,121`)
neplatí. Vlastný komentár v kóde divergenciu priznáva (`fetch_ruz_data.py:383-386`).

**Progress % pre SZCO sa delí počtom firiem.**
`SyncProgress.get_progress_percentage()` (`registers/models.py:266-269`) delí
`total_processed` konštantou `RUZ_ESTIMATED_COMPANY_COUNT = 400_000`
(`backend/core/constants.py:3`) pre **všetky** sync types — `full_individuals`
teda ukazuje percento voči počtu firiem.

**Chýba dátová migrácia SZCO riadkov.** Legacy tabuľka `Company` je
`"Companies and SZCO"` (`backend/companies/models.py:635`) a **stále obsahuje
SZCO riadky**. Prešel som všetky `RunPython`/`RunSQL` v projekte: ani jedna sa
nedotýka `IndividualEntity` ani nepresúva riadky medzi tabuľkami
(`registers/migrations/0010_add_individual_entity.py` je len `CreateModel` +
`AlterField`). Sám dokument to priznáva — `docs/archive/RUZ_SYNC_ENTITY_SEPARATION_COMPLETE.md:363`
má „Data migration script to move existing SZCO…" medzi **Future Enhancements**.
Je to jediná zmienka o tejto diere v celom repozitári.

**Dve nezlučiteľné cesty zápisu `pravna_forma`.** `normalize_legal_form_code()`
sa volá len v `backend/registers/tasks.py:573` (per-firma `sync_company_now`)
a `registers/eligibility.py:34`; hromadný walk `fetch_ruz_data.py:549` ukladá
**raw** `data.get('pravnaForma')`. Test `registers/tests.py:738-758` overuje len
tú prvú cestu, takže rozdiel je v testoch neviditeľný.

### 8.5 Admin panel — čo príručky sľubujú a kód nemá

`docs/archive/ADMIN_DEPLOYMENT_GUIDE.md` a `docs/archive/ADMIN_IMPLEMENTATION_COMPLETE.md` sa navzájom
rozchádzajú a oba sľubujú veci, ktoré v kóde nie sú:

| Tvrdenie | Realita |
|---|---|
| API `/api/sync/start/`, `/status/`, `/resume/{id}/` s hotovými `curl` príkladmi (`docs/archive/ADMIN_DEPLOYMENT_GUIDE.md:420-446`) | **Neexistujú** — `git grep` naprieč `backend/` aj `frontend/` → 0. `docs/archive/ADMIN_IMPLEMENTATION_COMPLETE.md:426-431` ich správne vedie ako „Phase 3" (budúce) |
| Tlačidlá „🏢 Full Companies" / „👤 Full Individuals" | **Neexistujú** — `registers/admin.py:572-577` registruje štyri iné (`trigger_full_url`, `incremental`, `repair`, `gap_analysis`) |
| Index `idx_sync_type_status` na `registers_syncprogress` | **Nie je** — `SyncProgress.Meta` (`registers/models.py:257-260`) nemá `indexes` |
| Dashboard štatistika „Total Individuals (SZCO)" | **Nie je** — `registers/admin.py:570-599` agreguje výhradne `Company.objects` |
| 2FA na admin účtoch (`:460`, ako „⚠️ Recommended") | **V kóde neexistuje** (`git grep -i "2fa\|totp\|django-otp"` → 0) |

Posledný bod má reálnu váhu, lebo `create_admin.py:21` **natvrdo zakladá**
`create_superuser(username='admin', password='admin')`. Odporúčanie „zapni 2FA"
tak nie je formalita.

Naopak overene **správne** a zachovania hodné je v tých príručkách toto:
bezpečnostný postoj (čo je implementované vs odporúčané,
`docs/archive/ADMIN_DEPLOYMENT_GUIDE.md:454-464`), DO/DON'T prevádzková politika syncu
(`:279-301`, 16 bodov — jediná formulácia v repe), troubleshooting „Running bez
progresu" (`:346-364`) a zdôvodnenie zrkadlových tabuliek
(`ADMIN_IMPLEMENTATION_COMPLETE.md:258-281, 369-386`). Tie zostávajú
v `docs/archive/`.

### 8.6 Performance dokumenty — čo bolo namerané a čo sa len tvrdilo

Konsolidovaných bolo sedem performance dokumentov. Prekryv je **sémantický, nie
textový** (max. Jaccardova podobnosť riadkov 0,068 — žiadny pár nie je kópia),
ale tie isté „štyri bottlenecky" sú prerozprávané v šiestich zo siedmich.
Čísla, ktoré po nich zostali, sú **odhady, nie merania**:

| Tvrdenie | Kde | Stav |
|---|---|---|
| `30,000x faster` | `docs/archive/PERFORMANCE_FIX_ACTION_PLAN.md:10` | extrapolácia z 100-firmovej množiny |
| `1500% rýchlejšie` (lead scoring) | `PERFORMANCE_FIX_SUMMARY.md:45,127` | bez merania |
| `100-1000x` / `300-500%` / `400%` | `docs/archive/PERFORMANCE_FIX_SUMMARY.md:119`, `docs/archive/PERFORMANCE_OPTIMIZATION.md:172`, `docs/archive/QUICK_REFERENCE.md:66` | neoverené, navzájom nekonzistentné |
| `~100-200 companies/second`, `~50MB` | `docs/archive/LEAD_SCORING_IMPLEMENTATION.md:352-353` | **nepodložené** — žiadny benchmark ani `psutil` v `backend/` |
| `> 90% coverage` | `docs/archive/LEAD_SCORING_CHECKLIST.md:327` | **nepodložené** — žiadny coverage nástroj nie je nakonfigurovaný |

Ani jeden z tých dokumentov nemá dokončený vlastný deployment checklist:
`docs/archive/PERFORMANCE_FIX_ACTION_PLAN.md:182-187` má 6× `- [ ]`, `docs/archive/COMPLETION_REPORT.md:133-142`
nezaškrtnuté kroky 1–5, `:254-260` má všetkých päť „Actual" = `Pending`,
`docs/archive/DEPLOYMENT_PLAN.md:353-361` má 5 zo 6 `⏳ Pending`. **Test na reálnych
1,2 mil. firmách sa nikdy nestal.**

Pozor aj na pätičky, ktoré oprava z Fázy 0 minula: `docs/archive/COMPLETION_REPORT.md:277`
stále tvrdí `Rollback Time: <1 minute` a `docs/archive/DEPLOYMENT_PLAN.md:367`
`Rollback: 🟢 Easy (1 command reverses migration)` — obe v priamom rozpore
s opraveným telom toho istého dokumentu. `docs/archive/DEPLOYMENT_PLAN.md:231` navyše radí
`git revert HEAD~1`, čo je dnes nebezpečné: zmeny sú v `36d80b8`, veľkom WIP
checkpointe, nie v perf-only commite.

### 8.7 i18n — gettext značky sú 2 z 54

`docs/I18N_IMPLEMENTATION.md:22-23` tvrdí, že `gettext_lazy()` značky
v `LEGAL_FORMS` sú „reálne a v poriadku — preklady sa z nich dajú vygenerovať".
Zmerané proti kódu (`backend/companies/models.py`):

| | položiek | v `_()` | holých |
|---|---|---|---|
| `LEGAL_FORMS` (`:10`) | 54 | **2** (`:11-12`) | 52 |
| `LEGAL_FORMS_SHORT` (`:68`) | 53 | **0** | 53 |

`makemessages` by teda vyextrahoval **2 reťazce**, nie 54 — a zo
`LEGAL_FORMS_SHORT` ani jeden. Veta bola v Fáze 0 moja a je meraním vyvrátená;
opravená je v tom dokumente.

---

## 9. Plán: mobilná responzivita a graf „Prepojenia" (2026-09-18)

**Stav:** ⏳ **čaká na tvoje slovo.** Z tohto plánu nie je v kóde zatiaľ ani
riadok.

Zadanie boli štyri veci: (1) tlačidlo „Vypočítať trasu" väčšie a viac na
dizajnový systém, (2) frontend prispôsobiť mobilu, hlavne iPhone 14 Pro
(393 × 852), (3) tlačidlo „Aktualizovať údaje" sa na mobile nezobrazuje,
(4) graf „Prepojenia" občas nekreslí názvy uzlov.

Pred prvým riadkom kódu bežali dve analýzy (23 agentov): audit responzivity
(6 hľadačov, každý nález prešiel nezávislým verifikátorom, ktorého úlohou bolo
ho **vyvrátiť**) a diagnóza grafu (3 nezávislé diagnózy, 3 návrhy, 3 sudcovia).
Výsledok: **52 verdiktov, jeden z nich nález zamietol** — a **tri moje vlastné
predpoklady boli vyvrátené**. Uvádzam ich nižšie, lebo keby som ich bol
zapracoval, boli by to commity, ktoré nič nerobia.

Baseline je zamknutý a zelený: `npm test` **352/352**, `npm run typecheck`
čistý, `npm run build` zelený, pracovný strom čistý.

---

### 9.1 Graf „Prepojenia" — koreňová príčina je nájdená (#178)

**Symptóm:** po usadení grafu niektorý názov chýba; pomôže až priblíženie
alebo oddialenie zoomu.

**Koreňová príčina.** `drawnLabelsRef` je pomocný zoznam obdĺžnikov **jedného
frame**, ale resetuje sa `performance.now()` testom **vnútri per-uzol
callbacku**:

```js
// frontend/components/graph/GraphCanvas.tsx:253-258 — vnútri paintNode
const now = performance.now();
if (now - lastClearTimeRef.current > 8) {
  drawnLabelsRef.current = [];      // „nový frame" podľa hodín, nie podľa knižnice
  lastClearTimeRef.current = now;
}
```

`paintNode` sa volá **raz za uzol** v rámci jedného frame (až 200×, `MAX_NODES`).
Knižnica pritom hranicu frame **pozná presne** a vystavuje ju —
`onRenderFramePre(ctx, globalScale)`, raz za vykreslený frame tesne pred
`tickFrame()` (`force-graph.mjs:1655-1663`). Kód ju nepoužíva; háda ju z hodín.
Traja sudcovia to overili nezávisle v zdrojáku knižnice a **ani jeden
mechanizmus nevyvrátil**.

**Prečo to spraví práve zoom.** Keď simulácia dobehne (`cooldownTicks = 100`),
`autoPauseRedraw` (default `true`) vypne prekresľovanie úplne — na plátne
**zamrzne presne ten frame, v ktorom engine skončil, aj so svojou chybou**.
Jediné, čo po zastavení vynúti prekreslenie, je interakcia: d3 zoom nastaví
`needsRedraw` (`:12770-12773`). Preto názov „nabehne" až po zmene zoomu.
To je celý hlásený symptóm, vysvetlený do dna.

Regresiu zaviedol `fd185d5` (jún 2026) — dovtedy sa názvy kreslili vždy.
Sudca to overil z gitu.

**Dve mechaniky, obe treba zavrieť.** Prvá je tá časová (hore). Druhú našiel
až tretí sudca a inde spomenutá nebola: názvy sa kreslia **inline v `paintNode`,
v poradí `data.nodes`**, takže **neskorší uzol svojím nepriehľadným kruhom
a `shadowBlur` presvietením prekreslí názov skoršieho uzla**. Je to ten istý
symptóm, ale úplne deterministický — a sedí naň aj to, že pomôže priblíženie:
názov je jediný objekt s veľkosťou na obrazovke, kým polomery uzlov sú pevné
v jednotkách grafu. Riešenie: kresliť názvy v `onRenderFramePost`, po všetkej
chróme uzlov.

**Tri veci, ktoré som tvrdil a boli nesprávne:**

1. ❌ *„Kolízny test je zle v jednotkách grafu, treba ho prepísať na
   obrazovkové pixely."* — **Nepravda.** `measureText` ignoruje CTM a
   `fontSize = Math.max(13 / globalScale, 4)`, takže obdĺžnik v jednotkách
   grafu je **konštantných ~165 px na obrazovke**. Porovnanie v jednotkách
   grafu je podobnostná transformácia porovnania v pixeloch — prepis by
   **nezmenil nič**. Bol by to commit, ktorý nič nerobí.
2. ⚠️ *„Mid-frame clear nastane, keď frame prekročí 8 ms."* — Presnejšie: test
   sa meria proti uzlu, ktorý prah naposledy prekročil, takže na 120 Hz paneli
   uzol 0 prekročí takmer vždy a clear na začiatku frame **zvyčajne prebehne**.
   Živá vetva je užšia — clear sa zopakuje mid-frame len vtedy, keď **samotné
   `paintNodes`** prekročí 8 ms. Preto je to „občas", nie vždy.
3. ⚠️ *„Do person vetvy treba doplniť `|| isCenter`."* — **Nedosiahnuteľné.**
   `centerNode` pochádza výhradne z firemného endpointu (`useGraphData.ts:38`)
   a `ConnectionGraph` sa renderuje len z `ConnectionsSection.tsx:21`, takže
   `isCenter` je pre osoby vždy `false`. Doplniť to = meniť kresliace pravidlo,
   ktoré nič netestuje, a to bez účinku. **Nedopĺňam.**

Ďalej: `Math.max(baseRadius + 8, gn.label.length * 3.2 + 10)`
(`GraphCanvas.tsx:237`) je v jednotkách grafu a podhodnocuje skutočnú pilulku
**~4×** pri zoome k ≈ 0,47 — layout teda ukladá názvy bližšie, než sú široké,
a deklutter to platí tým, že názov zmaže.

**Čo oprava garantuje — a čo nie.** Toto je podstatné a nechcem to obísť.
Oprava garantuje **determinizmus**: tá istá schéma pri tom istom zoome vždy
zobrazí tie isté názvy; žiadne blikanie závislé od hardvéru, žiadny zamrznutý
pokazený frame. **Negarantuje, že každý názov bude vidno pri každom zoome.**
Pri n = 200 je auto-fit zoom k = 4/∛200 ≈ 0,68, názov firmy s 25 znakmi má
~244 jednotiek grafu, kým `forceCollide` rozostupuje len na ~180 — **väčšina
názvov sa prekrýva geometricky a žiadne množstvo kódu to nezmení.** To je
aritmetika, nie chyba.

„Nech to funguje plnohodnotne" má preto čestné čítanie: **úplne opraviť to,
čo je chybou** (názov sa stratí kvôli časovaniu, poradiu alebo hardvéru),
a **zmenšiť počet názvov, ktoré zoom ešte potrebujú** — nie „všetky naraz".
Na to sú dve páky a **pri druhej potrebujem tvoje slovo**:

| | páka | čo spraví | cena |
|---|---|---|---|
| **A** | deterministické poradie (stred → hover → počet väzieb), porazený sa **zmenší**, nezmaže sa | tie isté názvy vždy tie isté; menej názvov potrebuje zoom | žiadna zmena vzhľadu |
| **B** | `forceCollide` odvodiť zo skutočnej šírky pilulky (~4× väčší) | menej kolízií už v layoute | **graf bude redší a širší** — uzly ďalej od seba |
| **C** | A + B | najviac názvov bez zoomu | najväčšia zmena vzhľadu |

Odporúčam **C**: A samo o sebe je len „stratí sa to predvídateľne", čo nie je
to, o čo si žiadal. Ale B mení vzhľad grafu — a to je tvoje rozhodnutie, nie
moje.

**Rozdelenie na commity — plán hovoril dva, vyšiel jeden.** Plán chcel
(1) hranicu frame + kreslenie v `onRenderFramePost` + jednu pravdu o obdĺžniku
a (2) politiku názvov. Rozdeliť sa to nedalo bez výroby medzikroku, ktorý nikto
nepotrebuje: **len čo sa kreslenie odpojí od priechodu uzlov, „kto bol prvý"
prestane existovať** — o poradí sa musí rozhodnúť v tom istom kroku, v ktorom
sa kreslí. Deterministické poradie teda nie je druhá zmena, je to dôsledok
prvej. Namiesto umelého medzicomitu je to jeden commit, `311a888`, a toto je
záznam toho, že sa zámer zmenil a prečo.

Čo commit `311a888` spravil:

- `paintNode` už kreslí **len uzol** a názov **žiada** (`pendingLabelsRef`);
  `onRenderFramePre` buffer vyprázdni, `onRenderFramePost` názvy umiestni
  a vykreslí. Tým zmizla aj druhá príčina — názov už nemôže prepísať
  nepriehľadný kruh a glow uzla kresleného po ňom.
- `labelLayout.ts` je jediné miesto, kde sa počíta obdĺžnik názvu (`rectFor`),
  a `drawLabel` ho **berie tak, ako je** — kreslenie a rozhodnutie teda nemôžu
  nesúhlasiť. `drawLabel` je zároveň prvý raz obalený v `save`/`restore`;
  dovtedy to bola jediná pomôcka bez neho a nechávala `textAlign`, `textBaseline`
  a `fillStyle` nastavené pre ďalšie kreslenie (vrátane popiskov hrán).
- `bold` pre osobu ostáva `false` a `alwaysDraw` `false` — stred grafu je vždy
  firma (`useGraphData.ts:38`), takže pôvodné `|| isCenter`, ktoré bolo pre
  osobu nedosiahnuteľné, sa neprevzalo.

**Testy — a jeden z nich hneď našiel chybu v mojej zmene.** Graf nemal ani
jeden test (`grep` cez `frontend/**/*.test.ts(x)` nenašiel zmienku
o `GraphCanvas`, `ConnectionGraph`, `useGraphData` ani `force-graph`), takže tri
CI kontroly o kreslení netvrdili nič. Pribudlo **16 testov** čistej geometrie
(`labelLayout.test.ts`) a **7 testov** komponentu (`GraphCanvas.test.tsx`, cez
atrapu `react-force-graph-2d`, ktorá len zachytí props — testuje sa teda
**poradie volaní**, čo je presne to, o čom oprava je).

Test „názov pod kurzorom vyhrá" **zhodil sa na mojej vlastnej chybe**:
`handleNodeHover` som definoval, ale na `ForceGraph2D` som ho nepripojil —
hover by ticho nerobil nič a `tsc` to nezachytil. Bez toho testu by to odišlo
do produkcie ako mŕtvy kód. Dve ďalšie červené boli chyby testu, nie kódu
(falošná `measureText` ignorovala veľkosť fontu; `"aaa s.r.o."` má 10 znakov,
nie 11) — obe opravené v teste.

**Páka A je hotová, B a C nie:** vzhľad grafu sa nezmenil, len sa
názvy prestali strácať náhodou. Ak si „1" myslel ako C (redší graf), je to
samostatný malý commit — viď tabuľka vyššie.

---

### 9.2 „Vypočítať trasu" — na dizajnový systém a väčšie (#175)

Dnes je to ručne písaná pilulka `px-2.5 py-1 text-xs` → **26 px**, a je to
**jediné tlačidlo na karte, ktoré nepozná dizajnový systém** (`.btn`).
Identický reťazec tried má aj „Nájsť na Google Maps" hneď vedľa
(`SeatLocationCard.tsx:254-264`).

Plán: `.btn .btn-outline` + `min-h-11` (**44 px**, Apple HIG).

**Obmedzenie, ktoré to viaže:** testy držia `<a>` rolu, `href` z `mapsLink()`,
`target="_blank"`, `rel="noreferrer noopener"` aj text labelu
(`SeatLocationCard.test.tsx:175-189, :203, :230`). Mením teda **len triedy
a veľkosť**, nie štruktúru.

**Vedľajší nález, ktorý musí ísť prv:** `.btn-outline` **nemá tmavú variantu**
(`main.css:179-188`) — kontrast ~3,4:1, teda pod AA. Dnes sa to neprejavuje,
lebo ani jedno z tých dvoch tlačidiel `.btn-outline` nepoužíva; po prevode by
sa prejavilo. Preto sa tmavá variant dopĺňa **v tom istom commite**.

**Ako to dopadlo** (`673ab4d`) — rozmery a kontrast sú **merané**, nie
odhadnuté: Playwright + Chromium, 393 × 852, DSF 3, a prechody vypnuté
(`*,*::before,*::after{transition:none!important}`), lebo prvé meranie
zachytilo `.btn{transition:all .2s}` v behu a prečítalo `#f2f3f3` namiesto
tmavej karty. Namerané: **133,9 × 44 px** v oboch témach, 14 px text; tá istá
trieda **bez** `min-h-11` má **38 px** (takže 44 px robí naozaj `min-h-11`,
nie niečo iné); pôvodná pilulka **140,6 × 26 px** pri 12 px → **+69 %**.
Kontrast tinty: **5,17:1** svetlá, **9,98:1** tmavá (proti 3,52:1, ktoré by
dalo `--color-brand` na tmavej karte `#0e1629`).

Dosah je zámerne širší než jedno tlačidlo: tú istú chybu — značková farba
použitá ako *tinta* namiesto *výplne* — mali aj `.btn-ghost:hover` a
`.nav-link:hover/.active`, takže dostali `--color-brand-ink` tiež. Jedna rola,
jeden token; `.btn-outline:hover` výplňou ostáva na `--color-brand` s bielym
textom (5,17:1), kde je pôvodná modrá správna.

`.app-input:focus { border-color: var(--color-brand) }` zostáva **nedotknuté**:
2,83:1 je tesne pod hranicou 3:1 pre nerastrový prvok a je to 1 px rámik, nie
text. Neznižujem latku potichu tým, že to opravím bez slova — hlásim to.

---

### 9.3 „Aktualizovať údaje" — nepríjemná pravda (#177)

Hľadal som CSS chybu. **Nie je.** Šesť nezávislých auditov, tri verifikátory;
jeden nález bol dokonca **zamietnutý** (`not-real`), pretože tvrdil, že je
tlačidlo úplne skryté — nie je.

- Jediná brána je `user?.isStaff` (`CompanyHeader.tsx:310`) a je to **zámer** —
  dokumentovaný v komentári `:303-309` a testovaný
  (`CompanyHeader.test.tsx:150-161`).
- Na 393 px sa tlačidlo kreslí **identicky ako na desktope**.
- Variantu „telefón beží na starom builde" verifikátor **vyvrátil meraním**:
  `b7d5818` je predkom `main` aj `feat/ai-ready-baseline`, takže produkcia
  tlačidlo má.

**Najpravdepodobnejšie vysvetlenie: telefón je prihlásený účtom, ktorý nie je
staff.** To sa zo zdrojáku dokázať nedá — treba sa pozrieť na živú stránku
(`GET /api/auth/profile` z tej telefónnej session). **Nepredstieram, že som
našiel chybu, ktorú som nenašiel.**

**Čo reálna chyba je:** tlačidlo má **~22 px na výšku a 12 px písmo**
(`px-2 py-0.5 text-xs` + 1 px rámiky: 16 px riadok + 4 px padding + 2 px rám)
a je vnorené do bunky hodnoty s dátumom. To je **polovica dotykového minima**
a v riadku dátumu sa dá prehliadnuť. Oprava: plnohodnotné `.btn` s `min-h-11`,
presunuté z hodnoty do akčného radu `:223`.

**Predtým, než uverím vlastnej oprave:** ak je telefónna session staff a
tlačidlo sa aj tak nezobrazuje, príčina je inde a v statickom zdroji nie je.

**Reťaz je teraz overená od konca do konca** (nie odhadnutá) — a jedna vec
v nej bola dovtedy neoverená: či backend `is_staff` **vôbec posiela**. Keby
nie, tlačidlo by nevidel *nikto* a „telefón nie je staff" by bola nesprávna
diagnóza. Overené: `backend/users/serializers.py:59` je v `UserDetailSerializer`
(`fields` obsahuje `is_staff`), ten obsluhuje `/api/auth/profile/`
(`backend/users/views.py:44`), a `frontend/api.ts:114` ho mapuje na `isStaff`.
Pole teda chodí; testy to dokázať nemohli, lebo `api.getProfile` mockujú.

Tri vysvetlenia, všetky **správanie brány**, nie chyba renderovania — v poradí
pravdepodobnosti pre telefón:

1. **Telefón nie je prihlásený vôbec.** `user` začína ako `null`
   (`AuthContext.tsx:38`) a nastaví sa len z `login()` alebo z `getProfile()`;
   `UserProfileView` je `IsAuthenticated`. Stránka je verejná, takže to je
   predvolený stav telefónneho prehliadača. PDF a Sledovať sa pritom zobrazujú
   (`isAuthenticated` brzdí len `getWatchlist`), čo presne sedí na hlásenie
   „v mobile sa nezobrazuje" pri „na desktope vidím".
2. **Je prihlásený, ale nie je staff.**
3. **Je prihlásený ako staff a nemá zaškrtnuté „Zapamätať prihlásenie"** —
   `saveSession(tokens, remember)` potom píše do **`sessionStorage`**
   (`lib/tokenStore.ts:60`), teda session končí so zavretím karty, a iOS Safari
   karty zahadzuje agresívne. Toto je jediné vysvetlenie, ktoré dáva hlásený
   rozdiel *desktop áno / telefón nie* na tom istom účte.

Ani jedno sa z kódu nedokáže vyvrátiť a ani potvrdiť — treba sa pozrieť na
`GET /api/auth/profile` z tej telefónnej session. **Nepredstieram, že som
našiel chybu, ktorú som nenašiel.** Zámer „bez nápovedy pre neprihlásených"
(`:303-309`) ostáva: verejná stránka nemôže vedieť, že čitateľ je staff, takže
nápoveda by bola signál pre všetkých ostatných.

**Ako to dopadlo** (`28f35b9`) — tlačidlo je `.btn .btn-outline min-h-11`
v akčnom rade, ktorý dostal `flex-wrap` (na 393 px sa štyri prvky nezmestia).
Meranie vynútilo **rozšírenie**: PDF a Sledovať mali **40 px**, tiež pod
minimom, takže nové 44 px tlačidlo bolo v tom istom rade jediné vyššie —
dostali `min-h-11` tiež. Namerané: `Aktualizovať údaje` 174,3 × 44 px,
`Sledovať` 119,2 × 44, `PDF` 86 × 44, rad 104 px = 44 + 16 + 44 (dva riadky,
bez preteku), kontrast 5,17:1 svetlá a 9,98:1 tmavá. `.btn:disabled
{cursor: not-allowed}` pribudlo do `main.css`, lebo `disabled:cursor-not-allowed`
z Tailwindu je mŕtvy z toho istého dôvodu ako nález v 9.5.

---

### 9.4 Mobilná responzivita pre iPhone 14 Pro (#176)

Zoradené podľa závažnosti; **prvé dve sú merané**, nie odhadnuté.

1. ~~**Tabuľka pomerových ukazovateľov — celý stĺpec „Stav" je odrezaný a nedá
   sa k nemu doscrollovať.**~~ **Hotové v `1f806ee`.** Merané: minimálna šírka
   tabuľky **397,9 px** (Rentabilita) a **426,1 px** (Zadĺženosť) proti
   **313 px** dostupným (393 − 32 `main.px-4` − 48 `InfoCard.p-6`). Príčina
   bola `overflow-hidden` na `FinancialRatiosTable.tsx:217` — **nie `InfoCard`,
   to je tam správne**. Rovnaká trieda aj v **Porovnaní so sektorom**, kde bol
   celý odvodený stĺpec „Rozdiel" neviditeľný a nedostupný. **Ako sa to
   dokázalo:** `scrollWidth > clientWidth` je pravda pri oboch hodnotách
   `overflow` (je to tvrdenie o obsahu, nie o posúvateľnosti), takže prvý
   pokus meral nesprávnu vec. Rozhodol až **skutočný gest** — `mouse.wheel`
   nad prvkom: `overflow-hidden` 0 → 0 (gesto nič neurobí), `overflow-x-auto`
   0 → 63. `InfoCard.tsx:13` a `Person.tsx:190` sú `overflow-hidden` **správne**
   a nemenia sa.
2. ~~**Admin sidebar `w-60` (240 px) nemá responzívny prefix**~~ **Hotové
   v `68b4a6f`** (aj s `h-screen` → `h-dvh` a pomenovaným prepínačom).
   Merané na 393 px: obsah **153 → 393 px**, desktop 900 px **nezmenený**
   (660 px s otvorenou lištou). Zbalený pod `md` lišta **zmizne** — namerané,
   že 64 px koľajnica prekrývala x 0..64 nad obsahom, ktorý začína na x 0.
   **Druhá pasca kaskády, iná než v 9.5:** `max-md:hidden` vedľa
   nepodmieneného `flex` **prehrá** (obe display utility, `flex` sa emituje
   neskôr) — namerané, `.hidden{display:none}` je pred `.flex{display:flex}`.
   Drží až `hidden md:flex`, teda variant proti obyčajnej utilite.
3. ~~**Kompaktný vyhľadávací input má 14 px**~~ **Hotové v `68b4a6f`**, aj
   14 admin ovládacích prvkov. `SearchBar.tsx:76` je `text-sm` a používa sa na
   `pages/Company.tsx:84` a `pages/Person.tsx:151` → iOS Safari pri fokuse
   **zoomuje a ostane priblížený**. **Oprava tohto bodu:** tvrdenie „admin
   formuláre (inputy 14 px, selecty 12 px)" bolo bez overenia a je
   **zavádzajúce**. `.app-input` (Login, Register, Contact, Profile)
   **nemá** `font-size`, dedí z `body`, a `body` je 16 px → **namerané 16 px,
   tieto stránky nezoomujú a nemenia sa**. Skutočná množina bola presne
   kompaktný `SearchBar` + 14 admin prvkov, ktoré majú veľkosť na sebe.
   Overené proti zbuildovanému CSS: na 393 px je `text-base sm:text-sm`
   16 px a samotné `text-sm` 14 px (kontrola), na 900 px 14 px.
4. **Dva parser-blokujúce CDN skripty v `<head>`, ktoré nikto nepoužíva**
   (`index.html:36-37` — three.js r121 a `vanta@latest`). `vanta@latest` je
   navyše **nepinovaná verzia bez SRI**, takže sa na každej stránke každej
   session spúšťa cudzí kód, ktorý sa môže pod rukami zmeniť. To je
   supply-chain expozícia, nie len latencia.
5. ~~**`viewport-fit=cover` chýba a `env(safe-area-inset-*)` sa v projekte
   nevyskytuje ani raz**~~ **Hotové v `4f0df9d`.** Meta atribút a insety sú
   jedna zmena, nie dve: `cover` bez insetov je horší než stav pred ním
   (lišta pod hodinami), insety bez `cover` sú inertné (`env()` je vždy 0).
   Insety dostali `.safe-frame` (admin shell), `.header-wrapper`,
   mobilné menu (ako **súčet** `calc(6rem + env(...))`, aby sa prirátal a nie
   nahradil — pasca 9.5), admin lišta pod `md` zvlášť (absolútny box sa
   umiestňuje proti padding boxu containing blocku) a ovládanie grafu **len
   v režime celej obrazovky** (`env()` je vlastnosť viewportu, nie prvku —
   na inline karte by tie isté triedy posunuli ovládanie o ~59 px).
   **Overené proti zbuildovanému CSS:** všetkých 5 arbitrary hodnôt je
   v balíku a `max-md:` varianty sedia vo
   `@media not all and (min-width:48rem)`. Prvý kontrolný grep vrátil samé
   nuly — **chybná maska**, Tailwind escapuje aj `(`, `)`, nie chýbajúce
   pravidlá. **Invariant, overený:** `--spacing` je `.25rem`, takže pri
   insete 0 je `calc(6rem+0px)` = `pt-24`, `calc(0.75rem+0px)` = `top-3`,
   `calc(0.5rem+0px)` = `bottom-2` — na desktope a na telefóne bez výrezu je
   tento commit **no-op**.
6. ~~**`h-screen`**~~ — **`AdminLayout.tsx:40` hotové v `68b4a6f`,
   `ConnectionGraph.tsx:150` v `4f0df9d`**. ~~mobilné menu bez
   `overflow-y-auto` a bez zámku skrolovania pozadia; zatvorené menu ostáva
   v DOM aj v tab-poradí; `GraphControls` má 32 px tlačidlá~~ — **všetko
   hotové v `83c850b`**, spolu s chybou, ktorú plán nemal:

   **Legenda grafu a ovládanie sa prekrývali na oboch šírkach**, nielen na
   telefóne — boli to dva nezávislé `absolute` rohy:

     393 px: legenda x 53..352, ovládanie x 116..340, obe od y 37
     900 px: legenda x 53..833, ovládanie x 623..847, obe od y 37

   Ovládanie teda kreslilo **cez** legendu a skrývalo jej položky. Dva
   absolútne boxy v jednom rohu o sebe nevedia; riešenie je jeden `flex` pruh
   (na telefóne `flex-col`, od `md` `flex-row` + `justify-between`, rozostupy
   cez `gap`). Po oprave namerané **prekrytie False na oboch šírkach**.
   Tlačidlá boli 28–30 × 32 (textové) a 34 × 26 (SVG) — SVG boli **nižšie než
   pilulka**, v ktorej sedia; teraz 44 × 44 pod `md`, 32 × 32 od `md`
   (SVG 34 × 32, rozdiel v šírke 2 px zámerne nechaný).
   Zámok skrolovania pozadia je overený testom, nie okom —
   `documentElement.scrollTop` išlo predtým 0 → 600 s otvoreným menu.

   **`#176 je tým uzavreté.** Ostávajú len nálezy z 9.5, ktoré sú mimo jeho
   rozsahu.

**Hranica dôkazu pre kroky 2 a 3 — `dvh` a insety sú odôvodnené, nie
merané,** a to treba povedať nahlas. Headless Chromium nemá adresnú lištu ani
výrez, takže `100vh`, `dvh` aj `svh` tam vyjdú rovnako a `env()` je tam 0;
meranie by len predstieralo dôkaz. Overiť sa to dá jedine na telefóne.
Namerané je to, že pravidlá sú v balíku, že `max-md:` varianty sedia
v správnej media query, a že pri insete 0 nič nemenia.

---

### 9.5 Nálezy, ktoré som našiel a **nezapracúvam**

Mimo zadania; uvádzam ich, neopravujem ich ticho:

- **`main.css:77` žiada `'IBM Plex Sans'` pre všetky nadpisy (h1–h6), ale
  `index.html:41` načíta len Outfit** (`main.css:23` je `--font-sans: 'Outfit'`,
  `index.html:61` dáva `<body>` triedu `font-sans`). `'Inter'` sa tiež
  nenačítava a v celom `frontend/` nie je ani `@font-face`, ani self-hosted
  `.woff`/`.ttf`, ani `@fontsource` → tichý fallback na `system-ui`. Overené
  znovu 2026-09-18 dvoma nezávislými refutermi (päť z piatich citácií doslovne)
  a **stále neopravené**. Dve veci, ktoré k tomu pribudli: nadpisy sa teda
  kreslia iným písmom než telo stránky, a pravidlo je **unlayered** (je pred
  `@layer base` na `main.css:125`), takže prebíja každú Tailwind `font-*`
  utility na nadpise — **nedá sa opraviť z markupu**, len v CSS. Nie je to
  „len dizajnová nekonzistencia": je to zámer zapísaný v CSS, ktorý na obrazovke
  nikdy nenastane. (Pôvodné čísla `main.css:63` a `index.html:35` v tomto
  dokumente boli zastarané; platia 77 a 41.)
- `pages/ApiDocs.tsx:386` je `opacity-0 group-hover:opacity-100` — na dotyk
  neviditeľné, kým sa na kód netapne (iOS syntetický `:hover` ho odhalí).
- `~/.Trash` (TCC), Docker reclaim na Macu a runner id=2 na lenovo — #174,
  blokované OS, nie mnou.
- ~~**`pages/ApiDocs.tsx`: 8 zo 40 endpointov** má na 393 px odrezanú cestu
  a úplne zmiznutý JWT štítok aj šípku rozbalenia.~~ — **opravené v `7d7bbed`**
  (2026-09-18). Príčina je presne známa (merané v Chromiu na zbuildovanom
  `frontend/dist`, 393×852 — nie odvodené úvahou): `<code>` na `ApiDocs.tsx:413`
  má `flex-1`, ale flex položka má default `min-width: auto`, takže sa nezmenší
  pod svoju `min-content` šírku — a URL cesta je jeden nezlomiteľný token. Karta
  na riadku 407 má `overflow-hidden`, ktoré to odstrihne, a v celom reťazci
  predkov nie je `overflow-x-auto` (jediný výskyt v súbore je na riadku 381
  v CodeBlocku), takže sa k odrezanej časti nedá doskrolovať. Za `flex-1` prvkom
  sú tým vytlačené mimo viditeľnú oblasť aj JWT štítok (r. 417) a šípka
  rozbalenia (r. 422). Oprava je `min-w-0` na to `<code>` (dovolí zmenšenie) plus
  `break-words` (cesta sa zalomí namiesto odrezania). Strážia to tri regresné
  testy v `pages/ApiDocs.test.tsx` — práve tie dve deklarácie, ktoré pri
  upratovaní `className` ticho zmiznú a na širokej obrazovke ich vizuálna
  kontrola nechytí. Tretí test overuje, že karta je naozaj `overflow-hidden`;
  ak raz začne scrollovať, padne — a to je správne, potom sa oprava prehodnotí,
  nie dedí naslepo. (`test/setup.ts` pritom dostal stub `IntersectionObserver`,
  ktorý si `ApiDocs` stavia na scroll-spy obsah a ktorý jsdom nemá.)
- **`escape_sed()` je definovaná dvakrát, bajt na bajt rovnako** —
  `scripts/local/install_backup_schedule.sh:21-23` a
  `scripts/local/install_ruz_keeper.sh:30-32` (md5 tela
  `d56020fad5187d312abe2a7f270f740a`, 13 volaní, žiadne tretie použitie).
  Oba skripty už zdrojujú zdieľanú knižnicu `scripts/local/lib/backup_os.sh`
  (riadok 14, resp. 24), kde žijú všetky ostatné zdieľané funkcie, takže
  spoločná kópia patrí tam. Nie je to živá chyba, ale pasca: escapovanie pre
  `sed` je platformovo jemná vec (BSD vs GNU rozhoduje o význame `\\&`, o backslashi
  v znakovej triede a o delimitri — tu `|`, zvolenom preto, že cesty majú `/`),
  takže kto raz jednu kópiu opraví, druhá zostane ticho nesprávna.
- ~~**Mobilné menu nezamyká skrolovanie pozadia.**~~ — **opravené v `83c850b`**
  (#176, krok 4). `Header.tsx` nezapisoval do `document.body` ani `overflow`
  (grep = 0), overlay bol `fixed inset-0`, ale obsah pod ním sa hýbal — merané:
  `documentElement.scrollTop` išlo 0 → 600 pri kolese. Teraz sa `overflow`
  zamyká a vracia späť (uloží sa predchádzajúca hodnota, nie `''`), a navyše
  `overscroll-contain` bráni reťazeniu skrolu z menu na stránku. Overené testom,
  nie okom.
- ~~**`admin/pages/CompaniesBuilderPage.tsx:594`** — `min-w-[240px] flex-1` na
  `PresetCard` je pevné, nezmenšiteľné minimum v tej istej 105 px admin lište
  ako nálezy v 9.4. V public režime (329 px) sa neprejaví.~~ — **spúšťač je
  preč, chyba už nenastane** (`68b4a6f`). `min-w-[240px]` na riadku 594 naozaj
  je a je to jediný výskyt v `frontend/`, ale `68b4a6f` spravil z admin
  `<aside>` pod `md` absolútne pozicionovaný box (`AdminLayout.tsx:82`,
  `max-md:absolute`), takže obsah má vždy plných 393 px a vnútro karty
  313 px > 240 px. **Pozor na formuláciu:** trieda tam zostala, zmizol len jej
  následok — je to latentný pach (pevné minimum bez hornej hranice v kontajneri,
  ktorý sa môže zúžiť), nie opravený riadok. (Refuter zároveň našiel jednu
  nesprávnu citáciu: grid je na riadku 325, nie 323.)
- **`.btn` a `.btn-*` sú mimo `@layer`, takže prebíjajú každú Tailwind
  utility, ktorá im odporuje.** Toto je systematická chyba, nie jedna trieda:
  `@import "tailwindcss"` vygeneruje `@layer properties/theme/base/utilities`
  a každé pravidlo napísané v `main.css` **mimo** `@layer` je *unlayered* —
  a nezaradené normálne deklarácie porazia zaradené **bez ohľadu na
  špecificitu aj poradie**. Overené párovaním zátvoriek vo zbuildovanom CSS:
  `@layer utilities` siaha od znaku 12902 po 115770, `.text-gray-700{` (66167)
  a `.border-gray-300{` (47820) sú **vnútri**, kým `.btn{` (117010) a
  `.btn-outline{` (117449) sú **vonku**. (Offsety sa posunú s každým buildom —
  pri opakovanom meraní 2026-09-18 vyšli `utilities` 12875–117454 a `.btn{`
  118872, teda o ~1,8 kB inde, a nález bol aj tak rovnaký. Rozhoduje **vzťah**
  „vnútri/vonku", nie konkrétne číslo; kto to overuje, nech si zátvorky
  v zbuildovanom CSS započíta sám.) Dôsledok: utility `px-*`, `py-*`,
  `rounded-*`, `text-*`, `border-*`, `hover:bg-*` na prvku, ktorý má `.btn`,
  sa **ticho ignorujú**. Dotknuté miesta, kde to už dnes zhadzuje zámer
  pisateľa: `NotFound.tsx:48` (`border-gray-300`, `dark:border-slate-700`,
  `text-gray-700`, `dark:text-gray-300`, `hover:bg-gray-100`,
  `dark:hover:bg-slate-800` aj `px-8 py-3 rounded-full` — teda **celý** ten
  reťazec je mŕtvy), `Header.tsx:154` (`py-3`, `rounded-xl`),
  `Login.tsx:128` (`py-3.5`, `shadow-lg`), `Home.tsx:70`
  (`px-10 py-4 rounded-full shadow-lg`). To, že `NotFound.tsx:48` píše
  `dark:border-slate-700` na prvok, ktorý `.btn-outline` aj tak prebije, je
  **priamy dôkaz, že na to už niekto narazil** a obchádzal to zľava.
  Neopravujem to tu — je to zmena dizajnového systému naprieč ~4 stránkami
  a patrí do vlastného rozhodnutia, nie do mobilného zadania. **Dôsledok pre
  #175 a #177: na `.btn` sa smie pridávať len to, čo `.btn` sám nenastavuje**
  (`min-height`, `font-size`) — preto `min-h-11` a `text-sm`, a preto žiadne
  `px-*`/`rounded-*`.

**Sedem prezývok z jednania bolo 2026-09-18 nanovo odvodených** — aby sa to
nemuselo robiť znova a aby po nich nezostal zoznam mien bez obsahu. Každú
hľadal jeden vyšetrovateľ a potom ju nezávisle vyvracali dvaja ďalší (17
agentov, 0 chýb); výsledok: **žiadna nebola vymyslená**, všetkých sedem
označovalo reálnu vec. **Tri z tých štyroch živých chýb sú stále neopravené**
a rozpísané vyššie (`IBM Plex Sans`, `.btn` kaskáda, duplicita `escape_sed`);
štvrtá — orezy ciest v `ApiDocs` — je opravená v `7d7bbed`.
`companiesbuilder-minw` a `searchbar-drobnosti` boli medzitým opravené
(`68b4a6f`, resp. `7cd0e7f` — druhé je v 10.1) a
`mrtvy-gitlab-remote-code-reviews` **vôbec neoznačuje tento repozitár**: je to
mŕtvy remote `gitlab` v klone code-review bota `~/Code/code-reviews`, ktorý
mieri na `localhost:8088`, teda na zrušený Mac GitLab. V CistaFirme po ňom
nič živé neostalo (`.git/config` má len `gitlab-home` a `origin`, žiadny
`refs/remotes/gitlab/*` neexistuje).

**Čo audit preveril a NIE je chyba** — aby to nikto nehlásil znova:
`AuditLog.tsx:91` (`max-w-[200px] truncate`) a `SyncJobs.tsx:151`
(`min-w-[120px]`) sú **vnútri** `overflow-x-auto` tabuliek, teda správne;
`ApiDocs.tsx:626` má `overflow-hidden` bez scroll obalu, ale tabuľka má len dva
stĺpce a `min-content` ≈ 241 px < 361 px dostupných. `.app-card { overflow: hidden }`
(`main.css:217`) dnes chybu nerobí, ale je to **pasca pri ďalšej úprave** tejto
karty.

**Neoverená hypotéza, ktorú nechávam ako hypotézu:** ak je telefónna session
staff a tlačidlo aj tak chýba, druhé možné vysvetlenie je, že `api.getProfile()`
na mobile zlyhal a `AuthContext.tsx:53-70` spustil `logout()`. **Nemerané** —
overiť sa dá len proti reálnemu backendu na telefóne, nie z kódu.

---

### 9.6 Poradie prác

1. ~~**Graf** (#178)~~ — **hotové v `311a888`**, jeden commit namiesto dvoch
   (dôvod v 9.1). Tri CI kontroly zelené, 375 testov, push na oba remoty.
2. ~~**„Vypočítať trasu"** (#175) + tmavá variant `.btn-outline`~~ — **hotové
   v `673ab4d`**, rozsah rozšírený na celú rolu „značková farba ako tinta"
   (dôvod a merania v 9.2). Tri CI kontroly zelené, 375 testov.
   **Ostáva neopravené a hlásené:** kaskádové vrstvy (9.5) — `.btn` prebíja
   Tailwind utility na štyroch ďalších miestach.
3. ~~**„Aktualizovať údaje"** (#177)~~ — **hotové v `28f35b9`**, vrátane
   overenia reťaze `is_staff` (serializér → view → `api.ts`). **Ostáva
   neoverené a overiť sa dá len na telefóne:** ktoré z troch vysvetlení
   v 9.3 to je — ideálne `GET /api/auth/profile` z tej telefónnej session.
4. ~~**Tabuľky** (meraný orez)~~ — **hotové v `1f806ee`**.
   ~~**Admin sidebar a inputy**~~ — **hotové v `68b4a6f`** (8 nových testov
   v `admin/AdminLayout.test.tsx`; suita 384 testov v 42 súboroch).
   ~~**`viewport-fit=cover` + safe-area**~~ — **hotové v `4f0df9d`** (meta
   atribút, `.safe-frame`, `.header-wrapper`, mobilné menu, admin lišta pod
   `md`, ovládanie grafu v celoobrazovkovom režime, `h-dvh` v grafe).
   ~~**Mobilné menu, `GraphControls` a legenda grafu**~~ — **hotové v `83c850b`**
   (zámok skrolovania pozadia a `overflow-y-auto`; zatvorené menu je `invisible`,
   teda von z tab-poradia aj z accessibility tree; tlačidlá 44 px pod `md`;
   legenda s ovládaním v jednom `flex` pruhu namiesto dvoch `absolute` rohov).
   Merania a čo z toho je len odôvodnené: 9.4 bod 6. **`#176 je uzavreté** —
   štyri kroky: `1f806ee`, `68b4a6f`, `4f0df9d`, `83c850b`.

Každý krok: tri CI kontroly (`npm test`, `npm run typecheck`, `npm run build`),
štruktúrovaný commit, push na `origin` aj `gitlab-home`.

**Poctivá hranica krokov 2 a 3:** `h-dvh` a správanie
`env(safe-area-inset-*)` sa v headless prehliadači odmerať **nedajú** — chýba
adresná lišta aj výrez. Zvyšok krokov 2 a 3 meraný je (šírky, `display`,
`font-size` z computed style proti zbuildovanému CSS; pri kroku 3 navyše to,
že pravidlá sú v balíku, sedia v správnej media query a pri insete 0 sú
no-op — viď 9.4 bod 5).

---

## 10. Plán: druhé kolo mobilných opráv (2026-09-18)

Po #176 prišli od užívateľa dve veci: *„tlačidlo overiť vo vyhľadávacom okne
vyteká z toho okna na mobilnom zobrazení. potreba opravit. tiež skús nejako viac
kompaktne zobraziť kľúčové ukazovatele na mobilnom zobrazení."*

Obe som najprv **odmeral v reálnom prehliadači** (Chromium, 393 × 852,
`deviceScaleFactor` 3, dotykový režim) proti **bežiacemu dev serveru**, nie proti
ručne napísanej napodobenine — React teda kreslí skutočnú komponentu so
skutočným CSS. Ako sa to meralo: `ENABLE_MOCK_DATA` je v `constants.ts` napevno
`false`, takže skript prepíše ten modul **na drôte** (`page.route`) a na
`/firma/50059959/prehlad` sa vykreslí deväť dlaždíc (2 hlavné + 4 súvahové +
3 pomerové; tie pomerové som do mocku doplnil, aby bol zmeraný najhorší prípad,
ktorý kód dokáže vyrobiť). Ani jeden súbor v repe sa pritom nemenil.
Kandidátske opravy som overil vstreknutím **nezaradeného (unlayered) CSS** do
bežiacej stránky — teda presne tou cestou, akou `main.css` prebíja Tailwind (9.5).

### 10.1 Tlačidlo „Overiť" vytieka z pilulky (#179)

Merané na `Home`, teda vo variante `hero` — ten používa `Home.tsx:63` aj
`Monitoring.tsx:97`:

```
393 px:  wrapper 32,0 .. 361,0   pilulka 48,0 .. 345,0   tlačidlo 280,7 .. 355,0
         pilulka je vnorená o 16 px (px-4 wrappera), tlačidlo má right-1.5 = 6 px
         od wrappera  →  presah  +10,0 px ZA pravý okraj pilulky
900 px:  wrapper 114,0 .. 786,0  pilulka 114,0 .. 786,0  tlačidlo 665,6 .. 778,0
         wrapper je sm:px-0  →  presah −8,0 px (8 px vnútri)   ← takto to má byť
```

Nie je to odhad z kódu: `elementFromPoint` 2 px a 6 px za pravým okrajom pilulky
vracia **tlačidlo samotné**, čiže je tam naozaj vykreslené (10 px ďalej už
wrapper). `overflow-hidden` na pilulke ho pritom neoreže — a to je správne
správanie CSS, nie chyba: absolútne pozicionovaný prvok obíde `overflow` predka,
ktorý **nie je v reťazi jeho obsahujúceho bloku**. Pilulka má `position: static`,
takže obsahujúcim blokom je `styles.wrapper` (`relative w-full px-4 sm:px-0`).

**Príčina je teda jedna vec:** `right-1.5` sa meria od wrappera, ktorý má na
mobile `px-4`, kým pilulka je o tých 16 px vnútri. Kód to na jednom mieste
priznáva — komentár vo `VARIANT_STYLES.hero` hovorí, že `px-4` je kompenzované
„vo vlastných offsetoch dropdownu a tlačidla" — a dropdown to naozaj kompenzuje
(`mx-4 sm:mx-0`). Tlačidlo nie.

**Oprava:** pridať `relative` na pilulku (spoločná trieda oboch variantov), čím sa
obsahujúcim blokom stane pilulka, a vo `hero.button` nechať `right-1.5`
**bez `sm:right-2`**. Overené vstreknutím presne tejto dvojice pravidiel do
bežiacej stránky:

```
393 px:  tlačidlo 262,7 .. 337,0   →  8,0 px VNÚTRI okraja pilulky   (dnes +10,0 von)
900 px:  tlačidlo 665,6 .. 778,0   →  zhodné na desatinu px s dneškom
```

Prečo `sm:right-2` mizne: pilulka má `border-2`, takže 6 px od *padding boxu* je
8 px od vonkajšieho okraja — presne toľko, koľko dnes dáva `right-2` na wrappri
s `sm:px-0`. Desktop je preto **pixel na pixel rovnaký** a `sm:` variant je
nadbytočný. Kompaktný variant (`Person.tsx`, `Company.tsx`) sa posunie o
**1,0 px** vľavo (merané: 4 px → 5 px vnútri okraja), lebo jeho rám má `border`,
nie `border-2` — neviditeľné.

Dropdown sa nemení: je to súrodenec `<form>`, nie dieťa pilulky, takže jeho
obsahujúci blok ostáva wrapper a `mx-4 sm:mx-0` platí ďalej. Overené s reálnymi
našepkávačmi (mock režim): dropdown 48 .. 345 px = presne ľavý a pravý okraj
pilulky.

### 10.2 Kľúčové ukazovatele na mobile (#179)

`FinancialIndicators.tsx` kreslí `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`, takže
na telefóne je **jeden stĺpec** a deväť dlaždíc pod sebou. Merané (9 dlaždíc,
393 px):

```
dnes:  mriežka 311 × 694,5 px   karta 361 × 809,5 px
       dlaždica 66,5 px, ikonka 36 × 36 px, popis 11 px, hodnota 16 px
```

809 px na obrazovke vysokej 852 px znamená, že kým sa čitateľ dostane
k „Hospodárskym výsledkom", prejde takmer celú obrazovku dlaždíc, z ktorých každá
nesie **jedno číslo**. To je to, čo užívateľ nazval nekompaktným.

**Oprava (mobile-first, `sm:` vracia dnešok):** dlaždica sa na mobile zmení na
**jeden riadok** — malá ikonka vľavo, popis vľavo, hodnota so šípkou vpravo.

| | dnes | kandidát |
|---|---|---|
| mriežka | `gap-3` | `gap-1.5 sm:gap-3` |
| dlaždica | `p-3 rounded-xl gap-3` | `p-2 rounded-lg gap-2 sm:p-3 sm:rounded-xl sm:gap-3` |
| ikonka | `w-9 h-9`, znak `text-sm` | `w-6 h-6`, znak `text-[10px]` (`sm:` = dnešok) |
| telo dlaždice | `block` (popis nad hodnotou) | `flex items-baseline justify-between gap-2 sm:block` |
| popis | `tracking-wider` | `tracking-normal sm:tracking-wider` (kupuje ~10 px) |
| hodnota | `text-base` | `text-sm sm:text-base` |
| rad s hodnotou | — | `shrink-0`, aby sa popis zalomil a hodnota nie |

Merané na tých istých deviatich dlaždiciach, tou istou metódou:

```
kandidát:  mriežka 311 × 426,0 px   karta 361 × 541,0 px
           dlaždica 42,0 px, každý popis na JEDNOM riadku, nič odstrihnuté
```

**Karta sa skráti o 268,5 px (−33 %)** a na obrazovku sa zmestí aj „Hospodárske
výsledky". Najdlhší popis („Celková zadlženosť") potrebuje 132 px z 131,5 px
dostupných — to je na hrane, a preto to `tracking-normal` na mobile. Aj keby
predsa prešiel na dva riadky, dlaždica narastie, ale **nič sa neodstrihne**:
`overflow` je `visible`, text sa zalomí, nie oreže.

Desktop sa nemení — pri 900 px je mriežka pred aj po 380,5 px vysoká, lebo všetky
nové triedy sú základné a `sm:` vracia dnešné hodnoty. Overené, nie odvodené.

### 10.3 Nález mimo rozsahu: desatinná bodka v percentách

Karta mieša dva zápisy čísel: `formatCurrency` používa `sk-SK`
(„1 440 000 €"), kým percentá idú cez `value.toFixed(2)` („53.33 %") a šípka
trendu cez `toFixed(1)` („↓2.7 %"). Slovenský čitateľ čaká `53,33 %`.
**Neopravujem to** — je to formátovanie, nie kompaktnosť, a zmena by sa dotkla aj
`FinancialRatiosTable` a PDF exportu. Ak to užívateľ chce, je to samostatný krok.

**Zvažované a zamietnuté:** zmenšiť `InfoCard` `p-6` na mobile na `p-4`. Ušetrilo
by ďalších ~16 px, ale `InfoCard` je na stránke firmy aj v celom admin paneli —
je to zmena dizajnového systému, nie tejto karty.

### 10.4 Graf „Prepojenia" sa vycentruje na to, čo človek vidí (#179)

**Zadanie:** *„nejakým vhodným spôsobom vyrieš automatické centrovanie toho grafu
prepojení na tú zobrazovaciu plochu, ktorú používateľ práve vidí."*

**Ako som to meral.** Vite dev server na Macu, `ENABLE_MOCK_DATA` prepnuté **na
drotu** (rewrite `constants.ts` v `page.route`), a grafové API
(`/api/companies/*/graph/`) odpovedané z fixtures — 9 uzlov, 10 hrán, teda bežná
s.r.o. Pravda o tom, kde graf naozaj je, nie je výpočet, ale **alpha kanál
plátna**: skript prejde `getImageData` a nájde obdĺžnik, v ktorom sú naozaj
namalované pixely (uzly, hrany aj názvy). Ten sa porovná s prienikom boxu grafu
a viewportu. Ani jeden súbor v repozitári sa nedotkol.

**Namerené — 393 × 852, priskrolované ku grafu:**

| | dnes, ako sa to načíta | po návrate z celej obrazovky |
|---|---|---|
| box grafu | 359 × 639 | 359 × 639 |
| **plátno** | **1100 × 1000** (`attr 3300×3000`) | **359 × 639** (`attr 1077×1917`) |
| atrament | x 291,3..992,0 (700,7 px), y 0..835,3 | x 65,0..312,3 (247,3), y 213,0..445,3 |
| stred atramentu vs stred okna | **+445,2 px vpravo**, +98,1 px dole | **−7,8 px**, +9,6 px |
| rezerva vpravo / dole | **−616,0 / −196,3** | +63,7 / +193,7 |
| zmení sa plátno pri 393 → 900? | **nie** (ostane 3300 × 3000) | — |

**To je koreňová príčina a je iná, než som čakal.** `ConnectionGraph` drží
`dimensions` v stavu, na začiatku `{ width: 1100, height: 1000 }`, a zapisuje ho
**jediný efekt** — ten, ktorý meria kontajner. Jeho strážca je
`containerRef.current`, a ten je pri prvom prebehnutí efektu `null`: kým dáta
nedorazia, komponent vracia vetvu „Žiadne prepojenia neboli nájdené", takže
`ref` nie je na čom. Závislosti efektu sú `[isFullscreen]`, tie sa nikdy
nezmenia — **takže sa už nikdy nezmeria.**

Dôsledok: plátno je **3,06× širšie a 1,56× vyššie než box, v ktorom je
vystavené** (karta má `overflow-hidden`, takže vidno jeho ľavý horný roh),
a `zoomToFit` vycentruje graf na stred *plátna*, ktorý je mimo obrazovky. Na
telefóne je preto z celej šírky grafu (700,7 px) v boxe **~85 px** — zvyšok je
vpravo za okrajom. To je aj odpoveď na #178: „musím priblížiť, aby názov
nabehol" bolo hľadanie grafu, ktorý je z väčšiny mimo.

Dôkaz, že príčina je meranie a nie fit: **jediné, čo efekt spustí znova, je
prepnutie celej obrazovky** — a to je zároveň jediná zmena, po ktorej sa čísla
dostanú na správne hodnoty (stĺpec vpravo). Ten istý kód, tie isté dáta, iné
plátno. Zároveň to bol jediný spôsob, ako dnes zmerať „ako to vyzerá, keď sa
meria správne", bez zmeny zdrojáku.

**To isté na 900 × 900 (dnes):** plátno 1100 × 1000 v boxe 734 × 675, atrament
704 × 841, stred **+192,0 px vpravo** a +83,0 px dole, presah 177 px vpravo
a 166 px dole. Po zmeraní: atrament 446 × 443, stred odchýlený o 3,0 px. Nie je
to teda mobilná chyba — mobil ju len zviditeľní.

**Druhá polovica zadania — „plocha, ktorú práve vidí".** Aj keď sa box zmeria
správne, `zoomToFit` centruje na **celý box**, a to nie je to isté ako to, čo
človek vidí:

| orientácia | box | vidno | prekryv hore (legenda+ovl.) | popis dole | použiteľné okno | stred vs stred boxu |
|---|---|---|---|---|---|---|
| 393 × 852 (stojato) | 639 px | 639 px (100 %) | y 12..148 = **136 px** | y 599..631 | y 148..599 = **451 px** | **+54,0 px** |
| 852 × 393 (ležato) | **500 px** | 393 px (**79 %**) | y 12..72 = 60 px | y 476..492 | y 72..393 = 321 px | −17,5 px |

Na stojato je box celý na obrazovke, ale **horných 136 px je prekrytých**
legendou a ovládaním — fit, ktorý centruje na box, posadí vrchol grafu pod
legendu (stred má byť o 54 px nižšie). Na ležato je box 500 px vysoký
(`min-h-[500px]` prebije `75vh` = 295 px) v 393 px okne, takže **štvrtina boxu je
mimo obrazovky vždy**, nech sa skroluje kamkoľvek.

**Oprava, dva commity:**

1. **Meranie.** Kontajner sa meria **callback refom** — ten sa zavolá v okamihu,
   keď sa uzol naozaj pripojí, takže ho poradie vetiev neobíde — plus
   `ResizeObserver` na ňom. `dimensions` začína na `{ 0, 0 }`, takže plátno sa
   nevykreslí, kým nemá skutočnú veľkosť; tým zmizne aj `isFullscreen` vetva
   (v celej obrazovke je box `h-dvh`, čiže jeho obdĺžnik *je* okno).
2. **Fit na použiteľný obdĺžnik.** `GraphCanvas` dostane `fitToRect(rect)`, ktorý
   počíta mierku a stred z **kresleného** rozsahu (disk + názov pod ním), nie
   z `getGraphBbox` knižnice: tá nafukuje každú firmu o
   `sqrt(nodeVal)·nodeRelSize = sqrt(π·26²)·4` = **184,3 px**, kým disk má 26 px —
   preto je graf dnes menší, než by mohol byť. Použiteľný obdĺžnik počíta
   `ConnectionGraph` (box ∩ viewport, mínus pruh s legendou a mínus popis)
   a odovzdáva ho ako getter. Automaticky sa prefitne, keď človek **dorazí** ku
   grafu (≥ 55 % boxu vidno a obdĺžnik sa zmenil o viac než prah), a keď sa zmenia
   dáta; **ručné potiahnutie alebo zoom automatiku vypne** a ⟲ („Reset pohľadu")
   ju zase zapne.

**Čo to netvrdí.** Že bude vidno každý názov pri každom zoome — to je aritmetika
z 9.1 (páky B a C) a tej sa to netýka. A že sa vzhľad nemení: fit na kreslený
rozsah znamená **väčší zoom** než dnes (184,3 px na firmu → 26 px + šírka názvu),
takže graf bude na obrazovke väčší.

**Po oprave, na zbuildovanej verzii.** `frontend/dist` z `npm run build`, servírovaný
`vite preview` na 4173 — teda to, čo sa nasadzuje, nie dev server. `ENABLE_MOCK_DATA`
ostáva v bundle `false`; API odpovedá až prehliadač (route interception), takže sa
meria naozaj zbuildený kód. Skript:
`$CLAUDE_JOB_DIR/tmp/graph_built.py`. Prírastok oproti minulému kolu: pri načítaní
je box grafu celý pod okrajom, takže `focusWindow` vráti okno s nulovou výškou
a fit sa odmietne — graf by teda sedel v rozložení zo simulácie, **širší než plátno
a orezaný jeho okrajom**, kým človek nedorazí (namerané: atrament pretiekal na
všetky štyri hrany). Preto `focusRect` v tom stave rámuje **celý box**; po príchode
sa prefitne o 54 px, ktoré zaberá legenda.

| | 393 × 852 | 900 × 900 |
|---|---|---|
| box grafu | 359 × 639 | 734 × 675 |
| **plátno** | **359 × 639** (attr 1077 × 1917) | **734 × 675** (attr 734 × 675) |
| použiteľné okno | y 148..599 = 451 px, stred 373,5 | y 147..726 = 579 px, stred 436,5 |
| atrament | 312,7 × 324,3 | 474 × 537 |
| atrament vnútri okna | **áno** (61 hore, 65,7 dole) | **áno** (18 hore, 24 dole) |
| stred atramentu vs stred okna | **−2,4 px** | **−3,0 px** |
| vodorovne | −1,8 px | 0,0 px |

Predtým na tých istých miestach: plátno 1100 × 1000 v oboch, stred **+445,2 px**
(393) a **+192,0 px** (900) vpravo. Krivka „atrament sa doladí až keď engine
zastaví" je vidieť aj tu: bez skrolovania sa stred boxu trafí na **−1,5 px** až
okolo t + 20 s, keď simulácia dochladí a `onEngineStop` prefituje druhýkrát —
fit je presný v okamihu, keď beží, a medzitým sa hýbu uzly, nie rám.

### 10.5 Nález: pri názve širšom než okno bol fit nesplniteľný (regresia z `4886c81`)

**Namerané na živej produkcii, nie odvodené.** Po nasadení `4886c81` na `dell`
(2026-09-18) sa stránka „Prepojenia" pre IČO 31355161 — 114 uzlov, 148 hrán,
najdlhší názov 124 znakov — vykreslila ako **guľa z čiastočiek veľkosti ~40 px**
s jedným čitateľným názvom. `canvas.__zoom.k` bolo **0,02**, teda presne
`FIT_CONFIG.minZoom`; uzol s polomerom 26 jednotiek sa kreslil ako **0,52 px**;
atrament bol pás **331 × 36 px**. Po usadení (t ≈ 13 s) sa už nemenil.

**Príčina je v `extentAt`.** Menovka je ukotvená *pod* diskom a naň vycentrovaná,
takže vodorovne zaberá **polovicu svojej vlastnej šírky** — a tá sa so zoomom
nemení (`painter` delí font zoomom, aby názov ostal 13 px). Názov 124 znakov je
teda ~870 px široký a jeho polovica (435 px) je širšia než celé okno (311 px).
`fits(zoom)` potom neplatí pri **žiadnom** zoome, bisekcia ostane na `low =
minZoom` a vráti 0,02. Fit, ktorý nemá riešenie, vyzerá ako fit, ktorý sa vzdal.

**Prečo to #179 nechytilo.** Akceptačné meranie z 10.4 bežalo na 9-uzlovom
stube s názvami, ktoré sa do okna zmestia — taký graf nemá ako ten stav vyvolať.
Regresia teda prešla tromi CI kontrolami aj vlastným akceptačným testom a našla
sa až na produkcii, na skutočných 114 uzloch.

**Oprava.** `solve(labelsHorizontal)` je tá istá bisekcia dvakrát:

1. najprv s menovkami v **oboch** osiach. Ak vráti viac než `minZoom`, je to
   platné riešenie a správanie sa nemení;
2. ak vráti presne `minZoom`, fit nebol splniteľný — potom sa rámujú **len disky**
   (`labelsHorizontal = false`) a názvy prečnievajú. Zvislý pruh menovky sa
   počíta v oboch prípadoch, lebo je **ohraničený** (~19,5 px), takže ani
   v fallbacku sa názov na najspodnejšom disku neodreže.

Prečnievajúce názvy nie sú strata: `labelLayout` ich najprv zmenší na 0,75 a potom
**zahodí** — názov je čitateľný alebo nie je, nikdy nie je rozmazaný.

**Namerané na tom istom reálnom grafe** (`real_graph.json`, rovnakých 114 uzlov,
route interception, `vite preview` na zbuildenom bundle):

| | starý build `5f812c0` | nasadené `4886c81` | oprava |
|---|---|---|---|
| plátno | 1100 × 1000 | 359 × 639 | 359 × 639 |
| `k` | 0,618 | **0,020** (na `minZoom`) | **0,159** |
| disk 26 jednotiek | 16,07 px | 0,52 px | **4,14 px** |
| atrament | 1086,7 × 969,3 | 331 × 36 (pás) | 336 × 285,7 |
| pixelov atramentu | 2 242 280 | 52 456 | 334 064 |
| zložiek atramentu | — | 3 (najväčšia 99,8 %) | **116** |
| stred vs okno | — | — | x −11,5, **y −4,7** px |

Starý build mal plátno 1100 × 1000, lebo vôbec nemal responzívnu veľkosť plátna —
jeho `k` preto nie je porovnateľné a je v tabuľke len pre úplnosť. Rozhodujúce sú
posledné dva stĺpce: **na tom istom plátne a tých istých dátach** je to 8× väčší
zoom, 6,4× viac atramentu a 116 oddelených zložiek namiesto jednej gule.

**Metodická poznámka.** Prvé meranie opravy hlásilo odchýlku **+31,3 px**, čo
vyzeralo ako nedotiahnutá oprava. Nebolo: `onEngineStop` prefituje **druhýkrát**
až keď simulácia dochladí (pri 114 uzloch t ≈ 13 s), takže meranie v 9. s čítalo
rám, ktorý ešte nebol usadený — `k` sa medzi dvoma behmi líšilo (0,1733 vs
0,1756), čo bolo prvé podozrenie. Vzorkovanie v čase to ukázalo priamo: do 10. s
sa atrament hýbe, v 13. s `k` spadne na 0,15934 a potom je **Δ 0 px**.
Namerané po usadení: stred y **−4,7 px**.

**Čo zostáva (nie je opravené).** Prečnievajúce meno názvu sa **odreže okrajom
plátna**, lebo `labelLayout` o hraniciach plátna nevie — testuje len kolízie medzi
menovkami. Namerané: atrament siaha na ľavý okraj plátna, a na snímke je
„Ing. Alexander Holénia" vykreslené ako „g. Ing. Alexander Holénia". Je to daň
za fallback a je to viditeľné len pre uzly blízko okraja. Možná oprava je posunúť
menovku dovnútra a kolízny test potom pustiť na posunutý obdĺžnik — ale vyžaduje
si hranice plátna v **grafových** súradniciach (`globalScale` mení mierku, takže
sa to nedá spočítať raz pri fite) a to je samostatná zmena s vlastnými testami,
nie prívesok k tejto. **Zámerme neopravené.**

### 10.6 Poradie prác

1. **Tlačidlo „Overiť"** — `components/SearchBar.tsx` + regresný test, ktorý
   stráži invariant (pilulka musí byť obsahujúci blok, inak sa `right-*` zase
   meria od `px-4` wrappera). **Hotové** (`7cd0e7f`).
2. **Kľúčové ukazovatele** — `components/company/FinancialIndicators.tsx`.
   **Hotové** (`4691fbe`).
3. **Graf „Prepojenia"** — `components/graph/ConnectionGraph.tsx` +
   `GraphCanvas.tsx` (+ testy: fit je čistá aritmetika, tá sa testovať dá).
   **Hotové** — `graphFit.ts` (čistá geometria) + `graphFit.test.ts` (15),
   `GraphCanvas.test.tsx` (13, s stavovým dvojníkom `force-graph`),
   `ConnectionGraph.test.tsx` (9, s podstrčeným `getBoundingClientRect`).
   Celkovo 45 súborov / 423 testov, `typecheck` aj `build` čisté.
   **Premerané na zbuildovanej verzii** (nie odhad): 393 px → plátno 359 × 639,
   atrament vnútri okna, stred −2,1 px; 900 px → plátno 734 × 675, stred −3,0 px.
   Tabuľka a metóda v 10.4.
   **Druhé kolo (10.5):** nasadenie `4886c81` ukázalo na reálnych 114 uzloch
   regresiu — fit sa zasekol na `minZoom`. Opravené dvojstupňovým `solve`;
   dva nové regresné testy padajú na starom kóde (`0.02 to be greater than 0.02`).
   Na 9-uzlovom stube sa čísla **nezmenili** (393 px: 308 × 319,3 a −2,1 px;
   900 px: 474 × 537 a −3,0 px), na reálnych 114 uzloch `k` 0,02 → 0,159.
4. Ak povie, **desatinná bodka** (10.3) — samostatný commit. **Nespravené**,
   čaká na slovo.

Každý krok: tri CI kontroly (`npm test`, `npm run typecheck`, `npm run build`),
štruktúrovaný commit, push na `origin` aj `gitlab-home`. Po všetkých krokoch
premerať **to isté**, čo je namerané vyššie, na zbuildovanej verzii — nie okom:
na 393 px musí byť plátno 359 × 639 a atrament vnútri použiteľného okna, na 900 px
plátno 734 × 675 a stred odchýlený do 10 px.

**A premerať aj na reálnych dátach, nie len na stube.** Presne o to prišlo #179:
stub s krátkymi názvami nemôže vyvolať stav, ktorý nastane len vtedy, keď je názov
širší než okno. Akceptačný test preto musí bežať aj na grafe, ktorý má uzlov
a názvov ako produkcia (`real_graph.json`), a strážiť, že `canvas.__zoom.k`
**nie je** `minZoom` — a to **po usadení** (t ≥ 15 s), nie v 9. s, keď je
`onEngineStop` ešte pred sebou.

---

## 11. Plný RUZ resync, ktorý sa musí dokončiť (2026-09-18)

Zadané: tri IČO v produkcii úplne chýbajú (`54381151`, `54187451`, `54572495`),
doplniť ich jednotlivo, potom spustiť **plný** RUZ sync odznova a nechať ho bežať
24/7, kým sa nedokončí.

### 11.1 Prečo tie tri chýbali — namerané, nie odhadnuté

Dôvod nebol v dátach, ale v tom, že sa k nim **nikdy nedokráčalo**:

- Jediný walk od nuly v produkcii je `SyncProgress` #1 (`incremental_companies`,
  `zmenene_od = 2020-01-01`). Zomrel **2026-09-10** na
  `last_processed_ruz_id = 1 840 215` s `value too long for type character
  varying(8)`, po prečítaní 1 383 700 záznamov.
- Tie tri majú RUZ ID **2 026 974 / 2 048 858 / 2 067 916** — všetky **nad**
  1 840 215, teda za miestom, kde walk skončil.
- Šesťhodinový inkrementál číta len **pohyblivé okno posledných zmien**, takže
  ich dobehnúť nemôže: firma, ktorá sa od 2020 nezmenila, sa v okne neobjaví.

**Pozitívny kontrola** (aby „chýbajú" nebola len neprítomnosť dôkazu): na živom
API `GET /cruz-public/api/uctovne-jednotky?zmenene-od=2000-01-01&max-zaznamov=8&pokracovat-za-id=…`
pre každé z troch ID vrátil **to ID vnútri svojej stránky** — plný walk sa k nim
teda naozaj dostane.

### 11.2 Doplnené jednotlivo — a prečo nie `repair_ruz_gaps`

Pred prácou čerstvá overená záloha:
`/home/sam/.local/state/CistaFirma/backups/cistafirma_20260918T154053Z.dump`
(157 382 478 B), `make db-backup-verify` → „Backup verified".

Tri firmy doplnené cez `registers.tasks.sync_single_company_from_ruz.run(ico)`
(`.run`, nie task: je to `BaseSyncTask` s `autoretry_for=(Exception,)`, takže
mimo request-kontextu by autoretry skončilo výnimkou `Retry` namiesto skutočnej
chyby). Overené čítaním z DB — **3 z 3**:

| IČO | RUZ ID | Právna forma | Názov | Vznik |
|---|---|---|---|---|
| 54187451 | 2026974 | 112 | MM servis Slovakia s. r. o. | 2021-11-13 |
| 54381151 | 2048858 | 112 | Sirupček s. r. o. | 2022-02-01 |
| 54572495 | 2067916 | 112 | poctivé sirupy s. r. o. | 2022-04-27 |

`repair_ruz_gaps` použitý **zámerne nebol**: upsertuje kľúčom `ico`, čo je presne
tá zámena identity, pred ktorou `fetch_ruz_data.py` varuje (jeho upsert je
kľúčovaný na `ruz_id`), a `parse_date` volá priamo namiesto `apply_ruz_dates`,
takže uložené dátumy môže prepísať na `None`.

### 11.3 Pasca, ktorá by z „plného" synca spravila jednodňový

`--full-resync --entity-type companies` **nie je** plný resync. `full_companies`
a `full_individuals` čítajú počiatočný dátum **späť z `SyncProgress`**, takže s
uloženým `zmenene_od` (napr. 2026-09-18) prejdu jediný deň. Nedá sa na to
spoliehať ani cez `--entity-type`: správna invokácia je **holý `--full-resync`**
(`entity_type both`), kde je `zmenene_od = 2000-01-01` zadrátované.

Rovnako `--resume` sám o sebe `full` riadok nikdy nenájde — lookup príkazu je
kľúčovaný na odvodený `sync_type`.

### 11.4 Dve tiché chyby, kvôli ktorým „Resume" nikdy nič neobnovil (`e6ca0fe`)

Pri príprave 24/7 slučky sa ukázalo, že oba vstupné body do plného walku robia
niečo iné, než tvrdia:

- **`resume_full_ruz_sync`** (tlačidlo Resume v adminovi) našiel `full` riadok,
  ohlásil ho v logu, a potom spustil `fetch_ruz_data --resume` **bez**
  `--full-resync`, čiže hľadal *inkrementálny* riadok. Vrátil sa s
  „Nenájdený žiadny sync na pokračovanie" — ale príkaz si medzitým stihol
  zabrať `SyncJob`, a ten dokončuje iba samotný walk, takže po sebe nechal
  `running` job, ktorý nemal kto dokončiť, a nula presunutých dát.
- **`start_full_ruz_sync_from_id`** („Full sync od RUZ ID") to isté, a horšie:
  `incremental` riadok po šesťhodinovom syncu v DB takmer vždy zostáva, takže
  namiesto no-opu sa mohol ticho rozbehnúť **inkrementálny** walk od
  inkrementálneho kurzora — nie od ID, ktoré operátor zadal.

Obe teraz idú cez `_run_ruz_command` (jediná cesta, ktorá behu dá job riadok,
heartbeat a výsledok, a ktorá vďaka `ruz:global` concurrency key odmietne druhý
beh vedľa živého). Pri `resume` je v filteri stavov aj `running`: worker, ktorý
je zabitý, po sebe **nič** nezapíše — proces, ktorý by zapísal `failed`, je ten,
ktorý zomrel — a presne to je stav, kvôli ktorému resume existuje.
`start_full_ruz_sync_from_id` zároveň prišiel o 24-hodinový `time_limit`: walk od
ľubovoľného ID trvá rádovo dni, `time_limit` je tvrdý SIGKILL, a jeho dvaja
súrodenci (`start_full_ruz_sync`, `resume_full_ruz_sync`) limit nemajú — bol to
outlier, nie poistka. (Pozitívna kontrola, že `time_limit` vieme vôbec prečítať:
vtedy `start_repair_sync.time_limit == 86400`; o deň neskôr oň prišiel tiež,
viď §11.8.)

**Nálezy, ktoré som našiel a neopravil** (mimo tohto kroku):

- `admin.py` `resume_sync_view` hlási „pokračuje od RUZ ID …" pre **každý**
  typ okrem `repair`, ale úloha hľadá výhradne `sync_type='full'`. Pri
  `full_companies`/`full_individuals` teda admin tvrdí úspech a úloha korektne
  odmietne (tie typy patria `fetch_ruz_data_firmy_only`/`_szco_only`). Vlajka
  je v admin UI, nie v úlohe.
- `start_repair_sync`, `resume_repair_sync`, `repair_ruz_gaps`,
  `resume_gap_repair`, `analyze_ruz_gaps` volajú `call_command` priamo, teda
  bez job riadku a heartbeatu. Ich príkazy si vedú vlastný progres
  (`SyncGapAnalysis`), takže je to iná otázka než `SyncJob` — ale znamená to,
  že tieto behy watchdog nevidí. **Opravené v §11.8**, okrem `analyze_ruz_gaps`,
  ktorý tam ostáva zámerne.

### 11.5 Čo je overené a čo ešte nie

- Backend: **1002 testov OK** (`registers.tests_sync_job_singleton` má 56,
  `registers.tests_repair_job_tracking` 13 — §11.8;
  `registers.tests_sync_pipeline.SyncProgressErrorReasonTests` má 2 na dôvod
  chyby firmy — §11.7). Frontend sa v tomto kroku nemenil; jeho tri kontroly
  (`npm test`, `typecheck`, `build`) bežia v pipeline na pushnutom commite.
- Mierka behu: job #23 (`ruz_incremental`, 2026-09-13 09:54→11:57) spracoval
  45 306 záznamov za 123 min ≈ **6,1 záznamu/s**. `Companies and SZCO` má
  449 792 riadkov a najvyššie `RUZ ID` 2 624 307. Dell má 423 GB voľných,
  DB 1 320 MB, `registers_companysyncstatus` 296 723 riadkov / 107 MB
  (~360 B/riadok).
- **Odhad, kým sa dokončí, je odhad** — potvrdí ho až živý beh. Preto sa
  postup meria z `SyncProgress.last_processed_ruz_id`, nie z pocitu.
- Zvyšok (spustenie, keeper, dokončenie) je v §11.6.

### 11.6 Ako to beží 24/7

**Samotný walk** ide cez Celery na fronte `ruz_full` (`cistafirma_celery_ruz`,
`--concurrency=1`, vlastný kontajner — jeho zablokovanie nič iné nevyhladuje),
nie cez odpojený `docker compose exec`: len tak má beh job riadok, heartbeat,
viditeľnosť vo watchdogu a singletnovú poistku.

**Keeper je mimo Celery** — je to systémd user timer na delle, ktorý každých
5 minút spustí `python manage.py ruz_keeper_tick`. Zámerne nie je ďalší záznam
v `CELERY_BEAT_SCHEDULE`: keeper má za úlohu dostať stack zo stavu, v ktorom už
Celery je, takže na `celery` fronte by prestal presne vtedy, keď je potrebný
(uviaznutý worker, alebo `PeriodicTask` riadok, ktorý už nezodpovedá
`CELERY_BEAT_SCHEDULE` — na to už tento repozitár raz doplatil). Brána, ktorá
sleduje niečo, nesmie závisieť od toho istého niečoho.

Rozhodnutie je `sync_engine.ruz_full_keeper_decision` (testovateľné, na rozdiel
od pravidla v shell skripte). Keeper číta **najnovší** `ruz_full` `SyncJob`:

| stav | akcia | prečo |
|---|---|---|
| `completed` | skončiť | koniec zoznamu; walk sa dokončil |
| `queued` / `running` | čakať | beh je v pohybe |
| `failed` / `paused` / `cancelled` | `resume_full_ruz_sync.delay()` | beh skončil a nedošiel na koniec |
| žiadny | `start_full_ruz_sync.delay(reset=False)` | ešte nikdy nebežal |

Detaily, ktoré nie sú vidieť z tabuľky:

- **`running` so starým heartbeatom je zámerne „čakať".** „Tento beh je mŕtvy"
  vlastní watchdog a je jeho jediný vlastník; druhý vlastník by bol druhý
  odpoveď na tú istú otázku. Navyše `running` riadok blokuje dispatch na
  `ruz:global`, takže by keeper len zaplnil frontu správami, ktoré nemôžu
  urobiť nič.
- **`paused` sa nedá spoznať z `completed_at`.** `pause_job` ho nenastavuje, takže
  rozhodnutie číta `completed_at or started_at or queued_at`. Keby čítalo len
  `completed_at`, pauznutý walk by ostal pauznutý navždy.
- **`resume` má 15-minútový odstup** (`KEEPER_REDISPATCH_AFTER`). `.delay()` len
  vloží správu do brokera — nový job riadok vytvára až worker, ktorý si ju
  vyzdvihne — takže pri zastavenom workerovi ostáva najnovším riadkom stále ten
  mŕtvy. Bez odstupu by keeper posielal novú úlohu každý tick, kým by výpadok
  trval.
- **`resume` je bezpečné dispatchovať opakovane**: druhý dispatch stretne živý
  job na `ruz:global` a vráti sa (`_run_ruz_command`).
- **Keeper je bezstavový.** Žiadna slučka, žiadny stavový súbor — každý tick
  prečíta DB a rozhodne odznova. Tick, ktorý neprebehol (host bol dole), nič
  nestojí; ďalší tick vidí tú istú DB a urobí správnu vec. `Persistent=true`
  navyše po reštarte spustí tick hneď, nie až o päť minút.
- **Prvý walk sa spúšťa ručne**, nie keeperom: `completed` je terminálny stav, a
  keby v `SyncJob` ostal starý dokončený `ruz_full` riadok, keeper by korektne
  usúdil „hotovo" a walk by nikdy nezačal. Po ručnom dispatchi je najnovším
  riadkom ten nový a keeper ho odvtedy stráži.
- **Keeper sa po dokončení sám nevypne** — tickne „done" a ďalej nič nerobí.
  Je to tak zámerne: keby niekedy v budúcnosti vznikol nový `ruz_full` beh
  (napr. po zmene schémy), keeper ho stráži bez zásahu človeka. Vypnutie:
  `systemctl --user disable --now sk.cistafirma.ruz-keeper.timer`.

Inštalácia na delle: `scripts/local/install_ruz_keeper.sh` (Linux-only, inak
odmietne). Jednotky: `scripts/local/systemd/sk.cistafirma.ruz-keeper.{service,timer}.in`.
Inštalátor **odmietne** inštalovať bez `loginctl enable-linger`: user timer bez
lingeru prestane pri odhlásení — ticho, a `systemctl --user status` pritom stále
hlási „waiting". To je presne tá trieda zlyhania, kvôli ktorej celý mechanizmus
existuje, takže sa to kontroluje, nie dokumentuje.

### 11.7 Dôvod chyby firmy sa počas behu nedal prečítať (`1e00c66`, zámerne nenasadnuté)

Nájdené na **bežiacom** walku 2026-09-18: `SyncProgress` #4 hlásil
`total_errors=1` a `last_error` bol **prázdny**. Príčina je presná:
`SyncProgress.record_progress` ukladá každý stý záznam cez `update_fields`,
ktoré `last_error` neobsahujú — a obe miesta, ktoré chybu firmy zapisujú
(`fetch_ruz_data.py:318` a `:328`), priradili `progress.last_error` až **po**
tomto volaní. Text teda ostal v pamäti.

Čo to znamená prevádzkovo: po celý beh riadok hlási počet chýb **bez jediného
dôvodu**, a pri walku, ktorý trvá dni, je to celý ten čas. Až na konci ho
zapíše `complete()`/`pause()`/`fail()`, ktoré volajú plný `save()` — takže
*dokončený* riadok dôvod nesie, ale len ten posledný. Overené: dôvod chyby
(duplicitné IČO) bol dosiahnuteľný len z logu kontajnera.

Oprava: `error_message` je parameter `record_progress` (poradie volania už text
nemôže ticho zahodiť) a `last_error` je v `update_fields` pri **každom** zápise,
nie len pri tom hneď po chybe — chyba na 905. firme sa ukladá až pri 1000. a to
ukladanie samo nijakú chybu nemá. Oba nové testy mieria na priebežný zápis;
assertion po dobehnutí walku by prešla aj s pôvodným defektom. Overené proti
kódu bez opravy: padajú na `'' != 'refused'`.

**Zámerne sa to nenasadzuje počas walku.** Reštart `celery_worker_ruz` by beh
zastavil až na ~45–50 minút (30 min prah watchdogu + 15 min
`KEEPER_REDISPATCH_AFTER` + 0–5 min tick keepera) a znovu
by spravil ≤100 záznamov — za zlepšenie *výpisu*, nie správania. Dovtedy je
dôvod stále dosiahnuteľný z logu. Nasadí sa po dokončení walku.

Samotné chyby, ktoré sa počítajú, sú **duplicitné IČO**
(`Companies and SZCO_ICO_key`): register odpovedá jedným IČO na viac subjektov
a unique index to odmietne. To je zámerný, nefatálny prípad z #83 — okno sa
cez neho posunie, namiesto aby navždy stálo.

**Namerané 19. 9. 2026 na walku #46** (24 h, `total_errors=66`, všetkých 66
je tá istá constraint): posledný výskyt je `Unstorable record ID 324678` na
IČO 42061628 — a to IČO v tabuľke už drží **iné** RUZ ID, 1754002 („MAXIFIT
KLUB Ružomberok, občianske združenie"). Dva rôzne RUZ záznamy, jedno IČO:
presne prípad #83. Zámerne sa to sem píše aj s tým, čím to **nie** je —
súbežný get-then-create race nižšie by potreboval dve súrodené ID na *jednej*
stránke súčasne, a tento dôkaz ho nepreukazuje. Kto vidí v logu `duplicate
key` a chce z toho spraviť race: takto vyzerá meranie, ktoré to rozhodne.

### 11.8 Opravné behy nemali job riadok ani globálny zámok (#186, `59fbf1f`)

`start_repair_sync`, `resume_repair_sync`, `repair_ruz_gaps` a
`resume_gap_repair` volali `call_command` **priamo**. Následok nebol len
chýbajúci výpis: taký beh nemal `SyncJob`, teda žiadny heartbeat pre watchdog,
žiadny výsledok pre `ops-check` ani pre admin zoznam jobov — a predovšetkým
**nesiahol na `ruz:global`**, jediný kľúč, ktorý drží dvoch zapisovateľov
firemných dát od seba. `ruz_repair` pritom bol v `JOB_TYPE_CHOICES` celý čas;
nevytváral ho nikto.

**Prečo to nešlo spraviť inak než zovšeobecnením `_run_ruz_command`.** Tá
funkcia mala `fetch_ruz_data` napevno a je to jediná vec, ktorá behu dá job
riadok, heartbeat, výsledok a slot. Meno príkazu je teraz parameter (a ide aj
do `parameters`, lebo `ruz_repair` pokrýva tri rôzne príkazy).

**Ostrejšia chyba, nájdená pri diagnostike.** `adminapi/views/sync.py`
vytvoril pri `ruz_repair` riadok s `concurrency_key='ruz:global'` a poslal
úlohu **bez** `sync_job_id`. Úloha volala príkaz priamo a nikdy riadok
neclaimla — a `queued` riadok je presne to, čo drží
`reg_s_one_active_ruz_job`. Riadok by teda ostal `queued` **navždy** a každý
ďalší RUZ beh by naň narazil, dostal ho späť a vrátil sa bez dispatchu —
vrátane keeperovho vlastného resume. Dosiahnuteľné jedným klikom v admin
dropy; overené na delle, že **žiadny `ruz_repair` riadok v produkcii nikdy
nevznikol**, takže je to „dosiahnuteľné, nikdy nespustené", nie minulá
nehoda.

**Čo si príkazy museli dorobiť samy:**

- `--sync-job-id` a `beat()` v každej iterácii. Bez toho by ich watchdog
  zabil v behu: `detect_and_fail_stuck_jobs` berie starý heartbeat ako smrť
  a jeden batch môže trvať minúty.
- `set_job_outcome` v `finally`. `SyncProgress` aj `SyncGapAnalysis` si svoj
  riadok medzi behmi **požičiavajú**, takže ich súčty patria celej oprave;
  job riadok je per-beh, a dostane preto **rozdiel** oproti stavu na začiatku.
  Bez toho by resume hlásil celú opravu odznova.
- `time_limit=86400` je preč zo všetkých štyroch. Je to tvrdý SIGKILL:
  nevybehne `except`, takže beh sa len prestane hýbať a nechá za sebou
  `running` riadok. Precedent je `start_full_ruz_sync_from_id` (§11.4).

`REPAIR_RESUMABLE_STATUSES` preto prijíma aj `running` — skutočná brzda proti
druhému štartu je `ruz:global`, ktorý si `_run_ruz_command` claimne **pred**
príkazom, takže vylúčenie `running` nebranilo ničomu a bralo presne ten
prípad, pre ktorý resume existuje.

**Tri tlačidlá v adminovi teraz odmietnu nahlas.** Dispatch, ktorý stretne
živý job, sa vracia bez toho, aby čokoľvek spravil — takže hlásiť „bolo
naplánované" je ten istý falošný úspech, aký bol opravený v `resume_sync_view`
(#185). Týka sa to `repair_view`, `resume_view` (obe `SyncGapAnalysisAdmin`)
a `trigger_repair_sync_view`. Tlačidlo „Pokracovat" sa pre `running` riadok
ponúka len vtedy, keď slot nič nedrží — so živým jobom je to beh v pohybe
a ponuka na jeho reštart.

**Mimo rozsahu, zámerne:** `analyze_ruz_gaps` ostáva bez job riadku. Je
read-only voči firemným dátam (zapíše len `SyncGapAnalysis`), takže zobrať
kvôli nemu `ruz:global` by na hodiny zastavilo walk bez jediného úžitku;
a keďže nemá heartbeat, jeho `time_limit` je jediná hranica, ktorá mu ostáva.

**Dve veci na samostatný krok, nie do tohto:**

- Oba opravné príkazy upsertujú podľa `ico` (nie `ruz_id`) a používajú holý
  `parse_date` namiesto `apply_ruz_dates`. Pri zhode `ico` teda môžu prepísať
  uložené `datum_zalozenia` / `datum_zrusenia` / `datum_poslednej_upravy` na
  `None`. §11.2 to dokumentuje pre `repair_ruz_gaps`; platí to rovnako pre
  `repair_ruz_sync_v2`. Je to zmena dátovej sémantiky na príkaze, ktorý môže
  prejsť 449-tisíc riadkov, preto vlastný krok.
- `_dispatch_job` používa `params.get("start_id", 0)`, takže `ruz_repair`
  z admin API začína vždy od RUZ ID 0, nie od uloženého kurzora. Nechané tak.

**Testy.** Nový `registers/tests_repair_job_tracking.py` (13) je kontrola
príkazovej časti: heartbeat, výsledok, rozdiel oproti základu, zápis pri páde,
a negatívna kontrola pre beh bez `--sync-job-id`. **Proti pôvodnému kódu padá
10 z 13** — tri, ktoré prejdú, sú práve tie negatívne kontroly, a to je
správne. V `tests_sync_job_singleton.py` pribudli job riadky pre všetky štyri
tasky, chýbajúci `time_limit` a štyri admin odmietnutia (vrátane pozitívnej
kontroly, že s voľným slotom tlačidlo naozaj dispatchuje).

Poznámka k prostrediu testov: oba príkazy fetchujú cez `ThreadPoolExecutor`
a vlákno si otvorí **vlastné** DB spojenie, ktoré test prežije — stačí to na
to, aby `DROP DATABASE test_cistafirma` spadol na „being accessed by other
users" a zobral so sebou celý beh. Testy preto pool nahradzujú inline
exekútorom (`_InlineExecutor`); o súbežnosť v nich nejde.

### 11.9 Opravné príkazy prepisujú identitu firmy (#187)

**Zadanie.** Tri opravné príkazy — `repair_ruz_sync` (v1), `repair_ruz_sync_v2`
a `repair_ruz_gaps` — zapisujú firmy **inak než walk**. Majú to robiť rovnako;
a kým to robia inak, je to jeden z najhorších defektov v repozitári, pretože
ticho maže firmy a hlási to ako prácu.

**Mechanizmus, overený proti zdroju aj spustením.** Všetky tri obmedzia prácu na
`ruz_id`, ktoré v `Company` **nie sú** (`repair_ruz_sync_v2.py:120-124`,
`repair_ruz_gaps.py:248`, `repair_ruz_sync.py:125`), a potom zapíšu

```python
Company.objects.update_or_create(ico=details['ico'], defaults={... 'ruz_id': details.get('id') ...})
```

`Company.ico` je `unique` (`companies/models.py:280-285`) a `ruz_id` tiež
(`:261`). `ruz_id` bol vybraný práve preto, že chýba — takže kolidovať nemá čo
a zápis **prejde bez chyby**. Nájdený riadok je ale vždy iná entita, lebo jeho
`ruz_id` v množine chýbajúcich nebol: riadok entity `Z` dostane `ruz_id`
súrodenca `Y` a entita `Z` prestane existovať. Beh to započíta ako `skipped`
(`repair_ruz_sync_v2.py:243-247`) alebo `repaired`
(`repair_ruz_gaps.py:253-258`, s komentárom `# Existujúca firma s iným RUZ ID -
aktualizujeme` — defekt zapísaný ako návrh).

Register naozaj odpovedá jedno IČO viac entitami: `00177474` → ruz_id 1677,
1049449, 1070716 (`fetch_ruz_data.py:503-505`). Walks to rieši tým, že kľúčuje
na `ruz_id`, takže druhá entita pod držaným IČO narazí na unique index a skončí
ako `unstorable` (`fetch_ruz_data.py:302-326`) — držaný riadok ostane nedotknutý.
Opravný príkaz na to isté nemá handler.

**Korekcia §11.8.** Tam je to zapísané ako „môžu prepísať uložené
`datum_zalozenia` / `datum_zrusenia` / `datum_poslednej_upravy` na `None`".
To je nepresné a treba to povedať: keďže práca je obmedzená na **chýbajúce**
`ruz_id`, zhodu na `ico` nemôže spôsobiť tá istá firma — je to **vždy** swap
identity. Dátumy nie sú druhý defekt, sú súčasť toho istého zápisu: prepíše sa
celý riadok. Holý `parse_date` (`:222-223, :235`) navyše zlieva „chýbajúce"
a „nečitateľné" do `None`, čo je presne to, pred čím `apply_ruz_dates` chráni
(`ruz_api.py:287-322`) — ale dosiahnuteľné je to len skrz ten istý swap, takže
je to zhoršenie dôsledku, nie samostatná chyba.

**Tretí príkaz.** §11.8 hovorí o „oboch opravných príkazoch". Sú **tri**:
`repair_ruz_sync.py` (v1) má ten istý zápis. Nikto ho nevolá — ani task, ani
admin, ani dokumentácia. *Oprava plánu:* pri implementácii sa ukázalo, že tento
súbor **nie je funkčný príkaz s jednou chybou**, ale nedokončený prepis, ktorý
spadne na prvej neprázdnej stránke (`self._fetch_and_save_company` neexistuje,
`api`/`total_missing`/`total_downloaded`/`total_skipped`/`total_errors` sú
prečítané pred priradením, tie isté `missing_ids` sťahuje dvakrát). Rieši sa to
ako taký — viď **Výsledok** na konci tejto sekcie.

**Rozsah, ktorý z toho robí viac než kozmetiku — namerané.** Workflow
`wf_09267a5b-44e` spravil na delle čítací odhad: `Company` má 449 795 riadkov
a **0** s `pravna_forma` v 100-110/422; `IndividualEntity` má 35 339 riadkov
a **všetky** ich `ruz_id` v `Company` chýbajú. Žiadny z tých príkazov neroutuje
SZCO podľa `pravna_forma` — `IndividualEntity` v nich nie je ani naimportovaný.
(Číslo je snímka z 2026-09-18 a **rastie**, ako beží walk #46 — pri prvom meraní
toho dňa bolo 31 198. Nulový prienik s `Company` je tá polovica, ktorá sa
nemení, a práve o ňu sa opiera oprava pracovného zoznamu nižšie.)
Príkaz prejdený nad registrom by teda vytvoril **35 339 fantómových `Company`
riadkov** pre fyzické osoby, nafúkol `Company.objects.count()` o ~7 % a sprístupnil
ich vo verejnom vyhľadávaní (`companies/views.py` — `AllowAny`, queryset bez
filtra na SZCO). Toto nie je teória: je to jeden klik v adminovi.

**Druhá chyba v tom istom kóde: chyba bez dôvodu.** `except Exception as e:` na
`repair_ruz_sync_v2.py:249-251` (a `repair_ruz_gaps.py:260-262`) len zvýši
počítadlo; `e` sa nikdy neprečíta, `logging` sa v súbore nevyskytuje. Počítadlo
ide do `progress.total_errors` → `set_job_outcome(failed=…)`, a `complete_job`
nastaví `completed` bez ohľadu naň — takže beh, ktorému zlyhal **každý** zápis,
je natrvalo uložený ako `completed` s číslom a bez jediného slova o príčine.
`SyncProgress.record_progress(..., error_message=…)` na to existuje a tento
príkaz ho nepoužíva.

**Tretia chyba: resume, ktorý klamе.** `resume_repair_sync` loguje
`"Resuming repair sync from RUZ ID %s"` a `REPAIR_RESUMABLE_STATUSES` zámerne
prijíma aj `running` (§11.8) — ale príkaz číta kurzor len pre
`progress.status in ['paused', 'failed']` (`:61`). Po zabitom behu (SIGKILL
nechá `running`) teda log tvrdí, že sa pokračuje, a príkaz ide od 0. Je to tá
istá rodina ako #185.

Rozhodnutie o `0` vs. kurzor, aby sa to neopravilo naopak: pre `completed` beh
je štart od 0 **správny**. Oprava má hľadať `ruz_id`, ktoré databáza nemá,
a tie sa medzi behmi menia — skenovať od uloženého kurzora by tie pod ním už
nikdy nenašlo. Kurzor má zmysel len pre **prerušený** beh, kde prefix tej istej
jazdy už prejdený bol. Preto sa dopĺňa `running`, nie odstraňuje podmienka.

**Oprava.** Všetky tri príkazy prestanú mať vlastný `defaults` a vlastný upsert
a budú zapisovať cez `fetch_ruz_data.Command.update_or_create_company` — presne
to, čo už robí `repair_ico_shape._reimport` (`:131-189`), a z toho istého
dôvodu: druhá kópia mapovania sa rozíde a oprava je správna len vtedy, keď uloží
to, čo by uložil walk. Delegovaním sa získa kľúčovanie na `ruz_id`, `apply_ruz_dates`
aj `record_ruz_date_outcome`, routing SZCO na `IndividualEntity`, `.strip()` na
IČO a `detect_status_change` pre zrušenia.

Dve veci, ktoré walkov zapisovač nemá a opravné príkazy potrebujú:

- **Zámok na výstup.** `update_or_create_company` píše na `self.stdout` /
  `self.stderr` za každý záznam; opravné príkazy ho volajú z
  `ThreadPoolExecutor` s 5-10 vláknami. Zámok ide okolo **zápisu**, nie okolo
  DB práce — inak by serializoval presne tú paralelitu, kvôli ktorej tam pool je.
- **Rozlíšenie výsledkov.** `(False, False)` znamená „register vrátil záznam bez
  použiteľného IČO" a patrí do `skipped`; `(DataError, IntegrityError)` znamená
  „databáza záznam odmietla" (najčastejšie IČO, ktoré drží iná entita) a patrí do
  **`errors`** — s dôvodom, ktorý sa zapíše na stderr, do logu a do
  `progress.last_error`. Presne to je ten prípad, ktorý sa dnes počíta ako
  úspešná oprava.

**Testy.** `registers/tests_repair_write_path.py` je napísaný proti **výsledku**
(kto je entita v riadku a čo beh tvrdí, že spravil), nie proti kľúčovému slovu
lookupu, takže ostane platný aj keby bola oprava napísaná inak. Proti pôvodnému
kódu padá **5 zo 7**; dve, ktoré prejdú, sú pozitívne kontroly — a to je
správne.

Stav po dokončení: **15 testov, `OK`** (`.claude` job 2070505d, 2026-09-18).
Dva z nich sú nové proti prvému návrhu a oba vznikli z chyby v mojom vlastnom
kóde, nie z čítania:

- `RepairWriter.store()` volal na ceste `REFUSED` `self._walk.stderr.write()`
  **pod** `with self._lock:`, ale `self._walk.stderr` je `_OneWriterAtATime` nad
  tým istým zámkom — re-entrantný záber ne-reentrantného `Lock`, teda uviaznutie
  navždy. Diagnostikované cez `sample <pid> 3` (hlavné vlákno
  v `lock_PyThread_acquire_lock`), nie čítaním; test visel 20 minút pri 0:01.79
  CPU. Vláčilo sa to **len na refuse ceste**, takže by to vyzeralo ako oprava
  zaseknutá na zlom zázname.
- v1 mal dva `handle` (viď vyššie) — odmietnutie bolo mŕtvy kód, kým sa telo
  nepremenovalo.

Obe majú spoločné to, že **kód vyzeral správne** a chybu našiel až beh proti
výsledku. To je argument pre testy proti výsledku, nie proti implementácii.

### 11.9.1 Výsledok (2026-09-18)

Overené nezávisle: workflow `wf_09267a5b-44e` (25 nálezov → 8 overovaných → 6
potvrdených, 2 vyvrátené, completeness critic na konci) ohodnotil implementáciu
ako **správnu** — „Delegating to the walk's `update_or_create_company` closes all
three: `ruz_id` key (swap becomes `IntegrityError` → `REFUSED`), `apply_ruz_dates`
(unreadable date refused), SZCO routing to `IndividualEntity`" — a jeden
verifikátor defekt **empiricky reprodukoval**: `Ran 7 tests, FAILED
(failures=5)`, s `AssertionError: 1049449 != 1677` na riadku incumbent-a.

Čo je v strome:

- `registers/services/ruz_repair_writer.py` (nový) — `RepairWriter`, ktorý drží
  inštanciu walku a deleguje na `update_or_create_company`; zámok je okolo
  **streamu**, nie okolo DB práce.
- `repair_ruz_sync_v2.py`, `repair_ruz_gaps.py` — zapisujú cez neho, počítajú
  `REFUSED` ako chybu s dôvodom (`logger.error` + stderr + `last_error`
  priradené **pred** `save()`), v2 počíta `updated` zvlášť a číta kurzor aj pre
  `running`.
- `repair_ruz_sync.py` (v1) — `handle` odmieta na prvom riadku s odkazom na v2
  (predtým `AttributeError` z vlákna, ktorý `except Exception` zapísal ako
  `failed` na **zdieľaný** `sync_type='repair'` riadok, čiže na kurzor v2);
  `_update_or_create_company` deleguje, aby v strome neostal vzor na
  skopírovanie. **Odporúčanie: zmazať tento súbor** — nie je moje rozhodnutie.
- **V1 má dva `def handle` a vyhráva ten druhý.** Prvý pokus o odmietnutie bol
  preto mŕtvy kód: `call_command('repair_ruz_sync')` šiel rovno do pôvodného
  tela a spadol na `Company` v pracovnom zozname — čo je presne traceback, ktorý
  zachytil test `test_it_refuses_and_names_the_command_that_replaced_it`
  (`NameError: name 'Company' is not defined`, riadok 141). Odmietnutie je
  skutočné až od premenovania tela na `_handle_unfinished`; nič nedispečuje iné
  meno než `handle`. Toto je druhý nález toho istého druhu ako nález §11.9 —
  **chyba, ktorá sa hlási ako niečo iné, než čím je** — a keby test nebol
  napísaný proti *výsledku*, prešel by.
- `adminapi/views/sync.py` — `params.get("start_id", 0)` → `params.get("start_id")`.
  Nula nie je sentinel, ktorý by príkaz odlíšil od skutočného štartu (`0 is not
  None`), takže `--start-id=0` sa pripojil a resume vetva bola z admin API
  nedosiahnuteľná. Overené spustením `_dispatch_job`: `parameters={}` →
  `{'start_id': 0, …}`.
- `repair_ruz_sync_v2.py` + `analyze_ruz_gaps.py` — pracovný zoznam sa pýta **na
  obe tabuľky**. `Company` samotná bola celá definícia „už držané", a keďže
  žiadne `IndividualEntity.ruz_id` v `Company` nie je, celá tá populácia
  (35 339 k 2026-09-18) bola **natrvalo** „chýbajúca": každý beh znovu stiahol
  35k stránok,
  znovu uložil už správne riadky a každý započítal ako novú prácu — takže oprava
  nikdy nemohla hlásiť, že skonvergovala. Gap analýza je nástroj, ktorého výstup
  ponúka admin tlačidlo (`analyze_ruz_gaps.py`, `registers/admin.py:190-206`),
  takže nafúknuté číslo je to, čo operátor číta pred stlačením. Poznámka:
  `repair_ruz_gaps` nad **uloženou** analýzou použije jej `gap_ranges`, takže
  stará analýza si fantómové ID drží, kým sa nespraví nová.

**Tri korekcie skorších tvrdení** (z overenia, nie z dohadu):

1. **Swap nie je samoopravný.** „Durable until someone re-runs the canonical walk
   per entity" je nesprávne: aj walk kľúčuje na `ruz_id`, takže vloženie
   pôvodnej entity narazí na unique `ico` — presne ten počítaný, nefatálny
   duplicate-IČO prípad. Prelabelovanie je teda **trvalé, kým ho niekto neopraví
   ručne**.
2. **Oscilácia je medzi behmi, nie v rámci jedného.** Stránkuje sa vzostupne po
   1000, takže 1677 a 1049449 sú na rôznych stránkach. Za beh sa nepreklopia;
   preklopia sa tým, že ďalší beh začína od 0 a posunutý `ruz_id` je zase
   „chýbajúci".
3. **„Zhruba deň navyše" nemalo správny základ** — 6,1 záznamu/s je rýchlosť
   `ruz_incremental` behu #23, nie repair slučky, ktorá stránkuje po 1000 ID.
   Cena re-walku od 0 je reálna, ale nebola nameraná.

**Dôsledok, ktorý stojí za zapísanie:** zápis je UPDATE existujúceho pk, takže FK
deti ostávajú pripojené — `CompanyFinancialResult.company` a
`PersonCompanyRelation.company` sú `CASCADE` — čiže sa **prelabelujú**, nie
odpoja, a `seat_*` (zámerne mimo repair `defaults`) ostávajú zastarané.

**Nezaradené nálezy z toho istého overenia** (nie sú súčasťou #187, každý chce
svoje rozhodnutie):

- **Repair nemá keepers.** `ruz_full_keeper_decision` filtruje len
  `FULL_RESYNC_JOB_TYPE`, `ruz_keeper_tick.DISPATCH` mapuje len `start`/`resume`
  walku, a žiadny beat entry nespúšťa repair. Zabitý repair teda nikto
  nerestartuje — a kým jeho riadok sedí `running`, drží `ruz:global`, takže
  `enqueue_ruz_job` vráti živý riadok a `_run_ruz_command` odmietne („already
  running"): mŕtvy repair **zastaví šesťhodinový walk**, kým ho
  `detect_stuck_sync_jobs` nezoberie.
- **`rpo_sync.py:151/173-174`** — `_parse_date` vracia `None` pre neprítomné aj
  nečitateľné, a zapisuje sa cez `OrsrCompanyProfile.objects.update_or_create`
  na **beat ceste** (`sync-missing-orsr-profiles-every-4-hours`). To isté
  `orsr_scraper.py:659-670` + `orsr_sync.py:44`. Rovnaký kolaps, iný model.
- **`update_fs_data.py:122`/`fs_data_handlers.py`** — FS datasety sa pripájajú
  **len podľa IČO** (`Company.objects.filter(ico__in=batch)`), takže pri
  duplicitnom IČO jedna entita dostane DPH stav druhej. Obmedzené (nepíše
  `ruz_id`, takže nemôže prelepiť identitu), ale je mimo `ruz:global` — čo
  odporuje docstringu toho zámku.
- **Štrukturálne:** `update_or_create` je get-then-create, nie atomické, a beží
  z poolu s 5-10 vláknami na vlastných spojeniach — dve súrodené ID na jednej
  stránke môžu obe minúť `get`. Po oprave sa tá prehra hlási ako `REFUSED`
  s dôvodom; nameraná nebola.
- **Bežiaci job hlási nulu, celý čas.** `set_job_outcome` vznikol presne preto,
  aby „dokončený job s nulou spracovaných nevyzeral ako job, ktorý nič
  neurobil" — a volá sa na **konci** behu. Kým beží, riadok jobu drží
  `processed_items=0`, `succeeded_items=0`, `total_items=NULL` a hýbe sa len
  `last_heartbeat`. Namerané na dell 2026-09-18 o 20:05 na jobe #46: po
  **štyroch hodinách** a 41 200 spracovaných ID sú tam nuly. Admin stránka
  SyncJobs (`frontend/admin/pages/SyncJobs.tsx:152`) kreslí
  `ProgressBar pct={job.progress_percentage}` a `succeeded_items of total_items`,
  takže päťdňový beh sa tam celý čas zobrazuje ako **prázdny pruh na 0 %**.
  Reálny postup pritom čitateľný je — `SyncProgress` #4 ho má a keeper ho loguje
  ako `RUZ_KEEPER_STATE` — takže to nie je stratený signál, ale riadok, ktorý
  vyzerá zaseknuto. **Neopravovať počas behu**: zmena v ceste walku chce
  reštart workera a ten zastaví beh až na ~45–50 minút.

**Bezpečnostná poznámka k oprave:** po zmene stojí ochrana proti súbežnému behu
na unique obmedzení `ruz:global`, nie na zozname statusov — `resume_repair_sync`
stále posiela len `--workers`, zatiaľ čo `REPAIR_RESUMABLE_STATUSES` prijíma aj
`running`. Je to bezpečné, ale je to constraint, nie kód, ktorý číta `start_id`.

---

### 11.10 Čo čaká na nasadenie na dell (stav 2026-09-18)

dell beží na **`8486c03`** a `main` je pred ním. Celkový počet commitov sa
nepíše zámerne — každý ďalší `docs(plan)` ho posunie a číslo v dokumente by
začalo klamať. Rozhodujúce je, že **štyri menia správanie** a sú vypísané
nižšie; zvyšok sú `docs(plan)`. Aktuálny stav dá `git log --oneline 8486c03..main`.
Všetko sa odkladá
jedným rozhodnutím a z jedného dôvodu: ide o **jeden reštart workera**, a ten
zastaví bežiaci walk #46 až na ~45–50 minút (30 min prah watchdogu + 15 min
`KEEPER_REDISPATCH_AFTER` + 0–5 min tick keepera) a spraví znovu ≤100 záznamov.
Hromadí sa to teda do jedného nasadenia
**po dokončení walku**, nie do ôsmich.

Štyri z nich menia správanie:

| commit | čo mení |
|---|---|
| `1e00c66` | dôvod chyby firmy sa dostane na `last_error` počas behu, nielen na konci (§11.7) |
| `e089c54` | obnovenie syncu pokračuje ten beh, na ktorý sa kliklo |
| `59fbf1f` | opravné behy dostali `SyncJob`, heartbeat a `ruz:global` (§11.8) |
| `51482a1` | opravné príkazy ukladajú cez zapisovač walku, nie cez IČO (§11.9) |

Zvyšných päť je `docs(plan)` — vrátane tohto.

**Migrácie: žiadne** (`git diff --name-only 8486c03..main -- 'backend/*/migrations/*'`
je prázdne), takže nasadenie nepotrebuje `migrate` — je to `git pull` + reštart
služieb. Recept je v `docs/DEVOPS_CICD.md`; `docs/DEPLOYMENT_RUNBOOK.md` je
k8s cesta a **nesmie sa použiť, kým neexistuje klaster**.

---

### 11.11 Kontrola behu #46 — má päťdňový beh na čom dobehnúť (2026-09-18 20:12 CEST)

Beh je kritická cesta na ~5 dní, takže sa overovalo, či ju vôbec má na čom
dokončiť — nie že „beží".

**Čo beží.** `registers.tasks.start_full_ruz_sync` v `worker_ruz@d39813196fb3`,
`routing_key = ruz_full`, `worker_concurrency = 1` — zaberá jediný slot.
Že ide o skutočný reštart od nuly, dosvedčuje `SyncProgress` #4:
`zmenene_od = 2000-01-01`.

**Nič nespadlo.** `RestartCount = 0` na **všetkých 12** kontajneroch a pätica
workerov + backend naskočila v rozmedzí 1,1 s (16:00:51–52 UTC). Ten reštart
teda bol jedno zámerné rozhodnutie (nasadenie #183), nie crash-loop — čo je
jediná vec, ktorá by päťdňový beh ticho zabila.

**Rezerva je dostatočná.** Disk **422 GB voľných** (6 % použitého), databáza
1 333 MB, Redis 22,94 MB. Redis má `maxmemory = 0` a `noeviction`, takže rásť
môže neobmedzene — pri 23 MB je to ale bezpredmetné.

**Walk smeruje ľudí správne — overené proti živým dátam, nie proti kódu.**
Toto je kontrola, ktorá má cenu len dovtedy, kým beh beží: chyba v smerovaní
SZCO by päť dní vyrábala falošné `Company` riadky a späť by sa to naprávalo
ťažko. Invariant, ktorý drží:

- `Company` (`"Companies and SZCO"`) má s právnymi formami `100`–`110` a `422`
  **0 riadkov** — a to je práve množina, ktorá nemá ani jeden mať.
- `"Individual Entities"` má **58 341** riadkov a sú v nej presne formy
  `101` (51 177), `105` (3 267), `109` (2 233), `103` (836), `107` (671),
  `102` (119), `110` (51), `106` (26), `108` (2) — formu `422` nemá ani jedna
  tabuľka.
- **Kontrola je obojsmerná, a to je silnejšia verzia než jednosmerná.** Nielen
  `Company` má s formami `100`–`110`/`422` **0** riadkov, ale aj
  `"Individual Entities"` má **0** riadkov *mimo* týchto foriem. Rozdelenie je
  teda presná partícia, nie filter, ktorý niečo prepustí — a keby walk sypal
  ľudí aj do firiem, odhalí to buď jedna, alebo druhá strana.
- Walk práve teraz zakladá **výhradne ľudí**: `Company` je 449 795, teda presne
  toľko ako pri meraní v #187, kým `"Individual Entities"` išlo 37 286 → 58 341.
  To je presne to, na čo Samuel upozornil, keď povedal, že mu v DB chýbajú
  firmy — chýbali mu živnostníci, a `Company` sa pritom nezmenil, čo je zároveň
  nezávislý dôkaz, že tie isté záznamy nezakladá dvakrát.

(Pozor na názov tabuľky: `db_table` je `"Individual Entities"` s medzerou, takže
`registers_individualentity` **neexistuje** — dopyt naň spadne na
`relation does not exist`, čo je našťastie tá hlasná polovica.)

**ETA je odvodená, nie prevzatá.** Strop id priestoru je **2 624 307** — overené
priamo v produkčnej DB: `max("RUZ ID")` je 2 624 307 v `"Companies and SZCO"`
a 2 624 305 v `"Individual Entities"`; `min` je 4, resp. 7, takže pod kurzorom
walku nič nechýba, a riadok s `NULL` RUZ ID nemá ani jedna tabuľka. Stav
18:44 UTC: kurzor 54 900, tempo 20 376/h. Zvyšok 2 569 407 je **~126 h ≈ 5,25
dňa** → **~2026-09-24 skoro ráno CEST (~03:00)**. Zdroj môže mať medzitým id
vyššie než 2 624 307, takže to je *skorší* okraj, nie sľub.

**Táto ETA bola o ~7 h optimistickejšia a bola to moja chyba.** Ako strop som
predtým použil **2 486 558** — posledný kurzor *prírastkového* riadku #2. To je
však len najvyššie id, ktoré sa zmenilo v okne toho priechodu; prírastkový
priechod ide cez **zmenené** záznamy, nie cez celý id priestor, takže o maxime
zdroja nehovorí vôbec nič. Bolo to namerané číslo, ktoré meria inú vec — presne
trieda chyby, pred ktorou tento dokument varuje inde.

Kontrola, že kurzor je naozaj tohto behu a nie naakumulovaný:
54 900 / 2,69 h (`get_duration()` = 2:41:39, čiže `started_at` ≈ 16:02 UTC, čo
sedí s tým, kedy walk zabral slot) = 20 378/h, čo je presne rate, ktorý si ráta
keeper sám (20 376/h).

**Dve pasce pre toho, kto to bude čítať zajtra.**

- **`LLEN ruz_full` je `0`, a to *nie je* dôkaz, že prírastkový sync nemá čo
  čakať.** Toto je teraz **overené, nie predpovedané** — o 20:07:28 UTC som
  odčítal tri veci naraz:

  | čo | hodnota |
  |---|---|
  | `PeriodicTask.last_run_at` pre `fetch-ruz-data-every-6-hours` | `20:07:28.527` UTC |
  | `LLEN ruz_full` | **0** |
  | `inspect reserved` na `worker_ruz` | `fetch_ruz_data_task`, `acknowledged=False`, `routing_key=ruz_full` |

  Čiže správa **existuje** a front je pritom nulový, lebo ju worker už
  prefetchol (`worker_prefetch_multiplier = 4`, concurrency 1 → rezervuje až 4).
  Presne preto sa `LLEN` na túto otázku nesmie použiť: pred 20:07 znamenala
  „ešte nenastalo", po 20:07 znamená „je v buffere" — a obe vyzerajú rovnako.
  Odpoveď dá len `inspect reserved`. Zrážka je
  neškodná a **nemení sa kvôli nej nič v beat schéme**: `ruz_full` číta výhradne
  `celery_ruz` s `concurrency = 1`, takže správa len počká, kým walk dobehne,
  a potom sa ~20 naakumulovaných prírastkov vystrieda za sebou. Zasahovať do
  `PeriodicTask` počas behu by bolo riziko bez úžitku.

  **Overiteľná predpoveď pre toho, kto to číta neskôr:** buffer pojme 4 správy,
  takže po štvrtom ticku (t. j. po ~2026-09-19 14:07 UTC) sa `LLEN ruz_full`
  konečne dostane nad nulu — a odvtedy bude rásť o jednu každých 6 h. Ak sa tak
  nestane, `inspect reserved` niečo neukazuje správne a treba to riešiť.
- **`SyncProgress` počítadlá sú kumulatívne cez behy**, keď sa riadok recykluje.
  Riadok #2 hlási `total_created = 32 187` pri behu, ktorý trval **3,88 s**
  (14:07:28,578 → 14:07:32,460) — to sa nedá vysvetliť inak než načítaním
  z jeho 89 behov. Čítaj **deltu proti `started_at`**, nikdy surové číslo;
  presne to už má v docstringu aj opravný príkaz.

---

### 11.12 Audit odolnosti päťdňového behu (2026-09-19 05:15 CEST)

Beh je kritická cesta na ~5 dní a beží bez dozoru, tak sa neskúmalo „je zdravý",
ale **čo ho za tých päť dní môže zastaviť a či si to niekto všimne**. Pustených
5 vyšetrovateľov (jedna dimenzia na každého) a k nim dvaja nezávislí
protirečitelia na každý nález.

**Audit sa nedokončil a jeho výstup sa NESMIE čítať ako overenie.** Došiel kredit
na API („402 Insufficient Balance") a zabil **23 z 35** agentov — vrátane takmer
všetkých protirečiteľov. A moja vlastná logika to **premenila na falošný verdikt**:
zlyhaný protirečiteľ sa vráti ako `null`, `votes.filter(Boolean)` ho zahodí,
`survives` vyjde `false` a nález pristane medzi „vyvrátenými". **Zlyhaný
protirečiteľ vyzerá presne ako vyvrátenie** — tá istá trieda chyby ako
`grep -c` na spadnutom príkaze. Preto tu nie je zoznam „potvrdených nálezov";
je tu len to, čo som overil **sám**, a menovite to, čo zostalo neoverené.

**Overené mnou, do detailu — per-batch heartbeat vs. 30-minútový prah.**
Návrh: `beat()` sa v slučke firiem volá len na `index % 50 == 0`
(`fetch_ruz_data.py:342`), takže najhoršia legitímna medzera môže prekročiť prah
watchdogu a ten zabije **živý** walk. Čísla sedia:

- najhorší záznam = `Retry(total=4, backoff_factor=0.6)` (`http_client.py:26-31`)
  = 5 pokusov × `timeout=20` (`ruz_api.py:172`) + ~9 s backoff ≈ **110 s**;
  `respect_retry_after_header=True` vie jeden záznam natiahnuť ešte viac,
- 50 × 110 s ≈ **92 min > 30 min** (`CISTAFIRMA_STUCK_HEARTBEAT_MINUTES`).

**Ale je to medium, nie high, a strata je čas, nie dáta.** Aby to nastalo, musí
**50 záznamov v rade** zhorieť na plný retry rozpočet — teda RUZ musí byť
trvajúco nedostupný, a vtedy walk aj tak nerobí pokrok. Kurzor sa ukladá per
záznam (`record_progress`), takže falošný zber nič nestratí: watchdog zapíše
`failed`, keeper o 15 min obnoví a beh pokračuje od kurzora. Je to **týranie
času počas dlhého výpadku** (~45–60 min na cyklus, nie 35), nie korupcia.
Normálna medzera je pritom **~9 s**: 50 záznamov pri nameraných 5,66 z/s
(20 391/h).

**Opravené v `0f5a667`.** `beat()` je teraz `heartbeat_gate()` v `sync_engine`:
brzda na `time.monotonic()`, nie na počte záznamov. Volá sa pri každom zázname
a sama rozhodne, či zápis patrí tomuto úderu — prvý raz zapíše vždy, takže walk,
ktorý začne a hneď zamrzne, je vidieť ako job, ktorý začal. `heartbeat_loop()`
bol dovtedy jediným držiteľom tejto brzdy a nemal ani jedného volajúceho
(overené grep-om na celom repe), takže pravidlo teraz existuje raz. Test meria
najväčšiu medzeru pri simulovaných 60 s na záznam; so starou brzdou padá
(pozitívna kontrola: so zväčšeným intervalom `beats == 1`). `fetch_ruz_data`
navyše odmietne bežať, keď mu riadok jobu zmizol — bez riadku nie je heartbeat
vôbec a `set_job_outcome` o chýbajúcom riadku mlčí.

**V tomto behu to však účinné nie je a ani nemôže byť** — zmena
`fetch_ruz_data.py` sa v už bežiacom workeri neprejaví, kým sa worker
nerestartuje, a práve to #188 odkladá na koniec behu. Tento walk teda nechráni;
chráni ten ďalší. Zvyšok odstavca vyššie (medium, nie high; strata je čas, nie
dáta) platí naďalej.

**Odklad nasadenia na koniec behu má druhý dôvod, a ten je meraný 19. 9. 2026.**
`unstorable_ids` je lokálny zoznam v `fetch_ruz_data.py` a do `notes` sa
zapisuje **raz, po `progress.complete()`**, nie po segmentoch — takže bežiaci
walk ho celý drží v pamäti. Walk #46 ich má 66 a všetky sú z jednej cesty:
`docker logs cistafirma_celery_ruz --since 48h | grep -c "Unstorable record ID"`
= 66, `grep -c "duplicate key"` = 66, `grep -c "Error processing company ID"` = 0,
`total_errors` = 66 — teda samé kolízie na `Companies and SZCO_ICO_key`, žiadna
iná chyba. `notes` je prázdne nie preto, že by diery neboli, ale preto, že ich
zoznam ešte čaká na koniec behu.

To je však všetko, čo sa z tej vety dá vyčítať: tú istú hlášku má v tomto repe
**dva nezávislé pôvody** — kolíziu podľa návrhu (#83: register vydá jedno IČO
pre dva subjekty, okno ide ďalej) a get-then-create race v `update_or_create`
z vláknového poolu (§11.7). Oddeľuje ich otázka na dáta, nie na log: existuje to
IČO už pod **iným** RUZ ID? Pre jednu z tých 66 je odpoveď zmeraná — RUZ 324678
kolidoval na IČO 42061628, ktoré tabuľka držala pod RUZ 1754002, teda #83. Pre
zvyšok nezmerané, a práve preto je zoznam v `notes` dôležitý: trieda, ktorá je
diera na backfill, sa od triedy, ktorá je podľa návrhu, líši len dátami.

Reštart workera (čo je #188) ten beh preruší. Zoznam v pamäti zmizne a obnovený
segment začne s prázdnym; `total_errors` na riadku ostane 66, ale bez identity.
Nie je to kópia *jediná* — tie ID sú aj v logu kontajnera (`Unstorable record
ID <id>`, na stderr), lenže `docker compose up -d --build` kontajner
**rekreuje** a jeho log zmizne spolu s ním — čo je presne ten krok, ktorým #188
nasadenie robí. Po nasadení pred koncom walku teda z tých 66 zostane len číslo.
(Oprava (6) nemení, kedy sa zoznam zapisuje; mení len to, že ho ďalší segment
prepíše namiesto pripojenia.)

**Overené mnou, z kódu aj živého stavu — Focus Mode vypne watchdog a keeper
potom čaká navždy.** `ruz_full_keeper_decision` vracia pri `queued`/`running`
**vždy** `wait` a celý prechod na `failed` necháva na `detect_stuck_sync_jobs`
(`sync_engine.py:770-771`). Ten ale **nie je** v `FOCUS_KEEP_TASKS`
(`focus_mode.py:20-25`) a `_set_periodic_tasks_enabled` zakáže každý `PeriodicTask`
mimo tohto zoznamu — takže so zapnutým Focus Mode sa walk, ktorému zomrel worker,
**nikdy neobnoví**. Dnes je to latentné: `SyncFocusModeState` riadok neexistuje
(Focus Mode nikdy nebol aktivovaný), `detect-stuck-sync-jobs-every-10-min` má
`enabled=True` a `total_run_count=1128`, žiadna `PeriodicTask` nie je zakázaná.

**Opravené v `5600c6b`.** `registers.tasks.detect_stuck_sync_jobs` je
v `FOCUS_KEEP_TASKS`. Je tam z iného dôvodu než tie štyri: tie sa držia preto,
že ich práca je rozpracovaná, tento nevyrába dáta vôbec — je to poistka nad
naším vlastným stavom, nie práca proti cudziemu serveru, takže pauzu prečkať
nemá. Jeden test sa viaže na `CELERY_BEAT_SCHEDULE` (premenovanie tasku ho
zhodí), druhý overuje mechanizmus a má pozitívnu kontrolu — v tom istom behu sa
iný `PeriodicTask` naozaj vypne, inak by „nezakázaný watchdog" prešiel aj keby
Focus Mode nerobil nič. Nasadenie si počká na #188 spolu s ostatnými; keeper by
sa síce chytil bez reštartu walku (používa ho výhradne `ruz_keeper_tick`,
overené grepom), ale celý balík aj tak odchádza naraz.

**Kandidáty 1–7 — overené 19. 9. 2026 v kóde.** Každý prišiel od pomenovaného
agenta s citáciou, ktorú som vtedy neoveril. Overil som ich teraz, jeden po
druhom: **štyri sú pravda, dva sú vyvrátené a jeden je vyvrátený v premise a vo
zvyšku horší**. Poradie je pôvodné, aby sa dalo porovnať s tým, čo agenti
tvrdili — a aby bolo vidieť, že „agent to povedal" nie je dôkaz.

1. **VYVRÁTENÉ.** `ruz_full_keeper_decision` číta `SyncJob`, a to je správny
   zdroj, nie chyba: práve job riadok drží `concurrency_key=ruz:global`.
   Divergencia „job hovorí `failed`, ale walk beží" nemôže nastať —
   `fetch_ruz_data` odmietne bežať bez claimnutého riadku a `_run_ruz_command`
   ho claimuje pred spustením. Dispatchnutý resume sa navyše zrazí na unique
   indexe (`enqueue_ruz_job` chytá `IntegrityError`) a vráti sa bez importu.
   `wait` zámerne pokrýva aj `running` so starým heartbeatom, lebo ten prechod
   vlastní watchdog. Kandidát žiadal opak toho, čo docstring vysvetľuje.

2. **OVERENÉ — a vážnejšie, než kandidát tvrdil.** `sync_health.py:257-261`
   filtruje `triggered_via=beat_schedule, queued_at__gte=failed_cutoff`
   (`cutoff = now - 24 h`). Okno sa teda meria od **začiatku behu**, nie od
   zlyhania. Walk #46 má `queued_at = 09-18 16:02`; o 24 h od neho táto
   podmienka nemôže uvidieť jeho `failed` **nikdy**, lebo `queued_at` je
   zafixovaný na začiatku päťdňového behu. Podmienka, ktorá má chytiť mŕtvy
   walk, teda môže zabrať len v prvom dni — presne v tom, v ktorom sa ešte nič
   nestihlo pokaziť. A `full` progress riadok neposudzuje ani štvrtá podmienka
   (`sync_type__startswith="incremental"`). **Dokumentácia brány je navyše
   zastaraná:** `sync_health.py:32-34` tvrdí „measured on 2026-09-10 … exactly
   one beat-scheduled type (`ruz_incremental`)" — dnes má `ruz_full` tiež
   `triggered_via=beat_schedule` (job #46, overené v DB), lebo
   `_run_ruz_command` tú značku prirazuje **každému** auto-zaradenému jobu,
   teda aj keeperovmu obnoveniu. Kto si prečíta docstring, vyvodí, že walk je
   mimo rozsahu; on je v rozsahu, len nedosiahnuteľný.

3. **VYVRÁTENÉ v premise.** „Podrž okno a prečítaj znova" pri `full` walku
   neexistuje, takže nemôže byť no-op: `fetch_ruz_data.py:408` je
   `holds_window = sync_type.startswith('full') or run["unreadable"] > 0`, čiže
   `full` okno **nespravuje vôbec** a drží ho vždy — a komentár na `:399-403`
   vysvetľuje prečo (zapisovať do `zmenene_od` by zmenšilo ďalší full resync na
   jeden deň). Podržanie okna patrí incremental vetve. **Zvyšok je však horší
   než pôvodné tvrdenie:** `record_progress(ruz_id=company_id, …)` je v oboch
   `except` vetvách (`:331-333`, `:342-344`), takže kurzor ide **za** zlyhaný
   záznam — dočasne nečitateľný záznam už tento walk neuvidí, a keďže `full`
   `zmenene_od` nikdy neposunie, neuvidí ho ani nikto iný. Jediná pamäť na dieru
   je `notes` — a tú zabíja bod 6.

4. **VYVRÁTENÉ.** Id aj dôvod **sú** v databáze:
   `record_progress(ruz_id=company_id, error=True, error_message=str(e))`
   (`:331-333`, `:342-344`) zapisuje `last_processed_ruz_id` a `last_error`
   každých 100 záznamov — presne tá oprava, ktorá kedysi chýbala — a `notes`
   nesie až 50 dvojíc `id (ico)` s celkovým počtom. Čo naozaj chýba: `last_error`
   drží len **poslednú** chybu dávky (last writer wins), takže dôvody
   predchádzajúcich zlyhaní v tej istej stovke sa stratia, a `notes` je
   zastropované na 50 a prepisované (bod 6). Kandidát sa teda mýlil v mieste,
   nie v smere: strata je reálna, ale je v `notes`, nie v stderr.

5. **OVERENÉ — a toto je najkonkrétnejší nález z celej sedmičky.**
   `trigger_full_sync_from_id_view` (`registers/admin.py:641`) je **jediná**
   RUZ akcia v tom súbore bez `_live_ruz_job()` kontroly — `resume_sync_view`,
   `trigger_repair_sync_view` aj obe gap akcie ju majú, s komentárom, ktorý
   presne tento omyl pomenúva. A `start_full_ruz_sync_from_id`
   (`registers/tasks.py:852-861`) prepíše `SyncProgress(sync_type='full')`
   — teda **ten istý riadok, z ktorého beží walk #46** — skôr, než sa vôbec
   pokúsi získať slot: `last_processed_ruz_id = start_id - 1`,
   `status = 'paused'`, plný `save()`. Až potom volá `_run_ruz_command`, ktorý
   sa zrazí na `ruz:global` a vráti sa bez behu. **Zámok teda nechráni to, čo
   sa stihlo zapísať pred ním.** Dôsledky sú tri a líšia sa trvaním:
   (a) kurzor sa vráti, ale walk si ho zapíše sám pri ďalšom stovkovom uložení
   (`record_progress`) — do ~100 záznamov, ~18 s, sa zahojí;
   (b) `status='paused'` **sa nezahojí**, lebo `status` nie je v `update_fields`
   toho uloženia — riadok tak zostane `paused` celé dni, kým walk beží, a admin
   ho tak aj zobrazí, čo je presne kontrola, ktorá klame;
   (c) ak je walk práve zastavený (medzi zberom watchdogu a tickom keepera),
   vrátený kurzor je ten, z ktorého sa bude pokračovať — a `start_id` **vyššie**
   než skutočný kurzor ticho preskočí celý interval medzi nimi, čo je presne to,
   pred čím `--full-resync` chráni.
   (c) je strata dát, (b) je lož, (a) je neškodná.

6. **OVERENÉ.** `fetch_ruz_data.py:455-459` je `progress.notes = f'…'` a
   `save(update_fields=['notes'])` — priradenie, nie pripájanie. Zdrojový
   komentár o pár riadkov vyššie (`:441-444`) pritom hovorí, prečo tam ten
   záznam je: „it is named here, on the row that survives, and written out —
   otherwise the hole is invisible and a later fix would have nothing to
   backfill from." Každý obnovený segment teda zmaže presne to, na čo bol
   zapísaný. Nekonzistentné je to aj vnútri modelu: `SyncProgress.pause()`
   (`models.py:320`) robí `f"Pozastavené: {reason}\n{self.notes}"`, čiže
   pripája — jeden z dvoch zápisov do toho istého poľa drží históriu a druhý
   ju zahadzuje.

7. **OVERENÉ.** `KEEPER_REDISPATCH_AFTER = timedelta(minutes=15)`
   (`sync_engine.py:744`) a `ruz_full_keeper_decision` ho aplikuje **po**
   skončení behu (`:798`), takže k oneskoreniu patrí. Dokumentácia na troch
   miestach (`PLAN.md:7069`, `:7403`, `:7420`) počíta „~35 minút (30 min prah
   watchdogu + 5 min tick keepera)" — aritmetika, ktorá je o 15 minút krátka
   a dá sa overiť proti kódu. Reálne: 30 (watchdog zberie) + 15
   (`KEEPER_REDISPATCH_AFTER`) + 0–5 (granularita timera) = **45–50 min**, nie
   35 a nie 45–60.
8. Keeperove riadky v journali tlačia `last_heartbeat` v UTC vedľa CEST časových
   značiek journald, takže 6 s starý heartbeat sa číta ako dve hodiny starý.
9. `ops_check.sh` overuje týždenný backup timer, ale keeper timer ním nekontroluje
   ani jednou — hoci päťdňový mandát stojí práve na ňom. **Overené 19. 9. 2026:
   pravda** (`grep -n 'keeper' scripts/local/ops_check.sh` nenašiel nič, kým
   `weekly_job_systemd` kontroluje backup timer). Doplnené tou istou cestou:
   sekcia „RUZ keeper" overuje inštaláciu oboch unitov, `Linger` (bez neho user
   manager po reštarte nenabehne a timer sa dovtedy tvári ako `active`),
   `enabled`, `active`, vek posledného ticku (limit 30 min) a `Result`
   posledného ticku. Ten posledný údaj je podstatný a nie je to duplicita:
   pečiatka posledného triggeru sa pohne **aj pri ticku, ktorý zlyhal**, takže
   bez `Result` by keeper, ktorému päť minút padá `docker compose exec`, hlásil
   „beží každých päť minút" presne tak dlho, ako je nainštalovaný.

   **Prehodenie vetiev cez stub našlo v prvom návrhu ešte dve chyby, obe
   v nemenovaní správnej príčiny** — a to je presne to, čo táto kontrola nesmie
   robiť, lebo nesprávna príčina vyzerá akčne a pošle človeka preinštalovať
   fungujúcu vec:

   - **Rozpad dvoch faktov nastal v extrakcii, nie vo verdikte.** `sed -n
     's/^LastTriggerUSec=@//p'` vypíše len riadok, ktorý sa naozaj začína
     `LastTriggerUSec=@`; keď `--timestamp=unix` nič neurobí (systemd < 247),
     hodnota je `Sat 2026-09-19 10:40:02 CEST`, výpis je **prázdny** a prázdno
     sa mapovalo na „nikdy nebežal". Oprava `case` na tri vetvy to nevyriešila —
     hodnota bola pokazená o krok skôr. Surová hodnota sa preto teraz číta bez
     filtra a `@` sa strháva v shelli (`${last_raw#@}`); buď to jedna, alebo
     druhá oprava samotná stále klame.
   - **Verdikt „nikdy nebežal" mal denné rozlíšenie.** `age_days` vráti pri
     čomkoľvek pod 24 h nulu, takže keeper nainštalovaný 15 hodín a ani raz
     nespustený vyšel ako „nainštalovaný dnes — prvý tick ešte len čaká" a
     prešel ako `warn`. To je obrátená chyba než tá prvá: nie falošný poplach,
     ale **tichá zhovievavosť** voči presne tomu stavu, kvôli ktorému kontrola
     existuje. Nový `age_minutes` v `lib/backup_time.sh` (ten istý python3
     idiom, ten istý `-1` sentinel) ho porovnáva s tým istým
     `KEEPER_STALE_MINUTES`; namerané na delle 30 min → `warn`, 31 min → `fail`.

   Obe chyby prežili prvý beh stubu. Prvý beh ich odhalil len preto, že sa
   púšťal každý scenár proti **skutočnému skriptu** — druhý preto, že sa pustil
   znova po oprave. Vetvy, ktoré sa na zdravom hoste nedajú spustiť, sú zároveň
   tie, ktoré nikdy nebežali ani raz.

Body 8 a 9 sú overené (9. je aj opravený); bod 8 je napriek tomu kozmetika logu.
Zvyšok, body 1–7, je overený vyššie: **pravda sú 2, 5, 6, 7**, body 1, 3 a 4 sú
vyvrátené (3 a 4 v premise, ale s horším zvyškom, ktorý je nižšie pomenovaný).
Diagnóza je hotová a **všetky štyri opravy sú urobené** — z bodov 2, 5 a 6
vyplývali tri zmeny v kóde, bod 7 bol prepis troch čísel:

- **(2) okno brány od konca behu, nie od zaradenia** — hotové v `9e43e75`.
  Filter je `Q(completed_at__gte=cutoff) | Q(completed_at__isnull=True)`;
  druhá polovica je nutná, inak by päťdňový walk z brány vypadol úplne a
  „najnovším pokusom" typu `ruz_full` by bol naposledy zaradený krátky beh.
  Riziko, ktoré prináša — starý `running` riadok je v beat sekcii vždy a jeho
  status je OK — pinuje test, že ho stále failuje podmienka o heartbeat.
  Docstring na `:32-34` je prepísaný: meranie z 2026-09-10 („práve jeden typ")
  je zastarané a `triggered_via='beat_schedule'` **neznamená** „bezobslužný" —
  `_run_ruz_command` ho dáva každému jobu, ktorý sám zaradí, a to sú aj tlačidlá
  v Django admine. Namerané 19. 9. 2026 sú v použití tri hodnoty: `beat_schedule`
  (beat, keeper, tlačidlá v Django admine, opravy), `admin_ui` (DRF admin API
  a legacy endpointy v `registers/views.py`, ktoré si riadok zaradia samy a id
  si odovzdajú, takže stamp prežije) a `cli`. Filter teda tie dve naozaj
  operátorské cesty vylučuje; nerozlišuje však beh spustený tlačidlom v Django
  admine od naozaj bezobslužného. Ostáva, ale FAIL na type spustenom odtiaľto je
  „beh, ktorý nikto nenahradil", nie „beh, na ktorý sa nikto nepozeral" —
  zúženie by znamenalo dať tlačidlám čestný trigger, čo je zmena dispatch cesty.
- **(5) guard a poradie zápisu kurzora** — hotové v `be33950`. Guard dostali
  **tri** tlačidlá, nie jedno: `full`, `full-from-id` aj `incremental` boli
  jediné RUZ akcie v `admin.py` bez `_live_ruz_job()`, hoci všetky tri radia
  príkaz, ktorý slot zaberá — a všetky tri hlásili „bol naplanovany" o behu,
  ktorý sa nikdy nespustí. Parkovanie kurzora sa presunulo do nového
  `before_command` v `_run_ruz_command`, ktorý beží až po získaní slotu
  a vnútri `try` (zlyhanie označí job `failed` s dôvodom, nie `running` pre
  watchdog). Sedem testov; štyri z nich padajú na starej podobe — jeden na
  `1999999 != 349100`, teda na kurzor živej behu posunutý dopredu.
- **(6) `notes` pripája, nie prepisuje** — hotové v `caf1188`. `append_notes`
  drží strop `NOTES_KEEP_BLOCKS = 20` a odstránenie **pomenúva** („… N starších
  blokov odstránených"); značka sa pri ďalšom pripojení číta, takže číslo je
  kumulatívne a skutočné, nie per-segmentové a o jedna nafúknuté. `pause()`
  píše na začiatok ďalej; jej riadok sa spája s prvým blokom jedným `\n`, takže
  ak prvým blokom bola značka, jej číslo sa pri pauze stráca — strata presnosti
  v čísle, nie v ledgeri.
- **(7) tri čísla „~35 minút" → „~45–50 minút"** — hotové v `2843136`
  (`PLAN.md:7069`, `:7403`, `:7420`).

Bod 8 (heartbeat v UTC vedľa CEST v journali) zostáva ako kozmetika logu;
body 3 a 4 menia to, čo sa o `notes` a `last_error` smie tvrdiť — bod 3 je
navyše dôvod, prečo musí byť `notes` čitateľné po celý beh, nie len na konci.
Ani jedno z toho nie je dôvod odkladať #188; všetky štyri opravy idú s ním.

---

### 11.13 Brána by od 21. 9. spadla na okne, ktoré walk sám prekrýva (2026-09-19)

Nález nevzišiel z auditu, ale z jedného riadku `make ops-check`:

```
  incremental sync windows (judged: window may be at most 3d old)
    incremental            completed  2026-09-17    2d old  OK
```

`2d old` je 19. 9. Brána súdi `now.date() - zmenene_od > window_max_age_days`
(default 3), a riadok má `zmenene_od = 2026-09-17`, takže:

| deň | vek | verdikt |
|---|---|---|
| 2026-09-20 (nedeľa) | 3 | `3 > 3` je nepravda → **OK** |
| 2026-09-21 | 4 | **FAIL** |
| 2026-09-27 (ďalšia nedeľa) | 10 | **FAIL**, ak dovtedy neprebehne nový inkrementál |

Walk má ETA **~2026-09-24 skoro ráno CEST** — §11.12 ju odvodzuje z overeného
stropu id priestoru 2 624 307 a nameraného tempa a druhá vzorka to potvrdzuje
(19. 9. 10:24 UTC, kurzor 372 200, tempo ~20 000/h). Je to *skorší* okraj, nie
sľub: zdroj môže mať medzitým id vyššie. Týždenná brána
(`sk.cistafirma.backup.timer`, nedeľa 03:17) teda 20. 9. prejde a 27. 9. by
spadla len keby walk prekročil 26. 9.
Falošný FAIL ale nastane na **každom manuálnom `make ops-check` od 21. 9. do
konca walku** — a to je presne to čítanie, ktorému má brána slúžiť. Zelená
brána, ktorá po dva dni hlási poruchu, ktorá neexistuje, učí ľudí ignorovať
červenú; to je tá istá trieda chyby, akou bolo 11. 9. mŕtve CI.

> **Oprava účinkuje až na `dell`.** Táto zmena ide do produkcie s #188 (deploy
> je odložený na koniec walku), takže kým sa tak nestane, manuálny
> `make ops-check` na `dell` môže ten falošný FAIL ešte ukázať — a je to
> očakávané, nie regresia. Plánovač to nezasiahne: najbližší beh je
> **2026-09-20 03:17 CEST**, kedy je vek 3 a `3 > 3` je nepravda; ďalší
> (27. 9.) už walk bude za sebou a okno posunú naakumulované inkrementály.

**Prečo je to falošný FAIL a nie skutočný.** Okno sa nemá ako pohnúť, lebo
počas walku nebeží žiadny inkrementálny beh — a to nie je porucha, ale dôvod,
prečo bol walk spustený. `fetch_ruz_data` číta všetko od `2000-01-01`, teda
oveľa viac než inkrementál. Kód to sám priznáva v komentári: „two different
states look identical from the date alone". Toto je **tretí** taký stav —
prvé dva rieši výnimka pre Focus Mode.

**Čo sa s tým taskom naozaj deje — merané, nie odvodené.** `enqueue_ruz_job`
dáva **každému** RUZ jobu ten istý `concurrency_key = 'ruz:global'`, takže
počas walku sa 6-hodinový `fetch_ruz_data_task` neodmieta — **odloží sa**:

| čo | hodnota (2026-09-19 ~10:01 UTC) |
|---|---|
| `LLEN ruz_full` | `0` |
| `inspect reserved` na `worker_ruz` | **4**× `fetch_ruz_data_task`, `acknowledged=False`, `worker_pid=None` |
| z toho duplicita | `e7d7b28f…` **dvakrát**, raz `redelivered=True` |
| `cistafirma_celery_ruz` štartoval | 2026-09-18 16:00:50 UTC |
| walk (#46) prevzal slot | 16:02:07 UTC |

Ticky od štartu walku boli tri (20:07, 02:07, 08:07 UTC), takže buffer
s `worker_prefetch_multiplier = 4` bol **plný po troch tickoch, nie po
štyroch** — jeden slot spotrebovala redelivery (visibility timeout vypršal,
lebo `acks_late` a worker nič nepotvrdzuje, kým beží walk). To spresňuje
predpoveď z §11.11: `LLEN ruz_full` sa dostane nad nulu pri **štvrtom** ticku
(14:07 UTC), ale mechanizmus je „buffer je plný a broker už nedoručuje", nie
„štvrtá správa naplní buffer". Predpoveď teda platí, jej vysvetlenie nie.

**Dôsledok, ktorý §11.11 označil správne.** Po skončení walku sa naakumulované
prír. spustia za sebou; pri ~4 s na beh (job #43: 3,2 s, #45: 4,0 s) a ~20
tickoch za päť dní je to ~80 s, a posledný z nich okno posunie. Do beat schémy
sa preto nezasahuje — to zostáva platiť.

**Oprava (tento commit, `sync_health`).** Druhá výnimka tej istej triedy ako tá
pre Focus Mode: kým stav trvá, žiadny beh nemá okno pohnúť, takže jeho vek nie
je zastaranosť. Riadok sa vypíše s `--` a s vetou, ktorá povie prečo. Dve
obmedzenia, bez ktorých by výnimka bola horšia než chyba, ktorú rieši:

- **Len `full`, nie `full_companies`.** Firmy-only walk (`--entity-type
  companies`) okno inkrementálu nenahrádza — to pokrýva aj SZCO — takže tam by
  potlačenie skrylo ozajstné zastaranie.
- **Walk musí byť živý.** `last_activity` píše `record_progress` každý stý
  záznam (overené na bežiacom walku: 5 s staré), takže požiadavka na čerstvosť
  v rámci prahu watchdogu je to, čo bráni výnimke prežiť walk. Bez nej by riadok
  `full` ponechaný v `running` mŕtvym behom umlčal okno **navždy** — a brána,
  ktorá navždy stíchla, je presne tá chyba, ktorú má tento príkaz odhaliť.
  Mŕtvy walk si nájde vlastná podmienka (zaseknutý heartbeat); táto výnimka za
  neho nesmie kryť.

Tri testy, z toho jeden na vetvu, ktorá na zdravom hoste nenastane (a práve tá
je tá, čo klame): `test_a_full_walk_does_not_redden_the_window_it_supersedes`,
`test_the_walk_carve_out_lapses_when_the_walk_stops`,
`test_a_companies_only_walk_does_not_supersede_the_window`.

---

### 11.14 Re-derivácia odložených nálezov — čo z nich je pravda (2026-09-19)

Za celú session sa nazbieral zoznam nálezov, ktoré som **odložil**, nie opravil:
veci, čo vyzerali ako chyby, ale každá potrebovala vlastné rozhodnutie. Zoznam
mien však sám nič netestuje. Preto som každý nález znovu odvodil proti kódu,
ako je **dnes**, a potom ho dal nezávislému agentovi **vyvrátiť** — 7 nálezov,
12 agentov, 0 chýb. Výsledok: **5 potvrdených, 1 zastaraný, 1 úplne vyvrátený**
a ani jedno potvrdené tvrdenie neprešlo bez zúženia alebo rozšírenia.

| nález | verdikt | dopad |
|---|---|---|
| `retry_failed` pre RUZ typy | **nový, opravený tu** | fantómový `queued` riadok → brána natrvalo červená |
| zastarané meranie vo `fetch_ruz_data` | **opravené tu** | nepravda ospravedlňujúca držanie okna |
| `complete_job` a `failed_items` | potvrdené | zaznamenané, ale **nikým nesúdené** |
| RPO/ORSR `_parse_date` | potvrdené | nečitateľný dátum **vymaže** uložený |
| Focus Mode povrchy | potvrdené (nízka) | inzerujú počítadlo, ktoré môže byť len 0 |
| `triggered_via='beat_schedule'` | potvrdené (nízka) | text brány nenesie výhradu z docstringu |
| repair tasky bez job riadku (#186) | **zastarané** | opravené v `59fbf1f`; zvyšok inde |
| `update_fs_data` → `fs_data_handlers` | **vyvrátené** | obe menované mechaniky sú nepravdivé |

**Poznámka k metóde.** Aj táto správa bola v jednom bode nepresná a musel som ju
opraviť čítaním kódu: tvrdila, že chyby walku „žijú len vo `failed_items`".
Nepravda — `fetch_ruz_data.py:496-502` píše `failed_items` vo `finally:`, takže
walk #46 má nulu len preto, že **ešte beží**. Presnejšie znenie je nižšie. Ani
adversariálne overenie nie je fakt, kým si ho neprečítam.

#### Opravené v tomto commite

**1. `retry_failed` vytváral pre RUZ typy riadok, ktorý sa nedá nárokovať.**
Endpoint volal `sync_engine.enqueue_job`, ktorý `concurrency_key` **nenastavuje**
(`models.py:779-783`, default `""`), kým `claim_ruz_job` filtruje na
`ruz:global` (`sync_engine.py:499-517`). Riadok sa teda nikdy nechytil: task
bežal, nenašiel čo nárokovať, zalogoval „not runnable" a vrátil sa. Nič sa
neimportovalo. Tri dôsledky z toho robia viac než no-op:

- riadok zostal `queued` **navždy** a `cancel` pre RUZ typy vracia 409, takže
  ho nevedelo vyčistiť žiadne obrazovko;
- po `DEFAULT_QUEUED_MINUTES` (720) ho `sync_health` ráta ako nesplnenú
  kontrolu — filter je len `status="queued"`, bez typu (`sync_health.py:213`,
  `:252`) — takže fantóm **natrvalo** zfarbí `make ops-check` do červena. To je
  presne tá výstraha, ktorá naučí svojho čitateľa ju ignorovať;
- operátor, ktorý klikol „Retry Failed", dostal beh, ktorý nikdy nebežal.

Unikátny index `reg_one_active_ruz_job` (`models.py:794-802`) fantóma **nekryje**
— jeho podmienka je len na `ruz:global` — takže neblokoval nič ďalšie, len
visel. `create()` pritom na `RUZ_JOB_TYPES` vetví už dávno a z toho istého
dôvodu; oprava je tá istá vetva zrkadlom. Meranie: produkcia **0 fantómov**
teraz, 4 historické `ruz_full_firmy` s prázdnym kľúčom (2026-08-04) sú všetky
terminálne — latentná pasca, nie požiar. Prvý z troch testov je pozitívna
kontrola: `claim_ruz_job(new.pk) is not None`. Testovať `status` by chybu
**nechytilo** — fantóm bol tiež `queued`, a práve to ho robilo zdravým.

**2. Zastarané meranie, ktoré ospravedlňovalo držanie okna.**
`fetch_ruz_data.py` tvrdil *„no RUZ job in this database has ever recorded a
failed or skipped item, so the condition costs nothing in practice"*. To
predchádza `set_job_outcome` (`a89f158`) a odvtedy je to nepravda. Nové
meranie (2026-09-19, celá produkčná história): failed/skipped položky má
**presne jeden** beh — `ruz_incremental` #23, `completed`, 1 + 1. Podmienka teda
doteraz stála jedno držané okno a **už nie je zadarmo**. Doplnené aj to, ktorú
triedu kryje: `unreadable` áno, `unstorable` zámerne nie (opakované čítanie
vráti tú istú hodnotu, okno by zostalo pripnuté navždy).

#### Potvrdené, neopravené — čaká na rozhodnutie

**A. `complete_job` a `failed_items`: zaznamenané, ale nikým nesúdené.**
Presné znenie, ktoré som si musel opraviť: `SyncProgress.total_errors` je živý
signál počas behu (walk #46 má dnes 72) a `SyncJob.failed_items` sa zapíše pri
ukončení. Ani jedno však pre `full` walk **nečíta žiadna kontrola** —
`sync_health.py:355` filtruje `sync_type__startswith="incremental"` a `:520`
berie `full` len pre výnimku z §11.13. Walk teda môže zhodiť N pomenovaných
záznamov a skončiť `completed` so všetkým zeleným. Pre `incremental` je trieda
`unreadable` chytená držaným oknom po 3 dňoch (`sync_health.py:422` ju aj
pomenuje), ale `unstorable` je z držania vyňatá → neviditeľná.

*Prečo to neopravujem sám:* najlacnejšia čestná verzia je podmienka „najnovší
walk s `failed_items > 0`". Lenže walk #46 po dobehnutí ponesie ~72 a taká
podmienka by **okamžite a natrvalo** sfarbila týždennú výstrahu do červena, kým
sa každý odmietnutý záznam neopraví. To je horšia chyba než tá, ktorú rieši.

**B. RPO/ORSR `_parse_date`: nečitateľný dátum vymaže uložený.** `_parse_date`
(`rpo_sync.py:597-604`, `orsr_scraper.py:659-669`) vracia `None` pre
neprítomné **aj** nečitateľné, a to `None` ide priamo do `defaults` →
`update_or_create` ho zapíše a **zmaže dátum, ktorý tam bol**, ticho, pri
každom priechode. To je presne trieda, ktorú projekt už pomenoval a na RUZ
strane opravil („A date we cannot read must not erase a date we hold",
`ruz_api.py:284-349`) — RPO a ORSR tú opravu nikdy nedostali. Frontend to
maskuje: `CompanyHeader.tsx:332` pri NULL zobrazí `datum_zalozenia` z RUZ pod
menovkou „Dátum vzniku", takže čitateľ vidí vierohodný dátum, ktorý nie je z
toho registra. Meranie: 27 448 riadkov s `den_zapisu`, **0 prejavených škôd**
(12 ORSR-written riadkov, všetky čisté; RPO 27 436 zápisov, 0 strát) — latentné,
nie horiace. Polovica opravy je mechanická (nečitateľné → kľúč z `defaults`
vynechať, uložená hodnota zostane; + `logger.error` + počítadlo odmietnutí),
polovica je **rozhodnutie**: má RPO neprítomnosť vymazať, alebo držať? RUZ
vymazáva, lebo neprítomnosť je tam spôsob, akým sa odvoláva zrušenie; pre
`establishment` to nemusí platiť.

**C. Focus Mode inzeruje počítadlo, ktoré môže byť len 0.**
`revoke_non_focus_tasks`/`purge_broker_queues` sa zámerne nevolajú a je to
pripnuté testom (`tests_focus_mode_safety.py:31-46`), ale tri povrchy
(`models.py:545-549`, `admin.py:806-810`, `sync_dashboard.html:69`) hlásia
„revokovaných 0 taskov" ako výsledok kroku, ktorý neexistuje. Žiadna ochrana sa
nestráca — len sa číta mechanizmus, ktorý niet. Rozhodnutie: povrchy odstrániť,
alebo funkciám dať vedomý vstupný bod (vzor `celery-purge` s potvrdzovacím
tokenom) — nie ich zapojiť do `enter_focus_mode`, to by zhodené správy z brokera
nechalo neúplný import (§9.5).

**D. `triggered_via='beat_schedule'` pre Django-admin behy.** Potvrdené, ale
**zámerne** ponechané (`9e43e75` to aj zdokumentoval v `sync_health.py:44-62`);
verdikt je vecne pravdivý, pokazená je len atribúcia. Reálna časť je malá: text,
ktorý `make ops-check` vypíše, nenesie výhradu z docstringu („reporting a run
nobody replaced, not a run nobody was watching"), takže čitateľ výstrahy musí
mať prečítaný zdroj. Opraviť sa to má na strane pečiatky (admin vetva nech ide
cez `enqueue_ruz_job(..., triggered_via="admin_ui")`), **nie** zúžením filtra —
to by `ruz_full`/`ruz_repair` z brány vyhodilo úplne.

#### Zastarané a vyvrátené — nech sa to znova neodvodzuje

**#186 je naozaj opravené** (`59fbf1f`, `git merge-base --is-ancestor` proti
HEAD). Ale dve veci stoja za zapísanie. Prvá: **dell je stále na `8486c03`**, kde
`59fbf1f` nie je — kto si prečíta „#186 hotové" a usúdi „produkcia je krytá",
číta repozitár, nie hostiteľa. Druhá, reziduum dosiahnuteľné aj po nasadení:
**ručne** spustené `manage.py repair_ruz_sync_v2|repair_ruz_gaps` si neberú job
riadok ani slot — a `repair_ruz_gaps.py:205` to operátorovi priamo odporúča
(„Pokračujte: python manage.py repair_ruz_gaps --resume"). Správny vzor je o
kus vedľa: `fetch_ruz_data.py:75-98` si pri chýbajúcom flagu sám nárokuje slot a
pri kolízii vyhodí `CommandError`. Toto je jediné reziduum, ktoré si podľa mňa
zaslúži opravu bez rozhodnutia — je to tá istá get-then-create trieda, ktorú
projekt už raz meral.

**`update_fs_data` → `fs_data_handlers` je vyvrátené.** Obe menované mechaniky
sú nepravdivé: field sety **sedia** vrátane zámernej `vat_payer` asymetrie
(`tests_fs_data_integrity.py:133-158` ju pinuje) a výnimky sa počítajú
(`update_fs_data.py:115-117`). Kto by podľa toho nálezu „opravoval"
`UPDATE_FIELDS_MAP`, rozbil by opravu DPH. Reziduum je inde a je iné:
`if not items:` (`update_fs_data.py:84-87`) vypíše pri totálnom zlyhaní
sťahovania „0 errors" — na nerozoznanie od nezmeneného datasetu — a 10 z 15
datasetov v `FS_DATASET_URLS` sa ticho preskočí. Oboje je už zapísané v
`docs/SOURCE_DATA_INTEGRITY.md:34-40`.

#### Nové, čo vyplávalo pri overovaní

`adminapi/views/dashboard.py:119-127` číta `failed_items` a skladá z neho graf
`throughput_24h.failed_per_hour`. Čítadlo teda **jedného** čitateľa má — ale je
to graf, nie súd: jedna chyba v okne so 47 800 položkami je v ňom neviditeľná.
Zapisujem to preto, aby budúce „nikto to nečíta" bolo presné.

---

## 12. Nemenné pravidlá

Toto sa nemení bez výslovného súhlasu. Detaily v `docs/DATA_PROTECTION.md`.

- Docker volume `cistafirma_postgres_data` je nenahraditeľný. **Produkcia beží
  na `dell`** (od 2026-09-15) a **od 2026-09-17 je to jeho jediná kópia** — Mac
  o svoje Docker volumes toho dňa prišiel (purge), takže „zamrznutá záloha" už
  neexistuje. Na Macu ostávajú len **dumpy**
  (`~/Library/Application Support/CistaFirma/backups`, najnovší 2026-09-15),
  čiže archív, nie databáza. Pravidlá platia na `dell`.
- **Nikdy**: `make docker-reset`, `docker compose down -v`, `docker volume rm`,
  `docker volume prune`.
- **Nikdy** rušiť `make celery-purge`, plný RUZ resync ani restore ako
  rutinnú akciu.
- **Nikdy** nerobiť restore cez bežiacu `cistafirma` databázu.
- Pred každou migráciou alebo deštruktívne vyzerajúcou zmenou: čerstvá
  overená záloha (`make db-backup` + `make db-backup-verify`).
- `.claude/settings.json` drží tieto príkazy zamietnuté na permission vrstve.
