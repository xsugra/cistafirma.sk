"""
NACE classification utilities for SK NACE Rev. 2.

Maps numeric NACE division codes to section letters and names.
Handles codes in format "43120", "62.01", "62010", etc.
"""

from __future__ import annotations

import re

# Division → Section mapping (by first 2 digits of NACE code)
# Source: SK NACE Rev. 2 (Eurostat / ŠÚ SR)
_DIVISION_TO_SECTION: dict[int, str] = {}

# Build the mapping from ranges
_SECTION_RANGES: list[tuple[range, str, str]] = [
    (range(1, 4), 'A', 'Poľnohospodárstvo, lesníctvo a rybolov'),
    (range(5, 10), 'B', 'Ťažba a dobývanie'),
    (range(10, 34), 'C', 'Priemyselná výroba'),
    (range(35, 36), 'D', 'Dodávka elektriny, plynu, pary a studeného vzduchu'),
    (range(36, 40), 'E', 'Dodávka vody; čistenie a odvod odpadových vôd, odpady a sanácia'),
    (range(41, 44), 'F', 'Stavebníctvo'),
    (range(45, 48), 'G', 'Veľkoobchod a maloobchod; oprava motorových vozidiel a motocyklov'),
    (range(49, 54), 'H', 'Doprava a skladovanie'),
    (range(55, 57), 'I', 'Ubytovacie a stravovacie služby'),
    (range(58, 64), 'J', 'Informácie a komunikácia'),
    (range(64, 67), 'K', 'Finančné a poisťovacie činnosti'),
    (range(68, 69), 'L', 'Činnosti v oblasti nehnuteľností'),
    (range(69, 76), 'M', 'Odborné, vedecké a technické činnosti'),
    (range(77, 83), 'N', 'Administratívne a podporné služby'),
    (range(84, 85), 'O', 'Verejná správa a obrana; povinné sociálne zabezpečenie'),
    (range(85, 86), 'P', 'Vzdelávanie'),
    (range(86, 89), 'Q', 'Zdravotníctvo a sociálna pomoc'),
    (range(90, 94), 'R', 'Umenie, zábava a rekreácia'),
    (range(94, 97), 'S', 'Ostatné činnosti'),
    (range(97, 99), 'T', 'Činnosti domácností ako zamestnávateľov'),
    (range(99, 100), 'U', 'Činnosti extrateritoriálnych organizácií a združení'),
]

for rng, letter, name in _SECTION_RANGES:
    for div in rng:
        _DIVISION_TO_SECTION[div] = letter

_SECTION_NAMES: dict[str, str] = {letter: name for _, letter, name in _SECTION_RANGES}

