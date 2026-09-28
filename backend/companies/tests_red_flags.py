"""Risk indicators: every rule, every branch, and the wording they publish.

Two properties matter more than the arithmetic, and most of this file is about
them.

**A rule that did not run must not read as a rule that ran.** Each rule returns
`fired`, `clear` or `unassessed`, and the third is not a softer kind of the
second: `clear` means the data was there and the shape was not, `unassessed`
means the data was not there. 63,3 % of active companies carry no size band and
~96,5 % have no filed statement, so on most companies most rules land in the
third state -- and a section that rendered that as "nothing found" would be
claiming a look that never happened.

**The wording has no verdict in it.** A flag describes what the register holds
("evidovaná v 14 firmách, z toho 5 zrušených") and names no conclusion. The
methodology the feature came from is explicit that public data cannot prove a
carousel or identify a straw man, so the tests below check the sentences as
carefully as the numbers: a detail string that said "biely kôň" would be a
product making an accusation it cannot support.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from companies.models import Company
from companies.services import red_flags as rf
from companies.services.velkost import SIZE_UNKNOWN


class _Company:
    """A company as the pure rules see it: scalars, and nothing else.

    A stub rather than a saved row, for the reason `tests_risk_score` gives --
    a real `Company` would make every attribute available and hide which ones a
    rule actually depends on. The two rules that query the database are tested
    against real rows further down.
    """

    def __init__(
        self,
        size=None,
        tax_reliability=None,
        vat_deleted=None,
        vat_reason=None,
        vat_registered=None,
        dissolved=None,
        vszp=None,
        soc=None,
        tax_debt=None,
        ulica=None,
        mesto=None,
        psc=None,
    ):
        self.velkost_organizacie = size
        self.tax_reliability = tax_reliability
        self.vat_deleted_date = vat_deleted
        self.vat_deleted_reason = vat_reason
        self.datum_reg_dph = vat_registered
        self.datum_zrusenia = dissolved
        self.debt_vszp = vszp
        self.debt_soc_poist = soc
        self.tax_debt = tax_debt
        self.ulica = ulica
        self.mesto = mesto
        self.psc = psc


def row(year=2025, **kwargs):
    """One filed year, with only the lines a rule reads.

    Everything defaults to `None`, which is the register's own way of saying a
    line is absent -- so a test that forgets to set a figure gets the
    `unassessed` branch rather than a silent zero.
    """
    fields = {
        'year': year,
        'revenue': None,
        'profit_after_tax': None,
        'income_tax': None,
        'assets_total': None,
        'assets_tangible': None,
        'assets_inventory': None,
        'assets_receivables_short': None,
    }
    fields.update(kwargs)
    return SimpleNamespace(**fields)


def run(rule, company, rows):
    """One rule, called the way `company_red_flags` calls it."""
    ordered = sorted(rows, key=lambda r: r.year)
    return rule(company, ordered, ordered[-1] if ordered else None)


class FormattingTests(SimpleTestCase):
    """The sentences, because they are what a reader actually sees."""

    def test_amounts_are_grouped_and_cased_the_slovak_way(self):
        self.assertEqual(rf._eur(Decimal('1234567')), '1 234 567 €')
        self.assertEqual(rf._eur(Decimal('1234.50')), '1 234,50 €')

    def test_a_loss_keeps_its_sign_outside_the_grouping(self):
        # `f'{-1234:,}'` is `-1,234`, which put the minus inside the digits and
        # printed the cents as `-56`: `-1 234,-56 €`. A negative profit after
        # tax is ordinary in this data, so this is not a hypothetical branch.
        self.assertEqual(rf._eur(Decimal('-1234.56')), '-1 234,56 €')
        self.assertEqual(rf._eur(Decimal('-500')), '-500 €')

    def test_rounding_to_the_cent_cannot_print_a_hundredth_cent(self):
        self.assertEqual(rf._eur(Decimal('1234.999')), '1 235 €')

    def test_shares_print_with_a_comma(self):
        self.assertEqual(rf._percent(Decimal('0.1234')), '12,3 %')

    def test_decimals_in_a_sentence_are_not_written_with_a_point(self):
        # `quantize` keeps the point, so the first version of the turnover rule
        # printed "1825.0 dňa" and the growth rule "10.0×" -- arithmetic
        # notation inside Slovak prose, in the text a reader is looking at.
        self.assertEqual(rf._num(Decimal('1825')), '1 825,0')
        self.assertEqual(rf._num(Decimal('2')), '2,0')
        self.assertEqual(rf._num(Decimal('10.25')), '10,3')

    def test_no_rule_prints_a_measurement_with_a_decimal_point(self):
        # Belt as well as braces: the sentences, read as a whole, must not carry
        # an English decimal separator anywhere.
        cases = [
            (rf._flag_inventory_turnover, _Company(), [row(
                revenue=1_000_000, assets_total=10_000_000, assets_inventory=5_000_000,
            )]),
            (rf._flag_revenue_jump, _Company(), [
                row(year=2024, revenue=200_000), row(year=2025, revenue=2_000_000),
            ]),
        ]
        for rule, company, rows in cases:
            outcome = run(rule, company, rows)
            with self.subTest(rule=rule.__name__):
                self.assertNotRegex(outcome['detail'], r'\d\.\d')


class RevenueWithoutEmployeesTests(SimpleTestCase):
    RULE = staticmethod(rf._flag_revenue_without_employees)

    def test_an_unrecorded_size_band_is_not_a_company_with_no_employees(self):
        # The band is unknown on 63,3 % of active companies. Reading `00` as
        # "no employees" would fire this rule on most of the register.
        for size in (None, '', SIZE_UNKNOWN):
            with self.subTest(size=size):
                outcome = run(self.RULE, _Company(size=size), [row(revenue=5_000_000)])
                self.assertEqual(outcome['state'], 'unassessed')
                self.assertIn('veľkosť', outcome['reason'])

    def test_a_band_outside_the_catalogue_is_unassessed_not_clear(self):
        outcome = run(self.RULE, _Company(size='99'), [row(revenue=5_000_000)])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_no_statement_at_all_is_unassessed(self):
        outcome = run(self.RULE, _Company(size='01'), [])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_a_statement_without_the_revenue_line_is_unassessed(self):
        outcome = run(self.RULE, _Company(size='01'), [row()])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_a_company_with_employees_has_looked_and_found_nothing(self):
        outcome = run(self.RULE, _Company(size='05'), [row(revenue=5_000_000)])
        self.assertEqual(outcome['state'], 'clear')
        self.assertIn('5-9', outcome['detail'])

    def test_one_employee_and_small_revenue_is_clear(self):
        outcome = run(self.RULE, _Company(size='02'), [row(revenue=999_999)])
        self.assertEqual(outcome['state'], 'clear')

    def test_one_employee_and_millions_fires(self):
        outcome = run(self.RULE, _Company(size='02'), [row(revenue=3_200_000)])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('3 200 000 €', outcome['detail'])
        self.assertEqual(outcome['evidence']['size_band'], '02')


class RevenueJumpTests(SimpleTestCase):
    RULE = staticmethod(rf._flag_revenue_jump)

    def test_one_filed_year_has_nothing_to_compare(self):
        outcome = run(self.RULE, _Company(), [row(year=2025, revenue=9_000_000)])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_from_zero_to_millions_fires_without_dividing(self):
        # The ratio would be a division by zero, and the fact it expresses --
        # nothing, then millions -- is the one the methodology describes.
        outcome = run(self.RULE, _Company(), [
            row(year=2024, revenue=0), row(year=2025, revenue=5_000_000),
        ])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('z 0 € na 5 000 000 €', outcome['detail'])

    def test_from_zero_to_a_little_is_clear(self):
        outcome = run(self.RULE, _Company(), [
            row(year=2024, revenue=0), row(year=2025, revenue=400_000),
        ])
        self.assertEqual(outcome['state'], 'clear')

    def test_a_negative_year_is_unassessed_because_a_ratio_would_lie(self):
        outcome = run(self.RULE, _Company(), [
            row(year=2024, revenue=-1000), row(year=2025, revenue=5_000_000),
        ])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_ten_times_the_revenue_fires(self):
        outcome = run(self.RULE, _Company(), [
            row(year=2024, revenue=200_000), row(year=2025, revenue=2_000_000),
        ])
        self.assertEqual(outcome['state'], 'fired')
        self.assertEqual(outcome['evidence']['ratio'], '10.00')

    def test_a_large_multiple_below_the_million_floor_is_clear(self):
        outcome = run(self.RULE, _Company(), [
            row(year=2024, revenue=1_000), row(year=2025, revenue=900_000),
        ])
        self.assertEqual(outcome['state'], 'clear')

    def test_an_ordinary_growth_year_is_clear(self):
        outcome = run(self.RULE, _Company(), [
            row(year=2024, revenue=1_000_000), row(year=2025, revenue=3_000_000),
        ])
        self.assertEqual(outcome['state'], 'clear')

    def test_the_comparison_is_the_two_most_recent_years_with_revenue(self):
        # A gap year with no revenue line must not count as "zero", or every
        # company with an unfiled year would fire this rule.
        outcome = run(self.RULE, _Company(), [
            row(year=2022, revenue=100_000),
            row(year=2023),
            row(year=2024, revenue=5_000_000),
        ])
        self.assertEqual(outcome['state'], 'fired')
        self.assertEqual(outcome['evidence']['from_year'], 2022)


class TurnoverWithoutProfitTests(SimpleTestCase):
    RULE = staticmethod(rf._flag_turnover_without_profit)

    def test_no_statement_is_unassessed(self):
        self.assertEqual(run(self.RULE, _Company(), [])['state'], 'unassessed')

    def test_a_missing_profit_line_is_unassessed(self):
        outcome = run(self.RULE, _Company(), [row(revenue=5_000_000)])
        self.assertEqual(outcome['state'], 'unassessed')
        self.assertIn('zisk', outcome['reason'])

    def test_revenue_below_the_floor_is_clear(self):
        outcome = run(self.RULE, _Company(), [
            row(revenue=900_000, profit_after_tax=0),
        ])
        self.assertEqual(outcome['state'], 'clear')

    def test_millions_in_revenue_and_a_profit_of_nothing_fires(self):
        outcome = run(self.RULE, _Company(), [row(
            revenue=10_000_000, profit_after_tax=2_000, income_tax=380,
        )])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('10 000 000 €', outcome['detail'])
        self.assertIn('380 €', outcome['detail'])

    def test_a_real_margin_is_clear(self):
        outcome = run(self.RULE, _Company(), [
            row(revenue=10_000_000, profit_after_tax=900_000),
        ])
        self.assertEqual(outcome['state'], 'clear')

    def test_a_loss_is_within_the_near_zero_band_and_says_the_tax_is_missing(self):
        outcome = run(self.RULE, _Company(), [
            row(revenue=2_000_000, profit_after_tax=-5_000),
        ])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('daň z príjmu neuvedená', outcome['detail'])


class BalanceWithoutFixedAssetsTests(SimpleTestCase):
    RULE = staticmethod(rf._flag_balance_without_fixed_assets)

    def test_no_statement_is_unassessed(self):
        self.assertEqual(run(self.RULE, _Company(), [])['state'], 'unassessed')

    def test_missing_assets_is_unassessed(self):
        outcome = run(self.RULE, _Company(), [row(assets_tangible=0)])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_missing_inventory_is_unassessed(self):
        outcome = run(self.RULE, _Company(), [
            row(assets_total=5_000_000, assets_tangible=0),
        ])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_a_small_balance_sheet_is_clear_whatever_its_shape(self):
        outcome = run(self.RULE, _Company(), [row(
            assets_total=500_000, assets_tangible=0,
            assets_inventory=400_000, assets_receivables_short=100_000,
        )])
        self.assertEqual(outcome['state'], 'clear')

    def test_a_large_balance_sheet_of_receivables_fires(self):
        outcome = run(self.RULE, _Company(), [row(
            assets_total=10_000_000, assets_tangible=0,
            assets_inventory=3_000_000, assets_receivables_short=6_000_000,
        )])
        self.assertEqual(outcome['state'], 'fired')
        self.assertEqual(outcome['evidence']['working_capital'], '9000000')

    def test_a_company_with_equipment_is_clear(self):
        outcome = run(self.RULE, _Company(), [row(
            assets_total=10_000_000, assets_tangible=4_000_000,
            assets_inventory=3_000_000, assets_receivables_short=3_000_000,
        )])
        self.assertEqual(outcome['state'], 'clear')

    def test_zero_assets_cannot_be_divided_by(self):
        outcome = run(self.RULE, _Company(), [row(
            assets_total=0, assets_tangible=0,
            assets_inventory=0, assets_receivables_short=0,
        )])
        self.assertEqual(outcome['state'], 'clear')  # below the floor first

    def test_a_zero_asset_row_above_the_floor_is_unassessed(self):
        # Only reachable if the floor is ever lowered, but the branch exists and
        # so it is pinned: a share with a zero denominator is not a share.
        original = rf.BALANCE_MIN_ASSETS
        rf.BALANCE_MIN_ASSETS = Decimal('0')
        try:
            outcome = run(self.RULE, _Company(), [row(
                assets_total=0, assets_tangible=0,
                assets_inventory=0, assets_receivables_short=0,
            )])
        finally:
            rf.BALANCE_MIN_ASSETS = original
        self.assertEqual(outcome['state'], 'unassessed')


class InventoryTurnoverTests(SimpleTestCase):
    RULE = staticmethod(rf._flag_inventory_turnover)

    def test_no_statement_is_unassessed(self):
        self.assertEqual(run(self.RULE, _Company(), [])['state'], 'unassessed')

    def test_zero_inventory_is_clear_rather_than_an_infinite_turnover(self):
        outcome = run(self.RULE, _Company(), [row(
            revenue=5_000_000, assets_total=5_000_000, assets_inventory=0,
        )])
        self.assertEqual(outcome['state'], 'clear')

    def test_a_token_stock_is_not_measured(self):
        # 0,5 % of assets: the ratio would be enormous and mean nothing, which
        # is why materiality is a guard and not a footnote.
        outcome = run(self.RULE, _Company(), [row(
            revenue=5_000_000, assets_total=10_000_000, assets_inventory=50_000,
        )])
        self.assertEqual(outcome['state'], 'clear')
        self.assertIn('nemateriálne', outcome['detail'])

    def test_stock_that_turns_over_in_days_fires(self):
        # The stock has to be material as well as fast, so the inventory here
        # is a fifth of the balance sheet -- an immaterial one is guarded
        # against above, and would hide the fast turnover in the wrong branch.
        outcome = run(self.RULE, _Company(), [row(
            revenue=36_500_000, assets_total=1_000_000, assets_inventory=200_000,
        )])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('2,0 dňa', outcome['detail'])

    def test_a_slow_moving_stock_is_clear(self):
        outcome = run(self.RULE, _Company(), [row(
            revenue=1_000_000, assets_total=10_000_000, assets_inventory=5_000_000,
        )])
        self.assertEqual(outcome['state'], 'clear')
        self.assertIn('1 825,0 dňa', outcome['detail'])


class UnreliableTaxIndexTests(SimpleTestCase):
    RULE = staticmethod(rf._flag_unreliable_tax_index)

    def test_no_index_is_unassessed_not_reliable(self):
        # 218 143 rows carry no index. That is the Financial Directorate having
        # rated nobody, which is not a rating.
        for value in (None, '', '   '):
            with self.subTest(value=value):
                outcome = run(self.RULE, _Company(tax_reliability=value), [])
                self.assertEqual(outcome['state'], 'unassessed')

    def test_the_registers_own_word_fires(self):
        outcome = run(self.RULE, _Company(tax_reliability='nespoľahlivý'), [])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('nespoľahlivý', outcome['detail'])

    def test_any_other_rating_is_clear_and_quotes_itself(self):
        outcome = run(self.RULE, _Company(tax_reliability='spoľahlivý'), [])
        self.assertEqual(outcome['state'], 'clear')
        self.assertIn('spoľahlivý', outcome['detail'])

    def test_surrounding_space_does_not_hide_the_rating(self):
        outcome = run(self.RULE, _Company(tax_reliability='  nespoľahlivý '), [])
        self.assertEqual(outcome['state'], 'fired')


class VatDeregisteredTests(SimpleTestCase):
    RULE = staticmethod(rf._flag_vat_deregistered)

    def test_no_removal_date_is_unassessed(self):
        outcome = run(self.RULE, _Company(), [])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_struck_off_and_not_re_registered_fires(self):
        outcome = run(self.RULE, _Company(vat_deleted=date(2024, 5, 1)), [])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('2024-05-01', outcome['detail'])

    def test_the_reason_is_reported_when_the_register_gives_one(self):
        outcome = run(self.RULE, _Company(
            vat_deleted=date(2024, 5, 1), vat_reason='Rok porušenia: 2023',
        ), [])
        self.assertIn('Rok porušenia: 2023', outcome['detail'])

    def test_struck_off_and_later_re_registered_is_clear(self):
        # 384 of the 32 127 rows carrying a removal date were re-registered
        # after it. Comparing the dates is what keeps this flag from calling a
        # current VAT payer deregistered -- the same rule the frontend chip
        # applies in `vatStatus.ts`.
        outcome = run(self.RULE, _Company(
            vat_deleted=date(2022, 1, 1), vat_registered=date(2024, 1, 1),
        ), [])
        self.assertEqual(outcome['state'], 'clear')
        self.assertIn('znovu zaregistrovaný', outcome['detail'])

    def test_a_registration_before_the_removal_still_fires(self):
        outcome = run(self.RULE, _Company(
            vat_deleted=date(2024, 1, 1), vat_registered=date(2015, 1, 1),
        ), [])
        self.assertEqual(outcome['state'], 'fired')

    def test_re_registered_on_the_same_day_is_not_a_re_registration(self):
        outcome = run(self.RULE, _Company(
            vat_deleted=date(2024, 1, 1), vat_registered=date(2024, 1, 1),
        ), [])
        self.assertEqual(outcome['state'], 'fired')


class DebtAndDissolutionTests(SimpleTestCase):
    RULE = staticmethod(rf._flag_debt_and_dissolution)

    def test_a_running_company_is_clear_even_with_debt(self):
        outcome = run(self.RULE, _Company(vszp=50_000), [])
        self.assertEqual(outcome['state'], 'clear')
        self.assertIn('50 000 €', outcome['detail'])

    def test_a_dissolved_company_without_debt_is_clear(self):
        outcome = run(self.RULE, _Company(dissolved=date(2020, 1, 1)), [])
        self.assertEqual(outcome['state'], 'clear')

    def test_both_halves_together_fire(self):
        outcome = run(self.RULE, _Company(
            dissolved=date(2020, 1, 1), vszp=1_000, soc=2_000, tax_debt=3_000,
        ), [])
        self.assertEqual(outcome['state'], 'fired')
        self.assertEqual(outcome['evidence']['total_debt'], '6000')

    def test_the_three_debts_are_read_the_same_way_the_score_reads_them(self):
        from companies.services.risk_score import total_debt

        company = _Company(dissolved=date(2020, 1, 1), vszp=1_000, soc=2_000, tax_debt=3_000)
        self.assertEqual(total_debt(company), Decimal(6000))


class AddressKeyTests(SimpleTestCase):
    """Folding the register's spelling into one key per building."""

    def test_a_seat_without_a_street_cannot_be_keyed(self):
        for ulica in (None, '', '   '):
            with self.subTest(ulica=ulica):
                company = _Company(ulica=ulica, mesto='Bratislava', psc='81101')
                self.assertIsNone(rf.address_key(company))

    def test_a_seat_without_a_postal_code_or_municipality_cannot_be_keyed(self):
        self.assertIsNone(rf.address_key(_Company(ulica='Hlavná 1', mesto='', psc='81101')))
        self.assertIsNone(rf.address_key(_Company(ulica='Hlavná 1', mesto='Bratislava', psc='')))

    def test_the_same_building_written_differently_is_one_key(self):
        spellings = [
            'Hlavná 1', 'Hlavná ulica 1', 'HLAVNÁ 1', 'Hlavná  1',
        ]
        keys = {
            rf.address_key(_Company(ulica=value, mesto='Bratislava', psc='811 01'))
            for value in spellings
        }
        self.assertEqual(len(keys), 1, f'folded to {keys}')

    def test_the_house_number_is_part_of_the_key(self):
        first = rf.address_key(_Company(ulica='Hlavná 1', mesto='Bratislava', psc='81101'))
        second = rf.address_key(_Company(ulica='Hlavná 2', mesto='Bratislava', psc='81101'))
        self.assertNotEqual(first, second)

    def test_the_postal_code_is_folded_too(self):
        spaced = rf.address_key(_Company(ulica='Hlavná 1', mesto='Bratislava', psc='811 01'))
        joined = rf.address_key(_Company(ulica='Hlavná 1', mesto='Bratislava', psc='81101'))
        self.assertEqual(spaced, joined)

    def test_a_rural_seat_is_a_building_not_a_refusal(self):
        # The register writes the number where the street would go, for
        # 973 318 of its rows, so an empty street name is a village house.
        key = rf.address_key(_Company(ulica='52', mesto='Krajné', psc='91616'))
        self.assertIsNotNone(key)
        self.assertEqual(key[2], '')


