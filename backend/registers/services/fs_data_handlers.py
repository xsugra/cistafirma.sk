"""
Handlery pre spracovanie dát z Finančnej správy.
Každý handler aktualizuje Company model podľa typu datasetu.
"""
from datetime import datetime
from typing import Callable
from companies.models import Company
from registers.utils import parse_money, validate_iban


class FSDataHandlers:
    """
    Trieda obsahujúca handlery pre jednotlivé datasety z Finančnej správy.
    """

    def __init__(self, stdout_write: Callable, stderr_write: Callable,
                 style_success: Callable, style_error: Callable,
                 style_warning: Callable, verbose: bool = False):
        self.stdout_write = stdout_write
        self.stderr_write = stderr_write
        self.style_success = style_success
        self.style_error = style_error
        self.style_warning = style_warning
        self.verbose = verbose

    def handle_tax_debtors(self, company: Company, item: dict) -> bool:
        """Handler pre daňových dlžníkov."""
        amount_str = item.get('CIASTKA')
        if not amount_str:
            return False

        try:
            debt_amount = parse_money(amount_str)
            if company.tax_debt != debt_amount:
                company.tax_debt = debt_amount
                if self.verbose:
                    self.stdout_write(
                        self.style_success(f"Updated tax debt for {company.nazov_UJ}: {debt_amount} €")
                    )
                return True
        except (ValueError, TypeError) as e:
            self.stderr_write(
                self.style_error(f"Could not parse money '{amount_str}' for {company.nazov_UJ}: {e}")
            )
        return False

    def handle_vat_payers(self, company: Company, item: dict) -> bool:
        """Handler pre platiteľov DPH."""
        updated = False

        if not company.vat_payer:
            company.vat_payer = True
            updated = True

        ic_dph = item.get('IC_DPH', '').strip()
        if ic_dph and company.ic_dph != ic_dph:
            company.ic_dph = ic_dph
            updated = True

        date_str = item.get('DATUM_REG')
        if date_str:
            try:
                parsed_date = datetime.strptime(date_str, '%d.%m.%Y').date()
                if company.datum_reg_dph != parsed_date:
                    company.datum_reg_dph = parsed_date
                    updated = True
            except ValueError:
                self.stderr_write(
                    self.style_error(f"Could not parse date '{date_str}' for {company.nazov_UJ}")
                )

        if updated and self.verbose:
            self.stdout_write(f"Updated VAT status for {company.nazov_UJ} (IČ DPH: {company.ic_dph})")

        return updated

    def handle_bank_accounts(self, company: Company, item: dict) -> bool:
        """Handler pre bankové účty (IBAN)."""
        iban = item.get('IBAN', '').strip().upper()

        if not iban:
            return False

        if not validate_iban(iban):
            self.stderr_write(
                self.style_warning(f"Invalid IBAN format '{iban}' for {company.nazov_UJ}")
            )
            return False

        if company.bank_accounts is None:
            company.bank_accounts = []

        if iban not in company.bank_accounts:
            company.bank_accounts.append(iban)
            if self.verbose:
                self.stdout_write(f"Added bank account for {company.nazov_UJ}: {iban}")
            return True

        return False

    def handle_vat_deleted(self, company: Company, item: dict) -> bool:
        """Handler pre vymazaných platiteľov DPH.

        `vat_deleted_date` a `vat_deleted_reason` sú **história** — zapisujú sa
        vždy, keď dataset nesie iný údaj, a nikdy sa nečistia. `vat_payer` je
        ale **súčasný stav**, a ten sa z histórie odvodiť nedá: kto sa po výmaze
        znovu zaregistroval, je dnes platiteľ.

        `FS_DATASET_URLS` púšťa `vat_payers` **pred** `vat_deleted`, takže v
        jednom priechode bežal tento handler druhý a vždy prepísal verdikt toho
        prvého — aj keď firma bola v oboch datasetoch súčasne. Merané na
        produkcii 2026-09-17: z 32 127 riadkov s `vat_deleted_date` má **384**
        `datum_reg_dph` *neskôr* než výmaz, a **379** z nich malo
        `vat_payer = False`. To je zlý stav: firma sa vykresľovala ako
        „Vymazaný z registra DPH", hoci register ju vedie ako platiteľa.

        Preto sa pri takom riadku flag **neprepína**, ale dátum a dôvod sa
        zapíšu ďalej — `ROK_PORUSENIA` hovorí, prečo bol človek vymazaný, a to
        platí aj po opätovnej registrácii. Nie je to strata údaja: porušenie
        zostáva v `vat_deleted_date`/`vat_deleted_reason` ako záznam.
        """
        updated = False

        dat_vymazu = item.get('DAT_VYMAZU')
        parsed_date = None
        if dat_vymazu:
            try:
                parsed_date = datetime.strptime(dat_vymazu, '%d.%m.%Y').date()
            except ValueError:
                self.stderr_write(
                    self.style_error(f"Could not parse deletion date '{dat_vymazu}' for {company.nazov_UJ}")
                )

        # Registrácia *po* výmaze znamená, že firma je v oboch datasetoch naraz.
        # `>` a nie `>=`: keď je to ten istý deň, poradie sa z dvoch dátumov
        # vyčítať nedá a ostáva pôvodné správanie (flag sa prepne).
        superseded = (
            parsed_date is not None
            and company.datum_reg_dph is not None
            and company.datum_reg_dph > parsed_date
        )

        if company.vat_payer and not superseded:
            company.vat_payer = False
            updated = True

        if parsed_date is not None and company.vat_deleted_date != parsed_date:
            company.vat_deleted_date = parsed_date
            updated = True

        rok_porusenia = item.get('ROK_PORUSENIA')
        if rok_porusenia:
            reason = f"Rok porušenia: {rok_porusenia}"
            if company.vat_deleted_reason != reason:
                company.vat_deleted_reason = reason
                updated = True

        if updated and self.verbose:
            self.stdout_write(
                self.style_warning(f"Marked {company.nazov_UJ} as deleted VAT payer (IČ DPH: {item.get('IC_DPH')})")
            )

        return updated

    def handle_tax_reliability(self, company: Company, item: dict) -> bool:
        """Handler pre index daňovej spoľahlivosti."""
        ids_value = item.get('IDS', '').strip()

        if ids_value and company.tax_reliability != ids_value:
            company.tax_reliability = ids_value
            if self.verbose:
                self.stdout_write(f"Updated tax reliability for {company.nazov_UJ}: {ids_value}")
            return True

        return False

    def update_company(self, company: Company, item: dict, source_key: str) -> bool:
        """
        Hlavná metóda - smeruje na správny handler podľa source_key.
        Returns True ak boli dáta aktualizované.
        """
        handler_map = {
            'tax_debtors': self.handle_tax_debtors,
            'vat_payers': self.handle_vat_payers,
            'bank_accounts': self.handle_bank_accounts,
            'vat_deleted': self.handle_vat_deleted,
            'tax_reliability': self.handle_tax_reliability,
        }

        handler = handler_map.get(source_key)
        if handler:
            return handler(company, item)
        return False
