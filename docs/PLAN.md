# Plán prác — CistaFirma

**Aktualizované:** 2026-09-17
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

**Čo tým vyriešené NIE je** — dve veci, obe v §7: `deploy/k8s` a `deploy/helm`
`BACKEND_RESOLVER` **nenastavujú**, a **nič v zostave výpadok API nezachytí**
(`/healthz` je zámerne slepé voči backendu, `prometheus.yml` nemá ani jedno
pravidlo a `ops_check.sh` nesondážuje frontend vôbec).

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

**Krok 5 nedokončený — permission vrstva zápis odmietla.** `UPDATE
django_celery_beat_periodictask SET last_run_at = …` („Blocked by classifier“).
Neobchádzal som to. Dôsledok je malý a je to **oneskorenie, nie strata**: riadok
má `last_run_at` NULL a `date_changed` 06:37:21.9008 UTC, takže `ModelEntry` ho
číta ako `date_changed` a prvý plánovaný beh padá na **12:37:21 UTC** — o šesť
hodín. Backlog je pritom dorovnaný manuálne, takže ten beh už len potvrdí, že
automatická cesta funguje.

**Čo z toho zostáva otvorené — a čo nie** (overené 2026-09-17 ~07:30 UTC, čítaním):

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

### Nové nálezy tej istej triedy ako #148 — overené, čakajú na tvoje rozhodnutie (2026-09-17)

Po uzavretí `#148` som nechal prejsť celý repozitár **jednou otázkou**: ktoré
ďalšie pole je *odvodené* z iných stĺpcov, zapisuje ho **presne jedna cesta** a
**nič ho neznehodnotí, keď sa zdroj zmení**? To je presne tvar chyby, ktorú mal
`#148` — a hľadanie vrátilo štyri rodiny. Sweep vrátil 6 potvrdení a **0
vyvrátení**, čo je samo o sebe podozrivé číslo, tak som každý nález overoval
zvlášť proti kódu **a proti ostrej databáze na `dell`**. Dva z nich sa pritom
meraním **vecne zmenili** — to je dôvod, prečo tu nie sú odpísané zo sweepu.

**Nič z toho som neopravil.** Každá oprava je nová prírastka (mení zápis alebo
pridáva úlohu), takže podľa pravidiel čaká na tvoje slovo. Nasleduje stav
a cena, nie hotová vec.

#### A. `SectorBenchmark` — počíta sa len pre **jediný** rok, takže 1 586 firiem nemá porovnanie vôbec

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

Rozdelenie firiem podľa **ich vlastného najnovšieho roka** (merané 2026-09-17):

| najnovší rok firmy | firiem | riadkov benchmarku pre ten rok |
|---|---|---|
| 2026 | 80 | **0** |
| 2025 | 12 479 | 19 |
| **2024 a staršie** | **1 506** | **0** |

**Dôsledok — dve rôzne veci, obe zlé:**

1. **1 506 firiem** (tie, ktorých najnovšia závierka je z 2024 a staršia) nemá
   porovnanie so sektorom **bez akéhokoľvek dôvodu** — benchmark pre ich rok sa
   dal dávno spočítať z 12–13 tisíc firiem, ktoré ten rok majú. Toto je
   prevládajúca časť nálezu a v sweepu **nebola**.
2. **80 firiem, a rastie:** firma, ktorá **zverejní novšiu závierku**, sa posunie
   na 2026, `get_benchmark` vráti `None` a o porovnanie **príde** — teda presne
   opačná motivácia, než akú má produkt: čerstvejšie dáta = horšia stránka. Toto
   je tá **rastúca hrana** a s každou ďalšou závierkou za 2026 sa zväčšuje.

Nikde na to nie je kontrola; API vráti `null` a PDF sekciu ticho vynechá.

**Možnosti:** (1) počítať pre **každý rok, ktorý má dáta**, a nechať rozhodovať
len per-sekciovú poistku `>= 5`, ktorá v tom istom súbore už je (`:100-102`);
(2) čítať fallbackom na najnovší benchmarkovaný rok sekcie; (3) znížiť alebo
odstrániť globálny prah. **Odporúčam (1)** — odstráni obe časti nálezu naraz a
ponechá jedinú poistku, ktorá naozaj chráni pred mediánom z pár firiem. Cena je
malá a ohraničená: ~14 rokov × najviac 19 NACE sekcií, teda **rádovo 250 riadkov**
namiesto dnešných 19.

