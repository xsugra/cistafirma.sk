

def is_money(text: str) -> bool:
    """
    Funkciu pouzivaju scrapery:
        - backend/registers/scrapers/soc_poist_debt.py
        - backend/registers/scrapers/vszp_debt.py
    Pomocná funkcia: Zistí, či string vyzerá ako peniaze.
    """
    # Odstranime medzery a znak EUR
    clean = text.replace(" ", "").replace("€", "").replace(",", ".")
    try:
        float(clean)
        return True
    except ValueError:
        return False


def parse_money(text: str) -> float:
    """
    Funkciu pouzivaju scrapery:
        - backend/registers/scrapers/soc_poist_debt.py
        - backend/registers/scrapers/vszp_debt.py
    Prevedie string '1 200,50 €' na float 1200.50
    """
    clean = text.replace(" ", "").replace("€", "").replace("\xa0", "")
    clean = clean.replace(",", ".")
    return float(clean)

import re

def clean_company_name(name: str) -> str:
    """
    Normalizuje názov firmy pre lepšie porovnávanie.
    - Odstráni úvodzovky a biele miesta na začiatku a na konci
    - Zjednotí právne formy (napr. "spol. s r.o.", "s.r.o." na "s r o")
    - Odstráni nadbytočné medzery
    - Prevedie na malé písmená
    """
    if not name:
        return ""

    name = name.lower()
    # Odstránenie obsahu v zátvorkách, často obsahuje "v likvidácii", "v konkurze"
    name = re.sub(r'\(.*\)', '', name)
    # Odstránenie úvodzoviek a podobných znakov
    name = name.replace('"', '').replace("'", "").replace("„", "").replace("“", "")
    # Nahradenie bodiek a čiarok za medzery, aby sa zjednotili formy ako s.r.o. a s r o
    name = name.replace('.', ' ').replace(',', ' ')
    # Zjednotenie právnych foriem
    replacements = {
        'spoločnosť s ručením obmedzeným': 's r o',
        'spol s r o': 's r o',
        'akciová spoločnosť': 'a s',
        'verejná obchodná spoločnosť': 'v o s',
        # ... pridať ďalšie podľa potreby
    }
    for old, new in replacements.items():
        name = name.replace(old, new)

    # Odstránenie nadbytočných medzier
    name = re.sub(r'\s+', ' ', name).strip()
    return name