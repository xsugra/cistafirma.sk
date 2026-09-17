"""The účtovné závierky we serve ourselves, and the four things they can be.

The section this replaces could only link out, and the link it produced was
rejected by the register's own front end -- so the one action it offered did not
work. Serving the documents here means the download is a promise this project
makes, which is why most of what follows tests the *refusals* rather than the
happy path.

The distinction the whole module is built on: **"we could not find out" is not
"there is nothing".** An empty document list rendered from an unreachable
register tells a reader that the company filed no accounts, which is a claim
about the company invented out of a network failure. So `unreachable` is a 503
and `no_statement` is a 200 that says `no_statement`, and there are tests below
that fail if either collapses into the other.

The second distinction is the security one. A download endpoint keyed by an id
from the URL is an open proxy onto registeruz.sk unless it verifies that the id
belongs to the company and year in the path -- so `open_document` re-derives the
listing rather than trusting the caller, and the test that it returns `None` for
a plausible-looking foreign id is the one that keeps that true.
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from companies.models import Company, CompanyFinancialResult
from companies.services import ruz_documents
from companies.services.ruz_documents import (
    KIND_PRILOHA,
    KIND_VYKAZ,
    STATE_LISTED,
    STATE_NO_STATEMENT,
    STATE_UNREACHABLE,
    list_documents,
    open_document,
    parse_document_id,
)
from companies.views import _content_disposition
from registers.integrations.ruz_api import RuzUnreachable


class FakeResponse:
    """Just enough of a `requests.Response` to stream and be closed."""

    def __init__(self, body=b'%PDF-1.4 fake', headers=None):
        self._body = body
        self.headers = headers or {
            'Content-Type': 'application/pdf',
            'Content-Length': str(len(body)),
        }
        self.closed = False

    def iter_content(self, chunk_size=1):
        for start in range(0, len(self._body), chunk_size):
            yield self._body[start:start + chunk_size]

    def close(self):
        self.closed = True


class FakeRuzApi:
    """A register that answers from a dict instead of the network.

    `statements` maps a závierka id to its JSON, `reports` a výkaz id to its
    JSON. `raises` makes every call fail, which is how the unreachable cases are
    driven.
    """

    def __init__(self, statements=None, reports=None, raises=None):
        self.statements = statements or {}
        self.reports = reports or {}
        self.raises = raises
        self.statement_calls = []
        self.report_calls = []
        self.document_calls = []

    def _check(self):
        if self.raises:
            raise self.raises

    def get_financial_statement_details(self, statement_id):
        self._check()
        self.statement_calls.append(statement_id)
        return self.statements.get(statement_id)

    def get_financial_report_details(self, report_id):
        self._check()
        self.report_calls.append(report_id)
        return self.reports.get(report_id)

    def fetch_document(self, kind, document_id):
        self._check()
        self.document_calls.append((kind, document_id))
        return FakeResponse()


def make_company(ico, *, ruz_id=800001, statements=None):
    return Company.objects.create(
        ruz_id=ruz_id,
        ico=ico,
        nazov_UJ='Testovacia, s. r. o.',
        id_uctovnych_zavierok=statements or [],
    )


def filed(company, year, *, statement_id=None, revenue=1000):
    return CompanyFinancialResult.objects.create(
        company=company,
        year=year,
        revenue=revenue,
        ruz_statement_id=statement_id,
    )


def statement(year, report_ids):
    return {
        'obdobieDo': f'{year}-12-31',
        'obdobieOd': f'{year}-01-01',
        'idUctovnychVykazov': list(report_ids),
    }


def report(attachments):
    return {'prilohy': attachments}


def attachment(attachment_id, name='Príloha.PDF', size=1234, pages=3):
    return {
        'id': attachment_id,
        'meno': name,
        'mimeType': 'application/pdf',
        'velkostPrilohy': size,
        'pocetStran': pages,
    }


class StatementAnchorTests(TestCase):
    """Which filing a year's figures came from, and how we find out."""

    def test_a_stored_statement_id_is_used_without_asking_ruz(self):
        company = make_company('50000001')
        filed(company, 2023, statement_id=777)
        api = FakeRuzApi(statements={777: statement(2023, [1])}, reports={1: report([])})

        listing = list_documents(company, 2023, api=api)

        self.assertEqual(listing.state, STATE_LISTED)
        self.assertEqual(api.statement_calls, [777])

    def test_an_unstamped_row_is_resolved_by_matching_the_year(self):
        """The 54 519 rows written before the field existed take this path."""
        company = make_company('50000002', statements=[111, 222, 333])
        filed(company, 2022)
        api = FakeRuzApi(
            statements={
                111: statement(2020, [1]),
                222: statement(2022, [2]),
                333: statement(2024, [3]),
            },
            reports={2: report([attachment(9001)])},
        )

        listing = list_documents(company, 2022, api=api)

        self.assertEqual(listing.state, STATE_LISTED)
        self.assertEqual([d.id for d in listing.documents], [f'{KIND_VYKAZ}-2', f'{KIND_PRILOHA}-9001'])

    def test_the_resolved_statement_is_cached_without_touching_the_rows_vintage(self):
        """`updated_at` is `auto_now`, and a lookup is not a re-read.

        `_resolve_statement_id` writes through `.update()` for this reason; a
        `.save()` would move the row's vintage forward and make a stored figure
        look as though it had just been read from the register.
        """
        company = make_company('50000003', statements=[222])
        row = filed(company, 2022)
        before = CompanyFinancialResult.objects.get(pk=row.pk).updated_at
        api = FakeRuzApi(statements={222: statement(2022, [2])}, reports={2: report([])})

        list_documents(company, 2022, api=api)

        row.refresh_from_db()
        self.assertEqual(row.ruz_statement_id, 222)
        self.assertEqual(row.updated_at, before)

    def test_the_walk_is_bounded(self):
        """A pathological statement list must not turn one click into a minute."""
        company = make_company(
            '50000004', statements=list(range(1, 200))
        )
        filed(company, 2022)
        api = FakeRuzApi(statements={i: statement(1999, [1]) for i in range(1, 200)})

        listing = list_documents(company, 2022, api=api)

        self.assertEqual(listing.state, STATE_NO_STATEMENT)
        self.assertEqual(len(api.statement_calls), ruz_documents.MAX_STATEMENT_PROBES)

    def test_a_year_we_hold_no_row_for_is_not_a_statement_about_ruz(self):
        company = make_company('50000005', statements=[111])
        api = FakeRuzApi()

        listing = list_documents(company, 2019, api=api)

        self.assertEqual(listing.state, STATE_NO_STATEMENT)
        self.assertEqual(api.statement_calls, [])


