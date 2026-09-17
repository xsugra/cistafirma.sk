from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.http import StreamingHttpResponse
from django.test import RequestFactory, TestCase

from adminapi.views.companies import AdminCompanyViewSet
from companies.admin import CompanyAdmin, MAX_SYNC_EXPORT_ROWS
from companies.models import Company


class AdminCompanyExportTests(TestCase):
    def setUp(self):
        self.view = AdminCompanyViewSet()
        self.company = Company.objects.create(
            ruz_id=910001,
            ico="91000001",
            nazov_UJ="Streaming Export s.r.o.",
        )

    def test_csv_export_is_streamed_and_contains_company_data(self):
        response = self.view._export_queryset(
            self.view._listing_queryset().filter(pk=self.company.pk),
            "csv",
        )

        self.assertIsInstance(response, StreamingHttpResponse)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="companies-report.csv"')
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("IČO", content)
        self.assertIn(self.company.ico, content)
        self.assertIn(self.company.nazov_UJ, content)

    def test_export_over_cap_is_rejected_before_queryset_serialization(self):
        queryset = MagicMock()
        queryset.count.return_value = self.view.MAX_SYNC_EXPORT_ROWS + 1

        response = self.view._export_queryset(queryset, "xlsx")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["max_rows"], self.view.MAX_SYNC_EXPORT_ROWS)
        self.assertIn("Zúžte filtre", response.data["detail"])
        queryset.order_by.assert_not_called()

    def test_django_admin_rejects_over_cap_before_xlsx_serialization(self):
        queryset = MagicMock()
        queryset.count.return_value = MAX_SYNC_EXPORT_ROWS + 1
        model_admin = CompanyAdmin(Company, AdminSite())

        with patch.object(model_admin, "message_user") as message_user:
            response = model_admin.export_to_xlsx(RequestFactory().post("/admin/"), queryset)

        self.assertIsNone(response)
        message_user.assert_called_once()
        self.assertIn("Zúžte filtre", message_user.call_args.args[1])
        queryset.iterator.assert_not_called()
