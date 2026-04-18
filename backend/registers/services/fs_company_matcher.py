"""
Fuzzy matching pre vyhľadávanie firiem v databáze.
Používa sa ako fallback keď IČO nie je dostupné.
"""
from typing import Optional
from thefuzz import fuzz
from companies.models import Company
from registers.utils import clean_company_name


def find_company_by_fuzzy_match(item: dict, confidence_threshold: int = 90) -> Optional[Company]:
    """
    Nájde firmu v databáze pomocou fuzzy matchingu na názov a adresu.

    Args:
        item: Slovník s dátami z FS (NAZOV_SUBJEKTU, PSC, OBEC, atď.)
        confidence_threshold: Minimálna zhoda v % (default 90%)

    Returns:
        Company objekt alebo None ak sa nenašla zhoda.
    """
    # Získanie názvu - rôzne datasety používajú rôzne kľúče
    cleaned_name = clean_company_name(
        item.get('NAZOV_SUBJEKTU') or item.get('NAZOV_DS') or item.get('NAZOV', '')
    )
    if not cleaned_name:
        return None

    psc = item.get('PSC', '').replace(' ', '')
    obec = item.get('OBEC', '')

    # Filtrovanie kandidátov podľa PSČ a obce
    candidate_companies = Company.objects.all()
    if psc:
        candidate_companies = candidate_companies.filter(psc=psc)
    if obec:
        candidate_companies = candidate_companies.filter(mesto__icontains=obec)

    # Limit kandidátov pre výkon
    candidates = list(candidate_companies[:1000])

    if not candidates:
        return None

    # Fuzzy matching
    best_match = None
    highest_ratio = 0

    for company in candidates:
        db_cleaned_name = clean_company_name(company.nazov_UJ)
        ratio = fuzz.ratio(cleaned_name, db_cleaned_name)

        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = company

    if highest_ratio > confidence_threshold:
        return best_match

    return None