# Common division names for context
_DIVISION_NAMES: dict[int, str] = {
    1: 'Pestovanie plodín a chov zvierat',
    2: 'Lesníctvo a ťažba dreva',
    3: 'Rybolov a akvakultúra',
    5: 'Ťažba uhlia a lignitu',
    6: 'Ťažba ropy a zemného plynu',
    7: 'Dobývanie kovových rúd',
    8: 'Iná ťažba a dobývanie',
    9: 'Pomocné činnosti pri ťažbe',
    10: 'Výroba potravín',
    11: 'Výroba nápojov',
    12: 'Výroba tabakových výrobkov',
    13: 'Výroba textilu',
    14: 'Výroba odevov',
    15: 'Výroba kože a kožených výrobkov',
    16: 'Spracovanie dreva a výroba výrobkov z dreva',
    17: 'Výroba papiera a papierových výrobkov',
    18: 'Tlač a reprodukcia záznamových médií',
    19: 'Výroba koksu a rafinovaných ropných produktov',
    20: 'Výroba chemikálií a chemických produktov',
    21: 'Výroba farmaceutických výrobkov',
    22: 'Výroba výrobkov z gumy a plastu',
    23: 'Výroba ostatných nekovových minerálnych výrobkov',
    24: 'Výroba a spracovanie kovov',
    25: 'Výroba kovových konštrukcií',
    26: 'Výroba počítačových, elektronických a optických výrobkov',
    27: 'Výroba elektrických zariadení',
    28: 'Výroba strojov a zariadení i. n.',
    29: 'Výroba motorových vozidiel, návesov a prívesov',
    30: 'Výroba ostatných dopravných prostriedkov',
    31: 'Výroba nábytku',
    32: 'Iná výroba',
    33: 'Oprava a inštalácia strojov a prístrojov',
    35: 'Dodávka elektriny, plynu, pary a studeného vzduchu',
    36: 'Zber, úprava a dodávka vody',
    37: 'Čistenie a odvod odpadových vôd',
    38: 'Zber, spracúvanie a likvidácia odpadov',
    39: 'Ozdravovacie činnosti a ostatné činnosti nakladania s odpadom',
    41: 'Výstavba budov',
    42: 'Inžinierske stavby',
    43: 'Špecializované stavebné práce',
    45: 'Veľkoobchod a maloobchod a oprava motorových vozidiel',
    46: 'Veľkoobchod okrem motorových vozidiel',
    47: 'Maloobchod okrem motorových vozidiel',
    49: 'Pozemná doprava a doprava potrubím',
    50: 'Vodná doprava',
    51: 'Letecká doprava',
    52: 'Skladové a pomocné činnosti v doprave',
    53: 'Poštové a kuriérske služby',
    55: 'Ubytovanie',
    56: 'Činnosti reštaurácií a pohostinstiev',
    58: 'Nakladateľské činnosti',
    59: 'Výroba filmov, videozáznamov a televíznych programov',
    60: 'Vysielanie a televízia',
    61: 'Telekomunikácie',
    62: 'Počítačové programovanie, poradenstvo a súvisiace služby',
    63: 'Informačné služby',
    64: 'Finančné služby okrem poistenia a dôchodkového zabezpečenia',
    65: 'Poistenie, zaistenie a dôchodkové zabezpečenie',
    66: 'Pomocné činnosti súvisiace s finančnými službami a poistením',
    68: 'Činnosti v oblasti nehnuteľností',
    69: 'Právne a účtovnícke činnosti',
    70: 'Vedenie firiem; poradenstvo v oblasti riadenia',
    71: 'Architektonické a inžinierske činnosti; technické testovanie',
    72: 'Vedecký výskum a vývoj',
    73: 'Reklama a prieskum trhu',
    74: 'Ostatné odborné, vedecké a technické činnosti',
    75: 'Veterinárne činnosti',
    77: 'Prenájom a lízing',
    78: 'Sprostredkovanie pracovných síl',
    79: 'Činnosti cestovných agentúr a tour operátorov',
    80: 'Bezpečnostné a pátracie služby',
    81: 'Činnosti súvisiace s údržbou zariadení a krajinnou úpravou',
    82: 'Administratívne, pomocné kancelárske a iné obchodné pomocné činnosti',
    84: 'Verejná správa a obrana; povinné sociálne zabezpečenie',
    85: 'Vzdelávanie',
    86: 'Zdravotníctvo',
    87: 'Starostlivosť v pobytových zariadeniach',
    88: 'Sociálna práca bez ubytovania',
    90: 'Tvorivé, umelecké a zábavné činnosti',
    91: 'Činnosti knižníc, archívov, múzeí a ostatných kultúrnych zariadení',
    92: 'Činnosti herní a stávkových kancelárií',
    93: 'Športové, zábavné a rekreačné činnosti',
    94: 'Činnosti členských organizácií',
    95: 'Oprava počítačov, osobných potrieb a potrieb pre domácnosti',
    96: 'Ostatné osobné služby',
    97: 'Činnosti domácností ako zamestnávateľov domáceho personálu',
    98: 'Nešpecifikované činnosti domácností produkujúcich tovary a služby',
    99: 'Činnosti extrateritoriálnych organizácií a združení',
}


def _extract_division(nace_code: str | None) -> int | None:
    """Extract the 2-digit division from a NACE code string.

    Handles: '43120', '62.01', '62010', '62.01.0', etc.
    """
    if not nace_code:
        return None
    # Remove dots and whitespace
    cleaned = re.sub(r'[.\s]', '', str(nace_code).strip())
    if not cleaned:
        return None
    # Take first two digits
    digits = re.findall(r'\d', cleaned)
    if len(digits) < 2:
        return None
    try:
        division = int(''.join(digits[:2]))
    except (ValueError, IndexError):
        return None
    return division


def get_nace_section(nace_code: str | None) -> str | None:
    """Return the section letter (A-U) for a NACE code, or None."""
    division = _extract_division(nace_code)
    if division is None:
        return None
    return _DIVISION_TO_SECTION.get(division)


def get_nace_section_name(nace_code: str | None) -> str | None:
    """Return the section name for a NACE code, or None."""
    section = get_nace_section(nace_code)
    if section is None:
        return None
    return _SECTION_NAMES.get(section)


def get_nace_division_name(nace_code: str | None) -> str | None:
    """Return the division name for a NACE code, or None."""
    division = _extract_division(nace_code)
    if division is None:
        return None
    return _DIVISION_NAMES.get(division)


def get_nace_info(nace_code: str | None) -> dict | None:
    """Return full NACE info dict for a code."""
    division = _extract_division(nace_code)
    if division is None:
        return None
    section = _DIVISION_TO_SECTION.get(division)
    return {
        'code': str(nace_code),
        'division': division,
        'division_name': _DIVISION_NAMES.get(division),
        'section': section,
        'section_name': _SECTION_NAMES.get(section) if section else None,
    }