class ListingStateTests(TestCase):
    """The four outcomes, and the two that must never be confused."""

    def test_a_reachable_register_with_nothing_filed_is_listed_and_empty(self):
        """RUZ answered; its answer was that there is nothing to download."""
        company = make_company('50000010', statements=[111])
        filed(company, 2021)
        api = FakeRuzApi(statements={111: statement(2021, [])})

        listing = list_documents(company, 2021, api=api)

        self.assertEqual(listing.state, STATE_LISTED)
        self.assertEqual(listing.documents, ())

    def test_an_unreachable_register_is_not_an_empty_one(self):
        company = make_company('50000011', statements=[111])
        filed(company, 2021)
        api = FakeRuzApi(raises=RuzUnreachable('connection reset'))

        listing = list_documents(company, 2021, api=api)

        self.assertEqual(listing.state, STATE_UNREACHABLE)
        self.assertNotEqual(listing.state, STATE_LISTED)
        self.assertIn('connection reset', listing.detail)

    def test_documents_are_listed_with_the_metadata_that_makes_them_worth_showing(self):
        company = make_company('50000012', statements=[111])
        filed(company, 2021)
        api = FakeRuzApi(
            statements={111: statement(2021, [42])},
            reports={42: report([attachment(7001, name='Sprava audítora.PDF', size=555, pages=9)])},
        )

        listing = list_documents(company, 2021, api=api)

        vykaz, priloha = listing.documents
        self.assertEqual(vykaz.kind, KIND_VYKAZ)
        self.assertEqual(vykaz.mime_type, 'application/pdf')
        self.assertEqual(priloha.name, 'Sprava audítora.PDF')
        self.assertEqual(priloha.size, 555)
        self.assertEqual(priloha.pages, 9)

    def test_an_attachment_without_a_usable_id_is_skipped_not_rendered_broken(self):
        company = make_company('50000013', statements=[111])
        filed(company, 2021)
        api = FakeRuzApi(
            statements={111: statement(2021, [42])},
            reports={42: report([{'meno': 'bez id'}, attachment(7002)])},
        )

        listing = list_documents(company, 2021, api=api)

        self.assertEqual([d.id for d in listing.documents], [f'{KIND_VYKAZ}-42', f'{KIND_PRILOHA}-7002'])