class SerialDirectorTests(TestCase):
    """The one company rule that reads the person graph."""

    def setUp(self):
        from connections.models import Person, PersonCompanyRelation

        self.Person = Person
        self.Relation = PersonCompanyRelation
        self.company = Company.objects.create(
            ruz_id=910001, ico='91000001', nazov_UJ='Test s. r. o.',
        )

    def _person(self, name, fingerprint):
        return self.Person.objects.create(name=name, fingerprint=fingerprint)

    def _link(self, person, company, role='konatel'):
        return self.Relation.objects.create(person=person, company=company, role=role)

    def _company(self, ico, index):
        return Company.objects.create(
            ruz_id=920000 + index, ico=ico, nazov_UJ=f'Firma {index} s. r. o.',
        )

    def test_a_company_with_no_person_graph_is_unassessed(self):
        outcome = run(rf._flag_serial_director, self.company, [])
        self.assertEqual(outcome['state'], 'unassessed')
        self.assertIn('osobou', outcome['reason'])

    def test_an_ordinary_director_is_clear(self):
        person = self._person('Ján Príklad', 'name:jan priklad|addr:')
        self._link(person, self.company)
        for index in range(2):
            self._link(person, self._company(f'9300000{index}', index))
        outcome = run(rf._flag_serial_director, self.company, [])
        self.assertEqual(outcome['state'], 'clear')
        self.assertEqual(outcome['evidence']['max_companies_per_person'], 3)

    def test_functions_across_many_companies_fires_and_counts_roles(self):
        person = self._person('Ján Príklad', 'name:jan priklad|addr:')
        self._link(person, self.company, role='konatel')
        for index in range(4):
            self._link(person, self._company(f'9400000{index}', index), role='spolocnik')
        outcome = run(rf._flag_serial_director, self.company, [])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('5 firmách', outcome['detail'])
        self.assertEqual(outcome['evidence']['max_companies_per_person'], 5)
        self.assertIn('Ján Príklad', outcome['detail'])

    def test_two_functions_in_one_company_are_one_company(self):
        person = self._person('Ján Príklad', 'name:jan priklad|addr:')
        self._link(person, self.company, role='konatel')
        self._link(person, self.company, role='spolocnik')
        outcome = run(rf._flag_serial_director, self.company, [])
        self.assertEqual(outcome['evidence']['max_companies_per_person'], 1)

    def test_the_wording_names_no_offence(self):
        person = self._person('Ján Príklad', 'name:jan priklad|addr:')
        self._link(person, self.company)
        for index in range(4):
            self._link(person, self._company(f'9500000{index}', index))
        detail = run(rf._flag_serial_director, self.company, [])['detail'].lower()
        for accusation in ('biely', 'kôň', 'podvod', 'karusel', 'falš'):
            self.assertNotIn(accusation, detail)