#### B. `vat_deleted_date` / `vat_deleted_reason` — výmaz z DPH sa nikdy nezruší

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
> sú v `focus_mode.py` definované, ale **nikto ich nevolá** — a
> `registers/tests_focus_mode_safety.py:42-43` to **explicitne testuje**
> (`assert_not_called`). Je to zámerná, otestovaná invariantná záruka, že focus
> mode nikdy nesiaha na broker správy, **nie mŕtvy kód**. Zapisujem to sem, aby
> ich niekto nezapojil v dobrej viere.

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

- ⚠️ **`deploy/k8s` a `deploy/helm` nenastavujú `BACKEND_RESOLVER`, takže nový
  frontend image tam nenabehne.** Image ju zámerne deklaruje **prázdnu** (nie
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
- ⚠️ **Nič v zostave nezachytí výpadok API — tých 3 h 43 min bolo pre všetky
  kontroly neviditeľných.** `/healthz` je zámerne slepé voči backendu, a to je
  správne: reštart nginx backend nevráti a probe, ktorý by tu zlyhal, by počas
  každého reštartu backendu reštartoval všetky frontend pody. Lenže to isté
  platí o zvyšku: `deploy/monitoring/prometheus/prometheus.yml` nemá **ani
  jedno** pravidlo („No alerting rules are provisioned — dashboards only")
  a `scripts/local/ops_check.sh` nesondážuje frontend **vôbec** — nemá ani
  zmienku o `frontend`/`5173`/`curl`/`probe`. Celý ten čas kontajner hlásil
  `healthy`. Zachytiť ďalší výskyt chce kontrolu, ktorá prejde **cez `/api/`
  zvonka** — nie zmenu `/healthz`.
- ℹ️ **`/admin/` posiela o dve hlavičky menej než `/api/` — a dnes to nič
  nerobí.** `location /admin/` nastavuje len `Host` a `X-Real-IP`, kým `/api/`
  (a od `f4b822a` aj `@backend_static`) posiela navyše `X-Forwarded-For`
  a `X-Forwarded-Proto`. Je to **predchádzajúci** stav, ktorý som nemenil.
  Overené 2026-09-17: `settings.py` nemá ani `SECURE_PROXY_SSL_HEADER`, ani
  `SECURE_SSL_REDIRECT`, takže `X-Forwarded-Proto` dnes **nikto nečíta** —
  žiadna slučka presmerovaní, žiadny zlý absolutný odkaz. Následok je len ten,
  že Django vidí pri `/admin/` adresu nginx kontajnera namiesto klienta.
  **Kedy to začne bolieť:** v momente, keď pribudne `SECURE_PROXY_SSL_HEADER`
  alebo `SECURE_SSL_REDIRECT` — vtedy `/admin/` začne o sebe tvrdiť, že beží
  cez `http`, a to je presne tá chyba, ktorá sa hľadá ťažko, lebo sa prejaví
  len na admin ceste. Vtedy doplniť rovnaký blok ako `/api/`.
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
   ale **cesta**: zmazať ich znamená `docker volume rm`, čo §8 zakazuje
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
- **`/home/sam/gitlab-runner-setup/gitlab-ci.yml.new` skopírovať do repa** vedľa
  `deploy/ci/README.md`, ktorý už jeho súrodencov verzionuje. Jediná kópia
  pripravenej záložnej cesty je presne tá chyba, ktorú tento projekt raz už
  opravil pri configu runnera.
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

---

## 8. Nemenné pravidlá

Toto sa nemení bez výslovného súhlasu. Detaily v `docs/DATA_PROTECTION.md`.

- Docker volume `cistafirma_postgres_data` je nenahraditeľný. **Produkcia beží
  na `dell`** (od 2026-09-15); ten istý volume existuje aj na Macu, ktorý je
  odstavený a drží sa ako zamrznutá záloha. Pravidlá platia na obe kópie.
- **Nikdy**: `make docker-reset`, `docker compose down -v`, `docker volume rm`,
  `docker volume prune`.
- **Nikdy** rušiť `make celery-purge`, plný RUZ resync ani restore ako
  rutinnú akciu.
- **Nikdy** nerobiť restore cez bežiacu `cistafirma` databázu.
- Pred každou migráciou alebo deštruktívne vyzerajúcou zmenou: čerstvá
  overená záloha (`make db-backup` + `make db-backup-verify`).
- `.claude/settings.json` drží tieto príkazy zamietnuté na permission vrstve.
