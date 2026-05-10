from __future__ import annotations

from companies.models import Company

# ORSR scraping is restricted to company types that should be in the Commercial Register.
# Keep this mapping centralized so all tasks/commands use identical rules.
ORSR_ELIGIBLE_LEGAL_FORMS = {
    "111",  # Verejna obchodna spolocnost
    "112",  # Spolocnost s rucenim obmedzenym
    "113",  # Komanditna spolocnost
    "114",  # Jednoducha spolocnost na akcie
    "121",  # Akciova spolocnost
    "122",  # Europske zoskupenie hospodarskych zaujmov
    "123",  # Europska spolocnost
    "124",  # Europske druzstvo
    "205",  # Druzstvo
    "301",  # Statny podnik
    "421",  # Zahranicna pravnicka osoba
    "931",  # Zastupenie zahranicnej pravnickej osoby
}


def is_orsr_eligible_company(company: Company) -> bool:
    legal_form = str(company.pravna_forma or "").strip()
    if not legal_form or legal_form not in ORSR_ELIGIBLE_LEGAL_FORMS:
        return False
    return company.datum_zrusenia is None