class CrowdedAddressTests(TestCase):
    """The rule whose counting depends on the fold, so the fold is what is tested."""

    def _company(self, ico, ulica, mesto='Bratislava', psc='81101', ruz_id=None):
        return Company.objects.create(
            ruz_id=ruz_id or int(ico), ico=ico, nazov_UJ=f'Firma {ico}',
            ulica=ulica, mesto=mesto, psc=psc,
        )

    def test_a_seat_with_no_address_is_unassessed(self):
        outcome = run(rf._flag_crowded_address, self._company('96000001', ''), [])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_a_quiet_building_is_clear(self):
        subject = self._company('96000002', 'Hlavná 1')
        for index in range(3):
            self._company(f'9600010{index}', 'Hlavná 1')
        outcome = run(rf._flag_crowded_address, subject, [])
        self.assertEqual(outcome['state'], 'clear')
        self.assertEqual(outcome['evidence']['matching_companies'], 4)

    def test_a_crowded_building_fires_counting_every_spelling(self):
        # The point of the fold: without it these rows are four different
        # addresses and the count never reaches the threshold.
        subject = self._company('96000003', 'Hlavná 1')
        for index, spelling in enumerate(('Hlavná ulica 1', 'HLAVNÁ 1', 'Hlavná  1')):
            self._company(f'9600020{index}', spelling)
        for index in range(16):
            self._company(f'960010{index:02d}', 'Hlavná 1')
        outcome = run(rf._flag_crowded_address, subject, [])
        self.assertEqual(outcome['state'], 'fired')
        self.assertEqual(outcome['evidence']['matching_companies'], 20)

    def test_the_same_street_at_another_number_is_a_different_building(self):
        subject = self._company('96000004', 'Hlavná 1')
        for index in range(30):
            self._company(f'960020{index:02d}', 'Hlavná 2')
        outcome = run(rf._flag_crowded_address, subject, [])
        self.assertEqual(outcome['state'], 'clear')
        self.assertEqual(outcome['evidence']['matching_companies'], 1)

    def test_another_postal_code_is_another_building(self):
        subject = self._company('96000005', 'Hlavná 1', psc='81101')
        for index in range(3):
            self._company(f'960030{index:02d}', 'Hlavná 1', psc='82101')
        outcome = run(rf._flag_crowded_address, subject, [])
        self.assertEqual(outcome['evidence']['matching_companies'], 1)

    def test_a_spaced_postal_code_still_finds_its_neighbours(self):
        subject = self._company('96000006', 'Hlavná 1', psc='811 01')
        for index in range(3):
            self._company(f'960040{index:02d}', 'Hlavná 1', psc='81101')
        outcome = run(rf._flag_crowded_address, subject, [])
        self.assertEqual(outcome['evidence']['matching_companies'], 4)

    def test_the_wording_admits_the_count_is_of_companies_not_of_schemes(self):
        subject = self._company('96000007', 'Hlavná 1')
        for index in range(19):
            self._company(f'960050{index:02d}', 'Hlavná 1')
        detail = run(rf._flag_crowded_address, subject, [])['detail']
        self.assertIn('20 firiem', detail)
        for accusation in ('podvod', 'karusel', 'biely', 'schránk'):
            self.assertNotIn(accusation, detail.lower())