class DocumentIdTests(TestCase):
    """The id vocabulary is closed: a caller can only name what we produced."""

    def test_round_trip(self):
        self.assertEqual(parse_document_id('priloha-8736666'), (KIND_PRILOHA, 8736666))
        self.assertEqual(parse_document_id('vykaz-12'), (KIND_VYKAZ, 12))

    def test_rejections(self):
        for bad in ['', 'priloha', 'priloha-', 'priloha-abc', 'nonsense-1', '../etc/passwd', 'pdf-1']:
            with self.subTest(bad=bad):
                self.assertIsNone(parse_document_id(bad))


class DownloadBoundaryTests(TestCase):
    """`None` here is the security boundary, not an error path."""

    def test_a_document_this_company_actually_has_is_opened(self):
        company = make_company('50000020', statements=[111])
        filed(company, 2021)
        api = FakeRuzApi(
            statements={111: statement(2021, [42])},
            reports={42: report([attachment(7003)])},
        )

        opened = open_document(company, 2021, f'{KIND_PRILOHA}-7003', api=api)

        self.assertIsNotNone(opened)
        self.assertEqual(api.document_calls, [('attachment', 7003)])
        self.assertEqual(opened.document.name, 'Príloha.PDF')

    def test_a_plausible_but_foreign_id_is_refused(self):
        """The id is well formed and RUZ would serve it -- but not for this company."""
        company = make_company('50000021', statements=[111])
        filed(company, 2021)
        api = FakeRuzApi(
            statements={111: statement(2021, [42])},
            reports={42: report([attachment(7003)])},
        )

        opened = open_document(company, 2021, f'{KIND_PRILOHA}-9999999', api=api)

        self.assertIsNone(opened)
        self.assertEqual(api.document_calls, [], 'nothing may be fetched before the check')

    def test_a_document_from_another_year_is_refused(self):
        company = make_company('50000022', statements=[111, 222])
        filed(company, 2020, statement_id=111)
        filed(company, 2021, statement_id=222)
        api = FakeRuzApi(
            statements={111: statement(2020, [1]), 222: statement(2021, [2])},
            reports={1: report([attachment(5001)]), 2: report([attachment(5002)])},
        )

        opened = open_document(company, 2020, f'{KIND_PRILOHA}-5002', api=api)

        self.assertIsNone(opened)
        self.assertEqual(api.document_calls, [])


class PortalUrlTests(TestCase):
    """The link that never worked, and the route that does."""

    def test_the_portal_url_is_the_route_the_register_actually_serves(self):
        from companies.serializers import CompanyDetailSerializer

        company = make_company('50000030')
        company.ruz_id = 1587213
        company.save(update_fields=['ruz_id'])

        url = CompanyDetailSerializer(company).data['ruz_portal_url']

        self.assertEqual(
            url,
            'https://www.registeruz.sk/cruz-public/domain/accountingentity/show/1587213',
        )
        self.assertNotIn('uctovna-jednotka?id=', url)

    def test_the_guard_for_a_missing_ruz_id_is_kept_even_though_it_cannot_fire(self):
        """`ruz_id` is NOT NULL, so this branch is unreachable today.

        Asserted anyway, because the branch is what the URL builder reads: if
        the column is ever relaxed -- a company entered by hand, a source that
        does not key on RUZ -- the alternative is `.../show/None` published as a
        working link. A cheap guard, and this is the note that says it was a
        decision rather than a leftover.
        """
        from companies.serializers import CompanyDetailSerializer

        company = make_company('50000031')
        company.ruz_id = None

        self.assertIsNone(CompanyDetailSerializer(company).data['ruz_portal_url'])


