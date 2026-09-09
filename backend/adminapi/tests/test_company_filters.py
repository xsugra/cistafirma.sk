import json
from decimal import Decimal
from unittest.mock import patch

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


class AdminCompanyReportModeTests(TestCase):
    def test_light_mode_is_default_and_full_mode_is_explicit(self):
        view = AdminCompanyViewSet()

        class _Request:
            def __init__(self, params):
                self.query_params = params

        self.assertTrue(view._is_light_mode(_Request({})))
        self.assertTrue(view._is_light_mode(_Request({"light": "1"})))
        self.assertFalse(view._is_light_mode(_Request({"mode": "full"})))


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
