import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db.models import OuterRef, Subquery
from django.http import QueryDict
from django.test import RequestFactory, TestCase, override_settings

from adminapi.services import CompanyFilterService
from adminapi.views.companies import AdminCompanyViewSet
from companies.models import Company, CompanyFinancialResult
from registers.models import CompanySyncStatus, OrsrCompanyProfile
from users.models import User


class CompanyFilterServicePerformanceTests(TestCase):
    def setUp(self):
        self.service = CompanyFilterService()
        self.view = AdminCompanyViewSet()

        self.matching = Company.objects.create(
            ruz_id=900001,
            ico="90000001",
            nazov_UJ="Matching s.r.o.",
            mesto="Bratislava",
            sk_NACE="62.01",
            debt_vszp=Decimal("0"),
            debt_soc_poist=Decimal("0"),
            tax_debt=Decimal("0"),
        )
        CompanyFinancialResult.objects.create(
            company=self.matching,
            year=2024,
            revenue=Decimal("100000"),
            profit=Decimal("20000"),
        )
        OrsrCompanyProfile.objects.create(company=self.matching, ico=self.matching.ico)
        CompanySyncStatus.objects.create(
            company=self.matching,
            source=CompanySyncStatus.SOURCE_FS,
            is_blocked=True,
            consecutive_failures=3,
        )

        self.non_matching = Company.objects.create(
            ruz_id=900002,
            ico="90000002",
            nazov_UJ="Non Matching s.r.o.",
            mesto="Bratislava",
            sk_NACE="70.22",
        )

    def test_builder_filters_use_annotated_flags_without_relation_joins(self):
        params = {
            "filter_builder": json.dumps(
                {
                    "id": "root",
                    "type": "group",
                    "logic": "and",
                    "children": [
                        {"type": "condition", "field": "has_financials", "operator": "equals", "value": "1"},
                        {"type": "condition", "field": "has_orsr", "operator": "equals", "value": "1"},
                        {"type": "condition", "field": "sync_state", "operator": "equals", "value": "blocked"},
                    ],
                }
            )
        }

        queryset = self.service.apply(self.view._listing_queryset(), params)
        sql = str(queryset.query)

        self.assertEqual(list(queryset.values_list("id", flat=True)), [self.matching.id])
        self.assertNotIn('JOIN "Company Financial Results"', sql)
        self.assertNotIn('JOIN "registers_companysyncstatus"', sql)

    def test_the_size_filter_matches_the_code_without_folding_its_case(self):
        """The column holds a two-digit code, so `iexact` buys nothing and costs the index.

        `velkost_organizacie` carries ŠÚ SR číselník 0073 -- `00` to `38`. There
        is no case in it to fold, and `iexact` compiles to
        `UPPER("Veľkosť") = UPPER(%s)`, which cannot use the composite
        `(velkost_organizacie, datum_zrusenia)` index the model declares and
        falls back to scanning the table. Both routes to this filter are checked
        because they are separate code paths -- the builder's `filter_builder`
        JSON and a flat `?velkost_organizacie=` query parameter -- and the admin
        UI only ever takes the first, so a fix applied to one of them would look
        like it had worked.
        """
        self.matching.velkost_organizacie = "04"
        self.matching.save(update_fields=["velkost_organizacie"])

        # The builder route, isolated so this asserts about the lookup alone
        # rather than about every `UPPER` anywhere in the listing queryset.
        condition = {"field": "velkost_organizacie", "operator": "equals", "value": "04"}
        sql = str(Company.objects.filter(self.service._condition_to_q(condition)).query)
        self.assertNotIn("UPPER(", sql)

        built = self.service.apply(
            self.view._listing_queryset(),
            {
                "filter_builder": json.dumps(
                    {
                        "id": "root",
                        "type": "group",
                        "logic": "and",
                        "children": [
                            {"type": "condition", "field": "velkost_organizacie", "operator": "equals", "value": "04"},
                        ],
                    }
                )
            },
        )
        self.assertEqual(list(built.values_list("id", flat=True)), [self.matching.id])

        # And the flat query parameter, which is a different branch of `apply`.
        flat = self.service.apply(self.view._listing_queryset(), {"velkost_organizacie": "04"})
        self.assertEqual(list(flat.values_list("id", flat=True)), [self.matching.id])
        self.assertNotIn("UPPER(", str(flat.query))

        # The code is a code, so a value one digit away is a different band and
        # must not match -- the reason an exact lookup is right here, rather than
        # a widening one that would answer a question nobody asked.
        other = self.service.apply(self.view._listing_queryset(), {"velkost_organizacie": "05"})
        self.assertEqual(list(other.values_list("id", flat=True)), [])