class ContentDispositionTests(TestCase):
    """A Slovak filename has to survive an HTTP header."""

    def test_the_real_name_travels_percent_encoded(self):
        header = _content_disposition('Príloha k účtovnej závierke.PDF')

        self.assertIn("filename*=UTF-8''", header)
        self.assertIn('Pr%C3%ADloha', header)
        self.assertTrue(header.startswith('attachment;'))

    def test_the_ascii_fallback_is_still_a_usable_filename(self):
        header = _content_disposition('Príloha k účtovnej závierke.PDF')

        fallback = header.split('filename="')[1].split('"')[0]
        self.assertTrue(fallback.isascii())
        self.assertTrue(fallback.endswith('.PDF'))

    def test_a_name_of_nothing_but_diacritics_still_yields_a_filename(self):
        header = _content_disposition('Účtovný výkaz')

        fallback = header.split('filename="')[1].split('"')[0]
        self.assertTrue(fallback)

    def test_a_name_carrying_crlf_cannot_inject_a_header(self):
        header = _content_disposition('evil\r\nX-Injected: 1.PDF')

        self.assertNotIn('\r', header)
        self.assertNotIn('\n', header)


class DocumentsEndpointTests(TestCase):
    """The two public routes, over HTTP."""

    def setUp(self):
        self.company = make_company('50000040', statements=[111])
        filed(self.company, 2021)

    def _url(self, suffix=''):
        # Trailing slash, matching the `url` the listing publishes -- DRF's
        # router wants it and Django's APPEND_SLASH would otherwise answer the
        # download with a 301 rather than the file.
        base = f'/api/companies/{self.company.ico}/financials/2021/documents/'
        return base if not suffix else base + suffix + ('' if suffix.endswith('/') else '/')

    def test_an_unknown_company_is_a_404(self):
        response = self.client.get('/api/companies/99999999/financials/2021/documents/')
        self.assertEqual(response.status_code, 404)

    def test_the_listing_carries_a_download_url_for_each_document(self):
        api = FakeRuzApi(
            statements={111: statement(2021, [42])},
            reports={42: report([attachment(7004, name='Výročná správa.PDF')])},
        )
        with patch.object(ruz_documents, '_client', return_value=api):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['state'], STATE_LISTED)
        self.assertEqual(len(body['documents']), 2)
        for document in body['documents']:
            self.assertTrue(document['url'].startswith(f'/api/companies/{self.company.ico}/'))
            self.assertNotIn('registeruz.sk', document['url'])

    def test_an_unreachable_register_is_a_503_and_says_so(self):
        """Not a 200 with an empty list -- that would read as "filed nothing"."""
        api = FakeRuzApi(raises=RuzUnreachable('timeout'))
        with patch.object(ruz_documents, '_client', return_value=api):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['state'], STATE_UNREACHABLE)

    def test_a_year_we_hold_nothing_for_is_a_200_that_says_no_statement(self):
        api = FakeRuzApi()
        with patch.object(ruz_documents, '_client', return_value=api):
            response = self.client.get(
                f'/api/companies/{self.company.ico}/financials/2001/documents/'
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['state'], STATE_NO_STATEMENT)

    def test_the_download_streams_the_bytes_and_names_the_file(self):
        api = FakeRuzApi(
            statements={111: statement(2021, [42])},
            reports={42: report([attachment(7004, name='Príloha.PDF')])},
        )
        with patch.object(ruz_documents, '_client', return_value=api):
            response = self.client.get(self._url('priloha-7004'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 fake')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('Pr%C3%ADloha.PDF', response['Content-Disposition'])
        self.assertEqual(api.document_calls, [('attachment', 7004)])

    def test_a_foreign_document_id_downloads_nothing(self):
        api = FakeRuzApi(
            statements={111: statement(2021, [42])},
            reports={42: report([attachment(7004)])},
        )
        with patch.object(ruz_documents, '_client', return_value=api):
            response = self.client.get(self._url('priloha-9999999'))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(api.document_calls, [])

    def test_a_malformed_document_id_is_not_a_route_at_all(self):
        response = self.client.get(self._url('../../etc/passwd'))
        self.assertEqual(response.status_code, 404)

    def test_an_unreachable_register_during_a_download_is_a_503_not_a_404(self):
        """A register we could not read must not read as "no such document"."""
        api = FakeRuzApi(raises=RuzUnreachable('timeout'))
        with patch.object(ruz_documents, '_client', return_value=api):
            response = self.client.get(self._url('priloha-7004'))

        self.assertEqual(response.status_code, 503)


class SyncStampingTests(TestCase):
    """The field is written by the sync, from an id it already had in hand."""

    def test_a_synced_row_records_the_statement_it_was_read_from(self):
        from registers.services.ruz_financials_sync import PARSER_REVISION

        self.assertGreaterEqual(PARSER_REVISION, 2, 'the row must know its filing')
