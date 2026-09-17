from __future__ import annotations

from companies.models import Company, normalize_legal_form_code

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
    # Normalize stored value before checking eligibility set
    legal_form = normalize_legal_form_code(getattr(company, 'pravna_forma', None))
    if not legal_form or legal_form not in ORSR_ELIGIBLE_LEGAL_FORMS:
        return False
    return company.datum_zrusenia is None


def orsr_ineligibility_reason(company: Company) -> str:
    """Why ORSR monitoring does not ask about this company, in one Slovak phrase.

    The counterpart of `is_orsr_eligible_company` for the places that need to
    *say* why rather than just decide. `sync_company_orsr_data` returns early on
    a company this refuses, and a due retry row it returns early on is a row
    nothing will ever write back -- it is drawn by every batch and left due by
    each one. Recording the reason on the row is what turns that from a state
    nobody can see into one an operator can read.

    Only meaningful for a company the predicate refuses; the caller checks that
    first, so this does not repeat the check.
    """
    if company.datum_zrusenia is not None:
        return f"firma je zrušená ({company.datum_zrusenia:%d.%m.%Y})"
    return (
        f"právna forma {company.pravna_forma!r} nepatrí medzi formy, "
        f"ktoré ORSR monitoruje"
    )

