import logging
from typing import Optional

from companies.models import Company
from registers.models import OrsrCompanyProfile
from registers.scrapers.orsr_scraper import OrsrScraper, OrsrScraperError


logger = logging.getLogger(__name__)


class OrsrSyncService:
    """Synchronizácia ORSR údajov pre firmu."""

    def __init__(self, scraper: Optional[OrsrScraper] = None):
        self.scraper = scraper or OrsrScraper()

    def sync_company(self, company: Company) -> OrsrCompanyProfile:
        try:
            result = self.scraper.fetch_by_ico(company.ico)
            payload = result.parsed

            profile, _ = OrsrCompanyProfile.objects.update_or_create(
                company=company,
                defaults={
                    "ico": payload.get("ico") or company.ico,
                    "oddiel": payload.get("oddiel", ""),
                    "vlozka_cislo": payload.get("vlozka_cislo", ""),
                    "obchodne_meno": payload.get("obchodne_meno", ""),
                    "sidlo": payload.get("sidlo", ""),
                    "den_zapisu": payload.get("den_zapisu"),
                    "pravna_forma": payload.get("pravna_forma", ""),
                    "konanie_menom_spolocnosti": payload.get("konanie_menom_spolocnosti", ""),
                    "vyska_zakladneho_imania": payload.get("vyska_zakladneho_imania", ""),
                    "predmet_podnikania": payload.get("predmet_podnikania", []),
                    "spolocnici": payload.get("spolocnici", []),
                    "vklady_spolocnikov": payload.get("vklady_spolocnikov", []),
                    "statutarny_organ": payload.get("statutarny_organ", []),
                    "orsr_aktualizacia_dat": payload.get("orsr_aktualizacia_dat"),
                    "orsr_datum_vypisu": payload.get("orsr_datum_vypisu"),
                    "source_url": result.source_url,
                    "raw_sections": payload.get("raw_sections", {}),
                    "raw_payload": payload,
                    "fetch_ok": True,
                    "last_error": "",
                },
            )
            return profile

        except OrsrScraperError as exc:
            logger.warning("ORSR sync failed for company=%s ico=%s: %s", company.id, company.ico, exc)
            profile, _ = OrsrCompanyProfile.objects.get_or_create(
                company=company,
                defaults={"ico": company.ico},
            )
            profile.fetch_ok = False
            profile.last_error = str(exc)
            profile.save(update_fields=["fetch_ok", "last_error", "last_synced_at"])
            raise

