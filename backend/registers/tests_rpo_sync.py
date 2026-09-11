from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from companies.models import Company
from registers.integrations.rpo_client import (
    RpoEntityNotFound,
    RpoClient,
    RpoEntity,
    RpoSourceRegister,
)
from registers.models import OrsrCompanyProfile
from registers.services.rpo_sync import NOT_STATED, RpoSyncService


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


class RpoValueMappingTests(TestCase):
    """A value that means "absent" must not be stored *as* a value.

    Measured 2026-09-11: RPO answers `"Neuvedené"` for an IČO it does not have
    (every one of the 87 profile-less `801` obec/mesto companies in the ORSR
    queue). `"Neuvedené"` is a truthy nine-character string, so `entity.ico or
    company.ico` never fell back and the sentinel went into `ico = varchar(8)`
    -- where Postgres refused it and the **whole profile** was lost.

    That refusal is the only reason the defect was visible. One character more
    of column width and the profile would have been saved, quietly, with an
    IČO of `"Neuvedené"` -- which is why the length guard below is the smaller
    half of this fix and the sentinel check is the half that matters.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=8801,
            ico="88010000",
            nazov_UJ="Obec Neuvedená",
            pravna_forma="801",
        )

    def _sync(self, entity):
        client = MagicMock()
        client.get_entity_by_ico.return_value = entity
        service = RpoSyncService(client=client)
        with patch.object(RpoSyncService, "_extract_persons"):
            return service.sync_company(self.company)

    def _entity(self, **kwargs):
        defaults = {
            "rpo_id": 123,
            "ico": "88010000",
            "current_name": "Obec Neuvedená",
            "legal_form": "Obec",
        }
        defaults.update(kwargs)
        return RpoEntity(**defaults)

    def test_the_sentinel_ico_becomes_an_absence_and_the_profile_survives(self):
        """The measured failure: nine characters into `varchar(8)`, profile lost."""
        profile = self._sync(self._entity(ico=NOT_STATED))

        self.assertEqual(profile.ico, self.company.ico)
        self.assertTrue(OrsrCompanyProfile.objects.filter(company=self.company).exists())

    def test_the_sentinel_is_refused_even_where_it_would_fit(self):
        """The half a width check cannot catch.

        `pravna_forma` is `varchar(200)`, so `"Neuvedené"` fits and would be
        stored. A reader of that row would see a legal form. It is not one.
        """
        profile = self._sync(self._entity(legal_form=NOT_STATED))

        self.assertEqual(profile.pravna_forma, "")

    def test_a_sentinel_in_a_sparse_field_is_an_absence_too(self):
        profile = self._sync(self._entity(current_name=NOT_STATED))

        self.assertEqual(profile.obchodne_meno, "")

    def test_a_value_wider_than_its_column_is_refused_not_truncated(self):
        """`Ministerstvo školstva a národnej osvety v Bratislave No33.121/IV/1929`.

        Taken from company 36289, where `_extract_oddiel` returns its 61-character
        first segment into `oddiel = varchar(50)`. Truncating would store a string
        nobody wrote, and the row would then look complete.
        """
        number = (
            "Ministerstvo školstva a národnej osvety v Bratislave No33.121/IV/1929"
        )
        profile = self._sync(
            self._entity(source_register=RpoSourceRegister(registration_number=number))
        )

        self.assertEqual(profile.oddiel, "")

    def test_a_refused_value_is_not_refused_silently(self):
        """Refusing is right; refusing without a trace is the defect class again."""
        number = "X" * 61

        with self.assertLogs("registers.services.rpo_sync", level="WARNING") as logs:
            self._sync(
                self._entity(
                    source_register=RpoSourceRegister(registration_number=number)
                )
            )

        self.assertIn("refusing oddiel", "\n".join(logs.output))
        self.assertIn("88010000", "\n".join(logs.output))

    def test_the_raw_registration_number_survives_a_refusal(self):
        """`oddiel` is *parsed* from it, so parsing is where the information dies.

        The refusal must not be the second loss: the profile keeps the source
        string whole, which is the only place it still exists.
        """
        number = "X" * 61
        profile = self._sync(
            self._entity(source_register=RpoSourceRegister(registration_number=number))
        )

        self.assertEqual(
            profile.raw_payload["source_register"]["registration_number"], number
        )

    def test_a_normal_registration_number_still_parses(self):
        """The regression guard: nothing above may change the ordinary case."""
        profile = self._sync(
            self._entity(
                source_register=RpoSourceRegister(registration_number="Sro/12345/B")
            )
        )

        self.assertEqual(profile.oddiel, "Sro")
        self.assertEqual(profile.oddiel_type, "sro")
        self.assertEqual(profile.vlozka_cislo, "12345")

    def test_a_real_ico_is_stored_unchanged(self):
        profile = self._sync(self._entity(ico="12345678"))

        self.assertEqual(profile.ico, "12345678")

