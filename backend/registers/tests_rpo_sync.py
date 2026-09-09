from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from registers.integrations.rpo_client import RpoEntityNotFound, RpoClient
from registers.services.rpo_sync import RpoSyncService


class RpoClientTests(SimpleTestCase):
    @patch.object(RpoClient, "search_by_ico", return_value=123)
    @patch.object(RpoClient, "get_entity")
    def test_get_entity_by_ico_returns_none_when_detail_is_missing(
        self,
        mock_get_entity,
        mock_search_by_ico,
    ):
        mock_get_entity.side_effect = RpoEntityNotFound("RPO entity 123 not found")

        client = RpoClient()
        self.assertIsNone(client.get_entity_by_ico("00596965"))
        mock_search_by_ico.assert_called_once_with("00596965")
        mock_get_entity.assert_called_once_with(123)


class RpoSyncServiceTests(SimpleTestCase):
    @patch("registers.services.rpo_sync.OrsrSyncService")
    def test_sync_company_falls_back_to_orsr_when_rpo_returns_no_entity(
        self,
        MockOrsrSyncService,
    ):
        company = MagicMock(ico="00596965")
        fallback_profile = MagicMock()
        client = MagicMock()
        client.get_entity_by_ico.return_value = None
        MockOrsrSyncService.return_value.sync_company.return_value = fallback_profile

        service = RpoSyncService(client=client)
        result = service.sync_company(company)

        self.assertIs(result, fallback_profile)
        client.get_entity_by_ico.assert_called_once_with("00596965")
        MockOrsrSyncService.return_value.sync_company.assert_called_once_with(company)