class CompanyPresetTests(TestCase):
    """Presets are a promise about the data, and until now nothing checked them.

    `it_trnava_no_debt` carried two conditions its own description never named
    -- `has_financials` and `has_orsr` -- and returned 0 rows out of a
    population of 136. Neither condition was broken; both were simply true of
    almost nobody (0 and 4 of the 136). A preset key that no branch of `apply()`
    reads fails the same way and just as quietly, so the first test below asks
    the generated query rather than a hand-kept list of key names.
    """

    def setUp(self):
        self.service = CompanyFilterService()
        self.view = AdminCompanyViewSet()
        self.base = self.view._listing_queryset()

    def test_every_preset_key_produces_a_filter(self):
        """A key `apply()` does not implement is dropped without a word.

        This is the shape of the whole defect class: the request looks
        well-formed, the response comes back, and the filter simply was not
        applied. Comparing the compiled SQL is data-independent, so this holds
        even on an empty table -- where every other assertion about a preset
        would pass vacuously.

        `self.fail` rather than `assertNotEqual`: the compiled SQL for this
        queryset is ~150 lines of annotated column list, and an equality
        assertion prints both copies, burying the one line that says which key
        was ignored.
        """
        unfiltered = str(self.service.apply(self.base, {}).query)
        for preset in CompanyFilterService.PRESETS:
            for key, value in preset["filters"].items():
                with self.subTest(preset=preset["key"], key=key):
                    filtered = str(self.service.apply(self.base, {key: value}).query)
                    if filtered == unfiltered:
                        self.fail(
                            f"preset {preset['key']!r} sets {key!r}={value!r}, but "
                            f"applying it does not change the query -- no branch "
                            f"of apply() reads that key, so the condition the "
                            f"preset claims is not being applied at all."
                        )

    def test_the_preset_matches_a_company_that_has_no_statements_yet(self):
        """The reported symptom, as a test.

        An active IT company in Trnava with no debts is what this preset says it
        looks for. It must match whether or not we happen to have imported the
        company's financial statement -- requiring the statement made the preset
        return nothing for months without anyone noticing.
        """
        Company.objects.create(
            ruz_id=910001,
            ico="91000001",
            nazov_UJ="IT Trnava s.r.o.",
            mesto="Trnava",
            psc="91701",
            sk_NACE="62.01",
            debt_vszp=Decimal("0"),
            debt_soc_poist=Decimal("0"),
            tax_debt=Decimal("0"),
        )
        preset = self.service.get_preset("it_trnava_no_debt")
        self.assertIsNotNone(preset)

        matched = self.service.apply(self.base, dict(preset["filters"]))

        self.assertEqual(list(matched.values_list("ico", flat=True)), ["91000001"])