class PayloadShapeTests(TestCase):
    """The contract the frontend renders, pinned key by key."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=970001, ico='97000001', nazov_UJ='Test s. r. o.',
            ulica='Hlavná 1', mesto='Bratislava', psc='81101',
            velkost_organizacie='01', tax_reliability='nespoľahlivý',
        )

    def test_every_company_rule_is_reported_once(self):
        payload = rf.company_red_flags(self.company)
        codes = [flag['code'] for flag in payload['flags']]
        self.assertEqual(len(codes), len(rf.COMPANY_RULES))
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(payload['counts']['fired'], 1)  # only the tax index fired

    def test_the_counts_account_for_every_rule(self):
        payload = rf.company_red_flags(self.company)
        counted = sum(payload['counts'].values())
        self.assertEqual(counted, len(rf.COMPANY_RULES))

    def test_every_flag_carries_the_same_keys(self):
        # Spelled out rather than asserted non-empty, so that a new key has to
        # be a deliberate edit here -- this is the payload the page renders.
        expected = sorted(
            ['code', 'label', 'severity', 'state', 'detail', 'reason', 'evidence']
        )
        for flag in rf.company_red_flags(self.company)['flags']:
            with self.subTest(code=flag['code']):
                self.assertEqual(sorted(flag), expected)

    def test_a_state_carries_its_own_kind_of_explanation(self):
        for flag in rf.company_red_flags(self.company)['flags']:
            with self.subTest(code=flag['code']):
                if flag['state'] == 'unassessed':
                    self.assertIsNone(flag['detail'])
                    self.assertTrue(flag['reason'])
                else:
                    self.assertIsNone(flag['reason'])
                    self.assertTrue(flag['detail'])

    def test_coverage_qualifies_the_verdict(self):
        payload = rf.company_red_flags(self.company)
        self.assertEqual(payload['coverage']['financial_years'], 0)
        self.assertFalse(payload['coverage']['has_financials'])
        self.assertEqual(payload['coverage']['persons_linked'], 0)
        self.assertTrue(payload['coverage']['size_band_known'])
        self.assertFalse(payload['coverage']['vat_register_dated'])

    def test_rows_may_be_passed_in_and_are_ordered_by_the_callee(self):
        from companies.models import CompanyFinancialResult

        for year in (2025, 2023, 2024):
            CompanyFinancialResult.objects.create(
                company=self.company, year=year, revenue=5_000_000,
                profit_after_tax=1_000, assets_total=9_000_000,
                assets_tangible=0, assets_inventory=3_000_000,
                assets_receivables_short=5_000_000,
            )
        passed = rf.company_red_flags(
            self.company, list(self.company.financial_results.all())
        )
        fetched = rf.company_red_flags(self.company)
        self.assertEqual(
            [f['state'] for f in passed['flags']],
            [f['state'] for f in fetched['flags']],
        )
        self.assertEqual(passed['coverage']['financial_years'], 3)


class CompanyDetailPublishesRedFlagsTests(TestCase):
    """The endpoint contract, tested through the serializer.

    Every test above would still pass with `redFlags` wired to nothing, so what
    is pinned here is that the response a page renders actually carries the
    payload -- and that it carries it *beside* `riskScore` rather than inside
    it, which is the §11.22.3 decision in one assertion.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=980001, ico='98000001', nazov_UJ='Test s. r. o.',
            velkost_organizacie='01', tax_reliability='nespoľahlivý',
        )

    def test_the_detail_response_carries_red_flags(self):
        from companies.serializers import CompanyDetailSerializer

        data = CompanyDetailSerializer(self.company).data
        payload = data['redFlags']
        self.assertEqual(len(payload['flags']), len(rf.COMPANY_RULES))
        self.assertEqual(sum(payload['counts'].values()), len(rf.COMPANY_RULES))
        self.assertIn('coverage', payload)

    def test_the_flags_are_not_folded_into_the_score(self):
        # The score is one number on an attention ladder; the flags are a dozen
        # separate observations. A future change that merged them would move
        # every score in the product at once, so the two fields are asserted to
        # be different shapes rather than merely both present.
        from companies.serializers import CompanyDetailSerializer

        data = CompanyDetailSerializer(self.company).data
        self.assertIsInstance(data['riskScore']['score'], int)
        self.assertIsInstance(data['redFlags']['flags'], list)
        self.assertNotIn('flags', data['riskScore'])

    def test_the_statement_rows_are_read_once_for_both_fields(self):
        # Both method fields walk the same rows, and DRF calls them
        # independently -- without the cache this is two queries per request.
        from companies.models import CompanyFinancialResult
        from companies.serializers import CompanyDetailSerializer

        for year in (2023, 2024, 2025):
            CompanyFinancialResult.objects.create(
                company=self.company, year=year, revenue=5_000_000,
                profit_after_tax=1_000, assets_total=9_000_000,
                assets_tangible=0, assets_inventory=3_000_000,
                assets_receivables_short=5_000_000,
            )
        serializer = CompanyDetailSerializer(self.company)
        with self.assertNumQueries(1):
            first = serializer._financial_rows(self.company)
            second = serializer._financial_rows(self.company)
        self.assertIs(first, second)
        self.assertEqual(len(second), 3)
