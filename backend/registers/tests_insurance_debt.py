from unittest.mock import Mock

from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from registers.scrapers.debt_result import DebtCheckState
from registers.scrapers.soc_poist_debt import _header_label, check_socpoist_debt
from registers.scrapers.vszp_debt import check_vszp_debt_get

# Trimmed copies of the two responses the live site actually returns, so the
# parser is pinned to the real markup rather than to an idea of it.
VSZP_NO_RECORD_PAGE = """
<html><body>
<form><input type="hidden" name="nazov" value="31700764"/></form>
<table class="table table-striped tabulkaStandard">
    <thead>
        <tr>
            <th>Obchodné meno</th><th>Obec</th><th>Ulica</th><th>PSČ</th>
            <th>Pohľadávka</th><th>Typ platiteľa</th><th>Rozsah</th>
        </tr>
    </thead>
    </tbody>
        </tbody>
    </table>
Nenašli sa žiadne záznamy.
</body></html>
"""

# Note what this response does *not* contain: any "€". The claim column is a
# bare number, right-aligned.
VSZP_DEBTOR_ROW_PAGE = """
<html><body>
<table class="table table-striped tabulkaStandard">
    <thead>
        <tr>
            <th>Obchodné meno</th><th>Obec</th><th>Ulica</th><th>PSČ</th>
            <th>Pohľadávka</th><th>Typ platiteľa</th><th>Rozsah</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>A - TEAM SECURITY, A.S.<br />IČO: 34136088</td>
            <td>BRATISLAVA-RUŽINOV</td>
            <td>MILETIČOVA 23</td>
            <td>82109</td>
            <td style="text-align: right;">6 641,86</td>
            <td>Zamestnávateľ</td>
            <td style="text-align: center;"> </td>
        </tr>
    </tbody>
</table>
</body></html>
"""

# The "no records" sentence, but only where no reader can see it: a JS string, an
# HTML comment and a <template>. The live site does not do this -- measured
# 2026-09-15, the sentence appears exactly once per page and as rendered prose --
# and that is precisely the hazard: a raw `response.text` substring search cannot
# tell the difference, so the day VSZP moves that sentence into the script that
# renders it, every unparsed page silently becomes a confident zero.
VSZP_MARKER_ONLY_IN_HIDDEN_PLACES = """
<html><body>
<script>var noResults = "Nenašli sa žiadne záznamy";</script>
<!-- Nenašli sa žiadne záznamy -->
<template><span>Nenašli sa žiadne záznamy</span></template>
<table class="table table-striped tabulkaStandard">
    <thead>
        <tr><th>Obchodné meno</th><th>Pohľadávka</th></tr>
    </thead>
    <tbody></tbody>
</table>
</body></html>
"""

# Both Socialna poistovna responses render the same `view-id-debitors`
# container -- that is the anchor. What separates them is the result count:
# only the response that has a debtor carries it. The page for a company that
# owes nothing states that by *omitting* the line, not by publishing a
# message, which is why looking for a "no records" sentence found nothing.
SP_GLOSSARY = """
      <ul class="links links--glossary">
        <li><a href="?glossary=%2A" class="govuk-link">INÉ</a></li>
        <li><a href="?glossary=a" class="govuk-link">A</a></li>
      </ul>"""

# The result table's header, column for column and in the order the view renders
# it. `period__value` carries the double underscore the live page uses.
_SP_COLUMNS = (
    ("Názov / Meno", "name", True),
    ("IČO", "ico", False),
    ("Adresa", "address", True),
    ("Mesto", "city", True),
    ("Dlžná suma", "price", True),
    ("Chýbajúce podklady za obdobie", "period__value", False),
)

# The price column really does carry `views-align-right` twice on the live page.
_SP_TH_CLASSES = {
    "name": "views-field views-field-name",
    "ico": "views-field views-field-ico",
    "address": "views-field views-field-address",
    "city": "views-field views-field-city",
    "price": "views-align-right views-field views-field-price views-align-right",
    "period__value": "views-field views-field-period__value",
}


