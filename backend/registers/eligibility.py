from __future__ import annotations

from companies.models import Company

# ORSR scraping is restricted to company/entity types supported by RPO.
# Keep this mapping centralized so all tasks/commands use identical rules.
ORSR_ELIGIBLE_LEGAL_FORMS = {
    # Obchodné spoločnosti
    "111",  # Verejná obchodná spoločnosť
    "112",  # Spoločnosť s ručením obmedzeným
    "113",  # Komanditná spoločnosť
    "114",  # Jednoduchá spoločnosť na akcie (starý kód)
    "125",  # Jednoduchá spoločnosť na akcie (nový kód z RÚZ)
    "121",  # Akciová spoločnosť
    "122",  # Európske zoskupenie hospodárskych záujmov
    "123",  # Európska spoločnosť
    "124",  # Európske družstvo
    "205",  # Družstvo
    "301",  # Štátny podnik
    "421",  # Zahraničná právnická osoba
    "931",  # Zastúpenie zahraničnej právnickej osoby
    # Verejná správa a samospráva
    "801",  # Obec, mesto (obecný/mestský úrad)
    "803",  # Samosprávny kraj (VÚC)
    "321",  # Rozpočtová organizácia
    "331",  # Príspevková organizácia
    # Cirkevné organizácie
    "721",  # Cirkevná organizácia
}


def is_orsr_eligible_company(company: Company) -> bool:
    legal_form = str(company.pravna_forma or "").strip()
    if not legal_form or legal_form not in ORSR_ELIGIBLE_LEGAL_FORMS:
        return False
    return company.datum_zrusenia is None

