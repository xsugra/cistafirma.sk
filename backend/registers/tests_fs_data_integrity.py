import io
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import OutputWrapper
from django.test import TestCase

from companies.models import Company
from registers.management.commands.update_fs_data import Command
from registers.services.fs_data_handlers import FSDataHandlers
from registers.utils import parse_money_decimal


class _FsCommandTestCase(TestCase):
    """Spoločný základ: reálne handlery a zachytený stderr.

    Handlery sú **skutočné**, nie `Mock` -- inak by test neoveril to, čo je na
    celej veci najdôležitejšie: že sa hodnota naozaj zapíše (alebo nezapíše)
    do stĺpca cez `bulk_update`.
    """

    DATASET_URL = "https://example.invalid/dataset.zip"

    def setUp(self):
        # Dva rôzne výstupy, a oba treba: handlery píšu do svojich callbackov,
        # ale príkaz sám píše cez `self.stdout`/`self.stderr`. Prvá verzia
        # testu zachytávala len tie prvé, takže hláška o datasete, ktorý nič
        # nenašiel, sa do asercie nikdy nedostala.
        self.stderr_lines = []
        self.stdout_lines = []
        self.command_out = io.StringIO()
        self.command_err = io.StringIO()
        self.handlers = FSDataHandlers(
            stdout_write=self.stdout_lines.append,
            stderr_write=self.stderr_lines.append,
            style_success=lambda s: s,
            style_error=lambda s: s,
            style_warning=lambda s: s,
        )

    def run_dataset(self, key, items, dry_run=False):
        target = "registers.management.commands.update_fs_data.download_and_parse_fs_data"
        command = Command()
        command.stdout = OutputWrapper(self.command_out)
        command.stderr = OutputWrapper(self.command_err)
        with patch(target) as mock_download:
            mock_download.return_value = items
            return command._process_dataset(key, self.DATASET_URL, self.handlers, dry_run)

    def allOutput(self):
        return "\n".join(
            self.stderr_lines + self.stdout_lines
            + [self.command_err.getvalue(), self.command_out.getvalue()]
        )

    def assertSaid(self, fragment):
        joined = self.allOutput()
        self.assertIn(fragment, joined, f"nevypísané: {fragment!r}\nbolo:\n{joined}")


