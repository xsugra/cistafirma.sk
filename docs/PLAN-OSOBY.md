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

Keď človek hľadá meno, ktoré u nás nie je (alebo chce overiť), spustí sa
**jeden** request na ORSR. Ak nájde firmy, ktoré nemáme rozpracované:

- zobrazia sa hneď (názov + funkcia + odkaz na výpis)
- vedľa je tlačidlo **„doplniť tieto firmy"**, ktoré pre ne zaradí náš
  existujúci ORSR scraper do fronty `orsr` (už beží na `15/m`)

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

1. ⛔ **`zanik_funkcie` a `is_active`** — doplniť `valid_to` z RPO, prestať
   tvrdiť „aktuálny" tam, kde to nevieme. *Bez tohto sa zvyšok nesmie spustiť.*
2. `GET /api/persons/?q=` — hľadanie bez diakritiky, s filtrom funkcie
3. Frontend: rozdelené výsledky v `SearchBar`, odkaz z `PersonCard`,
   routa `/osoba/:id`
4. Živé doplnenie z ORSR + tlačidlo „doplniť tieto firmy"
5. Stance k osobným údajom (rate limit, žiadny export)

**Pokrytie je jediná skutočná hranica.** 4,5 % firiem znamená, že väčšina
hľadaní u nás nič nenájde — a to je v poriadku, pokiaľ to sekcia povie
a ponúkne register. Čo nie je v poriadku, je tváriť sa, že 4,5 % je všetko.