class SyncStateBranchTests(TestCase):
    """`sync_state` must not answer differently depending on how it is asked.

    The filter has two branches -- one for a queryset carrying the
    `sync_failures` annotation (the admin listing), one for a queryset that does
    not (every other caller) -- and they disagreed about the largest population
    in the table: a company with no `CompanySyncStatus` rows at all. Its
    annotation is NULL, and `sync_failures = 0` is not true of NULL, so the
    annotated branch dropped them. Measured 2026-09-11 through the two paths:
    11 451 against 275 912 for the same filter, all of the difference being
    companies that had simply never failed anything.

    A test rather than a note, because the fix is one `isnull` away from being
    undone by anyone who reads `filter(sync_failures=0)` as the obvious way to
    write "has no failures" -- and the annotated path is the one the operator
    actually sees.
    """

    def setUp(self):
        self.service = CompanyFilterService()
        self.never_synced = Company.objects.create(
            ruz_id=920001, ico="92000001", nazov_UJ="Nikdy nesynchronizovana s.r.o."
        )
        self.clean = Company.objects.create(
            ruz_id=920002, ico="92000002", nazov_UJ="Cista s.r.o."
        )
        self.failing = Company.objects.create(
            ruz_id=920003, ico="92000003", nazov_UJ="Zlyhavajuca s.r.o."
        )
        CompanySyncStatus.objects.create(
            company=self.clean,
            source=CompanySyncStatus.SOURCE_FS,
            consecutive_failures=0,
        )
        CompanySyncStatus.objects.create(
            company=self.failing,
            source=CompanySyncStatus.SOURCE_FS,
            consecutive_failures=2,
        )

    def _annotated(self):
        """The admin listing's own annotation, ordering and all."""
        return Company.objects.annotate(
            sync_failures=Subquery(
                CompanySyncStatus.objects.filter(company_id=OuterRef("pk"))
                .order_by("-consecutive_failures", "-updated_at", "-id")
                .values("consecutive_failures")[:1]
            )
        )

    def _ids(self, queryset):
        return set(queryset.values_list("id", flat=True))

    def test_a_company_that_was_never_synced_is_healthy(self):
        """The whole point: absence of a failure is not a failure."""
        params = {"sync_state": "healthy"}

        for label, queryset in (
            ("without the annotation", Company.objects.all()),
            ("with the annotation", self._annotated()),
        ):
            with self.subTest(queryset=label):
                matched = self._ids(self.service.apply(queryset, params))
                self.assertIn(
                    self.never_synced.id,
                    matched,
                    "a company with no sync status rows was called unhealthy",
                )
                self.assertIn(self.clean.id, matched)
                self.assertNotIn(self.failing.id, matched)

    def test_both_branches_agree_on_both_values(self):
        for state in ("healthy", "failing"):
            with self.subTest(sync_state=state):
                params = {"sync_state": state}
                self.assertEqual(
                    self._ids(self.service.apply(Company.objects.all(), params)),
                    self._ids(self.service.apply(self._annotated(), params)),
                    f"the two branches disagree about sync_state={state}",
                )

    def test_the_filter_builder_path_agrees_as_well(self):
        """It carries its own copy of the same two branches."""
        params = {
            "filter_builder": json.dumps(
                {
                    "id": "root",
                    "type": "group",
                    "logic": "and",
                    "children": [
                        {
                            "type": "condition",
                            "field": "sync_state",
                            "operator": "equals",
                            "value": "healthy",
                        },
                    ],
                }
            )
        }

        without = self._ids(self.service.apply(Company.objects.all(), params))
        with_annotation = self._ids(self.service.apply(self._annotated(), params))

        self.assertEqual(without, with_annotation)
        self.assertIn(self.never_synced.id, without)


class AdminCompanyReportModeTests(TestCase):
    def test_light_mode_is_default_and_full_mode_is_explicit(self):
        view = AdminCompanyViewSet()

        class _Request:
            def __init__(self, params):
                self.query_params = params

        self.assertTrue(view._is_light_mode(_Request({})))
        self.assertTrue(view._is_light_mode(_Request({"light": "1"})))
        self.assertFalse(view._is_light_mode(_Request({"mode": "full"})))