def _sp_thead(column: str) -> str:
    """The result table's `<thead>`, as the view actually renders it.

    The sort control is the part that matters. Every *sortable* column nests an
    `<a>` whose screen-reader span reads `zoradiť podľa <column>`, so the cell's
    plain text comes out as

        "Dlžná suma zoradiť podľa Dlžná suma"

    -- a string equal to no column name at all. Verbatim from the live register,
    measured 2026-09-15, where the amount column renders as

        <th class="views-align-right views-field views-field-price views-align-right"
            id="view-price-table-column--2" scope="col"><span class="th-span">
          Dlžná suma
          <a class="arrowBtn" href="?order=price&amp;sort=asc" rel="nofollow"
             title="zoradiť podľa Dlžná suma"><span class="sr-only">zoradiť podľa
            Dlžná suma</span></a></span></th>

    IČO and `Chýbajúce podklady za obdobie` are not sortable and carry no anchor.

    Written out here rather than trimmed into each fixture by hand because these
    fixtures once carried `<th>Dlžná suma</th>` -- what the column *means* rather
    than what the page *emits*. Twenty tests passed against that while the live
    page matched nothing the parser looked for, so every check in the register
    would have come back `unknown`: the money path as well as the hyphen one.
    """
    cells = []
    for label, field, sortable in _SP_COLUMNS:
        anchor = ""
        if sortable:
            anchor = (
                f' <a class="arrowBtn" href="?order={field}&amp;sort=asc"'
                f' rel="nofollow" title="zoradiť podľa {label}">'
                f'<span class="sr-only">zoradiť podľa {label}</span></a>'
            )
        cells.append(
            f'<th class="{_SP_TH_CLASSES[field]}"'
            f' id="view-{field}-table-column--{column}" scope="col">'
            f'<span class="th-span">{label}{anchor}</span></th>'
        )
    return "\n          ".join(cells)

SP_NO_RECORD_PAGE = f"""
<html><body>
<div class="govuk-grid-column-full">
  <div class="view view-debitors view-id-debitors view-display-id-embed js-view-dom-id-439025d5">
    <div class="view-header">
      {SP_GLOSSARY}
    </div>
  </div>
</div>
</body></html>
"""

SP_DEBTOR_ROW_PAGE = f"""
<html><body>
<div class="govuk-grid-column-full">
  <div class="view view-debitors view-id-debitors view-display-id-embed js-view-dom-id-8f53fabc">
    <div class="view-header">
      Dlžníci podľa zadaných kritérií: <strong>1</strong>
      {SP_GLOSSARY}
    </div>
    <table class="cols-6">
      <thead>
        <tr>
          {_sp_thead("2")}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="views-field views-field-name" headers="view-name-table-column--2">MMBOXX, s.r.o.</td>
          <td class="views-field views-field-ico" headers="view-ico-table-column--2">36439151</td>
          <td class="views-field views-field-address" headers="view-address-table-column--2">Družstevná 4,</td>
          <td class="views-field views-field-city" headers="view-city-table-column--2">Liptovský Mikuláš</td>
          <td class="views-field views-field-price views-align-right" headers="view-price-table-column--2">731,46 €</td>
          <td class="views-field views-field-period__value" headers="view-period-value-table-column--2"><p>-</p></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
</body></html>
"""


# The second population the registry carries. SP publishes employers that did
# not submit their výkaz, and foreign SZČO that did not report income, in the
# same table as its debtors -- with a bare hyphen where the sum would be and
# the missing periods in the next column instead (measured 2026-09-15: the two
# columns are complementary, money with "-" in 43 of 50 rows and "-" with
# periods in 5). So the hyphen means "listed for a reporting breach", not
# "owes an amount we could not read".
SP_LISTED_WITHOUT_AMOUNT_PAGE = f"""
<html><body>
<div class="govuk-grid-column-full">
  <div class="view view-debitors view-id-debitors view-display-id-embed js-view-dom-id-a1b2c3d4">
    <div class="view-header">
      Dlžníci podľa zadaných kritérií: <strong>1</strong>
      {SP_GLOSSARY}
    </div>
    <table class="cols-6">
      <thead>
        <tr>
          {_sp_thead("3")}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="views-field views-field-name" headers="view-name-table-column--3">STAVBY - SERVIS, s.r.o.</td>
          <td class="views-field views-field-ico" headers="view-ico-table-column--3">36269727</td>
          <td class="views-field views-field-address" headers="view-address-table-column--3">Priemyselná 8,</td>
          <td class="views-field views-field-city" headers="view-city-table-column--3">Zvolen</td>
          <td class="views-field views-field-price views-align-right" headers="view-price-table-column--3"><p>-</p></td>
          <td class="views-field views-field-period__value" headers="view-period-value-table-column--3"><p>01/2026 - 03/2026</p></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
</body></html>
"""