class SafeNameMatchingTests(_FsCommandTestCase):
    """`ds_dsdd` (daňoví dlžníci) nemá IČO -- ani nemôže, súbor má päť textových
    polí a žiadny atribút. Páruje sa teda názvom a PSČ, ale **len keď je
    kandidát práve jeden**; dvaja kandidáti alebo žiadny znamenajú zahodenie.

    Merané na produkcii 2026-09-28: zo 90 902 položiek má 68 057 práve jedného
    kandidáta, 103 viac a 22 742 žiadneho.
    """

    def setUp(self):
        super().setUp()
        self.company = Company.objects.create(
            ruz_id=1,
            ico="50059959",
            nazov_UJ="Exact Name s. r. o.",
            mesto="Bratislava",
            psc="81101",
        )

    def debtor(self, **overrides):
        item = {
            "NAZOV_SUBJEKTU": self.company.nazov_UJ,
            "OBEC": self.company.mesto,
            "PSC": self.company.psc,
            "CIASTKA": "999,99",
        }
        item.update(overrides)
        return item

    def test_a_row_without_ico_is_matched_when_one_company_fits(self):
        """Náhrada za starý test „bez IČO sa nepáruje".

        Staré správanie bolo „nepáruj vôbec", čo nechalo 90 902 riadkov ročne
        nepoužitých. Nové je „páruj len vtedy, keď sa nedá pomýliť" -- a to je
        iná, užšia vlastnosť než tá, ktorú kódil pôvodný test.
        """
        stats = self.run_dataset("tax_debtors", [self.debtor()])

        self.assertEqual(stats["name_matched"], 1)
        self.assertEqual(stats["updated"], 1)
        self.company.refresh_from_db()
        self.assertEqual(self.company.tax_debt, Decimal("999.99"))

    def test_two_companies_with_the_same_name_and_psc_are_refused(self):
        """Presne to, čo robil odstránený fuzzy matcher: vybral najlepšieho.

        Dve firmy s tým istým názvom aj PSČ sú nerozoznateľné, takže sa
        nevyberá ani jedna -- dlh sa nepripíše ani jednej.
        """
        druha = Company.objects.create(
            ruz_id=2,
            ico="12345678",
            nazov_UJ=self.company.nazov_UJ,
            mesto="Bratislava",
            psc=self.company.psc,
        )

        stats = self.run_dataset("tax_debtors", [self.debtor()])

        self.assertEqual(stats["ambiguous"], 1)
        self.assertEqual(stats["updated"], 0)
        self.company.refresh_from_db()
        druha.refresh_from_db()
        self.assertIsNone(self.company.tax_debt)
        self.assertIsNone(druha.tax_debt)

    def test_a_different_psc_is_not_a_match(self):
        """Názov sedí, adresa nie -- to nie je zhoda, to je iná firma."""
        stats = self.run_dataset("tax_debtors", [self.debtor(PSC="81102")])

        self.assertEqual(stats["unmatched"], 1)
        self.assertEqual(stats["updated"], 0)
        self.company.refresh_from_db()
        self.assertIsNone(self.company.tax_debt)

    def test_a_row_without_a_psc_is_refused(self):
        """Prázdna PSČ je bezpečnostné pravidlo, nie formalita.

        Z 68 057 produkčných zhôd stojí **0** na prázdnej PSČ, takže požiadavka
        na neprázdnu PSČ nič nestojí a odstráni celú triedu zhôd postavených na
        samotnom názve.
        """
        stats = self.run_dataset("tax_debtors", [self.debtor(PSC=None)])

        self.assertEqual(stats["unmatched"], 1)
        self.assertEqual(stats["updated"], 0)

    def test_an_empty_psc_element_is_not_reported_as_ambiguous(self):
        """`<PSC/>` je `None`, nie prázdny reťazec -- obe cesty musia viesť von."""
        stats = self.run_dataset("tax_debtors", [self.debtor(PSC="")])

        self.assertEqual(stats["unmatched"], 1)
        self.assertEqual(stats["ambiguous"], 0)

    def test_a_missing_row_never_clears_an_existing_debt(self):
        """Neúčasť v súbore nie je dôkaz o nulovom dlhu.

        Keby matcher na nezhode zapisoval `None`, vyčistil by dlh každej firme,
        ktorú práve nenašiel. Nikdy sa nezapisuje `None` -- len suma.
        """
        self.company.tax_debt = Decimal("500.00")
        self.company.save(update_fields=["tax_debt"])

        stats = self.run_dataset("tax_debtors", [self.debtor(PSC="81102")])

        self.assertEqual(stats["unmatched"], 1)
        self.company.refresh_from_db()
        self.assertEqual(self.company.tax_debt, Decimal("500.00"))

    def test_the_stranded_legacy_value_is_replaced_not_deleted(self):
        """Staré hodnoty z odstráneného fuzzy matchera sa majú **opraviť**.

        Merané 2026-09-28 na produkcii: z 33 541 starých hodnôt ich 25 843
        (77 %) dnešný súbor potvrdzuje, 3 787 je zastaraných a 3 911 sa nedá
        overiť. Sú to teda staré dáta, nie pokazené -- a tu sa zastaraná hodnota
        prepíše tou zo súboru.
        """
        self.company.tax_debt = Decimal("100.00")
        self.company.save(update_fields=["tax_debt"])

        self.run_dataset("tax_debtors", [self.debtor(CIASTKA="999,99")])

        self.company.refresh_from_db()
        self.assertEqual(self.company.tax_debt, Decimal("999.99"))

    def test_the_matcher_is_not_built_for_datasets_that_carry_an_ico(self):
        """Index nad 631 988 firmami sa pre štyri z piatich datasetov nestavia."""
        target = "registers.management.commands.update_fs_data.CompanyNameMatcher"
        with patch(target) as matcher:
            self.run_dataset("bank_accounts", [{"ICO": self.company.ico, "IBAN": "SK3112000000198742637541"}])

        matcher.build.assert_not_called()

    def test_the_matcher_is_built_once_even_for_many_rows(self):
        """Index je drahý; postaviť ho raz za dataset, nie raz za riadok."""
        target = "registers.management.commands.update_fs_data.CompanyNameMatcher"
        with patch(target) as matcher:
            matcher.build.return_value = matcher
            matcher.resolve.return_value = (None, "no_candidate")
            self.run_dataset("tax_debtors", [self.debtor(), self.debtor(), self.debtor()])

        matcher.build.assert_called_once()