class ZeroResultDiagnosisTests(TestCase):
    """An empty table has to say which condition emptied it.

    The preset behind the reported symptom returned nothing for months and no
    screen could say why -- an empty result and a filter over a dataset we do
    not hold look exactly alike. The report now names the condition whose
    removal brings rows back, and only when the result is empty, so nothing
    pays for it on the ordinary path.
    """

    def setUp(self):
        self.service = CompanyFilterService()
        self.view = AdminCompanyViewSet()
        # Both match the Trnava IT preset in every respect except that both are
        # dissolved, so exactly one condition is responsible for the empty
        # result -- and the preset's own keys are what the diagnosis must see.
        for index, name in enumerate(("Alfa s.r.o.", "Beta s.r.o."), start=1):
            Company.objects.create(
                ruz_id=930000 + index,
                ico=f"9300000{index}",
                nazov_UJ=name,
                mesto="Trnava",
                psc="91701",
                sk_NACE="62.01",
                debt_vszp=Decimal("0"),
                debt_soc_poist=Decimal("0"),
                tax_debt=Decimal("0"),
                datum_zrusenia=date(2020, 1, 1),
            )

    def _summary(self, query_string):
        request = RequestFactory().get(f"/api/admin/companies/report/?{query_string}")
        request.query_params = QueryDict(query_string)
        filter_params = self.view._effective_filter_params(request)
        queryset = self.service.apply(self.view._listing_queryset(), filter_params)
        return self.view._build_aggregate_report(queryset, True, request)

    def test_the_condition_that_emptied_the_result_is_named(self):
        summary = self._summary("preset=it_trnava_no_debt")

        self.assertEqual(summary["count"], 0)
        diagnosis = summary["zero_diagnosis"]
        self.assertEqual(
            [item["condition"] for item in diagnosis],
            ["active"],
            "only `active` excludes these two; the other conditions restore none",
        )
        self.assertEqual(diagnosis[0]["count_without"], 2)

    def test_the_preset_is_not_reported_as_a_condition(self):
        """`preset` is a name for a set of conditions, not one of them."""
        conditions = [
            item["condition"] for item in self._summary("preset=it_trnava_no_debt")["zero_diagnosis"]
        ]

        self.assertNotIn("preset", conditions)
        self.assertNotIn("mode", conditions)

    def test_a_result_that_is_not_empty_carries_no_diagnosis(self):
        summary = self._summary("mesto=Trnava")

        self.assertEqual(summary["count"], 2)
        self.assertNotIn("zero_diagnosis", summary)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "admin-company-report-tests",
        },
    },
)
class AdminCompanyReportCacheTests(TestCase):
    def setUp(self):
        self.view = AdminCompanyViewSet()
        self.user = User.objects.create_user(
            username="report-admin",
            email="report-admin@example.com",
            password="not-used",
            is_staff=True,
        )

    def _request(self, query_string="", user=None):
        request = RequestFactory().get(f"/api/admin/companies/report/?{query_string}")
        request.query_params = QueryDict(query_string)
        request.user = user or self.user
        return request

    def test_cache_key_normalizes_filters_and_is_scoped_to_authenticated_user(self):
        first = self._request("mesto=Bratislava&mode=light&page=1&page_size=50")
        equivalent = self._request("light=1&mesto=Bratislava&page=8&page_size=200")
        other_user = User.objects.create_user(
            username="another-report-admin",
            email="another-report-admin@example.com",
            password="not-used",
            is_staff=True,
        )
        different_user = self._request("mesto=Bratislava", other_user)

        first_key = self.view._report_cache_key(first, mode="light")

        self.assertEqual(
            first_key,
            self.view._report_cache_key(equivalent, mode="light"),
        )
        self.assertNotEqual(
            first_key,
            self.view._report_cache_key(different_user, mode="light"),
        )
        self.assertNotIn("Bratislava", first_key)

    @patch.object(AdminCompanyViewSet, "_release_report_lock")
    def test_aggregate_failure_releases_owned_lock(self, release_lock):
        request = self._request()
        self.view.request = request

        with patch("adminapi.views.companies.cache") as cache_mock:
            cache_mock.get.return_value = None
            cache_mock.add.return_value = True
            with patch.object(
                self.view,
                "_build_aggregate_report",
                side_effect=RuntimeError("aggregate failed"),
            ):
                with self.assertRaisesMessage(RuntimeError, "aggregate failed"):
                    self.view.report(request)

        release_lock.assert_called_once()
        lock_key, lock_token = release_lock.call_args.args
        self.assertTrue(lock_key.endswith(":lock"))
        self.assertEqual(len(lock_token), 32)

    @patch.object(AdminCompanyViewSet, "_release_report_lock")
    def test_cache_set_failure_releases_owned_lock(self, release_lock):
        request = self._request()
        self.view.request = request
        summary = {"count": 1, "report_mode": "light", "presets": [], "top_companies": []}

        with patch("adminapi.views.companies.cache") as cache_mock:
            cache_mock.get.return_value = None
            cache_mock.add.return_value = True
            cache_mock.set.side_effect = ConnectionError("cache unavailable")
            with patch.object(
                self.view,
                "_build_aggregate_report",
                return_value=summary,
            ):
                with self.assertLogs("adminapi.views.companies", level="WARNING"):
                    response = self.view.report(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        release_lock.assert_called_once()

    @patch.object(AdminCompanyViewSet, "_release_report_lock")
    def test_cache_hit_avoids_rebuilding_same_filtered_aggregate(self, release_lock):
        request = self._request("mesto=Bratislava")
        self.view.request = request
        summary = {
            "count": 1,
            "report_mode": "light",
            "presets": [],
            "top_companies": [],
        }

        with patch.object(
            self.view,
            "_build_aggregate_report",
            return_value=summary,
        ) as build_report:
            first_response = self.view.report(request)
            second_response = self.view.report(request)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.data["count"], 1)
        self.assertEqual(second_response.data["filters_applied"], {"mesto": ["Bratislava"]})
        build_report.assert_called_once()
        release_lock.assert_called_once()

    @patch("adminapi.views.companies.time.sleep")
    @patch("adminapi.views.companies.cache")
    def test_concurrent_miss_waits_for_cached_summary(self, cache_mock, sleep_mock):
        request = self._request("mesto=Bratislava")
        self.view.request = request
        cache_mock.get.side_effect = [
            None,
            {"count": 7, "report_mode": "light", "presets": [], "top_companies": []},
        ]
        cache_mock.add.return_value = False

        with patch.object(self.view, "_build_aggregate_report") as build_report:
            response = self.view.report(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 7)
        cache_mock.add.assert_called_once()
        sleep_mock.assert_called_once()
        build_report.assert_not_called()

    @patch("adminapi.views.companies.time.monotonic", side_effect=[0, 31])
    @patch("adminapi.views.companies.cache")
    def test_waiter_timeout_returns_503_without_duplicate_aggregate(
        self, cache_mock, monotonic_mock
    ):
        request = self._request("mesto=Bratislava")
        self.view.request = request
        cache_mock.get.return_value = None
        cache_mock.add.return_value = False

        with patch.object(self.view, "_build_aggregate_report") as build_report:
            response = self.view.report(request)

        self.assertEqual(response.status_code, 503)
        self.assertIn("already being generated", response.data["detail"])
        build_report.assert_not_called()

    @patch("adminapi.views.companies.cache")
    def test_redis_lock_cleanup_compares_the_unique_token(self, cache_mock):
        backend_client = cache_mock._cache
        serializer = backend_client._serializer
        serializer.dumps.return_value = b"serialized-lock-token"
        redis_client = backend_client.get_client.return_value
        cache_mock.make_key.return_value = "prefix:report-lock"

        self.view._release_report_lock("report-lock", "unique-lock-token")

        redis_client.eval.assert_called_once()
        script, key_count, redis_key, serialized_token = redis_client.eval.call_args.args
        self.assertIn("redis.call('get', KEYS[1]) == ARGV[1]", script)
        self.assertEqual(key_count, 1)
        self.assertEqual(redis_key, "prefix:report-lock")
        self.assertEqual(serialized_token, b"serialized-lock-token")
        cache_mock.delete.assert_not_called()

    @patch("adminapi.views.companies.cache")
    def test_cache_error_is_logged_without_masking_aggregate_errors(self, cache_mock):
        request = self._request()
        self.view.request = request
        cache_mock.get.side_effect = ConnectionError("cache unavailable")

        with patch.object(
            self.view,
            "_build_aggregate_report",
            side_effect=RuntimeError("aggregate failed"),
        ):
            with self.assertLogs("adminapi.views.companies", level="WARNING"):
                with self.assertRaisesMessage(RuntimeError, "aggregate failed"):
                    self.view.report(request)
