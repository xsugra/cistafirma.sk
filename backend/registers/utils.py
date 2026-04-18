import re


def is_money(text: str) -> bool:
    """Overí, či string vyzerá ako suma (obsahuje číslice a €)."""
    if not text or "€" not in text:
        return False
    # Odstránime bordel
    clean = text.replace("€", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        float(clean)
        return True
    except ValueError:
        return False


def parse_money(text: str) -> float:
    """Konvertuje '1 200,50 €' na float 1200.5"""
    clean = text.replace("€", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(clean)


def clean_company_name(name: str) -> str:
    """
    Normalizuje názov spoločnosti pre fuzzy porovnávanie.
    - Prevedie na malé písmená.
    - Odstráni bežné právne formy a ich variácie.
    - Odstráni nadbytočné medzery a interpunkciu.
    """
    if not name:
        return ""

    name = name.lower()

    # Zoznam bežných právnych foriem a iných prípon na odstránenie
    legal_forms_patterns = [
        r'\s+s\s*\.?\s*r\s*\.?\s*o\s*\.?',
        r'\s+spol\s*\.\s*s\s*r\s*\.?\s*o\s*\.?',
        r'\s+a\s*\.?\s*s\s*\.?',
        r'\s+akciová\s+spoločnosť',
        r'\s+spoločnosť\s+s\s+ručením\s+obmedzeným',
        r'\s+v\s*\.?\s*o\s*\.?\s*s\s*\.?',
        r'\s+verejná\s+obchodná\s+spoločnosť',
        r'\s+k\s*\.?\s*s\s*\.?',
        r'\s+komanditná\s+spoločnosť',
        r'\s*,\s*s\s*\.\s*r\s*\.\s*o\s*\.?',
        r'\s*,\s*a\s*\.\s*s\s*\.?',
        r'\s+v\s+likvidácii',
        r'\s+v\s+konkurze',
    ]

    for pattern in legal_forms_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Odstráni interpunkciu, ktorá nie je súčasťou názvu
    name = re.sub(r'[,.]', '', name)

    # Nahradí viacnásobné medzery jednou a odstráni medzery na začiatku/konci
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def validate_iban(iban: str) -> bool:
    """
    Validuje IBAN formát.

    Slovenský IBAN má 24 znakov a začína na 'SK'.
    Validuje aj základný checksum podľa ISO 13616.
    """
    if not iban:
        return False

    # Odstránime medzery a prevedieme na veľké písmená
    iban = iban.replace(' ', '').upper()

    # Základná validácia dĺžky a formátu
    if len(iban) < 15 or len(iban) > 34:
        return False

    if not iban[:2].isalpha():
        return False

    if not iban[2:4].isdigit():
        return False

    # Pre slovenský IBAN kontrola dĺžky 24
    if iban.startswith('SK') and len(iban) != 24:
        return False

    # Validácia checksum (ISO 13616)
    try:
        # Presunieme prvé 4 znaky na koniec
        rearranged = iban[4:] + iban[:4]

        # Prevedieme písmená na čísla (A=10, B=11, ...)
        numeric_string = ''
        for char in rearranged:
            if char.isdigit():
                numeric_string += char
            else:
                numeric_string += str(ord(char) - ord('A') + 10)

        # Modulo 97 musí byť 1
        return int(numeric_string) % 97 == 1
    except (ValueError, OverflowError):
        return False
