"""
Párovanie riadkov z datasetov Finančnej správy, ktoré **nenesú IČO**.

Jediný taký dataset je `tax_debtors` (`ds_dsdd`). Overené na produkcii
2026-09-28: súbor má 90 902 položiek a presne päť textových polí
(`NAZOV_SUBJEKTU`, `CIASTKA`, `ULICA_CISLO`, `PSC`, `OBEC`), **žiadny atribút**
na `<ITEM>` ani na deťoch, a z 90 902 názvov obsahuje 8-cifernú skupinu
**jediný** („36597015 s. r. o."). Výskyty slov IČO/DIČ v názvoch (248 + 83 + 221
+ 34) sú súčasťou mena firmy — UNICORN, ABICON, MEDICAL, ADDICTION — nie
identifikátory. **Lepší identifikátor teda neexistuje** a jediná cesta je názov
a adresa.

Prečo je tento matcher taký obmedzujúci
--------------------------------------
Predchádzajúci matcher (tá istá cesta, odstránený 2026-09-09 v `36d80b8`) bral
`fuzz.ratio > 90` a vrátil **najlepšieho z až 1000 kandidátov**. To je presne
to, čo vie zapísať dlh nesprávnej firme, a je to dôvod, prečo bol odstránený.

Tento matcher namiesto hľadania najlepšieho kandidáta **odmieta**. Zhodu prijme
len vtedy, keď existuje **práve jedna** firma s tým istým normalizovaným názvom
**a** tou istou PSČ. Dvaja kandidáti alebo žiadny znamenajú `None` a volajúci
riadok sa preskočí. Nikdy sa nehádá.

Zmerané na produkcii 2026-09-28 (`ds_dsdd`, 90 902 položiek):

  * 68 057 položiek (74,9 %) má práve jedného kandidáta
  * 103 má kandidátov viac  -> odmietnuté
  * 22 742 nemá kandidáta   -> odmietnuté
  * `ULICA_CISLO` nepridáva rozlišovaciu silu (rovnakých 68 057), tak sa
    nepoužíva
  * z 68 057 zhôd stojí **0** na prázdnej PSČ — preto sa neprázdna PSČ
    **vyžaduje**; je to bezplatná bezpečnosť, nie obmedzenie
  * nezávislá kontrola poľom, ktoré match **nepoužil**: obec súhlasí v 97,8 %
    (66 574 z 68 057), a zvyšných 1 483 sú len varianty zápisu toho istého mesta
    („Bratislava - m. č." vs „Bratislava - mestská č")

Dopĺňanie chýbajúcej nuly do PSČ sa **zámerne nerobí**: 533 riadkov v súbore má
4-cifernú PSČ, ale doplnenie na 5 cifier neprinieslo **ani jednu** novú zhodu,
takže by to bol netestovaný kód bez prínosu.
"""
import re
from typing import Optional

from companies.models import Company
from registers.utils import clean_company_name


# Stavy, ktoré `resolve` vracia. Volajúci ich počíta do štatistík, aby bolo
# vidieť, koľko riadkov matcher odmietol a prečo.
UNIQUE = 'unique'            # práve jeden kandidát -- jediný stav, kedy sa páruje
AMBIGUOUS = 'ambiguous'      # viac kandidátov -- nikdy sa nehádame
NO_CANDIDATE = 'no_candidate'  # názov+PSČ nesedí na žiadnu firmu
NO_ADDRESS = 'no_address'    # chýba názov alebo PSČ na niektorej strane

# Sentinel v indexe: kľúč s viac ako jednou firmou. Odlíšiť ho od „kľúč tam
# nie je" je celý zmysel -- `dict.get` vracia `None` v oboch prípadoch, takže
# sa kľúč musí testovať cez `in`.
_AMBIGUOUS = object()


def normalise_psc(value: Optional[str]) -> str:
    """PSČ na porovnanie: len číslice.

    „811 01", „81101" aj „SK-81101" sú tá istá adresa. Nezmysly (1-3 cifry)
    ostanú nezmyslom a nezhodujú sa s ničím -- zámerne sa nedopĺňajú nulami,
    pozri hlavičku modulu.
    """
    return re.sub(r"\D", "", value or "")


class CompanyNameMatcher:
    """Index firiem podľa (normalizovaný názov, PSČ).

    Index drží **len IČO**, nie `Company` objekty: 631 988 firiem v pamäti by
    na produkcii znamenalo stovky MB. Volajúci si firmy potom načíta dávkovo
    podľa IČO, rovnako ako to už robí pre datasety s IČO.
    """

    def __init__(self, by_key: dict):
        self._by_key = by_key

    @classmethod
    def build(cls) -> "CompanyNameMatcher":
        """Postaví index. Beží len keď je naozaj potrebný.

        Pre štyri z piatich datasetov nesie každý riadok IČO, takže sa index
        vôbec nestavia a nič to nestojí.
        """
        by_key = {}
        rows = (
            Company.objects.exclude(nazov_UJ="")
            .exclude(psc="")
            .values_list("ico", "nazov_UJ", "psc")
            .iterator(chunk_size=2000)
        )
        for ico, nazov, psc in rows:
            name = clean_company_name(nazov or "")
            address = normalise_psc(psc)
            if not name or not address:
                continue
            key = (name, address)
            # Druhý výskyt kľúča znamená, že sa nedá rozhodnúť. Zvyšok kľúčov
            # (drvivá väčšina) ostáva jednoznačný.
            by_key[key] = _AMBIGUOUS if key in by_key else ico
        return cls(by_key)

    def __len__(self) -> int:
        return len(self._by_key)

    def resolve(self, item: dict) -> tuple[Optional[str], str]:
        """Vráti `(ico, stav)` pre jednu položku datasetu.

        `ico` je `None` vo všetkých stavoch okrem `UNIQUE` -- a to je celý
        bezpečnostný mechanizmus: keď sa nedá rozhodnúť jednoznačne, riadok sa
        zahodí, nie že by sa pripísal najpodobnejšej firme.
        """
        name = clean_company_name(
            item.get('NAZOV_SUBJEKTU') or item.get('NAZOV_DS') or item.get('NAZOV') or ''
        )
        address = normalise_psc(item.get('PSC'))
        if not name or not address:
            return None, NO_ADDRESS

        key = (name, address)
        if key not in self._by_key:
            return None, NO_CANDIDATE
        ico = self._by_key[key]
        if ico is _AMBIGUOUS:
            return None, AMBIGUOUS
        return ico, UNIQUE
