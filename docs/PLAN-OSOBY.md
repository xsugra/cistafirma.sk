# Hľadanie osôb — návrh

**Otázka:** „Dám do vyhľadávania meno a priezvisko a nájde mi to, v akých
všetkých firmách tá osoba figuruje."

**Krátka odpoveď:** áno, ORSR to vie a je to overené naživo. Ale **nie je
pravda, že by pri tom musel prebehnúť sync podľa mena** — a keby prebehol,
bola by to chyba. Graf osôb už v databáze máme.

Zisťovanie prebehlo 2026-09-13, všetky čísla sú z bežiacej databázy a všetky
tvary URL z naživo zavolaného registra.

---

## 1. Čo vie ORSR (overené naživo)

| | |
|---|---|
| formulár | `https://www.orsr.sk/search_osoba.asp` |
| výsledky | `https://www.orsr.sk/hladaj_osoba.asp` |
| parametre | `PR` = priezvisko, `MENO` = meno, `SID` = súd (0 = všetky), `T` = typ osoby, `R` = on |
| kódovanie | **cp1250**, nie UTF-8 |
| stránkovanie | 20 záznamov na stránku |

**Živý test** — `PR=Trnka&MENO=Miroslav`: **18 záznamov** na 1 stránke,
vrátane `ESET, spol. s r.o.`, `Trnka, s.r.o.` a `Trnka Investments`.
Záznamy 1–12 sú „Miroslav Trnka", 13–18 „Ing. Miroslav Trnka".

**Filter `Typ osoby` je presne to, čo si vymenoval** — dá sa vybrať:

```
fyzická (všetky)        fyzická - štatutár        fyzická - prokurista
fyzická - spoločník     fyzická - člen dozornej rady
fyzická - likvidátor    fyzická - konateľ*        fyzická - akcionár
fyzická - komanditista  fyzická - komplementár    fyzická - vedúci odt. závodu
+ právnická - spoločník / komanditista / komplementár / zakladateľ / akcionár
```
\* konateľ je v zozname ako „štatutár"; register nerozlišuje predsedu a člena.

### Jeho obmedzenia — a sú vážne

1. **Presná diakritika je povinná.** `PR=novak` → **0 záznamov**.
   `PR=Nov%E1k` → **24 záznamov**. Kto hľadá bez diakritiky, nedostane nič
   a bude si myslieť, že osoba v registri nie je.
2. **Len aktuálne záznamy.** Formulár ponúka jedinú možnosť „len v aktuálnych
   záznamoch"; históriu vybrať nedá. Overené nepriamo: `Tábor Tibor`, ktorého
   my vedieme v družstve `00363243` (zrušené), v registri **nemá záznam**.
3. **Výsledok neobsahuje IČO** — len názov firmy a odkaz
   `vypis.asp?ID=232588&SID=2&P=0`. Získať IČO znamená jeden ďalší request
   na každý výsledok.
4. **Nerozlišuje rovnomenných ľudí.** Pri Trnkovi ukáže 18 záznamov bez
   dátumu narodenia či adresy a nehovorí, koľko je to osôb. Či je
   „Miroslav Trnka" od ESETu ten istý ako pri `Trnka, s.r.o.`, sa z výsledku
   nedozvieš.

---

## 2. Čo už máme (a preto netreba sync)

```
connections_person                  44 897 osôb
connections_personcompanyrelation   64 128 väzieb
firiem s osobami                    19 906  (z 445 626 = 4,5 %)
osôb vo viac ako jednej firme        2 164
```

Väzby sú **štruktúrované podľa funkcie**, nie ako text:

| funkcia | počet |
|---|---|
| Spoločník v.o.s. / s.r.o. | 26 864 |
| Konateľ | 24 273 |
| Predstavenstvo | 5 102 |
| Člen dozorného orgánu | 4 741 |
| Prokurista | 829 |
| Likvidátor | 515 |
| Riaditeľ | 406 |
| Jediný akcionár a.s. | 272 |

A **endpoint na „v akých firmách figuruje" už existuje**:
`GET /api/persons/<id>/` vracia osobu a `companies[]` s rolou, `is_active`,
`vznik_funkcie` a `zanik_funkcie`. Chýba len **hľadanie podľa mena** —
dnes sa dá len podľa číselného `id`.

---

## 3. Prekážka, ktorú treba opraviť PRVÚ

**Naša databáza dnes tvrdí, že každá z 64 128 väzieb je aktuálna.** A nie je
to pravda.

```python
# connections/services.py
"is_active": True,          # natvrdo, pri každom zápise
```

`zanik_funkcie` sa **nikdy nezapisuje**. Dôkaz z bežiacej databázy: Tibor
Tábor, Jozef Tábor, Ján Vojtek, Ferdinand Nagy, Eugen Gaál, Anna Fábiková —
všetci `is_active=True` v `Poľnohospodárske družstvo Trávnik` (IČO 00363243),
ktoré je **zrušené**.

A pritom to vieme: RPO **posiela `validTo`**, klient ho **aj parsuje**
(`RpoPerson.valid_to`), má naň **aj vlastnosť**:

```python
@property
def is_current(self) -> bool:
    return not self.valid_to
```

…a potom ho `_person_to_structured` **zahodí** — do `structured` ide len
`vznik_funkcie`. Dáta sa stiahnu, namodelujú, dostanú pomôcku — a na poslednom
kroku sa zahodia.

**Prečo to musí byť prvé:** funkcia „v akých firmách figuruje Miroslav Trnka"
je tvrdenie o *súčasnosti*. Kým `is_active` znamená „nevieme" a číta sa ako
„áno", sekcia by o firmách tvrdila príbuzenstvo, ktoré sme neoverili — presne
to, čomu sa celý tento projekt vyhýba. Sú to tri stavy, nie dva: **áno / nie /
nevieme**.

---

## 4. Návrh

### 4.1 Dve odpovede, jasne označené

Jedno vyhľadávacie pole, výsledky rozdelené do dvoch skupín — rovnaký vzor,
aký už používajú účtovné závierky (naše dáta + odkaz na zdroj):

| skupina | odkiaľ | kedy |
|---|---|---|
| **Osoby u nás** | naša databáza | okamžite, s funkciou, firmou a dátumami |
| **Register ORSR** | živý request | na kliknutie, „overiť v registri" |

Čitateľ tak vidí, čo tvrdíme my (a s akým pokrytím), a čo hovorí register —
a nezamení si jedno za druhé.

### 4.2 Naše hľadanie

- nový endpoint `GET /api/persons/?q=` — hľadá v `connections_person.name`
- diakritiky **necitlivé** (fingerprint sa už tak normalizuje), takže
  „kovac" nájde „Kováč" — **to ORSR nevie a je to náš reálny prínos**
- filter podľa funkcie, z toho istého číselníka, ktorý už máme
- pri každom výsledku sa vypíše pokrytie: „máme osoby pre 19 906 z 445 626
  firiem" — bez toho by zoznam vyzeral ako zoznam všetkého
- `PersonCard` prestane byť mŕtvy text a meno sa stane odkazom
- routa `/osoba/:id`

### 4.3 Živé doplnenie z ORSR — to je tá „sync podľa mena", ale ohraničená

**Realizované 2026-09-13** ako `GET /api/persons/orsr/?q=` + `OrsrPersonSearch`,
a to inak, než tento plán pôvodne čakal. Overené proti živému registru:

- endpoint je `hladaj_osoba.asp`, stránka je **cp1250**, nie UTF-8;
- **diakritika je presná**: `PR=novak` vráti 0 záznamov, `PR=Novák` 24. Preto sa
  dotaz pošle raz tak, ako ho človek napísal, a **len ak nevrátil nič**, skúsi
  sa druhý raz bez diakritiky. Výsledky sa nezlúčia — druhý pokus je náhrada,
  nie rozšírenie, inak by počet z registra prestal opisovať to, čo je na obrazovke;
- výsledkový riadok je `Meno | Obchodné meno subjektu | Výpis | Zbierka
  dokumentov`. **Stĺpec s funkciou neexistuje** — register hovorí, *v akej
  firme* človek figuruje, nie *ako*. Pôvodný plán tu rátal s „názov + funkcia";
  funkcia by znamenala jeden `vypis.asp` request na firmu, čo je presne to
  hromadné doťahovanie, ktorému sa chceme vyhnúť. Odpoveď to hovorí nahlas
  (`note` v payloade) namiesto prázdneho stĺpca;
- register ukazuje **len aktuálne záznamy** — kto z firmy odišiel v 2019, v tom
  zozname nie je vôbec. To je presne dôvod, prečo musí existovať aj naša
  skupina výsledkov, a prečo sa to v UI píše;
- odpoveď sa **cachuje 900 s** (`ORSR_PERSON_CACHE_SECONDS`) a je
  **rate-limitovaná 60/h** na volajúceho (`OrsrPersonThrottle`); cache kľúč je
  normalizovaný, takže `trnka`, `Trnka` a `TRNKA` sú jeden request. Zlyhanie sa
  necachuje — inak by minúta výpadku registra bola štvrťhodinou tej istej
  nesprávnej odpovede.

**Rozhodnutie (2026-09-13): v prvej verzii nie je tlačidlo „doplniť tieto
firmy".** Register je formulár bez API a jeden request na firmu; tlačidlo vedľa
výsledku by znamenalo, že o tom, koľko requestov proti cudziemu serveru pošleme,
rozhoduje to, koľko priezvisko má zhod. Naša skupina výsledkov sa napĺňa
vlastným dočítaním histórie (`schedule_person_history_resync`), ktoré je

1. **ohraničené** — 2 000 firiem / 4 h, okolo 15 requestov/min,
2. **nezávislé od vstupu z klávesnice** — beží samo, nie preto, že niekto
   niečo napísal,
