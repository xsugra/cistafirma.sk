import logging
from datetime import date, datetime
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
            json_safe_payload = self._to_json_safe(payload)

            profile, _ = OrsrCompanyProfile.objects.update_or_create(
                company=company,
                defaults={
                    "ico": payload.get("ico") or company.ico,
                    "oddiel": payload.get("oddiel", "") or "",
                    "oddiel_type": payload.get("oddiel_type", "") or "",
                    "vlozka_cislo": payload.get("vlozka_cislo", "") or "",
                    "obchodne_meno": payload.get("obchodne_meno", "") or "",
                    "sidlo": payload.get("sidlo", "") or "",
                    "den_zapisu": payload.get("den_zapisu"),
                    "pravna_forma": payload.get("pravna_forma", "") or "",
                    "konanie": payload.get("konanie", "") or "",
                    "konanie_menom_spolocnosti": payload.get("konanie_menom_spolocnosti", "") or "",
                    "vyska_zakladneho_imania": payload.get("vyska_zakladneho_imania", "") or "",
                    "zapisovane_zakladne_imanie": payload.get("zapisovane_zakladne_imanie", "") or "",
                    "zakladny_clensky_vklad": payload.get("zakladny_clensky_vklad", "") or "",
                    "dalske_pravne_skutocnosti": payload.get("dalske_pravne_skutocnosti", "") or "",
                    "predmet_podnikania": payload.get("predmet_podnikania", []) or [],
                    "spolocnici": payload.get("spolocnici", []) or [],
                    "vklady_spolocnikov": payload.get("vklady_spolocnikov", []) or [],
                    "statutarny_organ": payload.get("statutarny_organ", []) or [],
                    "prokura": payload.get("prokura", []) or [],
                    "predstavenstvo": payload.get("predstavenstvo", []) or [],
                    "kontrolna_komisia": payload.get("kontrolna_komisia", []) or [],
                    "orsr_aktualizacia_dat": payload.get("orsr_aktualizacia_dat"),
                    "orsr_datum_vypisu": payload.get("orsr_datum_vypisu"),
                    "source_url": result.source_url,
                    "raw_sections": payload.get("raw_sections", {}) or {},
                    "raw_payload": json_safe_payload,
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

    def _to_json_safe(self, value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: self._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._to_json_safe(v) for v in value]
        return value
