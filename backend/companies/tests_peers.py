"""The five peer rankings, and the population each of them admits to.

Two properties matter more than the ordering itself.

The first is that a section shows what it says it shows: `total_ranked` counts
the rows the ranking was drawn from, `total_in_scope` counts the companies the
question was asked about, and a company with no filed revenue is inside the
second and outside the first. A test that only checked the top row would pass
with both numbers hard-coded to anything.

The second is that a company the data cannot rank degrades instead of failing.
`podobne` reads a logarithm, and Postgres raises on `ln(0)` rather than
returning null -- so a single zero-revenue company in a division would take the
whole section down with a 500. That case is in the corpus, and the test for it
is the reason the guard exists.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, override_settings
from unittest.mock import patch

from companies.models import Company, CompanyFinancialResult
from companies.services.peers import (
    PEER_LIMIT,
    PEER_SCOPES,
    SCOPE_KRAJ,
    SCOPE_ODVETVIE,
    SCOPE_PODOBNE,
    SCOPE_TRZBY,
    SCOPE_ZAMESTNANCI,
    peers_for,
)
from companies.throttles import PeersThrottle, ReportThrottle
from companies.views import CompanyViewSet

_ruz_id = iter(range(900000, 901000))


def make_company(ico, name, *, kraj=None, nace=None, dissolved=False, **kwargs):
    return Company.objects.create(
        ruz_id=next(_ruz_id),
        ico=ico,
        nazov_UJ=name,
        kraj=kraj,
        sk_NACE=nace,
        datum_zrusenia='2020-01-01' if dissolved else None,
        **kwargs,
    )


def filed(company, year, revenue, profit=None):
    return CompanyFinancialResult.objects.create(
        company=company, year=year, revenue=revenue, profit=profit
    )


class PeersServiceTests(TestCase):
    def test_the_scope_vocabulary_is_closed(self):
        self.assertEqual(
            sorted(PEER_SCOPES),
            ['kraj', 'odvetvie', 'podobne', 'trzby', 'zamestnanci'],
        )
        with self.assertRaises(ValueError):
            peers_for(make_company('10000001', 'X'), 'nonsense')

    def test_the_whole_register_is_ranked_by_revenue(self):
        subject = make_company('10000010', 'Subjekt')
        middle = make_company('10000011', 'Stredná')
        big = make_company('10000012', 'Veľká')
        filed(subject, 2024, 10_000)
        filed(middle, 2024, 5_000_000)
        filed(big, 2024, 90_000_000)

        payload = peers_for(subject, SCOPE_TRZBY)

        self.assertEqual([r['ico'] for r in payload['results']], ['10000012', '10000011'])
        self.assertEqual(payload['ranked_by'], 'revenue')
        self.assertIsNone(payload['subject'])
        self.assertIsNone(payload['reason'])

    def test_a_company_is_ranked_at_its_latest_statement_only(self):
        # The DISTINCT ON in `_latest_rows`. Without it a company with a decade
        # of filings would occupy ten of the ten rows, and the section would be
        # a history rather than a ranking.
        subject = make_company('10000020', 'Subjekt')
        history = make_company('10000021', 'S históriou')
        filed(subject, 2024, 1_000)
        for year in (2019, 2020, 2021, 2022, 2023):
            filed(history, year, 50_000)
        filed(history, 2024, 60_000)

        payload = peers_for(subject, SCOPE_TRZBY)
        rows = [r for r in payload['results'] if r['ico'] == '10000021']

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['year'], 2024)
        self.assertEqual(rows[0]['revenue'], '60000.00')

    def test_a_struck_off_company_is_not_a_peer(self):
        subject = make_company('10000030', 'Subjekt')
        alive = make_company('10000031', 'Živá')
        gone = make_company('10000032', 'Zrušená', dissolved=True)
        filed(subject, 2024, 1_000)
        filed(alive, 2024, 500)
        filed(gone, 2024, 900_000)

        rows = peers_for(subject, SCOPE_TRZBY)['results']

        self.assertEqual([r['ico'] for r in rows], ['10000031'])

    def test_the_region_scope_narrows_to_the_region_and_drops_the_subject(self):
        subject = make_company('10000040', 'Subjekt', kraj='SK010')
        same = make_company('10000041', 'Ten istý kraj', kraj='SK010')
        other = make_company('10000042', 'Iný kraj', kraj='SK021')
        filed(subject, 2024, 5_000)
        filed(same, 2024, 4_000)
        filed(other, 2024, 9_000_000)

        payload = peers_for(subject, SCOPE_KRAJ)

        self.assertEqual(payload['subject'], 'SK010')
        self.assertEqual(payload['subject_label'], 'Bratislavský kraj')
        self.assertEqual([r['ico'] for r in payload['results']], ['10000041'])

    def test_the_region_scope_counts_the_region_including_firms_that_never_filed(self):
        subject = make_company('10000050', 'Subjekt', kraj='SK010')
        filed(subject, 2024, 5_000)
        filed(make_company('10000051', 'Filer', kraj='SK010'), 2024, 4_000)
        make_company('10000052', 'Nefilujúca', kraj='SK010')
        make_company('10000053', 'Iný kraj', kraj='SK021')

        payload = peers_for(subject, SCOPE_KRAJ)

        # Both numbers, and they differ: this is the pair the section prints so
        # that "the largest in the region" cannot be read as "of everything".
        self.assertEqual(payload['total_ranked'], 1)
        self.assertEqual(payload['total_in_scope'], 3)

    def test_a_company_without_a_region_says_so_rather_than_ranking_nothing(self):
        payload = peers_for(make_company('10000060', 'Bez kraja'), SCOPE_KRAJ)

        self.assertEqual(payload['reason'], 'no_region')
        self.assertEqual(payload['results'], [])
        self.assertEqual(payload['total_in_scope'], 0)

    def test_the_industry_scope_matches_on_the_two_digit_division(self):
        # `_extract_division` owns the parsing, so both spellings of division 62
        # have to land together -- and division 63 has to stay out.
        subject = make_company('10000070', 'Subjekt', nace='62010')
        dotted = make_company('10000071', 'Bodkovaná', nace='62.01')
        sibling = make_company('10000072', 'Iná divízia', nace='63000')
        filed(subject, 2024, 5_000)
        filed(dotted, 2024, 4_000)
        filed(sibling, 2024, 9_000_000)

        payload = peers_for(subject, SCOPE_ODVETVIE)

        self.assertEqual(payload['subject'], '62')
        self.assertEqual([r['ico'] for r in payload['results']], ['10000071'])
        self.assertEqual(payload['ranked_by'], 'revenue')

    def test_a_company_without_a_nace_code_has_no_industry_to_be_ranked_in(self):
        company = make_company('10000080', 'Bez NACE')
        self.assertEqual(peers_for(company, SCOPE_ODVETVIE)['reason'], 'no_nace')
        self.assertEqual(peers_for(company, SCOPE_PODOBNE)['reason'], 'no_nace')

    def test_similarity_is_a_ratio_and_not_a_difference(self):
        # The whole point of the log metric. In euro, 2 000 000 is 1 000 000
        # away from the subject and 10 000 000 is 9 000 000 away, so the euro
        # ordering would put `blizko` first by luck. In ratio it is 2x against
        # 10x against 10x -- so the two tenfold firms tie and the twofold firm
        # wins, which is the ordering a reader means by "similar".
        subject = make_company('10000090', 'Subjekt', nace='62010')
        factor_two = make_company('10000091', 'Dvojnásobok', nace='62010')
        ten_up = make_company('10000092', 'Desaťnásobok hore', nace='62010')
        ten_down = make_company('10000093', 'Desaťnásobok dole', nace='62010')
        filed(subject, 2024, 1_000_000)
        filed(factor_two, 2024, 2_000_000)
        filed(ten_up, 2024, 10_000_000)
        filed(ten_down, 2024, 100_000)

        payload = peers_for(subject, SCOPE_PODOBNE)
        icos = [r['ico'] for r in payload['results']]

        self.assertEqual(payload['ranked_by'], 'similarity')
        self.assertEqual(icos[0], '10000091')
        # The two tenfold firms are equidistant by construction, so their order
        # between themselves is a name tiebreak -- asserted as a set, because
        # what matters is that both outrank a *closer in euro* peer and that
        # the order is stable rather than whatever the planner returned.
        self.assertEqual(set(icos[1:]), {'10000092', '10000093'})
        self.assertEqual(icos, ['10000091', '10000093', '10000092'])

    def test_a_zero_revenue_peer_does_not_take_the_section_down(self):
        # `Abs(Ln(revenue) - ...)` reaches Postgres as `ln(...)`, and Postgres
        # raises "cannot take logarithm of zero" rather than returning null.
        # The filter is `revenue > 0`, not `is not null`, for exactly this row.
        subject = make_company('10000100', 'Subjekt', nace='62010')
        zero = make_company('10000101', 'Nulová', nace='62010')
        filed(subject, 2024, 1_000_000)
        filed(zero, 2024, 0)

        payload = peers_for(subject, SCOPE_PODOBNE)

        self.assertEqual(payload['ranked_by'], 'similarity')
        self.assertEqual([r['ico'] for r in payload['results']], [])

    def test_a_subject_with_nothing_filed_falls_back_to_size_and_says_so(self):
        subject = make_company('10000110', 'Nefilujúca', nace='62010')
        other = make_company('10000111', 'Filujúca', nace='62010')
        filed(other, 2024, 1_000_000)

        payload = peers_for(subject, SCOPE_PODOBNE)

        # Not a failure and not a silent switch of meaning: the same rows under
        # an ordering the frontend can name, because `ranked_by` travels with
        # them.
        self.assertEqual(payload['ranked_by'], 'revenue')
        self.assertEqual([r['ico'] for r in payload['results']], ['10000111'])

    def test_a_zero_revenue_subject_falls_back_the_same_way(self):
        subject = make_company('10000120', 'Nulová', nace='62010')
        filed(subject, 2024, 0)
        other = make_company('10000121', 'Filujúca', nace='62010')
        filed(other, 2024, 1_000_000)

        self.assertEqual(peers_for(subject, SCOPE_PODOBNE)['ranked_by'], 'revenue')

    def test_a_company_without_revenue_is_counted_inside_the_scope_not_the_ranking(self):
        subject = make_company('10000130', 'Subjekt')
        filed(subject, 2024, 1_000)
        filed(make_company('10000132', 'S tržbami'), 2024, 500)
        # Filed a statement, and the statement carried no revenue line. It is a
        # company the register knows and a row no revenue order can place.
        statement_without_revenue = make_company('10000131', 'Bez tržieb')
        CompanyFinancialResult.objects.create(
            company=statement_without_revenue, year=2024, revenue=None
        )

        payload = peers_for(subject, SCOPE_TRZBY)

        self.assertEqual(payload['total_ranked'], 1)
        self.assertEqual(payload['total_in_scope'], 3)
        self.assertEqual([r['ico'] for r in payload['results']], ['10000132'])

    def test_a_section_shows_no_more_than_the_limit_and_reports_the_real_count(self):
        subject = make_company('10000140', 'Subjekt')
        filed(subject, 2024, 1)
        for i in range(PEER_LIMIT + 5):
            filed(make_company(f'200001{i:02d}', f'Firma {i}'), 2024, 1_000 + i)

        payload = peers_for(subject, SCOPE_TRZBY)

        self.assertEqual(len(payload['results']), PEER_LIMIT)
        # One short of the sixteen rows above: the subject is not one of its
        # own peers, so `total_ranked` counts the companies it was ranked
        # against rather than every company in the ranking.
        self.assertEqual(payload['total_ranked'], PEER_LIMIT + 5)

    def test_a_company_is_never_one_of_its_own_peers(self):
        # Its own largest filer by a mile, so in the whole-register scope it
        # would come first if it were not excluded -- an assertion that would
        # pass by accident if it were merely ranked low.
        company = make_company('10000150', 'Sama sebe', kraj='SK010', nace='62010',
                               velkost_organizacie='11')
        filed(company, 2024, 900_000_000)

        for scope in (SCOPE_TRZBY, SCOPE_KRAJ, SCOPE_ODVETVIE, SCOPE_PODOBNE,
                      SCOPE_ZAMESTNANCI):
            with self.subTest(scope=scope):
                icos = [r['ico'] for r in peers_for(company, scope)['results']]
                self.assertNotIn('10000150', icos)


class SizeBandScopeTests(TestCase):
    """`zamestnanci`: the neighbours that share the register's size code.

    The code is ŠÚ SR číselník 0073 and its band edges are uneven, so the
    assertions below are on the *code* being matched exactly and on its text
    coming from `services/velkost.py` rather than being reconstructed here.
    """

    def test_the_band_narrows_to_the_code_and_carries_its_text(self):
        subject = make_company('40000001', 'Subjekt', velkost_organizacie='04')
        same = make_company('40000002', 'Rovnaká kategória', velkost_organizacie='04')
        # Adjacent bands, and the one above it is far larger -- so a scope that
        # matched on anything but the exact code would be visibly wrong here.
        bigger = make_company('40000003', 'Väčšia', velkost_organizacie='05')
        filed(subject, 2024, 5_000)
        filed(same, 2024, 40_000)
        filed(bigger, 2024, 9_000_000)

        payload = peers_for(subject, SCOPE_ZAMESTNANCI)

        self.assertEqual([r['ico'] for r in payload['results']], ['40000002'])
        self.assertEqual(payload['subject'], '04')
        # The code and its číselník text together: the heading renders this
        # verbatim, so a band called by its number alone is not possible.
        self.assertEqual(payload['subject_label'], '04 — 3-4 zamestnanci')
        self.assertEqual(payload['reason'], None)

    def test_the_band_counts_firms_that_never_filed_inside_the_scope(self):
        subject = make_company('40000010', 'Subjekt', velkost_organizacie='04')
        filed(subject, 2024, 5_000)
        filed(make_company('40000011', 'Filer', velkost_organizacie='04'), 2024, 4_000)
        make_company('40000012', 'Nefilujúca', velkost_organizacie='04')
        make_company('40000013', 'Iná kategória', velkost_organizacie='05')

        payload = peers_for(subject, SCOPE_ZAMESTNANCI)

        self.assertEqual(payload['total_ranked'], 1)
        # Three, not four: the subject is in its own band's population, which is
        # the point -- the band is 3 231 firms and the subject is one of them.
        self.assertEqual(payload['total_in_scope'], 3)

    def test_a_company_the_register_gives_no_size_is_not_put_in_a_band(self):
        # `00` is "nezistený" -- the register stating that it does not know --
        # and it is the modal value in the table, not an edge case. Ten firms
        # would render as a band called "unknown" and read as a category.
        subject = make_company('40000020', 'Neznáma veľkosť', velkost_organizacie='00')
        filed(subject, 2024, 5_000)
        filed(make_company('40000021', 'Tiež neznáma', velkost_organizacie='00'), 2024, 1)

        payload = peers_for(subject, SCOPE_ZAMESTNANCI)

        self.assertEqual(payload['reason'], 'no_size')
        self.assertEqual(payload['results'], [])
        self.assertEqual(payload['total_ranked'], 0)
        self.assertIsNone(payload['subject_label'])
        # The code is still reported, so the section can say *which* value it
        # was that the register could not turn into a size.
        self.assertEqual(payload['subject'], '00')

    def test_the_refusal_counts_the_others_the_register_cannot_size(self):
        # The count is the explanation: it is what turns "we have nothing for
        # your firm" into "the register records no size for your firm, as for
        # these others". Read from the table, never written down as a constant.
        subject = make_company('40000030', 'Bez veľkosti', velkost_organizacie='00')
        make_company('40000031', 'Bez kódu')                      # NULL
        make_company('40000032', 'Prázdny kód', velkost_organizacie='')
        make_company('40000033', 'Tiež 00', velkost_organizacie='00')
        make_company('40000034', 'Má kategóriu', velkost_organizacie='12')
        make_company('40000035', 'Zrušená, bez kódu', dissolved=True)

        payload = peers_for(subject, SCOPE_ZAMESTNANCI)

        self.assertEqual(payload['reason'], 'no_size')
        # Three: the subject, the null, the empty string and the other `00` --
        # but not the firm with a band, and not the struck-off one, which no
        # other scope counts either.
        self.assertEqual(payload['total_in_scope'], 4)

    def test_a_size_code_the_codebook_does_not_define_is_refused_not_guessed(self):
        # Nothing in the live table looks like this (every value is `00`-`38` or
        # null, measured 2026-09-12), so it would mean the register has added a
        # band. The answer is still "no band" rather than a guess -- but the
        # service logs it, which is the only signal that the codebook is stale.
        subject = make_company('40000040', 'Nový kód', velkost_organizacie='99')

        with self.assertLogs('companies.services.peers', level='WARNING') as logs:
            payload = peers_for(subject, SCOPE_ZAMESTNANCI)

        self.assertEqual(payload['reason'], 'no_size')
        self.assertIn('99', ''.join(logs.output))

    def test_a_zero_revenue_company_in_the_band_does_not_take_the_section_down(self):
        # Same guard as `podobne`, reached a different way: the band is matched
        # on a code, and revenue is only the ordering, so a zero-revenue member
        # is ranked last rather than crashing the logarithm.
        subject = make_company('40000050', 'Subjekt', velkost_organizacie='06')
        filed(subject, 2024, 5_000)
        filed(make_company('40000051', 'Nulová', velkost_organizacie='06'), 2024, 0)
        filed(make_company('40000052', 'Kladná', velkost_organizacie='06'), 2024, 700)

        rows = peers_for(subject, SCOPE_ZAMESTNANCI)['results']

        self.assertEqual([r['ico'] for r in rows], ['40000052', '40000051'])


class PeersEndpointTests(TestCase):
    def setUp(self):
        self.subject = make_company('30000001', 'Subjekt', kraj='SK010', nace='62010',
                                    velkost_organizacie='11')
        self.peer = make_company('30000002', 'Kolega', kraj='SK010', nace='62010')
        filed(self.subject, 2024, 1_000_000)
        filed(self.peer, 2024, 900_000)

    def url(self, ico='30000001', scope='kraj'):
        query = f'?scope={scope}' if scope is not None else ''
        return f'/api/companies/{ico}/peers/{query}'

    def test_the_endpoint_answers_a_known_company(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['scope'], 'kraj')
        self.assertEqual(body['subject'], 'SK010')
        self.assertEqual([r['ico'] for r in body['results']], ['30000002'])

    def test_the_size_scope_answers_with_the_band_even_when_nobody_in_it_filed(self):
        # The subject carries band `11`; the peer carries none. So the question
        # has an answer -- here is your band, here is how many firms are in it --
        # and the answer happens to contain no ranked rows. That is *not* the
        # `no_size` refusal: `reason` stays null, and `total_in_scope` is 1,
        # which is the pair of facts the section renders.
        response = self.client.get(self.url(scope='zamestnanci'))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['scope'], 'zamestnanci')
        self.assertIsNone(body['reason'])
        self.assertEqual(body['subject'], '11')
        self.assertEqual(body['subject_label'], '11 — 25-49 zamestnancov')
        self.assertEqual(body['results'], [])
        self.assertEqual(body['total_ranked'], 0)
        self.assertEqual(body['total_in_scope'], 1)

    def test_the_size_scope_reports_the_refusal_over_the_wire(self):
        # The other branch, and the one 63,3 % of the register lands in: the
        # register records no size, so there is no band to rank within. It
        # travels as a reason code -- not a 404, and not an empty list with no
        # explanation -- with the count of firms in the same position, because
        # the frontend owns the sentence and needs the number for it.
        make_company('30000003', 'Bez veľkosti', velkost_organizacie='00')

        response = self.client.get(self.url(ico='30000003', scope='zamestnanci'))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['reason'], 'no_size')
        self.assertEqual(body['subject'], '00')
        self.assertIsNone(body['subject_label'])
        self.assertEqual(body['results'], [])
        self.assertEqual(body['total_ranked'], 0)
        # Two: this company, and `setUp`'s peer, which carries no code at all.
        # Both are "the register cannot size this firm", which is the point of
        # counting them together rather than only the `00`s.
        self.assertEqual(body['total_in_scope'], 2)

    def test_the_endpoint_refuses_an_unknown_scope_rather_than_guessing_one(self):
        # Every scope answers a different question, so a default would put one
        # ranking under another one's heading.
        for bad in ('', 'nonsense'):
            with self.subTest(scope=bad):
                response = self.client.get(self.url(scope=bad))
                self.assertEqual(response.status_code, 400)
                self.assertIn('rozsah', response.json()['detail'])

    def test_a_missing_scope_is_refused_too(self):
        response = self.client.get(self.url(scope=None))
        self.assertEqual(response.status_code, 400)

    def test_an_unknown_company_is_a_404(self):
        response = self.client.get(self.url(ico='99999999'))
        self.assertEqual(response.status_code, 404)

    def test_the_endpoint_is_readable_without_an_account(self):
        # `CompanyViewSet` is AllowAny, and the section renders on a public
        # company page. A throttle is not a login.
        self.assertEqual(self.client.get(self.url(scope='trzby')).status_code, 200)


class ThrottleWiringTests(TestCase):
    def test_only_the_two_expensive_actions_carry_a_limit(self):
        view = CompanyViewSet()

        view.action = 'peers'
        self.assertIsInstance(view.get_throttles()[0], PeersThrottle)

        view.action = 'report'
        self.assertIsInstance(view.get_throttles()[0], ReportThrottle)

        for action in ('retrieve', 'list', 'search'):
            with self.subTest(action=action):
                view.action = action
                self.assertEqual(view.get_throttles(), [])


class PublicThrottleTests(TestCase):
    """The limiter itself: what it keys on, and what it does when Redis dies."""

    def test_a_signed_in_caller_is_limited_per_account_and_not_per_address(self):
        throttle = PeersThrottle()
        user = get_user_model().objects.create_user(
            username='a@example.com', email='a@example.com', password='x'
        )
        request = type('R', (), {'user': user})()

        self.assertEqual(throttle.get_cache_key(request, None), f'throttle_peers_user:{user.pk}')

    def test_an_anonymous_caller_is_limited_by_address(self):
        throttle = PeersThrottle()
        request = type('R', (), {
            'user': AnonymousUser(),
            'META': {'REMOTE_ADDR': '203.0.113.9'},
        })()

        self.assertEqual(throttle.get_cache_key(request, None), 'throttle_peers_ip:203.0.113.9')

    @override_settings(
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    )
    def test_the_limit_actually_trips(self):
        cache.clear()
        throttle = PeersThrottle()
        throttle.rate = '2/hour'
        throttle.num_requests, throttle.duration = 2, 3600
        request = type('R', (), {
            'user': AnonymousUser(),
            'META': {'REMOTE_ADDR': '203.0.113.9'},
        })()

        self.assertTrue(throttle.allow_request(request, None))
        self.assertTrue(throttle.allow_request(request, None))
        self.assertFalse(throttle.allow_request(request, None))
        cache.clear()

    @override_settings(
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    )
    def test_an_unreachable_cache_lets_the_request_through_instead_of_failing_it(self):
        # A rate limiter that takes the endpoint down with it is worse than no
        # rate limiter. Failing open is the decision; failing open *quietly*
        # is the defect this asserts against, so the log record is checked too.
        from companies import throttles

        cache.clear()
        throttle = PeersThrottle()
        throttles._cache_failure_logged = False
        request = type('R', (), {
            'user': AnonymousUser(),
            'META': {'REMOTE_ADDR': '203.0.113.9'},
        })()

        # A cache whose every call raises, rather than a patched DRF internal:
        # the point is that the limiter survives Redis being gone, whichever
        # method it happens to reach for first.
        class _DeadCache:
            def get(self, *args, **kwargs):
                raise ConnectionError('redis is gone')

            def set(self, *args, **kwargs):
                raise ConnectionError('redis is gone')

        with patch.object(type(throttle), 'cache', _DeadCache()):
            with self.assertLogs('companies.throttles', level='ERROR') as captured:
                self.assertTrue(throttle.allow_request(request, None))

        self.assertIn('rate limiting is off', captured.output[0])
        throttles._cache_failure_logged = False