3. **samovyprázdňujúce sa** — vyberá profily bez `osoby_historia` a ten istý
   kľúč aj zapisuje, takže po poslednom prečítanom profile sa zastaví. To platí
   len vtedy, ak **každú vybranú firmu vie čítač aj označiť**: čítanie histórie
   preto beží v `read_person_history` bez `is_orsr_eligible_company`. Tá
   podmienka patrí ORSR monitoringu (register vedie len aktuálne záznamy), nie
   histórii osôb — a kým platila na obe, 92 profilov (zrušené firmy a cirkvi)
   nemohlo kľúč získať nikdy, takže populácia nikdy nedosiahla nulu a riadok
   beat-u by sa nedal vypnúť.

**Prečo to nesmie byť automatické pri každom hľadaní:**

1. Príkaz na zápis riadený vstupom z klávesnice je neohraničená cesta.
   „Trnka" = 18 firiem, ale bežné priezvisko môže byť stovky.
2. Sync nie je „podľa mena" — ORSR nemá enumerovateľné API, je to formulár.
   Nedá sa z neho „stiahnuť všetko".
3. Pre 19 906 firiem by sme znovu sťahovali to, čo už máme.

### 4.4 Čo si vyžaduje rozhodnutie: osobné údaje

Vyhľadávanie **podľa mena fyzickej osoby** je iná kategória než výpis
konateľov pri firme, ktorú práve pozeráš. Údaje sú verejné, ale nástroj
„zadaj meno a zisti, kde všade človek je" je nová funkcia s vlastným rizikom.
V projekte dnes **neexistuje dokument, ktorý by to riešil**
(`docs/DATA_PROTECTION.md` je o zálohách). Pred spustením by mal mať:
rate limit, žiadny hromadný export, a jednu vetu, ktorá používateľovi
povie, odkiaľ údaje sú.

---

## 5. Poradie prác

1. ✅ **`zanik_funkcie` a `is_active`** — `osoby_historia` v `structured`,
   trojstavové `is_active` (plná / čiarkovaná / bodkovaná hrana + legenda
   „Ukončené" a „Neznáme"), dočítanie histórie pre 24 237 profilov.
2. ✅ `GET /api/persons/?q=` — hľadanie bez diakritiky, s filtrom funkcie
3. ✅ Frontend: rozdelené výsledky v `SearchBar` („Osoby u nás" + register
   ORSR ako vlastná skupina), routa `/osoba/:id`, dvojklik na uzol osoby
   v grafe. **Odkaz z `PersonCard` zámerne nie je** — a nie je to
   nedokončená práca, ale chýbajúci údaj: osoby v sekcii `PeopleOrgansSection`
   prichádzajú z ORSR profilu firmy ako *mená*, bez `Person.id`, a endpoint
   firma → osoby neexistuje. Odkaz by teda nemal kam viesť; bola by to nová
   API plocha, nie odkaz.
4. ✅ `GET /api/persons/orsr/?q=` — živý register (bez tlačidla „doplniť tieto
   firmy", viď 4.3)
5. ✅ Stance k osobným údajom: rate limit (60/h) ✅, žiadny export ✅, veta
   o pôvode údajov v UI ✅. Register má vlastnú skupinu s odznakom „Nie sú to
   naše dáta", vlastným zdrojovým odkazom na `orsr.sk` a `note` z API
   o tom, čo register nezverejňuje — plus tri stavy, ktoré sa nesmú zliať:
   *nedostupné* / *prázdne* / *neopýtané sa*. Prázdny výsledok navyše hovorí,
   že bez diakritiky sme to už skúsili (endpoint to robí sám), takže
   „skúste to bez diakritiky" by bola rada, ktorú už nikto nemôže použiť.

**Pokrytie je jediná skutočná hranica.** 4,5 % firiem znamená, že väčšina
hľadaní u nás nič nenájde — a to je v poriadku, pokiaľ to sekcia povie
a ponúkne register. Čo nie je v poriadku, je tváriť sa, že 4,5 % je všetko.

### Stav dočítania histórie (merané 2026-09-13 10:53)

Dočítanie beží a je zdravé, ale **je pomalšie, než sa odhadovalo pri
schválení** — a to je rozhodnutie pre zadávateľa, nie vec, ktorú by som mal
ticho zmeniť.

| | |
|---|---|
| ORSR profilov celkom | 24 468 |
| s kľúčom `osoby_historia` (prečítané) | 263 |
| vynechaných z výberu (napr. `fetch_ok=False`) | 231 |
| zostáva (`pending_person_history()`) | 23 974 |
| rýchlosť (meraná z logu) | 46 úloh / 3 min = **15,3/min** |
| čistý čas fronty | 23 974 / 15,3 ≈ **26 h** |
| reálny čas pri dávke 2 000 / 4 h | ≈ **48 h** |

Rozdiel medzi 26 h a 48 h je prestoj medzi dávkami: 2 000 úloh sa pri
15/min vyčerpá za 133 min, takže z každého 4-hodinového okna je ~107 min
fronta prázdna. Fronta `orsr` je navyše spoločná so
`sync-missing-orsr-profiles`, takže reálna rýchlosť môže byť nižšia.

**Voľba:** zvýšiť dávku (menej prestojov, ale väčší tlak na zdieľanú frontu
a na orsr.sk) alebo nechať 2 000/4 h a prijať ~48 h. Bezpečnostná rezerva,
ktorú dávka drží, je dôvod, prečo som ju sám nemenil.