class MissingIdentifierRobustnessTests(_FsCommandTestCase):
    """Tri spôsoby, akými sa riadok nepriradí -- každý musí byť vidieť zvlášť."""

    def setUp(self):
        super().setUp()
        self.company = Company.objects.create(
            ruz_id=3,
            ico="50059959",
            nazov_UJ="Exact Name s. r. o.",
            mesto="Bratislava",
            psc="81101",
        )

    def test_an_empty_ico_element_does_not_kill_the_import(self):
        """Regresia: `<ICO/>` má `child.text is None`, nie chýbajúci kľúč.

        Pôvodné `item.get('ICO', '').isdigit()` preto spadlo na
        `AttributeError` a zhodilo **celý denný import** skôr, než vypísalo
        čokoľvek -- teda tichý deň bez FS dát.
        """
        stats = self.run_dataset("bank_accounts", [{"ICO": None, "IBAN": "SK3112000000198742637541"}])

        self.assertEqual(stats["no_ico"], 1)
        self.assertEqual(stats["errors"], 0)

    def test_an_ico_padded_with_spaces_is_still_found(self):
        """IČO s medzerou sa má dohľadať, nie ticho zahodiť."""
        stats = self.run_dataset("bank_accounts", [{"ICO": " 50059959 ", "IBAN": "SK3112000000198742637541"}])

        self.assertEqual(stats["no_ico"], 0)
        self.assertEqual(stats["not_in_register"], 0)
        self.assertEqual(stats["updated"], 1)

    def test_an_unknown_ico_is_counted_apart_from_a_missing_one(self):
        """"Zdroj IČO nemá" a „my tú firmu nemáme" sú dve rôzne veci.

        Predtým obe padali do jedného `not_found`, takže sa z logu nedalo
        vyčítať, či je medzera v zdroji alebo v našom registri.
        """
        stats = self.run_dataset("bank_accounts", [{"ICO": "99999999", "IBAN": "SK3112000000198742637541"}])

        self.assertEqual(stats["not_in_register"], 1)
        self.assertEqual(stats["no_ico"], 0)

    # Presný podreťazec z hlášky v príkaze. Musí to byť naozaj to, čo príkaz
    # píše -- negatívny test nižšie hľadá ten istý reťazec, a keby nesedel,
    # `assertNotIn` by prešiel vždy a nemeral by nič.
    LOUD = "sa nepodarilo priradiť ani jednu firmu"

    def test_a_dataset_that_matches_nothing_is_loud(self):
        """Presne takto vyzerali daňoví dlžníci roky: 90 902 položiek, 0 zhôd,
        a v logu to bolo na nerozoznanie od normálneho dňa."""
        self.run_dataset("tax_debtors", [{"NAZOV_SUBJEKTU": "Nikto s. r. o.", "PSC": "99999", "CIASTKA": "1,00"}])

        self.assertSaid(self.LOUD)

    def test_a_dataset_that_matches_something_is_not_loud(self):
        """Kontrola, že tá hláška nie je vždy -- inak je to len šum.

        Pozitívna kontrola k testu vyššie: bez nej by `assertNotIn` prešiel aj
        vtedy, keby príkaz hlásil poruchu pri každom datasete.

        Samotné `assertNotIn` ale nedokáže rozlíšiť „ticho, lebo sa riadok
        priradil" od „ticho, lebo sa nespracoval vôbec" -- a to druhé je presne
        ten tichý deň, ktorý tu chceme chytiť. Preto aj kladné tvrdenie: účet
        sa na firme naozaj objavil.
        """
        stats = self.run_dataset("bank_accounts", [{"ICO": self.company.ico, "IBAN": "SK3112000000198742637541"}])

        self.assertNotIn(self.LOUD, self.allOutput())
        self.assertEqual(stats["updated"], 1)
        self.company.refresh_from_db()
        self.assertIn("SK3112000000198742637541", self.company.bank_accounts)