# The same hyphen-first row with the header labels stripped, so the table can
# no longer say which column is the amount. Reading the mark from "whichever
# cell is empty" would answer `listed_no_amount` here; the header lookup leaves
# it unknown instead, which is the safe direction -- a re-queue, not a claim.
SP_LISTED_WITHOUT_AMOUNT_NO_HEADER_PAGE = (
    SP_LISTED_WITHOUT_AMOUNT_PAGE.replace("Dlžná suma", "Suma")
    .replace("Chýbajúce podklady za obdobie", "Obdobie")
)


class InsuranceDebtScraperTests(SimpleTestCase):
    def test_vszp_missing_result_row_is_unknown_not_zero(self):
        session = Mock()
        session.get.return_value = Mock(
            text="<html><body><p>Unexpected page structure</p></body></html>",
        )

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("12345678")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)
        self.assertEqual(result.error_type, "parse_error")

    def test_vszp_explicit_no_record_is_authoritative_zero(self):
        """The site's own "no records" message is the absence signal.

        Without this branch every company that is not a VSZP debtor reads as
        `unknown`, which tasks.update_insurance_debt refuses to count as a
        completed check -- so last_insurance_debt never advances and the whole
        table is re-queued forever.
        """
        session = Mock()
        session.get.return_value = Mock(text=VSZP_NO_RECORD_PAGE)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("31700764")

        self.assertEqual(result.state, DebtCheckState.NOT_FOUND)
        self.assertEqual(result.amount, 0.0)
        self.assertTrue(result.is_authoritative)

    def test_vszp_debtor_row_is_found_without_a_currency_symbol(self):
        """The claim column carries no "€", so is_money() cannot gate it."""
        session = Mock()
        session.get.return_value = Mock(text=VSZP_DEBTOR_ROW_PAGE)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("34136088")

        self.assertEqual(result.state, DebtCheckState.FOUND)
        self.assertAlmostEqual(result.amount, 6641.86, places=2)

    def test_vszp_row_for_another_ico_is_not_matched(self):
        """A bare substring match would confuse IČO 3413608 with 34136088."""
        session = Mock()
        session.get.return_value = Mock(text=VSZP_DEBTOR_ROW_PAGE)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("3413608")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)

    def test_vszp_unparseable_amount_is_unknown_not_zero(self):
        """A row we cannot read is not a row that says "no debt"."""
        page = VSZP_DEBTOR_ROW_PAGE.replace("6 641,86", "neuvedené")
        session = Mock()
        session.get.return_value = Mock(text=page)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("34136088")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)
        self.assertEqual(result.error_type, "parse_error")

    def test_vszp_no_record_sentence_inside_a_template_is_not_an_absence(self):
        """The regression test for reading absence out of the raw HTML.

        The sentence is present three times in this response, and a reader sees
        it zero times. Answering `not_found` here would write a zero for a
        company on the strength of a string in a template -- the one mistake the
        insurance pipeline must never make, because a zero is a published fact
        about somebody's debts.
        """
        session = Mock()
        session.get.return_value = Mock(text=VSZP_MARKER_ONLY_IN_HIDDEN_PLACES)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("12345678")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)
        self.assertEqual(result.error_type, "parse_error")

    def test_vszp_hidden_marker_does_not_overrule_a_listed_debtor(self):
        """A listed row outranks any absence signal, hidden or not."""
        page = VSZP_DEBTOR_ROW_PAGE.replace(
            "<html><body>",
            '<html><body><template><span>Nenašli sa žiadne záznamy</span></template>',
        )
        session = Mock()
        session.get.return_value = Mock(text=page)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("34136088")

        self.assertEqual(result.state, DebtCheckState.FOUND)
        self.assertAlmostEqual(result.amount, 6641.86, places=2)

    def test_vszp_rendered_marker_beside_an_unattributed_row_is_unknown(self):
        """The two signals contradict each other, so neither is trusted.

        The table lists somebody -- but not the company that was asked about --
        while the page also states there are no records. Picking either one would
        be inventing an answer.
        """
        page = VSZP_DEBTOR_ROW_PAGE.replace(
            "</body>", "<p>Nenašli sa žiadne záznamy.</p></body>"
        )
        session = Mock()
        session.get.return_value = Mock(text=page)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("99999999")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)

    def test_vszp_marker_typeset_with_a_non_breaking_space_still_counts(self):
        """The page typesets its prose with non-breaking spaces.

        "§ 25\\xa0ods.1" is how VSZP writes it, so the absence sentence has to
        match whichever space character the page used, or a genuine "no records"
        page reads as unparseable and the company is re-queued for ever.
        """
        page = VSZP_NO_RECORD_PAGE.replace(
            "Nenašli sa žiadne záznamy", "Nenašli sa\xa0žiadne záznamy"
        )
        session = Mock()
        session.get.return_value = Mock(text=page)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("31700764")

        self.assertEqual(result.state, DebtCheckState.NOT_FOUND)
        self.assertEqual(result.amount, 0.0)
        self.assertTrue(result.is_authoritative)

    def test_social_explicit_no_record_is_authoritative_zero(self):
        session = Mock()
        session.get.return_value = Mock(
            text="<html><body>Zadaným kritériám nevyhovuje žiaden záznam</body></html>",
        )

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("12345678")

        self.assertEqual(result.state, DebtCheckState.NOT_FOUND)
        self.assertEqual(result.amount, 0.0)

    def test_social_absent_result_count_is_an_authoritative_zero(self):
        """SP answers "no record" by leaving the result count out entirely.

        Without this branch the scraper found every debtor and misread every
        non-debtor as `unknown` -- so roughly two thirds of the table could
        never be marked checked, and the insurance queue refilled itself for
        ever while looking perfectly healthy.
        """
        session = Mock()
        session.get.return_value = Mock(text=SP_NO_RECORD_PAGE)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("31721737")

        self.assertEqual(result.state, DebtCheckState.NOT_FOUND)
        self.assertEqual(result.amount, 0.0)
        self.assertTrue(result.is_authoritative)

    def test_social_debtor_row_is_found_with_its_own_amount(self):
        session = Mock()
        session.get.return_value = Mock(text=SP_DEBTOR_ROW_PAGE)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("36439151")

        self.assertEqual(result.state, DebtCheckState.FOUND)
        self.assertAlmostEqual(result.amount, 731.46, places=2)

    def test_social_header_is_read_without_the_sort_control(self):
        """The name a column is matched by excludes the sort link inside it.

        This is the pin on the whole module. Drupal nests a sort anchor in every
        sortable `<th>`, and that anchor carries screen-reader text of its own,
        so the cell's plain text is

            "Dlžná suma zoradiť podľa Dlžná suma"

        Read that way the table named no amount column, so no table was found --
        and the consequence was not confined to the hyphen branch it was written
        for: the money path went with it and every SP check came back `unknown`,
        which is the re-queue-forever state the whole rewrite exists to end.
        """
        header = BeautifulSoup(_sp_thead("2"), "html.parser")
        labels = [_header_label(th) for th in header.find_all("th")]

        self.assertIn("Dlžná suma", labels)
        self.assertIn("Chýbajúce podklady za obdobie", labels)
        # The control is furniture, not part of the name.
        self.assertNotIn("zoradiť podľa", " ".join(labels))

    def test_social_row_for_another_ico_is_not_attributed(self):
        """The old scan took the first "€" anywhere on the page.

        A company nobody searched for must never be handed a figure that
        belongs to someone else.
        """
        session = Mock()
        session.get.return_value = Mock(text=SP_DEBTOR_ROW_PAGE)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("99999999")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)

    def test_social_page_without_the_results_view_is_unknown_not_zero(self):
        """An error or interstitial page is not an answer about the company."""
        session = Mock()
        session.get.return_value = Mock(
            text="<html><body><h1>Stránka je dočasne nedostupná</h1></body></html>",
        )

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("31721737")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)
        self.assertEqual(result.error_type, "parse_error")

    def test_social_unparseable_amount_is_unknown_not_zero(self):
        page = SP_DEBTOR_ROW_PAGE.replace("731,46 €", "neuvedené")
        session = Mock()
        session.get.return_value = Mock(text=page)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("36439151")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)
        self.assertEqual(result.error_type, "parse_error")

    def test_social_listed_row_without_an_amount_is_its_own_state(self):
        """A hyphen in the amount column is an answer, not a parsing failure.

        The registry lists employers who did not file and foreign SZČO who did
        not report, in the same table as its debtors, with a hyphen where the
        sum would be. Read as `unknown` the company was never written and never
        settled -- `last_insurance_debt` stayed NULL, so it sat in the
        never-checked group and was scraped twice a day for ever, while the
        company page showed it as debt-free. Read as `0.00` it would publish a
        figure the register never printed. It is neither.
        """
        session = Mock()
        session.get.return_value = Mock(text=SP_LISTED_WITHOUT_AMOUNT_PAGE)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("36269727")

        self.assertEqual(result.state, DebtCheckState.LISTED_NO_AMOUNT)
        # The whole point: conclusive about the company, silent about money.
        self.assertIsNone(result.amount)
        self.assertTrue(result.is_authoritative)

    def test_social_listed_row_carries_the_periods_the_register_published(self):
        """The periods are the claim. A sum was never the only thing SP says."""
        session = Mock()
        session.get.return_value = Mock(text=SP_LISTED_WITHOUT_AMOUNT_PAGE)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("36269727")

        self.assertIn("01/2026 - 03/2026", result.detail)
        self.assertIn("bez zverejnenej sumy", result.detail)

    def test_social_dash_elsewhere_does_not_make_the_row_a_listing(self):
        """A hyphen in *another* column is not the amount column's mark.

        This is the guard on the whole branch. The periods column is `-` on
        every ordinary debtor row, so a rule that accepted any empty cell would
        turn an unreadable amount into a confident "listed without a sum" --
        putting a claim in the register's mouth it never made.
        """
        page = SP_DEBTOR_ROW_PAGE.replace("731,46 €", "neuvedené")
        # The period cell in that fixture is already "-", so the row now holds
        # exactly one hyphen and no money at all.
        session = Mock()
        session.get.return_value = Mock(text=page)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("36439151")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)

    def test_social_listed_row_without_its_header_stays_unknown(self):
        """When the table cannot say which column is the amount, we do not guess.

        The failure is deliberately in the safe direction: the company is
        re-queued rather than recorded as something the register did not say.
        """
        session = Mock()
        session.get.return_value = Mock(text=SP_LISTED_WITHOUT_AMOUNT_NO_HEADER_PAGE)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("36269727")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)
        self.assertEqual(result.error_type, "parse_error")

    def test_social_debtor_row_beside_a_listed_row_is_still_found(self):
        """The two populations share a table; each row is read on its own."""
        page = SP_LISTED_WITHOUT_AMOUNT_PAGE.replace(
            "</tbody>",
            """
            <tr>
              <td class="views-field views-field-name" headers="view-name-table-column--3">MMBOXX, s.r.o.</td>
              <td class="views-field views-field-ico" headers="view-ico-table-column--3">36439151</td>
              <td class="views-field views-field-address" headers="view-address-table-column--3">Družstevná 4,</td>
              <td class="views-field views-field-city" headers="view-city-table-column--3">Liptovský Mikuláš</td>
              <td class="views-field views-field-price views-align-right" headers="view-price-table-column--3">731,46 €</td>
              <td class="views-field views-field-period__value" headers="view-period-value-table-column--3"><p>-</p></td>
            </tr>
            </tbody>""",
        )
        session = Mock()
        session.get.return_value = Mock(text=page)

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("36439151")

        self.assertEqual(result.state, DebtCheckState.FOUND)
        self.assertAlmostEqual(result.amount, 731.46, places=2)

    def _patch_session(self, target, session):
        from unittest.mock import patch

        return patch(target, return_value=session)