class TaxDebtAmountComparisonTests(_FsCommandTestCase):
    """`tax_debt` je `DecimalField`; `parse_money` vracia `float`.

    Python porovnáva `Decimal` s `float` presne, a žiadne desatinné číslo nie je
    v binárnej sústave presné -- `Decimal('2422.35') != 2422.35` je teda `True`.
    Handler preto hlásil zmenu pri každom opakovanom videní firmy. V dátach sa
    to nestratilo (stĺpec je `numeric(x,2)`), ale v logu áno: „updated" prestalo
    znamenať „zmenilo sa".
    """

    def setUp(self):
        super().setUp()
        self.company = Company.objects.create(
            ruz_id=4,
            ico="50059959",
            nazov_UJ="Debtor s. r. o.",
            mesto="Bratislava",
            psc="81101",
        )

    def test_the_same_amount_is_not_reported_as_a_change(self):
        self.company.tax_debt = Decimal("2422.35")
        self.company.save(update_fields=["tax_debt"])

        changed = self.handlers.handle_tax_debtors(self.company, {"CIASTKA": "2422,35"})

        self.assertFalse(changed, "rovnaká suma sa nesmie hlásiť ako zmena")

    def test_the_same_amount_written_differently_is_still_the_same_amount(self):
        """Zdroj píše „2 422,35 €"; stĺpec drží `Decimal('2422.35')`."""
        self.company.tax_debt = Decimal("2422.35")
        self.company.save(update_fields=["tax_debt"])

        changed = self.handlers.handle_tax_debtors(self.company, {"CIASTKA": "2 422,35 €"})

        self.assertFalse(changed)

    def test_a_changed_amount_is_reported(self):
        self.company.tax_debt = Decimal("2422.35")
        self.company.save(update_fields=["tax_debt"])

        changed = self.handlers.handle_tax_debtors(self.company, {"CIASTKA": "2668,41"})

        self.assertTrue(changed)
        self.assertEqual(self.company.tax_debt, Decimal("2668.41"))

    def test_the_value_written_to_the_column_is_a_two_place_decimal(self):
        """Stĺpec je `numeric(x,2)`; hodnota má mať dva miesta už pred zápisom,
        inak by sa porovnávala proti niečomu inému, než čo stĺpec drží."""
        self.handlers.handle_tax_debtors(self.company, {"CIASTKA": "2422,345"})

        self.assertEqual(self.company.tax_debt, Decimal("2422.35"))
        self.assertEqual(self.company.tax_debt.as_tuple().exponent, -2)

    def test_a_missing_amount_changes_nothing(self):
        self.company.tax_debt = Decimal("10.00")
        self.company.save(update_fields=["tax_debt"])

        self.assertFalse(self.handlers.handle_tax_debtors(self.company, {}))
        self.assertEqual(self.company.tax_debt, Decimal("10.00"))

    def test_an_unparseable_amount_raises_value_error_not_invalid_operation(self):
        """Volajúci má `except (ValueError, TypeError)`; `InvalidOperation` by
        mu prepadol až k `except Exception` a riadok by sa ticho preskočil."""
        with self.assertRaises(ValueError):
            parse_money_decimal("nie je suma")

    def test_a_good_amount_parses_without_a_float_round_trip(self):
        self.assertEqual(parse_money_decimal("1 200,50 €"), Decimal("1200.50"))
        self.assertEqual(parse_money_decimal("-350,00"), Decimal("-350.00"))


class VatRemovalIsHistoryNotStandingTests(TestCase):
    """`vat_deleted` is a **history** list; `vat_payers` is the **current state**.

    Measured on production 2026-09-17: of the 32 127 rows carrying a removal
    date, **384** have a registration date *later* than it -- the firm sits in
    both datasets at once -- and **379** of those had `vat_payer = False`, so
    the company page called it "Vymazaný z registra DPH" on no evidence but the
    order the datasets happen to be walked in (`vat_payers` first, so
    `vat_deleted` always won).
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=2,
            ico="35757442",
            nazov_UJ="Re-registered s. r. o.",
            datum_reg_dph=date(2024, 3, 1),
            vat_payer=True,
        )
        self.handlers = FSDataHandlers(
            stdout_write=lambda s: None,
            stderr_write=lambda s: None,
            style_success=lambda s: s,
            style_error=lambda s: s,
            style_warning=lambda s: s,
        )

    def _removal(self, dat_vymazu="05.05.2020", rok_porusenia="2019"):
        return self.handlers.handle_vat_deleted(
            self.company,
            {"DAT_VYMAZU": dat_vymazu, "ROK_PORUSENIA": rok_porusenia},
        )

    def test_registration_after_the_removal_does_not_clear_the_flag(self):
        self._removal()
        self.assertIs(self.company.vat_payer, True)

    def test_the_removal_is_still_recorded_on_a_superseded_row(self):
        """Not clearing the flag must not throw the history away."""
        self._removal()
        self.assertEqual(self.company.vat_deleted_date, date(2020, 5, 5))
        self.assertEqual(self.company.vat_deleted_reason, "Rok porušenia: 2019")

    def test_removal_after_the_registration_still_clears_the_flag(self):
        """The guard must not disable the handler's actual job."""
        self.company.datum_reg_dph = date(2018, 1, 1)
        self._removal()
        self.assertIs(self.company.vat_payer, False)

    def test_a_row_with_no_registration_date_still_clears_the_flag(self):
        """Nothing to compare against is not a reason to keep the flag."""
        self.company.datum_reg_dph = None
        self._removal()
        self.assertIs(self.company.vat_payer, False)

    def test_a_same_day_removal_keeps_the_previous_behaviour(self):
        """Two dates in one day cannot be ordered, so the old rule stands."""
        self.company.datum_reg_dph = date(2020, 5, 5)
        self._removal()
        self.assertIs(self.company.vat_payer, False)

    def test_an_unparseable_removal_date_still_clears_the_flag(self):
        self._removal(dat_vymazu="not a date")
        self.assertIs(self.company.vat_payer, False)
        self.assertIsNone(self.company.vat_deleted_date)

    @patch("registers.management.commands.update_fs_data.download_and_parse_fs_data")
    def test_one_pass_over_both_datasets_leaves_the_firm_a_payer(self, mock_download):
        """The defect itself: both datasets run, and the second one used to win.

        `bulk_update` is what makes this a real test rather than an in-memory
        one -- `vat_deleted` writes `vat_payer` for every row it touches, so
        the handler's decision is what lands in the column.
        """
        mock_download.side_effect = [
            [{"ICO": self.company.ico, "DATUM_REG": "01.03.2024", "IC_DPH": "SK1234567890"}],
            [{"ICO": self.company.ico, "DAT_VYMAZU": "05.05.2020", "ROK_PORUSENIA": "2019"}],
        ]
        command = Command()

        command._process_dataset(
            "vat_payers", "https://example.invalid/payers.zip", self.handlers, dry_run=False
        )
        command._process_dataset(
            "vat_deleted", "https://example.invalid/deleted.zip", self.handlers, dry_run=False
        )

        self.company.refresh_from_db()
        self.assertIs(self.company.vat_payer, True)
        self.assertEqual(self.company.datum_reg_dph, date(2024, 3, 1))
        self.assertEqual(self.company.vat_deleted_date, date(2020, 5, 5))
        self.assertEqual(self.company.vat_deleted_reason, "Rok porušenia: 2019")
